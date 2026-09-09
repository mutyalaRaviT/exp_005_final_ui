"""pipeline.tests.test_sqoop_lane — proofs for the whole SQOOP lane, end to
end: tokenise (lossless) -> gen_prolog -> fold/round-trip -> node4 -> Phase-D
codegen (Python wrapper STUBS), over the real 4-file corpus/sqoop/small
corpus (not a fixture) — same discipline test_fold_roundtrip.py and
test_codegen_pig.py already use for pig/hive, folded into one file since
this lane owns no shared fold-harness/codegen-law proof of its own to
split against (see pipeline/specs/sqoop.py and
pipeline/codegen/sqoop_python.py for what each phase actually does).

What this proves:
  1. LOSSLESS — `python3 -m pipeline.run_tokenise sqoop` exits 0, every
     corpus file's *.tokens.json says "lossless": true.
  2. FOLD + ROUND-TRIP — `python3 -m pipeline.run_fold sqoop` exits 0,
     folded_n == roundtrip_n == n (== 1) for every one of the 4 files, and
     every out/ir/sqoop/*.node4.json has exactly one cmd(Kind, Opts)
     record with a well-formed trace.
  3. THE BOOLEAN-FLAG CASE — s04's `--hive-import` (a flag with no
     following value) folds to opt('--hive-import', none), never
     misconsuming the next flag as its own value (the DCG's Opt-inside-
     Group backtracking actually resolves the ambiguity correctly, not
     just "some parse was found").
  4. STUB GENERATION — pipeline.codegen.sqoop_python.generate_lines is
     deterministic; every generated stub parses as valid Python
     (ast.parse); every stub's docstring is BYTE-IDENTICAL to the
     original sqoop command line sliced out of the corpus file via the
     node4 trace's own b0/b1 (not just "some docstring" — the actual
     source bytes, round-tripped through repr()); every stub's TODO dict
     promotes connect/table/target/format and preserves every other
     option under "extra" (see sqoop_python.py's own docstring for that
     promotion table).
  5. THE CLI — `python3 -m pipeline.run_codegen sqoop` (run in-process,
     same pattern test_codegen_pig.py uses) exits 0 and leaves all 4
     files on disk at the SQOOP lane's own flat layout,
     out/wrappers/<stem>.py (no out/pyspark/sqoop/ — these are not
     PySpark programs).

Run: python3 -m pipeline.tests.test_sqoop_lane
(needs `swipl` on PATH for the fold/round-trip phase — same as this
track's other swipl-driven work; run `eval "$(/usr/libexec/path_helper)"`
first in a fresh shell if it isn't)
"""
import ast
import json
import os
import subprocess
from pathlib import Path

from pipeline import gen_prolog, run_codegen, run_fold, run_tokenise, term_parse
from pipeline.codegen import common, sqoop_python

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "corpus" / "sqoop" / "small"
TOKENS_DIR = REPO_ROOT / "out" / "tokens" / "sqoop"
IR_DIR = REPO_ROOT / "out" / "ir" / "sqoop"
GRAMMAR_PATH = REPO_ROOT / "out" / "grammar" / "sqoop.pl"
WRAPPERS_DIR = REPO_ROOT / "out" / "wrappers"

CORPUS_STEMS = [
    "s01_import_basic",
    "s02_export_basic",
    "s03_import_query_split",
    "s04_import_hive",
]


