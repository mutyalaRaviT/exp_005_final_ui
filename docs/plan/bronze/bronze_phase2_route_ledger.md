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
| neighborhood | yes | yes (288 accepted, 3 root causes — Task 6 note) | 288 |
| convert | yes | no oracle — new surface (Task 6b note) | — |
| blocklinks | yes | yes (80 accepted, 1 root cause — Task 7 note) | 80 |
| edges | yes | yes (84 accepted, 2 root causes — Task 7 note) | 84 |
| source | yes | yes (0 diffs, Bench `/api/file?path=` — M2/G2) | — |
| file | yes | yes (64 accepted, 6 root causes — Task 9 note) | 64 |
| blocks | yes | yes (81 accepted, 6 root causes — Task 9 note) | 81 |
| tablegraph | yes | yes (4 accepted, 1 root cause — Task 10 note) | 4 |
| story | yes | no oracle — the Bench has no story surface (Task 10 note) | — |
| run | yes | no oracle — the pass mark is the 2026-09-09 receipt, 11/11 (Task 12 note) | — |

**Twelve of twelve, 2026-09-10 (M4a).** `convert` was the last unlanded question; with it the
`landed` column has no `no` left in it and `/api/health` reports `forwarded: []`. The fallback and
`oracle.rs` still exist — deleting them is Task 14 (M4b), whose job is to prove nothing needs them.

`landed`: `no` until the route reads from the store instead of forwarding to a Python oracle
(`oracle::forward` deleted for that arm) and its `diff_route.py` run — or, for `convert`/`run`,
its stated pass mark — is clean. `corpus clean`: `yes` once every file in the question's corpus
diffs clean (after accepted divergences are subtracted); `no oracle — new surface` for `convert`
and `run`, whose briefs (Task 6b, Task 12) explicitly say no oracle comparison applies. `accepted
divergences`: a count with a link into the table below, or `—` if none.

## Accepted divergences

