"""pipeline.tests.test_datamatch — proofs for the exp_014 PHASE-D
DataMatch harness (pipeline/datamatch.py).

This is the harness agent's OWN proof, run entirely against a fixture
tree it owns — pipeline/tests/fixtures/datamatch/{corpus,ir,ref,conv}/
fakelang/... — never against out/pig, out/hive_ref, or out/pyspark_out.
It deliberately does NOT import anything from pipeline/codegen or
pipeline/term_parse — those belong to another agent and this harness is
language-agnostic by contract: it proves itself against a fake language
("fakelang") whose manifests and node4 terms are hand-written here, in
the exact shape real pig/hive output already has (checked against the
real out/ir/pig/*.node4.json and corpus/pig/small/*.io.json files while
this suite was written).

Coverage, one test function per contract point:
  - PASS: reference and converted rows match exactly (f01_pass) — also
    proves multi-part-file concatenation (2 ref part files) and control-
    file skipping (_SUCCESS, a .crc dotfile) in the same fixture
  - FAIL: a real value differs, sample_mismatches names the row and each
    side's count (f02_fail)
  - REF_MISSING: no reference target exists on disk (neither the dir nor
    the .csv shape) even though a converted output does (f03_refmissing)
  - CONV_MISSING: reference exists, out/pyspark_out-shaped converted dir
    was never created (f04_convmissing)
  - float precision: 30.376666666666665 (ref) vs 30.3766667 (conv) PASS
    at 6dp, in the same fixture as int-vs-whole-float unification
    ("5.0" vs "5") — also proves the single-CSV-file reference shape
    (hive-style) resolves correctly (f05_float)
  - row-order shuffle: same rows, different order, still PASS (f06_shuffle)
  - duplicate-row multiset semantics: ref has a row twice, conv has it
    once — FAIL, because counts differ even though the plain SETS are
    equal (f07_dupcount)
  - file-level rollup: one PASS output + one FAIL output on the same
    source file rolls up to a FAIL file verdict (f08_multi)
  - BlockId attribution picks the LAST block (by seq) whose term text
    mentions the output name, across multiple candidate blocks (f01_pass:
    the name appears in b_001's assign AND b_002's store; b_002 wins)
  - BlockId attribution unit-level word-boundary check: a name must not
    match as a substring of a longer identifier
  - normalize_value: int/float unification and non-numeric pass-through,
    as pure unit tests independent of any fixture file
  - resolve_ref_target supports both the directory shape and the single-
    CSV-file shape, and returns None (not a crash) when neither exists
  - merge_report never clobbers one language's entry when another
    language's run writes the same report file
  - the full CLI (main()) exits 0 when run against a PASS-only stem and
    exits 1 when run against a FAIL stem — proving reports/e2e_status.json
    and reports/datamatch.html actually get written, not just the
    in-process run() dict

Run: python3 -m pipeline.tests.test_datamatch
"""
import json
import tempfile
from pathlib import Path

