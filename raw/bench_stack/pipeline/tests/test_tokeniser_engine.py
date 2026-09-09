"""pipeline.tests.test_tokeniser_engine — proofs for the tokeniser ENGINE.

This is deliberately NOT a test of pig.py or hive.py — those specs belong
to other agents and do not exist yet. Instead this defines a THROWAWAY
inline mini-spec (3 leaves: whitespace, word, number) and drives the
engine at pipeline.tokeniser.tokenise() to prove the contract it must
honor for every real spec later:

  1. LOSSLESS LAW  — ''.join(t["text"] for t in tokens) == text, byte for
     byte, for plain ASCII input AND for input with a multi-byte UTF-8
     character (so char-count and byte-count can't be silently conflated).
  2. SYMBOL FALLBACK — a character no leaf matches (@, :) becomes a
     single-char {"kind": "symbol"} token, never an UNKNOWN, never a raise.
  3. KEYWORD CASEFOLDING — a WORD token whose casefolded text is in the
     spec's keyword list is relabelled kind "keyword"; a WORD token that
     isn't stays kind "word". Text is untouched either way.
  4. ZERO-WIDTH EOS — a marker with b0 == b1 and text == "" appears right
     after any token whose text is in statement_end, AND unconditionally
     at end of input — including input that does NOT end in a newline
     (the exp_008 bug this contract exists to prevent).

Run: python3 -m pipeline.tests.test_tokeniser_engine
"""
from pipeline.pydsl.pydsl_lib import leaf
from pipeline.tokeniser import tokenise

# --- throwaway mini-spec: 3 leaves, never promoted to pipeline/specs/ ---
MINI_LANG = {
    "name": "mini",
    "keywords": ["select", "from"],
    "leaves": [
        leaf("ws", r"[ \t\n]+", "whitespace"),
        leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
        leaf("num", r"[0-9]+(\.[0-9]+)?", "number"),
    ],
    "statement_end": [";"],
}


def _find(tokens, text, kind=None):
    """First token matching text (and kind, if given). Raises if none."""
    for t in tokens:
        if t["text"] == text and (kind is None or t["kind"] == kind):
            return t
    raise AssertionError(f"no token found: text={text!r} kind={kind!r} in {tokens}")


def test_lossless_join_ascii():
    text = "SELECT foo FROM bar@baz:qux;\nselect x"
    tokens = tokenise(MINI_LANG, text)
    assert "".join(t["text"] for t in tokens) == text
    assert "".join(t["text"] for t in tokens).encode("utf-8") == text.encode("utf-8")


def test_symbol_fallback_on_at_and_colon():
    text = "bar@baz:qux;"
    tokens = tokenise(MINI_LANG, text)
    at_tok = _find(tokens, "@")
    colon_tok = _find(tokens, ":")
    assert at_tok["kind"] == "symbol", at_tok
    assert colon_tok["kind"] == "symbol", colon_tok
    # single character, not swallowed into anything bigger, and never UNKNOWN
    assert len(at_tok["text"]) == 1
    assert len(colon_tok["text"]) == 1
    assert all(t["kind"] != "unknown" for t in tokens)


def test_keyword_casefolding():
    text = "SELECT foo FROM bar select x"
    tokens = tokenise(MINI_LANG, text)
    words = [t for t in tokens if t["text"].casefold() in ("select", "from")]
    assert len(words) == 3  # SELECT, FROM, select
    for t in words:
        assert t["kind"] == "keyword", t
        # casefolding relabels the kind, never rewrites the text
        assert t["text"] in ("SELECT", "FROM", "select")
    foo_tok = _find(tokens, "foo")
    assert foo_tok["kind"] == "word", foo_tok  # not a keyword, stays "word"
    x_tok = _find(tokens, "x")
    assert x_tok["kind"] == "word", x_tok


def test_eos_after_statement_end_semicolon():
    text = "select x;\nfoo"
    tokens = tokenise(MINI_LANG, text)
    semi_idx = next(i for i, t in enumerate(tokens) if t["text"] == ";")
    eos_after_semi = tokens[semi_idx + 1]
    assert eos_after_semi["kind"] == "eos", eos_after_semi
    assert eos_after_semi["text"] == ""
    assert eos_after_semi["b0"] == eos_after_semi["b1"], eos_after_semi
    # b0 must sit right at the byte offset just after ';'
    semi_tok = tokens[semi_idx]
    assert eos_after_semi["b0"] == semi_tok["b1"]


