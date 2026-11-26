import pytest
import requests

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.error import HTTPError

from src.server.loader.helper import RuneClass
from src.server.loader.names import DDragonName, NameDictionary
from src.server.loader.patchloader2 import (
    check_patch_available,
    _fetch_riot_patch_list,
    _get_newer_patches,
    wiki_hotfix_dates,
    hotfix_others,
    _load_all_items,
    _load_all_runes,
    _load_all_summonerspells,
    _load_item,
    _load_rune,
    _load_rune_stat_shards,
    _load_summonerspell,
    _fetch_wiki_html,
    _wiki_name,
    _load_image,
    _load_image_rune,
    _load_rune_tree_images,
    _patch_items,
    _add_changes_item,
    _patch_runes,
    _find_rune,
    _add_changes_rune,
    _patch_summonerspells,
    _add_changes_summonerspell,
    _clean_up
)
from src.server.loader.patchexceptions import PatcherError, LoadError
from src.server.models.ability import Ability, ChampionAbility
from src.server.models.change import patch_note
from src.server.models.champion import NewChampion
from src.server.models.enums import RangeType, Stat
from src.server.models.image import Image
from src.server.models.item import NewItem
from src.server.models.json_validation import PathJson
from src.server.models.passive import Passive, ChampionPassive
from src.server.models.patch import NewPatch, Patch
from src.server.models.rune import NewRune
from src.server.models.summonerspell import NewSummonerspell



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
async def test_load_all_items_calls_each(mocker, loaded_patch):
    # Given
    item_list = [("1001", "ItemA"), ("1002", "ItemB")]
    mock_session = AsyncMock()

    # Mock _load_item
    mocked_load_item = mocker.patch("src.server.loader.patchloader2._load_item", new=AsyncMock())

    # When
    await _load_all_items(item_list, mock_session, loaded_patch)

    # Then
    assert mocked_load_item.call_count == len(item_list)
    mocked_load_item.assert_any_call("1001", "ItemA", mock_session, loaded_patch)
    mocked_load_item.assert_any_call("1002", "ItemB", mock_session, loaded_patch)


