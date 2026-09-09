"""pipeline.tests.test_fold_harness — proofs for the exp_014 FOLD HARNESS
(pipeline/blocks.py, pipeline/run_fold.py, pipeline/prolog/driver.pl).

This is the harness agent's OWN proof, run against a fixture it owns —
pipeline/tests/fixtures/mini_grammar.pl (2 toy statement types conforming
to the stmt/3 + print_stmt/2 contract) and
pipeline/tests/fixtures/tokens/mini_demo.tokens.json (a hand-made token
file in the same shape as out/tokens/pig/*.tokens.json, generated once by
running pipeline.tokeniser over a small hand-written mini source string —
see pipeline/tests/fixtures/mini_demo.mini). It deliberately does NOT
touch out/grammar/pig.pl — that grammar belongs to another agent and does
not exist yet; this suite proves the harness works on ANY grammar
conforming to the contract, which is the only thing this agent owns.

Coverage, one test function per contract point:
  - statement splitting on eos, INCLUDING skipping the empty statement a
    ';' at EOF's double-eos produces
  - comment/whitespace tokens stripped from what reaches the grammar
  - atom quoting into stmts_in.pl for a string token with an embedded
    single quote (backslash-escaped in Pig-style string syntax) —
    proven both in pure Python (quote_atom/parse_quoted_list are inverse)
    and by actually round-tripping it through swipl
  - driver.pl's main/0 (fold) and unfold/0 (print) goals, including their
    failed(Seq)/printfailed(Seq) paths
  - the BlockId 7-15 line law (pipeline.blocks.assign_blocks), including
    the three cases the contract names by name: 3+3+3 lines -> one
    9-line block, a 20-line single statement -> its own block, and 6
    one-line statements -> one block ONLY IF the file ends there
  - node4.json + node4.pl emission, with trace byte ranges checked
    against the exact offsets pipeline.tokeniser produced for the fixture
  - the full retokenise -> refold fixpoint loop (run_fold.process_file),
    wired through pipeline.tokeniser + a spec module path exactly as it
    will be wired for a real grammar later — nothing here is fixture-only
    except the grammar/spec/tokens PATHS passed in

Run: python3 -m pipeline.tests.test_fold_harness
(needs `swipl` on PATH; run `eval "$(/usr/libexec/path_helper)"` first in
a fresh shell if it isn't, same as this track's other swipl-driven work)
"""
import json
import subprocess
import tempfile
from pathlib import Path

