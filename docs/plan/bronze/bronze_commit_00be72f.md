---
tags: [plan, bronze, generated, commit]
---
# bronze_commit_00be72f — Phase 0: fill README gaps and add tools/wiki_from_git.py

**Why this file exists.** Machine-lifted record of one commit: what changed, why, the doc comments of the artefacts it touched, and the receipt in its git note. Written by `tools/wiki_from_git.py`; not curated.

**Inputs → outputs.** commit `00be72f` (message, 4 changed path(s), git note) + 4 doc comment(s) → this page.

## Provenance

| field | value |
|---|---|
| commit | `00be72f200ca1394a514873968404c78584e7ff2` |
| author | Ravi Teja Mutyala <mutyala.ravit@gmail.com> |
| authored | 2026-09-08T22:11:24+05:30 |
| lifted by | `tools/wiki_from_git.py` at 2026-09-08T22:11:47+0530 |

## What changed

Phase 0: fill README gaps and add tools/wiki_from_git.py

| status | path |
|---|---|
| A | `backend/testdata_rules/README.md` |
| A | `build_bin/README.md` |
| A | `docs/README.md` |
| A | `tools/wiki_from_git.py` |

## Why (commit body, verbatim)

> Why: phase 0's pass mark is "every folder has a README; wiki_from_git.py
> writes one bronze page from one commit". Three folders had no README
> (build_bin/, backend/testdata_rules/, docs/) and the tool did not exist.
>
> What:
> - build_bin/README.md, backend/testdata_rules/README.md, docs/README.md,
>   in the same four-line house style as tools/README.md.
> - tools/wiki_from_git.py (362 lines, Python 3 stdlib only): lifts a
>   commit's message, the doc comments of the artefacts it touched, and its
>   git note into docs/<dimension>/bronze/bronze_commit_<shortsha>.md with
>   house-style YAML frontmatter. README extractor registered today; Rust
>   //! and TS /** */ extractors written and waiting on phase 1 files.
>   A commit with no note gets a Receipts section saying so.
>
> Judgement call: the five docs/plan medallion tier folders (raw, bronze,
> silver, gold and docs/plan itself) get no README — docs/wiki_root.md and
> docs/plan/plan.md already say what each tier holds, and the
> medallion-wiki-obsidian layout is the same in every dimension. So
> "every folder has a README" holds for every code/artefact folder, 21 of
> 26 paths, with the 5 vault tiers documented by their hub pages instead.
>
> Pass mark: half met by this commit (READMEs + the tool); the other half
> is the generated page, which lands in the next commit.
>
> Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
> Claude-Session: https://claude.ai/code/session_01SmR7Xvw2eaZymWC7AMDJno

## Doc comments of the artefacts touched

### `backend/testdata_rules/README.md` — testdata_rules — Test data for the rules

- **Why it exists.** Groups the generated test data the engines are checked against; `engine/` holds the Z3 rows per node/4 branch.
- **Inputs → outputs.** node/4 branches + Z3 → rows per branch for the run and data-match strip.

### `build_bin/README.md` — build_bin — Build outputs

- **Why it exists.** Holds the desktop build; `tauri_builder/` is its only member today.
- **Inputs → outputs.** the Rust backend + the two TypeScript UIs → one app bundle.

### `docs/README.md` — docs — Obsidian medallion vault

- **Why it exists.** The wiki for this track; open `wiki_root.md` first, then a dimension hub such as `plan/plan.md`.
- **Inputs → outputs.** doc comments, commit messages and git notes (lifted by `tools/wiki_from_git.py`) plus hand curation → raw / bronze / silver / gold pages per dimension.

### `tools/README.md` — tools — Tools

- **Why it exists.** wiki_from_git.py: doc comments + commit messages + git notes → bronze pages.
- **Inputs → outputs.** the git history → docs/<dimension>/bronze/*.md.
- **Covers.** `tools/wiki_from_git.py`

## Receipts

From `git notes show 00be72f`:

```
receipt: phase 0, READMEs + wiki_from_git.py (2026-09-08)

folders scanned          25 (find . -type d, excluding .git)
folders with a README    20 of 25 code/artefact folders (+ repo root) = 21 READMEs
folders left without     5 (docs/plan and its raw/bronze/silver/gold tiers) — by
                         judgement; covered by docs/wiki_root.md + docs/plan/plan.md
READMEs added this commit 3 (build_bin, backend/testdata_rules, docs)
READMEs read by the tool  4 doc comments lifted on this commit's 4 changed paths
tool size                362 lines, Python 3 stdlib only, 0 third-party imports
tool runtime             77 ms wall per run (5 runs: 77/78/78/76/77 ms, --stdout,
                         darwin 25.5.0, python3 --version below)
git calls per run        4 (rev-parse, show -s, diff-tree, notes show)
pass mark                READMEs: met for every code/artefact folder.
                         "writes one bronze page from one commit": met by the next
                         commit, which contains the generated page.
```

## Decisions

- **PROVEN ∎** — every line above is lifted from git; re-derive with `python3 tools/wiki_from_git.py 00be72f`.
