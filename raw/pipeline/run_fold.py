"""pipeline.run_fold — the exp_014 FOLD HARNESS runner (language-agnostic).

Why this file exists: turns a language's out/tokens/<lang>/*.tokens.json
into out/ir/<lang>/*.node4.json + *.node4.pl by driving a generated
out/grammar/<lang>.pl through pipeline/prolog/driver.pl. This file holds
NO language knowledge of its own — the pyDSL-only law — everything that
differs between languages (the grammar, the tokeniser spec) is a path or
a dotted module name passed in on the command line, never a fact baked in
here. Statement shapes belong in pipeline/specs/<lang>.py; this file only
knows the shared shapes: tok(Kind,Text), stmt_tokens/2, folded/2,
printed/2, and out/ir's node4 record.

THE PHASE-C API CONTRACT this file implements (see the driver.pl header
for the Prolog half of it):

  1. Statements are already delimited by the tokeniser: tokens between
     zero-width "eos" markers form one statement. comment/whitespace
     tokens are stripped before folding (they stay in the source
     .tokens.json for trace replay, untouched). A statement segment with
     zero grammar tokens after that stripping — including the "double
     eos" a ';' at EOF produces — is an EMPTY statement and gets no seq,
     no stmts_in.pl fact, nothing: it is simply not there.

  2. stmts_in.pl / terms_out.pl / printed_out.pl are all plain Prolog
     fact files, written and read as TEXT by this module (never parsed
     as general Prolog) — see quote_atom()/parse_quoted_list() below for
     the one shared escaping convention (backslash doubled, then quote
     doubled) both this file and driver.pl commit to, in both
     directions, so the two ends always agree without either one needing
     a full Prolog reader.

  3. The round-trip check treats a folded Term as an OPAQUE string: the
     writeq text of a term is deterministic for a given term structure,
     so "Term2 == Term" is checked as plain string equality between two
     writeq outputs, never by parsing Prolog terms in Python.

  4. BlockIds come from pipeline.blocks.assign_blocks — the 7-15 line law
     lives there once, not reimplemented here.

CLI:
    python3 -m pipeline.run_fold <lang>
        [--tokens-dir out/tokens/<lang>]   (default derived from <lang>)
        [--grammar out/grammar/<lang>.pl]  (default derived from <lang>)
        [--out-dir out/ir/<lang>]          (default derived from <lang>)
        [--spec pipeline.specs.<lang>]     (default derived from <lang>;
                                             dotted module path exporting
                                             LANG, used only to retokenise
                                             print_stmt's output for the
                                             round-trip check)
        [--driver pipeline/prolog/driver.pl]  (default: this repo's copy)
        [--work-dir DIR]                   (default: a fresh tempdir;
                                             intermediate .pl files land
                                             here — pass one to inspect
                                             them after a run)
        [--file STEM]                      (process only <STEM>.tokens.json
                                             instead of every file in
                                             --tokens-dir)

Prints a per-file "folded n/n, roundtrip n/n" line and exits 0 only if
every processed file folded and round-tripped ALL its statements.
"""
import argparse
import importlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.tokeniser import tokenise
from pipeline.blocks import assign_blocks, assign_blocks_by_steps
from pipeline.term_parse import parse_term, TermParseError
from pipeline.comments import extract_comments, attach_comments

GRAMMAR_KINDS = ("keyword", "word", "number", "string", "symbol", "path", "datalines")  # exp_42: + datalines

_FOLDED_RE = re.compile(r"^folded\((\d+), (.*)\)\.\s*$", re.DOTALL)
_FAILED_RE = re.compile(r"^failed\((\d+)\)\.\s*$")
_PRINTED_RE = re.compile(r"^printed\((\d+), \[(.*)\]\)\.\s*$", re.DOTALL)
_PRINTFAILED_RE = re.compile(r"^printfailed\((\d+)\)\.\s*$")


