import pytest

from src.server.loader.lua import parse_lua_table


def test_keyed_and_nested_tables():
    assert parse_lua_table('return { ["a"] = 1, ["b"] = { ["c"] = "x" }, d = 2.5 }') == {"a": 1, "b": {"c": "x"}, "d": 2.5}


@pytest.mark.parametrize("table", ['{"x", "y"}', '{[1] = "x", [2] = "y"}', '{"x"; "y";}'])
def test_tables_keyed_one_to_n_are_lists(table):
    assert parse_lua_table(f"return {table}") == ["x", "y"]


def test_comments_are_skipped():
    text = '-- <pre>\nreturn {\n  ["range"] = 175,--see his passive\n  --["aram"] = { this is pointless\n}\n-- </pre>'

    assert parse_lua_table(text) == {"range": 175}


def test_strings_numbers_and_words():
    text = r'return { "Kai\'Sa", "say \"hi\"", -0.1090625, 1e3, true, false }'

    assert parse_lua_table(text) == ["Kai'Sa", 'say "hi"', -0.1090625, 1000.0, True, False]


def test_arithmetic():
    # Kled's HP per level in the wiki module.
    assert parse_lua_table("return { 84+1000/17, 2*(3-1), -2-1 }") == [pytest.approx(142.8235, abs=1e-4), 4, -3]


def test_broken_lua_is_an_error_not_a_guess():
    with pytest.raises(ValueError):
        parse_lua_table('return { ["a"] = @ }')
