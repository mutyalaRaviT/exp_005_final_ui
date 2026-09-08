"""pipeline.codegen.sqoop_python — Sqoop node/4 terms -> Python wrapper STUBS.

Why this file exists: the ONLY place Sqoop `cmd/2` terms are matched
against Python code strings — same Codegen law as pig_pyspark.py/
hive_pyspark.py (no cross-language branching lives here; a Pig or Hive
term is simply not a shape this module's dispatcher knows). Unlike those
two, this module does NOT emit a runnable PySpark program: a Sqoop
`import`/`export` invocation moves data between an external DB and
HDFS/Hive, work no local PySpark session can stand in for, so what this
module generates is a typed, documented STUB — a function whose body
raises NotImplementedError, carrying everything a person (or a later
automated pass) needs to actually wire the command into the target
platform's real ingestion path.

Dumb-printer contract, same as pig_pyspark.py: every function here takes
an already-parsed term (pipeline.term_parse tuples/atoms/numbers/lists)
plus the node4 entry's own "trace" dict, and returns Python source text.
Nothing here re-reads a corpus *.sqoop file for anything OTHER than
slicing the exact original command text back out via trace b0/b1 (the
Codegen law's one sanctioned exception: the trace is part of the node4
record itself, not a side channel).

Term shape handled (exactly the 4-file sqoop/small corpus, see
out/ir/sqoop/*.node4.json):
    cmd(import|export, [opt(Name, none|some(Value)), ...])
        Name a bare atom carrying its source '--flag' spelling whole
        (e.g. '--connect', '--fields-terminated-by'); Value is
        none for a boolean flag with no following value (--hive-import)
        or some(col(Atom)|lit(V)) otherwise.

Layout law (SQOOP lane's own — distinct from pig/hive's out/pyspark/<lang>
layout, since these are not PySpark programs at all):
    generated wrapper stubs -> out/wrappers/<stem>.py   (flat, no lang dir)
"""
import json
from pathlib import Path

from pipeline import term_parse
from pipeline.codegen import common

# The SQOOP lane's layout law lives HERE and only here: this module owns
# where its wrapper stubs go, and pipeline.run_codegen reads DEFAULT_OUT_DIR
# off this module (see its load_generator/default_out_dir) instead of keeping
# a second copy of the same path that could drift out of step with this one.
DEFAULT_OUT_DIR = Path("out") / "wrappers"          # repo-relative
WRAPPERS_DIR = common.REPO_ROOT / DEFAULT_OUT_DIR   # absolute

# The normalized opt keys that graduate into the TODO dict's own top-level
# fields — connect/table/target/format is the fixed vocabulary this lane
# promised (see the SQOOP-lane brief); target folds BOTH --target-dir
# (import) and --export-dir (export) into one field since a wrapper only
# ever has one or the other, never both. Everything else normalized-but-
# unpromoted (--query, --split-by, --hive-import, ...) still survives,
# under "extra", so no option is ever silently dropped.
_TARGET_KEYS = ("target_dir", "export_dir")
_PROMOTED_KEYS = ("connect", "table") + _TARGET_KEYS + ("fields_terminated_by",)


def _safe_ident(name):
    """A node4 stem, as a Python identifier. Every stem in this corpus is
    already a valid identifier; this just makes that a guarantee instead
    of an assumption (same discipline as pig_pyspark._pyvar)."""
    out = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
    if not out or out[0].isdigit():
        out = "_" + out
    return out


def _opt_value(value_term):
    """none -> None; some(col(Atom)) -> Atom (str); some(lit(V)) -> V (str
    or a real number, per the string/number leaf's own dequoting)."""
    if value_term == "none":
        return None
    if isinstance(value_term, tuple) and value_term[0] == "some":
        inner = value_term[1]
        if isinstance(inner, tuple) and inner[0] in ("col", "lit"):
            return inner[1]
        raise ValueError(f"sqoop_python: unsupported option value shape {inner!r}")
    raise ValueError(f"sqoop_python: unsupported opt value term {value_term!r}")


def _opts_dict(opts):
    """[opt(Name, ValueTerm), ...] -> {normalized_key: value}, source order
    preserved (Python dicts are ordered). `Name` arrives with its leading
    '--' still attached (e.g. '--fields-terminated-by'); the normalized
    key strips it and turns the remaining dashes into underscores
    ('fields_terminated_by'), so it reads as a plain identifier-shaped
    key. A boolean flag with no value (--hive-import) maps to True."""
    out = {}
    for opt_term in opts:
        _functor, name, value_term = opt_term
        key = name.lstrip("-").replace("-", "_")
        value = _opt_value(value_term)
        out[key] = True if value is None else value
    return out


