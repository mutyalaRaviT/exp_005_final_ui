# tools/tests/test_diff_route.py — the failing-then-passing tests for the differential oracle
#
# Why: `tools/diff_route.py` is what decides whether a route may "land" (Task 4 brief). Its
# three building blocks — diff_json, load_accepted, filter_accepted — are unit-tested here in
# isolation from any network call, so the tool's correctness does not depend on the two Python
# oracles or the Rust API being up. The CLI's live behaviour (oracles reachable/unreachable,
# real corpus runs) is exercised by hand and recorded in the Task 4 report, not here — this
# suite is the part that must be true regardless of what is or is not running on :8000/:8042/:8110.
import os
import tempfile

from tools.diff_route import diff_json, load_accepted, filter_accepted


def test_identical_payloads_have_no_differences():
    assert diff_json({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]}) == []


def test_a_changed_leaf_is_reported_with_its_path():
    d = diff_json({"nodes": [{"id": "x", "role": "up"}]},
                   {"nodes": [{"id": "x", "role": "down"}]})
    assert d == [("nodes[0].role", "up", "down")]


def test_list_order_does_not_matter_for_edges():
    a = {"edges": [{"src": "p", "dst": "q"}, {"src": "r", "dst": "s"}]}
    b = {"edges": [{"src": "r", "dst": "s"}, {"src": "p", "dst": "q"}]}
    assert diff_json(a, b, unordered={"edges"}) == []


def _ledger_fixture():
    """A throwaway ledger file with exactly one accepted divergence, in the same markdown
    shape `bronze_phase2_route_ledger.md` uses: a `## Accepted divergences` table keyed
    `question | fileid | json_path`. Returns the path; the caller does not need to clean it
    up (tempfile module cleans the directory at interpreter exit, and each call gets a fresh
    file)."""
    text = """# bronze_phase2_route_ledger — which routes have landed

| question | landed | corpus clean | accepted divergences |
|---|---|---|---|
| neighborhood | no | no | 1 |

## Accepted divergences

| question | fileid | json_path | why the parser is right |
|---|---|---|---|
| neighborhood | f.sas | nodes[0].score | the parser sees a flow the regex scanner missed |
"""
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


def test_an_accepted_divergence_is_not_a_failure():
    acc = load_accepted(_ledger_fixture())     # one row: neighborhood | f.sas | nodes[0].score
    d = [("nodes[0].score", 0, 3)]
    assert filter_accepted(d, acc, "neighborhood", "f.sas") == []


def test_an_accepted_divergence_for_a_different_file_still_fails():
    # the same json_path, accepted for f.sas, must NOT swallow a difference in g.sas — an
    # accepted divergence is keyed by (question, fileid, json_path), not by json_path alone.
    acc = load_accepted(_ledger_fixture())
    d = [("nodes[0].score", 0, 3)]
    assert filter_accepted(d, acc, "neighborhood", "g.sas") == d


def test_an_accepted_divergence_for_a_different_question_still_fails():
    acc = load_accepted(_ledger_fixture())
    d = [("nodes[0].score", 0, 3)]
    assert filter_accepted(d, acc, "edges", "f.sas") == d


def test_load_accepted_on_the_real_ledger_seeded_by_this_task_is_empty():
    # Task 4 seeds the real ledger with zero accepted rows — no route has landed yet, so
    # nothing has been classified. This guards against the parser silently swallowing rows
    # it should not (e.g. matching the table header as a data row).
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ledger = os.path.join(here, "docs", "plan", "bronze", "bronze_phase2_route_ledger.md")
    assert load_accepted(ledger) == set()


def test_a_missing_key_on_either_side_is_reported():
    d = diff_json({"a": 1}, {"a": 1, "b": 2})
    assert d == [("b", None, 2)]
    d = diff_json({"a": 1, "b": 2}, {"a": 1})
    assert d == [("b", 2, None)]


def test_unordered_list_reports_missing_and_extra_when_sets_differ():
    a = {"edges": [{"src": "p", "dst": "q"}]}
    b = {"edges": [{"src": "p", "dst": "q"}, {"src": "r", "dst": "s"}]}
    d = diff_json(a, b, unordered={"edges"})
    assert d == [("edges[extra]", None, '{"dst": "s", "src": "r"}')]


def test_root_level_list_diffs_by_index():
    d = diff_json([{"id": "a"}], [{"id": "b"}])
    assert d == [("[0].id", "a", "b")]
