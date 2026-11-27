import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import src.server.loader.patchloader as loader
from src.server.loader.names import DDragonName, NameDictionary
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.loader.rune_builder import RuneEntry
from src.server.models.change import patch_note
from src.server.models.champion import Champion, RawChampion
from src.server.models.json_validation import ChampionJson
from src.server.models.patch import NewPatch
from src.server.loader.champion_builder import champion_stats
from src.tests.test_champion_builder import raw_champion
from src.tests.test_summonerspell_builder import entry


CDRAGON = Path(__file__).parent / "static" / "cdragon"
BUILD = "16.23.8406595+branch.releases-16-23.content.release"


def fixture(name: str) -> dict:
    return json.loads((CDRAGON / name).read_text(encoding="utf-8"))


class FakeSession:
    """Answers like SafeSession: the JSON for known URLs, "" for everything else (a 404)."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def get_json(self, url: str) -> dict | str:
        self.urls.append(url)
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


@pytest.fixture(autouse=True)
def images(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(loader, "load_champion_images", mock)
    return mock


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
    async def test_images_are_stored_and_failures_logged(self, session, patch, database, loggers, images):
        images.return_value = ["spell veigarbalefulstrike: 404 Image not found"]

        await loader.load_all_champions([veigar_entry()], session, patch)

        assert images.call_args.args[3] == "16.23"
        assert database.add_champion.call_args.args[0] is images.call_args.args[1]
        loggers["patch"].warning.assert_any_call("[CHAMPION] [IMAGE] [Veigar] spell veigarbalefulstrike: 404 Image not found")

    @pytest.mark.asyncio
    async def test_champion_data_reaches_the_champion(self, session, patch, database):
        await loader.load_all_champions([veigar_entry()], session, patch)

        assert database.upsert_raw_champion.call_args.args[0].champion_data["apiname"] == "Veigar"
        assert database.add_champion.call_args.args[0].last_changed == "16.7.1"

    @pytest.mark.asyncio
    async def test_the_patch_remembers_the_build(self, session, patch, database):
        await loader.load_all_champions([veigar_entry()], session, patch)

        assert patch.build and patch.build == database.upsert_raw_champion.call_args.args[0].build


    @pytest.mark.asyncio
    async def test_missing_module_is_only_a_warning(self, session, patch, database, loggers):
        del session.responses["ChampionData"]

        await loader.load_all_champions([veigar_entry()], session, patch)

        assert patch.loaded_champion_count == 1
        warnings = [call.args[0] for call in loggers["patch"].warning.call_args_list]
        assert any("Module:ChampionData not loaded" in warning for warning in warnings)


    @pytest.mark.asyncio
    async def test_missing_cooldowns_are_logged(self, session, patch, database, loggers, monkeypatch):
        monkeypatch.setattr(loader, "missing_cooldowns", Mock(return_value=["w"]))

        await loader.load_all_champions([veigar_entry()], session, patch)

        warnings = [call.args[0] for call in loggers["patch"].warning.call_args_list]
        assert any(warning.startswith("[CHAMPION] [COOLDOWN] [Veigar] W Dark Matter:") for warning in warnings)
        database.add_champion.assert_called_once()


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
    async def test_wiki_templates_are_fetched_by_wiki_name(self, session, patch, database):
        names = NameDictionary({"Veigar": "Tiny Master of Evil"}, [DDragonName("Veigar", "Veigar")])

        await loader.load_all_champions([veigar_entry()], session, patch, names)

        assert any("gapprefix=Data+Tiny+Master+of+Evil%2F" in url for url in session.urls)


    @pytest.mark.asyncio
    async def test_missing_build_stops_before_any_champion(self, session, patch, database):
        del session.responses["content-metadata.json"]

        with pytest.raises(LoadError):
            await loader.load_all_champions([veigar_entry()], session, patch)

        database.add_champion.assert_not_called()


class TestNameDictionaries():

    @pytest.mark.asyncio
    async def test_without_the_wiki_data_dragons_names_stay(self, monkeypatch, loggers):
        monkeypatch.setattr(loader, "load_name_dictionaries", AsyncMock(side_effect=LoadError(404, "down", "", "", "")))

        result = await loader.name_dictionaries(FakeSession({}), [veigar_entry()], [], [], [])

        assert result["champions"].wiki_name("Veigar", "Veigar") == "Veigar"
        assert "Wiki names not loaded" in loggers["patch"].warning.call_args.args[0]


    @pytest.mark.asyncio
    async def test_only_summoners_rift_objects_are_looked_up(self, monkeypatch):
        lookup = AsyncMock(return_value={})
        monkeypatch.setattr(loader, "load_name_dictionaries", lookup)
        items = [("1001", SimpleNamespace(name="Boots", maps={"11": True})),
                 ("3901", SimpleNamespace(name="Fire at Will", maps={"11": False}))]
        spells = [SimpleNamespace(id_="SummonerFlash", name="Flash", modes=["CLASSIC", "ARAM"]),
                  SimpleNamespace(id_="SummonerSnowball", name="Mark", modes=["ARAM"])]
        runes = [RuneEntry(8112, "Electrocute", "Domination", 8100, 0, 0, "electrocute.png"),
                 RuneEntry(5008, "Adaptive Force (Offense)", "Stat Shard", 0, 0, 0, "adaptive.png")]

        await loader.name_dictionaries(FakeSession({}), [], items, runes, spells)

        entries = lookup.call_args.args[1]
        assert entries["items"] == [DDragonName("1001", "Boots")]
        assert entries["summonerspells"] == [DDragonName("SummonerFlash", "Flash")]
        # Stat shards have no wiki pages to look up.
        assert entries["runes"] == [DDragonName("8112", "Electrocute")]


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


class TestFetchOtherLists():

    @pytest.mark.asyncio
    async def test_items_by_id(self):
        items = fixture("items.ddragon.json")["data"]
        session = FakeSession({"16.23.1/data/en_GB/item.json": {"type": "item", "version": "16.23.1", "basic": {},
                                                                "data": items, "groups": [], "tree": []}})

        result = await loader.fetch_item_list(session, "16.23.1")

        assert [item_id for item_id, _ in result] == list(items)
        assert result[0][1].name == items["3057"]["name"]


    @pytest.mark.asyncio
    async def test_summonerspells(self):
        ignite = entry().dict(by_alias=True)
        session = FakeSession({"16.23.1/data/en_GB/summoner.json": {"type": "summoner", "version": "16.23.1",
                                                                    "data": {"SummonerDot": ignite}}})

        assert [spell.id_ for spell in await loader.fetch_summonerspell_list(session, "16.23.1")] == ["SummonerDot"]


    @pytest.mark.asyncio
    async def test_missing_lists_are_errors(self):
        with pytest.raises(PatcherError):
            await loader.fetch_item_list(FakeSession({}), "16.23.1")
        with pytest.raises(PatcherError):
            await loader.fetch_summonerspell_list(FakeSession({}), "16.23.1")


class TestLoadFreshDatabase():

    @pytest.fixture
    def lists(self, monkeypatch) -> None:
        spells = [SimpleNamespace(id_="SummonerFlash", modes=["CLASSIC"]), SimpleNamespace(id_="SummonerMana", modes=["ARAM"])]
        monkeypatch.setattr(loader, "fetch_item_list", AsyncMock(return_value=[("1001", None), ("322065", None)]))
        monkeypatch.setattr(loader, "fetch_summonerspell_list", AsyncMock(return_value=spells))


    @pytest.fixture
    def champions(self, monkeypatch) -> None:
        monkeypatch.setattr(loader, "fetch_champion_list", AsyncMock(return_value=[veigar_entry()]))
        monkeypatch.setattr(loader, "load_all_champions", AsyncMock(side_effect=self._count_one))
        monkeypatch.setattr(loader, "load_all_summonerspells", AsyncMock())
        monkeypatch.setattr(loader, "load_all_items", AsyncMock())
        monkeypatch.setattr(loader, "item_sources", AsyncMock(return_value=Mock(item_data={
            "1001": {"modes": {"classic sr 5v5": True}}, "322065": {"modes": {"swiftplay": True}}})))
        monkeypatch.setattr(loader, "fetch_rune_entries", AsyncMock(return_value=[]))
        # Two runes: one tree rune from Data Dragon, one stat shard from CommunityDragon.
        monkeypatch.setattr(loader, "rune_sources", AsyncMock(return_value=Mock(entries=[Mock(), Mock()])))
        monkeypatch.setattr(loader, "load_all_runes", AsyncMock())
        monkeypatch.setattr(loader, "name_dictionaries", AsyncMock(
            return_value={"champions": NameDictionary(), "summonerspells": NameDictionary(), "runes": NameDictionary()}))


    @staticmethod
    async def _count_one(champions, session, patch, names) -> None:
        patch.loaded_champion_count += 1


    @pytest.mark.asyncio
    async def test_counts_and_stores_the_patch(self, database, lists, champions):
        await loader.load_fresh_database(["16.23.1"])

        patch = database.upsert_patch.call_args.args[0]
        assert patch.patch == "16.23.1"
        # Only Summoner's Rift spells and items count: Clarity (ARAM) and Swiftplay's copy are left out.
        assert (patch.champion_count, patch.item_count, patch.summonerspell_count, patch.rune_count,
                patch.total_count) == (1, 1, 1, 2, 5)
        assert patch.loaded_total_count == 1
        loader.load_all_items.assert_called_once()


    @pytest.mark.asyncio
    async def test_a_failing_type_still_stores_the_patch(self, database, lists, champions, loggers):
        loader.load_all_runes.side_effect = RuntimeError("wiki down")

        await loader.load_fresh_database(["16.23.1"])

        database.upsert_patch.assert_called_once()
        assert "wiki down" in loggers["patch"].error.call_args.args[0]


    @pytest.mark.asyncio
    async def test_resumes_an_unfinished_load_of_the_same_patch(self, database, lists, champions):
        unfinished = NewPatch(patch="16.23.1", champion_count=1, loaded_champion_count=0, cached_documents=3)
        database.fetch_patch_latest.return_value = unfinished

        await loader.load_fresh_database(["16.23.1"])

        assert database.upsert_patch.call_args.args[0] is unfinished


class TestPendingHotfix():

    @pytest.fixture
    def sources(self, monkeypatch) -> AsyncMock:
        wiki = AsyncMock(return_value=[])
        monkeypatch.setattr(loader, "fetch_build", AsyncMock(return_value=BUILD))
        monkeypatch.setattr(loader, "fetch_hotfix_dates", wiki)
        return wiki


    @pytest.mark.asyncio
    async def test_same_build_and_no_wiki_hotfix_is_nothing(self, session, sources):
        assert await loader.pending_hotfix(session, NewPatch(patch="16.23.1", build=BUILD)) is None


    @pytest.mark.asyncio
    async def test_a_new_build_is_a_hotfix(self, session, sources):
        hotfix = await loader.pending_hotfix(session, NewPatch(patch="16.23.1", build="16.23.1000"))

        assert (hotfix.build, hotfix.build_changed, hotfix.wiki_dates) == (BUILD, True, [])


    @pytest.mark.asyncio
    async def test_only_wiki_hotfixes_after_the_last_run_day_count(self, session, sources):
        sources.return_value = [datetime(2026, 11, 20), datetime(2026, 11, 22)]
        patch = NewPatch(patch="16.23.1", build=BUILD, updated_at=datetime(2026, 11, 20, 18, 0))

        hotfix = await loader.pending_hotfix(session, patch)

        assert (hotfix.build_changed, hotfix.wiki_dates) == (False, [datetime(2026, 11, 22)])


    @pytest.mark.asyncio
    async def test_without_a_run_the_load_day_counts(self, session, sources):
        # The load already took the earlier wiki hotfixes with it.
        sources.return_value = [datetime(2026, 11, 20), datetime(2026, 11, 22)]
        patch = NewPatch(patch="16.23.1", build=BUILD, timestamp=datetime(2026, 11, 21, 9, 0))

        hotfix = await loader.pending_hotfix(session, patch)

        assert hotfix.wiki_dates == [datetime(2026, 11, 22)]


class TestHotfixOneChampion():

    @pytest.fixture
    def veigar(self, load_champion) -> Champion:
        champion = load_champion("veigar").copy(update=champion_stats(raw_champion("Veigar").cdragon))
        champion.changes = [patch_note("Base health increased")]
        return champion


    @pytest.fixture
    def stored_raw(self, database) -> RawChampion:
        raw = raw_champion("Veigar")
        for spell in raw.cdragon.values():
            if isinstance(spell, dict) and spell.get("mScriptName") == "VeigarBalefulStrike":
                next(value for value in spell["mSpell"]["DataValues"] if value["name"] == "BaseDamage")["values"][1] = 70
        database.fetch_raw_champion = AsyncMock(return_value=raw)
        database.update_champion = AsyncMock()
        return raw


    @pytest.mark.asyncio
    async def test_compares_with_its_own_patch_and_keeps_earlier_lines(self, session, patch, database, veigar,
                                                                       stored_raw):
        strings = fixture("veigar.strings.json")["entries"]
        hotfixed_at = datetime(2026, 11, 22, 18, 0)
        await loader.hotfix_one_champion(veigar_entry(), veigar, {}, session, patch, hotfixed_at, BUILD, strings, {})

        database.fetch_raw_champion.assert_called_once_with("Veigar", "16.23.1")
        champion = database.update_champion.call_args.args[0]
        assert champion.id == veigar.id
        assert [change.text for change in champion.changes] == ["Base health increased"]
        assert [(change.text, change.hotfix) for change in champion.q.changes] == [
            ("BaseDamage: by_rank(70, 120, 160, 200, 240) ⇒ by_rank(80, 120, 160, 200, 240)", hotfixed_at)]
        assert patch.changed_champion_count == 0  # already changed in this patch


class TestLoadData():

    @pytest.mark.asyncio
    async def test_the_hotfix_comes_before_the_next_patch(self, database, monkeypatch):
        latest = NewPatch(patch="16.22.1")
        hotfixed = NewPatch(patch="16.22.1", build=BUILD)
        hotfix = loader.Hotfix(BUILD, True)
        database.fetch_patch_latest.return_value = latest
        monkeypatch.setattr(loader, "check_updates", AsyncMock(return_value=(["16.23.1"], hotfix)))
        load_hotfix = AsyncMock(return_value=hotfixed)
        load_patches = AsyncMock()
        monkeypatch.setattr(loader, "load_hotfix", load_hotfix)
        monkeypatch.setattr(loader, "load_patches", load_patches)

        await loader.load_data()

        load_hotfix.assert_called_once_with(latest, hotfix)
        load_patches.assert_called_once_with(["16.23.1"], hotfixed)
