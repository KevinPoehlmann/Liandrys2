import json
import pytest

from datetime import datetime

from src.server.loader.patchloader import Patchloader, Todo, TodoType
from src.server.models.patch import NewPatch



@pytest.fixture()
def clean_Patchloader():
    yield
    Patchloader.mute = False
    Patchloader.todo = []

@pytest.fixture()
def version1321_json():
    with open("src/tests/files/versions1321.json") as versions:
        return json.load(versions)


@pytest.fixture()
def version1322_json():
    with open("src/tests/files/versions1322.json") as versions:
        return json.load(versions)


@pytest.fixture()
def champion_json():
    with open("src/tests/files/champion.json", encoding='UTF-8') as champion:
        return json.load(champion)


@pytest.fixture()
def item_json():
    with open("src/tests/files/item.json", encoding='UTF-8') as item:
        return json.load(item)


@pytest.fixture()
def runesReforged_json():
    with open("src/tests/files/runesReforged.json", encoding='UTF-8') as rune:
        return json.load(rune)


@pytest.fixture()
def summoner_json():
    with open("src/tests/files/summoner.json", encoding='UTF-8') as summoner:
        return json.load(summoner)


@pytest.fixture()
def patch1321():
    with open("src/tests/files/Patch1321.html", encoding="utf-8") as patch:
        by = patch.read()
        return by.encode("utf-8")
    


@pytest.fixture()
def db_fake_patch():
    patch = NewPatch(
        patch="13.21.1",
        champion_count=0,
        item_count=0,
        rune_count=0,
        summonerspell_count=0,
        document_count=0
    )
    return patch


@pytest.fixture()
def db_fake_patch_hotfix():
    patch = NewPatch(
        patch="13.21.1",
        hotfix=datetime(2023, 10, 26),
        champion_count=0,
        item_count=0,
        rune_count=0,
        summonerspell_count=0,
        document_count=0
    )
    return patch


@pytest.fixture()
def db_fake_patch_uptodate():
    patch = NewPatch(
        patch="13.21.1",
        hotfix=datetime(2023, 10, 27),
        champion_count=0,
        item_count=0,
        rune_count=0,
        summonerspell_count=0,
        document_count=0
    )
    return patch









