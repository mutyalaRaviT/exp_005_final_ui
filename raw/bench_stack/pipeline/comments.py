"""pipeline.comments — source-comment extraction and reattachment (pure
functions, no I/O), 2026-08-26.

Why this file exists: comments are tokenised (every language's tokeniser
leaf tags them `kind: "comment"`) but pipeline.run_fold's split_statements
strips them before folding — they never reach node/4 or codegen (Codegen
law: "the term is the only input", pig_pyspark.py's own docstring). This
module is the missing bridge: it reads the SAME raw token list run_fold
already has, in file order, and maps every comment to the statement it
belongs closest to, so a caller (run_fold, then codegen) can re-emit it
near the corresponding GENERATED line, tagged with its ORIGINAL source
line number.

THE CONTRACT:
  extract_comments(tokens) -> [{"line", "col", "text"}, ...]
    Every comment token, split into one entry PER PHYSICAL SOURCE LINE —
    a multi-line /* ... */ block comment becomes multiple entries, each
    carrying its own real line number, not the block's start line.

  attach_comments(comments, stmts) -> {seq_or_None: [Attachment, ...]}
    Maps each comment to exactly one statement seq and a position:
    "leading" (own line, before the statement), "trailing" (own line,
    after the statement's last line), or "inline" (embedded between two
    tokens of a multi-line statement — no clean place for its own line,
    so it renders as a TRAILING FRAGMENT on the statement's last
    generated line instead — the owner's specifically-requested fallback
    case). Comments before the very first statement attach as "leading"
    on statement 1 — there is nothing else to attach them to. Whether
    codegen renders a run of "leading" comments on statement 1
    differently (a file-header block near program_header, the
    recommended choice) from an ordinary one-line "leading" comment
    elsewhere is a RENDERING decision made by the caller, not by this
    module — attach_comments only decides WHICH statement a comment
    belongs to, never how it prints. key=None ("prologue") is reserved
    for the one genuine edge case: a file with literally zero statements
    (all comment, no code) has nothing to attach any comment to at all.

  render(attachment, source_label, comment_prefix="#") -> str
    One rendered line: "# [source_label:line] text" (or a trailing
    fragment when called from with_trailing). The language's own comment
    introducer (--, /*, <!--) inside `text` is kept VERBATIM — stripping
    it would put language-specific knowledge into this generic module,
    and keeping it makes the generated file honestly say "this text came
    from the source language", not from the generator.

ATTACHMENT ALGORITHM (attach_comments), per comment, in file order:
  1. Does the comment's line sit INSIDE some statement's own [l0, l1]
     span? If so: "trailing" when it is on that statement's LAST line
     (safe on its own line right after); otherwise "inline" — the
     owner's specifically-requested fallback case for a comment with no
     clean place of its own.
  2. Otherwise the comment sits BETWEEN statements (or before the first /
     after the last): attach to the NEARER one by line distance, ties
     going to the FOLLOWING statement — a comment written directly above
     the statement it describes is the overwhelmingly common shape, and
     that tie-break needs no special case for it.
  3. A comment with no following statement at all is "trailing" on the
     last statement; a comment before the very first statement is
     "prologue" (key None).

HONESTY NOTE: the "inline" branch has ZERO instances in this project's
corpus as of 2026-08-26 (a comment that lands inside a statement's own
line span but not on its last line) — see
pipeline/tests/fixtures/comments/inline_fallback.pig for the
purpose-built fixture that exercises it, since no real corpus file does.
"""


def extract_comments(tokens):
    out = []
    for t in tokens:
        if t["kind"] != "comment":
            continue
        for i, line_text in enumerate(t["text"].split("\n")):
            out.append({"line": t["line"] + i, "col": t["col"] if i == 0 else 1, "text": line_text})
    return out


def _get(st, key):
    return st[key] if isinstance(st, dict) else getattr(st, key)


def attach_comments(comments, stmts):
    stmts = list(stmts)
    by_seq = {}

    def emit(seq, pos, c):
        by_seq.setdefault(seq, []).append(
            {"seq": seq, "pos": pos, "line": c["line"], "text": c["text"]}
        )

    for c in comments:
        line = c["line"]
        inside = next((s for s in stmts if _get(s, "l0") <= line <= _get(s, "l1")), None)
        if inside is not None:
            pos = "trailing" if line == _get(inside, "l1") else "inline"
            emit(_get(inside, "seq"), pos, c)
            continue

        after = next((s for s in stmts if _get(s, "l0") > line), None)
        before = next((s for s in reversed(stmts) if _get(s, "l1") < line), None)
        if after is None and before is None:
            emit(None, "prologue", c)
        elif after is None:
            emit(_get(before, "seq"), "trailing", c)
        elif before is None:
            emit(_get(after, "seq"), "leading", c)
        else:
            d_after = _get(after, "l0") - line
            d_before = line - _get(before, "l1")
            if d_after <= d_before:
                emit(_get(after, "seq"), "leading", c)
            else:
                emit(_get(before, "seq"), "trailing", c)
    return by_seq


def render(attachment, source_label, comment_prefix="#"):
    """One rendered comment line's TEXT (no leading indent — the caller
    adds that): "# [source_label:line] original text"."""
    return f"{comment_prefix} [{source_label}:{attachment['line']}] {attachment['text']}".rstrip()
