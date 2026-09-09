"""pipeline.tests.test_e2e_datamatch — Phase-D GATE proof: the whole chain,
both languages, all 13 corpus files, every output PASS.

Why this file exists: every other Phase-D suite proves ONE stage in
isolation (codegen against a fixture-free real IR, or DataMatch's own
mechanics against a hand-written fakelang fixture). None of them proves
the chain actually reaches PASS end-to-end for the real corpus. This
suite is that proof — it is the automated form of the Phase D gate:

    run_codegen pig/hive -> run_pyspark pig/hive -> run_reference_hive
    -> datamatch pig/hive -> reports/e2e_status.json all-PASS

It deliberately REUSES the outputs already on disk from a prior full
chain run (out/pyspark/*, out/pyspark_out/*, out/hive_ref/*, and pig's
committed out/pig/* receipts — never regenerated, never written to by
this suite or by anything it calls) rather than re-running codegen/
pyspark/reference here — those stages already have their own proof
suites (test_codegen_pig, test_codegen_hive) and re-running PySpark here
would make this suite slow and flaky in CI. What it DOES re-run for
real, against the live repo trees (no fixture, no tmpdir substitution),
is pipeline.datamatch itself — the actual comparison step — so a green
run here proves DataMatch was exercised fresh, not that reports/
e2e_status.json merely happens to hold an old PASS from a previous run.

Coverage:
  - datamatch.main() re-run for pig and for hive, both exit 0
  - reports/e2e_status.json, after that re-run, shows PASS for every
    output of all 13 corpus files (7 pig — 6 small + 1 medium — + 6
    hive) — the literal gate. pipeline.datamatch.find_manifests() scans
    corpus/pig/**/*.io.json regardless of tier subfolder (small/medium/
    ...), so corpus/pig/medium/p07_txn_region_tier.pig — added for the
    Z3 test-data slice, see pipeline/z3gen/ — is picked up by the SAME
    "pig" run as the 6 small files, not a separate lane; PIG_STEMS/
    PIG_FILES below grew to match, same as they will the next time a
    tier gains a file.
  - every generated out/pyspark/<lang>/<stem>.py carries at least one
    "# blockid: b_00N" header (run_codegen's own verify_generated, reused
    here rather than re-implemented)
  - logs/run_<lang>_<stem>.log exists for all 13 stems (layout law)
  - reports/datamatch.html, after the re-run, renders both "pig" and
    "hive" section headers plus every one of the 13 corpus file paths

Run: python3 -m pipeline.tests.test_e2e_datamatch
"""
import json
from pathlib import Path

from pipeline import datamatch, run_codegen

REPO_ROOT = Path(__file__).resolve().parents[2]

PIG_STEMS = [
    "p01_load_filter_store",
    "p02_foreach_arithmetic",
    "p03_group_agg",
    "p04_join",
    "p05_order_limit_distinct",
    "p06_union_split",
    "p07_txn_region_tier",
]
HIVE_STEMS = [
    "h01_create_select",
    "h02_where_case",
    "h03_group_having",
    "h04_join_two_tables",
    "h05_insert_union",
    "h06_nested_subquery",
]

REPORT_PATH = REPO_ROOT / "reports" / "e2e_status.json"
HTML_PATH = REPO_ROOT / "reports" / "datamatch.html"

# corpus/pig/<tier>/<stem>.pig — every PIG_STEM lives under small/ except
# the medium-file Z3 slice (p07), which lives under medium/ (see
# corpus/pig/medium/p07_txn_region_tier.pig + pipeline/z3gen/).
_PIG_TIER = {"p07_txn_region_tier": "medium"}
PIG_FILES = [f"corpus/pig/{_PIG_TIER.get(s, 'small')}/{s}.pig" for s in PIG_STEMS]
HIVE_FILES = [f"corpus/hive/small/{s}.hql" for s in HIVE_STEMS]


def _rerun_datamatch(lang):
    """Call the real CLI entrypoint, against the real repo trees (default
    corpus-root/ir-root/conv-root, default ref-root per lang), writing the
    real reports/e2e_status.json + reports/datamatch.html — the same call
    `python3 -m pipeline.datamatch <lang>` makes from the shell."""
    rc = datamatch.main([lang])
    assert rc == 0, f"pipeline.datamatch {lang} exited {rc}, expected 0 (all PASS)"


def test_datamatch_pig_rerun_exits_zero():
    _rerun_datamatch("pig")


def test_datamatch_hive_rerun_exits_zero():
    _rerun_datamatch("hive")


def _load_report():
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH} — run the datamatch re-run tests first"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_report_has_both_languages():
    report = _load_report()
    assert set(report.keys()) >= {"pig", "hive"}, (
        f"reports/e2e_status.json must carry both pig and hive entries, got {sorted(report.keys())}"
    )


def test_every_pig_file_and_output_is_pass():
    report = _load_report()
    files = {f["file"]: f for f in report["pig"]["files"]}
    assert set(files.keys()) == set(PIG_FILES), (
        f"expected exactly the 6 pig corpus files, got {sorted(files.keys())}"
    )
    for path, entry in files.items():
        assert entry["verdict"] == "PASS", f"{path}: file verdict {entry['verdict']!r}, expected PASS"
        assert entry["outputs"], f"{path}: no outputs recorded"
        for o in entry["outputs"]:
            assert o["verdict"] == "PASS", f"{path}/{o['name']}: {o['verdict']!r}, expected PASS ({o})"
            assert o["n_mismatch"] == 0, f"{path}/{o['name']}: n_mismatch={o['n_mismatch']}, expected 0"


