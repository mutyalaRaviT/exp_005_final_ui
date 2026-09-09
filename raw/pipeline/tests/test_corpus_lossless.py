"""pipeline.tests.test_corpus_lossless — the Phase B gate, as a runnable test.

Why this file exists: pipeline/tests/test_tokeniser_engine.py proves the
tokeniser ENGINE's contract against a throwaway mini-spec. This file proves
the real specs (pipeline/specs/pig.py, pipeline/specs/hive.py) hold that
contract over the actual corpus — the same two commands a human runs by
hand:

    python3 -m pipeline.run_tokenise pig
    python3 -m pipeline.run_tokenise hive

THE GATE (Phase B, exp_014):
  1. Every corpus file tokenises with lossless=true (run_tokenise's own
     exit code is 0 for each language — a spec bug or AssertionError
     inside tokenise() would flip that to 1).
  2. Zero UNKNOWN kinds anywhere in any token stream. The engine has no
     UNKNOWN kind by design (see pipeline/tokeniser.py's docstring, rule 3:
     an unmatched character falls back to a 1-char "symbol" token, never
     an error, never an "unknown" kind) — this test verifies that design
     promise holds for real output, not just by reading the source.
  3. Every file's token stream ends with an eos marker (kind "eos",
     text "", b0 == b1) — EOF is EOS, unconditionally.
  4. Spot-check: every ';' token is immediately followed by an eos marker
     (the statement_end rule, not just the EOF rule).

This test reruns the CLI exactly as the gate does (via run_tokenise.main,
in-process — same code path as `python3 -m pipeline.run_tokenise <lang>`)
so a regression in the runner's own file discovery (e.g. corpus files
living under corpus/<lang>/small/ instead of corpus/<lang>/ directly) is
caught here too, not just a change to tokeniser.py or the specs.

Run: python3 -m pipeline.tests.test_corpus_lossless
"""
import json
from pathlib import Path

from pipeline import run_tokenise
from pipeline.tokeniser import tokenise
from pipeline.specs.hive import LANG as HIVE
from pipeline.specs.pig import LANG as PIG

REPO_ROOT = Path(__file__).resolve().parents[2]

# All kinds tokenise() is allowed to emit. "unknown" is deliberately absent —
# see pipeline/tokeniser.py: there is no UNKNOWN kind by design.
ALLOWED_KINDS = {"comment", "whitespace", "string", "number", "word", "keyword", "symbol", "eos"}

LANGS = ["pig", "hive"]


def _run_lang_cli(lang):
    """Run the CLI exactly as the gate does; return its exit code."""
    cwd = Path.cwd()
    try:
        import os
        os.chdir(REPO_ROOT)
        return run_tokenise.main([lang])
    finally:
        os.chdir(cwd)


def _load_token_records(lang):
    out_dir = REPO_ROOT / "out" / "tokens" / lang
    paths = sorted(out_dir.glob("*.tokens.json"))
    assert paths, f"no token output files found under {out_dir} — did the CLI run?"
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def test_cli_exits_zero_for_every_language():
    for lang in LANGS:
        rc = _run_lang_cli(lang)
        assert rc == 0, f"python3 -m pipeline.run_tokenise {lang} exited {rc} (expected 0)"


def test_every_file_lossless_true():
    for lang in LANGS:
        for path, rec in _load_token_records(lang):
            assert rec["lossless"] is True, f"{path}: lossless != true ({rec.get('lossless')!r})"
            src_path = Path(rec["file"])
            assert src_path.exists(), f"{path}: source file missing ({src_path})"
            joined = "".join(t["text"] for t in rec["tokens"])
            source_text = src_path.read_text(encoding="utf-8")
            assert joined == source_text, f"{path}: joined token text != source text"
            assert joined.encode("utf-8") == source_text.encode("utf-8"), (
                f"{path}: joined token text != source text at byte level"
            )


def test_zero_unknown_kinds_everywhere():
    for lang in LANGS:
        for path, rec in _load_token_records(lang):
            for t in rec["tokens"]:
                assert t["kind"] != "unknown", f"{path}: found kind=='unknown' token {t}"
                assert t["kind"] in ALLOWED_KINDS, f"{path}: found kind {t['kind']!r} outside the allowed set {t}"


