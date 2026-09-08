"""pipeline.tests.test_fold_roundtrip — the Phase C gate, as a runnable test.

Why this file exists: pipeline/tests/test_fold_harness.py proves the FOLD
HARNESS (pipeline/blocks.py, pipeline/run_fold.py, pipeline/prolog/driver.pl)
against a throwaway mini-grammar it owns. pipeline/tests/test_pig_grammar.py
and test_hive_grammar.py prove each real grammar folds+round-trips on its
own corpus, driving swipl directly (they do not touch run_fold.py). This
file is the Phase C GATE ITSELF: it runs the real two-command gate —

    python3 -m pipeline.run_fold pig
    python3 -m pipeline.run_fold hive

in-process (pipeline.run_fold.main(["pig"]) / (["hive"]), same code path,
same default paths — see test_corpus_lossless.py's identical pattern for
run_tokenise) — and proves everything the gate promises, over ALL 13 corpus
files (7 pig — 6 small + 1 medium, see corpus/pig/medium/
p07_txn_region_tier.pig — + 6 hive), not just the harness's 2-statement
fixture:

  1. Every statement folds to a Term: zero failed(Seq) anywhere (folded_n
     == n for every file, both languages).
  2. Every statement passes the print -> retokenise -> refold TERM FIXPOINT
     (roundtrip_n == n for every file — the actual round-trip check, not
     just "it printed something").
  3. Every file's out/ir/<lang>/<stem>.node4.json exists, is valid JSON,
     and has exactly one record per statement that folded.
  4. Every file's BlockIds obey the 7-15 line law (pipeline.blocks.
     assign_blocks re-applied to the real statement spans, cross-checked
     against the "block" field actually written into node4.json).
  5. Every file's trace byte ranges slice the ORIGINAL SOURCE BYTES to
     exactly the statement text: for 5 random statements per language
     (fixed seed, so the sample is reproducible), source_bytes[b0:b1] is
     read back off disk and RETOKENISED through the same spec; the
     resulting grammar-kind (kind, text) sequence must equal the
     statement's own original token sequence exactly — the strongest form
     of "the joined token texts match", since it proves no adjacent
     statement's text leaked into the slice and no byte was dropped.

Tokens and grammar are regenerated fresh at the top of this run (same
run_tokenise.main() / gen_prolog.generate() calls the earlier phases use)
so this test never trusts stale out/ artifacts left over from a manual run
— it reproduces the gate from source every time it runs.

Run: python3 -m pipeline.tests.test_fold_roundtrip
(needs `swipl` on PATH; run `eval "$(/usr/libexec/path_helper)"` first in a
fresh shell if it isn't, same as this track's other swipl-driven work)
"""
import json
import os
import random
import re
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from pipeline import gen_prolog, run_fold, run_tokenise
from pipeline.blocks import assign_blocks, MAX_BLOCK_LINES, MIN_BLOCK_LINES
from pipeline.run_fold import split_statements

REPO_ROOT = Path(__file__).resolve().parents[2]

CORPUS_STEMS = {
    "pig": [
        "p01_load_filter_store",
        "p02_foreach_arithmetic",
        "p03_group_agg",
        "p04_join",
        "p05_order_limit_distinct",
        "p06_union_split",
        "p07_txn_region_tier",
    ],
    "hive": [
        "h01_create_select",
        "h02_where_case",
        "h03_group_having",
        "h04_join_two_tables",
        "h05_insert_union",
        "h06_nested_subquery",
    ],
}
LANGS = ["pig", "hive"]

# Fixed seed: "5 random statements per language" must be reproducible from
# run to run, not a flaky sample that only sometimes catches a bug.
SAMPLE_SEED = 20260824
SAMPLE_SIZE = 5

_ROW_RE = re.compile(r"^(\S+)\s+(\d+)/(\d+)\s+(\d+)/(\d+)\s+(OK|FAIL)\s*$")


