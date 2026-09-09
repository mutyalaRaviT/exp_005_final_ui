---
tags: [plan, bronze, phase2, ledger]
---
# bronze_phase2_route_ledger — which routes have landed

**Why this file exists.** `tools/diff_route.py` is the differential oracle for phase 2: a route
only "lands" (moves from `oracle::forward` to the store) once its answers are proved identical to
the Python implementation it replaces, question by question, file by file. This page is the
record of that proof: which of the twelve questions in the plan's §6 table have landed, whether
their corpus ran clean, and every difference a human has looked at and accepted as the parser
being right instead of the scanner. There is no other way to wave a difference through — no flag
does it silently. See `tools/diff_route.py`'s module doc comment and Task 4's report
(`.superpowers/sdd/silver_phase2_implementation_plan/task-4-report.md`) for how the tool works.

## Routes

| question | landed | corpus clean | accepted divergences |
|---|---|---|---|
| files | yes | yes | — |
| search | yes | yes (q="") | — |
| neighborhood | no | — | — |
| convert | no | — | — |
| blocklinks | no | — | — |
| edges | no | — | — |
| source | no | — | — |
| file | no | — | — |
| blocks | no | — | — |
| tablegraph | no | — | — |
| story | no | — | — |
| run | no | — | — |

`landed`: `no` until the route reads from the store instead of forwarding to a Python oracle
(`oracle::forward` deleted for that arm) and its `diff_route.py` run — or, for `convert`/`run`,
its stated pass mark — is clean. `corpus clean`: `yes` once every file in the question's corpus
diffs clean (after accepted divergences are subtracted); `no oracle — new surface` for `convert`
and `run`, whose briefs (Task 6b, Task 12) explicitly say no oracle comparison applies. `accepted
divergences`: a count with a link into the table below, or `—` if none.

## Accepted divergences

| question | fileid | json_path | why the parser is right |
|---|---|---|---|

No rows yet for a diff `diff_route.py` actually ran and found a difference in. Each row here is
added by the task that lands the route it belongs to, never by this task: Task 4 only builds the
ledger and the tool that reads it.

## Task 5 note: `search()`'s oracle check is `q=""` only

`diff_route.py`'s `search` route (`ROUTES["search"]`, `tools/diff_route.py`) checks
`GET /api/search?q=` against `:8000` — both sides correctly return `{"hits":[]}`, so the tool's
own run is clean by construction and has never seen a non-empty query. That is not a gap in
`diff_route.py` to fix here (no brief gives it a rule for which queries to check across a
25-file corpus); it means Task 5's answer-quality claim for non-empty `q` rests on
`backend/api/tests/search.rs`'s direct assertions instead, not the differential oracle.

Verified live against `:8000` for `q=fx`: `work.fx_rates` (written by `06_seed_fx_rates.sas`) and
`work.txns_fx` (written by `07_enrich_fx.sas`) both come back with fewer files on the Rust side
than `:8000`'s regex-scan `mentions` index finds — `work.fx_rates` is missing `07_enrich_fx.sas`
as a reader, `work.txns_fx` is missing `07_enrich_fx.sas` as its writer entirely. The cause is not
`search()`: `07_enrich_fx.sas`'s `PROC SQL CREATE TABLE AS SELECT` fails to fold in
`rust_rules_converter` (a pre-existing parser gap — `receipts.folded` is 2 of 3 statements for
that file), so no `edges` row and no `tables` row ever exists for what it reads or writes.
`search()` correctly reports everything the store currently holds; the store just holds less than
`:8000`'s regex scan does for this file. This is the same class of gap Task 6's own brief expects
("the parser finding a flow the regex scanner missed is the likely shape" — here it is the other
direction, the parser finding *less* because it fails to fold a statement `:8000`'s regex scan
does not need to parse at all). Not fixed here: it is a `rust_rules_converter` SQL-fold gap, not a
`files()`/`search()` defect, and fixing the SQL parser is out of Task 5's scope. Left for whichever
later task (`neighborhood`, `edges`, `blocklinks` all read the same `edges` table) needs
`07_enrich_fx.sas` to fold correctly to hit its own pass mark.
