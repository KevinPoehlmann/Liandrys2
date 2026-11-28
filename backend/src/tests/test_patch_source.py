from datetime import datetime
from types import SimpleNamespace

import pytest

from src.server.loader.patch_source import (fetch_patch_list, new_on_pbe, patches_to_load, preview_is_current,
                                            preview_name)
from src.server.loader.patchexceptions import PatcherError
from src.server.models.patch import NewPatch
from src.tests.test_patchloader import FakeSession


class TestFetchPatchList():

    @pytest.mark.asyncio
    async def test_returns_riots_list(self):
        assert await fetch_patch_list(FakeSession({"versions.json": ["15.8.1", "15.7.1"]})) == ["15.8.1", "15.7.1"]


    @pytest.mark.asyncio
    @pytest.mark.parametrize("versions", [{}, "notalist", [123], ["15.7.1"], ["15.7.1", 123]])
    async def test_a_wrong_shape_is_an_error(self, versions):
        with pytest.raises(PatcherError):
            await fetch_patch_list(FakeSession({"versions.json": versions}))


    @pytest.mark.asyncio
    async def test_a_missing_list_is_an_error(self):
        with pytest.raises(PatcherError):
            await fetch_patch_list(FakeSession({}))


class TestPatchesToLoad():

    def test_an_empty_database_loads_the_newest_patch(self):
        assert patches_to_load(None, ["15.8.1", "15.7.1"]) == ["15.8.1"]


    def test_skips_the_loaded_patch_oldest_first(self, loaded_patch):
        assert patches_to_load(loaded_patch, ["15.9.1", "15.8.1", "15.7.1", "15.6.1"]) == ["15.8.1", "15.9.1"]


    def test_resumes_an_unfinished_patch(self, loaded_patch):
        loaded_patch.loaded_champion_count = 100
        loaded_patch.update_totals()

        assert patches_to_load(loaded_patch, ["15.8.1", "15.7.1"]) == ["15.7.1", "15.8.1"]


    def test_up_to_date_is_nothing(self, loaded_patch):
        assert patches_to_load(loaded_patch, ["15.7.1", "15.6.1"]) == []


    def test_a_patch_missing_from_riots_list_is_an_error(self):
        with pytest.raises(PatcherError):
            patches_to_load(NewPatch(patch="14.9.1"), ["15.7.1", "15.6.1"])


PBE_BUILD = "16.24.8420984+branch.main.content.beta"


class TestPreviewName():

    def test_the_pbe_build_names_the_coming_patch(self):
        assert preview_name(PBE_BUILD) == "16.24.1"


    def test_a_build_without_a_version_is_an_error(self):
        with pytest.raises(PatcherError):
            preview_name("main")


class TestPreviewIsCurrent():

    @pytest.fixture
    def live(self) -> NewPatch:
        return NewPatch(patch="16.23.1", timestamp=datetime(2026, 11, 20, 9, 0))


    @pytest.fixture
    def preview(self) -> NewPatch:
        return NewPatch(patch="16.24.1", preview=True, build=PBE_BUILD, timestamp=datetime(2026, 11, 25, 9, 0))


    def test_same_patch_and_build_is_current(self, preview, live):
        assert preview_is_current(preview, "16.24.1", PBE_BUILD, live)


    def test_a_new_pbe_build_is_not(self, preview, live):
        assert not preview_is_current(preview, "16.24.1", "16.24.8430000+branch.main.content.beta", live)


    def test_an_interrupted_load_has_no_build_yet(self, preview, live):
        preview.build = None

        assert not preview_is_current(preview, "16.24.1", PBE_BUILD, live)


    def test_a_live_hotfix_after_the_preview_reloads_it(self, preview, live):
        # The preview copies the live patch's hand-made part and compares with its numbers.
        live.updated_at = datetime(2026, 11, 26, 12, 0)

        assert not preview_is_current(preview, "16.24.1", PBE_BUILD, live)


    def test_a_live_patch_loaded_after_the_preview_reloads_it(self, preview, live):
        # A database catching up several patches: the preview was built from an older live patch.
        live.timestamp = datetime(2026, 11, 26, 12, 0)

        assert not preview_is_current(preview, "16.24.1", PBE_BUILD, live)


def test_new_on_pbe_skips_live_champions_and_mode_copies():
    champions = [SimpleNamespace(key="1"), SimpleNamespace(key="254")]
    summary = [{"id": -1, "alias": "None"}, {"id": 1, "alias": "Annie"}, {"id": 254, "alias": "Vi"},
               {"id": 60001, "alias": "Jade_Annie"}, {"id": 951, "alias": "Newcomer"}]

    assert new_on_pbe(summary, champions) == ["Newcomer"]
