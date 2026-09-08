#!/usr/bin/env python3
"""wiki_from_git.py — grow the wiki from the code.

**Why this file exists.** The plan (section 9 of
``docs/plan/gold/gold_draft_exp_005_plan.md``) says the wiki is not hand-typed twice:
the facts already live in git — in the doc comment at the top of every module, in the
commit message that changed it, and in the ``git notes`` receipt attached to that
commit. This script lifts those three, unedited, into one bronze page per commit, so
silver and gold have something with provenance to link to.

**Inputs → outputs.** one commit-ish (its message, its changed paths, its git note) plus
the doc comments of the artefacts that commit touched → one
``docs/<dimension>/bronze/bronze_commit_<shortsha>.md`` page with YAML frontmatter,
a What changed / Why section, a Doc comments section and a Receipts section.

Bronze rule (``medallion-wiki-obsidian``): everything written here is machine-lifted and
carries its provenance. The script never writes prose of its own about the work; the
curation happens in silver and gold, by hand.

Usage::

    python3 tools/wiki_from_git.py <commit-ish> [--dimension plan] [--out docs/<dimension>/bronze/]

Python 3, standard library only.

Doc-comment extractors: today the only documented artefacts are the folder ``README.md``
files, so ``extract_readme`` is the only extractor registered. When Rust crates and TS
modules land in phase 1, register ``extract_rust_module_doc`` (``//!`` lines) and
``extract_ts_header_doc`` (a leading ``/** ... */``) in ``EXTRACTORS`` — the rest of the
script does not change.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- git


def git(*args: str, repo: Path) -> str:
    """Run a git command in `repo` and return stdout, stripped of the trailing newline."""
    out = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.rstrip("\n")


def git_or_none(*args: str, repo: Path) -> str | None:
    """Same, but return None when git exits non-zero (e.g. a commit with no note)."""
    out = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    )
    if out.returncode != 0:
        return None
    return out.stdout.rstrip("\n")


def repo_root(start: Path) -> Path:
    return Path(git("rev-parse", "--show-toplevel", repo=start))


def commit_facts(repo: Path, rev: str) -> dict:
    """sha, short sha, author, ISO date, subject and body of one commit."""
    sep = "\x1f"
    fmt = sep.join(["%H", "%h", "%an <%ae>", "%aI", "%s", "%b"])
    raw = git("show", "-s", f"--format={fmt}", rev, repo=repo)
    sha, short, author, date, subject, body = raw.split(sep, 5)
    return {
        "sha": sha,
        "short": short,
        "author": author,
        "date": date,
        "subject": subject,
        "body": body.strip("\n"),
    }


def changed_paths(repo: Path, sha: str) -> list[tuple[str, str]]:
    """[(status, path)] for one commit; the root commit is diffed against the empty tree."""
    raw = git_or_none(
        "diff-tree", "--no-commit-id", "--name-status", "-r", "-m", "--root", sha,
        repo=repo,
    )
    rows: list[tuple[str, str]] = []
    for line in (raw or "").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))
    # de-duplicate while keeping order (a merge commit lists a path once per parent)
    seen: set[str] = set()
    uniq = []
    for status, path in rows:
        if path in seen:
            continue
        seen.add(path)
        uniq.append((status, path))
    return uniq


def note_for(repo: Path, sha: str) -> str | None:
    """The git note on a commit, or None when it has none."""
    return git_or_none("notes", "show", sha, repo=repo)


# ------------------------------------------------------------------ doc comments

DOC_FIELDS = ("Why this folder exists.", "Why this file exists.", "Inputs → outputs.")


def extract_readme(text: str) -> dict | None:
    """Lift the opening doc block of a folder README.

    Returns {title, why, io} or None when the file does not carry one.
    """
    title = None
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        title = m.group(1).strip()
    why = io = None
    for line in text.splitlines():
        s = line.strip()
        for field in ("Why this folder exists.", "Why this file exists."):
            if s.startswith(f"**{field}**"):
                why = s[len(field) + 4 :].strip()
        if s.startswith("**Inputs → outputs.**"):
            io = s[len("**Inputs → outputs.**") :].strip()
    if not (title or why or io):
        return None
    return {"title": title, "why": why, "io": io}


def extract_rust_module_doc(text: str) -> dict | None:
    """Rust `//!` header block → the same shape. Registered from phase 1 on."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("//!"):
            lines.append(s[3:].strip())
        elif lines:
            break
    if not lines:
        return None
    return extract_readme("\n".join(lines)) or {
        "title": None,
        "why": lines[0],
        "io": None,
    }


def extract_ts_header_doc(text: str) -> dict | None:
    """A leading `/** ... */` block in a TS/JS file → the same shape. Phase 2/3."""
    m = re.match(r"\s*/\*\*(.*?)\*/", text, re.S)
    if not m:
        return None
    body = "\n".join(ln.strip().lstrip("*").strip() for ln in m.group(1).splitlines())
    return extract_readme(body) or {"title": None, "why": body.strip(), "io": None}


# suffix / basename → extractor. Add Rust and TS here when those files exist.
EXTRACTORS = {
    "README.md": extract_readme,
}


