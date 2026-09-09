"""pipeline.tests.test_oozie_lane — the Oozie XML lane, as a runnable test.

Why this file exists: pipeline/specs/oozie.py, pipeline/codegen/oozie_airflow.py,
and the small gen_prolog.py/tokeniser.py generalisations they needed (see
oozie.py's own module docstring for the DECISION log) together turn
corpus/oozie/small/*.xml into out/airflow/dags/*.py. This suite is the gate
for that whole lane, same self-registering TESTS-list shape as
test_corpus_lossless.py (Phase B) and test_fold_roundtrip.py (Phase C):

  1. LOSSLESS (Phase B) — every corpus file tokenises with lossless=true,
     zero UNKNOWN kinds, every stream ends with eos (same three checks
     test_corpus_lossless.py runs for pig/hive, run here for oozie).
  2. FOLD + ROUND-TRIP (Phase C) — `python3 -m pipeline.gen_prolog oozie`
     then `python3 -m pipeline.run_fold oozie`, in-process, the same two
     commands a human runs by hand: every file folds to ONE term (the
     whole-file `workflow/3` statement — see oozie.py's DECISION) and
     passes the print -> retokenise -> refold term fixpoint. node4.json
     exists per file with exactly that one record.
  3. CODEGEN (Phase D) — `python3 -m pipeline.run_codegen oozie` writes
     out/airflow/dags/<stem>.py for every corpus file: valid Python
     (ast.parse), carries a "# blockid: b_00N" header, AND — the part
     ast.parse alone can't prove — actually IMPORT-CONSTRUCTS cleanly
     under the project .venv's python (`airflow.DAG(...)` runs for real,
     proving every operator/import resolves, not just that the source
     parses).
  4. THE DAG'S SHAPE (Phase D) — the `>>` edge set of each generated DAG,
     read back out with ast, is EXACTLY the transition set of its own
     folded term, and w03's <fork>/<join> is asserted by name to fan OUT
     to both branches and fan IN to one join task with no orphan tasks
     left over. Checks 1-3 all stay green if codegen silently drops a
     fork branch (the DAG still parses and still constructs); this is the
     check that does not.

This suite does NOT drive `airflow dags test` (a real DagRun needs an
initialised AIRFLOW_HOME/metadata DB and takes real wall-clock time,
including a live Pig invocation for w02) — that is the separate, slower
end-to-end EXECUTE step logged to logs/airflow_w0{1,2,3}.log. This file
proves the generated DAGs are correct and importable; the log files prove
they actually ran.

Run: python3 -m pipeline.tests.test_oozie_lane
(needs `swipl` on PATH; run `eval "$(/usr/libexec/path_helper)"` first in a
fresh shell if it isn't, same as this track's other swipl-driven work)
"""
import ast
import json
import os
import subprocess
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from pipeline import gen_prolog, run_codegen, run_fold, run_tokenise
from pipeline.codegen.common import DEFAULT_VENV_PYTHON
from pipeline.specs.oozie import LANG as OOZIE

REPO_ROOT = Path(__file__).resolve().parents[2]

CORPUS_STEMS = ["w01_shell_chain", "w02_pig_action", "w03_fork_join"]

ALLOWED_KINDS = {"comment", "whitespace", "string", "word", "keyword", "symbol", "eos"}