def _todo_dict(opts_dict):
    """opts_dict -> the structured TODO dict: connect/table/target/format
    promoted to top-level fields (None where this command never set one),
    every other normalized option preserved under "extra" so nothing is
    ever silently dropped on the floor."""
    target = None
    for k in _TARGET_KEYS:
        if k in opts_dict:
            target = opts_dict[k]
            break
    extra = {k: v for k, v in opts_dict.items() if k not in _PROMOTED_KEYS}
    return {
        "connect": opts_dict.get("connect"),
        "table": opts_dict.get("table"),
        "target": target,
        "format": opts_dict.get("fields_terminated_by"),
        "extra": extra,
    }


# --------------------------------------------------------------------
# top-level statement -> one stub function's source lines

def _stub_lines(term, stem, trace):
    _functor, kind, opts = term
    if kind not in ("import", "export"):
        raise ValueError(f"sqoop_python: unsupported cmd kind {kind!r} in term {term!r}")

    source_path = common.REPO_ROOT / trace["file"]
    raw = source_path.read_bytes()[trace["b0"]:trace["b1"]]
    original_line = raw.decode("utf-8")

    opts_dict = _opts_dict(opts)
    todo = _todo_dict(opts_dict)

    fn_name = _safe_ident(stem)
    return [
        f"def {fn_name}() -> None:",
        f"    {original_line!r}",
        f"    # sqoop {kind}: TODO wire this command into the target platform's real ingestion path.",
        f"    TODO = {todo!r}",
        f'    raise NotImplementedError(f"sqoop {kind} wrapper stub not implemented: {{TODO}}")',
    ]


def _emit_statement(term, stem, trace):
    functor = term[0] if isinstance(term, tuple) else term
    if functor == "cmd":
        return _stub_lines(term, stem, trace)
    raise ValueError(f"sqoop_python: unhandled top-level functor {functor!r} in term {term!r}")


# --------------------------------------------------------------------
# whole-program generation

def _module_header(stem):
    return [
        "# AUTO-GENERATED by pipeline.codegen — DO NOT EDIT BY HAND.",
        "# Generated ONLY from out/ir/sqoop/*.node4.json terms (Phase-D codegen law).",
        f'"""Sqoop wrapper stub(s) generated from {stem}.sqoop — each function\'s own',
        "docstring carries the exact original sqoop command line it was generated",
        'from; each body raises NotImplementedError with a structured TODO."""',
        "",
    ]


def generate_lines(node4_entries, stem, lang="sqoop"):
    """node4_entries: the parsed *.node4.json list (each a dict with
    "block", "seq", "term", "trace", and — 2026-08-26 — "comments").
    Returns the full generated module as a list of source lines (header,
    one "# blockid: b_00N" per distinct block followed by that block's
    statement(s)). Leading comments land above the stub's `def` line
    (module level, no indent needed); trailing/inline ones append to
    `_stub_lines`' LAST body line, which is already 4-space indented —
    with_trailing only appends text, so that indentation survives
    untouched. Sqoop's own comment leaf (pipeline/specs/sqoop.py, added
    2026-08-26 alongside this) is what makes a `#` comment in a .sqoop
    file tokenise at all — see that spec's own comment for why it didn't
    before."""
    lines = list(_module_header(stem))
    cur_block = None

    for entry in node4_entries:
        term = term_parse.parse_term(entry["term"])
        attachments = entry.get("comments", [])
        source_label = Path(entry["trace"]["file"]).name if entry.get("trace") else stem

        if entry["block"] != cur_block:
            if cur_block is not None:
                lines.append("")
            lines.append(common.blockid_header(entry["block"]))
            cur_block = entry["block"]

        lines.extend(common.comment_lines(attachments, source_label))
        stmt_lines = _emit_statement(term, stem, entry["trace"])
        if stmt_lines:
            stmt_lines[-1] = common.with_trailing(stmt_lines[-1], attachments, source_label)
        lines.extend(stmt_lines)
        lines.append("")

    return lines


def generate_file(ir_json_path, out_py_path=None, lang="sqoop"):
    ir_json_path = Path(ir_json_path)
    node4_entries = json.loads(ir_json_path.read_text(encoding="utf-8"))
    stem = common.stem_of(ir_json_path)
    lines = generate_lines(node4_entries, stem, lang=lang)
    out_py_path = Path(out_py_path) if out_py_path else (WRAPPERS_DIR / f"{stem}.py")
    common.write_program(out_py_path, lines)
    return out_py_path
