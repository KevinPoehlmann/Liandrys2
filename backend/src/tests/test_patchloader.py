import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

import src.server.loader.patchloader as loader
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.models.json_validation import ChampionJson
from src.server.models.patch import NewPatch


CDRAGON = Path(__file__).parent / "static" / "cdragon"
BUILD = "16.23.8406595+branch.releases-16-23.content.release"


def fixture(name: str) -> dict:
    return json.loads((CDRAGON / name).read_text(encoding="utf-8"))


class FakeSession:
    """Answers like SafeSession: the JSON for known URLs, "" for everything else (a 404)."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses

    async def get_json(self, url: str) -> dict | str:
        return next((data for part, data in self.responses.items() if part in url), "")


def module_response(text: str) -> dict:
    return {"query": {"pages": [{"title": "Module:ChampionData/data", "revisions": [{"slots": {"main": {"content": text}}}]}]}}


def veigar_entry() -> ChampionJson:
    return ChampionJson(**fixture("veigar.ddragon.json"))


def unknown_entry() -> ChampionJson:
    entry = fixture("veigar.ddragon.json") | {"id": "Unknown", "key": "999", "name": "Unknown"}
    return ChampionJson(**entry)


@pytest.fixture
def session() -> FakeSession:
    return FakeSession({
        "content-metadata.json": {"version": BUILD},
        "lol.stringtable.json": {"entries": fixture("veigar.strings.json")["entries"]},
        "veigar/veigar.bin.json": fixture("veigar.bin.json"),
        "gapprefix=Data+": fixture("veigar.wiki.json"),
        "ChampionData": module_response((CDRAGON / "champion_data.lua").read_text(encoding="utf-8")),
    })


@pytest.fixture
def patch() -> NewPatch:
    return NewPatch(patch="16.23.1", champion_count=2)


@pytest.fixture(autouse=True)
def loggers(monkeypatch) -> dict[str, Mock]:
    mocks = {"patch": Mock(), "load": Mock()}
    monkeypatch.setattr(loader, "patch_logger", mocks["patch"])
    monkeypatch.setattr(loader, "load_logger", mocks["load"])
    monkeypatch.setattr(loader, "attach_fallback_logfile", Mock())
    return mocks


@pytest.fixture
def database(monkeypatch) -> Mock:
    mock = Mock(exists_champion_by_name=AsyncMock(return_value=False), upsert_raw_champion=AsyncMock(),
                add_champion=AsyncMock(), fetch_patch_latest=AsyncMock(return_value=None), upsert_patch=AsyncMock())
    monkeypatch.setattr(loader, "db", mock)
    return mock


class TestLoadChampion():

    @pytest.mark.asyncio
    async def test_stores_raw_data_and_champion(self, session, patch, database):
        await loader.load_champion(veigar_entry(), session, patch, BUILD, fixture("veigar.strings.json")["entries"])

        raw = database.upsert_raw_champion.call_args.args[0]
        champion = database.add_champion.call_args.args[0]
        assert (raw.champion_id, raw.build, raw.patch) == ("Veigar", BUILD, "16.23.1")
        assert raw.wiki
        assert champion.q.values["BaseDamage"] == "by_rank(80, 120, 160, 200, 240)"
        assert patch.loaded_champion_count == 1


    @pytest.mark.asyncio
    async def test_skips_a_champion_that_is_already_loaded(self, session, patch, database):
        database.exists_champion_by_name.return_value = True

        await loader.load_champion(veigar_entry(), session, patch, BUILD, {})

        database.upsert_raw_champion.assert_not_called()
        database.add_champion.assert_not_called()
        assert patch.loaded_champion_count == 0


    @pytest.mark.asyncio
    async def test_raw_data_is_kept_when_building_fails(self, session, patch, database, monkeypatch):
        monkeypatch.setattr(loader, "build_champion", Mock(side_effect=ValueError("no windup")))

        with pytest.raises(ValueError):
            await loader.load_champion(veigar_entry(), session, patch, BUILD, {})

        database.upsert_raw_champion.assert_called_once()
        database.add_champion.assert_not_called()


    @pytest.mark.asyncio
    async def test_missing_wiki_templates_are_a_warning(self, session, patch, database, loggers):
        session.responses["gapprefix=Data+"] = {"query": {"pages": []}}

        await loader.load_champion(veigar_entry(), session, patch, BUILD, {})

        database.add_champion.assert_called_once()
        warnings = [call.args[0] for call in loggers["patch"].warning.call_args_list]
        assert any("No wiki data templates" in warning for warning in warnings)


class TestLoadAllChampions():

    @pytest.mark.asyncio
    async def test_champion_data_reaches_the_champion(self, session, patch, database):
        await loader.load_all_champions([veigar_entry()], session, patch)

        assert database.upsert_raw_champion.call_args.args[0].champion_data["apiname"] == "Veigar"
        assert database.add_champion.call_args.args[0].last_changed == "16.7.1"


    @pytest.mark.asyncio
    async def test_missing_module_is_only_a_warning(self, session, patch, database, loggers):
        del session.responses["ChampionData"]

        await loader.load_all_champions([veigar_entry()], session, patch)

        assert patch.loaded_champion_count == 1
        warnings = [call.args[0] for call in loggers["patch"].warning.call_args_list]
        assert any("Module:ChampionData not loaded" in warning for warning in warnings)


    @pytest.mark.asyncio
    async def test_mismatches_are_logged(self, session, patch, database, loggers, monkeypatch):
        monkeypatch.setattr(loader, "wiki_mismatches", Mock(return_value=["hp: wiki 1, CDragon 2"]))

        await loader.load_all_champions([veigar_entry()], session, patch)

        loggers["patch"].warning.assert_called_with("[CHAMPION] [WIKI] [Veigar] hp: wiki 1, CDragon 2")
        database.add_champion.assert_called_once()


    @pytest.mark.asyncio
    async def test_one_failing_champion_does_not_stop_the_others(self, session, patch, database, loggers):
        await loader.load_all_champions([unknown_entry(), veigar_entry()], session, patch)

        assert patch.loaded_champion_count == 1
        assert database.add_champion.call_args.args[0].name == "Veigar"
        assert "[Unknown]" in loggers["patch"].error.call_args.args[0]


    @pytest.mark.asyncio
    async def test_missing_build_stops_before_any_champion(self, session, patch, database):
        del session.responses["content-metadata.json"]

        with pytest.raises(LoadError):
            await loader.load_all_champions([veigar_entry()], session, patch)

        database.add_champion.assert_not_called()


class TestFetchChampionList():

    @pytest.mark.asyncio
    async def test_parses_every_champion(self):
        session = FakeSession({"championFull.json": {"type": "champion", "format": "full", "version": "16.23.1",
                                                     "data": {"Veigar": fixture("veigar.ddragon.json")}}})

        champions = await loader.fetch_champion_list(session, "16.23.1")

        assert [champion.id_ for champion in champions] == ["Veigar"]


    @pytest.mark.asyncio
    async def test_missing_list_is_an_error(self):
        with pytest.raises(PatcherError):
            await loader.fetch_champion_list(FakeSession({}), "16.23.1")


class TestLoadFreshDatabase():

    @pytest.fixture
    def old_loader(self, monkeypatch) -> Mock:
        mock = Mock(_list_other_data=AsyncMock(return_value=([("1001", None)], [], [])), _load_all_items=AsyncMock(),
                    _load_all_runes=AsyncMock(), _load_all_summonerspells=AsyncMock())
        monkeypatch.setattr(loader, "old", mock)
        return mock


    @pytest.fixture
    def champions(self, monkeypatch) -> None:
        monkeypatch.setattr(loader, "fetch_champion_list", AsyncMock(return_value=[veigar_entry()]))
        monkeypatch.setattr(loader, "load_all_champions", AsyncMock(side_effect=self._count_one))


    @staticmethod
    async def _count_one(champions, session, patch) -> None:
        patch.loaded_champion_count += 1


    @pytest.mark.asyncio
    async def test_counts_and_stores_the_patch(self, database, old_loader, champions):
        await loader.load_fresh_database({"16.23.1": []})

        patch = database.upsert_patch.call_args.args[0]
        assert (patch.patch, patch.hotfix) == ("16.23.1", None)
        assert (patch.champion_count, patch.item_count, patch.total_count) == (1, 1, 2)
        assert patch.loaded_total_count == 1
        old_loader._load_all_items.assert_called_once()


    @pytest.mark.asyncio
    async def test_a_failing_type_still_stores_the_patch(self, database, old_loader, champions, loggers):
        old_loader._load_all_items.side_effect = RuntimeError("wiki down")

        await loader.load_fresh_database({"16.23.1": []})

        database.upsert_patch.assert_called_once()
        assert "wiki down" in loggers["patch"].error.call_args.args[0]


    @pytest.mark.asyncio
    async def test_resumes_an_unfinished_load_of_the_same_patch(self, database, old_loader, champions):
        unfinished = NewPatch(patch="16.23.1", champion_count=1, loaded_champion_count=0, cached_documents=3)
        database.fetch_patch_latest.return_value = unfinished

        await loader.load_fresh_database({"16.23.1": []})

        assert database.upsert_patch.call_args.args[0] is unfinished