def _swipl_available():
    try:
        subprocess.run(["swipl", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _chdir_repo_root(fn, *a, **kw):
    cwd = Path.cwd()
    try:
        os.chdir(REPO_ROOT)
        return fn(*a, **kw)
    finally:
        os.chdir(cwd)


# ---------------------------------------------------------------------
# module-level cache: run the tokenise -> grammar -> fold -> codegen gate
# ONCE; every test below reads the results or the on-disk artifacts the
# gate just wrote, same discipline as test_fold_roundtrip.py's _run_gate.

_GATE = {}


def _run_gate():
    if _GATE:
        return _GATE

    rc_tok = _chdir_repo_root(run_tokenise.main, ["oozie"])
    gen_prolog.generate("oozie")

    buf = StringIO()
    with redirect_stdout(buf):
        rc_fold = _chdir_repo_root(run_fold.main, ["oozie"])
    fold_output = buf.getvalue()

    buf2 = StringIO()
    with redirect_stdout(buf2):
        rc_codegen = _chdir_repo_root(run_codegen.main, ["oozie"])
    codegen_output = buf2.getvalue()

    _GATE.update({
        "rc_tok": rc_tok,
        "rc_fold": rc_fold,
        "fold_output": fold_output,
        "rc_codegen": rc_codegen,
        "codegen_output": codegen_output,
    })
    return _GATE


def _load_token_records():
    out_dir = REPO_ROOT / "out" / "tokens" / "oozie"
    paths = sorted(out_dir.glob("*.tokens.json"))
    assert paths, f"no token output files found under {out_dir} — did the CLI run?"
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in paths]


# ---------------------------------------------------------------------
# Phase B: lossless

def test_tokenise_cli_exits_zero():
    gate = _run_gate()
    assert gate["rc_tok"] == 0, f"python3 -m pipeline.run_tokenise oozie exited {gate['rc_tok']}"


def test_every_file_lossless_true():
    _run_gate()
    for path, rec in _load_token_records():
        assert rec["lossless"] is True, f"{path}: lossless != true"
        src_path = Path(rec["file"])
        assert src_path.exists(), f"{path}: source file missing ({src_path})"
        joined = "".join(t["text"] for t in rec["tokens"])
        source_text = src_path.read_text(encoding="utf-8")
        assert joined == source_text, f"{path}: joined token text != source text"


def test_zero_unknown_kinds_everywhere():
    _run_gate()
    for path, rec in _load_token_records():
        for t in rec["tokens"]:
            assert t["kind"] != "unknown", f"{path}: found kind=='unknown' token {t}"
            assert t["kind"] in ALLOWED_KINDS, f"{path}: found kind {t['kind']!r} outside {ALLOWED_KINDS}"


def test_every_stream_ends_with_eos():
    _run_gate()
    for path, rec in _load_token_records():
        toks = rec["tokens"]
        assert toks, f"{path}: empty token stream"
        last = toks[-1]
        assert last["kind"] == "eos", f"{path}: last token is not eos: {last}"
        assert last["text"] == "" and last["b0"] == last["b1"], f"{path}: eos marker not zero-width: {last}"


def test_every_oozie_corpus_stem_produced_tokens():
    _run_gate()
    got = {p.stem[: -len(".tokens")] if p.stem.endswith(".tokens") else p.stem
           for p, _ in _load_token_records()}
    missing = [s for s in CORPUS_STEMS if s not in got]
    assert not missing, f"missing token output for: {missing}"


# ---------------------------------------------------------------------
# Phase C: fold + round-trip (the whole file is ONE workflow/3 statement)

def test_gen_prolog_writes_oozie_grammar():
    _run_gate()
    grammar_path = REPO_ROOT / "out" / "grammar" / "oozie.pl"
    assert grammar_path.is_file(), f"missing {grammar_path}"


def test_run_fold_cli_exits_zero():
    if not _swipl_available():
        return
    gate = _run_gate()
    assert gate["rc_fold"] == 0, (
        f"python3 -m pipeline.run_fold oozie exited {gate['rc_fold']}\n{gate['fold_output']}"
    )
    assert "ALL FOLDED AND ROUND-TRIPPED: true" in gate["fold_output"], gate["fold_output"]


def test_every_file_folds_to_exactly_one_statement_and_roundtrips():
    """Each corpus file is ONE workflow-app element -> ONE statement (the
    module DECISION: statement_end == []) — folded_n == roundtrip_n == 1,
    not just nonzero, for every one of the 3 files."""
    if not _swipl_available():
        return
    gate = _run_gate()
    # Parse the gate table directly instead of pattern-matching its padding.
    import re
    row_re = re.compile(r"^(\S+)\s+(\d+)/(\d+)\s+(\d+)/(\d+)\s+(OK|FAIL)\s*$")
    rows = {}
    for line in gate["fold_output"].splitlines():
        m = row_re.match(line)
        if m:
            s, folded_n, n1, roundtrip_n, n2, verdict = m.groups()
            rows[s] = (int(folded_n), int(n1), int(roundtrip_n), int(n2), verdict)
    for stem in CORPUS_STEMS:
        assert stem in rows, f"{stem}: never appeared in the run_fold gate table\n{gate['fold_output']}"
        folded_n, n, roundtrip_n, n2, verdict = rows[stem]
        assert n == 1, f"{stem}: expected exactly 1 statement (whole file), got {n}"
        assert folded_n == 1, f"{stem}: folded {folded_n}/1"
        assert roundtrip_n == 1, f"{stem}: roundtrip {roundtrip_n}/1"
        assert verdict == "OK", f"{stem}: verdict {verdict!r}"


def test_node4_json_has_exactly_one_workflow_record_per_file():
    if not _swipl_available():
        return
    _run_gate()
    out_dir = REPO_ROOT / "out" / "ir" / "oozie"
    for stem in CORPUS_STEMS:
        json_path = out_dir / f"{stem}.node4.json"
        assert json_path.is_file(), f"missing {json_path}"
        node4 = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(node4) == 1, f"{stem}: expected 1 node4 record, got {len(node4)}"
        rec = node4[0]
        assert set(rec.keys()) == {"block", "seq", "term", "trace", "comments"}, rec
        assert rec["term"].startswith("workflow("), f"{stem}: term is not workflow/3: {rec['term']!r}"


def test_workflow_terms_carry_the_documented_node_functors():
    """Every node inside a folded workflow/3's node list is one of the five
    functors oozie.py's `RULES["node"]` declares — start/1, end/1,
    action/4, fork/2, join/2 — proving the fold produced the SHAPE the
    codegen module (and its own docstring) assumes, not just *a* term."""
    if not _swipl_available():
        return
    _run_gate()
    from pipeline import term_parse
    known = {"start", "end", "action", "fork", "join"}
    out_dir = REPO_ROOT / "out" / "ir" / "oozie"
    seen = set()
    for stem in CORPUS_STEMS:
        node4 = json.loads((out_dir / f"{stem}.node4.json").read_text(encoding="utf-8"))
        term = term_parse.parse_term(node4[0]["term"])
        assert term[0] == "workflow" and len(term) == 4, f"{stem}: {term!r}"
        _f, _name, _xmlns, nodes = term
        assert isinstance(nodes, list) and nodes, f"{stem}: empty node list"
        for node in nodes:
            functor = node[0] if isinstance(node, tuple) else node
            assert functor in known, f"{stem}: unexpected node functor {functor!r} in {node!r}"
            seen.add(functor)
    # every corpus file together exercises every node kind at least once
    assert seen == known, f"corpus never exercised: {known - seen}"


# ---------------------------------------------------------------------
# Phase D: codegen (out/airflow/dags/<stem>.py) + real import-construct

def test_run_codegen_cli_exits_zero():
    if not _swipl_available():
        return
    gate = _run_gate()
    assert gate["rc_codegen"] == 0, (
        f"python3 -m pipeline.run_codegen oozie exited {gate['rc_codegen']}\n{gate['codegen_output']}"
    )
    assert "ALL GENERATED: true" in gate["codegen_output"], gate["codegen_output"]


def test_dag_files_exist_and_ast_parse_clean_with_blockid_header():
    if not _swipl_available():
        return
    _run_gate()
    dags_dir = REPO_ROOT / "out" / "airflow" / "dags"
    for stem in CORPUS_STEMS:
        py_path = dags_dir / f"{stem}.py"
        assert py_path.is_file(), f"missing {py_path}"
        text = py_path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(py_path))  # raises SyntaxError on failure
        blockid_lines = [ln for ln in text.splitlines() if ln.startswith("# blockid: ")]
        assert blockid_lines, f"{stem}: no '# blockid: b_00N' header found"
        for ln in blockid_lines:
            rest = ln[len("# blockid: "):].strip()
            assert rest.startswith("b_") and rest[2:].isdigit(), f"{stem}: malformed {ln!r}"