| question | fileid | json_path | why the parser is right |
|---|---|---|---|
| blocklinks | * | links[missing:3e4322a1c4a9] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:666b86d8ec26] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:b9fa62b615af] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:37e3a4f8a1c2] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:1f3eda49f6cf] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:ba87a0718062] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:0119efeb3e46] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:a82a4ca7f453] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:0ec4fb4f0d47] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:e7cf0bfd7102] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:419d9a75770b] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:ddb9acbd4496] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:0c472968a28a] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:154a2b441ae5] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:5fb5ad5c6aa6] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:25cf457ea932] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:bc01d61b039e] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:0353ceab6fb1] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:3b9fd8e2e82e] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:471494708abf] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:af0a82cc56ae] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:68f726f8e715] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:95de359d97a1] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:fd9807b21e89] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:8516451dead9] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:fb595f3d0c22] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:316231cd2e72] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:88134454d613] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:5b77d2adf7ed] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:e47db1c32078] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:88e349737ce9] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:373304c777d5] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:12ef81664384] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:d3336d993fea] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:4b8a61016235] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:959ee5d4cbe9] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:684ba8fd1d94] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:2b2ff4ba9f05] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:8e87d9e07620] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[missing:661d1e1ecc09] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:9974babccab6] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:b81679f7ce6c] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:a16cb38549f4] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:5eacfcbdfcbd] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:fd306bab44cc] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:4a1a1d0395b1] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:a996b7776bcb] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:10071fd27b84] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:23d9813ae9ef] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:983d6ae86a31] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:97e76cb7b0b6] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:08a0983eb787] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:e4133698dc44] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:8a8992c2ef07] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:affe76a86b27] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:2d6da6e2a42e] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:38e9e6b66eea] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:b9e82562c20c] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:32b04efcea85] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:11769cfe64af] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:64d83bc5adcc] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:7d7d4646a6f2] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:67a087f5825f] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:2f62992b9129] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:0b95e69f74f8] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:c554dbb87392] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:32216d01605b] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:1937e90b2c1d] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:a9b49a9c31c3] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:cddc9dddd3d7] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:66a0008066d2] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:ce63ea7f0e6f] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:7ee62de0ce52] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:11b00e9f8f5a] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:6be713e7b90c] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:6972772d336b] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:5a07bc3f787f] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:5185d3025d82] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:788abf126619] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| blocklinks | * | links[extra:2b9e1bb3ba23] | block-id naming (cause B1) — same link, `:8000` names the blocks `b_<n>_<hash8>` and its refs `:t_<n>`; this store names them `b_<nnn>` and `<block>:<table>`. Membership identical: stripping the four id fields makes the two lists equal, 40 = 40. |
| edges | * | rows[missing:d41464d8e3e3] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:e9dec18dfe24] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:a6fe9ce4bb59] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:df7aabc850af] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:2f5e4d087f60] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:0f35cf973cb8] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:19fe89a2c0e7] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:794e09ca90f7] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:2049f85219b3] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:9ab198b21df7] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:3acc8fefe924] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:10019f180d78] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:8212d29bb608] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:bd5614e2c83c] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:11e5cb908e8e] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:bb7e1a4c907f] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:ea1c12c38fd1] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:c08fcf0d6d91] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:a8ba69e5a655] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:fab241d38da4] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:1224e3604972] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:bf30f7206387] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:e319a95adaac] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:1cf1611d7112] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:8f464a423141] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:f058838f44ff] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:d5957d0aa995] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:1d0d46866d7b] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:2ec5dcdfc2e6] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:8b60e282f7d4] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:a5f0326ed4b2] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:3b4890de9a36] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:33bf0abbba3f] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:ce79531ff9d4] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:2f6304f61c74] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:39054adc5ecd] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:c60ad5b87679] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:4cfb8b1cdbee] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:e4c79c6aede8] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:88b35c07752b] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:2eebf96cf7dd] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[missing:a3939754b95d] | `FILE_FLOW` shape (cause B2) — `:8000` records an intra-file block-to-block handoff (`b_1_eab6f12f` writes `work.accounts_raw`, `b_2_66e46f94` reads it) as one `level=file` self-edge `work.accounts_raw -> work.accounts_raw`. This store has no `FILE_FLOW` fact and states the same handoff as its two `level=block` rows, both present in the answer. No fact is lost; only the shape differs. |
| edges | * | rows[extra:b451675f7155] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:279b770a227b] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:8b1bf8c50f35] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:dd33f34c3fa5] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:939d08f6287c] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:9dee9ffd6f4e] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:323f7ffcf264] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:9fdd24ac17c9] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:f133dce6129e] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:6e529ecece8c] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:5b6e88e78028] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:b8b02961ac21] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:06740a6e4331] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:d9652e2ff4e6] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:a9f0b6411871] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:11f15e74e466] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:2bdef9409523] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:2f25022bcf10] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:5c15f8a00af9] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:a438dad93c83] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:8dbfd13a22bf] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:f2a3817ff5cd] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:cef6916e1b6d] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:57cf0389115d] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:877e43d32373] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:45fc402d9d34] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:9867f2876814] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:2cbba91c5750] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:5ada34f2ccba] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:bd36a04ffd8b] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:81384e91af92] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:19851e676b06] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:4c9f106f23d0] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:f4f7564c6094] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:786a7472a430] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:328554d5cf4e] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:7a91781160fb] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:06d1968521a9] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:34b79622480d] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:abf8f91719f8] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | rows[extra:1c4de2e0e71a] | block-id naming (cause B1) — same flow, different block-id scheme; stripping `block_id` makes the two row multisets equal, 41 = 41. |
| edges | * | total | follows arithmetically from the one `FILE_FLOW` row above (cause B2): 83 - 1 = 82. Not an independent difference. |
| file | test_vishnu_testdata_fixed.sas | blocks[0].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[0].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[0].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[1].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[1].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[2].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[2].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[3].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[3].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[4].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[4].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[5].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[5].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[6].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[6].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[7].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[7].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[8].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[8].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[9].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[9].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[10].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[10].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[11].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[11].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[12].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[12].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[12].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[13].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[13].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[13].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[14].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[14].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[14].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[15].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[15].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[15].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[16].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[16].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[16].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[17].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[17].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[17].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[18].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[18].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[18].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[19].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[19].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[19].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[20].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[20].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[20].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[21].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[21].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[21].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | blocks[22].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| file | test_vishnu_testdata_fixed.sas | blocks[22].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| file | test_vishnu_testdata_fixed.sas | blocks[22].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| file | test_vishnu_testdata_fixed.sas | path | C4 addressing — the Bench addresses a file by a path relative to `raw/bench_stack/` (`../../corpus/fixtures/<name>.sas`); this store addresses it by the fileid `convert` assigned, relative to the converted folder. Two spellings of the same file. |
| file | test_vishnu_testdata_fixed.sas | receipts.node4_same | C5 proof receipts — `node4_same`/`pyspark_same`/`pyspark_pretty_same` are filled by the Prolog proof, which does not run until M3, so they are NULL here; `proof_state` ('pending') is this store's own column and the Bench has no counterpart; `rust_us` is a wall-clock measurement of two separate runs and can never agree by construction. The four receipts that carry the answer — statements, folded, roundtrip, source_match — are 80/80/80/true on both sides. |
| file | test_vishnu_testdata_fixed.sas | receipts.proof_state | C5 proof receipts — `node4_same`/`pyspark_same`/`pyspark_pretty_same` are filled by the Prolog proof, which does not run until M3, so they are NULL here; `proof_state` ('pending') is this store's own column and the Bench has no counterpart; `rust_us` is a wall-clock measurement of two separate runs and can never agree by construction. The four receipts that carry the answer — statements, folded, roundtrip, source_match — are 80/80/80/true on both sides. |
| file | test_vishnu_testdata_fixed.sas | receipts.pyspark_pretty_same | C5 proof receipts — `node4_same`/`pyspark_same`/`pyspark_pretty_same` are filled by the Prolog proof, which does not run until M3, so they are NULL here; `proof_state` ('pending') is this store's own column and the Bench has no counterpart; `rust_us` is a wall-clock measurement of two separate runs and can never agree by construction. The four receipts that carry the answer — statements, folded, roundtrip, source_match — are 80/80/80/true on both sides. |
| file | test_vishnu_testdata_fixed.sas | receipts.pyspark_same | C5 proof receipts — `node4_same`/`pyspark_same`/`pyspark_pretty_same` are filled by the Prolog proof, which does not run until M3, so they are NULL here; `proof_state` ('pending') is this store's own column and the Bench has no counterpart; `rust_us` is a wall-clock measurement of two separate runs and can never agree by construction. The four receipts that carry the answer — statements, folded, roundtrip, source_match — are 80/80/80/true on both sides. |
| file | test_vishnu_testdata_fixed.sas | receipts.rust_us | C5 proof receipts — `node4_same`/`pyspark_same`/`pyspark_pretty_same` are filled by the Prolog proof, which does not run until M3, so they are NULL here; `proof_state` ('pending') is this store's own column and the Bench has no counterpart; `rust_us` is a wall-clock measurement of two separate runs and can never agree by construction. The four receipts that carry the answer — statements, folded, roundtrip, source_match — are 80/80/80/true on both sides. |
| blocks | test_vishnu_testdata_fixed.sas | [0].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [0].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [0].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [0].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [1].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [1].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [1].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [2].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [2].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [2].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [3].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [3].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [3].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [4].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [4].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [4].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [5].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [5].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [5].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [6].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [6].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [6].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [7].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [7].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [7].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [8].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [8].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [8].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [9].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [9].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [9].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [10].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [10].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [10].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [11].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [11].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [11].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [12].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [12].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [12].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [12].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [13].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [13].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [13].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [13].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [14].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [14].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [14].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [14].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [15].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [15].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [15].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [15].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [16].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [16].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [16].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [16].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [17].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [17].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [17].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [17].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [18].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [18].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [18].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [18].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [19].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [19].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [19].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [19].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [20].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [20].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [20].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [20].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [21].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [21].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [21].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [21].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |
| blocks | test_vishnu_testdata_fixed.sas | [22].kind | C2 kind vocabulary — this store prints the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`). The Bench prints the section header of its *pretty-printed PySpark* when it finds one and a hand-written display map (`{'libname':'LIBNAME','data':'DATA step',...}`, `bench_api.py:312`) when it does not. Same block, one engine value and one display value. |
| blocks | test_vishnu_testdata_fixed.sas | [22].n | C1 block index base — this store's `n` is the 0-based `blocks.n` that `blocks(from,to)` windows on; the Bench prints `int(block_id.split('_')[1])`, i.e. 1-based. The block ids themselves are identical (`b_001`..`b_023`), so this is one number written two ways. Emitting the Bench's would make `file()` and `blocks()` disagree about which block a window contains. |
| blocks | test_vishnu_testdata_fixed.sas | [22].name | C3 name of a block that makes no table — this store leaves `blocks.name` empty when the block writes nothing (LIBNAME, every PROC PRINT); the Bench falls back to the head functor, so it reads `name: 'proc_print'`. Every block that does write a table agrees exactly (21/23 names identical). |
| blocks | test_vishnu_testdata_fixed.sas | [22].py | C6 packaging of the generated PySpark — the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's `py` is the block's own standalone runnable program (preamble, the generated statement, epilogue), which is the form Task 12's `run()` executes. Traced by hand over all 23 blocks: for the 11 blocks where the Bench emits any code at all, its exact text is a verbatim substring of this store's `py_pretty` (the one exception, b_012, is the Bench's last section running to EOF and swallowing 11 PROC PRINT comment blocks; its first line matches verbatim). For the other 12 the Bench emits `''` because its section finder finds no section, while this store does generate the LIBNAME and PROC PRINT code. |

164 rows: `blocklinks` 80, `edges` 84 — all of them Task 7's, all of them traced to the two
root causes in the Task 7 note below. `neighborhood` carried 288 rows here (Task 6, three `rust_rules_converter` fold gaps —
qualified star, `CROSS JOIN`, `UNION ALL` under-reporting) until Task 5d fixed all three; see the
"Task 5d note" below. `files`/`search` have run clean by construction since Task 5 (0 diffs
found) and never needed a row.

## Task 10 note: `tablegraph()`'s 4 divergences are the `ctl` label alone, and `story()` has
## no oracle anywhere to check against

Run (2026-09-10): `python tools/diff_route.py tablegraph --rust-base http://127.0.0.1:8112
--oracle-b http://127.0.0.1:8342` — 4 diffs, one cause, then clean.

