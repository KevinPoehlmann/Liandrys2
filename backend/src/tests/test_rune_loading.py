import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

import src.server.loader.patchloader as loader
from src.server.loader.names import NameDictionary
from src.server.models.change import patch_note
from src.server.models.patch import NewPatch, Patch
from src.server.models.rune import Rune
from src.tests.test_patchloader import BUILD, FakeSession
from src.tests.test_rune_builder import (ADAPTIVE_ID, CONQUEROR_ID, DEMOLISH_ID, ELECTROCUTE, ELECTROCUTE_ID,
                                         HEALTH_SCALING_ID, PERKS, STRINGS, WIKI, entry, raw)


SHARD_COUNT = 9


def stored_electrocute(patch: str = "16.22.1") -> Rune:
    return Rune.parse_obj(json.loads(ELECTROCUTE.read_text(encoding="utf-8")) | {"patch": patch})


@pytest.fixture
def session() -> FakeSession:
    return FakeSession({
        "content-metadata.json": {"version": BUILD},
        "perks.cdtb.bin.json": PERKS,
        "lol.stringtable.json": {"entries": STRINGS},
        "titles=Template%3ARune": WIKI,
    })


@pytest.fixture(autouse=True)
def loggers(monkeypatch) -> dict[str, Mock]:
    mocks = {"patch": Mock(), "load": Mock()}
    monkeypatch.setattr(loader, "patch_logger", mocks["patch"])
    monkeypatch.setattr(loader, "load_logger", mocks["load"])
    return mocks


