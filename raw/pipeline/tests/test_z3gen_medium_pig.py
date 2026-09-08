"""pipeline.tests.test_z3gen_medium_pig — proof for the medium-file Z3
test-data slice: corpus/pig/medium/p07_txn_region_tier.pig,
pipeline/z3gen/pig_semantics.py + pipeline/z3gen/gen.py.

Why this file exists: the other Phase-D suites prove the small (hand-
typed-fixture) 6-file pig corpus end to end. This suite is that same
proof for the ONE medium-file script this slice added, PLUS the thing
the small corpus never needed: proof that the Z3 engine itself found
every branch its own FILTER conditions can take, and solved BOTH
polarities of each one — not just that DataMatch happens to pass on
whatever rows are currently sitting in the fixture file.

Coverage:
  1. pipeline.z3gen.gen.run(), re-run in-process against the real
     out/ir/pig/p07_txn_region_tier.node4.json (not a fixture — the
     same file run_fold pig already wrote), finds exactly 6 leaf branch
     conditions (1 from the plain `amount > 0.0` FILTER, 3 from the
     compound OR-of-AND FILTER, 2 from the compound AND FILTER) and
     solves BOTH polarities of every one of them.
  2. `python3 -m pipeline.datamatch pig` (the real CLI, full corpus —
     see the note in test_e2e_datamatch.py's PIG_STEMS/PIG_FILES about
     why this is a full re-run and not a --stem one) exits 0, and
     reports/e2e_status.json shows PASS for corpus/pig/medium/
     p07_txn_region_tier.pig and all three of its outputs (qualifying_txn,
     gold_txn, region_summary), with zero mismatches.
  3. out/pyspark/pig/p07_txn_region_tier.py carries "# blockid: b_00N"
     headers and no absolute machine paths (run_codegen's own
     verify_generated, reused here rather than re-implemented).
  4. logs/run_pig_p07_txn_region_tier.log exists (layout law).
  5. reports/datamatch.html renders the medium file's row.

Run: python3 -m pipeline.tests.test_z3gen_medium_pig
"""
import json
from pathlib import Path

from pipeline import datamatch, run_codegen
from pipeline.z3gen import gen as z3gen

REPO_ROOT = Path(__file__).resolve().parents[2]
STEM = "p07_txn_region_tier"
PIG_FILE = "corpus/pig/medium/p07_txn_region_tier.pig"
IR_PATH = REPO_ROOT / "out" / "ir" / "pig" / f"{STEM}.node4.json"
PY_PATH = REPO_ROOT / "out" / "pyspark" / "pig" / f"{STEM}.py"
LOG_PATH = REPO_ROOT / "logs" / f"run_pig_{STEM}.log"
REPORT_PATH = REPO_ROOT / "reports" / "e2e_status.json"
HTML_PATH = REPO_ROOT / "reports" / "datamatch.html"


def _load_ir():
    assert IR_PATH.is_file(), f"missing IR: {IR_PATH} (run pipeline.run_fold pig --file {STEM} first)"
    return json.loads(IR_PATH.read_text(encoding="utf-8"))


def test_z3_engine_finds_exactly_six_leaf_branches():
    lineage, scenarios, _raw_rows, _cust = z3gen.run(_load_ir())
    assert len(lineage.filters) == 3, f"expected 3 FILTER statements, got {len(lineage.filters)}"
    legs = {(s["filter"], s["leaf"], tuple(s["guards"])) for s in scenarios}
    assert len(legs) == 6, f"expected 6 distinct leaf branch conditions, got {len(legs)}: {sorted(legs)}"


def test_z3_engine_hits_every_branch_both_ways():
    _lineage, scenarios, _raw_rows, _cust = z3gen.run(_load_ir())
    by_leg = {}
    for s in scenarios:
        key = (s["filter"], s["leaf"], tuple(s["guards"]))
        by_leg.setdefault(key, {})[s["polarity"]] = s["sat"]
    unsat = {k: v for k, v in by_leg.items() if not (v.get(True) and v.get(False))}
    assert not unsat, f"branch(es) not hit both ways by Z3: {unsat}"


def test_z3_engine_produces_rows_for_both_tables():
    _lineage, _scenarios, raw_rows, cust_by_id = z3gen.run(_load_ir())
    assert len(raw_rows) > 0, "z3gen.run produced no raw_txn rows"
    assert len(cust_by_id) > 0, "z3gen.run produced no customers rows"