def test_every_stream_ends_with_eos():
    for lang in LANGS:
        for path, rec in _load_token_records(lang):
            toks = rec["tokens"]
            assert toks, f"{path}: empty token stream"
            last = toks[-1]
            assert last["kind"] == "eos", f"{path}: last token is not eos: {last}"
            assert last["text"] == "", f"{path}: eos marker is not zero-width (text): {last}"
            assert last["b0"] == last["b1"], f"{path}: eos marker is not zero-width (bytes): {last}"


def test_semicolon_spot_check_emits_eos():
    """Spot-check the statement_end rule: every ';' is immediately followed
    by an eos marker, in every corpus file that contains at least one ';'."""
    saw_a_semicolon = False
    for lang in LANGS:
        for path, rec in _load_token_records(lang):
            toks = rec["tokens"]
            for i, t in enumerate(toks):
                if t["text"] == ";":
                    saw_a_semicolon = True
                    assert i + 1 < len(toks), f"{path}: ';' at end of token list with no following eos"
                    nxt = toks[i + 1]
                    assert nxt["kind"] == "eos", f"{path}: ';' not immediately followed by eos, got {nxt}"
                    assert nxt["text"] == "" and nxt["b0"] == nxt["b1"], f"{path}: eos after ';' not zero-width: {nxt}"
    assert saw_a_semicolon, "no ';' found in any corpus file — spot-check did not exercise anything"


# --------------------------------------------------------------------------
# Adversarial spec probes — snippets the corpus does not contain.
#
# Why these live here: the six corpus files are clean, so tokenising them
# green proves less than it looks. It cannot catch a spec whose leaves are
# lossless but WRONG — covering every byte with the wrong boundaries. The
# Hive spec shipped exactly that bug (no block-comment leaf), and every
# test above stayed green through it, because the mangled text still joined
# back byte for byte. These probes attack the leaf ORDER directly.
# --------------------------------------------------------------------------

SPECS = [("pig", PIG), ("hive", HIVE)]


def _kinds_of(spec, text):
    return [(t["kind"], t["text"]) for t in tokenise(spec, text)]


def test_block_comment_is_one_token_in_every_spec():
    """A /* ... */ comment must be consumed whole by BOTH specs.

    The two ways this breaks, both seen for real in hive.py before the
    block-comment leaf was added:
      - an apostrophe inside the comment ("don't") opens a string that runs
        past the closing */ and buries live SQL inside a string token;
      - a `--` inside the comment matches the line-comment leaf, which then
        eats the closing */ and the entire following statement.
    """
    for lang, spec in SPECS:
        for body in ["/* plain */", "/* don't */", "/* -- note */", "/* a; b */"]:
            toks = tokenise(spec, body)
            comments = [t for t in toks if t["kind"] == "comment"]
            assert len(comments) == 1, f"{lang}: {body!r} -> not one comment token: {toks}"
            assert comments[0]["text"] == body, f"{lang}: {body!r} -> comment was {comments[0]['text']!r}"
            # nothing leaked out of the comment as a string or a keyword
            assert not [t for t in toks if t["kind"] in ("string", "keyword")], (
                f"{lang}: {body!r} leaked non-comment tokens: {toks}"
            )


def test_comment_never_swallows_the_statement_after_it():
    """Code following a block comment must survive as real tokens.

    The check is on the KIND FAMILY, not on a specific kind: `SELECT` is a
    keyword to the Hive spec but an ordinary word to the Pig spec (Pig Latin
    does not reserve it), and both are correct. What must never happen is
    `SELECT` arriving as comment or string text — that is the masking bug.
    """
    for lang, spec in SPECS:
        for prefix in ["/* don't */", "/* -- note */"]:
            text = f"{prefix} SELECT 1;"
            toks = tokenise(spec, text)
            select_toks = [t for t in toks if t["text"] == "SELECT"]
            assert len(select_toks) == 1, (
                f"{lang}: SELECT after {prefix!r} did not survive as its own token: {toks}"
            )
            assert select_toks[0]["kind"] in ("word", "keyword"), (
                f"{lang}: SELECT after {prefix!r} was masked as "
                f"{select_toks[0]['kind']}: {toks}"
            )
            # the ';' still ends a statement, so its eos still fires
            texts = [t["text"] for t in toks]
            assert ";" in texts, f"{lang}: ';' after {prefix!r} was swallowed: {toks}"
            semi = texts.index(";")
            assert toks[semi + 1]["kind"] == "eos", f"{lang}: ';' lost its eos: {toks}"