def test_eof_is_always_eos_even_without_trailing_newline():
    # the exp_008 bug: input that does NOT end in a newline must still
    # get a final EOS marker.
    text = "select x"  # no trailing newline, no trailing semicolon
    assert not text.endswith("\n")
    tokens = tokenise(MINI_LANG, text)
    last = tokens[-1]
    assert last["kind"] == "eos", last
    assert last["text"] == ""
    assert last["b0"] == last["b1"] == len(text.encode("utf-8"))

    # also true for input that DOES end in ';': the statement_end rule fires
    # (eos right after ';') AND the EOF rule fires unconditionally on top of
    # it — two zero-width eos markers back to back is correct, not a bug;
    # the contract runs both rules independently and never deduplicates.
    text2 = "select x;"
    tokens2 = tokenise(MINI_LANG, text2)
    last2 = tokens2[-1]
    assert last2["kind"] == "eos", last2
    assert last2["b0"] == last2["b1"] == len(text2.encode("utf-8"))
    assert tokens2[-2]["kind"] == "eos", tokens2[-2]  # the statement_end eos
    assert tokens2[-3]["text"] == ";"


def test_eos_is_zero_width_and_never_advances_position():
    text = "x;y;"
    tokens = tokenise(MINI_LANG, text)
    eos_tokens = [t for t in tokens if t["kind"] == "eos"]
    assert len(eos_tokens) == 3  # after first ';', after second ';', and at EOF
    for t in eos_tokens:
        assert t["text"] == ""
        assert t["b0"] == t["b1"]


def test_lossless_join_multibyte_utf8():
    # 'é' is one Python character but TWO bytes in UTF-8 — proves b0/b1
    # are real byte offsets, not char counts mislabelled as bytes.
    text = "café;\nnext"
    tokens = tokenise(MINI_LANG, text)
    assert "".join(t["text"] for t in tokens) == text
    assert "".join(t["text"] for t in tokens).encode("utf-8") == text.encode("utf-8")

    e_tok = _find(tokens, "é")
    assert e_tok["kind"] == "symbol", e_tok  # not ASCII, no leaf matches it
    assert e_tok["b1"] - e_tok["b0"] == 2, e_tok  # 2 bytes, not 1
    assert len(e_tok["text"]) == 1  # but exactly 1 python character

    caf_tok = _find(tokens, "caf")
    assert caf_tok["kind"] == "word", caf_tok
    # 'caf' is 3 ASCII bytes, so 'é' must start right after it
    assert e_tok["b0"] == caf_tok["b1"]

    last = tokens[-1]
    assert last["kind"] == "eos"
    assert last["b0"] == last["b1"] == len(text.encode("utf-8"))


def test_byte_spans_tile_the_source_exactly():
    """The BYTE-OFFSET LAW (tokeniser.py rule 6), checked from outside.

    b0/b1 are the pipeline's source-of-truth for slicing raw source bytes,
    and the lossless law does NOT cover them: token text can join back
    perfectly while b0/b1 drift. So they get their own proof. The input
    mixes 1-, 2- and 4-byte UTF-8 characters, so any place the engine
    counted characters where it meant bytes shows up as a mismatch.
    """
    text = "a é;\n🚀 b"
    raw = text.encode("utf-8")
    assert len(raw) != len(text)  # the input really is multi-byte
    tokens = tokenise(MINI_LANG, text)

    cursor = 0
    for t in tokens:
        # every token starts exactly where the previous one ended
        assert t["b0"] == cursor, t
        # and its span slices back out of the raw bytes to its own text
        assert raw[t["b0"]:t["b1"]] == t["text"].encode("utf-8"), t
        cursor = t["b1"]
    # the spans together cover the whole source, ending on the last byte
    assert cursor == len(raw)

    rocket = _find(tokens, "🚀")
    assert rocket["b1"] - rocket["b0"] == 4, rocket  # 4 bytes, 1 character
    assert len(rocket["text"]) == 1


def test_token_indices_are_sequential():
    text = "select x;\nfoo@bar"
    tokens = tokenise(MINI_LANG, text)
    assert [t["i"] for t in tokens] == list(range(len(tokens)))


TESTS = [
    test_lossless_join_ascii,
    test_symbol_fallback_on_at_and_colon,
    test_keyword_casefolding,
    test_eos_after_statement_end_semicolon,
    test_eof_is_always_eos_even_without_trailing_newline,
    test_eos_is_zero_width_and_never_advances_position,
    test_lossless_join_multibyte_utf8,
    test_byte_spans_tile_the_source_exactly,
    test_token_indices_are_sequential,
]


def main():
    failures = []
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            failures.append((t.__name__, str(e)))
            print(f"FAIL  {t.__name__}: {e}")
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
