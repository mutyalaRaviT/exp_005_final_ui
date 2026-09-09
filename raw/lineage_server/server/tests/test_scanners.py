from pathlib import Path
import scanners

def make_tree(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.sas").write_text("data work.customers; run;")
    (tmp_path / "sub" / "b.sas").write_text("set WORK.CUSTOMERS;")
    (tmp_path / "c.sas").write_text("no match here")
    (tmp_path / "d.txt").write_text("work.customers")   # wrong extension
    return tmp_path

def test_python_scanner_case_insensitive_sas_only(tmp_path):
    make_tree(tmp_path)
    hits = scanners._scan_python("work.customers", [tmp_path])
    assert {p.name for p in hits} == {"a.sas", "b.sas"}

def test_rg_and_python_parity(tmp_path):
    make_tree(tmp_path)
    if scanners.active_scanner() != "rg":
        import pytest; pytest.skip("rg not installed")
    assert scanners._scan_rg("work.customers", [tmp_path]) == \
           scanners._scan_python("work.customers", [tmp_path])

def test_fallback_when_rg_absent(tmp_path, monkeypatch):
    make_tree(tmp_path)
    monkeypatch.setattr(scanners.shutil, "which", lambda _: None)
    assert scanners.active_scanner() == "python"
    hits = scanners.scan_term("work.customers", [tmp_path])
    assert {p.name for p in hits} == {"a.sas", "b.sas"}

def test_term_is_literal_not_regex(tmp_path):
    (tmp_path / "e.sas").write_text("workXcustomers")
    hits = scanners.scan_term("work.customers", [tmp_path])
    assert not hits   # '.' must not match 'X'


def test_active_scanner_prefers_duckdb_over_python(monkeypatch):
    monkeypatch.setattr("scanners.shutil.which", lambda _: None)
    assert scanners.active_scanner() == "python"          # default: no store
    assert scanners.active_scanner(store_ready=False) == "python"
    assert scanners.active_scanner(store_ready=True) == "duckdb"


def test_rg_beats_duckdb(monkeypatch):
    monkeypatch.setattr("scanners.shutil.which", lambda _: "/usr/bin/rg")
    assert scanners.active_scanner(store_ready=True) == "rg"
