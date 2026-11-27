import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

import src.server.loader.patchloader as loader
from src.server.models.change import patch_note
from src.server.models.patch import NewPatch, Patch
from src.server.models.summonerspell import Summonerspell
from src.tests.test_patchloader import BUILD, CDRAGON, FakeSession
from src.tests.test_summonerspell_builder import IGNITE, entry, raw


def module_response(text: str) -> dict:
    return {"query": {"pages": [{"title": "Module:SpellData/data", "revisions": [{"slots": {"main": {"content": text}}}]}]}}


def article(title: str) -> dict:
    text = "{{Spell info|Ignite}}\n== Notes ==\n* Ignite deals proc damage."
    return {"query": {"pages": [{"title": title, "revisions": [{"revid": 42, "slots": {"main": {"content": text}}}]}]}}


def stored_ignite(patch: str = "16.22.1") -> Summonerspell:
    spell = json.loads(IGNITE.read_text(encoding="utf-8")) | {"patch": patch}
    return Summonerspell.parse_obj(spell)


@pytest.fixture
def session() -> FakeSession:
    return FakeSession({
        "content-metadata.json": {"version": BUILD},
        "shared.cdtb.bin.json": json.loads((CDRAGON / "summonerspells.bin.json").read_text(encoding="utf-8")),
        "lol.stringtable.json": json.loads((CDRAGON / "summonerspells.strings.json").read_text(encoding="utf-8")),
        "SpellData": module_response((CDRAGON / "spell_data.lua").read_text(encoding="utf-8")),
        "titles=Ignite&": article("Ignite"),
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
    monkeypatch.setattr(loader, "load_summonerspell_image", mock)
    return mock


@pytest.fixture
def database(monkeypatch) -> Mock:
    mock = Mock(exists_summonerspell_by_key=AsyncMock(return_value=False), upsert_raw_summonerspell=AsyncMock(),
                add_summonerspell=AsyncMock(), update_summonerspell=AsyncMock(),
                fetch_summonerspells_by_patch=AsyncMock(return_value=[]),
                fetch_raw_summonerspell=AsyncMock(return_value=raw(patch="16.22.1")))
    monkeypatch.setattr(loader, "db", mock)
    return mock


def warnings(loggers) -> list[str]:
    return [call.args[0] for call in loggers["patch"].warning.call_args_list]


class TestLoad():

    @pytest.mark.asyncio
    async def test_stores_raw_data_and_spell(self, session, database):
        patch = NewPatch(patch="16.23.1", summonerspell_count=1)

        await loader.load_all_summonerspells([entry()], session, patch)

        stored_raw = database.upsert_raw_summonerspell.call_args.args[0]
        spell = database.add_summonerspell.call_args.args[0]
        assert (stored_raw.key, stored_raw.build, stored_raw.spell_data["cooldown"]) == ("SummonerDot", BUILD, "180")
        assert (stored_raw.wiki.title, stored_raw.wiki.revision_id) == ("Ignite", 42)
        assert spell.ability.values["GrievousAmount"] == "0.4"
        database.add_summonerspell.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_missing_article_and_module_are_warnings(self, session, database, loggers):
        del session.responses["titles=Ignite&"], session.responses["SpellData"]

        await loader.load_all_summonerspells([entry()], session, NewPatch(patch="16.23.1"))

        database.add_summonerspell.assert_called_once()
        assert "[SUMMONERSPELL] [WIKI] [Ignite] No wiki article found" in warnings(loggers)
        assert any("Module:SpellData not loaded" in warning for warning in warnings(loggers))

    @pytest.mark.asyncio
    async def test_a_failing_spell_does_not_stop_the_others(self, session, database, loggers):
        unknown = entry("SummonerSmite").copy(update={"id_": "SummonerUnknown"})
        patch = NewPatch(patch="16.23.1")

        await loader.load_all_summonerspells([unknown, entry()], session, patch)

        database.add_summonerspell.assert_called_once()
        loggers["load"].error.assert_called_once_with("[SUMMONERSPELL] Smite ❌ Failed to load")

    @pytest.mark.asyncio
    async def test_skips_a_spell_that_is_already_loaded(self, session, database):
        database.exists_summonerspell_by_key.return_value = True

        await loader.load_all_summonerspells([entry()], session, NewPatch(patch="16.23.1"))

        database.upsert_raw_summonerspell.assert_not_called()

    @pytest.mark.asyncio
    async def test_image_failures_are_warnings(self, session, database, loggers, images):
        images.return_value = ["404 Image not found — url"]

        await loader.load_all_summonerspells([entry()], session, NewPatch(patch="16.23.1"))

        assert images.call_args.args[3] == "16.23"
        assert "[SUMMONERSPELL] [IMAGE] [Ignite] 404 Image not found — url" in warnings(loggers)


class TestPatch():

    @pytest.mark.asyncio
    async def test_patches_old_spells_and_loads_new_ones(self, session, database):
        database.fetch_summonerspells_by_patch.return_value = [stored_ignite()]
        patch, old_patch = NewPatch(patch="16.23.1"), NewPatch(patch="16.22.1")
        notes = {"changed": {"Ignite": [patch_note("Grievous Wounds duration changed")]}}

        await loader.patch_all_summonerspells([entry(), entry("SummonerFlash")], notes, session, patch, old_patch)

        ignite, flash = [call.args[0] for call in database.add_summonerspell.call_args_list]
        assert (ignite.patch, ignite.ability.cooldown) == ("16.23.1", "cooldownTime")  # the hand-made part stays
        assert [change.text for change in ignite.changes] == ["Grievous Wounds duration changed"]
        assert not ignite.validated  # named in the patch notes, but CDragon's numbers didn't change
        assert flash.name == "Flash"
        assert patch.summonerspell_count == 2

    @pytest.mark.asyncio
    async def test_without_old_raw_data_the_stored_values_are_compared(self, session, database, loggers):
        database.fetch_summonerspells_by_patch.return_value = [stored_ignite()]
        database.fetch_raw_summonerspell.return_value = None
        patch = NewPatch(patch="16.23.1")

        await loader.patch_all_summonerspells([entry()], {}, session, patch, NewPatch(patch="16.22.1"))

        assert database.add_summonerspell.call_args.args[0].validated
        assert any("No raw data of the old patch" in warning for warning in warnings(loggers))

    @pytest.mark.asyncio
    async def test_a_spell_gone_from_the_list_is_left_behind(self, session, database):
        database.fetch_summonerspells_by_patch.return_value = [stored_ignite()]
        patch = NewPatch(patch="16.23.1")

        await loader.patch_all_summonerspells([entry("SummonerFlash")], {}, session, patch, NewPatch(patch="16.22.1"))

        assert [call.args[0].name for call in database.add_summonerspell.call_args_list] == ["Flash"]
        assert patch.summonerspell_count == 1


class TestHotfix():

    @pytest.mark.asyncio
    async def test_adds_the_hotfix_lines_in_place(self, session, database):
        current = stored_ignite("16.23.1")
        current.changes = [patch_note("Damage increased")]
        database.fetch_summonerspells_by_patch.return_value = [current]
        database.fetch_raw_summonerspell.return_value = raw()
        patch, hotfixed_at = Patch(_id="0" * 24, patch="16.23.1", summonerspell_count=1), datetime(2026, 11, 27, 18)
        notes = {"Ignite": [patch_note("Damage increased"), patch_note("Cooldown reduced")]}

        await loader.hotfix_all_summonerspells([entry()], notes, session, patch, hotfixed_at)

        updated = database.update_summonerspell.call_args.args[0]
        assert updated.id == current.id
        assert [(change.text, change.hotfix) for change in updated.changes] == [("Damage increased", None),
                                                                                ("Cooldown reduced", hotfixed_at)]

    @pytest.mark.asyncio
    async def test_nothing_to_hotfix_downloads_nothing(self, session, database):
        await loader.hotfix_all_summonerspells([], {}, session, Patch(_id="0" * 24, patch="16.23.1"), datetime.now())

        assert session.urls == []