from pipeline.blocks import assign_blocks, MAX_BLOCK_LINES, MIN_BLOCK_LINES
from pipeline.tokeniser import tokenise
from pipeline.run_fold import (
    GRAMMAR_KINDS,
    load_spec,
    parse_quoted_list,
    process_file,
    quote_atom,
    read_printed_out,
    read_terms_out,
    run_swipl,
    split_statements,
    write_stmts_in,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TOKENS_PATH = FIXTURES_DIR / "tokens" / "mini_demo.tokens.json"
GRAMMAR_PATH = FIXTURES_DIR / "mini_grammar.pl"
DRIVER_PATH = REPO_ROOT / "pipeline" / "prolog" / "driver.pl"
SPEC_MODULE = "pipeline.tests.fixtures.mini_spec"


def _swipl_available():
    try:
        subprocess.run(["swipl", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _load_fixture_tokens():
    data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------
# statement splitting: eos boundaries, double-eos empty-statement skip,
# comment/whitespace stripping

def test_fixture_file_has_the_shapes_this_suite_relies_on():
    data = _load_fixture_tokens()
    assert data["lossless"] is True
    kinds = [t["kind"] for t in data["tokens"]]
    assert kinds.count("eos") == 3  # after stmt1's ';', after stmt2's ';', and EOF
    assert "comment" in kinds and "whitespace" in kinds
    # the fixture's whole point: the last two tokens are eos, eos back to
    # back — the double-eos a ';' at EOF produces, contract-locked in
    # Phase B — with nothing in between.
    assert data["tokens"][-1]["kind"] == "eos"
    assert data["tokens"][-2]["kind"] == "eos"


def test_split_statements_yields_exactly_two_seqs():
    data = _load_fixture_tokens()
    stmts = split_statements(data["tokens"])
    # 3 eos markers delimit at most 3 segments; the last one (between the
    # statement_end eos and the EOF eos) is empty and must be skipped.
    assert [s["seq"] for s in stmts] == [1, 2]


def test_split_statements_strips_comment_and_whitespace():
    data = _load_fixture_tokens()
    stmts = split_statements(data["tokens"])
    for st in stmts:
        for t in st["tokens"]:
            assert t["kind"] in GRAMMAR_KINDS, t
    # statement 1 is the LOAD assign; its first grammar token is the word
    # 'a', NOT the leading comments/blank line that sit before it in the
    # raw token stream.
    assert stmts[0]["tokens"][0]["text"] == "a"
    assert stmts[0]["tokens"][0]["kind"] == "word"


def test_split_statements_line_and_byte_spans_match_source():
    # cross-checked against the exact offsets pipeline.tokeniser produced
    # when pipeline/tests/fixtures/tokens/mini_demo.tokens.json was built
    # (see that file's header comment / the .mini source alongside it).
    data = _load_fixture_tokens()
    stmts = split_statements(data["tokens"])
    s1, s2 = stmts
    assert (s1["l0"], s1["l1"], s1["b0"], s1["b1"]) == (4, 4, 126, 151)
    assert (s2["l0"], s2["l1"], s2["b0"], s2["b1"]) == (6, 6, 153, 176)


def test_split_statements_empty_input_and_all_trivia_segment():
    # a segment holding only comment/whitespace tokens between two eos
    # markers is exactly as empty as the double-eos case, and must also
    # be skipped.
    tok = lambda kind, text, line=1, b0=0, b1=0: {
        "kind": kind, "text": text, "line": line, "b0": b0, "b1": b1, "col": 1, "i": 0,
    }
    tokens = [
        tok("comment", "-- just a comment, no statement here"),
        tok("eos", ""),
        tok("word", "x"), tok("symbol", ";"),
        tok("eos", ""),
        tok("eos", ""),  # EOF, nothing after the previous eos
    ]
    stmts = split_statements(tokens)
    assert len(stmts) == 1
    assert stmts[0]["tokens"][0]["text"] == "x"


# ---------------------------------------------------------------------
# atom quoting: the shared escaping convention (Python <-> driver.pl)

def test_quote_atom_and_parse_quoted_list_are_inverses():
    cases = [
        "plain",
        "it's a test",
        "a\\b",
        "back\\slash and 'quote' together",
        "",
        "''''",
        "\\\\\\\\",
    ]
    for original in cases:
        quoted = quote_atom(original)
        assert quoted.startswith("'") and quoted.endswith("'")
        decoded = parse_quoted_list(quoted)
        assert decoded == [original], (original, quoted, decoded)


def test_quote_atom_list_round_trips_multiple_elements():
    originals = ["a", "it's", "b\\c", "="]
    joined = ", ".join(quote_atom(o) for o in originals)
    assert parse_quoted_list(joined) == originals


def test_stmts_in_pl_quoting_survives_a_real_swipl_consult():
    if not _swipl_available():
        return  # covered elsewhere; this one specifically needs swipl
    data = _load_fixture_tokens()
    stmts = split_statements(data["tokens"])
    # statement 1's string token is the one with the embedded, backslash-
    # escaped single quote: 'it\'s a test' (raw source text, quotes and
    # backslash all literal characters in the token's own text).
    string_tok = next(t for t in stmts[0]["tokens"] if t["kind"] == "string")
    assert "\\" in string_tok["text"] and string_tok["text"].count("'") >= 2

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        stmts_in = td / "stmts_in.pl"
        write_stmts_in(stmts_in, stmts)
        # Consult it for real and read the string token's Text back out
        # UNQUOTED (write/2, not writeq/2) — if quoting round-tripped,
        # this is byte-identical to the original token text.
        probe = (
            f"consult('{stmts_in.as_posix()}'), "
            "stmt_tokens(1, Toks), "
            "member(tok(string, T), Toks), "
            "format('~w', [T]), halt."
        )
        proc = subprocess.run(["swipl", "-q", "-g", probe], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == string_tok["text"], (proc.stdout, string_tok["text"])


# ---------------------------------------------------------------------
# driver.pl: main/0 (fold) and unfold/0 (print), success and failure paths

def test_driver_main_folds_a_load_statement():
    if not _swipl_available():
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tok_list = [("word", "x"), ("symbol", "="), ("keyword", "LOAD"),
                    ("string", "'f.csv'"), ("symbol", ";")]
        toks_pl = ", ".join(f"tok({k},{quote_atom(t)})" for k, t in tok_list)
        stmts_in = td / "stmts_in.pl"
        stmts_in.write_text(f"stmt_tokens(1, [{toks_pl}]).\n", encoding="utf-8")
        terms_out = td / "terms_out.pl"
        run_swipl(DRIVER_PATH, "main", GRAMMAR_PATH, stmts_in, terms_out)
        folded, failed = read_terms_out(terms_out)
        assert failed == set()
        assert folded == {1: "assign(rel(x),load(lit('f.csv')))"}


def test_driver_main_reports_failed_for_an_unparseable_statement():
    if not _swipl_available():
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        stmts_in = td / "stmts_in.pl"
        # neither toy statement type: a lone word token, no '=' etc.
        stmts_in.write_text(
            f"stmt_tokens(1, [tok(word,{quote_atom('nonsense')})]).\n", encoding="utf-8",
        )
        terms_out = td / "terms_out.pl"
        run_swipl(DRIVER_PATH, "main", GRAMMAR_PATH, stmts_in, terms_out)
        folded, failed = read_terms_out(terms_out)
        assert folded == {}
        assert failed == {1}


def test_driver_unfold_prints_canonical_texts():
    if not _swipl_available():
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        terms_in = td / "terms_in.pl"
        terms_in.write_text(
            "folded(1, assign(rel(x),load(lit('f.csv')))).\n", encoding="utf-8",
        )
        printed_out = td / "printed_out.pl"
        run_swipl(DRIVER_PATH, "unfold", GRAMMAR_PATH, terms_in, printed_out)
        printed, printfailed = read_printed_out(printed_out)
        assert printfailed == set()
        assert printed == {1: ["x", "=", "load", "'f.csv'", ";"]}


def test_driver_unfold_reports_printfailed_for_an_unknown_term_shape():
    if not _swipl_available():
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        terms_in = td / "terms_in.pl"
        terms_in.write_text("folded(1, some_other_shape(1,2)).\n", encoding="utf-8")
        printed_out = td / "printed_out.pl"
        run_swipl(DRIVER_PATH, "unfold", GRAMMAR_PATH, terms_in, printed_out)
        printed, printfailed = read_printed_out(printed_out)
        assert printed == {}
        assert printfailed == {1}


# ---------------------------------------------------------------------
# BlockId law: pipeline.blocks.assign_blocks (7-15 line law)

def _st(seq, l0, l1):
    return {"seq": seq, "l0": l0, "l1": l1}


def test_blocks_three_three_three_lines_merge_into_one_nine_line_block():
    stmts = [_st(1, 1, 3), _st(2, 4, 6), _st(3, 7, 9)]
    assert assign_blocks(stmts) == [("b_001", [1, 2, 3])]


def test_blocks_a_twenty_line_single_statement_is_its_own_block():
    stmts = [_st(1, 1, 20)]
    assert assign_blocks(stmts) == [("b_001", [1])]
    # and it stays its own block even with a follow-on statement: the
    # oversized statement alone already closes (span 20 >= 7), so the
    # next statement starts a fresh block regardless of its own size.
    stmts2 = [_st(1, 1, 20), _st(2, 21, 21)]
    assert assign_blocks(stmts2) == [("b_001", [1]), ("b_002", [2])]


def test_blocks_six_one_liners_merge_only_because_the_file_ends():
    stmts = [_st(i, i, i) for i in range(1, 7)]  # lines 1..6, span 1 each
    assert assign_blocks(stmts) == [("b_001", [1, 2, 3, 4, 5, 6])]


def test_blocks_six_one_liners_keep_absorbing_when_the_file_does_not_end():
    # same 6 one-line statements, but a 7th follows: the running span only
    # reaches 7 once the 7th is added, so ALL SEVEN land in one block —
    # proving "one block only if file ends" is doing real work above,
    # not just an artifact of stopping at 6.
    stmts = [_st(i, i, i) for i in range(1, 8)]  # lines 1..7
    assert assign_blocks(stmts) == [("b_001", [1, 2, 3, 4, 5, 6, 7])]


def test_blocks_max_cap_forces_an_early_close_before_absorbing_an_oversized_neighbor():
    stmts = [_st(1, 1, 2), _st(2, 3, 22)]  # merged span would be 22 > 15
    assert assign_blocks(stmts) == [("b_001", [1]), ("b_002", [2])]


def test_blocks_close_exactly_at_seven_not_before():
    # span 6 after two statements (lines 1-6): must NOT close yet.
    stmts = [_st(1, 1, 3), _st(2, 4, 6)]
    assert assign_blocks(stmts) == [("b_001", [1, 2])]  # forced closed: file ends
    # add a 3rd 1-liner: span becomes 7, closes right there.
    stmts2 = stmts + [_st(3, 7, 7)]
    assert assign_blocks(stmts2) == [("b_001", [1, 2, 3])]


def test_blocks_cover_every_seq_exactly_once_in_order():
    stmts = [_st(i, i * 2, i * 2) for i in range(1, 11)]  # 10 one-liners, gaps between
    blocks = assign_blocks(stmts)
    seen = [seq for _, seqs in blocks for seq in seqs]
    assert seen == list(range(1, 11))
    # block ids are sequential, zero-padded, 1-indexed
    assert [b for b, _ in blocks] == [f"b_{i:03d}" for i in range(1, len(blocks) + 1)]


# ---------------------------------------------------------------------
# full harness: process_file — fold, round-trip, node4 emission

def _run_fixture():
    spec = load_spec(SPEC_MODULE)
    with tempfile.TemporaryDirectory() as work_td, tempfile.TemporaryDirectory() as out_td:
        return process_file(
            lang="mini", spec=spec, grammar_path=GRAMMAR_PATH, driver_path=DRIVER_PATH,
            tokens_path=TOKENS_PATH, out_dir=Path(out_td), work_dir=Path(work_td),
        )


def test_process_file_folds_and_round_trips_every_statement():
    if not _swipl_available():
        return
    result = _run_fixture()
    assert result["errors"] == [], result["errors"]
    assert result["n"] == 2
    assert result["folded_n"] == 2
    assert result["roundtrip_n"] == 2
    assert result["ok"] is True


def test_process_file_node4_shape_and_traces():
    if not _swipl_available():
        return
    result = _run_fixture()
    node4 = result["node4"]
    assert len(node4) == 2
    assert {rec["seq"] for rec in node4} == {1, 2}
    for rec in node4:
        assert set(rec.keys()) == {"block", "seq", "term", "trace", "comments"}
        assert set(rec["trace"].keys()) == {"file", "l0", "l1", "b0", "b1"}
        assert rec["trace"]["file"] == "pipeline/tests/fixtures/mini_demo.mini"

    by_seq = {rec["seq"]: rec for rec in node4}
    assert by_seq[1]["trace"] == {
        "file": "pipeline/tests/fixtures/mini_demo.mini", "l0": 4, "l1": 4, "b0": 126, "b1": 151,
    }
    assert by_seq[2]["trace"] == {
        "file": "pipeline/tests/fixtures/mini_demo.mini", "l0": 6, "l1": 6, "b0": 153, "b1": 176,
    }
    # both statements sit close together (2 source lines apart) — well
    # under the 7-line threshold — so the 7-15 line law puts them in the
    # SAME block (this is a real block.py call, not hand-picked).
    assert by_seq[1]["block"] == by_seq[2]["block"] == "b_001"
    assert result["blocks"] == [("b_001", [1, 2])]

    assert by_seq[1]["term"] == "assign(rel(a),load(lit('it\\\\\\'s a test')))"
    assert by_seq[2]["term"] == "assign(rel(b),filter(rel(a),gt(col(v),lit(15))))"


def test_process_file_writes_json_and_valid_pl_facts_to_disk():
    if not _swipl_available():
        return
    spec = load_spec(SPEC_MODULE)
    with tempfile.TemporaryDirectory() as work_td, tempfile.TemporaryDirectory() as out_td:
        result = process_file(
            lang="mini", spec=spec, grammar_path=GRAMMAR_PATH, driver_path=DRIVER_PATH,
            tokens_path=TOKENS_PATH, out_dir=Path(out_td), work_dir=Path(work_td),
        )
        json_path, pl_path = result["json_path"], result["pl_path"]
        assert json_path.is_file() and pl_path.is_file()

        on_disk = json.loads(json_path.read_text(encoding="utf-8"))
        assert on_disk == result["node4"]

        # the .pl facts must be valid Prolog AND, once consulted, writeq
        # back out to the EXACT same term text captured in node4.json —
        # proving the spliced-in term text round-trips through a real
        # Prolog reader, not just through Python string handling.
        probe = (
            f"consult('{pl_path.as_posix()}'), "
            "forall(node(B,S,T,trace(F,L0,L1,B0,B1)), "
            "(writeq(S), write(' | '), writeq(B), write(' | '), writeq(T), "
            "write(' | '), writeq(trace(F,L0,L1,B0,B1)), nl)), halt."
        )
        proc = subprocess.run(["swipl", "-q", "-g", probe], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        assert len(lines) == 2
        for rec, line in zip(result["node4"], lines):
            seq_txt, block_txt, term_txt, trace_txt = [p.strip() for p in line.split(" | ")]
            assert seq_txt == str(rec["seq"])
            assert block_txt == rec["block"]
            assert term_txt == rec["term"]
            expected_trace = "trace({},{},{},{},{})".format(
                quote_atom(rec["trace"]["file"]),
                rec["trace"]["l0"], rec["trace"]["l1"], rec["trace"]["b0"], rec["trace"]["b1"],
            )
            assert trace_txt == expected_trace


# ---------------------------------------------------------------------
# BlockId law + trace law, END TO END on sources this test constructs.
#
# Why these exist on top of the assign_blocks unit tests above: those call
# assign_blocks directly with hand-made {seq,l0,l1} dicts. These drive the
# WHOLE harness — tokenise, split, fold, print, retokenise, refold, emit
# node4 — over a real source file, so they also prove run_fold hands
# assign_blocks the line spans the law expects. The corpus happens to
# contain neither edge case (no statement is over 15 lines, no file is
# under 7), so without these two the edges are only ever exercised on
# synthetic dicts.

def _process_source(text, source_name="synthetic.mini"):
    """Tokenise `text` with the mini spec, write it out in the exact shape
    run_tokenise writes out/tokens/<lang>/*.tokens.json, and run the real
    process_file over it. Returns process_file's result with the source
    bytes attached, so trace byte ranges can be checked against them."""
    spec = load_spec(SPEC_MODULE)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src_path = td / source_name
        src_path.write_text(text, encoding="utf-8")
        tokens = tokenise(spec, text)
        tokens_path = td / "synthetic.tokens.json"
        tokens_path.write_text(json.dumps({
            "file": str(src_path), "lossless": True,
            "n_tokens": len(tokens), "tokens": tokens,
        }), encoding="utf-8")
        work_dir, out_dir = td / "work", td / "out"
        work_dir.mkdir()
        result = process_file(
            lang="mini", spec=spec, grammar_path=GRAMMAR_PATH, driver_path=DRIVER_PATH,
            tokens_path=tokens_path, out_dir=out_dir, work_dir=work_dir,
        )
        result["source_bytes"] = text.encode("utf-8")
        return result


def test_blocks_end_to_end_single_statement_longer_than_fifteen_lines_stays_whole():
    """BlockId edge case 1: ONE statement that alone spans more than 15
    source lines. The cap may not split it — it becomes its own block."""
    if not _swipl_available():
        return
    # one token per line, blank line between: 9 tokens -> lines 1,3,..,17.
    text = "\n\n".join(["b", "=", "FILTER", "a", "BY", "v", ">", "15", ";"]) + "\n"
    result = _process_source(text)

    assert result["errors"] == [], result["errors"]
    assert result["n"] == 1 and result["folded_n"] == 1 and result["roundtrip_n"] == 1

    rec = result["node4"][0]
    span = rec["trace"]["l1"] - rec["trace"]["l0"] + 1
    assert (rec["trace"]["l0"], rec["trace"]["l1"]) == (1, 17), rec["trace"]
    assert span > MAX_BLOCK_LINES, (
        f"this case is only meaningful if the statement really exceeds the "
        f"{MAX_BLOCK_LINES}-line cap; it spans {span}"
    )
    assert result["blocks"] == [("b_001", [1])]
    assert rec["block"] == "b_001"
    assert rec["term"] == "assign(rel(b),filter(rel(a),gt(col(v),lit(15))))"


def test_blocks_end_to_end_file_shorter_than_seven_lines_is_one_short_block():
    """BlockId edge case 2: a whole file shorter than the 7-line minimum.
    The block never reaches MIN_BLOCK_LINES, so it closes only because the
    statements run out — and every seq still lands in exactly one block."""
    if not _swipl_available():
        return
    text = "a = LOAD 'f.csv';\nb = FILTER a BY v > 15;\n"
    assert len(text.splitlines()) < MIN_BLOCK_LINES  # the premise of this case
    result = _process_source(text)

    assert result["errors"] == [], result["errors"]
    assert result["n"] == 2 and result["folded_n"] == 2 and result["roundtrip_n"] == 2
    assert result["blocks"] == [("b_001", [1, 2])]

    l0 = min(r["trace"]["l0"] for r in result["node4"])
    l1 = max(r["trace"]["l1"] for r in result["node4"])
    assert (l1 - l0 + 1) < MIN_BLOCK_LINES
    assert [r["block"] for r in result["node4"]] == ["b_001", "b_001"]


def test_trace_byte_range_excludes_a_comment_sitting_directly_above_a_statement():
    """Trace law: b0 is the first GRAMMAR token's offset, so a comment (and
    the whitespace after it) immediately above a statement must fall
    outside that statement's byte range. Every corpus file only comments at
    its head, so this case is synthetic on purpose."""
    if not _swipl_available():
        return
    text = (
        "-- file header comment\n"
        "a = LOAD 'f.csv';\n"
        "\n"
        "   -- a comment sitting directly above the second statement\n"
        "b = FILTER a BY v > 15;\n"
    )
    result = _process_source(text)
    assert result["errors"] == [], result["errors"]
    assert result["n"] == 2

    src = result["source_bytes"]
    by_seq = {r["seq"]: r for r in result["node4"]}
    slices = {seq: src[r["trace"]["b0"]:r["trace"]["b1"]].decode("utf-8")
              for seq, r in by_seq.items()}
    assert slices[1] == "a = LOAD 'f.csv';"
    assert slices[2] == "b = FILTER a BY v > 15;"
    for seq, sliced in slices.items():
        assert "--" not in sliced, f"seq {seq} trace swallowed a comment: {sliced!r}"
        assert not sliced[:1].isspace() and not sliced[-1:].isspace(), (
            f"seq {seq} trace has leading/trailing trivia: {sliced!r}"
        )
    # and the second statement's b0 really is PAST the comment above it
    assert by_seq[2]["trace"]["b0"] > text.index("-- a comment sitting")
    assert by_seq[2]["trace"]["l0"] == 5


TESTS = [
    test_fixture_file_has_the_shapes_this_suite_relies_on,
    test_split_statements_yields_exactly_two_seqs,
    test_split_statements_strips_comment_and_whitespace,
    test_split_statements_line_and_byte_spans_match_source,
    test_split_statements_empty_input_and_all_trivia_segment,
    test_quote_atom_and_parse_quoted_list_are_inverses,
    test_quote_atom_list_round_trips_multiple_elements,
    test_stmts_in_pl_quoting_survives_a_real_swipl_consult,
    test_driver_main_folds_a_load_statement,
    test_driver_main_reports_failed_for_an_unparseable_statement,
    test_driver_unfold_prints_canonical_texts,
    test_driver_unfold_reports_printfailed_for_an_unknown_term_shape,
    test_blocks_three_three_three_lines_merge_into_one_nine_line_block,
    test_blocks_a_twenty_line_single_statement_is_its_own_block,
    test_blocks_six_one_liners_merge_only_because_the_file_ends,
    test_blocks_six_one_liners_keep_absorbing_when_the_file_does_not_end,
    test_blocks_max_cap_forces_an_early_close_before_absorbing_an_oversized_neighbor,
    test_blocks_close_exactly_at_seven_not_before,
    test_blocks_cover_every_seq_exactly_once_in_order,
    test_process_file_folds_and_round_trips_every_statement,
    test_process_file_node4_shape_and_traces,
    test_process_file_writes_json_and_valid_pl_facts_to_disk,
    test_blocks_end_to_end_single_statement_longer_than_fifteen_lines_stays_whole,
    test_blocks_end_to_end_file_shorter_than_seven_lines_is_one_short_block,
    test_trace_byte_range_excludes_a_comment_sitting_directly_above_a_statement,
]


def main():
    # Most of this suite cannot prove anything without swipl: those tests
    # return early, which would otherwise be reported as PASS and print a
    # green "ALL TESTS PASSED" for a run that proved almost nothing. Refuse
    # to run at all instead — the same hard stop test_pig_grammar.py and
    # test_hive_grammar.py already use.
    if not _swipl_available():
        print("swipl not on PATH — this suite cannot prove its contract without it.\n"
              "Run: eval \"$(/usr/libexec/path_helper)\" first")
        return 1

    failures = []
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            failures.append((t.__name__, str(e)))
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            failures.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
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