def _swipl_available():
    try:
        subprocess.run(["swipl", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _chdir_repo_root(fn, *a, **kw):
    """Run fn(*a, **kw) with cwd == REPO_ROOT — run_tokenise/gen_prolog/
    run_fold/run_codegen all default their I/O paths relative to the
    current directory, same helper test_fold_roundtrip.py uses."""
    cwd = Path.cwd()
    try:
        os.chdir(REPO_ROOT)
        return fn(*a, **kw)
    finally:
        os.chdir(cwd)


# ---------------------------------------------------------------------
# module-level cache: regenerate everything fresh ONCE — never trust
# stale out/ artifacts left over from an earlier manual run.

_GATE = {}


def _run_gate():
    if _GATE:
        return _GATE
    tok_rc = _chdir_repo_root(run_tokenise.main, ["sqoop"])
    gen_prolog.generate("sqoop")
    fold_rc = None
    if _swipl_available():
        fold_rc = _chdir_repo_root(run_fold.main, ["sqoop"])
    _GATE["tok_rc"] = tok_rc
    _GATE["fold_rc"] = fold_rc
    return _GATE


# ---------------------------------------------------------------------
# 1. LOSSLESS

def test_run_tokenise_cli_exits_zero_lossless():
    gate = _run_gate()
    assert gate["tok_rc"] == 0, "python3 -m pipeline.run_tokenise sqoop exited non-zero"


def test_every_corpus_file_tokens_json_says_lossless_true():
    _run_gate()
    for stem in CORPUS_STEMS:
        path = TOKENS_DIR / f"{stem}.tokens.json"
        assert path.is_file(), f"missing {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["lossless"] is True, f"{stem}: lossless is not true"
        assert data["n_tokens"] > 0, f"{stem}: zero tokens"


def test_the_opt_flag_leaf_keeps_every_long_option_one_token():
    """The house rule this lane was built to prove: '--[a-z-]+' must
    tokenise a whole --long-option flag as ONE word token, never split
    into bare '-' symbol tokens by the engine's 1-char fallback."""
    _run_gate()
    for stem in CORPUS_STEMS:
        data = json.loads((TOKENS_DIR / f"{stem}.tokens.json").read_text(encoding="utf-8"))
        symbol_dashes = [
            t for t in data["tokens"] if t["kind"] == "symbol" and t["text"] == "-"
        ]
        assert not symbol_dashes, f"{stem}: a bare '-' symbol token leaked through: {symbol_dashes}"
        flag_words = [
            t for t in data["tokens"] if t["kind"] == "word" and t["text"].startswith("--")
        ]
        assert flag_words, f"{stem}: no --flag word token found at all"


# ---------------------------------------------------------------------
# 2. FOLD + ROUND-TRIP

def test_run_fold_cli_exits_zero_all_roundtripped():
    if not _swipl_available():
        return
    gate = _run_gate()
    assert gate["fold_rc"] == 0, "python3 -m pipeline.run_fold sqoop exited non-zero"


def test_every_file_has_exactly_one_folded_roundtripped_statement():
    """Each corpus file is, by design, ONE sqoop invocation == ONE
    statement (see pipeline/specs/sqoop.py's own module docstring)."""
    if not _swipl_available():
        return
    _run_gate()
    for stem in CORPUS_STEMS:
        tokens_path = TOKENS_DIR / f"{stem}.tokens.json"
        data = json.loads(tokens_path.read_text(encoding="utf-8"))
        stmts = run_fold.split_statements(data["tokens"])
        assert len(stmts) == 1, f"{stem}: expected exactly 1 statement, found {len(stmts)}"

        node4_path = IR_DIR / f"{stem}.node4.json"
        assert node4_path.is_file(), f"missing {node4_path}"
        node4 = json.loads(node4_path.read_text(encoding="utf-8"))
        assert len(node4) == 1, f"{stem}: node4.json has {len(node4)} records, expected 1"
        rec = node4[0]
        assert set(rec.keys()) == {"block", "seq", "term", "trace", "comments"}, rec
        assert set(rec["trace"].keys()) == {"file", "l0", "l1", "b0", "b1"}, rec
        assert rec["term"].startswith("cmd("), f"{stem}: term does not start with cmd(: {rec['term']!r}"


def test_boolean_flag_folds_to_none_not_a_misconsumed_neighbor():
    """s04's --hive-import must fold to opt('--hive-import', none) — the
    DCG's Opt-inside-Group backtracking must resolve the boolean-flag
    ambiguity to the semantically correct term, not merely to A term."""
    if not _swipl_available():
        return
    _run_gate()
    node4 = json.loads((IR_DIR / "s04_import_hive.node4.json").read_text(encoding="utf-8"))
    term = term_parse.parse_term(node4[0]["term"])
    _functor, kind, opts = term
    assert kind == "import"
    opts_by_name = {name: value for (_f, name, value) in opts}
    assert opts_by_name.get("--hive-import") == "none", (
        f"s04: --hive-import folded to {opts_by_name.get('--hive-import')!r}, expected 'none'"
    )
    # and --target-dir must still carry ITS OWN value, not have been eaten
    assert isinstance(opts_by_name.get("--target-dir"), tuple) and opts_by_name["--target-dir"][0] == "some", (
        f"s04: --target-dir value is {opts_by_name.get('--target-dir')!r}, expected some(...)"
    )


def test_all_four_kinds_and_option_names_match_the_source_intent():
    if not _swipl_available():
        return
    _run_gate()
    expected_kind = {
        "s01_import_basic": "import",
        "s02_export_basic": "export",
        "s03_import_query_split": "import",
        "s04_import_hive": "import",
    }
    expected_flags = {
        "s01_import_basic": {"--connect", "--table", "--target-dir", "--fields-terminated-by"},
        "s02_export_basic": {"--connect", "--table", "--export-dir"},
        "s03_import_query_split": {"--connect", "--query", "--split-by", "--target-dir"},
        "s04_import_hive": {"--connect", "--table", "--hive-import", "--target-dir"},
    }
    for stem in CORPUS_STEMS:
        node4 = json.loads((IR_DIR / f"{stem}.node4.json").read_text(encoding="utf-8"))
        term = term_parse.parse_term(node4[0]["term"])
        _functor, kind, opts = term
        assert kind == expected_kind[stem], f"{stem}: kind {kind!r} != {expected_kind[stem]!r}"
        names = {name for (_f, name, _v) in opts}
        assert names == expected_flags[stem], f"{stem}: flags {names} != {expected_flags[stem]}"


# ---------------------------------------------------------------------
# 3/4. STUB GENERATION — deterministic, ast-clean, byte-faithful docstring

def _load_node4(stem):
    path = IR_DIR / f"{stem}.node4.json"
    assert path.is_file(), f"missing IR fixture: {path} (run pipeline.run_fold sqoop first)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_stub_generation_is_deterministic():
    if not _swipl_available():
        return
    for stem in CORPUS_STEMS:
        node4 = _load_node4(stem)
        lines_a = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        lines_b = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        assert lines_a == lines_b, f"{stem}: stub generation is not deterministic"


def test_generated_stubs_parse_as_valid_python():
    if not _swipl_available():
        return
    for stem in CORPUS_STEMS:
        node4 = _load_node4(stem)
        lines = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        source = "\n".join(lines) + "\n"
        ast.parse(source, filename=f"{stem}.py")  # raises SyntaxError on failure


def test_stub_docstring_is_byte_identical_to_the_original_sqoop_line():
    if not _swipl_available():
        return
    for stem in CORPUS_STEMS:
        node4 = _load_node4(stem)
        rec = node4[0]
        trace = rec["trace"]
        source_bytes = (REPO_ROOT / trace["file"]).read_bytes()
        expected = source_bytes[trace["b0"]:trace["b1"]].decode("utf-8")

        lines = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        tree = ast.parse("\n".join(lines) + "\n", filename=f"{stem}.py")
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        doc = ast.get_docstring(fn, clean=False)
        assert doc == expected, f"{stem}: stub docstring != original source slice\n{doc!r}\n!=\n{expected!r}"


def test_stub_function_name_and_typed_return_annotation():
    if not _swipl_available():
        return
    for stem in CORPUS_STEMS:
        node4 = _load_node4(stem)
        lines = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        tree = ast.parse("\n".join(lines) + "\n", filename=f"{stem}.py")
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        assert fn.name == stem, f"{stem}: function named {fn.name!r}, expected {stem!r}"
        assert fn.returns is not None, f"{stem}: def {fn.name}() has no return type annotation"


def test_stub_todo_dict_promotes_connect_table_target_format():
    if not _swipl_available():
        return
    expected_target = {
        "s01_import_basic": "/user/hadoop/customers",
        "s02_export_basic": "/user/hadoop/customers/processed",
        "s03_import_query_split": "/user/hadoop/orders",
        "s04_import_hive": "/user/hive/warehouse/customers",
    }
    for stem in CORPUS_STEMS:
        node4 = _load_node4(stem)
        lines = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        tree = ast.parse("\n".join(lines) + "\n", filename=f"{stem}.py")
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        assign = next(
            n for n in fn.body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "TODO"
        )
        todo = ast.literal_eval(assign.value)
        assert set(todo.keys()) == {"connect", "table", "target", "format", "extra"}, (
            f"{stem}: TODO dict keys {sorted(todo.keys())}"
        )
        assert todo["connect"] == "jdbc:mysql://dbhost:3306/salesdb", f"{stem}: {todo}"
        assert todo["target"] == expected_target[stem], f"{stem}: {todo}"
        assert isinstance(todo["extra"], dict), f"{stem}: extra is not a dict: {todo}"


def test_every_stub_has_exactly_one_blockid_header():
    if not _swipl_available():
        return
    for stem in CORPUS_STEMS:
        node4 = _load_node4(stem)
        lines = sqoop_python.generate_lines(node4, stem, lang="sqoop")
        blockid_lines = [ln for ln in lines if ln.startswith("# blockid: ")]
        assert blockid_lines == ["# blockid: b_001"], f"{stem}: blockid headers {blockid_lines}"


# ---------------------------------------------------------------------
# 5. THE CLI, in-process, at the SQOOP lane's own flat out/wrappers/ layout

def test_run_codegen_cli_generates_all_four_files_under_out_wrappers():
    if not _swipl_available():
        return
    _run_gate()
    rc = _chdir_repo_root(run_codegen.main, ["sqoop"])
    assert rc == 0, "python3 -m pipeline.run_codegen sqoop exited non-zero"
    for stem in CORPUS_STEMS:
        py_path = WRAPPERS_DIR / f"{stem}.py"
        assert py_path.is_file(), f"expected generated file missing: {py_path}"
        problems = run_codegen.verify_generated(py_path)
        assert not problems, f"{stem}: {problems}"
        # the flat layout law: no out/pyspark/sqoop/ or out/wrappers/sqoop/
        # subdirectory — these are not PySpark programs.
        assert py_path.parent == WRAPPERS_DIR, f"{stem}: {py_path} not directly under {WRAPPERS_DIR}"


def test_run_codegen_default_out_dir_for_sqoop_is_out_wrappers():
    assert run_codegen.default_out_dir("sqoop") == Path("out/wrappers")
    assert run_codegen.default_out_dir("pig") == Path("out/pyspark") / "pig"


def test_generator_module_registered_for_sqoop():
    gen = run_codegen.load_generator("sqoop")
    assert gen is sqoop_python


# ---------------------------------------------------------------------

def test_every_test_in_this_file_is_registered_to_run():
    """Same self-check test_corpus_lossless.py/test_fold_roundtrip.py use:
    a test defined here but left out of TESTS would silently never run."""
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
    # 1. lossless
    test_run_tokenise_cli_exits_zero_lossless,
    test_every_corpus_file_tokens_json_says_lossless_true,
    test_the_opt_flag_leaf_keeps_every_long_option_one_token,
    # 2. fold + round-trip
    test_run_fold_cli_exits_zero_all_roundtripped,
    test_every_file_has_exactly_one_folded_roundtripped_statement,
    test_boolean_flag_folds_to_none_not_a_misconsumed_neighbor,
    test_all_four_kinds_and_option_names_match_the_source_intent,
    # 3/4. stub generation
    test_stub_generation_is_deterministic,
    test_generated_stubs_parse_as_valid_python,
    test_stub_docstring_is_byte_identical_to_the_original_sqoop_line,
    test_stub_function_name_and_typed_return_annotation,
    test_stub_todo_dict_promotes_connect_table_target_format,
    test_every_stub_has_exactly_one_blockid_header,
    # 5. the CLI
    test_run_codegen_cli_generates_all_four_files_under_out_wrappers,
    test_run_codegen_default_out_dir_for_sqoop_is_out_wrappers,
    test_generator_module_registered_for_sqoop,
    # the registry checks itself — keep this last
    test_every_test_in_this_file_is_registered_to_run,
]


def main():
    if not _swipl_available():
        print("swipl not on PATH — fold/round-trip and codegen phases will be "
              "SKIPPED (not failed). Run: eval \"$(/usr/libexec/path_helper)\" first")

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