def test_leaf_order_does_not_let_comments_mask_strings():
    """`--` inside a string is string content, not the start of a comment."""
    for lang, spec in SPECS:
        for text in ["'a--b'", "'a;b'", "'/* x */'"]:
            toks = [t for t in tokenise(spec, text) if t["kind"] != "eos"]
            assert len(toks) == 1 and toks[0]["kind"] == "string", (
                f"{lang}: {text!r} did not stay one string token: {toks}"
            )
            assert toks[0]["text"] == text
        # a ';' inside a string must NOT fire the statement_end rule
        assert not [t for t in tokenise(spec, "'a;b'") if t["kind"] == "eos"][:-1], (
            f"{lang}: ';' inside a string emitted a spurious eos"
        )


def test_leaf_order_does_not_let_strings_mask_comments():
    """An apostrophe inside a line comment is comment text, not a string."""
    for lang, spec in SPECS:
        text = "-- don't\n"
        toks = tokenise(spec, text)
        assert ("comment", "-- don't") in _kinds_of(spec, text), f"{lang}: {toks}"
        assert not [t for t in toks if t["kind"] == "string"], f"{lang}: {toks}"


def test_escaped_quote_does_not_break_string_pairing():
    """A quote escaped INSIDE a literal must not end that literal.

    This is the bug the Hive spec shipped: its string leaves knew only the
    doubled-quote escape ('') and not the backslash escape (\\'), so
    `SELECT 'don\\'t' AS a, 'ok' AS b FROM t;` tokenised as string `'don\\'`,
    word `t`, string `' AS a, '` — the live SQL `AS a,` buried inside a
    string token and every later quote paired off by one. It stayed
    byte-for-byte lossless throughout, which is exactly why no other test
    here could see it.

    Each case is (spec, source, the one string token it must produce). The
    cases are per-language on purpose: the backslash escape is valid in both
    Pig and Hive, but the doubled-quote escape is Hive's alone.
    """
    cases = [
        ("pig", PIG, r"'don\'t'", r"'don\'t'"),
        ("pig", PIG, r"'back\\'", r"'back\\'"),
        ("hive", HIVE, r"'don\'t'", r"'don\'t'"),
        ("hive", HIVE, r"'back\\'", r"'back\\'"),
        ("hive", HIVE, "'don''t'", "'don''t'"),
        ("hive", HIVE, r'"say \"hi\""', r'"say \"hi\""'),
        ("hive", HIVE, '"say ""hi"""', '"say ""hi"""'),
    ]
    for lang, spec, text, want in cases:
        toks = [t for t in tokenise(spec, text) if t["kind"] != "eos"]
        assert len(toks) == 1, f"{lang}: {text!r} did not stay one token: {toks}"
        assert toks[0]["kind"] == "string", f"{lang}: {text!r} -> {toks[0]}"
        assert toks[0]["text"] == want, f"{lang}: {text!r} -> {toks[0]['text']!r}"

    # the full statement form: nothing after the escaped quote gets masked
    stmt = r"SELECT 'don\'t' AS a, 'ok' AS b FROM t;"
    toks = tokenise(HIVE, stmt)
    strings = [t["text"] for t in toks if t["kind"] == "string"]
    assert strings == [r"'don\'t'", "'ok'"], f"hive: string tokens were {strings}"
    # `AS a,` and `FROM t` must be live tokens, not string content
    kinds = [(t["kind"], t["text"]) for t in toks]
    for want in [("keyword", "SELECT"), ("keyword", "AS"), ("word", "a"),
                 ("keyword", "FROM"), ("word", "t")]:
        assert want in kinds, f"hive: {want} was masked in {stmt!r}: {kinds}"


