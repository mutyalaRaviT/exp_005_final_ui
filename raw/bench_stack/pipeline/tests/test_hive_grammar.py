"""pipeline.tests.test_hive_grammar — THROWAWAY proof for out/grammar/hive.pl,
the grammar pipeline/gen_prolog.py compiles from pipeline/specs/hive.py's
`statements`/`rules`/`ladder`/`forms`/`expr_leaves`. This is the vocabulary
+generator agent's own proof, not the fold-harness agent's — it does NOT
touch (or import) pipeline/prolog/driver.pl or pipeline/run_fold.py, which
belong to that other agent; it drives swipl directly, on the real token
JSONs already sitting in out/tokens/hive/*.tokens.json. Mirrors
pipeline.tests.test_pig_grammar exactly (same proof shape, same driving
style), just pointed at hive.py's grammar and corpus.

What it proves, per corpus/hive/small/*.hql file:
  1. FOLD — every statement (tokens between eos markers, comment/whitespace
     filtered, per the phase-C contract) parses via stmt(Term, Tokens, [])
     to a term.
  2. ROUND-TRIP (term fixpoint, the phase-C pass mark) — print_stmt(Term,
     Texts), join Texts with single spaces, retokenise that text with
     pipeline.tokeniser + pipeline.specs.hive's own LANG spec, refold ->
     Term2; PASS iff Term2 == Term (compared as writeq text, which is
     deterministic for a ground term).

Run: python3 -m pipeline.tests.test_hive_grammar
(needs `swipl` on PATH — same as this track's other swipl-driven work)
"""
import json
import subprocess
import sys
from pathlib import Path

from pipeline.gen_prolog import plq
from pipeline.tokeniser import tokenise
from pipeline.specs.hive import LANG as HIVE_LANG

ROOT = Path(__file__).resolve().parents[2]
GRAMMAR = ROOT / "out" / "grammar" / "hive.pl"
TOKENS_DIR = ROOT / "out" / "tokens" / "hive"
CORPUS_DIR = ROOT / "corpus" / "hive" / "small"

GRAMMAR_KINDS = {"keyword", "word", "number", "string", "symbol"}


def split_statements(tokens):
    """Real token dicts (as read from a .tokens.json) -> list of statements,
    each a list of (kind, text) pairs, comment/whitespace/eos stripped, an
    empty segment (a ';' at EOF's double-eos, or an all-trivia segment)
    skipped — same contract point exp_014's fold harness proves."""
    stmts, cur = [], []
    for t in tokens:
        if t["kind"] == "eos":
            grammar_only = [(x["kind"], x["text"]) for x in cur if x["kind"] in GRAMMAR_KINDS]
            if grammar_only:
                stmts.append(grammar_only)
            cur = []
        else:
            cur.append(t)
    return stmts


def fold_via_swipl(tokens):
    """tokens: [(kind,text), ...] one statement. -> (term_text, joined_print_text)
    or (None, None) if the parse itself fails. `term_text` is Term's writeq
    text; `joined_print_text` is print_stmt's canonical texts joined with
    single spaces (ready to feed straight back through the tokeniser)."""
    toks_pl = ", ".join(f"tok({k},{plq(t)})" for k, t in tokens)
    goal = (
        f"consult('{GRAMMAR.as_posix()}'), "
        f"( catch(stmt(Term,[{toks_pl}],[]),_,fail) -> "
        f"    with_output_to(atom(TA), writeq(Term)), "
        f"    ( catch(print_stmt(Term,Texts),_,fail) -> "
        f"        atomic_list_concat(Texts,' ',Joined), "
        f"        format('~w~n~w~n', [TA, Joined]) "
        f"    ; format('~w~nPRINT_FAIL~n', [TA]) ) "
        f"; format('PARSE_FAIL~n~n') ), halt."
    )
    proc = subprocess.run(["swipl", "-q", "-g", goal], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"swipl crashed: {proc.stderr}\ngoal: {goal}")
    lines = proc.stdout.split("\n")
    term_text = lines[0] if lines else ""
    print_line = lines[1] if len(lines) > 1 else ""
    if term_text == "PARSE_FAIL" or term_text == "":
        return None, None
    if print_line == "PRINT_FAIL":
        return term_text, None
    return term_text, print_line


def fold_and_roundtrip_file(stem):
    """-> dict(n, folded_n, roundtrip_n, failures: [(seq, reason)])."""
    data = json.loads((TOKENS_DIR / f"{stem}.tokens.json").read_text(encoding="utf-8"))
    assert data["lossless"] is True
    stmts = split_statements(data["tokens"])
    n = len(stmts)
    folded_n = roundtrip_n = 0
    failures = []
    for seq, toks in enumerate(stmts, start=1):
        term1, joined = fold_via_swipl(toks)
        if term1 is None:
            failures.append((seq, "did not fold"))
            continue
        folded_n += 1
        if joined is None:
            failures.append((seq, "print_stmt failed"))
            continue
        retok = tokenise(HIVE_LANG, joined)
        retoks = [(t["kind"], t["text"]) for t in retok if t["kind"] in GRAMMAR_KINDS]
        term2, _joined2 = fold_via_swipl(retoks)
        if term2 == term1:
            roundtrip_n += 1
        else:
            failures.append((seq, f"roundtrip mismatch: {term1!r} != {term2!r} (printed {joined!r})"))
    return {"n": n, "folded_n": folded_n, "roundtrip_n": roundtrip_n, "failures": failures}


CORPUS_STEMS = [
    "h01_create_select",
    "h02_where_case",
    "h03_group_having",
    "h04_join_two_tables",
    "h05_insert_union",
    "h06_nested_subquery",
]


def _swipl_available():
    try:
        subprocess.run(["swipl", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def main():
    if not _swipl_available():
        print("swipl not on PATH — run: eval \"$(/usr/libexec/path_helper)\" first")
        return 1
    if not GRAMMAR.is_file():
        print(f"missing {GRAMMAR} — run: python3 -m pipeline.gen_prolog hive")
        return 1

    all_ok = True
    total_n = total_folded = total_roundtrip = 0
    for stem in CORPUS_STEMS:
        r = fold_and_roundtrip_file(stem)
        total_n += r["n"]
        total_folded += r["folded_n"]
        total_roundtrip += r["roundtrip_n"]
        ok = r["folded_n"] == r["n"] and r["roundtrip_n"] == r["n"]
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {stem}: folded {r['folded_n']}/{r['n']}, roundtrip {r['roundtrip_n']}/{r['n']}")
        for seq, reason in r["failures"]:
            print(f"      seq {seq}: {reason}")

    print()
    print(f"TOTAL: folded {total_folded}/{total_n}, roundtrip {total_roundtrip}/{total_n}")
    if all_ok:
        print("ALL PASS")
        return 0
    print("SOME FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
