from pathlib import Path

import indexer
from sas_lineage.store import LineageStore


def make_repo(tmp_path):
    (tmp_path / "a.sas").write_text("data work.customers; run;")
    (tmp_path / "b.sas").write_text("data work.orders; set work.customers; run;")
    return tmp_path


def test_build_and_hash_skip(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    store = LineageStore(tmp_path / "db.duckdb")
    ix = indexer.Indexer(store, [root])
    s1 = ix.build()
    assert s1["files_indexed"] == 2
    assert ix.files_mentioning("work.customers")
    calls = []
    monkeypatch.setattr(ix, "_cheap_scan",
                        lambda p: calls.append(p) or set())
    s2 = ix.build()
    assert s2["files_indexed"] == 0 and calls == []


def test_reindex_only_changed(tmp_path):
    root = make_repo(tmp_path)
    store = LineageStore(tmp_path / "db.duckdb")
    ix = indexer.Indexer(store, [root]); ix.build()
    (root / "a.sas").write_text("data work.customers work.extra; run;")
    assert ix.build()["files_indexed"] == 1
    assert ix.files_mentioning("work.extra")


def test_suggest_prefix(tmp_path):
    root = make_repo(tmp_path)
    ix = indexer.Indexer(LineageStore(tmp_path / "db.duckdb"), [root]); ix.build()
    hits = ix.suggest("work.cust")
    assert any(h["kind"] == "table" and h["value"] == "work.customers"
               for h in hits)


def test_files_mentioning_returns_both(tmp_path):
    root = make_repo(tmp_path)
    store = LineageStore(tmp_path / "db.duckdb")
    ix = indexer.Indexer(store, [root])
    ix.build()
    fileids = ix.files_mentioning("work.customers")
    names = {f.rsplit("/", 1)[-1] for f in fileids}
    assert len(fileids) == 2
    assert names == {"a.sas", "b.sas"}


def test_fileid_is_the_path_relative_to_the_root(tmp_path):
    root = tmp_path / "repo"
    (root / "etl" / "load").mkdir(parents=True)
    (root / "etl" / "load" / "deep.sas").write_text("data work.deep; run;")
    store = LineageStore(tmp_path / "db.duckdb")
    ix = indexer.Indexer(store, [root])
    ix.build()
    assert ix.files_mentioning("work.deep") == ["etl/load/deep.sas"]
    # fileid and folder_path are cut from the same root
    assert store.con.execute(
        "SELECT folder_path FROM files WHERE fileid = ?",
        ["etl/load/deep.sas"]).fetchone() == ("etl/load",)


def test_fileid_survives_an_edit_and_only_the_hash_moves(tmp_path):
    root = make_repo(tmp_path)
    store = LineageStore(tmp_path / "db.duckdb")
    ix = indexer.Indexer(store, [root])
    ix.build()
    before = dict(store.con.execute(
        "SELECT fileid, sashashcode FROM files").fetchall())

    (root / "a.sas").write_text("data work.customers work.extra; run;")
    assert ix.build()["files_indexed"] == 1
    after = dict(store.con.execute(
        "SELECT fileid, sashashcode FROM files").fetchall())

    assert sorted(after) == sorted(before)          # ids unchanged
    fileid = f"{root.name}/a.sas"
    assert after[fileid] != before[fileid]          # content hash moved
    assert after[f"{root.name}/b.sas"] == before[f"{root.name}/b.sas"]
    assert len(after) == 2                          # no orphan row left behind


def test_automaton_knows_new_term_after_rebuild(tmp_path):
    root = make_repo(tmp_path)
    store = LineageStore(tmp_path / "db.duckdb")
    ix = indexer.Indexer(store, [root])
    ix.build()
    assert ix.automaton.get("work.brandnew", None) is None
    (root / "c.sas").write_text("data work.brandnew; run;")
    ix.build()
    assert ix.automaton.get("work.brandnew", None) == "work.brandnew"
    matches = list(ix.automaton.iter("prefix work.brandnew suffix"))
    assert any(value == "work.brandnew" for _end, value in matches)


# ---- UX round 2: suggest ranking --------------------------------------------

def _rank_repo(tmp_path):
    """Real tables next to the alias noise a cheap `x.y` scan picks up:
    `c.cust_id` / `a.cust_id` are SQL-alias column refs, not tables."""
    (tmp_path / "one.sas").write_text(
        "proc sql; create table work.cust_summary as "
        "select c.cust_id, a.cust_id from work.customers c "
        "left join work.accounts a on c.cust_id = a.cust_id; quit;")
    (tmp_path / "two.sas").write_text(
        "data work.cust_flags; set work.cust_summary; run;")
    return tmp_path


def test_suggest_ranks_real_tables_over_alias_columns(tmp_path):
    root = _rank_repo(tmp_path)
    ix = indexer.Indexer(LineageStore(tmp_path / "db.duckdb"), [root])
    ix.build()
    hits = ix.suggest("cust")
    values = [h["value"] for h in hits]
    # every real work.* table sorts above every single-letter alias ref
    aliasy = [v for v in values if v.split(".", 1)[0] in ("a", "c")]
    real = [v for v in values if v.startswith("work.")]
    assert real and aliasy
    assert max(values.index(v) for v in real) < min(
        values.index(v) for v in aliasy)


def test_suggest_puts_exact_match_first(tmp_path):
    root = _rank_repo(tmp_path)
    ix = indexer.Indexer(LineageStore(tmp_path / "db.duckdb"), [root])
    ix.build()
    hits = ix.suggest("work.cust_summary")
    assert hits[0]["value"] == "work.cust_summary"


def test_suggest_prefers_the_better_connected_table(tmp_path):
    root = _rank_repo(tmp_path)
    ix = indexer.Indexer(LineageStore(tmp_path / "db.duckdb"), [root])
    ix.build()
    hits = ix.suggest("cust")
    values = [h["value"] for h in hits]
    # cust_summary is mentioned in two files, cust_flags in one
    assert values.index("work.cust_summary") < values.index("work.cust_flags")