def test_every_test_in_this_file_is_registered_to_run():
    """The TESTS list must contain every test_* function defined here.

    Why this exists: seven of the twelve tests in this file were defined but
    left out of TESTS, so `python3 -m pipeline.tests.test_corpus_lossless`
    printed "ALL 5 TESTS PASSED" while the adversarial spec probes — the
    only tests that attack leaf order — never executed at all. One of them
    was failing the whole time. A green run that skips over half its own
    file is worse than a red one, so the registry now checks itself.
    """
    registered = {t.__name__ for t in TESTS}
    defined = {
        name for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    }
    missing = sorted(defined - registered)
    assert not missing, (
        f"{len(missing)} test(s) defined but never run — add them to TESTS: {missing}"
    )


def test_eos_at_eof_midword_no_trailing_newline_real_specs():
    """EOF is EOS even when the source stops mid-word with no newline.

    The engine test proves this against the mini-spec; this proves the real
    specs inherit it, including the ugly case of a source that ends inside
    an unterminated string.
    """
    cases = [("pig", PIG, "A = LOAD 'x' AS bar"), ("hive", HIVE, "SELECT foo FROM ba"),
             ("hive", HIVE, "SELECT 'abc"), ("pig", PIG, "")]
    for lang, spec, text in cases:
        assert not text.endswith("\n")
        toks = tokenise(spec, text)
        last = toks[-1]
        assert last["kind"] == "eos", f"{lang}: {text!r} last token not eos: {last}"
        assert last["text"] == "" and last["b0"] == last["b1"], f"{lang}: {last}"
        assert last["b0"] == len(text.encode("utf-8")), f"{lang}: {last}"


def test_byte_offsets_survive_multibyte_utf8_in_real_specs():
    """b0/b1 tile the source exactly when the source is not pure ASCII."""
    cases = [("hive", HIVE, "SELECT 'café' AS c FROM t;"),
             ("hive", HIVE, "SELECT '🚀' AS c;"),
             ("pig", PIG, "A = LOAD 'données/café';")]
    for lang, spec, text in cases:
        raw = text.encode("utf-8")
        assert len(raw) != len(text), f"{lang}: {text!r} is not actually multi-byte"
        cursor = 0
        for t in tokenise(spec, text):
            assert t["b0"] == cursor, f"{lang}: {t}"
            assert raw[t["b0"]:t["b1"]] == t["text"].encode("utf-8"), f"{lang}: {t}"
            cursor = t["b1"]
        assert cursor == len(raw), f"{lang}: spans end at {cursor}, source is {len(raw)} bytes"


def test_every_spec_declares_its_own_file_extension():
    """Per-language knowledge lives in the spec, never in the runner.

    run_tokenise reads the extension off the LANG dict, so teaching the
    pipeline a new language is one new file and no edits to shared code.
    """
    for lang, spec in SPECS:
        assert spec.get("ext"), f"{lang}: LANG declares no 'ext' key"
        assert spec["ext"].startswith("."), f"{lang}: ext {spec['ext']!r} should start with '.'"
        assert spec.get("name") == lang, f"{lang}: LANG['name'] is {spec.get('name')!r}"


TESTS = [
    # corpus gate
    test_cli_exits_zero_for_every_language,
    test_every_file_lossless_true,
    test_zero_unknown_kinds_everywhere,
    test_every_stream_ends_with_eos,
    test_semicolon_spot_check_emits_eos,
    # adversarial spec probes (snippets the corpus does not contain)
    test_block_comment_is_one_token_in_every_spec,
    test_comment_never_swallows_the_statement_after_it,
    test_leaf_order_does_not_let_comments_mask_strings,
    test_leaf_order_does_not_let_strings_mask_comments,
    test_escaped_quote_does_not_break_string_pairing,
    test_eos_at_eof_midword_no_trailing_newline_real_specs,
    test_byte_offsets_survive_multibyte_utf8_in_real_specs,
    test_every_spec_declares_its_own_file_extension,
    # the registry checks itself — keep this last
    test_every_test_in_this_file_is_registered_to_run,
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
