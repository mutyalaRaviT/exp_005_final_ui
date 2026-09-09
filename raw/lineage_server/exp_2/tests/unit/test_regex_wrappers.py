from sas_lineage.regex_wrappers import (
    is_keyword,
    match_identifier,
    match_table_name,
    strip_keyword,
)


def test_match_identifier():
    assert match_identifier("customer_1 rest") == ("customer_1", 10)
    assert match_identifier("1bad") is None


def test_match_table_name_two_level():
    assert match_table_name("raw.customer(keep=id)") == ("raw.customer", 12)
    assert match_table_name("work") == ("work", 4)


def test_is_keyword_case_insensitive_word_bounded():
    assert is_keyword("DATA work.x", "data")
    assert is_keyword("  set a", "set")
    assert not is_keyword("dataset a", "data")
    assert not is_keyword("x = 1", "set")


def test_strip_keyword():
    assert strip_keyword("set raw.a raw.b", "set") == "raw.a raw.b"
    assert strip_keyword("x = 1", "set") is None