**The pass mark is met on the nose.** The owner's Bench screenshot of
`test_vishnu_testdata_fixed.sas` says **12 edges**, `sales.sales_data` at the source and
`sales.final_summary` at the end, and `sales.q1_avg_sales` made by `b_007`. This store answers
12 edges, and all twelve match the Bench's `ds_lineage` facts exactly — same `src`, same `dst`,
same `block_id`, including `b_007`.

**Cause C7 — RETIRED by M3a (2026-09-10), commit `6a2db0c`.** The four rows are DELETED, not
re-accepted, and `diff_route.py tablegraph --corpus exp42` is clean without them (re-run below).
The label was never missing from `rust_rules_converter` at all: it emits `ctl_lineage(Out, In,
Col)` and always has. It was dropped by the store's edge writer,
`rust_inferred_duckdb/src/lineage_blocks.rs::edges_per_block`, which parsed `ds_lineage/2` lines
and skipped every other fact. That writer now also reads `ctl_lineage/3`, deduplicated per
(src, dst, block) because the fact names a column and the store's edge names a table pair. The
store answers 12 `ds` + 4 `ctl` for this fixture; the pass mark is unchanged — it counts the
twelve dataset flows — and `backend/api/tests/tablegraph.rs` now pins both counts plus the fact
that every `ctl` edge repeats a triple one of the twelve `ds` edges already draws.

What the four were (kept as the record of the trace):