# --------------------------------------------------------------------
# The one shared atom-escaping convention (mirrors driver.pl's
# escape_pl_atom/2 exactly: backslash doubled first, then quote doubled).

def quote_atom(s):
    """Turn a Python string into a Prolog single-quoted atom literal that
    reads back as exactly `s`, byte for byte. Order matters: backslash
    first (so the quote-doubling step below never touches a backslash
    THIS step just introduced), then quote."""
    escaped = s.replace("\\", "\\\\").replace("'", "''")
    return "'" + escaped + "'"


def parse_quoted_list(list_text):
    """Inverse of driver.pl's write_quoted_list/write_quoted_atom: every
    element is ALWAYS single-quoted with backslash-then-quote doubling
    (never writeq's own "quote only if needed" heuristic), so this is a
    small hand-scanner, not a general Prolog term reader."""
    s = list_text
    i, n = 0, len(s)
    out = []
    while i < n:
        while i < n and s[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if s[i] != "'":
            raise ValueError(f"parse_quoted_list: expected opening quote at {i} in {list_text!r}")
        i += 1
        buf = []
        closed = False
        while i < n:
            c = s[i]
            if c == "\\":
                if i + 1 >= n:
                    raise ValueError(f"parse_quoted_list: trailing backslash in {list_text!r}")
                buf.append(s[i + 1])
                i += 2
                continue
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                i += 1
                closed = True
                break
            buf.append(c)
            i += 1
        if not closed:
            raise ValueError(f"parse_quoted_list: unterminated quoted atom in {list_text!r}")
        out.append("".join(buf))
    return out


# --------------------------------------------------------------------
# statement splitting (tokeniser output -> one entry per real statement)

def split_statements(tokens, grammar_kinds=GRAMMAR_KINDS):
    """Group `tokens` (one file's full token list, comments/whitespace/eos
    included) into statements: everything strictly between consecutive
    zero-width eos markers is one segment; a segment is kept only if it
    has at least one grammar-kind token after comment/whitespace are
    stripped (an all-comment/all-whitespace segment, or the truly-empty
    segment a ';' immediately followed by EOF produces via the double
    eos, is skipped — no seq assigned).

    Returns a list of dicts, seq 1..n over the KEPT statements only:
        {"seq": N, "tokens": [grammar tokens...], "l0", "l1", "b0", "b1"}
    """
    stmts = []
    seq = 0
    segment = []
    for t in tokens:
        if t["kind"] == "eos":
            grammar_toks = [x for x in segment if x["kind"] in grammar_kinds]
            if grammar_toks:
                seq += 1
                stmts.append({
                    "seq": seq,
                    "tokens": grammar_toks,
                    "l0": grammar_toks[0]["line"],
                    "l1": grammar_toks[-1]["line"],
                    "b0": grammar_toks[0]["b0"],
                    "b1": grammar_toks[-1]["b1"],
                })
            segment = []
        else:
            segment.append(t)
    return stmts


# --------------------------------------------------------------------
# .pl fact-file writers / readers

def write_stmts_in(path, stmts, key="tokens"):
    lines = ["% auto-generated by pipeline.run_fold — DO NOT EDIT BY HAND\n"]
    for st in stmts:
        toks_pl = ", ".join(
            f"tok({t['kind']},{quote_atom(t['text'])})" for t in st[key]
        )
        lines.append(f"stmt_tokens({st['seq']}, [{toks_pl}]).\n")
    path.write_text("".join(lines), encoding="utf-8")


def read_terms_out(path):
    """Returns (folded: {seq: term_text}, failed: set(seq))."""
    folded, failed = {}, set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = _FOLDED_RE.match(line)
        if m:
            folded[int(m.group(1))] = m.group(2)
            continue
        m = _FAILED_RE.match(line)
        if m:
            failed.add(int(m.group(1)))
            continue
        raise ValueError(f"read_terms_out: unrecognised line {line!r} in {path}")
    return folded, failed


def _records(text):
    """exp_42 (2026-09-05): a printed/2 record may span several physical
    lines when a token text itself holds newlines (SAS datalines). Lines are
    joined until the single quotes in the buffer balance and the buffer ends
    in `).` — the quoted-list format doubles quotes, so parity is exact."""
    buf = None
    for line in text.splitlines():
        buf = line if buf is None else buf + "\n" + line
        if not buf.strip():
            buf = None
            continue
        if buf.rstrip().endswith(").") and buf.count("'") % 2 == 0:
            yield buf
            buf = None
    if buf is not None and buf.strip():
        yield buf


def read_printed_out(path):
    """Returns (printed: {seq: [texts...]}, printfailed: set(seq))."""
    printed, printfailed = {}, set()
    for line in _records(path.read_text(encoding="utf-8")):
        if not line.strip():
            continue
        m = _PRINTED_RE.match(line)
        if m:
            printed[int(m.group(1))] = parse_quoted_list(m.group(2))
            continue
        m = _PRINTFAILED_RE.match(line)
        if m:
            printfailed.add(int(m.group(1)))
            continue
        raise ValueError(f"read_printed_out: unrecognised line {line!r} in {path}")
    return printed, printfailed


# --------------------------------------------------------------------
# exp_42: source rebuild

def _raw_body(text):
    i = text.find(";")
    return (text[i + 1:] if i >= 0 else text).strip()


def rebuild_source(tokens, stmts, folded, printed, grammar_kinds=GRAMMAR_KINDS):
    """Walk the full token list; every grammar token is replaced by the next
    printed text of its statement. A printed text that equals the original
    ignoring keyword case (or, for a raw datalines block, whose body equals
    the original body) keeps the ORIGINAL spelling — the print is then proven
    equal and the source is reproduced exactly. Returns (text, mismatches)."""
    queues = {st["seq"]: list(printed.get(st["seq"]) or []) for st in stmts}
    out, mism = [], []
    seq_iter = iter([st["seq"] for st in stmts])
    seq, seg_has_grammar = None, False
    for t in tokens:
        if t["kind"] == "eos":
            seq, seg_has_grammar = None, False
            continue
        if t["kind"] not in grammar_kinds:
            out.append(t["text"])
            continue
        if not seg_has_grammar:
            seg_has_grammar = True
            seq = next(seq_iter, None)
        q = queues.get(seq)
        if seq is None or seq not in folded or not q:
            out.append(t["text"])       # statement did not fold/print: keep the source
            continue
        p = q.pop(0)
        if p == t["text"] or p.casefold() == t["text"].casefold():
            out.append(t["text"])
        elif t["kind"] == "datalines" and _raw_body(p) == _raw_body(t["text"]):
            out.append(t["text"])
        else:
            out.append(p)
            mism.append({"seq": seq, "source": t["text"], "printed": p})
    return "".join(out), mism


# --------------------------------------------------------------------
# driving swipl

def run_swipl(driver_path, goal, grammar_path, in_path, out_path):
    cmd = [
        "swipl", "-q", "-s", str(driver_path), "-g", goal, "--",
        str(grammar_path), str(in_path), str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(
            f"swipl -g {goal} failed (exit {proc.returncode})\n"
            f"cmd: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


# --------------------------------------------------------------------
# spec loading (dotted module path -> LANG dict; no language table here)

def load_spec(module_path):
    mod = importlib.import_module(module_path)
    return mod.LANG


# --------------------------------------------------------------------
# one file, end to end

def process_file(*, lang, spec, grammar_path, driver_path, tokens_path,
                  out_dir, work_dir, source_file_override=None):
    data = json.loads(tokens_path.read_text(encoding="utf-8"))
    source_file = source_file_override or data["file"]
    tokens = data["tokens"]

    stmts = split_statements(tokens)
    n = len(stmts)
    stem = tokens_path.stem
    if stem.endswith(".tokens"):
        stem = stem[: -len(".tokens")]

    result = {
        "stem": stem, "n": n, "folded_n": 0, "roundtrip_n": 0,
        "errors": [], "source_match": None,
    }
    if n == 0:
        result["ok"] = True
        return result

    # ---- pass 1: fold the real statements ----
    stmts_in = work_dir / f"{stem}.stmts_in.pl"
    terms_out = work_dir / f"{stem}.terms_out.pl"
    write_stmts_in(stmts_in, stmts)
    run_swipl(driver_path, "main", grammar_path, stmts_in, terms_out)
    folded, failed = read_terms_out(terms_out)
    result["folded_n"] = len(folded)
    for st in stmts:
        if st["seq"] in failed:
            result["errors"].append(f"seq {st['seq']}: fold failed")

    # TERM-READABILITY LAW (2026-08-26): a term driver.pl reports as folded
    # must be readable by pipeline.term_parse — the same reader every
    # downstream codegen module uses to turn this term text back into a
    # Term. driver.pl writes with plain writeq/2 (backslash escaping);
    # term_parse only decodes '' doubling. The two can disagree on a term
    # containing an escaped quote, and the disagreement is invisible here —
    # it would otherwise surface many stages later, deep inside codegen, as
    # a bare TermParseError with a raw character offset and no file, block,
    # or seq to point at. Catching it at fold time, with that context, is
    # the whole point: this is not optional defensive coding, it closes a
    # real gap the round-trip check cannot see (see
    # code_graph/gold/pig/coverage.md-adjacent proposal, 2026-08-26 — a
    # string escape survives fold+round-trip as text while the decoded
    # VALUE is already wrong; term-readability is the next-cheapest place
    # to catch a term the pipeline's own reader cannot parse at all).
    # Explicit raise, not a bare assert — same reasoning as the lossless/
    # byte-offset laws in pipeline/tokeniser.py: a bare assert compiles out
    # under python -O, which would silently turn this into a no-op while
    # this function still reports folded_n as if every term were readable.
    for seq, term_text in folded.items():
        try:
            parse_term(term_text)
        except TermParseError as e:
            raise AssertionError(
                f"TERM-READABILITY LAW violated: {source_file} seq {seq}: "
                f"driver.pl wrote a term pipeline.term_parse cannot read "
                f"back ({e}). Term text: {term_text!r}"
            )

    # ---- pass 2: unfold (print) every term that DID fold ----
    printed_out = work_dir / f"{stem}.printed_out.pl"
    run_swipl(driver_path, "unfold", grammar_path, terms_out, printed_out)
    printed, printfailed = read_printed_out(printed_out)

    # ---- pass 3: retokenise the printed texts, refold, compare text ----
    retokenised_stmts = []
    for st in stmts:
        seq = st["seq"]
        if seq not in folded:
            continue  # already recorded as a fold failure above
        texts = printed.get(seq)
        if texts is None:
            result["errors"].append(f"seq {seq}: print_stmt failed (round-trip)")
            continue
        snippet = " ".join(texts)
        try:
            retoks = tokenise(spec, snippet)
        except AssertionError as e:
            result["errors"].append(f"seq {seq}: retokenise raised: {e}")
            continue
        grammar_retoks = [t for t in retoks if t["kind"] in GRAMMAR_KINDS]
        if not grammar_retoks:
            result["errors"].append(f"seq {seq}: retokenise produced no grammar tokens")
            continue
        retokenised_stmts.append({"seq": seq, "retoks": grammar_retoks})

    roundtrip_n = 0
    if retokenised_stmts:
        stmts_in2 = work_dir / f"{stem}.stmts_in2.pl"
        terms_out2 = work_dir / f"{stem}.terms_out2.pl"
        write_stmts_in(stmts_in2, retokenised_stmts, key="retoks")
        run_swipl(driver_path, "main", grammar_path, stmts_in2, terms_out2)
        folded2, failed2 = read_terms_out(terms_out2)
        for st in retokenised_stmts:
            seq = st["seq"]
            term1 = folded[seq]
            term2 = folded2.get(seq)
            if term2 is None:
                result["errors"].append(f"seq {seq}: refold after print failed (round-trip)")
            elif term2 != term1:
                result["errors"].append(
                    f"seq {seq}: round-trip term mismatch: {term1!r} != {term2!r}"
                )
            else:
                roundtrip_n += 1
    result["roundtrip_n"] = roundtrip_n

    # ---- exp_42 (2026-09-05) SOURCE-REBUILD LAW (exp_011's R3 oracle) ----
    # The printed tokens of every statement are put back into the ORIGINAL
    # token stream (whitespace, comments, keyword casing kept), and the
    # result must equal the source byte for byte. This is stricter than the
    # term round trip above: it proves nothing was lost, not just that the
    # term is stable. Written to out/roundtrip/<stem>.rebuilt.sas.
    rebuilt, rebuild_mismatches = rebuild_source(tokens, stmts, folded, printed)
    result["source_match"] = (rebuilt == data.get("text", "".join(t["text"] for t in tokens)))
    result["rebuild_mismatches"] = rebuild_mismatches
    rt_dir = out_dir.parent.parent / "roundtrip"
    rt_dir.mkdir(parents=True, exist_ok=True)
    (rt_dir / f"{stem}.rebuilt.sas").write_text(rebuilt, encoding="utf-8")
    if not result["source_match"]:
        result["errors"].append(f"rebuilt source differs from the original ({len(rebuild_mismatches)} token(s): {rebuild_mismatches[:3]})")

    # ---- node4 emission ----
    # exp_42 (2026-09-05): a spec may declare step boundaries (SAS: a block
    # is one DATA step / one PROC step / one global statement). When it
    # does, blocks follow the language's own steps, not the 7-15 line law.
    if spec.get("blocks"):
        blocks = assign_blocks_by_steps(stmts, folded, spec["blocks"])
    else:
        blocks = assign_blocks(stmts)
    block_of_seq = {}
    for block_id, seqs in blocks:
        for seq in seqs:
            block_of_seq[seq] = block_id

    # COMMENT REATTACHMENT (2026-08-26, pipeline.comments): source comments
    # are tokenised but stripped by split_statements before folding — this
    # is the one place that reads them back, from the file's FULL token
    # list (untouched by the grammar-kinds filtering above), and maps each
    # one to the statement it belongs closest to. attach_comments needs the
    # FULL `stmts` list (every seq's l0/l1), not just the ones that folded,
    # to place a comment correctly relative to its real neighbours; a
    # comment attached to a seq that never made it into node4 (failed to
    # fold) is simply not emitted below — there is no generated line left
    # for it to attach to. node/4 itself stays arity 4, unchanged: comments
    # ride in node4.json's own "comments" key and node4.pl's sibling
    # node_comment/5 facts, never inside the Term.
    comments = extract_comments(tokens)
    attached_comments = attach_comments(comments, stmts)

    node4 = []
    for st in stmts:
        seq = st["seq"]
        term_text = folded.get(seq)
        if term_text is None:
            continue  # no Term to attach; not emitted as a node
        node4.append({
            "block": block_of_seq[seq],
            "seq": seq,
            "term": term_text,
            "trace": {
                "file": source_file,
                "l0": st["l0"], "l1": st["l1"],
                "b0": st["b0"], "b1": st["b1"],
            },
            "comments": attached_comments.get(seq, []),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.node4.json"
    json_path.write_text(json.dumps(node4, indent=2), encoding="utf-8")

    pl_path = out_dir / f"{stem}.node4.pl"
    pl_lines = []
    for rec in node4:
        pl_lines.append(
            "node({}, {}, {}, trace({},{},{},{},{})).\n".format(
                quote_atom(rec["block"]), rec["seq"], rec["term"],
                quote_atom(rec["trace"]["file"]),
                rec["trace"]["l0"], rec["trace"]["l1"],
                rec["trace"]["b0"], rec["trace"]["b1"],
            )
        )
        for c in rec["comments"]:
            pl_lines.append(
                "node_comment({}, {}, {}, {}, {}).\n".format(
                    quote_atom(rec["block"]), rec["seq"],
                    quote_atom(c["pos"]), c["line"], quote_atom(c["text"]),
                )
            )
    pl_path.write_text("".join(pl_lines), encoding="utf-8")

    result["ok"] = (result["folded_n"] == n and result["roundtrip_n"] == n and result.get("source_match", True))
    result["json_path"] = json_path
    result["pl_path"] = pl_path
    result["node4"] = node4
    result["blocks"] = blocks
    return result


# --------------------------------------------------------------------
# CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run_fold")
    ap.add_argument("lang")
    ap.add_argument("--tokens-dir", default=None)
    ap.add_argument("--grammar", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--spec", default=None)
    ap.add_argument("--driver", default=None)
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--file", default=None, help="process only this stem's *.tokens.json")
    args = ap.parse_args(argv)

    lang = args.lang
    tokens_dir = Path(args.tokens_dir) if args.tokens_dir else Path("out/tokens") / lang
    grammar_path = Path(args.grammar) if args.grammar else Path("out/grammar") / f"{lang}.pl"
    out_dir = Path(args.out_dir) if args.out_dir else Path("out/ir") / lang
    spec_module = args.spec or f"pipeline.specs.{lang}"
    driver_path = Path(args.driver) if args.driver else (Path(__file__).resolve().parent / "prolog" / "driver.pl")

    if not tokens_dir.is_dir():
        print(f"ERROR: tokens dir not found: {tokens_dir}", file=sys.stderr)
        return 1
    if not grammar_path.is_file():
        print(f"ERROR: grammar file not found: {grammar_path}", file=sys.stderr)
        return 1
    if not driver_path.is_file():
        print(f"ERROR: driver.pl not found: {driver_path}", file=sys.stderr)
        return 1

    try:
        spec = load_spec(spec_module)
    except Exception as e:
        print(f"ERROR: could not load spec module {spec_module}: {e}", file=sys.stderr)
        return 1

    files = sorted(tokens_dir.glob("*.tokens.json"))
    if args.file:
        files = [f for f in files if f.stem == f"{args.file}.tokens" or f.stem == args.file]
    if not files:
        print(f"ERROR: no *.tokens.json files found in {tokens_dir}", file=sys.stderr)
        return 1

    work_dir = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix=f"run_fold_{lang}_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    all_ok = True
    rows = []
    for tokens_path in files:
        result = process_file(
            lang=lang, spec=spec, grammar_path=grammar_path, driver_path=driver_path,
            tokens_path=tokens_path, out_dir=out_dir, work_dir=work_dir,
        )
        all_ok = all_ok and result["ok"]
        rows.append(result)

    name_w = max(len(r["stem"]) for r in rows)
    print(f"{'file'.ljust(name_w)}  folded      roundtrip   source==rebuilt  verdict")
    print(f"{'-' * name_w}  ----------  ----------  ---------------  -------")
    for r in rows:
        verdict = "OK" if r["ok"] else "FAIL"
        sm = {True: "yes", False: "NO", None: "-"}[r.get("source_match")]
        print(f"{r['stem'].ljust(name_w)}  {r['folded_n']}/{r['n']:<8} {r['roundtrip_n']}/{r['n']:<8} {sm:<15}  {verdict}")
        for e in r["errors"]:
            print(f"    {e}")

    print()
    print(f"ALL FOLDED AND ROUND-TRIPPED: {'true' if all_ok else 'false'}")
    print(f"(work dir: {work_dir})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
