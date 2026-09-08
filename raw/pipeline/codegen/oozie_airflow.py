"""pipeline.codegen.oozie_airflow — Oozie node/4 terms -> an Airflow 2.x DAG.

Why this file exists: the ONLY place Oozie term shapes are matched
against Airflow Python source (the Codegen law — no cross-language
branching lives here, and this file never re-reads the source .xml or an
io.json manifest; the node4 term is the only input).

Term shapes handled (see pipeline/specs/oozie.py's module docstring for
the full grammar this mirrors):
    workflow(Name, Xmlns, [Node, ...])           the one node4 record
    start(To)                                    <start to="X"/>
    end(Name)                                    <end name="X"/>
    action(Name, Body, to(OkTo), to(ErrTo))      <action name="X">...
    fork(Name, [path(Start), ...])               <fork name="X">...
    join(Name, To)                               <join name="X" to="Y"/>
    path(Start)                                  one <fork> branch
Body: shell(ExecPath) | pig(ScriptPath)

MAPPING RULE — every Oozie node becomes exactly one Airflow task, no
contraction:
    start/end/fork/join  -> EmptyOperator(task_id=<node's own name>)
    action                -> BashOperator(task_id=Name, bash_command=...)
        shell(Path)  -> `bash "<repo>/<Path>"`
        pig(Path)    -> `"<repo>/install/bin/pig11" -x local "<repo>/<Path>"`
       (install/bin/pig11 is the Java-11 Homebrew-Pig wrapper this track
        already uses for every direct Pig run — see install/bin/pig11.)
Every node's OK-transition becomes one `upstream >> downstream` line (the
phase spec's "ok-transitions -> >> chains"); ERROR transitions are parsed
into the term (to(ErrTo)) but deliberately not wired into the DAG — Oozie's
ok/error branching has no Airflow trigger-rule analogue in this vertical
slice, and wiring it in would silently misrepresent what "error" means in
Airflow's retry/trigger model. A `fork`'s several outgoing edges become
several downstream `>>` lines from the SAME upstream task (fan-out); a
`join`'s single outgoing edge, fed by every branch action's own OK edge
landing on the join's task_id, is the fan-in — no special-cased fork/join
plumbing needed beyond "every node is a task, every OK edge is a `>>`".

`start` has no name field in the grammar (Oozie's <start> is an unnamed,
one-per-workflow element) — this file gives it the fixed task_id "start".
"""
import json
from pathlib import Path

from pipeline import term_parse
from pipeline.codegen import common

REPO_ROOT = common.REPO_ROOT
PIG11 = (REPO_ROOT / "install" / "bin" / "pig11").as_posix()

# The OOZIE lane's layout law lives HERE and only here (an Airflow
# `dags_folder`, not a PySpark output dir): pipeline.run_codegen reads
# DEFAULT_OUT_DIR off this module (see its load_generator/default_out_dir)
# instead of keeping a second copy of the same path that could drift.
DEFAULT_OUT_DIR = Path("out") / "airflow" / "dags"  # repo-relative
DAGS_DIR = REPO_ROOT / DEFAULT_OUT_DIR              # absolute


def _pyvar(name):
    """An Oozie node name, as a Python identifier — same discipline as
    pig_pyspark._pyvar. Every name in this corpus is already a valid
    identifier; this just makes that a guarantee instead of an assumption."""
    out = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(name))
    if not out or out[0].isdigit():
        out = "_" + out
    return out


def _abs_repo_path(rel_path):
    """A workflow-relative path (as captured from the XML, e.g.
    'scripts/oozie/first_shell.sh') -> an absolute path under REPO_ROOT.
    Airflow's scheduler/executor does not promise `cwd == repo root` the
    way pipeline.codegen.common.run_generated guarantees for PySpark
    scripts, so every path baked into a BashOperator command here is
    absolute rather than relative."""
    return (REPO_ROOT / rel_path).as_posix()


def _bash_command(body):
    """action_body term (shell(Path) | pig(Path)) -> a bash_command string."""
    functor = body[0] if isinstance(body, tuple) else body
    if functor == "shell":
        _f, path = body
        return f'bash "{_abs_repo_path(path)}"'
    if functor == "pig":
        _f, path = body
        return f'"{PIG11}" -x local "{_abs_repo_path(path)}"'
    raise ValueError(f"oozie_airflow: unhandled action body functor {functor!r} in {body!r}")