| the `ctl` edge the Bench also emits | already present here as |
|---|---|
| `sales.sales_data -> sales.q1_sales`, `b_005` | `ds` |
| `sales.avg_sales -> sales.above_avg_sales`, `b_010` | `ds` |
| `sales.sales_data -> sales.above_avg_sales`, `b_010` | `ds` |
| `sales.sales_data -> sales.monthly_sales`, `b_011` | `ds` |

No table pair was missing from the graph and none was invented — what was missing was a second,
control-flavoured label on a pair that was already drawn. M3a landed it in the owning layer and
deleted these four rows.

`tables[].kind` is projected off both sides, as it has been since Task 4's tool: the Bench's
lineage facts carry no per-table classification at all, so there is nothing to check this
store's `source`/`derived` against.

**`story()` stays `no_oracle`, and this is the revisit finding G2 asked for.** The old note
guessed the blocker was "which table's story for a given file", solvable with a `--table` flag
or a fixture map. It is not: the Bench has **no story surface at all** — no route of its takes
a table name — so even with a fixture map there would be nothing on the oracle side to diff.
`story()` therefore lands on its own pass mark instead: `tests/tablegraph.rs` asserts that
`sales.final_summary`'s makers come back ordered by `blocks.n` (run order, not the order
`edges` happens to scan), that a maker names its file and block (`b_012`), and that a table
nobody makes — `sales.sales_data`, built from datalines — is an empty list and not an error.

## Task 9 note: `file()`'s 64 and `blocks()`'s 81 divergences are six packaging differences,
## and `source()` matched the Bench byte for byte

Runs (2026-09-10):

```
python tools/diff_route.py source --rust-base http://127.0.0.1:8112 --oracle-b http://127.0.0.1:8342
python tools/diff_route.py file   --rust-base http://127.0.0.1:8112 --oracle-b http://127.0.0.1:8342
python tools/diff_route.py blocks --rust-base http://127.0.0.1:8112 --oracle-b http://127.0.0.1:8342
```

`--rust-base` and `--oracle-b` are new (M2/G2). Both are needed and neither could be a
constant. `:8110` serves the `team_finance` store, whose `/api/files` answer is 25 files and
must stay 25 (Task 5), so the exp42 corpus lives in its own store and its own API instance.
`:8042` belongs to the owner's **other** checkout (`lineageQ_aug_experiments/
exp_42_test_vishnu`, plan Part F, F8): it answers, so a run against it silently compares this
repo's Rust to another repo's Python. This repo's Bench was started on a free port
(`cd raw/bench_stack && .venv/bin/python server/convert_api.py --port 8342`) and stopped after.

**`source`: 0 diffs.** Oracle is the Bench's `GET /api/file?path=` -> `{path, text, size}`,
the candidate the old `no_oracle` note itself named. `path` is projected off both sides — the
Bench spells a file as a path relative to `raw/bench_stack/`, this store as a fileid, and
those are two spellings of one file, not two answers. `text` and `size` are compared and
agree exactly. That closes finding G2 for `source`.

**`file`: 64. `blocks`: 81.** Six causes:

| cause | field | what it is |
|---|---|---|
| C1 | `n` | this store's 0-based `blocks.n` — the index `blocks(from,to)` windows on — against the Bench's `int(block_id.split("_")[1])`, which is 1-based. The ids themselves are identical, `b_001`..`b_023`. Printing the Bench's number here would make `file()` and `blocks()` disagree about which block a window holds. |
| C2 | `kind` | the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`) against the Bench's *display* value: the section header of its pretty-printed PySpark when it finds one, and a hand-written map (`bench_api.py:312`) when it does not. |
| C3 | `name` | empty when the block writes no table, against the Bench's head-functor fallback (`name: "proc_print"`). All 21 blocks that do write a table agree exactly. |
| C4 | `path` | fileid against a `raw/bench_stack/`-relative path — the same difference `source` projects away, reported once here. |
| C5 | `receipts.*` | `node4_same` / `pyspark_same` / `pyspark_pretty_same` are filled by the Prolog proof, which does not run until M3, so they are NULL on this side; `proof_state` is this store's own column with no Bench counterpart; `rust_us` is a wall-clock timing of two separate runs. |
| C6 | `py` | the Bench's `py` is one section sliced out of its whole-file pretty program (`_py_sections`); this store's is the block's own standalone runnable program — preamble, the generated statement, epilogue — which is the form Task 12's `run()` executes. |

C6 was traced block by block rather than asserted: of the 23 blocks, the Bench emits PySpark
for 11, and for every one of those its exact text is a **verbatim substring** of this store's
`py_pretty` (the single exception, `b_012`, is the Bench's last section running to end of file
and swallowing eleven PROC PRINT comment blocks; its first line matches verbatim). For the
other 12 — the LIBNAME and every PROC PRINT — the Bench emits `""` because its section finder
finds no section, while this store does generate their code.

What matched exactly, and is why these two land: `stem`, `ok`, `errors`, and every block's
`id`, `lines`, `warn`, `reads` and `writes` — all 23 — plus the four receipts that carry the
answer: **statements 80, folded 80, roundtrip 80, source_match true** on both sides. No fact
is missing on either side and none is invented on this one.

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

## Task 6 note: `neighborhood()`'s 288 accepted divergences trace to three `rust_rules_converter`
## fold gaps, not to `neighborhood()` itself

