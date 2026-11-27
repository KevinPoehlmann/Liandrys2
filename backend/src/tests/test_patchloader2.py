import pytest
import requests

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.server.loader.patchloader2 import (
    check_patch_available,
    _fetch_riot_patch_list,
    _get_newer_patches,
    wiki_hotfix_dates,
    _load_image_rune,
)
from src.server.loader.patchexceptions import PatcherError
from src.server.models.json_validation import PathJson


def test_fetch_riot_patch_list_valid(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = ["15.7.1", "15.6.1"]
    mocker.patch("requests.get", return_value=mock_response)

    result = _fetch_riot_patch_list()
    assert result == ["15.7.1", "15.6.1"]

@pytest.mark.parametrize("invalid_json", [
    {}, None, "notalist", [123], ["15.7.1"], ["15.7.1", 123]
])
def test_fetch_riot_patch_list_invalid(mocker, invalid_json):
    mock_response = mocker.Mock()
    mock_response.json.return_value = invalid_json
    mocker.patch("requests.get", return_value=mock_response)

    with pytest.raises(PatcherError):
        _fetch_riot_patch_list()


def test_get_newer_patches_with_existing_db_patch():
    class MockPatch: patch = "15.6.1"
    patches = ["15.7.1", "15.6.1", "15.5.1"]
    result = _get_newer_patches(MockPatch(), patches)
    assert result == ["15.7.1", "15.6.1"]

def test_get_newer_patches_without_db_patch():
    patches = ["15.7.1", "15.6.1"]
    result = _get_newer_patches(None, patches)
    assert result == ["15.7.1"]

def test_get_newer_patches_with_unlisted_patch():
    class MockPatch: patch = "14.9.1"
    patches = ["15.7.1", "15.6.1"]

    with pytest.raises(PatcherError):
        _get_newer_patches(MockPatch(), patches)


def test_wiki_hotfix_dates(mocker):
    wikitext = "|Release = March {{NumberSup|31}}, 2025\n== Hotfixes ==\n=== April 1st Hotfix ===\n== See Also =="
    response = mocker.Mock()
    response.json.return_value = {"query": {"pages": [{"revisions": [{"slots": {"main": {"content": wikitext}}}]}]}}
    get = mocker.patch("src.server.loader.patchloader2.requests.get", return_value=response)

    assert wiki_hotfix_dates("15.7.1") == [datetime(2025, 4, 1)]
    assert get.call_args.kwargs["params"]["titles"] == "V25.07"


def test_wiki_hotfix_dates_missing_page(mocker):
    response = mocker.Mock()
    response.json.return_value = {"query": {"pages": [{"title": "V25.07", "missing": True}]}}
    mocker.patch("src.server.loader.patchloader2.requests.get", return_value=response)

    with pytest.raises(PatcherError):
        wiki_hotfix_dates("15.7.1")


def test_wiki_hotfix_dates_invalid_response(mocker):
    response = mocker.Mock()
    response.raise_for_status.side_effect = requests.RequestException("Not Found")
    mocker.patch("src.server.loader.patchloader2.requests.get", return_value=response)

    with pytest.raises(PatcherError):
        wiki_hotfix_dates("15.7.1")


@pytest.mark.asyncio
async def test_check_patch_available_skips_the_loaded_patch(mocker, loaded_patch):
    mocker.patch("src.server.loader.patchloader2._fetch_riot_patch_list", return_value=["15.9.1", "15.8.1", "15.7.1"])
    mocker.patch("src.server.loader.patchloader2.db.fetch_patch_latest", return_value=loaded_patch)

    assert await check_patch_available() == ["15.8.1", "15.9.1"]


@pytest.mark.asyncio
async def test_check_patch_available_resumes_an_unfinished_patch(mocker, loaded_patch):
    loaded_patch.loaded_champion_count = 100
    loaded_patch.update_totals()
    mocker.patch("src.server.loader.patchloader2._fetch_riot_patch_list", return_value=["15.8.1", "15.7.1"])
    mocker.patch("src.server.loader.patchloader2.db.fetch_patch_latest", return_value=loaded_patch)

    assert await check_patch_available() == ["15.7.1", "15.8.1"]


@pytest.mark.asyncio
async def test_load_image_rune(mocker):
    icon = "perksStylesPrecision.png"
    session = AsyncMock()
    session.get_bytes.return_value = b"<fake image bytes>"

    # Patch: info_loader returns image/sprite paths
    mocker.patch(
        "src.server.loader.patchloader2.info_loader",
        return_value=SimpleNamespace(
            paths=PathJson(image= "mock/img", sprite= "mock/sprite",  cache= "mock/cache")
        )
    )

    # Patch: make .exists() return False so it tries to download
    mocker.patch("pathlib.Path.exists", return_value=False)

    # Patch: simulate writing to disk with no real I/O
    mocker.patch("pathlib.Path.mkdir", return_value=None)
    mocker.patch("pathlib.Path.write_bytes")

    # Act
    result = await _load_image_rune(icon, session)

    # Assert
    assert result.full == "perksStylesPrecision.png"
    assert result.group == "rune"
    session.get_bytes.assert_called_once()
