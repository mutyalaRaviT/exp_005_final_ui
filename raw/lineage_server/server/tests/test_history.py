"""EstateHistory — the pure-python (dulwich) shadow repo behind code saves.

Every save is a git commit: author = the editor, message = the reason,
author_time = when. The edge timeline is a line-diff of the file's
`.edges.jsonl` between a commit and its parent.
"""
from history import EstateHistory

E1 = {"src": "work.a", "dst": "work.b", "table_name": "work.a",
      "level": "block", "block_id": "b_1_aaaa1111"}
E2 = {"src": "work.a2", "dst": "work.b", "table_name": "work.a2",
      "level": "block", "block_id": "b_1_bbbb2222"}


def test_record_then_history_newest_first_with_edge_delta(tmp_path):
    h = EstateHistory(tmp_path / "hist")
    assert h.has_file("repo/a.sas") is False

    c1 = h.record("repo/a.sas", "data b; set a; run;", [E1],
                  "engine", "original import")
    assert h.has_file("repo/a.sas") is True

    c2 = h.record("repo/a.sas", "data b; set a2; run;", [E2],
                  "ravi", "swapped the source table")

    hist = h.history("repo/a.sas")
    assert [e["commit"] for e in hist] == [c2, c1]
    assert hist[0]["editor"] == "ravi"
    assert hist[0]["reason"] == "swapped the source table"
    assert hist[0]["added"] == [E2]
    assert hist[0]["removed"] == [E1]
    # the seed commit: everything is new, nothing removed
    assert hist[1]["editor"] == "engine"
    assert hist[1]["added"] == [E1]
    assert hist[1]["removed"] == []
    # saved_at is an ISO timestamp string
    assert "T" in hist[0]["saved_at"]


def test_at_returns_that_versions_code_and_edges(tmp_path):
    h = EstateHistory(tmp_path / "hist")
    c1 = h.record("repo/a.sas", "data b; set a; run;", [E1], "engine",
                  "original import")
    h.record("repo/a.sas", "data b; set a2; run;", [E2], "ravi", "swap")

    old = h.at("repo/a.sas", c1)
    assert old["code"] == "data b; set a; run;"
    assert old["edges"] == [E1]


def test_files_do_not_interleave(tmp_path):
    h = EstateHistory(tmp_path / "hist")
    h.record("repo/a.sas", "data b; set a; run;", [E1], "engine", "import a")
    h.record("repo/deep/c.sas", "data d; set c; run;", [E2], "engine",
             "import c")
    assert len(h.history("repo/a.sas")) == 1
    assert len(h.history("repo/deep/c.sas")) == 1
    assert h.history("repo/missing.sas") == []


def test_relative_repo_dir_is_resolved(tmp_path, monkeypatch):
    # the server passes a path derived from a RELATIVE $SAS_DB; dulwich
    # rejects add() paths that don't resolve inside the repo, so the repo
    # dir must be absolutized up front
    monkeypatch.chdir(tmp_path)
    h = EstateHistory("rel_hist_dir")
    c1 = h.record("repo/a.sas", "data b; set a; run;", [E1], "engine",
                  "original import")
    assert c1
    assert h.history("repo/a.sas")[0]["editor"] == "engine"
