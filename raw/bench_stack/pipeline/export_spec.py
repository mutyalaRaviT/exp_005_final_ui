"""pipeline.export_spec — dump pipeline/specs/<lang>.py's LANG to JSON for the
Rust engine (exp_42, 2026-09-05). The Rust engine INTERPRETS this JSON at run
time — the same data gen_prolog.py compiles to a DCG — so one spec drives
both engines and Rust is rebuilt only when a new KIND of piece appears.

Run: python3 -m pipeline.export_spec sas   (writes out/spec/<lang>.json)
"""
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def piece(p):
    k = type(p).__name__
    if k == "KW":
        return {"t": "kw", "text": p.text}
    if k == "SYM":
        return {"t": "sym", "text": p.text}
    if k == "Cap":
        return {"t": "cap", "field": p.field, "kind": p.kind}
    if k == "Group":
        return {"t": "group", "functor": p.functor, "parts": [piece(x) for x in p.parts]}
    if k == "CommaList":
        return {"t": "list", "field": p.field, "parts": [piece(x) for x in p.parts],
                "min": p.min, "sep": [piece(x) for x in p.sep]}
    if k == "Choice":
        return {"t": "choice", "field": p.field, "options": [[k, v] for k, v in p.options.items()], "default": p.default}
    if k == "Opt":
        return {"t": "opt", "parts": [piece(x) for x in p.parts]}
    if k == "RuleRef":
        return {"t": "rule", "field": p.field, "name": p.name}
    raise SystemExit(f"export_spec: unknown piece {p!r}")


def form(f):
    k = type(f).__name__
    if k == "Form":
        return {"t": "shape", "name": f.name, "shape": f.shape}
    if k == "PartsForm":
        return {"t": "parts", "name": f.name, "parts": [piece(x) for x in f.parts]}
    if k == "RuleForm":
        return {"t": "rule", "name": f.name, "rule": f.rule_name}
    raise SystemExit(f"export_spec: unknown form {f!r}")


def export(lang):
    LANG = importlib.import_module(f"pipeline.specs.{lang}").LANG
    out = {
        "name": LANG["name"],
        "keywords": LANG["keywords"],
        "statement_end": LANG["statement_end"],
        "eos_kinds": LANG.get("eos_kinds", []),
        "bracket_pairs": LANG.get("bracket_pairs", []),   # exp_42 2026-09-07
        "leaves": [{"name": lf.name, "pattern": lf.pattern, "kind": lf.term} for lf in LANG["leaves"]],
        "ladder": [{"name": lv.name, "assoc": lv.assoc,
                    "ops": [{"spelling": o.spelling, "functor": o.functor, "kind": o.kind} for o in lv.ops]}
                   for lv in LANG["ladder"]],
        "forms": [form(f) for f in LANG["forms"]],
        # M3a defect 1: keep_lexeme travels to Rust too — it decides the ARITY of
        # the term this leaf builds (lit/1 vs lit/2), which the Rust parser has to
        # mirror exactly or node/4 stops being byte-identical with Prolog's.
        "expr_leaves": [{"name": lf.name, "term": lf.term, "double_delim": lf.double_delim,
                         "keep_lexeme": lf.keep_lexeme,
                         "backslash_escape": lf.backslash_escape} for lf in LANG["expr_leaves"]],
        "statements": [{"name": st.name, "assign": st.assign, "parts": [piece(x) for x in st.parts]}
                       for st in LANG["statements"]],
        "rules": {name: [{"functor": ra.functor, "parts": [piece(x) for x in ra.parts]} for ra in alts]
                  for name, alts in LANG.get("rules", {}).items()},
        "blocks": LANG.get("blocks"),
    }
    d = ROOT / "out" / "spec"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{lang}.json"
    p.write_text(json.dumps(out, indent=1))
    print(f"wrote {p}")


if __name__ == "__main__":
    for lang in sys.argv[1:] or ["sas"]:
        export(lang)