`python3 tools/diff_route.py neighborhood --corpus ankitha` checks all 25 `ankitha_1/*.sas` files
at `up=1&down=1` against `:8000`. 10 of 25 files diff perfectly clean with **zero** differences
(`03_seed_branches`, `05_seed_transactions`, `06_seed_fx_rates`, `07_enrich_fx`, `12_txn_agg`,
`13_risk_flags`, `19_export_dashboard`, `20_seed_crm_scores`, `21_crm_overlay`, `23_seed_watchlist`)
— including both of the brief's headline files' *sibling* corpus members, and `07_enrich_fx.sas`
itself, whose own pass mark (`enrich_fx_is_four_files_and_three_edges`, 1 seed / 2 up / 1 down)
matches `:8000` exactly, byte for byte, `order` and `story` text included. That is the proof the
BFS/roll-up/`compute_order`/story algorithm ported here is right: every one of the other 15
files' 288 diffs traces to one of exactly three pre-existing `rust_rules_converter` fold gaps —
none to a bug in this route's own logic — verified by hand for every affected file below, not
merely assumed from the pattern.

**Root cause A — `04_build_accounts.sas`'s qualified star.** Block `b_002`
(`create table work.accounts as select a.*, c.segment, p.prod_type from work.accounts_raw a inner
join work.customers c on ... inner join work.products p on ...`) never produces a fold `Term` at
all (`receipts` for this file: 10 statements, 9 folded — the missing one is this statement).
Named in the Task 6 brief as a known-unsupported construct. Consequence: **no** `ds_lineage` fact
and **no** `blocks.name` row exists anywhere in the store for `work.accounts` — not even a partial
one (`block_write_target`'s fallback, added in Task 5, only fires for a term that DID fold; there
is none here). So `work.accounts` has no registered writer at all, and every file that reads it
(`08_daily_balances`, `09_customer_summary`, `10_product_metrics`, `11_branch_rollup`,
`14_large_txn_report`, `15_join_risk_txn`, `22_marketing_list`, `24_ops_alerts`) is missing
`04_build_accounts.sas` as an up-node in its own neighborhood, and `04_build_accounts.sas`'s own
neighborhood is missing every one of them as a down-node. Every node/edge/`order`/`story` line
naming that link is legitimately absent from the Rust answer — verified against `edges`/`tables`/
`blocks` directly: `SELECT * FROM tables WHERE name='work.accounts'` returns zero rows;
`SELECT * FROM edges WHERE src_table='work.accounts' OR dst_table='work.accounts'` returns eight
rows, all with `work.accounts` as `src_table` (a read), never as `dst_table` (a write). Affects:
`01_seed_customers`, `02_seed_products`, `04_build_accounts`, `08_daily_balances`,
`09_customer_summary`, `10_product_metrics`, `11_branch_rollup` (**the brief's own pass-mark
file**), `14_large_txn_report`, `15_join_risk_txn`, `18_dashboard_mart`, `22_marketing_list`,
`24_ops_alerts`.

**Root cause C — `17_compliance_check.sas`'s `CROSS JOIN`.** Its single statement
(`create table work.compliance_check as select ... from work.risk_txn r cross join
work.audit_log a where a.event = 'PIPELINE_CHECKPOINT'`) never folds, for the same reason as A —
`CROSS JOIN` is the second construct the Task 6 brief names as known-unsupported. Same
consequence, same verification method: `work.compliance_check` has no writer row anywhere in the
store. Affects: `15_join_risk_txn` (also under A), `16_audit_log`, `17_compliance_check`,
`25_final_pack`.

**Root cause U — `UNION ALL` loses 3 of its 4 branches (newly found this task, not named in the
brief).** `18_dashboard_mart.sas` and `25_final_pack.sas` are the corpus's only two files whose
`CREATE TABLE AS SELECT` is a multi-branch `UNION ALL`. Both **do** fold — `receipts.folded`
equals `receipts.statements` for each (3/3 and 3/3) — but
`rust_rules_converter::lineage::sas::run` emits exactly one `ds_lineage` fact per `CREATE TABLE
AS` statement, so only the first `UNION ALL` branch's source table is ever recorded. Verified
directly: `18_dashboard_mart.sas` reads four tables (`work.branch_rollup`, `work.prod_metrics`,
`work.cust_summary`, `work.large_txn_report` — its own header comment says so) but `SELECT * FROM
edges WHERE dst_table='work.dashboard_mart'` returns exactly one row (`work.branch_rollup`, the
first branch). `25_final_pack.sas` reads four tables (`work.compliance_check`,
`work.ops_alerts`, `work.dashboard_mart`, `work.marketing_list`) but `SELECT * FROM edges WHERE
dst_table='work.final_pack'` returns exactly one row (`work.compliance_check`, its first branch —
itself unreachable per root cause C, which is why `25_final_pack.sas`'s diff list also carries
that edge as missing). This is a `lineage::sas::run` gap distinct from A and C (the statement
folds; the *lineage rule* under-reports), still entirely inside `rust_rules_converter`, still out
of this task's explicit scope ("Do not edit `backend/rust_rules_converter`"). Affects:
`18_dashboard_mart`, `25_final_pack`.

