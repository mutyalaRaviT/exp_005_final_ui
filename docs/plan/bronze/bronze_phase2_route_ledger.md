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
| convert | no | — | — |
| blocklinks | yes | yes (80 accepted, 1 root cause — Task 7 note) | 80 |
| edges | yes | yes (84 accepted, 2 root causes — Task 7 note) | 84 |
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

164 rows: `blocklinks` 80, `edges` 84 — all of them Task 7's, all of them traced to the two
root causes in the Task 7 note below. `neighborhood` carried 288 rows here (Task 6, three `rust_rules_converter` fold gaps —
qualified star, `CROSS JOIN`, `UNION ALL` under-reporting) until Task 5d fixed all three; see the
"Task 5d note" below. `files`/`search` have run clean by construction since Task 5 (0 diffs
found) and never needed a row.

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
