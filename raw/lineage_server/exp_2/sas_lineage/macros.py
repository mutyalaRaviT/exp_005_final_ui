"""Macro preprocessing: extract %macro definitions, expand invocations, and
resolve %let variables — all BEFORE block splitting, so downstream parsers
(including sqlglot for PROC SQL) only ever see plain SAS.

Unresolvable `&var` references are left in the text on purpose: the table
parser then reports them as `unresolved` (PARTIAL), never silently.
"""
import re
from dataclasses import dataclass, field

from sas_lineage.scanner import QUOTES, balanced_parentheses, skip_quote

_MACRO_DEF = re.compile(
    r"%macro\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s*;(.*?)%mend[^;]*;",
    re.IGNORECASE | re.DOTALL,
)
_LET = re.compile(r"%let\s+([A-Za-z_]\w*)\s*=\s*([^;]*);", re.IGNORECASE)

_MAX_PASSES = 5
_MAX_EXPANSIONS = 50  # runaway/recursive macro backstop


@dataclass
class MacroDef:
    name: str
    params: list[str] = field(default_factory=list)
    body: str = ""
    defaults: dict[str, str] = field(default_factory=dict)  # keyword params


def extract_macros(source: str):
    """Return (source without %macro..%mend blocks, {lowername: MacroDef})."""
    macros: dict[str, MacroDef] = {}

    def grab(m):
        params = [p.strip() for p in (m.group(2) or "").split(",") if p.strip()]
        names, defaults = [], {}
        for p in params:  # keyword params carry defaults: name=default
            name, _, default = p.partition("=")
            names.append(name.strip().lower())
            if default:
                defaults[name.strip().lower()] = default.strip()
        macros[m.group(1).lower()] = MacroDef(
            m.group(1), names, m.group(3).strip(), defaults
        )
        return ""

    return _MACRO_DEF.sub(grab, source), macros


def extract_lets(source: str):
    """Return (source without %let statements, {lowername: value})."""
    variables: dict[str, str] = {}

    def grab(m):
        variables[m.group(1).lower()] = m.group(2).strip()
        return ""

    return _LET.sub(grab, source), variables


def _substitute_var(text: str, name: str, value: str) -> str:
    return re.sub(rf"&{re.escape(name)}\b\.?", value.replace("\\", "\\\\"), text,
                  flags=re.IGNORECASE)


def _split_args(argtext: str) -> list[str]:
    """Split macro-call arguments on top-level commas (paren/quote aware)."""
    args, start, depth, i, n = [], 0, 0, 0, len(argtext)
    while i < n:
        ch = argtext[i]
        if ch in QUOTES:
            i = skip_quote(argtext, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(argtext[start:i].strip())
            start = i + 1
        i += 1
    tail = argtext[start:].strip()
    if tail or args:
        args.append(tail)
    return args


def _bind_args(macro: MacroDef, args: list[str]) -> dict[str, str]:
    bound: dict[str, str] = dict(macro.defaults)
    positional = iter([p for p in macro.params])
    for arg in args:
        if "=" in arg and arg.split("=", 1)[0].strip().lower() in macro.params:
            key, value = arg.split("=", 1)
            bound[key.strip().lower()] = value.strip()
        else:
            try:
                bound[next(positional)] = arg
            except StopIteration:
                pass  # extra positional arg: ignored, prototype scope
    return bound


def expand_invocations(source: str, macros: dict[str, MacroDef]) -> str:
    """Replace every %name(args) call with the macro body, params substituted."""
    out = source
    expansions = 0
    changed = True
    while changed and expansions < _MAX_EXPANSIONS:
        changed = False
        for name, macro in macros.items():
            m = re.search(rf"%{re.escape(name)}\b", out, re.IGNORECASE)
            if not m:
                continue
            end = m.end()
            j = end
            while j < len(out) and out[j].isspace():
                j += 1
            args: list[str] = []
            if j < len(out) and out[j] == "(":
                balanced = balanced_parentheses(out, j)
                if balanced:
                    args = _split_args(balanced[0][1:-1])
                    end = balanced[1]
            body = macro.body
            for key, value in _bind_args(macro, args).items():
                body = _substitute_var(body, key, value)
            out = out[: m.start()] + body + out[end:]
            expansions += 1
            changed = True
    return out


def resolve_vars(source: str, variables: dict[str, str]) -> str:
    out = source
    for name, value in variables.items():
        out = _substitute_var(out, name, value)
    return out


def expand(source: str, extra_macros: dict[str, MacroDef] | None = None):
    """Full preprocessing. Returns (expanded_source, macro_defs, let_vars).

    `extra_macros` lets callers inject definitions loaded from the global
    registry (macros defined in other files).
    """
    text, defs = extract_macros(source)
    if extra_macros:
        defs = {**{k.lower(): v for k, v in extra_macros.items()}, **defs}
    text, variables = extract_lets(text)
    for _ in range(_MAX_PASSES):
        expanded = resolve_vars(expand_invocations(text, defs), variables)
        if expanded == text:
            break
        text = expanded
    return text, defs, variables