**Why 288 rows and not 3.** `diff_route.py`'s `filter_accepted` matches on the exact
`(question, fileid, json_path)` triple — there is no wildcard and, by design, no `--force`
(`tools/diff_route.py`'s own module doc: "There is no third option"). Each of the 288 rows in the
table above is one leaf `diff_json` found and traced, by hand, to A, C, U or a combination
(`15_join_risk_txn.sas` needs A+C; `25_final_pack.sas` needs C+U) — generated mechanically from
`python3 tools/diff_route.py neighborhood --corpus ankitha --json`'s own diff list once every
file's cause was confirmed against the store directly (not inferred from the pattern alone), so
no individual row hides a difference nobody looked at. None of the 288 is a Rust bug in
`neighborhood()`: the 10 clean files and the exact match on both of the brief's own worked
examples for a file unaffected by A/C/U (`07_enrich_fx.sas`) are the evidence for that claim, not
an assumption.

**Consequence for the brief's own pass marks.**
`enrich_fx_is_four_files_and_three_edges` (1 seed / 2 up / 1 down) passes exactly as specified —
`07_enrich_fx.sas` sits outside all three root causes. `branch_rollup_is_six_files_and_seven_edges`
does **not**: `11_branch_rollup.sas` is squarely inside root cause A (it reads `work.accounts`,
written only by the block that never folds), so the Rust answer is 5 nodes / 4 edges, not the
brief's 6 / 7 — the brief's numbers were confirmed live against `:8000` (the regex scanner, which
has no trouble with `a.*`), not against this store. `backend/api/tests/neighborhood.rs` asserts
the achievable 5/4 with a comment pointing here; getting to 6/7 needs A fixed in
`rust_rules_converter`, which this task was explicitly told not to touch.

## Task 5d note: all three root causes fixed — the 288 rows above are retired

Task 5d fixed all three `rust_rules_converter` fold gaps the Task 6 note named, in the order the
project's own rule requires (spec → generated Prolog DCG → hand-written Prolog codegen mirrors →
Rust, one commit each):

- **Root cause A (qualified star)** — `pipeline/specs/sas.py` gained `star(Alias)` (arity 1,
  overloading bare `star/0` the same way `col/1` vs `col/2` already does), resolved against
  whichever of FROM/JOIN carries that alias in `lineage.rs::select_lineage` (and its four sibling
  functions/Prolog mirrors).
- **Root cause C (`CROSS JOIN`)** — `join_clause` gained a third alternative, `cross_join(Src)`
  (arity 1, no `ON`). Every one of the eight consumers named in the Task 6 note (four Rust
  functions, four Prolog mirrors) now branches on the join term's own arity before indexing its
  `On` argument, instead of assuming arity 2.
- **Root cause U (`UNION ALL` under-reporting)** — a lineage-rule bug, not a grammar gap, exactly
  as the Task 5d brief predicted: `lineage::sas::run`'s `step` (and `sas_lineage.pl`'s own `step`)
  read `select_stmt`'s `cores` list as `.list()[0]` / `[Core|_]` — the first `UNION ALL` branch
  only. Fixed to walk every branch for its own reads/controls/col-lineage, while still taking the
  statement's output schema from the first branch only (real SQL semantics).

`python3 tools/diff_route.py neighborhood --corpus ankitha` now reports **0 diffs across all 25
files** — every one of the 288 rows above is retired, along with `enrich_fx_is_four_files_and_three_edges`'s
sibling pass mark `branch_rollup_is_six_files_and_seven_edges` (`backend/api/tests/neighborhood.rs`),
now asserting the brief's literal 6 nodes / 7 edges, unedited, and passing. Full accounting —
before/after fold and edge counts, the regression net after each commit, Prolog/Rust agreement —
in `.superpowers/sdd/silver_phase2_implementation_plan/task-5d-report.md`.

Two things found while fixing U were **not** fixed, being outside Task 5d's named scope (a
lineage-rule bug in `lineage::sas::run`/`sas_lineage.pl`, not the PySpark codegen path):
`emit.rs`/`emit_pretty.rs`/`sas_pyspark.pl`/`sas_pyspark_pretty.pl`'s own `sql_lines`/`select_stmt`
still render only the *first* `UNION ALL` branch's PySpark (a separate, pre-existing gap in the
codegen layer, silently dropping the same information the lineage layer used to); and
`case_expr` (`CASE WHEN...END`) has never had a `px`/`pe` rule in either PySpark emitter (present
since task 5b, confirmed pre-existing on the unmodified base commit via `13_risk_flags.sas`,
whose own `CASE` already failed to render before this task touched anything) — both caught by
`catch_unwind` at the API layer (`rust_inferred_duckdb::catch_emit`), so neither crashes ingestion,
they just leave that block's PySpark blank with a warning. Neither affects `ds_lineage`, so
neither affects `neighborhood()`, `edges()`, or any pass mark checked by `diff_route.py`.

## Task 7 note: `blocklinks()`'s 80 and `edges()`'s 84 divergences are two naming/shape
## differences, not a missing or extra fact anywhere

`python3 tools/diff_route.py blocklinks --corpus ankitha` and `… edges --corpus ankitha` were run
against all 25 `sas/raw/*.sas` files (one whole-corpus call each, `limit=10000` on `edges`) on
2026-09-10 with `:8000` up. Both report differences; **neither reports a flow one side has and the
other does not**, once the ids are set aside. That claim is not an impression — it is a
mechanical check, run over `diff_route.py --json`'s own output:

- **`blocklinks`: 40 missing + 40 extra, 0 anything else.** Strip the four id fields
  (`src_block`, `dst_block`, `src_ref`, `dst_ref`) from both multisets and they are *equal* —
  `(oracle - rust)` and `(rust - oracle)` are both empty. Same 40 links, same files, same tables,
  same direction.
