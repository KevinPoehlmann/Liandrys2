import pytest

from src.server.loader.patch_source import fetch_patch_list, patches_to_load
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
