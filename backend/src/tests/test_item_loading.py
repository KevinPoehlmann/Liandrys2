from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

import src.server.loader.patchloader as loader
from src.server.models.change import patch_note
from src.server.models.item import Item
from src.server.models.patch import NewPatch, Patch
from src.tests.test_item_builder import (BUILD, CDRAGON, GUNBLADE, ITEM_DATA, ITEMS, SHARED, SHEEN, STRINGS,
                                         THORNMAIL, TEST_GROUP, entry, raw)
from src.tests.test_patchloader import FakeSession
from src.tests.test_summonerspell_loading import module_response


def sources(item_data: dict | None = None) -> loader.ItemSources:
    return loader.ItemSources(build=BUILD, items=ITEMS, shared=SHARED, strings=STRINGS,
                              item_data=ITEM_DATA if item_data is None else item_data)


def stored_thornmail(patch: str = "16.22.1") -> Item:
    return Item.parse_raw((TEST_GROUP / "thornmail.json").read_text(encoding="utf-8")).copy(update={"patch": patch})


@pytest.fixture(autouse=True)
def loggers(monkeypatch) -> dict[str, Mock]:
    mocks = {"patch": Mock(), "load": Mock()}
    monkeypatch.setattr(loader, "patch_logger", mocks["patch"])
    monkeypatch.setattr(loader, "load_logger", mocks["load"])
    return mocks


