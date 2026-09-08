"""pipeline.tokeniser — the tokeniser ENGINE for exp_014.

Why this file exists: every language spec (pig.py, hive.py, ...) is just
data — a list of leaf regexes, a keyword list, a statement-end symbol list.
This module is the one place that walks a source string against that data
and turns it into a token stream. It is language-agnostic on purpose: teach
it a new language by writing a new spec module, never by editing this file.

THE SPEC CONTRACT (see pipeline/specs/<lang>.py):
    LANG = {
        "name": "pig" | "hive",
        "keywords": [ ...lowercase strings... ],
        "leaves": [ leaf(name, regex_pattern, kind), ... ],  # order matters
        "statement_end": [";"],
    }
`leaf()` comes from pipeline.pydsl.pydsl_lib. Its three fields, as read
here, are: lf.name (label, for humans), lf.pattern (a Python regex,
matched with re.match at the current offset), lf.term (the token kind —
one of comment, whitespace, string, number, word, symbol).

THE ENGINE RULES:
  1. At each position, try the leaves IN ORDER. The first leaf whose
     pattern matches (non-zero length) at the current position wins.
  2. A WORD token whose casefolded text is in the spec's keyword list is
     relabelled kind "keyword" (the text itself is untouched).
  3. If NO leaf matches, emit a single character as a {"kind": "symbol"}
     token. This is a fallback, not an error: single stray characters
     (`@`, `:`, `.`, ...) are legal input by construction. There is no
     UNKNOWN kind and tokenise() never raises for unmatched input.
  4. EOS marker: immediately after any token whose text is one of the
     spec's `statement_end` symbols, and unconditionally at end of input
     (EOF is EOS), append a zero-width {"kind": "eos", "text": ""}
     marker. Zero-width means b0 == b1 — it carries no source bytes and
     does not advance line/col.
  5. LOSSLESS LAW: ''.join(t["text"] for t in tokens) == text, byte for
     byte. This is not just tested externally — it is asserted inside
     tokenise() itself, every call, so a spec that breaks it fails loudly
     at the moment it happens, not three pipeline stages later.
  6. BYTE-OFFSET LAW: the b0/b1 spans tile the source exactly — each token
     starts where the last one ended, each span slices back to that token's
     own bytes, and the final span ends at the last byte. Asserted inside
     tokenise() alongside rule 5, because rule 5 does NOT imply it: token
     text can join back perfectly while b0/b1 drift.

  What NEITHER law catches: a spec whose leaves are lossless but WRONG —
  they cover every byte, just with the wrong boundaries. A missing
  block-comment leaf, for instance, still joins back byte for byte while
  burying live code inside a string or comment token. Losslessness is
  necessary, not sufficient; leaf correctness is the spec's own job.

Token shape: {"i": idx, "kind": ..., "text": ..., "line": ..., "col": ...,
"b0": ..., "b1": ...}. `i` is a running index over every emitted token,
including eos markers. line/col are 1-based and character-counted (a
tab or a multibyte character each count as one column). b0/b1 are byte
offsets into the UTF-8 encoding of `text` — the source-of-truth for slicing
raw source bytes later in the pipeline.
"""
import re