def doc_artifacts(repo: Path, paths: list[str]) -> list[dict]:
    """For every changed path, find the doc comment that documents it.

    A README documents itself; any other file is documented by the nearest README
    at or above it. Each artefact is reported once, with the paths it covers.
    """
    found: dict[str, dict] = {}
    for path in paths:
        doc_path = None
        if os.path.basename(path) in EXTRACTORS:
            doc_path = path
        else:
            d = Path(path).parent
            while True:
                cand = d / "README.md"
                if (repo / cand).is_file():
                    doc_path = str(cand)
                    break
                if str(d) in (".", "", "/"):
                    break
                d = d.parent
        if not doc_path:
            continue
        f = repo / doc_path
        if not f.is_file():
            continue
        if doc_path not in found:
            extractor = EXTRACTORS[os.path.basename(doc_path)]
            doc = extractor(f.read_text(encoding="utf-8"))
            if not doc:
                continue
            doc["path"] = doc_path
            doc["covers"] = []
            found[doc_path] = doc
        if path != doc_path:
            found[doc_path]["covers"].append(path)
    return [found[k] for k in sorted(found)]


# ----------------------------------------------------------------- page writing


def render(facts: dict, changed: list[tuple[str, str]], docs: list[dict],
           note: str | None, dimension: str, stats: dict) -> str:
    L: list[str] = []
    L.append("---")
    L.append(f"tags: [{dimension}, bronze, generated, commit]")
    L.append("---")
    L.append(f"# bronze_commit_{facts['short']} — {facts['subject']}")
    L.append("")
    L.append(
        "**Why this file exists.** Machine-lifted record of one commit: what changed, "
        "why, the doc comments of the artefacts it touched, and the receipt in its git "
        "note. Written by `tools/wiki_from_git.py`; not curated."
    )
    L.append("")
    L.append(
        f"**Inputs → outputs.** commit `{facts['short']}` "
        f"(message, {len(changed)} changed path(s), git note) + "
        f"{len(docs)} doc comment(s) → this page."
    )
    L.append("")
    L.append("## Provenance")
    L.append("")
    L.append("| field | value |")
    L.append("|---|---|")
    L.append(f"| commit | `{facts['sha']}` |")
    L.append(f"| author | {facts['author']} |")
    L.append(f"| authored | {facts['date']} |")
    L.append(f"| lifted by | `tools/wiki_from_git.py` at {stats['run_at']} |")
    L.append("")
    L.append("## What changed")
    L.append("")
    L.append(f"{facts['subject']}")
    L.append("")
    if changed:
        L.append("| status | path |")
        L.append("|---|---|")
        for status, path in changed:
            L.append(f"| {status} | `{path}` |")
    else:
        L.append("_No paths reported for this commit._")
    L.append("")
    L.append("## Why (commit body, verbatim)")
    L.append("")
    if facts["body"]:
        for line in facts["body"].splitlines():
            L.append(f"> {line}" if line.strip() else ">")
    else:
        L.append("_This commit has no message body._")
    L.append("")
    L.append("## Doc comments of the artefacts touched")
    L.append("")
    if docs:
        for d in docs:
            L.append(f"### `{d['path']}`" + (f" — {d['title']}" if d["title"] else ""))
            L.append("")
            if d["why"]:
                L.append(f"- **Why it exists.** {d['why']}")
            if d["io"]:
                L.append(f"- **Inputs → outputs.** {d['io']}")
            if d["covers"]:
                L.append(f"- **Covers.** " + ", ".join(f"`{p}`" for p in d["covers"]))
            L.append("")
    else:
        L.append("_No documented artefact was touched by this commit._")
        L.append("")
    L.append("## Receipts")
    L.append("")
    if note:
        L.append(f"From `git notes show {facts['short']}`:")
        L.append("")
        L.append("```")
        L.append(note)
        L.append("```")
    else:
        L.append(
            f"_No git note on `{facts['short']}`. Add one with "
            f"`git notes add {facts['short']}` and re-run this tool._"
        )
    L.append("")
    L.append("## Decisions")
    L.append("")
    L.append("- **PROVEN ∎** — every line above is lifted from git; re-derive with "
             f"`python3 tools/wiki_from_git.py {facts['short']}`.")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Lift a commit's message, doc comments and git note into a bronze wiki page."
    )
    p.add_argument("commitish", help="the commit to document (sha, tag, HEAD~1, ...)")
    p.add_argument("--dimension", default="plan",
                   help="wiki dimension the page belongs to (default: plan)")
    p.add_argument("--out", default=None,
                   help="output directory (default: docs/<dimension>/bronze/)")
    p.add_argument("--stdout", action="store_true",
                   help="print the page instead of writing it")
    args = p.parse_args(argv)

    t0 = time.perf_counter()
    here = Path(__file__).resolve().parent
    try:
        repo = repo_root(here)
    except subprocess.CalledProcessError:
        print("not inside a git repository", file=sys.stderr)
        return 2
    try:
        facts = commit_facts(repo, args.commitish)
    except subprocess.CalledProcessError:
        print(f"no such commit: {args.commitish}", file=sys.stderr)
        return 2

    changed = changed_paths(repo, facts["sha"])
    docs = doc_artifacts(repo, [path for _, path in changed])
    note = note_for(repo, facts["sha"])

    stats = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    page = render(facts, changed, docs, note, args.dimension, stats)

    if args.stdout:
        print(page)
        return 0

    out_dir = Path(args.out) if args.out else repo / "docs" / args.dimension / "bronze"
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"bronze_commit_{facts['short']}.md"
    out_file.write_text(page, encoding="utf-8")

    ms = (time.perf_counter() - t0) * 1000
    rel = out_file.relative_to(repo)
    print(f"commit    {facts['short']}  {facts['subject']}")
    print(f"changed   {len(changed)} path(s)")
    print(f"doc       {len(docs)} doc comment(s) lifted")
    print(f"note      {'yes, ' + str(len(note.splitlines())) + ' line(s)' if note else 'none'}")
    print(f"wrote     {rel}  ({out_file.stat().st_size} bytes)")
    print(f"runtime   {ms:.0f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