from pipeline.datamatch import (
    attribute_block,
    compare_rows,
    find_manifests,
    load_node4,
    main,
    merge_report,
    normalize_value,
    process_manifest,
    read_rows,
    resolve_ref_target,
    run,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "datamatch"
CORPUS_ROOT = FIXTURES / "corpus"
IR_ROOT = FIXTURES / "ir"
REF_ROOT = FIXTURES / "ref" / "fakelang"
CONV_ROOT = FIXTURES / "conv"
LANG = "fakelang"


def _run(stem=None):
    return run(LANG, stem=stem, corpus_root=CORPUS_ROOT, ir_root=IR_ROOT,
               ref_root=REF_ROOT, conv_root=CONV_ROOT)


def _file_result(stem):
    data = _run(stem=stem)
    assert len(data["files"]) == 1, (
        f"expected exactly one file result for stem={stem!r}, got {len(data['files'])}"
    )
    return data["files"][0]


def _output(file_result, name):
    for o in file_result["outputs"]:
        if o["name"] == name:
            return o
    raise AssertionError(f"no output named {name!r} in {file_result}")


def test_pass_when_reference_and_converted_rows_match():
    fr = _file_result("f01_pass")
    o = _output(fr, "out_pass")
    assert o["verdict"] == "PASS", o
    assert o["rows_ref"] == 3, "2 rows from part-00000 + 1 from part-00001 must concatenate"
    assert o["rows_conv"] == 3
    assert o["n_mismatch"] == 0
    assert o["sample_mismatches"] == []
    assert fr["verdict"] == "PASS"


def test_control_files_are_excluded_from_the_row_count():
    # f01_pass's ref dir also holds _SUCCESS and a .crc dotfile; rows_ref
    # == 3 (proven above) already shows they were not read as data rows.
    rows = read_rows(REF_ROOT / "f01_pass" / "out_pass")
    assert len(rows) == 3, f"control files leaked into row data: {rows}"


def test_fail_reports_sample_mismatches_for_the_differing_row():
    fr = _file_result("f02_fail")
    o = _output(fr, "out_fail")
    assert o["verdict"] == "FAIL", o
    assert o["rows_ref"] == 2 and o["rows_conv"] == 2
    assert o["n_mismatch"] == 2, "one row missing-from-conv + one row extra-in-conv = 2"
    assert len(o["sample_mismatches"]) >= 1
    rows_in_samples = [s["row"] for s in o["sample_mismatches"]]
    assert ["2", "200"] in rows_in_samples, o["sample_mismatches"]
    assert fr["verdict"] == "FAIL"


def test_ref_missing_when_no_reference_target_exists():
    fr = _file_result("f03_refmissing")
    o = _output(fr, "out_refmissing")
    assert o["verdict"] == "REF_MISSING", o
    assert o["rows_ref"] is None
    assert o["rows_conv"] == 1, "converted rows should still be counted and reported"
    assert fr["verdict"] == "REF_MISSING"


def test_conv_missing_when_reference_exists_but_converted_does_not():
    fr = _file_result("f04_convmissing")
    o = _output(fr, "out_convmissing")
    assert o["verdict"] == "CONV_MISSING", o
    assert o["rows_ref"] == 2
    assert o["rows_conv"] is None
    assert fr["verdict"] == "CONV_MISSING"


def test_float_precision_six_decimals_and_int_unification_pass():
    fr = _file_result("f05_float")
    o = _output(fr, "out_float")
    assert o["verdict"] == "PASS", o
    assert o["rows_ref"] == 2 and o["rows_conv"] == 2


def test_resolve_ref_target_supports_the_single_csv_file_shape():
    target = resolve_ref_target(REF_ROOT, "f05_float", "out_float")
    assert target is not None and target.is_file(), target
    assert target.name == "out_float.csv"


def test_resolve_ref_target_supports_the_directory_shape():
    target = resolve_ref_target(REF_ROOT, "f01_pass", "out_pass")
    assert target is not None and target.is_dir(), target


def test_resolve_ref_target_returns_none_when_neither_shape_exists():
    target = resolve_ref_target(REF_ROOT, "f03_refmissing", "out_refmissing")
    assert target is None, target


def test_row_order_shuffle_still_passes():
    fr = _file_result("f06_shuffle")
    o = _output(fr, "out_shuffle")
    assert o["verdict"] == "PASS", o


def test_duplicate_row_counts_fail_under_multiset_semantics():
    fr = _file_result("f07_dupcount")
    o = _output(fr, "out_dup")
    assert o["verdict"] == "FAIL", (
        "ref has ('1','X') twice, conv once — a plain-set comparison would "
        "wrongly PASS this; multiset semantics must catch the count diff"
    )
    assert o["n_mismatch"] == 1
    assert len(o["sample_mismatches"]) == 1
    s = o["sample_mismatches"][0]
    assert s["row"] == ["1", "X"] and s["ref_count"] == 2 and s["conv_count"] == 1, s


def test_file_level_rollup_is_fail_when_any_output_fails():
    fr = _file_result("f08_multi")
    a = _output(fr, "out_multi_a")
    b = _output(fr, "out_multi_b")
    assert a["verdict"] == "PASS"
    assert b["verdict"] == "FAIL"
    assert fr["verdict"] == "FAIL", "worst-of-outputs rollup must surface the FAIL"


def test_block_attribution_picks_the_last_matching_block_by_seq():
    node4 = load_node4(IR_ROOT, LANG, "f01_pass")
    assert attribute_block(node4, "out_pass") == "b_002", (
        "out_pass appears in b_001 (assign) and b_002 (store); the LAST "
        "(highest-seq) match must win — b_002 is the block that actually "
        "persists it"
    )


def test_block_attribution_is_reported_on_every_output():
    fr = _file_result("f02_fail")
    o = _output(fr, "out_fail")
    assert o["block"] == "b_001", o


def test_attribute_block_word_boundary_rejects_substring_matches():
    node4 = [
        {"block": "b_001", "seq": 1, "term": "assign(rel(txn_id_extra),load(lit('x')))"},
        {"block": "b_002", "seq": 2, "term": "assign(rel(raw_txn2),load(lit('y')))"},
    ]
    # "txn" is a substring of both txn_id_extra and raw_txn2 but must not
    # match as a whole identifier in either.
    assert attribute_block(node4, "txn") is None


def test_attribute_block_matches_a_quoted_atom_inside_a_path_literal():
    node4 = [
        {"block": "b_001", "seq": 1, "term": "store(rel(x),lit('out/some/dir/exact_name'),call('Y',[]))"},
    ]
    assert attribute_block(node4, "exact_name") == "b_001"


def test_normalize_value_unifies_int_and_float_forms():
    assert normalize_value("5") == normalize_value("5.0") == normalize_value("5.000000")
    assert normalize_value("30.376666666666665") == normalize_value("30.3766667") == "30.376667"


def test_normalize_value_passes_through_non_numeric_strings():
    assert normalize_value("  EAST  ") == "EAST"
    assert normalize_value("north") == "north"


def test_normalize_value_survives_nan_and_infinity_without_raising():
    """round()/int() raise on NaN and Inf. Before this was handled, one
    NaN cell (Spark prints 0.0/0.0 as "NaN") crashed the whole DataMatch
    run instead of producing a verdict."""
    for spelling in ("nan", "NaN", "inf", "-inf", "Infinity", "-Infinity"):
        normalize_value(spelling)  # must not raise


def test_normalize_value_canonicalizes_nan_and_infinity_spellings():
    """The two engines spell these differently; a spelling difference is
    not a data difference. NaN/+Inf/-Inf still stay distinct from each
    other and from every real number."""
    assert normalize_value("NaN") == normalize_value("nan") == "nan"
    assert normalize_value("Infinity") == normalize_value("inf") == "inf"
    assert normalize_value("-Infinity") == normalize_value("-inf") == "-inf"
    assert len({normalize_value(s) for s in ("nan", "inf", "-inf", "0")}) == 4


def test_nan_row_compares_without_crashing_and_still_catches_a_real_diff():
    assert compare_rows([["1", "NaN"]], [["1", "nan"]])[0] == "PASS"
    assert compare_rows([["1", "NaN"]], [["1", "0"]])[0] == "FAIL"
    assert compare_rows([["1", "inf"]], [["1", "-inf"]])[0] == "FAIL"


def test_compare_rows_direct_pass_and_fail():
    assert compare_rows([["1", "a"]], [["1", "a"]])[0] == "PASS"
    verdict, n, samples = compare_rows([["1", "a"]], [["1", "b"]])
    assert verdict == "FAIL"
    assert n == 2
    assert len(samples) == 2


def test_merge_report_does_not_clobber_the_other_langs_entry():
    with tempfile.TemporaryDirectory() as td:
        report_path = Path(td) / "e2e_status.json"
        pig_data = {"lang": "pig", "generated_at_run": "t1", "files": [{"file": "p.pig", "verdict": "PASS", "outputs": []}]}
        hive_data = {"lang": "hive", "generated_at_run": "t2", "files": [{"file": "h.hql", "verdict": "FAIL", "outputs": []}]}
        merge_report(report_path, "pig", pig_data)
        merged = merge_report(report_path, "hive", hive_data)
        assert set(merged.keys()) == {"pig", "hive"}
        assert merged["pig"] == pig_data, "writing hive must not touch the pig entry already on disk"
        assert merged["hive"] == hive_data
        on_disk = json.loads(report_path.read_text(encoding="utf-8"))
        assert on_disk == merged


def test_find_manifests_stem_filter_narrows_to_one_file():
    all_manifests = find_manifests(CORPUS_ROOT, LANG)
    assert len(all_manifests) == 8, f"expected 8 fakelang fixture manifests, found {len(all_manifests)}"
    one = find_manifests(CORPUS_ROOT, LANG, stem_filter="f02_fail")
    assert len(one) == 1
    assert Path(json.loads(one[0].read_text())["file"]).stem == "f02_fail"


def test_process_manifest_used_directly_matches_run_output():
    manifests = find_manifests(CORPUS_ROOT, LANG, stem_filter="f01_pass")
    direct = process_manifest(manifests[0], LANG, IR_ROOT, REF_ROOT, CONV_ROOT)
    via_run = _file_result("f01_pass")
    assert direct == via_run


def test_cli_exits_zero_and_writes_reports_for_a_pass_only_stem():
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "e2e_status.json"
        html = Path(td) / "datamatch.html"
        rc = main([
            LANG, "--stem", "f01_pass",
            "--corpus-root", str(CORPUS_ROOT), "--ir-root", str(IR_ROOT),
            "--ref-root", str(REF_ROOT), "--conv-root", str(CONV_ROOT),
            "--report", str(report), "--html", str(html),
        ])
        assert rc == 0, "a PASS-only stem must exit 0"
        assert report.exists() and html.exists()
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data[LANG]["files"][0]["verdict"] == "PASS"
        assert "out_pass" in html.read_text(encoding="utf-8")


def test_cli_exits_nonzero_for_a_failing_stem():
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "e2e_status.json"
        html = Path(td) / "datamatch.html"
        rc = main([
            LANG, "--stem", "f02_fail",
            "--corpus-root", str(CORPUS_ROOT), "--ir-root", str(IR_ROOT),
            "--ref-root", str(REF_ROOT), "--conv-root", str(CONV_ROOT),
            "--report", str(report), "--html", str(html),
        ])
        assert rc == 1, "a stem with a FAIL output must exit non-zero"


def test_cli_exits_nonzero_when_no_manifests_match():
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "e2e_status.json"
        html = Path(td) / "datamatch.html"
        rc = main([
            "no_such_lang",
            "--corpus-root", str(CORPUS_ROOT), "--ir-root", str(IR_ROOT),
            "--conv-root", str(CONV_ROOT),
            "--report", str(report), "--html", str(html),
        ])
        assert rc == 1


def test_every_test_in_this_file_is_registered_to_run():
    """The TESTS list must contain every test_* function defined here — see
    pipeline/tests/test_corpus_lossless.py's test of the same name for why
    this guard exists: a green run that silently skips half its own file
    is worse than a red one."""
    registered = {t.__name__ for t in TESTS}
    defined = {
        name for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    }
    missing = sorted(defined - registered)
    assert not missing, f"{len(missing)} test(s) defined but never run — add them to TESTS: {missing}"


TESTS = [
    test_pass_when_reference_and_converted_rows_match,
    test_control_files_are_excluded_from_the_row_count,
    test_fail_reports_sample_mismatches_for_the_differing_row,
    test_ref_missing_when_no_reference_target_exists,
    test_conv_missing_when_reference_exists_but_converted_does_not,
    test_float_precision_six_decimals_and_int_unification_pass,
    test_resolve_ref_target_supports_the_single_csv_file_shape,
    test_resolve_ref_target_supports_the_directory_shape,
    test_resolve_ref_target_returns_none_when_neither_shape_exists,
    test_row_order_shuffle_still_passes,
    test_duplicate_row_counts_fail_under_multiset_semantics,
    test_file_level_rollup_is_fail_when_any_output_fails,
    test_block_attribution_picks_the_last_matching_block_by_seq,
    test_block_attribution_is_reported_on_every_output,
    test_attribute_block_word_boundary_rejects_substring_matches,
    test_attribute_block_matches_a_quoted_atom_inside_a_path_literal,
    test_normalize_value_unifies_int_and_float_forms,
    test_normalize_value_passes_through_non_numeric_strings,
    test_normalize_value_survives_nan_and_infinity_without_raising,
    test_normalize_value_canonicalizes_nan_and_infinity_spellings,
    test_nan_row_compares_without_crashing_and_still_catches_a_real_diff,
    test_compare_rows_direct_pass_and_fail,
    test_merge_report_does_not_clobber_the_other_langs_entry,
    test_find_manifests_stem_filter_narrows_to_one_file,
    test_process_manifest_used_directly_matches_run_output,
    test_cli_exits_zero_and_writes_reports_for_a_pass_only_stem,
    test_cli_exits_nonzero_for_a_failing_stem,
    test_cli_exits_nonzero_when_no_manifests_match,
    test_every_test_in_this_file_is_registered_to_run,
]


def main_test_runner():
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
    raise SystemExit(main_test_runner())