@pytest.fixture(autouse=True)
def images(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(loader, "load_rune_image", mock)
    return mock


@pytest.fixture(autouse=True)
def tree_icons(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(loader, "load_rune_tree_icons", mock)
    return mock


@pytest.fixture
def database(monkeypatch) -> Mock:
    mock = Mock(exists_rune=AsyncMock(return_value=False), upsert_raw_rune=AsyncMock(), add_rune=AsyncMock(),
                update_rune=AsyncMock(), fetch_runes_by_patch=AsyncMock(return_value=[]),
                fetch_raw_rune=AsyncMock(return_value=raw(patch="16.22.1")))
    monkeypatch.setattr(loader, "db", mock)
    return mock


def warnings(loggers) -> list[str]:
    return [call.args[0] for call in loggers["patch"].warning.call_args_list]


async def sources(session, *rune_ids: int):
    names = NameDictionary({str(ELECTROCUTE_ID): "Electrocute"})
    return await loader.rune_sources(session, "16.23", [entry(rune_id) for rune_id in rune_ids], names)


def added(database) -> list:
    return [call.args[0] for call in database.add_rune.call_args_list]


class TestSources():

    @pytest.mark.asyncio
    async def test_tree_runes_and_shards_with_one_wiki_request(self, session):
        found = await sources(session, ELECTROCUTE_ID)

        assert len(found.entries) == 1 + SHARD_COUNT
        assert found.build == BUILD
        assert [url for url in session.urls if "api.php" in url] == [session.urls[-1]]
        assert "Template:Rune data Electrocute" in found.wiki_pages


    @pytest.mark.asyncio
    async def test_without_the_wiki_runes_still_load(self, session, database, loggers):
        del session.responses["titles=Template%3ARune"]
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_runes(session, patch, await sources(session, ELECTROCUTE_ID))

        assert database.add_rune.await_count == 1 + SHARD_COUNT
        assert any("Rune wiki pages not loaded" in warning for warning in warnings(loggers))
        assert not any("No wiki article" in warning for warning in warnings(loggers))  # no warning per rune


class TestLoad():

    @pytest.mark.asyncio
    async def test_stores_raw_data_and_runes(self, session, database):
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_runes(session, patch, await sources(session, ELECTROCUTE_ID))

        electrocute = next(rune for rune in added(database) if rune.rune_id == ELECTROCUTE_ID)
        assert electrocute.passive.values["WindowDuration"] == "3"
        raws = [call.args[0] for call in database.upsert_raw_rune.call_args_list]
        assert next(found for found in raws if found.rune_id == ELECTROCUTE_ID).wiki_data.revision_id == 4060699
        assert database.add_rune.await_count == 1 + SHARD_COUNT


    @pytest.mark.asyncio
    async def test_a_shards_second_row_waits_for_its_first(self, session, database):
        await loader.load_all_runes(session, NewPatch(patch="16.23.1"), await sources(session))

        stored = [call.args[0].rune_id for call in database.upsert_raw_rune.call_args_list]
        # Adaptive Force and Health Scaling sit in two rows each: their second raw upsert comes after every first one.
        assert len(stored) == SHARD_COUNT and len(set(stored)) == SHARD_COUNT - 2
        assert stored[-2:] == [ADAPTIVE_ID, HEALTH_SCALING_ID]


    @pytest.mark.asyncio
    async def test_a_missing_wiki_page_is_a_warning(self, session, database, loggers):
        await loader.load_all_runes(session, NewPatch(patch="16.23.1"), await sources(session, DEMOLISH_ID))

        assert "[RUNE] [WIKI] [Demolish] No Template:Rune data Demolish" in warnings(loggers)
        assert "[RUNE] [WIKI] [Demolish] No wiki article found" in warnings(loggers)


    @pytest.mark.asyncio
    async def test_skips_a_rune_that_is_already_loaded(self, session, database):
        database.exists_rune.return_value = True

        await loader.load_all_runes(session, NewPatch(patch="16.23.1"), await sources(session, ELECTROCUTE_ID))

        database.upsert_raw_rune.assert_not_called()
        # A shard is looked up by its row too.
        assert database.exists_rune.call_args_list[-1].args[2] is not None


    @pytest.mark.asyncio
    async def test_a_failing_rune_does_not_stop_the_others(self, session, database, loggers):
        found = await sources(session, ELECTROCUTE_ID)
        found.records.pop(ELECTROCUTE_ID)
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_runes(session, patch, found)

        assert database.add_rune.await_count == SHARD_COUNT
        loggers["load"].error.assert_called_once_with("[RUNE] Electrocute ❌ Failed to load")


    @pytest.mark.asyncio
    async def test_image_failures_are_warnings(self, session, database, loggers, images):
        images.return_value = ["404 Image not found — url"]

        await loader.load_all_runes(session, NewPatch(patch="16.23.1"), await sources(session, ELECTROCUTE_ID))

        assert images.call_args.args[3] == "16.23"
        assert "[RUNE] [IMAGE] [Electrocute] 404 Image not found — url" in warnings(loggers)


    @pytest.mark.asyncio
    async def test_the_tree_icons_load_once_per_patch(self, session, database, loggers, tree_icons):
        tree_icons.return_value = ["Domination: 404 Image not found — url"]
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_runes(session, patch, await sources(session, ELECTROCUTE_ID))

        tree_icons.assert_called_once()
        assert tree_icons.call_args.args[1] is patch
        assert tree_icons.call_args.args[2] == {8100: ("Domination", "assets/perks/styles/7200_domination.tex")}
        assert "[RUNE] [IMAGE] [Tree] Domination: 404 Image not found — url" in warnings(loggers)


class TestPatch():

    @pytest.mark.asyncio
    async def test_patches_old_runes_and_loads_new_ones(self, session, database):
        database.fetch_runes_by_patch.return_value = [stored_electrocute()]
        patch, old_patch = NewPatch(patch="16.23.1"), NewPatch(patch="16.22.1")
        notes = {"changed": {"Electrocute": [patch_note("Bug fixed")]}}

        await loader.patch_all_runes(notes, session, patch, old_patch, await sources(session, ELECTROCUTE_ID))

        electrocute = next(rune for rune in added(database) if rune.rune_id == ELECTROCUTE_ID)
        assert electrocute.patch == "16.23.1"
        assert electrocute.passive.rules == stored_electrocute().passive.rules  # the hand-made part stays
        assert [change.text for change in electrocute.changes] == ["Bug fixed"]
        assert not electrocute.validated  # named in the patch notes, but CDragon's numbers didn't change
        assert patch.rune_count == len(added(database)) == 10


    @pytest.mark.asyncio
    async def test_without_old_raw_data_the_stored_values_are_compared(self, session, database, loggers):
        database.fetch_runes_by_patch.return_value = [stored_electrocute()]
        database.fetch_raw_rune.return_value = None
        patch = NewPatch(patch="16.23.1")

        await loader.patch_all_runes({}, session, patch, NewPatch(patch="16.22.1"), await sources(session, ELECTROCUTE_ID))

        assert next(rune for rune in added(database) if rune.rune_id == ELECTROCUTE_ID).validated
        assert any("No raw data of the old patch" in warning for warning in warnings(loggers))


    @pytest.mark.asyncio
    async def test_a_rune_gone_from_the_list_is_left_behind(self, session, database, loggers):
        database.fetch_runes_by_patch.return_value = [stored_electrocute()]
        patch = NewPatch(patch="16.23.1")

        await loader.patch_all_runes({}, session, patch, NewPatch(patch="16.22.1"), await sources(session, CONQUEROR_ID))

        assert ELECTROCUTE_ID not in [rune.rune_id for rune in added(database)]
        loggers["load"].info.assert_any_call("[RUNE] Electrocute ✔ Not in patch 16.23.1 anymore, left behind")


class TestHotfix():

    @pytest.fixture
    def patch(self) -> Patch:
        return Patch(_id="0" * 24, patch="16.23.1", rune_count=1)


    @pytest.mark.asyncio
    async def test_adds_the_hotfix_lines_in_place(self, session, database, patch):
        current = stored_electrocute("16.23.1")
        current.changes = [patch_note("Damage increased")]
        database.fetch_runes_by_patch.return_value = [current]
        database.fetch_raw_rune.return_value = raw()
        hotfixed_at = datetime(2026, 11, 27, 18)
        notes = {"Electrocute": [patch_note("Damage increased"), patch_note("Cooldown reduced")]}
        hotfix = loader.Hotfix(BUILD, build_changed=False)
        names = NameDictionary({str(ELECTROCUTE_ID): "Electrocute"})

        counts = await loader.hotfix_runes([entry(ELECTROCUTE_ID)], notes, session, patch, hotfix, hotfixed_at, names)

        updated = database.update_rune.call_args.args[0]
        assert (counts, updated.id) == ((1, 0), current.id)
        assert [(change.text, change.hotfix) for change in updated.changes] == [("Damage increased", None),
                                                                                ("Cooldown reduced", hotfixed_at)]


    @pytest.mark.asyncio
    async def test_nothing_named_and_the_same_build_downloads_nothing(self, session, database, patch):
        hotfix = loader.Hotfix(BUILD, build_changed=False)

        counts = await loader.hotfix_runes([entry(ELECTROCUTE_ID)], {}, session, patch, hotfix, datetime.now())

        assert counts == (0, 0) and session.urls == []


    @pytest.mark.asyncio
    async def test_a_new_build_hotfixes_every_rune(self, session, database, patch):
        database.fetch_runes_by_patch.return_value = [stored_electrocute("16.23.1")]
        hotfix = loader.Hotfix("new build", build_changed=True)

        counts = await loader.hotfix_runes([entry(ELECTROCUTE_ID)], {}, session, patch, hotfix, datetime.now())

        # Electrocute is updated; the shards aren't in the patch yet and are skipped with a warning, not failed.
        assert counts == (1 + SHARD_COUNT, 0)
        database.update_rune.assert_called_once()
