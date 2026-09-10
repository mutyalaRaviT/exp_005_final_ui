# corpus/fixtures — files that pin a pass mark

**Why this folder exists.** `test_vishnu_testdata_fixed.sas` is the exp_42 receipt file: 23 blocks,
80 statements, folded 80/80, round trip 80/80, 12 table edges, 11 runnable blocks that match on
Spark. Tasks 9, 10, 12 and 13 assert those numbers. Task 5 (2026-09-09) deleted the folders it used
to live in; this is its home now. Like `perf/`, it is a fixture, not a corpus anyone browses.

**Inputs → outputs.** the file → `diff_route.py --corpus exp42`, `backend/api` tests, the Bench oracle on :8042.
