"""Macros as lambdas.

A macro whose body contains complete steps (data/proc ... run) compiles into
a MacroLambda: a callable that, given table arguments, generates the lineage
edges of the macro body.

Block ids:
  - Within-macro (in-block) edges carry the MACRO DEFINITION's block id —
    the injected BLOCKID wrapping the %macro..%mend span when present,
    otherwise `m_<name>` — suffixed with the call instance: `<def_id>#1`,
    `<def_id>#2`, ... (and `.j` when one body holds several steps).
  - In-file edges: the pipeline places each instance's blocks at the call
    position, so FILE_FLOW naturally links the caller's blocks (their
    injected ids) with the macro instance's definition-derived ids.
"""
import re
from dataclasses import dataclass, field

from sas_lineage.blocks import split_blocks
from sas_lineage.macros import (
    MacroDef,
    _bind_args,
    _substitute_var,
    expand_invocations,
    resolve_vars,
)

_STEP_BODY = re.compile(r"(?:^|;)\s*(data|proc)\b", re.IGNORECASE | re.DOTALL)


def is_step_macro(macro: MacroDef) -> bool:
    """True when the body holds complete steps (worth its own blocks);
    False for expression macros (e.g. a table-name fragment) — those are
    inlined into the surrounding statement instead."""
    return bool(_STEP_BODY.search(macro.body))


@dataclass
class MacroLambda:
    macro: MacroDef
    def_block_id: str  # injected BLOCKID of the definition, or m_<name>
    macros: dict[str, MacroDef] = field(default_factory=dict)  # for nested calls
    lets: dict[str, str] = field(default_factory=dict)

    def instantiate(self, args: list[str], instance: int = 1) -> str:
        """The macro body with arguments (and defaults, lets, nested
        expression macros) substituted — plain SAS text."""
        body = self.macro.body
        for key, value in _bind_args(self.macro, args).items():
            body = _substitute_var(body, key, value)
        for _ in range(5):
            expanded = resolve_vars(expand_invocations(body, self.macros), self.lets)
            if expanded == body:
                break
            body = expanded
        return body

    def units(self, args: list[str], instance: int = 1):
        """(block_id, statements) pairs for one invocation, ids derived from
        the macro definition's block id."""
        base = f"{self.def_block_id}#{instance}"
        step_blocks = split_blocks(self.instantiate(args, instance))
        if len(step_blocks) <= 1:
            return [(base, statements) for statements in step_blocks]
        return [(f"{base}.{j}", statements)
                for j, statements in enumerate(step_blocks, start=1)]

    def __call__(self, *args: str, instance: int = 1, **keyword_args: str):
        """The lambda: tables in, edges out.
        `lam("raw.cust")` or `lam(t="cust")` -> the body's lineage edges."""
        from sas_lineage.graph import build_graph_from_units

        arg_list = [*args, *(f"{k}={v}" for k, v in keyword_args.items())]
        _, edges = build_graph_from_units(self.units(arg_list, instance))
        return edges


def find_step_calls(text: str, step_macros: dict[str, MacroDef]):
    """Split segment text at step-macro call sites.
    Returns parts: ("text", chunk) | ("call", name, args_list)."""
    from sas_lineage.macros import _split_args
    from sas_lineage.scanner import balanced_parentheses

    if not step_macros:
        return [("text", text)]
    names = sorted(step_macros, key=len, reverse=True)
    call_re = re.compile(
        r"%(" + "|".join(re.escape(n) for n in names) + r")\b", re.IGNORECASE
    )
    parts, last = [], 0
    for m in call_re.finditer(text):
        name = m.group(1).lower()
        end = m.end()
        j = end
        while j < len(text) and text[j].isspace():
            j += 1
        args: list[str] = []
        if j < len(text) and text[j] == "(":
            balanced = balanced_parentheses(text, j)
            if balanced:
                args = _split_args(balanced[0][1:-1])
                end = balanced[1]
        while end < len(text) and text[end] in " \t":
            end += 1
        if end < len(text) and text[end] == ";":  # the call's own terminator
            end += 1
        if text[last:m.start()].strip():
            parts.append(("text", text[last:m.start()]))
        parts.append(("call", name, args))
        last = end
    if text[last:].strip() or not parts:
        parts.append(("text", text[last:]))
    return parts