def _dag_edges(py_path):
    """The generated DAG's dependency edges, read back out of the emitted
    Python itself: every top-level `a >> b` statement inside the `with
    DAG(...)` body, as a set of (upstream_task, downstream_task) name
    pairs. Read via ast (an RShift BinOp expression statement), not by
    string-matching the source text, so re-indentation or a formatting
    change never silently turns this proof off."""
    tree = ast.parse(Path(py_path).read_text(encoding="utf-8"), filename=str(py_path))
    edges = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr)
                and isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.RShift)
                and isinstance(node.value.left, ast.Name)
                and isinstance(node.value.right, ast.Name)):
            edges.add((node.value.left.id, node.value.right.id))
    return edges


def _expected_edges_from_term(term):
    """The edge set the folded workflow/3 term REQUIRES the DAG to contain,
    derived from the term alone (not from the generated file): `start(To)`
    contributes start->To, `action(Name,_,to(Ok),_)` contributes Name->Ok,
    `fork(Name,[path(P),...])` contributes ONE edge per path (the fan-out),
    `join(Name,To)` contributes Name->To, `end/1` contributes none. Error
    transitions are deliberately excluded — oozie_airflow.py's docstring
    says they are parsed but never wired, and this mirrors that decision so
    the two cannot drift apart silently."""
    _f, _name, _xmlns, nodes = term
    edges = set()
    for node in nodes:
        functor = node[0]
        if functor == "start":
            edges.add(("start", node[1]))
        elif functor == "action":
            _fn, name, _body, ok, _err = node
            edges.add((name, ok[1]))
        elif functor == "fork":
            _fn, name, paths = node
            for p in paths:
                edges.add((name, p[1]))
        elif functor == "join":
            _fn, name, to = node
            edges.add((name, to))
    return edges