def _swipl_available():
    import subprocess
    try:
        subprocess.run(["swipl", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _chdir_repo_root(fn, *a, **kw):
    """Run fn(*a, **kw) with cwd == REPO_ROOT, restoring cwd afterwards —
    both run_tokenise and run_fold default their I/O paths (corpus/<lang>,
    out/tokens/<lang>, out/grammar/<lang>.pl, out/ir/<lang>) relative to
    the CURRENT directory, exactly like a human typing the gate command
    from this repo's root."""
    cwd = Path.cwd()
    try:
        os.chdir(REPO_ROOT)
        return fn(*a, **kw)
    finally:
        os.chdir(cwd)


# ---------------------------------------------------------------------
# module-level cache: regenerate tokens+grammar and run the gate ONCE,
# every test function below reads the results (either the parsed gate
# table or the on-disk artifacts the gate just wrote) rather than
# re-running swipl per assertion.

_GATE_CACHE = {}


def _run_gate():
    if _GATE_CACHE:
        return _GATE_CACHE

    # 1. regenerate out/tokens/<lang> and out/grammar/<lang>.pl fresh, the
    #    same two generator steps the earlier phases run — this test never
    #    trusts stale out/ files left over from a previous manual run.
    for lang in LANGS:
        rc = _chdir_repo_root(run_tokenise.main, [lang])
        assert rc == 0, f"run_tokenise {lang} exited {rc} (expected 0)"
        gen_prolog.generate(lang)

    # 2. run the actual gate command, in-process, capturing stdout so the
    #    per-file table can be parsed for structured assertions.
    gate = {}
    for lang in LANGS:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = _chdir_repo_root(run_fold.main, [lang])
        output = buf.getvalue()
        rows = {}
        for line in output.splitlines():
            m = _ROW_RE.match(line)
            if m:
                stem, folded_n, n1, roundtrip_n, n2, verdict = m.groups()
                rows[stem] = {
                    "folded_n": int(folded_n), "n": int(n1),
                    "roundtrip_n": int(roundtrip_n), "n2": int(n2),
                    "verdict": verdict,
                }
        gate[lang] = {"rc": rc, "output": output, "rows": rows}

    _GATE_CACHE.update(gate)
    return _GATE_CACHE


# ---------------------------------------------------------------------
# gate point 1+2 combined: the literal CLI, its exit code, and the parsed
# per-file folded/roundtrip counts (zero failed(Seq), full term fixpoint)

def test_run_fold_cli_exits_zero_for_every_language():
    if not _swipl_available():
        return
    gate = _run_gate()
    for lang in LANGS:
        assert gate[lang]["rc"] == 0, (
            f"python3 -m pipeline.run_fold {lang} exited {gate[lang]['rc']} "
            f"(expected 0)\n{gate[lang]['output']}"
        )
        assert "ALL FOLDED AND ROUND-TRIPPED: true" in gate[lang]["output"], (
            f"{lang}: gate did not print the all-true summary line:\n{gate[lang]['output']}"
        )


def test_every_corpus_file_appears_in_the_gate_table():
    if not _swipl_available():
        return
    gate = _run_gate()
    for lang in LANGS:
        rows = gate[lang]["rows"]
        missing = [s for s in CORPUS_STEMS[lang] if s not in rows]
        assert not missing, f"{lang}: {missing} never appeared in the gate's own output table"
        extra = sorted(set(rows) - set(CORPUS_STEMS[lang]))
        assert not extra, f"{lang}: gate table has unexpected extra file(s) {extra}"


def test_every_statement_folds_zero_failed_seq():
    """Gate point 1: folded_n == n for every one of the 12 files — no
    failed(Seq) anywhere. n is also asserted > 0 so an empty/misparsed
    table row can't pass this vacuously."""
    if not _swipl_available():
        return
    gate = _run_gate()
    for lang in LANGS:
        for stem in CORPUS_STEMS[lang]:
            row = gate[lang]["rows"][stem]
            assert row["n"] > 0, f"{lang}/{stem}: zero statements found — table row is vacuous"
            assert row["folded_n"] == row["n"], (
                f"{lang}/{stem}: folded {row['folded_n']}/{row['n']} — "
                f"some statement(s) failed to fold\n{gate[lang]['output']}"
            )


def test_every_statement_passes_the_print_retokenise_refold_fixpoint():
    """Gate point 2: roundtrip_n == n for every one of the 12 files — the
    full print -> retokenise -> refold term fixpoint, not just a fold."""
    if not _swipl_available():
        return
    gate = _run_gate()
    for lang in LANGS:
        for stem in CORPUS_STEMS[lang]:
            row = gate[lang]["rows"][stem]
            assert row["roundtrip_n"] == row["n"], (
                f"{lang}/{stem}: roundtrip {row['roundtrip_n']}/{row['n']} — "
                f"some statement(s) failed the print->retokenise->refold fixpoint\n"
                f"{gate[lang]['output']}"
            )
            assert row["verdict"] == "OK", f"{lang}/{stem}: verdict {row['verdict']!r}, expected OK"


# ---------------------------------------------------------------------
# gate point 3: node4.json exists for every corpus file, one record per
# folded statement

def test_node4_json_exists_and_has_one_record_per_folded_statement():
    if not _swipl_available():
        return
    gate = _run_gate()
    for lang in LANGS:
        out_dir = REPO_ROOT / "out" / "ir" / lang
        for stem in CORPUS_STEMS[lang]:
            json_path = out_dir / f"{stem}.node4.json"
            pl_path = out_dir / f"{stem}.node4.pl"
            assert json_path.is_file(), f"{lang}/{stem}: missing {json_path}"
            assert pl_path.is_file(), f"{lang}/{stem}: missing {pl_path}"
            node4 = json.loads(json_path.read_text(encoding="utf-8"))
            row = gate[lang]["rows"][stem]
            assert len(node4) == row["folded_n"], (
                f"{lang}/{stem}: node4.json has {len(node4)} records, "
                f"expected {row['folded_n']} (folded_n)"
            )
            for rec in node4:
                assert set(rec.keys()) == {"block", "seq", "term", "trace", "comments"}, rec
                assert set(rec["trace"].keys()) == {"file", "l0", "l1", "b0", "b1"}, rec


# ---------------------------------------------------------------------
# gate point 4: BlockIds obey the 7-15 line law over every real corpus file

def _load_stmts_and_node4(lang, stem):
    tokens_path = REPO_ROOT / "out" / "tokens" / lang / f"{stem}.tokens.json"
    data = json.loads(tokens_path.read_text(encoding="utf-8"))
    stmts = split_statements(data["tokens"])
    node4_path = REPO_ROOT / "out" / "ir" / lang / f"{stem}.node4.json"
    node4 = json.loads(node4_path.read_text(encoding="utf-8"))
    return data, stmts, node4


def test_block_ids_obey_the_seven_to_fifteen_line_law():
    if not _swipl_available():
        return
    _run_gate()
    for lang in LANGS:
        for stem in CORPUS_STEMS[lang]:
            _data, stmts, node4 = _load_stmts_and_node4(lang, stem)
            blocks = assign_blocks(stmts)
            stmt_by_seq = {s["seq"]: s for s in stmts}
            last_block_id = blocks[-1][0] if blocks else None
            for block_id, seqs in blocks:
                l0 = min(stmt_by_seq[s]["l0"] for s in seqs)
                l1 = max(stmt_by_seq[s]["l1"] for s in seqs)
                span = l1 - l0 + 1
                single_oversized = len(seqs) == 1 and span > MAX_BLOCK_LINES
                # a block that reached the file's end without ever hitting
                # MIN_BLOCK_LINES is still contract-legal (blocks.py's own
                # "6 one-line statements -> one block only if file ends"
                # case) — every other block must land inside [7, 15].
                is_final_short_block = block_id == last_block_id and span < MIN_BLOCK_LINES
                ok = single_oversized or is_final_short_block or (
                    MIN_BLOCK_LINES <= span <= MAX_BLOCK_LINES
                )
                assert ok, (
                    f"{lang}/{stem}: block {block_id} (seqs {seqs}) spans "
                    f"{span} lines (l0={l0}, l1={l1}) — violates the 7-15 line law"
                )
                assert span <= MAX_BLOCK_LINES or single_oversized, (
                    f"{lang}/{stem}: block {block_id} spans {span} > "
                    f"{MAX_BLOCK_LINES} lines with {len(seqs)} statement(s) — "
                    f"the cap may only be exceeded by a single oversized statement"
                )

            # cross-check: node4.json's own "block" field for each seq must
            # equal what assign_blocks assigns when re-run on the same
            # statement spans right now — no drift between what run_fold
            # wrote and what the law actually computes.
            block_of_seq = {}
            for block_id, seqs in blocks:
                for s in seqs:
                    block_of_seq[s] = block_id
            for rec in node4:
                expected = block_of_seq.get(rec["seq"])
                assert rec["block"] == expected, (
                    f"{lang}/{stem}: node4 seq {rec['seq']} block "
                    f"{rec['block']!r} != recomputed {expected!r}"
                )


# ---------------------------------------------------------------------
# gate point 5: trace byte ranges slice the original source bytes to
# EXACTLY the statement text — 5 random statements per language, fixed seed

def test_trace_byte_ranges_slice_source_to_exact_statement_text():
    if not _swipl_available():
        return
    _run_gate()

    from pipeline.specs.hive import LANG as HIVE_SPEC
    from pipeline.specs.pig import LANG as PIG_SPEC
    from pipeline.tokeniser import tokenise

    specs = {"pig": PIG_SPEC, "hive": HIVE_SPEC}
    grammar_kinds = run_fold.GRAMMAR_KINDS

    rng = random.Random(SAMPLE_SEED)
    checked = 0
    for lang in LANGS:
        candidates = []  # (stem, stmt, source_bytes)
        for stem in CORPUS_STEMS[lang]:
            data, stmts, node4 = _load_stmts_and_node4(lang, stem)
            source_bytes = Path(data["file"]).read_bytes()
            node4_by_seq = {rec["seq"]: rec for rec in node4}
            for st in stmts:
                if st["seq"] in node4_by_seq:  # only statements that folded have a trace
                    candidates.append((stem, st, source_bytes, node4_by_seq[st["seq"]]))

        assert len(candidates) >= SAMPLE_SIZE, (
            f"{lang}: only {len(candidates)} traced statements available, "
            f"need at least {SAMPLE_SIZE} to sample"
        )
        sample = rng.sample(candidates, SAMPLE_SIZE)
        for stem, st, source_bytes, rec in sample:
            b0, b1 = rec["trace"]["b0"], rec["trace"]["b1"]
            # the trace's own b0/b1 must equal the statement's first/last
            # grammar token span (what run_fold actually derived them from)
            assert (b0, b1) == (st["b0"], st["b1"]), (
                f"{lang}/{stem} seq {st['seq']}: trace b0/b1 ({b0},{b1}) != "
                f"statement span ({st['b0']},{st['b1']})"
            )
            assert 0 <= b0 < b1 <= len(source_bytes), (
                f"{lang}/{stem} seq {st['seq']}: b0/b1 ({b0},{b1}) out of "
                f"range for a {len(source_bytes)}-byte source file"
            )
            sliced_text = source_bytes[b0:b1].decode("utf-8")

            # retokenise the raw slice through the SAME spec used to tokenise
            # the whole file, and compare the resulting grammar-kind (kind,
            # text) sequence against the statement's own original tokens —
            # the strongest form of "the joined token texts match": it
            # proves the slice is exactly this statement's text, with
            # nothing from a neighboring statement leaked in and no byte of
            # this statement dropped.
            retoks = tokenise(specs[lang], sliced_text)
            retoks_grammar = [(t["kind"], t["text"]) for t in retoks if t["kind"] in grammar_kinds]
            original_grammar = [(t["kind"], t["text"]) for t in st["tokens"]]
            assert retoks_grammar == original_grammar, (
                f"{lang}/{stem} seq {st['seq']}: retokenised slice "
                f"{retoks_grammar!r} != original tokens {original_grammar!r}\n"
                f"slice was: {sliced_text!r}"
            )
            checked += 1

    assert checked == len(LANGS) * SAMPLE_SIZE


# ---------------------------------------------------------------------

def test_every_test_in_this_file_is_registered_to_run():
    """Same self-check as test_corpus_lossless.py: a test defined here but
    left out of TESTS would silently never run — this catches that."""
    registered = {t.__name__ for t in TESTS}
    defined = {
        name for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    }
    missing = sorted(defined - registered)
    assert not missing, (
        f"{len(missing)} test(s) defined but never run — add them to TESTS: {missing}"
    )


TESTS = [
    test_run_fold_cli_exits_zero_for_every_language,
    test_every_corpus_file_appears_in_the_gate_table,
    test_every_statement_folds_zero_failed_seq,
    test_every_statement_passes_the_print_retokenise_refold_fixpoint,
    test_node4_json_exists_and_has_one_record_per_folded_statement,
    test_block_ids_obey_the_seven_to_fifteen_line_law,
    test_trace_byte_ranges_slice_source_to_exact_statement_text,
    # the registry checks itself — keep this last
    test_every_test_in_this_file_is_registered_to_run,
]


def main():
    # This file IS the Phase C gate. Every gate point below needs swipl, and
    # each test returns early without it — which would be reported as PASS
    # and print a green "ALL TESTS PASSED" for a gate that never ran. Refuse
    # to run at all instead, the same hard stop test_pig_grammar.py and
    # test_hive_grammar.py already use.
    if not _swipl_available():
        print("swipl not on PATH — the Phase C gate cannot run without it.\n"
              "Run: eval \"$(/usr/libexec/path_helper)\" first")
        return 1

    failures = []
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            failures.append((t.__name__, str(e)))
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            failures.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
        else:
            print(f"PASS  {t.__name__}")

    print()
    if failures:
        print(f"{len(failures)}/{len(TESTS)} FAILED")
        return 1
    print(f"ALL {len(TESTS)} TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