def _rerun_full_pig_datamatch():
    """A FULL `datamatch pig` re-run (no --stem): pipeline.datamatch's
    find_manifests() scans corpus/pig/**/*.io.json regardless of tier,
    so a --stem-scoped re-run here would REPLACE the merged report's
    entire "pig" key with just this one file, clobbering the other 6
    small-corpus files' PASS records that test_e2e_datamatch.py's own
    gate depends on. Always re-run the whole language, exactly like
    test_e2e_datamatch.py's own _rerun_datamatch does."""
    rc = datamatch.main(["pig"])
    assert rc == 0, f"pipeline.datamatch pig exited {rc}, expected 0 (all PASS)"


def test_datamatch_pig_full_rerun_exits_zero():
    _rerun_full_pig_datamatch()


def _load_report():
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH} — run the datamatch re-run test first"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_medium_file_and_both_outputs_are_pass():
    report = _load_report()
    files = {f["file"]: f for f in report["pig"]["files"]}
    assert PIG_FILE in files, f"{PIG_FILE} missing from reports/e2e_status.json pig files: {sorted(files)}"
    entry = files[PIG_FILE]
    assert entry["verdict"] == "PASS", f"{PIG_FILE}: file verdict {entry['verdict']!r}, expected PASS"
    names = {o["name"] for o in entry["outputs"]}
    # qualifying_txn added by Fix 2: the FILTER1+FILTER2 chain's own direct
    # output, so DataMatch is no longer structurally blind to those two
    # FILTERs' exact row-level behavior (see the .pig file's own comment).
    assert names == {"qualifying_txn", "gold_txn", "region_summary"}, \
        f"{PIG_FILE}: unexpected outputs {sorted(names)}"
    for o in entry["outputs"]:
        assert o["verdict"] == "PASS", f"{PIG_FILE}/{o['name']}: {o['verdict']!r}, expected PASS ({o})"
        assert o["n_mismatch"] == 0, f"{PIG_FILE}/{o['name']}: n_mismatch={o['n_mismatch']}, expected 0"
        assert o["rows_ref"] and o["rows_ref"] > 0, f"{PIG_FILE}/{o['name']}: rows_ref={o['rows_ref']}"


def test_generated_py_carries_blockid_headers_and_no_absolute_paths():
    assert PY_PATH.is_file(), f"missing generated file: {PY_PATH}"
    problems = run_codegen.verify_generated(PY_PATH)
    assert not problems, f"{STEM}.py: {problems}"
    text = PY_PATH.read_text(encoding="utf-8")
    repo_str = str(REPO_ROOT)
    assert repo_str not in text, f"{STEM}.py bakes in this checkout's absolute path {repo_str!r}"
    offenders = [ln for ln in text.splitlines() if '"/' in ln or "'/" in ln]
    assert not offenders, f"{STEM}.py has absolute path literal(s): {offenders}"


def test_run_log_exists():
    assert LOG_PATH.is_file(), f"missing run log: {LOG_PATH}"
    assert LOG_PATH.stat().st_size > 0, f"empty run log: {LOG_PATH}"


def test_datamatch_html_renders_the_medium_file():
    assert HTML_PATH.is_file(), f"missing {HTML_PATH}"
    html = HTML_PATH.read_text(encoding="utf-8")
    assert PIG_FILE in html, f"reports/datamatch.html is missing the row for {PIG_FILE}"


def test_every_test_in_this_file_is_registered_to_run():
    """See test_corpus_lossless.py / test_datamatch.py's test of the same
    name for why this guard exists: a green run that silently skips half
    its own file is worse than a red one."""
    registered = {t.__name__ for t in TESTS}
    defined = {
        name for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    }
    missing = sorted(defined - registered)
    assert not missing, f"{len(missing)} test(s) defined but never run — add them to TESTS: {missing}"


TESTS = [
    test_z3_engine_finds_exactly_six_leaf_branches,
    test_z3_engine_hits_every_branch_both_ways,
    test_z3_engine_produces_rows_for_both_tables,
    test_datamatch_pig_full_rerun_exits_zero,
    test_medium_file_and_both_outputs_are_pass,
    test_generated_py_carries_blockid_headers_and_no_absolute_paths,
    test_run_log_exists,
    test_datamatch_html_renders_the_medium_file,
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