def test_generated_dag_edges_match_the_folded_terms_transitions():
    """The `>>` structure of every generated DAG is EXACTLY the transition
    set of its folded term — no edge invented, and (the case that matters)
    no edge dropped. Without this, a codegen bug that emitted only the
    first branch of a <fork> would leave every other test in this file
    green: the DAG would still ast.parse and still import-construct
    cleanly, just with an orphaned task nobody ever runs."""
    if not _swipl_available():
        return
    _run_gate()
    from pipeline import term_parse
    ir_dir = REPO_ROOT / "out" / "ir" / "oozie"
    dags_dir = REPO_ROOT / "out" / "airflow" / "dags"
    for stem in CORPUS_STEMS:
        node4 = json.loads((ir_dir / f"{stem}.node4.json").read_text(encoding="utf-8"))
        expected = _expected_edges_from_term(term_parse.parse_term(node4[0]["term"]))
        actual = _dag_edges(dags_dir / f"{stem}.py")
        assert actual == expected, (
            f"{stem}: generated DAG edges do not match the folded term's transitions\n"
            f"  missing from the DAG: {sorted(expected - actual)}\n"
            f"  invented by the DAG:  {sorted(actual - expected)}"
        )


def test_w03_fork_join_produces_real_fan_out_and_fan_in():
    """The fork/join case, stated literally rather than derived — w03's
    <fork name="split"> must fan OUT to both branches from the SAME
    upstream task, and both branches must fan IN to the single `joined`
    task. This is the shape the whole Oozie->Airflow mapping exists to
    preserve, so it is asserted by name and not left implicit."""
    if not _swipl_available():
        return
    _run_gate()
    edges = _dag_edges(REPO_ROOT / "out" / "airflow" / "dags" / "w03_fork_join.py")
    assert edges == {
        ("start", "split"),
        ("split", "branch_a"),
        ("split", "branch_b"),
        ("branch_a", "joined"),
        ("branch_b", "joined"),
        ("joined", "end"),
    }, f"w03 edge set is not the expected fork/join shape: {sorted(edges)}"

    fan_out = {d for u, d in edges if u == "split"}
    assert fan_out == {"branch_a", "branch_b"}, f"fork fan-out is not both branches: {fan_out}"
    fan_in = {u for u, d in edges if d == "joined"}
    assert fan_in == {"branch_a", "branch_b"}, f"join fan-in is not both branches: {fan_in}"

    # no orphans: every task defined in the DAG participates in at least one
    # edge — the exact symptom a dropped fan-out edge produces.
    defined = _dag_task_ids(REPO_ROOT / "out" / "airflow" / "dags" / "w03_fork_join.py")
    wired = {n for e in edges for n in e}
    assert defined == wired, f"w03 tasks defined but never wired into the DAG: {sorted(defined - wired)}"


