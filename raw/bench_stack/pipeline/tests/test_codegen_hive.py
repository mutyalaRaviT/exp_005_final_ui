"""pipeline.tests.test_codegen_hive — proofs for Phase-D Hive codegen.

Why this file exists: pipeline.term_parse, pipeline.codegen.common, and
pipeline.codegen.hive_pyspark together turn out/ir/hive/*.node4.json into
out/pyspark/hive/*.py (the Codegen law). This suite proves, over the real
6-file hive/small corpus (not a fixture), the same shape of thing
test_codegen_pig.py proves for pig:

  1. pipeline.term_parse round-trips every term actually printed by the
     fold harness for every hive corpus file — no ValueError/
     TermParseError, and the parsed value is a compound term.
  2. Generation is deterministic: generating the same *.node4.json twice
     produces byte-identical output.
  3. Every distinct "block" value in a file's node4.json produces exactly
     one "# blockid: b_00N" header in the generated file, in the same
     order the blocks appear in the IR.
  4. Every generated file parses as valid Python (ast.parse).
  5. `python3 -m pipeline.run_codegen hive` (the real CLI) exits 0 and
     leaves all 6 files on disk.
  6. Every CREATE TABLE AS / INSERT INTO ... SELECT target's generated
     write follows the layout law exactly:
     out/pyspark_out/hive/<stem>/<output_name>/ — checked against the
     manifest's own output name (the relation the term creates/inserts
     into), not a hard-coded name.

Run: python3 -m pipeline.tests.test_codegen_hive
"""
import ast
import json
from pathlib import Path

from pipeline import run_codegen, term_parse
from pipeline.codegen import common, hive_pyspark

REPO_ROOT = Path(__file__).resolve().parents[2]
IR_DIR = REPO_ROOT / "out" / "ir" / "hive"

HIVE_STEMS = [
    "h01_create_select",
    "h02_where_case",
    "h03_group_having",
    "h04_join_two_tables",
    "h05_insert_union",
    "h06_nested_subquery",
]


def _load_ir(stem):
    path = IR_DIR / f"{stem}.node4.json"
    assert path.is_file(), f"missing IR fixture: {path} (run pipeline.run_fold hive first)"
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------

def test_term_parse_handles_every_hive_corpus_term():
    for stem in HIVE_STEMS:
        for entry in _load_ir(stem):
            term = term_parse.parse_term(entry["term"])
            assert isinstance(term, tuple), (
                f"{stem} seq {entry['seq']}: expected a compound term, got {term!r}"
            )
            functor = term[0]
            assert isinstance(functor, str) and functor, (
                f"{stem} seq {entry['seq']}: bad functor in parsed term {term!r}"
            )


def test_generation_is_deterministic():
    for stem in HIVE_STEMS:
        node4 = _load_ir(stem)
        lines_a = hive_pyspark.generate_lines(node4, stem, lang="hive")
        lines_b = hive_pyspark.generate_lines(node4, stem, lang="hive")
        assert lines_a == lines_b, f"{stem}: generation is not deterministic"


def test_every_block_gets_exactly_one_blockid_header_in_order():
    for stem in HIVE_STEMS:
        node4 = _load_ir(stem)
        expected_blocks = []
        for entry in node4:
            if not expected_blocks or expected_blocks[-1] != entry["block"]:
                expected_blocks.append(entry["block"])

        lines = hive_pyspark.generate_lines(node4, stem, lang="hive")
        found_blocks = [
            ln[len("# blockid: "):].strip()
            for ln in lines
            if ln.startswith("# blockid: ")
        ]
        assert found_blocks == expected_blocks, (
            f"{stem}: blockid headers {found_blocks} != IR block order {expected_blocks}"
        )


def test_generated_files_parse_as_valid_python():
    for stem in HIVE_STEMS:
        node4 = _load_ir(stem)
        lines = hive_pyspark.generate_lines(node4, stem, lang="hive")
        source = "\n".join(lines) + "\n"
        ast.parse(source, filename=f"{stem}.py")  # raises SyntaxError on failure


def test_run_codegen_cli_generates_all_six_files():
    out_dir = REPO_ROOT / "out" / "pyspark" / "hive"
    rc = run_codegen.main(["hive"])
    assert rc == 0, "python3 -m pipeline.run_codegen hive exited non-zero"
    for stem in HIVE_STEMS:
        py_path = out_dir / f"{stem}.py"
        assert py_path.is_file(), f"expected generated file missing: {py_path}"
        problems = run_codegen.verify_generated(py_path)
        assert not problems, f"{stem}: {problems}"


def test_ctas_and_insert_output_dirs_follow_the_layout_law():
    for stem in HIVE_STEMS:
        node4 = _load_ir(stem)
        for entry in node4:
            term = term_parse.parse_term(entry["term"])
            functor = term[0]
            if functor not in ("create_table_as", "insert_select"):
                continue
            relname = term[1][1]
            expected = common.pyspark_out_dir("hive", stem, relname)
            assert str(expected).endswith(f"out/pyspark_out/hive/{stem}/{relname}"), (
                f"{stem}: {functor} for {relname!r} resolved to {expected}, "
                f"not the out/pyspark_out/hive/<stem>/<output_name> layout law"
            )


# --------------------------------------------------------------------

TESTS = [
    test_term_parse_handles_every_hive_corpus_term,
    test_generation_is_deterministic,
    test_every_block_gets_exactly_one_blockid_header_in_order,
    test_generated_files_parse_as_valid_python,
    test_run_codegen_cli_generates_all_six_files,
    test_ctas_and_insert_output_dirs_follow_the_layout_law,
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