@pytest.mark.asyncio
async def test_load_all_runes_calls_each(mocker, loaded_patch):
    rune_list = ["Conqueror", "Electrocute"]
    mock_session = AsyncMock()

    # Patch _load_rune
    mocked_load_rune = mocker.patch("src.server.loader.patchloader2._load_rune", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2._load_rune_stat_shards", new=AsyncMock())

    await _load_all_runes(rune_list, mock_session, loaded_patch)

    assert mocked_load_rune.call_count == len(rune_list)
    mocked_load_rune.assert_any_call("Conqueror", mock_session, loaded_patch)
    mocked_load_rune.assert_any_call("Electrocute", mock_session, loaded_patch)


@pytest.mark.asyncio
async def test_load_all_summonerspells_calls_each(mocker, loaded_patch):
    summoner_list = ["Flash", "Ignite"]
    mock_session = AsyncMock()

    # Patch _load_summonerspell
    mocked_load_spell = mocker.patch("src.server.loader.patchloader2._load_summonerspell", new=AsyncMock())

    await _load_all_summonerspells(summoner_list, mock_session, loaded_patch)

    assert mocked_load_spell.call_count == len(summoner_list)
    mocked_load_spell.assert_any_call("Flash", mock_session, loaded_patch)
    mocked_load_spell.assert_any_call("Ignite", mock_session, loaded_patch)




@pytest.mark.asyncio
async def test_load_item_success(mocker, loaded_patch):
    item_id = "3031"
    item_json = mocker.Mock()
    item_json.name = "Infinity Edge"
    item_json.image = mocker.Mock(full="infinity_edge.png")

    item_obj = mocker.Mock()
    item_obj.name = "Infinity Edge"

    item_masterwork_obj = mocker.Mock()
    item_masterwork_obj.name = "Infinity Edge"

    session = AsyncMock()

    mocker.patch("src.server.loader.patchloader2.db.exists_item_by_item_id", return_value=False)

    # Mock wiki fetch
    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>infinity</html>")

    # Mock item logic
    ws_create_item = mocker.patch(
        "src.server.loader.patchloader2.ws.scrape_item",
        side_effect=[item_obj, item_masterwork_obj]
    )

    # Mock image + DB
    mocker.patch("src.server.loader.patchloader2._load_image", new=AsyncMock())
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_item", new=AsyncMock())

    await _load_item(item_id, item_json, session, loaded_patch)
    assert ws_create_item.called

    assert mock_add.call_count == 1


@pytest.mark.asyncio
async def test_load_rune_success(mocker, loaded_patch):
    rune = mocker.Mock()
    rune.name = "Electrocute"
    rune.icon = "path/to/electrocute.png"
    rune_class = mocker.Mock(rune=rune)

    session = AsyncMock()

    mocker.patch("src.server.loader.patchloader2.db.exists_rune_by_name", return_value=False)

    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>rune</html>")
    mocker.patch("src.server.loader.patchloader2._load_image_rune", return_value="rune_image")

    class DummyRune:
        name = "Mock Rune"
        patch = "14.12"
        validated = True
    mocker.patch("src.server.loader.patchloader2.ws.scrape_rune", return_value=DummyRune())
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_rune", new=AsyncMock())

    await _load_rune(rune_class, session, loaded_patch)

    assert mock_add.called


@pytest.mark.asyncio
async def test_load_summonerspell_success(mocker, loaded_patch, smite):
    spell_json = mocker.Mock()
    spell_json.name = "Flash"
    spell_json.image = mocker.Mock(full="flash.png")

    session = AsyncMock()

    mocker.patch("src.server.loader.patchloader2.db.exists_summonerspell_by_key", return_value=False)

    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>flash</html>")
    mocker.patch("src.server.loader.patchloader2.ws.scrape_summonerspell", return_value=smite)
    mocker.patch("src.server.loader.patchloader2._load_image", new=AsyncMock())
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_summonerspell", new=AsyncMock())

    await _load_summonerspell(spell_json, session, loaded_patch)

    assert mock_add.called



def test_wiki_name_comes_from_the_name_dictionary(mocker):
    names = NameDictionary({"3153": "Blade of the Ruined King"}, [DDragonName("3153", "Blade of The Ruined King")])
    mocker.patch("src.server.loader.patchloader2.WIKI_NAMES", {"items": names})

    assert _wiki_name("items", "3153", "Blade of The Ruined King") == "Blade of the Ruined King"
    assert _wiki_name("runes", "8010", "Jack Of All Trades") == "Jack Of All Trades"


@pytest.mark.asyncio
async def test_fetch_wiki_html_fetches_the_given_page(mocker, loaded_patch):
    session = AsyncMock()
    session.get_html.return_value = "<html>page</html>"
    mocker.patch("src.server.loader.patchloader2.URLS.wiki", "https://wiki/")

    result = await _fetch_wiki_html("Fancy Sword", "Item", loaded_patch, session)

    session.get_html.assert_called_once_with("https://wiki/Fancy Sword")
    assert result == "<html>page</html>"

@pytest.mark.asyncio
async def test_fetch_wiki_html_raises_loaderror_on_http_error(mocker, loaded_patch):
    session = AsyncMock()
    session.get_html.side_effect = HTTPError(
        url="https://wiki/missing",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None
    )

    mocker.patch("src.server.loader.patchloader2.URLS.wiki", "https://wiki/")

    with pytest.raises(LoadError) as exc:
        await _fetch_wiki_html("MissingItem", "Item", loaded_patch, session)

    assert exc.value.code == 404
    assert exc.value.name == "MissingItem"
    assert exc.value.type == "Item"



@pytest.mark.asyncio
async def test_load_image_downloads_file(mocker):
    image = mocker.Mock()
    image.full = "icon.png"
    image.group = "champion"
    image.sprite = None
    image.x = 0
    image.y = 0

    session = AsyncMock()
    session.get_bytes.return_value = b"fake_image_data"

    # Patch path config
    mocker.patch("src.server.loader.patchloader2.info_loader", return_value=SimpleNamespace(
        paths=PathJson(image="mock/img", sprite="mock/sprite", cache="mock/cache")
    ))

    # Patch URL paths
    mocker.patch("src.server.loader.patchloader2.URLS.dataLink", "https://riot.cdn/")
    mocker.patch("src.server.loader.patchloader2.URLS.image", "img/")
    mocker.patch("src.server.loader.patchloader2.URLS.sprite", "sprite/")

    # Patch only the .exists() and .mkdir() methods — not Path itself
    mocker.patch("pathlib.Path.exists", return_value=False)
    mocker.patch("pathlib.Path.mkdir", return_value=None)

    # Patch file writing
    mocked_write = mocker.patch("pathlib.Path.write_bytes")

    # Run the function
    await _load_image(image, session, NewPatch(patch="15.8.1"))

    # Assertions
    session.get_bytes.assert_called_once_with("https://riot.cdn/15.8.1/img/champion/icon.png")
    mocked_write.assert_called_once_with(b"fake_image_data")



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





@pytest.mark.asyncio
async def test_patch_items(mocker):
    patch_obj = NewPatch(patch="15.8.1")
    session = AsyncMock()

    # Existing item in DB
    existing_item = NewItem(
        item_id="3071",
        name="Black Cleaver",
        patch="15.8.0",
        gold=3000,
        into=[],
        from_=[],
        stats={},
        masterwork={},
        validated=True,
        image=Image(
            full="Black Cleaver.png",
            group="items"
        ),
        active=None,
        passives=[],
        limitations="",
        requirements="",
        maps=[],
        changes=[]
    )
    mocker.patch("src.server.loader.patchloader2.db.fetch_items_by_patch", return_value=[existing_item])
    mock_add_item = mocker.patch("src.server.loader.patchloader2.db.add_item")
    mock_load_item = mocker.patch("src.server.loader.patchloader2._load_item")

    # Riot API item structure
    riot_item_data = {
        "type": "Item",
        "version": "15.8.1",
        "basic": {},
        "data": {
            "3071": {
                "name": "Black Cleaver",
                "description": "",
                "colloq": "",
                "plaintext": "",
                "gold": {
                    "base": 500,
                    "purchasable": True,
                    "total": 3000,
                    "sell": 2100
                },
                "from": [],
                "into": [],
                "image": Image(
                    full="Black Cleaver.png",
                    group="items"
                ),
                "maps": {"11": True},
                "tags": [],
                "stats": {}
            },
            "7000": {
                "name": "Mythic Cleaver",
                "description": "",
                "colloq": "",
                "plaintext": "",
                "gold": {
                    "base": 500,
                    "purchasable": True,
                    "total": 3000,
                    "sell": 2100
                },
                "from": [],
                "into": [],
                "image": Image(
                    full="Black Cleaver.png",
                    group="items"
                ),
                "maps": {"11": True},
                "tags": [],
                "stats": {}
            }
        },
        "groups": [],
        "tree": []
    }
    session.get_json.return_value = riot_item_data

    changes = {
        "new": ["Mythic Cleaver"],
        "changed": {"Black Cleaver": [patch_note("Cooldown reduced")]},
        "deleted": []
    }

    await _patch_items(changes, patch_obj, patch_obj, session)

    mock_load_item.assert_called_once()
    mock_add_item.assert_called()



@pytest.mark.asyncio
async def test_patch_runes(mocker):
    patch_obj = NewPatch(patch="15.8.1")
    session = AsyncMock()

    # Mock existing rune
    existing_rune = NewRune(
        rune_id=8126,
        name="Cheap Shot",
        patch="15.8.0",
        tree="Domination",
        tree_id=8100,
        row=0,
        slot=1,
        passive=Passive(name="Cheap Shot"),
        image=Image(
            full="Cheap_Shot.png",
            group="runes"
        )
    )
    mocker.patch("src.server.loader.patchloader2.db.fetch_runes_by_patch", return_value=[existing_rune])
    mock_add_rune = mocker.patch("src.server.loader.patchloader2.db.add_rune")
    mock_load_rune = mocker.patch("src.server.loader.patchloader2._load_rune")

    # Rune data as from Riot API (runesReforged.json)
    mock_runes_data = [{
        "id": 8100,
        "key": "i really dont know",
        "name": "Domination",
        "icon": "domination.png",
        "slots": [
            {
                "runes": [
                    {"id": 8124, "key": "hmm", "name": "Electrocute", "icon": "electrocute.png", "shortDesc": "123", "longDesc": "1234"},
                    {"id": 8126, "key": "hmm", "name": "Cheap Shot", "icon": "cheapshot.png", "shortDesc": "123", "longDesc": "1234"},
                ]
            }
        ]
    }]
    session.get_json.return_value = mock_runes_data

    changes = {
        "new": ["Electrocute"],
        "changed": {"Cheap Shot": [patch_note("Effect clarified")]},
        "deleted": []
    }

    await _patch_runes(changes, patch_obj, patch_obj, session)

    # Load was called for new rune
    mock_load_rune.assert_called_once()
    # Add was called for updated rune
    mock_add_rune.assert_called()


def test_find_rune_success():
    mock_rune = {
        "id": 8100,
        "key": "i really dont know",
        "name": "Domination",
        "icon": "domination.png",
        "slots": [
            {
                "runes": [
                    {"id": 8124, "key": "hmm", "name": "Electrocute", "icon": "electrocute.png", "shortDesc": "123", "longDesc": "1234"},
                    {"id": 8126, "key": "hmm", "name": "Cheap Shot", "icon": "cheapshot.png", "shortDesc": "123", "longDesc": "1234"},
                ]
            }
        ]
    }

    result = _find_rune("Electrocute", [mock_rune])
    assert isinstance(result, RuneClass)
    assert result.rune.name == "Electrocute"
    assert result.tree == "Domination"
    assert result.tree_id == 8100
    assert result.row == 0

def test_find_rune_not_found():
    result = _find_rune("Unseen Rune", {})
    assert result is None



@pytest.mark.asyncio
async def test_patch_summonerspells(mocker):
    patch_obj = NewPatch(patch="15.8.1")
    session = AsyncMock()

    # Mocks
    mock_fetch_old = mocker.patch("src.server.loader.patchloader2.db.fetch_summonerspells_by_patch")
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_summonerspell")
    mock_load = mocker.patch("src.server.loader.patchloader2._load_summonerspell")
    #mock_get_json = mocker.patch("src.server.loader.patchloader2.SafeSession.get_json")

    # Setup
    existing = NewSummonerspell(key="walk fast", name="Ghost", patch="15.8.0", ability=Ability(name="Ghost"), validated=True, image=Image(full="ghost.png", group="summonerspell"))
    mock_fetch_old.return_value = [existing]

    riot_api_data = {
        "type": "Summonerspells",
        "version": "15.8.1",
        "data": {
            "Flash": {
                "id": "Flash",
                "name": "Flash",
                "description": "Teleports your champion a short distance toward your cursor's location.",
                "tooltip": "Flash forward a short distance.",
                "maxrank": 1,
                "cooldown": [300],
                "cooldownBurn": "300",
                "cost": [0],
                "costBurn": "0",
                "datavalues": {},
                "effect": [],
                "effectBurn": [],
                "vars": [],
                "key": "4",
                "summonerLevel": 1,
                "modes": ["CLASSIC"],
                "costType": "No Cost",
                "maxammo": "1",
                "range": [425],
                "rangeBurn": "425",
                "image": {
                    "full": "SummonerFlash.png",
                    "sprite": "spell0.png",
                    "group": "summoner",
                    "x": 0,
                    "y": 0,
                    "w": 48,
                    "h": 48
                },
                "resource": "None"
            },
            "Ghost": {
                "id": "Ghost",
                "name": "Ghost",
                "description": "Gain movement speed and ignore unit collision.",
                "tooltip": "Grants bonus movement speed and ghosting.",
                "maxrank": 1,
                "cooldown": [210],
                "cooldownBurn": "210",
                "cost": [0],
                "costBurn": "0",
                "datavalues": {},
                "effect": [],
                "effectBurn": [],
                "vars": [],
                "key": "6",
                "summonerLevel": 1,
                "modes": ["CLASSIC"],
                "costType": "No Cost",
                "maxammo": "1",
                "range": [0],
                "rangeBurn": "0",
                "image": {
                    "full": "SummonerHaste.png",
                    "sprite": "spell0.png",
                    "group": "summoner",
                    "x": 0,
                    "y": 0,
                    "w": 48,
                    "h": 48
                },
                "resource": "None"
            }
        }
    }

    session.get_json.return_value = riot_api_data

    changes = {
        "new": ["Flash"],
        "changed": {"Ghost": [patch_note("Cooldown reduced from 210 to 180")]},
        "deleted": []
    }

    await _patch_summonerspells(changes, patch_obj, patch_obj, session)

    mock_load.assert_called_once()
    mock_add.assert_called()



@pytest.mark.asyncio
async def test_load_rune_stat_shards_as_stat_modifiers(mocker, loaded_patch):
    mocker.patch("src.server.loader.patchloader2.db.exists_rune_by_name", new=AsyncMock(return_value=False))
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_rune", new=AsyncMock())

    await _load_rune_stat_shards(loaded_patch)

    stats = {call.args[0].name: call.args[0].passive.stats for call in mock_add.call_args_list}
    [movement_speed] = stats["Flex Movementspeed"]
    assert (movement_speed.stat, movement_speed.formula) == (Stat.MOVESPEED_P, "0.02")  # 2 %, stored as a fraction
    [scaling_health] = stats["Defense Scaling Health"]
    assert (scaling_health.stat, scaling_health.formula) == (Stat.HP, "10 * level")


@pytest.mark.asyncio
async def test_hotfix_others_changes_the_named_objects_in_place(mocker, loaded_patch):
    sheen = SimpleNamespace(name="Sheen", changes=[patch_note("Cost reduced")], validated=True)
    thornmail = SimpleNamespace(name="Thornmail", changes=[], validated=True)
    ghost = SimpleNamespace(name="Ghost", changes=[], validated=True)
    for type_, documents in (("items", [sheen, thornmail]), ("runes", []), ("summonerspells", [ghost])):
        mocker.patch(f"src.server.loader.patchloader2.db.fetch_{type_}_by_patch", new=AsyncMock(return_value=documents))
    update_item = mocker.patch("src.server.loader.patchloader2.db.update_item", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2.db.update_rune", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2.db.update_summonerspell", new=AsyncMock())
    notes = {"items": {"changed": {"Sheen": [patch_note("Cost reduced"), patch_note("Damage increased")]}},
             "summonerspells": {"changed": {"Ghost": [patch_note("Cooldown reduced")]}}}

    await hotfix_others(notes, loaded_patch)

    assert [change.text for change in sheen.changes] == ["Cost reduced", "Damage increased"]
    assert not sheen.validated and not ghost.validated
    assert thornmail.validated
    update_item.assert_called_once_with(sheen)
    # Sheen already changed in this patch, Ghost is new to the count.
    assert (loaded_patch.changed_item_count, loaded_patch.changed_summonerspell_count) == (0, 1)