def _dag_task_ids(py_path):
    """Every task variable assigned inside the generated DAG body — the
    `name = SomeOperator(task_id=...)` left-hand sides."""
    tree = ast.parse(Path(py_path).read_text(encoding="utf-8"), filename=str(py_path))
    ids = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)):
            ids.add(node.targets[0].id)
    return ids


def test_dag_files_import_construct_under_the_project_venv():
    """The real proof ast.parse can't give: every generated DAG file
    actually BUILDS an `airflow.DAG` when run under the project .venv's
    python — every operator class resolves, every DAG(...) kwarg is
    accepted by the installed Airflow version, with exit code 0 and no
    exception. This is the "import-construct" check the phase spec calls
    for, run as a real subprocess (not just `python -c "import ..."`) so a
    bug that only bites when the `with DAG(...):` block actually executes
    is caught here too."""
    if not _swipl_available():
        return
    _run_gate()
    assert DEFAULT_VENV_PYTHON.is_file(), f"missing venv python: {DEFAULT_VENV_PYTHON}"
    dags_dir = REPO_ROOT / "out" / "airflow" / "dags"
    for stem in CORPUS_STEMS:
        py_path = dags_dir / f"{stem}.py"
        proc = subprocess.run(
            [str(DEFAULT_VENV_PYTHON), str(py_path)],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, (
            f"{stem}: import-construct failed (exit {proc.returncode})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


# ---------------------------------------------------------------------

def test_every_test_in_this_file_is_registered_to_run():
    """Same self-check as test_corpus_lossless.py / test_fold_roundtrip.py:
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
    # Phase B — lossless
    test_tokenise_cli_exits_zero,
    test_every_file_lossless_true,
    test_zero_unknown_kinds_everywhere,
    test_every_stream_ends_with_eos,
    test_every_oozie_corpus_stem_produced_tokens,
    # Phase C — fold + round-trip
    test_gen_prolog_writes_oozie_grammar,
    test_run_fold_cli_exits_zero,
    test_every_file_folds_to_exactly_one_statement_and_roundtrips,
    test_node4_json_has_exactly_one_workflow_record_per_file,
    test_workflow_terms_carry_the_documented_node_functors,
    # Phase D — codegen + import-construct
    test_run_codegen_cli_exits_zero,
    test_dag_files_exist_and_ast_parse_clean_with_blockid_header,
    test_generated_dag_edges_match_the_folded_terms_transitions,
    test_w03_fork_join_produces_real_fan_out_and_fan_in,
    test_dag_files_import_construct_under_the_project_venv,
    # the registry checks itself — keep this last
    test_every_test_in_this_file_is_registered_to_run,
]


def main():
    if not _swipl_available():
        print("swipl not on PATH — the fold/codegen gate cannot run without it.\n"
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