def _task_def_and_edges(node):
    """One `node` term -> (task_id, def_line, [(from_task_id, to_task_id), ...]).
    def_line is the Python source line that constructs the task (unindented;
    the caller indents it)."""
    functor = node[0]

    if functor == "start":
        _f, to = node
        task_id = "start"
        line = f'{_pyvar(task_id)} = EmptyOperator(task_id="{task_id}")'
        return task_id, line, [(task_id, to)]

    if functor == "end":
        _f, name = node
        line = f'{_pyvar(name)} = EmptyOperator(task_id="{name}")'
        return name, line, []

    if functor == "action":
        _f, name, body, ok, err = node
        _okf, ok_to = ok
        bash_cmd = _bash_command(body)
        # cwd pinned to the repo root — same discipline pipeline.codegen.
        # common.run_generated already uses for PySpark scripts. Without it,
        # a script's own relative paths (e.g. p01_load_filter_store.pig's
        # `LOAD 'corpus/data/pig/raw_txn.csv'`) resolve against whatever
        # scratch directory Airflow's BashOperator happens to run in, not
        # against this repo.
        line = (
            f'{_pyvar(name)} = BashOperator(task_id="{name}", '
            f"bash_command={bash_cmd!r}, cwd={REPO_ROOT.as_posix()!r})"
        )
        return name, line, [(name, ok_to)]

    if functor == "fork":
        _f, name, paths = node
        line = f'{_pyvar(name)} = EmptyOperator(task_id="{name}")'
        edges = [(name, p[1]) for p in paths]  # path(Start)
        return name, line, edges

    if functor == "join":
        _f, name, to = node
        line = f'{_pyvar(name)} = EmptyOperator(task_id="{name}")'
        return name, line, [(name, to)]

    raise ValueError(f"oozie_airflow: unhandled node functor {functor!r} in {node!r}")


def _header(dag_id):
    return [
        "# AUTO-GENERATED by pipeline.codegen.oozie_airflow — DO NOT EDIT BY HAND.",
        "# Generated ONLY from out/ir/oozie/*.node4.json terms (Phase-D codegen law).",
        "from datetime import datetime",
        "",
        "from airflow import DAG",
        "from airflow.operators.bash import BashOperator",
        "from airflow.operators.empty import EmptyOperator",
        "",
    ]


def _emit_workflow(term, dag_id):
    _f, _name, _xmlns, nodes = term
    lines = [
        "with DAG(",
        f'    dag_id="{dag_id}",',
        "    start_date=datetime(2026, 1, 1),",
        "    schedule=None,",
        "    catchup=False,",
        ") as dag:",
    ]
    edges = []
    for node in nodes:
        _task_id, def_line, node_edges = _task_def_and_edges(node)
        lines.append(f"    {def_line}")
        edges.extend(node_edges)
    lines.append("")
    for from_id, to_id in edges:
        lines.append(f"    {_pyvar(from_id)} >> {_pyvar(to_id)}")
    return lines


def generate_lines(node4_entries, stem, lang="oozie"):
    """node4_entries: the parsed *.node4.json list — exactly one record for
    an oozie file (the whole file is one `workflow` statement; see
    pipeline/specs/oozie.py's module docstring). Returns the full generated
    DAG program as a list of source lines."""
    if len(node4_entries) != 1:
        raise ValueError(
            f"oozie_airflow: expected exactly 1 node4 record (the whole-file "
            f"workflow statement), got {len(node4_entries)} for stem {stem!r}"
        )
    entry = node4_entries[0]
    term = term_parse.parse_term(entry["term"])
    if not (isinstance(term, tuple) and term[0] == "workflow"):
        raise ValueError(f"oozie_airflow: top-level term is not workflow/3: {term!r}")

    lines = list(_header(stem))
    lines.append(common.blockid_header(entry["block"]))

    # DEGRADED comment mode (2026-08-26, owner-accepted): the whole file
    # is one `workflow` statement (owner decision, 2026-08-24), so EVERY
    # source comment attaches to this one seq, and per pipeline.comments'
    # attachment rule almost all of them land "inline" (there is no
    # per-action trace to give a comment its own generated line next to
    # the specific <action> it described). _emit_workflow also walks the
    # term structure, not source order, so "the nearest generated line"
    # is not well-defined here either way. Rather than fake a false
    # precision, every comment in the file is emitted as its own line,
    # in original source order, right after the blockid header — real
    # per-action placement would need per-action traces, which the
    # whole-file-is-one-statement decision rules out today.
    attachments = entry.get("comments", [])
    source_label = Path(entry["trace"]["file"]).name if entry.get("trace") else stem
    lines.extend(common.comment_lines(
        attachments, source_label,
        positions=("leading", "trailing", "inline", "prologue"),
    ))

    lines.extend(_emit_workflow(term, stem))
    lines.append("")
    return lines


def generate_file(ir_json_path, out_py_path=None, lang="oozie"):
    ir_json_path = Path(ir_json_path)
    node4_entries = json.loads(ir_json_path.read_text(encoding="utf-8"))
    stem = common.stem_of(ir_json_path)
    lines = generate_lines(node4_entries, stem, lang=lang)
    out_py_path = Path(out_py_path) if out_py_path else (DAGS_DIR / f"{stem}.py")
    common.write_program(out_py_path, lines)
    return out_py_path