def test_every_hive_file_and_output_is_pass():
    report = _load_report()
    files = {f["file"]: f for f in report["hive"]["files"]}
    assert set(files.keys()) == set(HIVE_FILES), (
        f"expected exactly the 6 hive corpus files, got {sorted(files.keys())}"
    )
    for path, entry in files.items():
        assert entry["verdict"] == "PASS", f"{path}: file verdict {entry['verdict']!r}, expected PASS"
        assert entry["outputs"], f"{path}: no outputs recorded"
        for o in entry["outputs"]:
            assert o["verdict"] == "PASS", f"{path}/{o['name']}: {o['verdict']!r}, expected PASS ({o})"
            assert o["n_mismatch"] == 0, f"{path}/{o['name']}: n_mismatch={o['n_mismatch']}, expected 0"


def test_all_thirteen_files_pass_the_gate():
    """The literal Phase-D gate statement: 7 pig (6 small + 1 medium) + 6
    hive files, every output of every one of them, PASS. Counts outputs
    directly rather than trusting the file-level rollup alone, so a
    rollup bug could not hide a still-failing individual output."""
    report = _load_report()
    total_outputs = 0
    for lang in ("pig", "hive"):
        for f in report[lang]["files"]:
            assert f["verdict"] == "PASS", f"{lang}/{f['file']}: {f['verdict']}"
            for o in f["outputs"]:
                assert o["verdict"] == "PASS", f"{lang}/{f['file']}/{o['name']}: {o['verdict']}"
                total_outputs += 1
    assert total_outputs == 17, (
        f"expected 17 total outputs across the 13 gate files "
        f"(pig: 4 single-output files + 2 two-output files + 1 "
        f"THREE-output medium file [qualifying_txn, gold_txn, region_summary — "
        f"qualifying_txn added by Fix 2, see corpus/pig/medium/p07_txn_region_tier.pig's "
        f"own comment] = 11 outputs; "
        f"hive: 6 single-output files = 6 outputs), got {total_outputs}"
    )
    n_files = sum(len(report[lang]["files"]) for lang in ("pig", "hive"))
    assert n_files == 13, f"expected 13 total files (7 pig + 6 hive), got {n_files}"


def test_every_generated_py_carries_blockid_headers():
    for lang, stems in (("pig", PIG_STEMS), ("hive", HIVE_STEMS)):
        for stem in stems:
            py_path = REPO_ROOT / "out" / "pyspark" / lang / f"{stem}.py"
            assert py_path.is_file(), f"missing generated file: {py_path}"
            problems = run_codegen.verify_generated(py_path)
            assert not problems, f"{lang}/{stem}.py: {problems}"


def test_generated_code_contains_no_absolute_machine_paths():
    """Generated PySpark must be byte-identical on every machine: no
    developer's home directory, no checkout location. Generated programs
    always run with cwd = repo root, so every input AND output path they
    carry is repo-root-relative. A leaked absolute path still runs here
    but would not run on anyone else's checkout or on a cluster."""
    repo_str = str(REPO_ROOT)
    for lang, stems in (("pig", PIG_STEMS), ("hive", HIVE_STEMS)):
        for stem in stems:
            py_path = REPO_ROOT / "out" / "pyspark" / lang / f"{stem}.py"
            text = py_path.read_text(encoding="utf-8")
            assert repo_str not in text, (
                f"{lang}/{stem}.py bakes in this checkout's absolute path "
                f"{repo_str!r} — generated code must be machine-independent"
            )
            offenders = [
                ln for ln in text.splitlines()
                if '"/' in ln or "'/" in ln
            ]
            assert not offenders, (
                f"{lang}/{stem}.py has absolute path literal(s): {offenders}"
            )


def test_converted_outputs_landed_where_the_layout_law_says():
    """The relative write path the generator emits must resolve, from the
    repo root, to exactly out/pyspark_out/<lang>/<stem>/<name>/ — proof
    the relative form points at the same place DataMatch reads from."""
    report = _load_report()
    for lang in ("pig", "hive"):
        for f in report[lang]["files"]:
            stem = Path(f["file"]).stem
            for o in f["outputs"]:
                d = REPO_ROOT / "out" / "pyspark_out" / lang / stem / o["name"]
                assert d.is_dir(), f"converted output dir missing: {d}"


def test_run_logs_exist_for_every_stem_per_layout_law():
    for lang, stems in (("pig", PIG_STEMS), ("hive", HIVE_STEMS)):
        for stem in stems:
            log_path = REPO_ROOT / "logs" / f"run_{lang}_{stem}.log"
            assert log_path.is_file(), f"missing run log: {log_path}"
            assert log_path.stat().st_size > 0, f"empty run log: {log_path}"


def test_datamatch_html_renders_both_languages():
    assert HTML_PATH.is_file(), f"missing {HTML_PATH}"
    html = HTML_PATH.read_text(encoding="utf-8")
    assert ">pig " in html or ">pig<" in html or "<h2>pig" in html, (
        "reports/datamatch.html does not render a pig section header"
    )
    assert ">hive " in html or ">hive<" in html or "<h2>hive" in html, (
        "reports/datamatch.html does not render a hive section header"
    )
    for path in PIG_FILES + HIVE_FILES:
        assert path in html, f"reports/datamatch.html is missing the row for {path}"


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
    test_datamatch_pig_rerun_exits_zero,
    test_datamatch_hive_rerun_exits_zero,
    test_report_has_both_languages,
    test_every_pig_file_and_output_is_pass,
    test_every_hive_file_and_output_is_pass,
    test_all_thirteen_files_pass_the_gate,
    test_every_generated_py_carries_blockid_headers,
    test_generated_code_contains_no_absolute_machine_paths,
    test_converted_outputs_landed_where_the_layout_law_says,
    test_run_logs_exist_for_every_stem_per_layout_law,
    test_datamatch_html_renders_both_languages,
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
