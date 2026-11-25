from unittest.mock import Mock

import pytest

import src.server.loader.names as names
from src.server.loader.names import (DDragonName, NameDictionary, ddragon_notes, load_name_dictionaries,
                                     parse_item_data, parse_page_titles, same_title_but_case)


class FakeSession:
    """Answers like SafeSession: the JSON of the first matching URL part, "" for everything else (a 404)."""

    def __init__(self, responses: dict[str, dict | list]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def get_json(self, url: str) -> dict | list | str:
        self.urls.append(url)
        return next((data for part, data in self.responses.items() if part in url), "")


@pytest.fixture(autouse=True)
def logger(monkeypatch) -> Mock:
    mock = Mock()
    monkeypatch.setattr(names, "patch_logger", mock)
    return mock


def warnings(logger: Mock) -> list[str]:
    return [call.args[0] for call in logger.warning.call_args_list]


NUNU = DDragonName("Nunu", "Nunu & Willump")
JACK = DDragonName("8010", "Jack Of All Trades")


class TestNameDictionary():

    def test_wiki_name_falls_back_to_the_given_name(self):
        dictionary = NameDictionary({"Nunu": "Nunu"}, [NUNU])

        assert dictionary.wiki_name("Nunu", "Nunu & Willump") == "Nunu"
        assert dictionary.wiki_name("Unknown", "Unknown Name") == "Unknown Name"


    @pytest.mark.parametrize("name", ["Nunu", "nunu", "Nunu & Willump", "NUNU & WILLUMP"])
    def test_finds_data_dragons_name_by_wiki_name_id_or_own_name(self, name):
        assert NameDictionary({"Nunu": "Nunu"}, [NUNU]).ddragon_name(name) == "Nunu & Willump"


    def test_a_real_name_wins_over_another_entrys_alias(self):
        dictionary = NameDictionary({"1": "Sheen"}, [DDragonName("1", "Old Sheen"), DDragonName("2", "Sheen")])

        assert dictionary.ddragon_name("Sheen") == "Sheen"


    def test_unknown_name_is_none(self):
        assert NameDictionary().ddragon_name("Nobody") is None


class TestParsing():

    def test_page_titles_follow_normalization_and_redirects(self):
        response = {"query": {
            "normalized": [{"from": "nunu & Willump", "to": "Nunu & Willump"}],
            "redirects": [{"from": "Nunu & Willump", "to": "Nunu"}, {"from": "Kalista's Black Spear", "to": "LoR:Kalista"}],
            "pages": [{"ns": 0, "title": "Nunu"}, {"ns": 0, "title": "Flash"}, {"ns": 3000, "title": "LoR:Kalista"},
                      {"ns": 0, "title": "Jack Of All Trades", "missing": True}],
        }}

        titles = parse_page_titles(response, ["nunu & Willump", "Flash", "Kalista's Black Spear", "Jack Of All Trades"])

        assert titles == {"nunu & Willump": "Nunu", "Flash": "Flash", "Kalista's Black Spear": None,
                          "Jack Of All Trades": None}


    def test_search_hit_only_counts_when_it_differs_in_case(self):
        assert same_title_but_case(["Jack Of All Trades", ["Jack of All Trades"]], "Jack Of All Trades") == "Jack of All Trades"
        assert same_title_but_case(["Anti-tower Socks", ["Siege minion"]], "Anti-tower Socks") is None
        assert same_title_but_case("", "Anything") is None


    def test_item_data_maps_ids_to_wiki_names(self):
        text = 'return {\n["Blade of the Ruined King"] = {["id"] = 3153},\n["No Id"] = {["tier"] = 1},\n}'

        assert parse_item_data(text) == {"3153": "Blade of the Ruined King"}


class TestLoadNameDictionaries():

    @pytest.fixture
    def session(self) -> FakeSession:
        item_data = 'return {\n["Crystalline Overgrowth"] = {["id"] = 1524},\n}'
        return FakeSession({
            "Module%3AItemData": {"query": {"pages": [{"revisions": [{"slots": {"main": {"content": item_data}}}]}]}},
            "action=query": {"query": {
                "redirects": [{"from": "Nunu & Willump", "to": "Nunu"}],
                "pages": [{"ns": 0, "title": "Nunu"}, {"ns": 0, "title": "Flash"},
                          {"ns": 0, "title": "Jack Of All Trades", "missing": True},
                          {"ns": 0, "title": "Gangplank Placeholder", "missing": True}],
            }},
            "search=Jack": ["Jack Of All Trades", ["Jack of All Trades"]],
            "search=Gangplank": ["Gangplank Placeholder", ["Gangplank"]],
        })


    @pytest.mark.asyncio
    async def test_each_source_resolves_its_cases(self, session):
        result = await load_name_dictionaries(session, {
            "champions": [NUNU],
            "items": [DDragonName("1524", "Overgrowth"), DDragonName("7050", "Gangplank Placeholder")],
            "runes": [JACK],
            "summonerspells": [DDragonName("SummonerFlash", "Flash")],
        }, {"summonerspells": {"SummonerFlash": "Flash (Summoner Spell)"}})

        assert result["champions"].wiki_name("Nunu", "") == "Nunu"
        assert result["items"].wiki_name("1524", "") == "Crystalline Overgrowth"
        assert result["items"].wiki_name("7050", "") == "Gangplank Placeholder"
        assert result["runes"].wiki_name("8010", "") == "Jack of All Trades"
        assert result["summonerspells"].wiki_name("SummonerFlash", "") == "Flash (Summoner Spell)"


    @pytest.mark.asyncio
    async def test_unresolved_names_are_a_warning(self, session, logger):
        await load_name_dictionaries(session, {"items": [DDragonName("7050", "Gangplank Placeholder")]}, {})

        assert warnings(logger) == ["[ITEM] [NAMES] [Gangplank Placeholder] No wiki page found, Data Dragon's name is used"]


    @pytest.mark.asyncio
    async def test_known_names_need_no_title_query(self, session):
        await load_name_dictionaries(session, {"items": [DDragonName("1524", "Overgrowth")]}, {})

        assert len(session.urls) == 1  # only Module:ItemData


class TestDDragonNotes():

    def test_names_become_data_dragons(self):
        notes = {"champions": {"new": [], "changed": {"Nunu": {"Q": []}}, "deleted": []},
                 "runes": {"new": ["Jack of All Trades"], "changed": {}, "deleted": []}}
        dictionaries = {"champions": NameDictionary({"Nunu": "Nunu"}, [NUNU]),
                        "runes": NameDictionary({"8010": "Jack of All Trades"}, [JACK])}

        result = ddragon_notes(notes, dictionaries)

        assert result["champions"]["changed"] == {"Nunu & Willump": {"Q": []}}
        assert result["runes"]["new"] == ["Jack Of All Trades"]


    def test_unknown_names_stay_and_only_warn_when_not_removed(self, logger):
        notes = {"items": {"new": [], "changed": {"Mystery Item": []}, "deleted": ["Old Item"]}}

        result = ddragon_notes(notes, {"items": NameDictionary()})

        assert result["items"]["changed"] == {"Mystery Item": []}
        assert result["items"]["deleted"] == ["Old Item"]
        assert warnings(logger) == ["[ITEM] [NAMES] [Mystery Item] Patch notes name not in Data Dragon"]