def tokenise(spec, text):
    """Tokenise `text` per `spec` (a LANG dict). Returns a list of token dicts.

    Raises AssertionError if the lossless law is violated — this should
    never happen for a well-formed spec; it is a defence, not a normal
    control-flow path.
    """
    leaves = spec["leaves"]
    compiled = [(lf, re.compile(lf.pattern)) for lf in leaves]
    keywords = {k.casefold() for k in spec.get("keywords", [])}
    stmt_end = set(spec.get("statement_end", []))
    # exp_42 (2026-09-05): a token KIND that ends a statement by itself —
    # SAS datalines: the raw block is one token and the statement ends with it.
    eos_kinds = set(spec.get("eos_kinds", []))
    # exp_42 (2026-09-07): bracket_pairs — [["(", ")"], ["[", "]"], ...]. While a
    # bracket is open, no statement ends (Python's implicit line joining: a
    # newline inside brackets is whitespace). Empty for SAS; nothing changes.
    bracket_pairs = spec.get("bracket_pairs", [])
    opens = {o for o, _c in bracket_pairs}
    closes = {c for _o, c in bracket_pairs}
    depth = 0

    n = len(text)
    pos = 0
    line = 1
    col = 1
    byte_pos = 0
    idx = 0
    tokens = []

    def emit(kind, s):
        nonlocal idx, byte_pos, line, col
        b0 = byte_pos
        b1 = b0 + len(s.encode("utf-8"))
        tokens.append({
            "i": idx,
            "kind": kind,
            "text": s,
            "line": line,
            "col": col,
            "b0": b0,
            "b1": b1,
        })
        idx += 1
        byte_pos = b1
        for ch in s:
            if ch == "\n":
                line += 1
                col = 1
            else:
                col += 1

    while pos < n:
        matched_leaf = None
        matched_text = None
        for lf, rx in compiled:
            m = rx.match(text, pos)
            if m and m.end() > pos:  # reject zero-length matches: they would loop forever
                matched_leaf = lf
                matched_text = m.group(0)
                break

        if matched_leaf is not None:
            kind = matched_leaf.term
            s = matched_text
            if kind == "word" and s.casefold() in keywords:
                kind = "keyword"
        else:
            # No leaf matched at this position: fall back to a 1-char symbol.
            # This is the "never UNKNOWN, never an error" rule — any stray
            # character (@, :, ., ...) is legal input by construction.
            kind = "symbol"
            s = text[pos:pos + 1]

        emit(kind, s)
        pos += len(s)

        if kind == "symbol" and s in opens:
            depth += 1
        elif kind == "symbol" and s in closes and depth > 0:
            depth -= 1
        if (s in stmt_end or kind in eos_kinds) and depth == 0:
            emit("eos", "")

    # EOF is EOS, always — even if the input didn't end with a statement_end
    # symbol, and even if the input doesn't end with a newline (the exp_008 bug).
    emit("eos", "")

    # LOSSLESS LAW, checked on the bytes themselves. Comparing the joined
    # str to `text` would be the same test — equal Python strings always
    # encode identically — so the comparison is done once, on the UTF-8
    # bytes, which is the level the law is actually stated at.
    #
    # Both laws are checked with an explicit `if ...: raise AssertionError`
    # rather than a bare `assert`. A bare assert is compiled OUT when Python
    # runs under -O or PYTHONOPTIMIZE, which would silently turn both gates
    # into no-ops — and run_tokenise.py writes "lossless": true for any file
    # that did not raise, so under -O that field would become an unverified
    # claim rather than a proof. The exception TYPE stays AssertionError so
    # run_tokenise's existing handler still catches it.
    raw = text.encode("utf-8")
    joined = "".join(t["text"] for t in tokens).encode("utf-8")
    if joined != raw:
        raise AssertionError(
            "LOSSLESS LAW violated: joined token bytes != source bytes "
            f"(joined {len(joined)} bytes, source {len(raw)} bytes)"
        )

    # BYTE-OFFSET LAW. b0/b1 are documented above as the source-of-truth for
    # slicing raw source bytes later in the pipeline, so they get their own
    # assertion. The lossless law alone does NOT cover them: token *text*
    # can join back perfectly while b0/b1 drift (e.g. if a byte count were
    # ever computed as a character count), and that corruption would then
    # ship silently past a green "lossless" gate. Every token must start
    # exactly where the previous one ended, its span must slice back to its
    # own bytes, and the last token must land on the end of the source.
    cursor = 0
    for t in tokens:
        if t["b0"] != cursor:
            raise AssertionError(
                f"BYTE-OFFSET LAW violated: token {t['i']} ({t['kind']}) starts at "
                f"b0={t['b0']} but the previous token ended at {cursor}"
            )
        if raw[t["b0"]:t["b1"]] != t["text"].encode("utf-8"):
            raise AssertionError(
                f"BYTE-OFFSET LAW violated: token {t['i']} ({t['kind']}) span "
                f"[{t['b0']}:{t['b1']}] does not slice back to its own text"
            )
        cursor = t["b1"]
    if cursor != len(raw):
        raise AssertionError(
            f"BYTE-OFFSET LAW violated: token spans end at byte {cursor}, "
            f"source is {len(raw)} bytes"
        )

    return tokens