- **`edges`: 42 missing + 41 extra + one `total`.** Strip `block_id` and the two multisets differ
  by exactly one row, in the oracle's favour, plus the `total` that row accounts for.

**Root cause B1 — block ids and refs are named differently, because they are made differently.**
`:8000` names a block `b_<n>_<hash8>` (`b_1_1a0b027b`) and numbers every table token it scanned
inside it (`b_1_1a0b027b:t_1`, `:t_2`, …, in order of appearance in the statement text). This
store's converter names blocks `b_001`, `b_002` by position (`blocks.block_id`,
`rust_rules_converter`), and has no per-token occurrence index at all — `node4` holds statements,
not table tokens. So `blocklinks()` refs are `"<block_id>:<table>"`: what the store can prove,
stable, and still satisfying the field's contract (one ref = one table occurrence in one block;
two links through different tables get different refs, which is what `elkLayout.ts` groups on).
Neither name is more correct than the other and neither is reachable from the other without
changing `rust_rules_converter`'s id scheme — explicitly out of scope for Task 7, and a change
that would ripple through every table in the store. Accounts for all 80 `blocklinks` rows and 82
of the 84 `edges` rows.

**Root cause B2 — `:8000` has a `FILE_FLOW` edge type; this store does not.** The one row Rust
does not produce is `sas/raw/04_build_accounts.sas`, `level=file`, `provenance=inferred`,
`work.accounts_raw -> work.accounts_raw` — a self-edge. Read against `:8000`'s own `lineage`
table it is not a self-edge at all: `source_ref_id` is `b_1_eab6f12f:t_1` and `target_ref_id` is
`b_2_66e46f94:t_1`, i.e. "block 1 of this file wrote `work.accounts_raw`, block 2 of the same file
read it" — an intra-file handoff, flattened to the table name on both sides because a `FILE_FLOW`
row is keyed by table, not by block. This store states the *same* handoff as its two `level=block`
rows, both of which are in the answer: `b_001` writes `work.accounts_raw` (the `data` step at
line 10) and `b_002` reads it (`from work.accounts_raw a`, line 28). No fact is lost; the shape
differs. Accounts for the one missing `edges` row and, arithmetically, for `total` 83 vs 82.

**What this does *not* cover, and why that is safe.** `diff_route.py`'s `edges` call passes no
`filter` and no `level`, so neither is checked against `:8000`. Both are implemented as
`service.py::_edges_where` states them (case-insensitive substring over `src`/`dst`/`table_name`;
exact match on `level`) and are covered by `routes::edges`'s own unit tests, not by this tool — the
same position `search()`'s non-empty `q` is in (Task 5 note above).

**The `human_gold` row is not a divergence: both sides merge the same edit.** `edges()`'s pass
mark needs one `human_gold` row, which `:8000` gets from its own `human_edits` table. This store
had no such table; Task 7 added it to `schema.rs` (additive, nothing that converts a folder writes
there) and copied that table's rows across verbatim — **1 row**, an `action='correct'`,
`level='project'` assertion by `web-ui` on 2026-08-25 that `09_customer_summary.sas` feeds
`18_dashboard_mart.sas` through `work.cust_summary`. It is in
`backend/api/tests/fixtures/human_edits.json` (loaded by `lineageq_api::test_state`) and in the
dev store on :8110. Its `src`/`dst` still carry pre-Task-5 `ankitha_1/` fileids: that is what the
row says on *both* sides, so both answers carry it identically and it produces no diff. Rewriting
it for tidiness would have created one.

## Task 12 note: `run()` is landed against a receipt, not an oracle — and what the 11/11 rests on

**Why there is no oracle row for `run`.** Neither Python server answers this question. `:8000`
knows nothing about executing anything, and the Bench's `/api/run_block` is not a shape
`diff_route.py` can line up field for field — it returns whole CSV tables per side, keyed by
table, with the block's SAS and PySpark text attached. `tools/diff_route.py` therefore keeps
`run` as `no_oracle` (its own brief's wording, unchanged by Task 12). What replaces the oracle is
a **known-good receipt**: `raw/bench_stack/server/bench_receipt.py` on
`corpus/fixtures/test_vishnu_testdata_fixed.sas` said 11/11 blocks match, both engines, on
2026-09-09. Reproduced on 2026-09-10 before any code was written (M3b step 0), then reproduced
again through `POST /api/run`.

**Measured 2026-09-10, `POST /api/run` on `:8113` over a store built from `corpus/team_finance`
plus `corpus/fixtures`:** `b_002`…`b_012`, all eleven `match` with `engine: rust` (left 1.2–2.0 ms,
right 4327–4602 ms) and all eleven `match` with `engine: prolog` (left 25.6–43.9 ms, right
4310–4852 ms). 22 `runs` rows, 22 `run_tables` rows, 0 `run_samples` rows — nothing differed, so
there was nothing to sample.

**The one thing the 11/11 does *not* prove, and the reader should know it.**
`raw/bench_stack/loops/gen_block_testdata.py` — the Z3 row generator both the receipt and this
route shell out to (Decision D1) — **cannot regenerate this fixture's inputs today**. Its
`Schemas.core_cols` unpacks a SELECT projection as `e, a = targs(p)`, and the SAS pyDSL has
emitted `proj(Expr, Alias, Length)` — three arguments — since commit `4bc57dc` (Task 5b, the
CASE/LENGTH/JOIN wave). Every run since then, the receipt's included, has been reusing the
`out/api/<stem>/blocks/` tree that was generated *before* that change; `bench_api._ensure_blocks`
caches on `manifest.json` existing and never checks the generator's exit code, so the staleness
has been silent. It surfaced here only because `run()`'s first end-to-end test ran with that
cache deleted.

The rows themselves are still good rows — they are inputs, not expectations (Decision D9), and
both engines read the same ones — so the 11/11 verdict is a real comparison of two independent
implementations. But it is a comparison on **inputs generated from an older node/4**, and a new
file, or this file after a spec change, cannot get inputs at all until the generator is fixed.
The fix is one line, measured: `e, a = targs(p)` → take the first two of `targs(p)`, after which
the generator produces all 11 blocks from today's node/4 (probed at
`raw/bench_stack/out/gen_block_testdata_probe.py`, a gitignored copy — M3b's write scope
excludes `raw/bench_stack/`, so the fix was proved and left for the owner rather than applied).

