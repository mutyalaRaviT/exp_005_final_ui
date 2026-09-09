"""mini_spec.py — throwaway tokeniser spec paired 1:1 with
pipeline/tests/fixtures/mini_grammar.pl.

Why this file exists: pipeline.run_fold's retokenise-refold round-trip
step needs a LANG dict (pipeline.tokeniser's spec contract) to turn
print_stmt's canonical texts back into tokens. run_fold.py is generic —
it takes a spec MODULE PATH on the command line — so this is just the
spec that fixture tests pass in. It is NOT promoted to pipeline/specs/
on purpose: that directory is real out/grammar/<lang>.pl languages
(pig.py, hive.py, ...) this agent does not own, and this vocabulary only
exists to exercise mini_grammar.pl's two toy statement types (word,
symbol, keyword load/filter/by, string, number) — see that file's header
for what it parses.
"""
from pipeline.pydsl.pydsl_lib import leaf

LANG = {
    "name": "mini",
    "ext": ".mini",
    "keywords": ["load", "filter", "by"],
    "leaves": [
        # comments before whitespace, same reasoning as pipeline/specs/pig.py.
        leaf("comment", r"--[^\n]*", "comment"),
        leaf("whitespace", r"[ \t\r\n]+", "whitespace"),
        # strings: single-quoted, backslash escapes anything incl. `\'`.
        leaf("string", r"'(?:\\.|[^'\\])*'", "string"),
        leaf("number", r"\d+(?:\.\d+)?", "number"),
        leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
        # everything else (`=`, `;`, `>`) falls through to the engine's
        # 1-char symbol fallback — no leaf needed for any of them.
    ],
    "statement_end": [";"],
}
