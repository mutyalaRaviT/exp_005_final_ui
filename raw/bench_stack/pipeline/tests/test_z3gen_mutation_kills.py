"""pipeline.tests.test_z3gen_mutation_kills — Fix 6: turn the reviewer's
mutation-testing find into a PERMANENT regression test.

Why this file exists: an Opus reviewer took the REAL generated
out/pyspark/pig/p07_txn_region_tier.py and injected one plausible
Pig->PySpark translation bug at a time (M1-M9 below), then checked
whether DataMatch still said PASS against the REAL `pig -x local`
reference. Before Fix 1/2/3 (see pipeline/z3gen/gen.py's module
docstring and CLAUDE.md's fix list), 8 of 9 slipped through undetected —
the fixture was too thin to observe most of the FILTER/JOIN chain at
all. This module makes that adversarial check permanent: for each
mutation, it patches the real generated source (never pipeline/
datamatch.py's comparison logic, and never the fixture data — see the
"no loosening the checker" rule in CLAUDE.md), runs the mutated program
for real, and asserts DataMatch's own row-multiset comparison
(pipeline.datamatch.compare_rows) against the real Pig reference now
says FAIL for at least one output. A mutation that turns out to be a
genuine semantic no-op on this exact fixture (M8, and — discovered while
writing this suite — M6) is not asserted FAIL; each is called out by its
own test with a comment explaining exactly why, and what would be needed
to make it observable.

How a mutation is applied: a UNIQUE, hand-verified substring (or, for
M3's precedence rewrite, a whole-line regex) is replaced in a fresh copy
of the real generated source's TEXT — never in pipeline/codegen itself,
never in the fixture CSVs. Every mutator asserts it found exactly the
substring(s) it expected before mutating, so a future codegen change
that silently reshapes the generated line (e.g. reformats the boolean
tree) fails LOUDLY here (as an assertion in the mutator) instead of
silently no-oping the whole test.

Isolation: each mutated copy is written to a temp file and run with cwd
= REPO_ROOT (so its baked-in relative corpus/... input paths resolve),
but its STORE write calls are text-patched to an isolated temp output
directory first — so a mutation run never touches, and can never
clobber, the real out/pyspark_out/pig/p07_txn_region_tier/ tree the
OTHER tests (test_z3gen_medium_pig.py, test_e2e_datamatch.py) depend on.
The comparison itself reuses pipeline.datamatch.read_rows/compare_rows
directly against the real out/pig/p07_txn_region_tier/<output>/ reference
already on disk (the real `pig -x local` run) — this module never calls
pipeline.datamatch.main() and never touches reports/e2e_status.json.

Run: .venv/bin/python3 -m pipeline.tests.test_z3gen_mutation_kills
     .venv/bin/python3 -m pytest pipeline/tests/test_z3gen_mutation_kills.py -q
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline import datamatch

REPO_ROOT = Path(__file__).resolve().parents[2]
STEM = "p07_txn_region_tier"
REAL_PY = REPO_ROOT / "out" / "pyspark" / "pig" / f"{STEM}.py"
REF_ROOT = REPO_ROOT / "out" / "pig" / STEM  # real `pig -x local` reference
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"
OUTPUTS = ["qualifying_txn", "gold_txn", "region_summary"]
ORIG_OUT_PREFIX = f"out/pyspark_out/pig/{STEM}/"


def _load_real_source():
    assert REAL_PY.is_file(), (
        f"missing generated file: {REAL_PY} "
        f"(run pipeline.run_codegen pig --file {STEM} first)"
    )
    return REAL_PY.read_text(encoding="utf-8")


def _sub_once(text, old, new, label):
    """Plain substring replace, but LOUD if the codegen output ever
    stops matching what this mutator expects — a silently-skipped
    mutator would be worse than a red test."""
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly 1 occurrence of {old!r}, found {n}"
    return text.replace(old, new, 1)


_QUALIFYING_LINE_RE = re.compile(
    r'^qualifying_txn = positive_txn\.filter\(.*\)$', re.MULTILINE
)


def _mutate_M1_filter1_gt_to_ge(text):
    """FILTER 1: `amount > 0.0` -> `amount >= 0.0`."""
    return _sub_once(
        text,
        '(F.col("amount") > F.lit(0.0))',
        '(F.col("amount") >= F.lit(0.0))',
        "M1",
    )


def _mutate_M2_gold_gt200_to_ge(text):
    """FILTER 3: `amount > 200.0` -> `amount >= 200.0`."""
    return _sub_once(
        text,
        'F.col("amount") > F.lit(200.0)',
        'F.col("amount") >= F.lit(200.0)',
        "M2",
    )


def _mutate_M3_or_and_precedence(text):
    """`(A and B) or C` -> `A and (B or C)` for FILTER 2's condition.
    Rewrites the whole qualifying_txn line rather than patching a
    substring in place: the two structures don't share a common paren
    nesting, so there is no single-token edit that expresses this."""
    new_line = (
        'qualifying_txn = positive_txn.filter((F.col("amount") > F.lit(100.0)) & '
        '((F.col("region") == F.lit(\'EAST\')) | (F.col("channel") == F.lit(\'ONLINE\'))))'
    )
    mutated, n = _QUALIFYING_LINE_RE.subn(lambda _m: new_line, text)
    assert n == 1, f"M3: expected exactly 1 qualifying_txn filter line, found {n}"
    return mutated


# The three chararray `==` comparisons a case/whitespace mutation can act
# on — every OTHER `==` in this script (the JOIN key) compares two
# F.col(...)s, never a F.col(...) literal pair, so this list is exactly
# and only FILTER 2's and FILTER 3's string equalities.
_STR_EQ_TARGETS = [
    ('F.col("region") == F.lit(\'EAST\')', "region", "EAST"),
    ('F.col("channel") == F.lit(\'ONLINE\')', "channel", "ONLINE"),
    ('F.col("customer_tier") == F.lit(\'GOLD\')', "customer_tier", "GOLD"),
]


def _mutate_M4_case_insensitive_eq(text):
    """Add .lower() to both sides of every chararray `==`."""
    for old, col, lit in _STR_EQ_TARGETS:
        new = f'F.lower(F.col("{col}")) == F.lower(F.lit(\'{lit}\'))'
        text = _sub_once(text, old, new, "M4")
    return text


def _mutate_M5_trim_eq(text):
    """Add .strip()-equivalent (F.trim) to both sides of every chararray `==`."""
    for old, col, lit in _STR_EQ_TARGETS:
        new = f'F.trim(F.col("{col}")) == F.trim(F.lit(\'{lit}\'))'
        text = _sub_once(text, old, new, "M5")
    return text


def _mutate_M6_join_inner_to_left(text):
    """inner join -> left join."""
    return _sub_once(text, 'how="inner"', 'how="left"', "M6")


def _mutate_M7_eq_to_startswith(text):
    """`region == 'EAST'` -> `region.startswith('EA')`."""
    return _sub_once(
        text,
        'F.col("region") == F.lit(\'EAST\')',
        'F.col("region").startswith(\'EA\')',
        "M7",
    )


def _mutate_M8_count_col_to_star(text):
    """`COUNT(txn_id)` -> `count(1)` (count(*) equivalent)."""
    return _sub_once(
        text,
        'F.count(F.col("raw_txn.txn_id"))',
        'F.count(F.lit(1))',
        "M8",
    )


def _mutate_M9_filter2_or_to_and(text):
    """The OR in FILTER 2's condition -> AND (a token swap right before the
    channel comparison — the reviewer's own pre-fix run already caught this
    one; this test confirms it is STILL caught after Fix 1/2/3)."""
    return _sub_once(
        text,
        "EAST')))) | (F.col(\"channel\")",
        "EAST')))) & (F.col(\"channel\")",
        "M9",
    )


# name -> (mutator, expect_caught). expect_caught=False means: run it,
# but do NOT assert FAIL — see that mutation's own test for why it is a
# genuine no-op on this exact fixture, and what would make it observable.
MUTATIONS = {
    "M1_filter1_gt_to_ge": (_mutate_M1_filter1_gt_to_ge, True),
    "M2_gold_gt200_to_ge": (_mutate_M2_gold_gt200_to_ge, True),
    "M3_or_and_precedence": (_mutate_M3_or_and_precedence, True),
    "M4_case_insensitive_eq": (_mutate_M4_case_insensitive_eq, True),
    "M5_trim_eq": (_mutate_M5_trim_eq, True),
    "M6_join_inner_to_left": (_mutate_M6_join_inner_to_left, False),
    "M7_eq_to_startswith": (_mutate_M7_eq_to_startswith, True),
    "M8_count_col_to_star": (_mutate_M8_count_col_to_star, False),
    "M9_filter2_or_to_and": (_mutate_M9_filter2_or_to_and, True),
}


def _redirect_outputs(text, out_dir: Path):
    """Point every STORE write call at an isolated temp dir instead of
    the real out/pyspark_out/pig/<stem>/ tree, so a mutation run can
    never clobber the real converted output other tests depend on."""
    n = text.count(ORIG_OUT_PREFIX)
    assert n == len(OUTPUTS), (
        f"expected {len(OUTPUTS)} STORE write paths with prefix {ORIG_OUT_PREFIX!r}, "
        f"found {n} — has codegen's output layout changed?"
    )
    new_prefix = str(out_dir.as_posix()) + "/"
    return text.replace(ORIG_OUT_PREFIX, new_prefix)


def _run_mutation(name):
    """Apply mutation `name` to a fresh copy of the real generated source,
    redirect its outputs to an isolated temp dir, run it for real under
    the project .venv, then compare each of its 3 outputs against the
    REAL `pig -x local` reference with pipeline.datamatch's own row-
    multiset comparison. Returns {"verdict": "PASS"|"FAIL", "per_output": {...}}
    — file-level verdict is FAIL if ANY output mismatches (same
    worst-of-outputs rule pipeline.datamatch.py itself uses)."""
    mutate_fn, _expect_caught = MUTATIONS[name]
    real_text = _load_real_source()
    mutated_text = mutate_fn(real_text)

    with tempfile.TemporaryDirectory(prefix=f"z3gen_mutation_{name}_") as tmp:
        tmp_dir = Path(tmp)
        out_dir = tmp_dir / "conv_out"
        out_dir.mkdir()
        script_text = _redirect_outputs(mutated_text, out_dir)
        script_path = tmp_dir / f"{STEM}_{name}.py"
        script_path.write_text(script_text, encoding="utf-8")

        proc = subprocess.run(
            [str(VENV_PYTHON), str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, (
            f"mutation {name}: mutated script exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )

        per_output = {}
        for out_name in OUTPUTS:
            ref_target = REF_ROOT / out_name
            conv_target = out_dir / out_name
            ref_rows = datamatch.read_rows(ref_target)
            conv_rows = datamatch.read_rows(conv_target)
            assert ref_rows is not None, f"mutation {name}: missing real Pig reference at {ref_target}"
            assert conv_rows is not None, f"mutation {name}: mutated script wrote nothing to {conv_target}"
            verdict, n_mismatch, samples = datamatch.compare_rows(ref_rows, conv_rows)
            per_output[out_name] = {"verdict": verdict, "n_mismatch": n_mismatch, "samples": samples}

        file_verdict = "FAIL" if any(o["verdict"] == "FAIL" for o in per_output.values()) else "PASS"
        return {"verdict": file_verdict, "per_output": per_output}


def _assert_caught(name):
    result = _run_mutation(name)
    assert result["verdict"] == "FAIL", (
        f"mutation {name} was expected to be CAUGHT (DataMatch FAIL against "
        f"the real Pig reference) but DataMatch still says {result['verdict']}: "
        f"{result['per_output']}"
    )


def test_M1_filter1_gt_to_ge_is_caught():
    _assert_caught("M1_filter1_gt_to_ge")


def test_M2_gold_gt200_to_ge_is_caught():
    _assert_caught("M2_gold_gt200_to_ge")


def test_M3_or_and_precedence_is_caught():
    _assert_caught("M3_or_and_precedence")


def test_M4_case_insensitive_eq_is_caught():
    _assert_caught("M4_case_insensitive_eq")


def test_M5_trim_eq_is_caught():
    _assert_caught("M5_trim_eq")


def test_M6_join_inner_to_left_is_a_documented_no_op():
    """NOT asserted FAIL. gold_txn — the only STORE downstream of the
    JOIN — always applies FILTER 3's `customer_tier == 'GOLD'`. Under a
    real LEFT join, a qualifying_txn row whose customer_id has no match
    in `customers` gets a NULL customer_tier; `NULL == 'GOLD'` is NULL,
    which DataFrame.filter() (and Pig's own FILTER) both treat as "drop
    the row" — the same outcome an INNER join already gives that row (it
    never appears at all). Separately, this fixture also has ZERO orphan
    customer_ids (every raw_txn customer_id has a matching customers
    row — see corpus/data/pig/medium_customers.csv), so even
    txn_customer_proj (were it observed) would be identical either way.
    So inner-vs-left is a GENUINE structural no-op for every output this
    script currently STOREs. Catching it would need a NEW unfiltered
    STORE of txn_customer_proj itself (Fix 2's option (b), not taken —
    see p07_txn_region_tier.pig's own comment for why option (a) was
    preferred) PLUS at least one orphan customer_id in the fixture."""
    result = _run_mutation("M6_join_inner_to_left")
    assert result["verdict"] == "PASS", (
        f"M6 was expected to be a documented no-op (DataMatch PASS) but got "
        f"{result['verdict']} — if a future fixture/script change makes this "
        f"mutation observable, flip this test to test_M6_..._is_caught() "
        f"and assert FAIL instead: {result['per_output']}"
    )


def test_M7_eq_to_startswith_is_caught():
    _assert_caught("M7_eq_to_startswith")


def test_M8_count_col_to_star_is_a_documented_no_op():
    """NOT asserted FAIL. Pig's COUNT(col) skips NULLs in that column;
    count(1)/count('*') counts every row regardless. txn_id is never
    NULL in this fixture — pipeline/z3gen/gen.py's finalize_rows()
    always assigns it sequentially (1..N) to every row, by design (it is
    documented there as "never a branch input"), so there is currently no
    row anywhere in the fixture where COUNT(txn_id) and count(1) could
    disagree. This is the exact case the reviewer flagged: a real no-op
    ONLY because there are no nulls in the counted column. Catching it
    would need one row with a NULL txn_id in some region's group — which
    would mean teaching gen.py's finalize_rows() to leave a hole, a
    change to the general (branch-input-only) fixture-generation design
    that this fix pass deliberately did not make."""
    result = _run_mutation("M8_count_col_to_star")
    assert result["verdict"] == "PASS", (
        f"M8 was expected to be a documented no-op (DataMatch PASS) but got "
        f"{result['verdict']} — if the fixture ever gains a NULL txn_id row, "
        f"flip this test to test_M8_..._is_caught() and assert FAIL instead: "
        f"{result['per_output']}"
    )


def test_M9_filter2_or_to_and_is_caught():
    _assert_caught("M9_filter2_or_to_and")


def test_every_test_in_this_file_is_registered_to_run():
    """See test_z3gen_medium_pig.py's test of the same name for why this
    guard exists: a green run that silently skips half its own file is
    worse than a red one."""
    registered = {t.__name__ for t in TESTS}
    defined = {
        name for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    }
    missing = sorted(defined - registered)
    assert not missing, f"{len(missing)} test(s) defined but never run — add them to TESTS: {missing}"


TESTS = [
    test_M1_filter1_gt_to_ge_is_caught,
    test_M2_gold_gt200_to_ge_is_caught,
    test_M3_or_and_precedence_is_caught,
    test_M4_case_insensitive_eq_is_caught,
    test_M5_trim_eq_is_caught,
    test_M6_join_inner_to_left_is_a_documented_no_op,
    test_M7_eq_to_startswith_is_caught,
    test_M8_count_col_to_star_is_a_documented_no_op,
    test_M9_filter2_or_to_and_is_caught,
    test_every_test_in_this_file_is_registered_to_run,
]


def main():
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
