"""Top-level entry point.

analyze_source / analyze_file:
  1. resolve %include (relative to the including file)
  2. split on injected /*BLOCKID ...*/ annotations (all incoming SAS code
     arrives wrapped in these; content-hashed b_<n>_<hash8> ids are only the
     fallback)
  3. extract %macro definitions (remembering the BLOCKID wrapping each
     definition) and %let variables
  4. inline expression macros; compile step macros into MacroLambdas
  5. replace each step-macro call with its instance blocks — ids derived
     from the DEFINITION's block id (`<def_id>#<call_no>`), placed at the
     call position so FILE_FLOW links caller blocks and macro blocks
  6. build the graph

register_file: push a file's macro definitions into the global YAML registry
through the hash-guarded updater.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from sas_lineage.annotations import Segment, split_annotated
from sas_lineage.blocks import fallback_block_id, split_blocks
from sas_lineage.scanner import strip_comments
from sas_lineage.graph import build_graph_from_units
from sas_lineage.macro_lambdas import MacroLambda, find_step_calls, is_step_macro
from sas_lineage.macros import (
    MacroDef,
    expand_invocations,
    extract_lets,
    extract_macros,
    resolve_vars,
)
from sas_lineage.models import BlockResult, Edge
from sas_lineage.registry import (
    DEFAULT_REGISTRY,
    entries_for_file,
    load_macros,
    update_registry,
)

_LIBNAME = re.compile(
    r"\blibname\s+([A-Za-z_]\w*)\s+(['\"])([^'\"]+)\2", re.IGNORECASE
)
_INCLUDE = re.compile(r"%include\s+(['\"])([^'\"]+)\1\s*;", re.IGNORECASE)
_MAX_INCLUDE_DEPTH = 5


@dataclass
class MacroCall:
    name: str
    args: list[str]
    instance: int
    call_block_id: str | None  # injected BLOCKID around the call site, if any
    def_block_id: str          # id used by the instance's blocks


@dataclass
class Analysis:
    blocks: list[BlockResult]
    edges: list[Edge]
    macros: dict[str, MacroDef] = field(default_factory=dict)
    let_vars: dict[str, str] = field(default_factory=dict)
    libnames: dict[str, str] = field(default_factory=dict)  # libref -> path
    lambdas: dict[str, MacroLambda] = field(default_factory=dict)
    macro_calls: list[MacroCall] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    missing_includes: list[str] = field(default_factory=list)


def extract_libnames(source: str) -> dict[str, str]:
    """`libname raw '/data/raw';` -> {"raw": "/data/raw"} (last one wins)."""
    return {m.group(1).lower(): m.group(3) for m in _LIBNAME.finditer(source)}


def inline_includes(source: str, base_dir: Path | None,
                    includes: list[str], missing: list[str],
                    depth: int = 0) -> str:
    """Replace `%include 'file.sas';` with the file's content, recursively.
    Unresolvable includes are removed from the text but recorded in
    `missing` — never silently ignored."""

    def replace(m):
        target = Path(m.group(2))
        if not target.is_absolute() and base_dir is not None:
            target = base_dir / target
        if depth < _MAX_INCLUDE_DEPTH and target.is_file():
            includes.append(str(target))
            return inline_includes(target.read_text(), target.parent,
                                   includes, missing, depth + 1)
        missing.append(m.group(2))
        return ""

    return _INCLUDE.sub(replace, source)


def _collect_definitions(segments: list[Segment], known: dict[str, MacroDef]):
    """Strip %macro/%let out of every segment; remember which BLOCKID wrapped
    each definition. Comments are stripped first so a %macro or %call inside
    a comment can never define or trigger anything."""
    defs: dict[str, MacroDef] = dict(known)
    def_block_ids: dict[str, str] = {name: f"m_{name}" for name in known}
    lets: dict[str, str] = {}
    cleaned: list[Segment] = []
    for seg in segments:
        text, found = extract_macros(strip_comments(seg.text))
        for name, macro in found.items():
            defs[name] = macro
            # several macros in one annotated span each need a distinct id
            base = seg.block_id or f"m_{name}"
            def_block_ids[name] = f"{base}.{name}" if len(found) > 1 else base
        text, found_lets = extract_lets(text)
        lets.update(found_lets)
        cleaned.append(Segment(seg.block_id, text, seg.meta))
    return cleaned, defs, def_block_ids, lets


def analyze_source(source: str, registry_path: Path | None = None,
                   base_dir: Path | None = None) -> Analysis:
    includes: list[str] = []
    missing: list[str] = []
    source = inline_includes(source, base_dir, includes, missing)

    known = load_macros(registry_path) if registry_path else {}
    segments, defs, def_block_ids, lets = _collect_definitions(
        split_annotated(source), known
    )

    step_macros = {n: m for n, m in defs.items() if is_step_macro(m)}
    expr_macros = {n: m for n, m in defs.items() if not is_step_macro(m)}
    # lambdas expand with ALL macros so a step macro calling another step
    # macro inlines the nested body instead of silently dropping its lineage
    lambdas = {
        name: MacroLambda(macro, def_block_ids[name], macros=defs, lets=lets)
        for name, macro in step_macros.items()
    }

    units: list[tuple[str, list[str]]] = []
    calls: list[MacroCall] = []
    synthetic = 0
    instances: dict[str, int] = {}
    expanded_texts: list[str] = []

    for seg in segments:
        text = seg.text
        for _ in range(5):
            expanded = resolve_vars(expand_invocations(text, expr_macros), lets)
            if expanded == text:
                break
            text = expanded
        expanded_texts.append(text)
        annotated_count = 0
        for part in find_step_calls(text, step_macros):
            if part[0] == "call":
                _, name, args = part
                instances[name] = instances.get(name, 0) + 1
                call = MacroCall(name, args, instances[name],
                                 seg.block_id, def_block_ids[name])
                calls.append(call)
                units.extend(lambdas[name].units(args, call.instance))
                expanded_texts.append(lambdas[name].instantiate(args))
            else:
                for statements in split_blocks(part[1]):
                    if seg.block_id:
                        annotated_count += 1
                        block_id = (seg.block_id if annotated_count == 1
                                    else f"{seg.block_id}.{annotated_count}")
                    else:
                        synthetic += 1
                        block_id = fallback_block_id(synthetic, statements)
                    units.append((block_id, statements))

    blocks, edges = build_graph_from_units(units)
    return Analysis(
        blocks=blocks, edges=edges, macros=defs, let_vars=lets,
        libnames=extract_libnames("\n".join(expanded_texts)),
        lambdas=lambdas, macro_calls=calls,
        includes=includes, missing_includes=missing,
    )


def analyze_file(path: str | Path,
                 registry_path: Path | None = DEFAULT_REGISTRY) -> Analysis:
    path = Path(path)
    return analyze_source(path.read_text(), registry_path=registry_path,
                          base_dir=path.parent)


def register_file(path: str | Path, registry_path: Path = DEFAULT_REGISTRY,
                  gap_seconds: int | None = None):
    """Extract a file's %macro definitions and merge them into the registry
    via the hash-guarded updater (optimistic lock)."""
    path = Path(path)
    source = path.read_text()
    _, macros = extract_macros(source)
    if not macros:
        return None
    entries = entries_for_file(path.name, source, macros)
    return update_registry(entries, registry_path=registry_path, gap_seconds=gap_seconds)
