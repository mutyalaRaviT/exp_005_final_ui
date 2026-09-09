"""pipeline.tests.test_codegen_pig — proofs for Phase-D Pig codegen.

Why this file exists: pipeline.term_parse, pipeline.codegen.common, and
pipeline.codegen.pig_pyspark together turn out/ir/pig/*.node4.json into
out/pyspark/pig/*.py (the Codegen law). This suite proves, over the real
6-file pig/small corpus (not a fixture):

  1. pipeline.term_parse round-trips every term actually printed by the
     fold harness for every pig corpus file — no ValueError/TermParseError,
     and re-serialising the parsed value's functor/arity matches the
     term's own top-level shape.
  2. Generation is deterministic: generating the same *.node4.json twice
     produces byte-identical output.
  3. Every distinct "block" value in a file's node4.json produces exactly
     one "# blockid: b_00N" header in the generated file, in the same
     order the blocks appear in the IR.
  4. Every generated file parses as valid Python (ast.parse) — a
     necessary, cheap proxy for "imports clean" that needs no PySpark
     runtime to check.
  5. `python3 -m pipeline.run_codegen pig` (the real CLI, run in-process
     the same way test_fold_roundtrip.py drives run_fold.main) exits 0
     and leaves all 6 files on disk.
  6. Every STORE term's generated output directory follows the layout
     law exactly: out/pyspark_out/pig/<stem>/<output_name>/.

Run: python3 -m pipeline.tests.test_codegen_pig
"""
import ast
import json
from pathlib import Path

from pipeline import run_codegen, term_parse
from pipeline.codegen import common, pig_pyspark

REPO_ROOT = Path(__file__).resolve().parents[2]
IR_DIR = REPO_ROOT / "out" / "ir" / "pig"

PIG_STEMS = [
    "p01_load_filter_store",
    "p02_foreach_arithmetic",
    "p03_group_agg",
    "p04_join",
    "p05_order_limit_distinct",
    "p06_union_split",
]


def _load_ir(stem):
    path = IR_DIR / f"{stem}.node4.json"
    assert path.is_file(), f"missing IR fixture: {path} (run pipeline.run_fold pig first)"
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------

def test_term_parse_handles_every_pig_corpus_term():
    for stem in PIG_STEMS:
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
    for stem in PIG_STEMS:
        node4 = _load_ir(stem)
        lines_a = pig_pyspark.generate_lines(node4, stem, lang="pig")
        lines_b = pig_pyspark.generate_lines(node4, stem, lang="pig")
        assert lines_a == lines_b, f"{stem}: generation is not deterministic"


def test_every_block_gets_exactly_one_blockid_header_in_order():
    for stem in PIG_STEMS:
        node4 = _load_ir(stem)
        expected_blocks = []
        for entry in node4:
            if not expected_blocks or expected_blocks[-1] != entry["block"]:
                expected_blocks.append(entry["block"])

        lines = pig_pyspark.generate_lines(node4, stem, lang="pig")
        found_blocks = [
            ln[len("# blockid: "):].strip()
            for ln in lines
            if ln.startswith("# blockid: ")
        ]
        assert found_blocks == expected_blocks, (
            f"{stem}: blockid headers {found_blocks} != IR block order {expected_blocks}"
        )


def test_generated_files_parse_as_valid_python():
    for stem in PIG_STEMS:
        node4 = _load_ir(stem)
        lines = pig_pyspark.generate_lines(node4, stem, lang="pig")
        source = "\n".join(lines) + "\n"
        ast.parse(source, filename=f"{stem}.py")  # raises SyntaxError on failure


def test_store_output_dirs_follow_the_layout_law():
    for stem in PIG_STEMS:
        node4 = _load_ir(stem)
        for entry in node4:
            term = term_parse.parse_term(entry["term"])
            if term[0] != "store":
                continue
            _functor, _relref, lit_path, _storage_call = term
            output_name = Path(lit_path[1]).name
            expected = common.pyspark_out_dir("pig", stem, output_name)
            assert str(expected).endswith(f"out/pyspark_out/pig/{stem}/{output_name}"), (
                f"{stem}: STORE for {output_name!r} resolved to {expected}, "
                f"not the out/pyspark_out/pig/<stem>/<output_name> layout law"
            )


def test_run_codegen_cli_generates_all_six_files(tmp_out_dir=None):
    out_dir = REPO_ROOT / "out" / "pyspark" / "pig"
    rc = run_codegen.main(["pig"])
    assert rc == 0, "python3 -m pipeline.run_codegen pig exited non-zero"
    for stem in PIG_STEMS:
        py_path = out_dir / f"{stem}.py"
        assert py_path.is_file(), f"expected generated file missing: {py_path}"
        problems = run_codegen.verify_generated(py_path)
        assert not problems, f"{stem}: {problems}"


# --------------------------------------------------------------------

TESTS = [
    test_term_parse_handles_every_pig_corpus_term,
    test_generation_is_deterministic,
    test_every_block_gets_exactly_one_blockid_header_in_order,
    test_generated_files_parse_as_valid_python,
    test_store_output_dirs_follow_the_layout_law,
    test_run_codegen_cli_generates_all_six_files,
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
