from pathlib import Path

from sas_lineage.pipeline import analyze_file, analyze_source

EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"


def test_include_inlines_file(tmp_path):
    (tmp_path / "setup.sas").write_text("%let lib = raw;\nlibname raw '/d/raw';")
    main = tmp_path / "main.sas"
    main.write_text("%include 'setup.sas';\ndata work.x;\n set &lib..y;\nrun;")
    analysis = analyze_file(main, registry_path=None)
    assert analysis.includes == [str(tmp_path / "setup.sas")]
    assert analysis.missing_includes == []
    assert [o.name for o in analysis.blocks[0].reads] == ["raw.y"]
    assert analysis.libnames == {"raw": "/d/raw"}


def test_include_nested(tmp_path):
    (tmp_path / "inner.sas").write_text("%let lib = raw;")
    (tmp_path / "outer.sas").write_text("%include 'inner.sas';")
    main = tmp_path / "main.sas"
    main.write_text("%include 'outer.sas';\ndata w.x;\n set &lib..t;\nrun;")
    analysis = analyze_file(main, registry_path=None)
    assert len(analysis.includes) == 2
    assert analysis.blocks[0].status == "PARSED"


def test_missing_include_is_recorded_not_silent(tmp_path):
    main = tmp_path / "main.sas"
    main.write_text("%include 'nowhere.sas';\ndata w.x;\n set raw.y;\nrun;")
    analysis = analyze_file(main, registry_path=None)
    assert analysis.missing_includes == ["nowhere.sas"]
    assert analysis.blocks[0].status == "PARSED"  # rest still analyzed


def test_include_without_base_dir_is_missing():
    analysis = analyze_source("%include 'setup.sas';\ndata w.x;\n set r.y;\nrun;")
    assert analysis.missing_includes == ["setup.sas"]


def test_included_macro_used_with_annotated_def_id(tmp_path):
    analysis = analyze_file(EXAMPLES / "ex12_include_main.sas",
                            registry_path=None)
    assert analysis.includes == [str(EXAMPLES / "inc_common_setup.sas")]
    ids = [b.block_id for b in analysis.blocks]
    # the macro instance uses the DEFINITION's injected id from the include
    assert ids == ["1:9990005556667778", "2:4564564564564564#1"]
    assert analysis.let_vars["cutoff"] == "2026"
    assert analysis.libnames == {
        "raw": "/data/landing/raw", "mart": "/data/warehouse/mart",
    }
    assert analysis.macro_calls[0].call_block_id == "2:1010106667778889"
