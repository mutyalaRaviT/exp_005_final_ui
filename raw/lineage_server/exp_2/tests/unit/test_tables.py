from sas_lineage.tables import parse_table_list, parse_table_ref


def test_plain_ref():
    ref, end = parse_table_ref("raw.customer")
    assert ref.name == "raw.customer"
    assert end == 12


def test_ref_with_options():
    ref, _ = parse_table_ref("raw.customer(keep=id name)")
    assert ref.name == "raw.customer"
    assert ref.raw == "raw.customer(keep=id name)"


def test_ref_with_nested_where_options():
    text = 'raw.customer(where=(status="A" and region in ("IN", "US")) rename=(id=cid))'
    ref, end = parse_table_ref(text)
    assert ref.name == "raw.customer"
    assert end == len(text)


def test_ref_with_multiline_options():
    ref, _ = parse_table_ref("raw.customer(\n    keep=id name\n)")
    assert ref.name == "raw.customer"


def test_table_list_mixed():
    refs, unresolved = parse_table_list(
        "raw.a(keep=id amount)\n raw.b(rename=(amt=amount)\n where=(status=\"A\"))"
    )
    assert [r.name for r in refs] == ["raw.a", "raw.b"]
    assert unresolved == []


def test_table_list_unresolved_fragment():
    refs, unresolved = parse_table_list("raw.a &badmacro")
    assert [r.name for r in refs] == ["raw.a"]
    assert unresolved == ["&badmacro"]
