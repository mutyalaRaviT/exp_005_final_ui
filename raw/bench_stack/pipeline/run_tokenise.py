"""pipeline.run_tokenise — CLI: tokenise every corpus file for one language.

Usage:
    python3 -m pipeline.run_tokenise <lang> [--dir <corpus dir>]

<lang> selects pipeline/specs/<lang>.py (must export LANG, see
pipeline/tokeniser.py for the spec contract). The file extension to scan
for comes from that spec's own "ext" key — *.pig for pig, *.hql for hive
— so this runner holds no per-language table of any kind.

The corpus dir is scanned RECURSIVELY (files may sit directly under it, or
one or more tiers down, e.g. corpus/pig/small/*.pig) — so the default
`--dir` (./corpus/<lang>) picks up corpus/<lang>/small/*.<ext> without
needing --dir spelled out.

For each matching file this writes out/tokens/<lang>/<stem>.tokens.json:
    {"file": ..., "lossless": true, "n_tokens": ..., "tokens": [...]}
`lossless` is always true in a written file — tokenise() asserts the
lossless law itself, so a file only gets written after that assertion
already passed for it.

Prints a per-file verdict table, then a final "ALL LOSSLESS: true/false"
line, and exits 0 if every file tokenised cleanly, 1 otherwise (a spec bug,
a missing corpus dir, or zero matching files all count as failure).
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

from pipeline.tokeniser import tokenise


def load_spec(lang):
    mod = importlib.import_module(f"pipeline.specs.{lang}")
    return mod.LANG


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run_tokenise")
    ap.add_argument("lang", help="language name, e.g. pig or hive (must match pipeline/specs/<lang>.py)")
    ap.add_argument("--dir", dest="corpus_dir", default=None,
                     help="corpus directory to scan (default: ./corpus/<lang>)")
    args = ap.parse_args(argv)

    lang = args.lang

    try:
        spec = load_spec(lang)
    except ModuleNotFoundError as e:
        print(f"ERROR: could not load pipeline/specs/{lang}.py ({e})", file=sys.stderr)
        return 1

    # The file extension is language knowledge, so it lives in the spec with
    # the rest of it — not in a table here. A runner-side {lang: ext} dict
    # would mean teaching the pipeline a new language takes two edits: the
    # new spec module, plus this shared file. One edit is the rule.
    ext = spec.get("ext")
    if not ext:
        print(f"ERROR: pipeline/specs/{lang}.py declares no 'ext' key — every "
              f"LANG dict must name its source file extension, e.g. \"ext\": \".hql\"",
              file=sys.stderr)
        return 1

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else Path("corpus") / lang
    if not corpus_dir.is_dir():
        print(f"ERROR: corpus dir not found: {corpus_dir}", file=sys.stderr)
        return 1

    files = sorted(corpus_dir.rglob(f"*{ext}"))
    if not files:
        print(f"ERROR: no {ext} files found in {corpus_dir}", file=sys.stderr)
        return 1

    out_dir = Path("out") / "tokens" / lang
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []  # (stem, verdict_str, n_tokens_or_dash)
    all_lossless = True

    for path in files:
        stem = path.stem
        text = path.read_text(encoding="utf-8")
        try:
            tokens = tokenise(spec, text)
        except AssertionError as e:
            all_lossless = False
            rows.append((stem, "FAIL", str(e)))
            continue
        except Exception as e:  # a broken spec (bad regex, etc.) is still a per-file failure
            all_lossless = False
            rows.append((stem, "ERROR", f"{type(e).__name__}: {e}"))
            continue

        record = {
            "file": str(path),
            "lossless": True,
            "n_tokens": len(tokens),
            "tokens": tokens,
        }
        out_path = out_dir / f"{stem}.tokens.json"
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        rows.append((stem, "OK", len(tokens)))

    name_w = max(len(r[0]) for r in rows)
    print(f"{'file'.ljust(name_w)}  verdict  n_tokens / note")
    print(f"{'-' * name_w}  -------  --------------")
    for stem, verdict, extra in rows:
        print(f"{stem.ljust(name_w)}  {verdict:<7}  {extra}")

    print()
    print(f"ALL LOSSLESS: {'true' if all_lossless else 'false'}")
    return 0 if all_lossless else 1


if __name__ == "__main__":
    raise SystemExit(main())