> **RESOLVED 2026-09-10 by M4a (plan Part J, J1).** The one line is applied
> (`_pa = targs(p); e, a = _pa[0], _pa[1]`, which takes `proj/2` and `proj/3` alike) and
> `_ensure_blocks` now raises on a non-zero exit from either child and removes the partial
> `blocks/` tree, so a failed generation can never be cached as a complete one again. The
> fixture's `blocks/` tree was deleted and regenerated from today's node/4 (generator exit 0,
> manifest 2026-09-10 15:00:07, 11 block input sets) and everything above was re-measured on
> those fresh rows: `bench_receipt.py --engine both` 11/11 rust and 11/11 prolog;
> `tools/xcheck_datamatch.py` 11/11 identical on both legs; `POST /api/run` on `:8116`
> 11/11 `match` with `engine: rust` and 11/11 with `engine: prolog`. **No verdict changed.**
> The paragraph above stands as the record of what the 09-09 and M3b receipts actually rested
> on; from 2026-09-10 the 11/11 rests on inputs generated from the node/4 in the tree.

**Finding I5 is handled, not fixed.** The four team_finance files the Rust emitter still panics on
come back as a structured answer, not a 500: measured 2026-09-10, `sas/raw/07_enrich_fx.sas`
returns HTTP 200 with `match: "error"`, `message: "emit PySpark for 07_enrich_fx: LINEAGEQ: no
PySpark mapping for SAS function coalesce"`, and `sas/raw/14_large_txn_report.sas` likewise with
`not a list: orderby(col(t,amt_usd_sum),some(desc))`. A block that creates no table (`b_001`, the
LIBNAME) answers `match: "no inputs"`. Neither hangs; every child process carries a 300 s deadline.

---

## Task 6b note: `convert()` lands as new surface — the one honest reason a route may land undiffed

**Why there is no oracle row for `convert`.** Neither Python server answers this question in this
shape. `:8000` has no convert route at all — its store was filled by a separate indexer. The
Bench's `:8042 /api/convert` converts **one open file for its own editor** and returns that file's
cells; this one walks a folder, writes eight tables and returns a `ConvertReport`. There is no
field-for-field alignment for `diff_route.py` to make, so `convert` keeps its brief's own wording
(silver plan, Task 6b step 5): **`no oracle — new surface`**. That is the only reason in this
ledger that lets a route land without a differential, and it applies to exactly two rows,
`convert` and `run`.

**What stands in for the oracle.** The plan's own idempotence test, plus its guard:

- `backend/api/tests/convert.rs::convert_is_idempotent_over_http` — first convert of a folder
  `ok: 1`, `blocks > 0`; second convert of the *unchanged* folder `blocks: 0`.
- `::a_changed_file_is_reconverted` — the guard that keeps the line above from being satisfied by
  a `convert` that writes nothing at all: change the file's bytes and the blocks come back.
- `::a_single_file_converts_too`, `::the_report_has_every_field_the_plan_names`,
  `::a_request_with_no_target_is_a_400`, `::a_missing_path_is_a_404`,
  `::convert_is_landed_and_no_longer_forwarded` — seven tests, all green.

**Measured over HTTP, 2026-09-10, `:8116` on an empty store, `GET /api/files` polled every 20 ms
for the whole call** (the point of the measurement is what a *read* sees while a convert runs):

| convert | files | blocks | lock held | worst concurrent read | reads failed |
|---|---:|---:|---:|---:|---:|
| `corpus/team_finance` (first) | 25 | 26 | 106.5 ms | 81.3 ms | 0 |
| `corpus/team_finance` (again, unchanged) | 25 | 0 | 5.2 ms | 1.1 ms | 0 |
| `corpus/perf/big_2000.sas` (first) | 1 | 2000 | 2353.1 ms | 2328.4 ms | 0 |
| `corpus/perf/big_2000.sas` (again, unchanged) | 1 | 0 | 1.3 ms | 1.3 ms | 0 |

The handler takes the store mutex for the whole call, so those worst-read numbers are the cost of
the spec's one-connection choice, stated rather than hidden: **2.3 s of blocked reads on a
2000-block file**. Nothing failed — reads wait. The report carries `lock_ms` so the number is
visible to any caller, not only to whoever runs this table again.

**No stream.** Plan §6 says `convert()` "streams `block ready` events"; nothing in this slice
consumes them (the spec's own OPEN item), so the route answers synchronously rather than shipping
an SSE channel with no reader (Task 6b step 3).

