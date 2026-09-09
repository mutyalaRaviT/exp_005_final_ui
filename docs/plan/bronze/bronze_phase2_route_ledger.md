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
| files | no | — | — |
| search | no | — | — |
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

No rows yet — no route has landed. Each row here is added by the task that lands the route it
belongs to, never by this task: Task 4 only builds the ledger and the tool that reads it.