@pytest.fixture(autouse=True)
def images(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(loader, "load_item_image", mock)
    return mock


@pytest.fixture(autouse=True)
def border(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(loader, "load_masterwork_border", mock)
    return mock


@pytest.fixture
def database(monkeypatch) -> Mock:
    mock = Mock(exists_item_by_item_id=AsyncMock(return_value=False), upsert_raw_item=AsyncMock(),
                add_item=AsyncMock(), update_item=AsyncMock(), fetch_items_by_patch=AsyncMock(return_value=[]),
                fetch_raw_item=AsyncMock(return_value=raw(THORNMAIL, patch="16.22.1")))
    monkeypatch.setattr(loader, "db", mock)
    return mock


def warnings(loggers) -> list[str]:
    return [call.args[0] for call in loggers["patch"].warning.call_args_list]


class TestSources():

    @pytest.mark.asyncio
    async def test_downloads_everything_once(self):
        session = FakeSession({
            "content-metadata.json": {"version": BUILD}, "items.cdtb.bin.json": ITEMS,
            "shared.cdtb.bin.json": SHARED, "lol.stringtable.json": {"entries": STRINGS},
            "ItemData": module_response((CDRAGON / "item_data.lua").read_text(encoding="utf-8")),
        })

        found = await loader.item_sources(session, "16.23")

        assert found.build == BUILD
        assert found.item_data[SHEEN]["effects"]["pass"]["name"] == "Spellblade"
        assert all("/16.23/" in url for url in session.urls if "communitydragon" in url)

    @pytest.mark.asyncio
    async def test_a_missing_module_is_a_warning(self, loggers):
        session = FakeSession({"content-metadata.json": {"version": BUILD}, "items.cdtb.bin.json": ITEMS,
                               "shared.cdtb.bin.json": SHARED, "lol.stringtable.json": {"entries": STRINGS}})

        found = await loader.item_sources(session, "16.23")

        assert found.item_data == {}
        assert any("Module:ItemData not loaded" in warning for warning in warnings(loggers))


class TestLoad():

    @pytest.mark.asyncio
    async def test_stores_raw_data_and_item(self, database, images):
        patch = NewPatch(patch="16.23.1", item_count=1)

        await loader.load_all_items([(GUNBLADE, entry(GUNBLADE))], FakeSession({}), patch, sources())

        stored_raw = database.upsert_raw_item.call_args.args[0]
        item = database.add_item.call_args.args[0]
        assert (stored_raw.item_id, stored_raw.build, stored_raw.active["mScriptName"]) == (GUNBLADE, BUILD,
                                                                                           "HextechGunbladeSpell")
        assert item.values["Cooldown"] == "60"
        assert patch.loaded_item_count == 1
        assert images.call_args.args[3] == "16.23"

    @pytest.mark.asyncio
    async def test_cross_check_and_image_failures_are_warnings(self, database, loggers, images):
        images.return_value = ["404 Image not found — url"]
        cheaper = entry(SHEEN).copy(update={"gold": entry(SHEEN).gold.copy(update={"total": 800})})

        await loader.load_all_items([(SHEEN, cheaper)], FakeSession({}), NewPatch(patch="16.23.1"), sources())

        assert "[ITEM] [WIKI] [Sheen] gold: wiki 900, Data Dragon 800" in warnings(loggers)
        assert "[ITEM] [IMAGE] [Sheen] 404 Image not found — url" in warnings(loggers)

    @pytest.mark.asyncio
    async def test_the_masterwork_border_is_loaded_once_per_patch(self, database, border, loggers):
        border.return_value = ["404 Image not found — url"]
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_items([(SHEEN, entry(SHEEN)), (GUNBLADE, entry(GUNBLADE))], FakeSession({}), patch,
                                    sources())

        border.assert_called_once()
        assert border.call_args.args[1] is patch and border.call_args.args[3] == "16.23"
        assert "[ITEM] [IMAGE] [Masterwork border] 404 Image not found — url" in warnings(loggers)

    @pytest.mark.asyncio
    async def test_an_item_missing_in_the_module_is_a_warning(self, database, loggers):
        await loader.load_all_items([(SHEEN, entry(SHEEN))], FakeSession({}), NewPatch(patch="16.23.1"),
                                    sources({GUNBLADE: ITEM_DATA[GUNBLADE]}))

        database.add_item.assert_called_once()
        assert "[ITEM] [WIKI] [Sheen] Not in Module:ItemData" in warnings(loggers)

    @pytest.mark.asyncio
    async def test_a_failing_item_does_not_stop_the_others(self, database, loggers):
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_items([("9999", entry(SHEEN)), (GUNBLADE, entry(GUNBLADE))], FakeSession({}), patch,
                                    sources())

        assert patch.loaded_item_count == 1
        loggers["load"].error.assert_called_once_with("[ITEM] Sheen ❌ Failed to load")

    @pytest.mark.asyncio
    async def test_skips_an_item_that_is_already_loaded(self, database):
        database.exists_item_by_item_id.return_value = True

        await loader.load_all_items([(SHEEN, entry(SHEEN))], FakeSession({}), NewPatch(patch="16.23.1"), sources())

        database.upsert_raw_item.assert_not_called()


class TestPatch():

    @pytest.mark.asyncio
    async def test_patches_old_items_and_loads_new_ones(self, database):
        database.fetch_items_by_patch.return_value = [stored_thornmail()]
        patch, old_patch = NewPatch(patch="16.23.1"), NewPatch(patch="16.22.1")
        notes = {"changed": {"Thornmail": [patch_note("Thorns damage changed")]}}
        items = [(THORNMAIL, entry(THORNMAIL)), (SHEEN, entry(SHEEN))]

        await loader.patch_all_items(items, notes, FakeSession({}), patch, old_patch, sources())

        stored = {call.args[0].item_id: call.args[0] for call in database.add_item.call_args_list}
        thornmail = stored[THORNMAIL]
        assert (thornmail.patch, thornmail.passives[0].rules[0].actions[0].props.amount) == ("16.23.1", "TotalDamage")
        assert [change.text for change in thornmail.changes] == ["Thorns damage changed"]
        assert not thornmail.validated  # named in the patch notes, but CDragon's numbers didn't change
        assert stored[SHEEN].name == "Sheen"
        assert (patch.item_count, patch.loaded_item_count, patch.changed_item_count) == (2, 2, 1)

    @pytest.mark.asyncio
    async def test_without_old_raw_data_the_stored_values_are_compared(self, database, loggers):
        database.fetch_items_by_patch.return_value = [stored_thornmail()]
        database.fetch_raw_item.return_value = None

        await loader.patch_all_items([(THORNMAIL, entry(THORNMAIL))], {}, FakeSession({}), NewPatch(patch="16.23.1"),
                                     NewPatch(patch="16.22.1"), sources())

        assert database.add_item.call_args.args[0].validated
        assert any("No raw data of the old patch" in warning for warning in warnings(loggers))

    @pytest.mark.asyncio
    async def test_an_item_gone_from_the_list_is_left_behind(self, database):
        database.fetch_items_by_patch.return_value = [stored_thornmail()]
        patch = NewPatch(patch="16.23.1")

        await loader.patch_all_items([(SHEEN, entry(SHEEN))], {}, FakeSession({}), patch, NewPatch(patch="16.22.1"),
                                     sources())

        assert [call.args[0].name for call in database.add_item.call_args_list] == ["Sheen"]
        assert patch.item_count == 1


class TestHotfix():

    @pytest.mark.asyncio
    async def test_adds_the_hotfix_lines_in_place(self, database):
        current = stored_thornmail("16.23.1")
        current.changes = [patch_note("Thorns damage changed")]
        database.fetch_items_by_patch.return_value = [current]
        database.fetch_raw_item.return_value = raw(THORNMAIL)
        patch, hotfixed_at = Patch(_id="0" * 24, patch="16.23.1", item_count=1), datetime(2026, 11, 27, 18)
        notes = {"Thornmail": [patch_note("Thorns damage changed"), patch_note("Grievous Wounds duration reduced")]}

        await loader.hotfix_all_items([(THORNMAIL, entry(THORNMAIL))], notes, FakeSession({}), patch, hotfixed_at,
                                      sources())

        updated = database.update_item.call_args.args[0]
        assert updated.id == current.id
        assert [(change.text, change.hotfix) for change in updated.changes] == [
            ("Thorns damage changed", None), ("Grievous Wounds duration reduced", hotfixed_at)]
        assert patch.changed_item_count == 0  # it already counted as changed in this patch

    @pytest.mark.asyncio
    async def test_an_item_not_in_the_patch_is_skipped(self, database, loggers):
        await loader.hotfix_all_items([(SHEEN, entry(SHEEN))], {}, FakeSession({}),
                                      Patch(_id="0" * 24, patch="16.23.1"), datetime.now(), sources())

        database.update_item.assert_not_called()
        assert "[ITEM] [HOTFIX] [Sheen] Not in patch 16.23.1, skipped" in warnings(loggers)
