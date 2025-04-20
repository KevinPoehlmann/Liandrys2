import pytest
import requests

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, mock_open
from urllib.error import HTTPError

from src.server.loader.helper import RuneClass
from src.server.loader.patchloader2 import (
    load_data,
    check_patch_available,
    _fetch_riot_patch_list,
    _get_newer_patches,
    _check_wiki_for_hotfixes,
    _get_newer_hotfixes,
    _load_fresh_database,
    _list_data,
    _load_all_champions,
    _load_all_items,
    _load_all_runes,
    _load_all_summonerspells,
    _load_champion,
    _load_item,
    _load_rune,
    _load_summonerspell,
    _fetch_wiki_html,
    _load_image,
    _load_image_rune,
    _load_rune_tree_images,
    _load_all_patches,
    _load_patch,
    _patch_champions,
    _add_changes_champion,
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
from src.server.models.champion import NewChampion
from src.server.models.dataenums import RangeType
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


@pytest.mark.asyncio
async def test_check_wiki_for_hotfixes(mocker):
    mock_response = mocker.Mock()
    mock_response.ok = True
    mock_response.text = "<html>Some wiki patch content</html>"

    mock_session = mocker.Mock()
    mock_session.get.return_value = mock_response
    mocker.patch("src.server.loader.patchloader2.HTMLSession", return_value=mock_session)

    mock_hotfix_list = [datetime(2025, 4, 1)]
    mocker.patch("src.server.loader.patchloader2.ws.scrape_hotfix_list", return_value=mock_hotfix_list)

    result = await _check_wiki_for_hotfixes(["15.7.1"])
    assert result == {"15.7.1": mock_hotfix_list}

@pytest.mark.asyncio
async def test_check_wiki_for_hotfixes_invalid_response(mocker):
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = requests.RequestException("Not Found")

    mocker.patch("src.server.loader.patchloader2.requests.get", return_value=mock_response)

    mocker.patch("src.server.loader.patchloader2.ws.scrape_hotfix_list")

    with pytest.raises(PatcherError):
        await _check_wiki_for_hotfixes(["15.7.1"])



@pytest.mark.parametrize("hotfix_list, expected", [
    (
        [datetime(2024, 4, 6, 13, 0), datetime(2024, 4, 6, 11, 0)],
        {"15.7.1": [datetime(2024, 4, 6, 13, 0)]}
    ),
    (
        [datetime(2024, 4, 6, 14, 0), datetime(2024, 4, 6, 13, 0)],
        {"15.7.1": [datetime(2024, 4, 6, 14, 0), datetime(2024, 4, 6, 13, 0)]}
    ),
    (
        [datetime(2024, 4, 6, 12, 0), datetime(2024, 4, 6, 11, 0)],
        {}
    ),
])
def test_get_newer_hotfixes_with_hotfix_param(patch_with_hotfix, hotfix_list, expected):
    hotfixes = {"15.7.1": hotfix_list}
    result = _get_newer_hotfixes(patch_with_hotfix, hotfixes)
    assert result == expected

@pytest.mark.parametrize("hotfix_list, expected", [
    (
        [datetime(2024, 4, 6, 13, 0), datetime(2024, 4, 6, 11, 0)],
        {"15.7.1": [datetime(2024, 4, 6, 13, 0)]}
    ),
    (
        [],
        {"15.7.1": []}
    ),
])
def test_get_newer_hotfixes_without_dbpatch(hotfix_list, expected):
    hotfixes = {"15.7.1": hotfix_list}
    result = _get_newer_hotfixes(None, hotfixes)
    assert result == expected

@pytest.mark.parametrize("hotfix_list, expected", [
    (
        [datetime(2024, 4, 6, 13, 0), datetime(2024, 4, 6, 11, 0)],
        {"15.7.1": [datetime(2024, 4, 6, 13, 0), datetime(2024, 4, 6, 11, 0)]}
    ),
    (
        [datetime(2024, 4, 6, 11, 0)],
        {"15.7.1": [datetime(2024, 4, 6, 11, 0)]}
    ),
    (
        [],
        {}
    )
])
def test_get_newer_hotfixes_without_hotfix_param(patch_without_hotfix, hotfix_list, expected):
    hotfixes = {"15.7.1": hotfix_list}
    result = _get_newer_hotfixes(patch_without_hotfix, hotfixes)
    assert result == expected



@pytest.mark.asyncio
async def test_check_patch_available(mocker):
    mocker.patch("src.server.loader.patchloader2._fetch_riot_patch_list", return_value=["15.7.1", "15.6.1"])
    mocker.patch("src.server.loader.patchloader2.db.fetch_patch_latest", return_value=mocker.Mock(patch="15.6.1", hotfix=None))
    mocker.patch("src.server.loader.patchloader2._get_newer_patches", return_value=["15.7.1", "15.6.1"])
    mocker.patch("src.server.loader.patchloader2._check_wiki_for_hotfixes", return_value={"15.7.1": [], "15.6.1": []})

    result = await check_patch_available()
    assert result == {"15.7.1": []}



@pytest.mark.asyncio
async def test_load_fresh_database_success(mocker):
    mock_patch = "15.7.1"
    mock_hotfix = datetime(2024, 4, 8)
    hotfixes = {mock_patch: [mock_hotfix]}

    # Mock _list_data to return dummy objects
    mocker.patch("src.server.loader.patchloader2._list_data", return_value=(
        ["Ahri", "Garen"],            # champion_list
        [("1001", "item")],          # item_list
        ["rune"],                    # rune_list
        ["Flash"],                   # summoner_list
    ))

    # Mock all loading functions (don't actually load anything)
    mocker.patch("src.server.loader.patchloader2._load_all_champions", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2._load_all_items", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2._load_all_runes", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2._load_all_summonerspells", new=AsyncMock())

    # Mock db.add_patch
    mock_add_patch = mocker.patch("src.server.loader.patchloader2.db.add_patch", new=AsyncMock())

    # Run the function
    await _load_fresh_database(hotfixes)

    # Assert patch was added
    assert mock_add_patch.called

@pytest.mark.asyncio
async def test_load_fresh_database_failure_triggers_cleanup(mocker):
    mock_patch = "15.7.1"
    mock_hotfix = datetime(2024, 4, 8)
    hotfixes = {mock_patch: [mock_hotfix]}

    # Return data
    mocker.patch("src.server.loader.patchloader2._list_data", return_value=(["Ahri"], [], [], []))

    # Inject a LoadError in one of the loaders
    mocker.patch("src.server.loader.patchloader2._load_all_champions", new=AsyncMock(side_effect=LoadError(500, "fail", "url", "Champion", "Ahri")))
    mocker.patch("src.server.loader.patchloader2._load_all_items", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2._load_all_runes", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2._load_all_summonerspells", new=AsyncMock())

    mock_clean_up = mocker.patch("src.server.loader.patchloader2._clean_up", new=AsyncMock())
    mock_add_patch = mocker.patch("src.server.loader.patchloader2.db.add_patch", new=AsyncMock())

    await _load_fresh_database(hotfixes)

    mock_clean_up.assert_called_once()
    mock_add_patch.assert_not_called()



@pytest.mark.asyncio
async def test_load_all_champions_calls_each(mocker, patch_with_hotfix):
    # Given
    champion_list = [
        "Ahri",
        "Garen",
        "Akali"
    ]
    mock_session = AsyncMock()

    # Patch _load_champion
    mocked_load = mocker.patch("src.server.loader.patchloader2._load_champion", new=AsyncMock())

    # When
    await _load_all_champions(champion_list, mock_session, patch_with_hotfix)

    # Then
    assert mocked_load.call_count == len(champion_list)
    mocked_load.assert_any_call("Ahri", mock_session, patch_with_hotfix)
    mocked_load.assert_any_call("Garen", mock_session, patch_with_hotfix)
    mocked_load.assert_any_call("Akali", mock_session, patch_with_hotfix)


@pytest.mark.asyncio
async def test_load_all_items_calls_each(mocker, patch_with_hotfix):
    # Given
    item_list = [("1001", "ItemA"), ("1002", "ItemB")]
    mock_session = AsyncMock()

    # Mock _load_item
    mocked_load_item = mocker.patch("src.server.loader.patchloader2._load_item", new=AsyncMock())

    # When
    await _load_all_items(item_list, mock_session, patch_with_hotfix)

    # Then
    assert mocked_load_item.call_count == len(item_list)
    mocked_load_item.assert_any_call("1001", "ItemA", mock_session, patch_with_hotfix)
    mocked_load_item.assert_any_call("1002", "ItemB", mock_session, patch_with_hotfix)


@pytest.mark.asyncio
async def test_load_all_runes_calls_each(mocker, patch_with_hotfix):
    rune_list = ["Conqueror", "Electrocute"]
    mock_session = AsyncMock()

    """ # Mock info_loader and wiki names
    mock_info_loader = mocker.patch("src.server.loader.patchloader2.info_loader")
    mock_info_loader.return_value.runeWikiNames = {"Conqueror": "Conqueror", "Electrocute": "Electrocute"} """

    # Patch _load_rune
    mocked_load_rune = mocker.patch("src.server.loader.patchloader2._load_rune", new=AsyncMock())

    await _load_all_runes(rune_list, mock_session, patch_with_hotfix)

    assert mocked_load_rune.call_count == len(rune_list)
    mocked_load_rune.assert_any_call("Conqueror", mock_session, patch_with_hotfix)
    mocked_load_rune.assert_any_call("Electrocute", mock_session, patch_with_hotfix)


@pytest.mark.asyncio
async def test_load_all_summonerspells_calls_each(mocker, patch_with_hotfix):
    summoner_list = ["Flash", "Ignite"]
    mock_session = AsyncMock()

    # Patch _load_summonerspell
    mocked_load_spell = mocker.patch("src.server.loader.patchloader2._load_summonerspell", new=AsyncMock())

    await _load_all_summonerspells(summoner_list, mock_session, patch_with_hotfix)

    assert mocked_load_spell.call_count == len(summoner_list)
    mocked_load_spell.assert_any_call("Flash", mock_session, patch_with_hotfix)
    mocked_load_spell.assert_any_call("Ignite", mock_session, patch_with_hotfix)




@pytest.mark.asyncio
async def test_load_champion_success(mocker, patch_with_hotfix):
    champion_id = "Ahri"
    session = AsyncMock()
    
    # Mock preloaded ChampionJson (from list_data)
    mock_champion_json = mocker.Mock()
    mock_champion_json.name = "Ahri"
    mock_champion_json.image.full = "ahri.png"
    mock_champion_json.passive.image.full = "passive.png"
    spell_mock = mocker.Mock()
    spell_mock.image.full = "q.png"
    mock_champion_json.spells = [spell_mock, spell_mock, spell_mock]

    # Patch _fetch_wiki_html
    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>ahri</html>")

    # Patch create_champion and dependencies
    mocker.patch("src.server.loader.patchloader2.ws.scrape_champion", return_value="champ_obj")
    mocker.patch("src.server.loader.patchloader2._load_image", new=AsyncMock())
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_champion", new=AsyncMock())

    await _load_champion(mock_champion_json, session, patch_with_hotfix)

    assert mock_add.called


@pytest.mark.asyncio
async def test_load_item_success(mocker, patch_with_hotfix):
    item_id = "3031"
    item_json = mocker.Mock()
    item_json.name = "Infinity Edge"
    item_json.image = mocker.Mock(full="infinity_edge.png")

    item_obj = mocker.Mock()
    item_obj.name = "Infinity Edge"

    item_masterwork_obj = mocker.Mock()
    item_masterwork_obj.name = "Infinity Edge"

    session = AsyncMock()

    # Mock wiki fetch
    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>infinity</html>")

    # Mock item logic
    ws_create_item = mocker.patch(
        "src.server.loader.patchloader2.ws.scrape_item",
        side_effect=[item_obj, item_masterwork_obj]
    )

    # Mock image + DB
    mocker.patch("src.server.loader.patchloader2._load_image", new=AsyncMock())
    mocker.patch("src.server.loader.patchloader2.db.increment_item_count", new=AsyncMock())
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_item", new=AsyncMock())

    await _load_item(item_id, item_json, session, patch_with_hotfix)
    assert ws_create_item.called

    assert mock_add.call_count == 1


@pytest.mark.asyncio
async def test_load_rune_success(mocker, patch_with_hotfix):
    rune = mocker.Mock()
    rune.name = "Electrocute"
    rune.icon = "path/to/electrocute.png"
    rune_class = mocker.Mock(rune=rune)

    session = AsyncMock()

    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>rune</html>")
    mocker.patch("src.server.loader.patchloader2._load_image_rune", return_value="rune_image")

    mocker.patch("src.server.loader.patchloader2.ws.scrape_rune", return_value="rune_obj")
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_rune", new=AsyncMock())

    await _load_rune(rune_class, session, patch_with_hotfix)

    assert mock_add.called


@pytest.mark.asyncio
async def test_load_summonerspell_success(mocker, patch_with_hotfix):
    spell_json = mocker.Mock()
    spell_json.name = "Flash"
    spell_json.image = mocker.Mock(full="flash.png")

    session = AsyncMock()

    mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value="<html>flash</html>")
    mocker.patch("src.server.loader.patchloader2.ws.scrape_summonerspell", return_value="spell_obj")
    mocker.patch("src.server.loader.patchloader2._load_image", new=AsyncMock())
    mock_add = mocker.patch("src.server.loader.patchloader2.db.add_summonerspell", new=AsyncMock())

    await _load_summonerspell(spell_json, session, patch_with_hotfix)

    assert mock_add.called



@pytest.mark.asyncio
async def test_fetch_wiki_html_uses_name_mapping(mocker):
    session = AsyncMock()
    session.get_html.return_value = "<html>mapped</html>"

    mocker.patch("src.server.loader.patchloader2.URLS.wiki", "https://wiki/")
    mocker.patch("src.server.loader.patchloader2.info_loader", return_value=mocker.Mock(
        itemWikiNames={"Fancy Sword": "Fancy_Sword_Wiki"}
    ))

    result = await _fetch_wiki_html("Fancy Sword", "Item", session)

    session.get_html.assert_called_once_with("https://wiki/Fancy_Sword_Wiki")
    assert result == "<html>mapped</html>"

@pytest.mark.asyncio
async def test_fetch_wiki_html_raises_loaderror_on_http_error(mocker):
    session = AsyncMock()
    session.get_html.side_effect = HTTPError(
        url="https://wiki/missing",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None
    )

    mocker.patch("src.server.loader.patchloader2.URLS.wiki", "https://wiki/")
    mocker.patch("src.server.loader.patchloader2.info_loader", return_value=mocker.Mock(
        itemWikiNames={}
    ))

    with pytest.raises(LoadError) as exc:
        await _fetch_wiki_html("MissingItem", "Item", session)

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
        paths=PathJson(image="mock/img", sprite="mock/sprite")
    ))

    # Patch URL paths
    mocker.patch("src.server.loader.patchloader2.URLS.dataLink", "https://riot.cdn/")
    mocker.patch("src.server.loader.patchloader2.URLS.image", "img/")
    mocker.patch("src.server.loader.patchloader2.URLS.sprite", "sprite/")

    # Patch only the .exists() and .mkdir() methods — not Path itself
    mocker.patch("pathlib.Path.exists", return_value=False)
    mocker.patch("pathlib.Path.mkdir", return_value=None)

    # Patch file writing
    mocked_open = mocker.patch("builtins.open", mock_open())

    # Run the function
    await _load_image(image, session, NewPatch(patch="15.8.1"))

    # Assertions
    session.get_bytes.assert_called_once_with("https://riot.cdn/15.8.1/img/champion/icon.png")
    mocked_open.assert_called_once()



@pytest.mark.asyncio
async def test_load_image_rune(mocker):
    icon = "perksStylesPrecision.png"
    session = AsyncMock()
    session.get_bytes.return_value = b"<fake image bytes>"

    # Patch: info_loader returns image/sprite paths
    mocker.patch(
        "src.server.loader.patchloader2.info_loader",
        return_value=SimpleNamespace(
            paths=PathJson(image= "mock/img", sprite= "mock/sprite")
        )
    )

    # Patch: make .exists() return False so it tries to download
    mocker.patch("pathlib.Path.exists", return_value=False)

    # Patch: simulate writing to disk with no real I/O
    mocker.patch("builtins.open", mock_open())

    # Act
    result = await _load_image_rune(icon, session)

    # Assert
    assert result.full == "perksStylesPrecision.png"
    assert result.group == "rune"
    session.get_bytes.assert_called_once()





@pytest.mark.asyncio
async def test_load_patch(mocker):
    patch_str = "15.8.1"
    hotfix = datetime(2025, 4, 10)
    old_patch = NewPatch(patch="15.8.0", hotfix=None)

    session_mock = mocker.Mock()

    # Mocks
    mock_wiki_html = "<html>patch wiki</html>"
    mock_fetch_html = mocker.patch("src.server.loader.patchloader2._fetch_wiki_html", return_value=mock_wiki_html)
    mock_scrape_patch = mocker.patch(
        "src.server.loader.patchloader2.ws.scrape_patch",
        new_callable=AsyncMock,
        return_value={
            "champions": {},
            "items": {},
            "runes": {},
            "summonerspells": {}
        }
    )

    mock_patch_champions = mocker.patch("src.server.loader.patchloader2._patch_champions", return_value=None)
    mock_patch_items = mocker.patch("src.server.loader.patchloader2._patch_items", return_value=None)
    mock_patch_runes = mocker.patch("src.server.loader.patchloader2._patch_runes", return_value=None)
    mock_patch_summoners = mocker.patch("src.server.loader.patchloader2._patch_summonerspells", return_value=None)

    mock_add_patch = mocker.patch("src.server.loader.patchloader2.db.add_patch")

    await _load_patch(patch_str, hotfix, old_patch)

    mock_fetch_html.assert_called_once_with("V25.08", "Patch", mocker.ANY)
    mock_scrape_patch.assert_called_once_with(mock_wiki_html, hotfix)
    mock_patch_champions.assert_called_once()
    mock_patch_items.assert_called_once()
    mock_patch_runes.assert_called_once()
    mock_patch_summoners.assert_called_once()
    mock_add_patch.assert_called_once()



@pytest.mark.asyncio
async def test_patch_champions(mocker):
    patch_obj = NewPatch(patch="15.8.1", hotfix=datetime(2025, 4, 10))
    session = AsyncMock()

    # Champion currently in DB
    existing = NewChampion(
        name="Ahri",
        champion_id="Ahri",
        key="103",
        patch="15.8.0",
        hotfix=None,
        image=Image(
            full="Ahri.png",
            group="champions"
        ),
        validated=True,
        changes=[],
        passive=ChampionPassive(
            name="ahri heal",
            image=Image(
            full="Black Cleaver.png",
            group="passives"
            )
        ),
        q=ChampionAbility(
            name="q",
            maxrank=5,
            image=Image(
                full="Black Cleaver.png",
                group="items"
            ),
        ),
        w=ChampionAbility(
            name="w",
            maxrank=5,
            image=Image(
                full="Black Cleaver.png",
                group="items"
            ),
        ),
        e=ChampionAbility(
            name="e",
            maxrank=5,
            image=Image(
                full="Black Cleaver.png",
                group="items"
            ),
        ),
        r=ChampionAbility(
            name="r",
            maxrank=3,
            image=Image(
                full="Black Cleaver.png",
                group="items"
            ),
        ),
        attackspeed=0.625,
        attackspeed_per_lvl=0.02,
        attackspeed_ratio=0.625,
        attack_windup=0.2,
        windup_modifier=1.0,
        missile_speed=1500,
        hp=600, hp_per_lvl=100, mana=300, mana_per_lvl=50,
        ad=53, ad_per_lvl=3, armor=20, armor_per_lvl=4,
        mr=30, mr_per_lvl=1.3, movementspeed=330,
        attackrange=550, hp_regen=6, hp_regen_per_lvl=0.6,
        mana_regen=8, mana_regen_per_lvl=1.2,
        range_type=RangeType.RANGED, resource_type="Mana",
        last_changed="15.7"
    )

    # Mock Riot API champion list
    riot_champion_data = {
        "id": "Milio",
        "key": "901",
        "name": "Milio",
        "title": "",
        "image": {
            "full": "Milio.png",
            "group": "champions"
        },
        "stats": {
            "hp": 560, "hpperlevel": 88,
            "mp": 340, "mpperlevel": 50,
            "attackdamage": 50, "attackdamageperlevel": 3,
            "armor": 22, "armorperlevel": 4.5,
            "spellblock": 30, "spellblockperlevel": 1.3,
            "movespeed": 330, "attackrange": 550,
            "hpregen": 6, "hpregenperlevel": 0.6,
            "mpregen": 8, "mpregenperlevel": 1.2,
            "attackspeed": 0.625, "attackspeedperlevel": 2,
            "crit": 0, "critperlevel": 0,
        },
        "partype": "Mana",
        "spells": [],
        "passive": {
            "name": "warmness",
            "description": "warm",
            "image": {
                "full": "Milio.png",
                "group": "champions"
            },
        },
        "skins": [], "lore": "", "blurb": "",
        "allytips": [], "enemytips": [],
        "tags": [], "info": {}, "recommended": []
    }

    mocker.patch("src.server.loader.patchloader2.db.fetch_champions_by_patch", return_value=[existing])
    mock_add_champion = mocker.patch("src.server.loader.patchloader2.db.add_champion")
    mock_load_champion = mocker.patch("src.server.loader.patchloader2._load_champion")
    session.get_json.return_value = riot_champion_data

    changes = {
        "new": ["Milio"],
        "changed": {"Ahri": {"Q": ["Cooldown increased"]}},
        "deleted": []
    }

    await _patch_champions(changes, patch_obj, patch_obj, session)

    mock_load_champion.assert_called_once()
    mock_add_champion.assert_called()


@pytest.mark.asyncio
async def test_add_changes_champion_applies_correct_diffs():
    # Setup dummy abilities and passive
    passive = ChampionPassive(name="Void Shift", image=Image(full="", group=""))
    q = ChampionAbility(name="Call of the Void", image=Image(full="", group=""), maxrank=5)
    w = ChampionAbility(name="Null Zone", image=Image(full="", group=""), maxrank=5)
    e = ChampionAbility(name="Malefic Visions", image=Image(full="", group=""), maxrank=5)
    r = ChampionAbility(name="Nether Grasp", image=Image(full="", group=""), maxrank=3)

    champ = NewChampion(
        name="Malzahar",
        key="90",
        champion_id="Malzahar",
        patch="15.8.1",
        hotfix=None,
        validated=True,
        changes=[],
        image=Image(full="", group=""),
        hp=500, hp_per_lvl=90, mana=375, mana_per_lvl=30,
        ad=55, ad_per_lvl=3.3, armor=18, armor_per_lvl=4.5,
        mr=30, mr_per_lvl=1.3, movementspeed=335,
        attackrange=500, hp_regen=6, hp_regen_per_lvl=0.6,
        mana_regen=8, mana_regen_per_lvl=0.8,
        attackspeed=0.625, attackspeed_per_lvl=2,
        attackspeed_ratio=0.625, attack_windup=0.2,
        windup_modifier=1.0, missile_speed=1400,
        passive=passive, q=q, w=w, e=e, r=r,
        range_type=RangeType.RANGED, resource_type="Mana",
        last_changed="15.7"
    )

    # Mock diff with matching and non-matching entries
    diff = {
        "Call of the Void": ["Now silences for 1.5s instead of 1s"],
        "Void Shift": ["Cooldown reduced from 30 to 20"],
        "Some Untracked Label": ["General tooltip updated"]
    }

    await _add_changes_champion(champ, diff)

    # Ability-specific changes
    assert champ.q.changes == ["Now silences for 1.5s instead of 1s"]
    assert champ.q.validated is False

    assert champ.passive.changes == ["Cooldown reduced from 30 to 20"]
    assert champ.passive.validated is False

    # Remaining diff line gets added to general changes
    assert champ.changes == ["General tooltip updated"]
    assert champ.validated is False



@pytest.mark.asyncio
async def test_patch_items(mocker):
    patch_obj = NewPatch(patch="15.8.1", hotfix=datetime(2025, 4, 10))
    session = AsyncMock()

    # Existing item in DB
    existing_item = NewItem(
        item_id="3071",
        name="Black Cleaver",
        patch="15.8.0",
        hotfix=None,
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
        "changed": {"Black Cleaver": ["Cooldown reduced"]},
        "deleted": []
    }

    await _patch_items(changes, patch_obj, patch_obj, session)

    mock_load_item.assert_called_once()
    mock_add_item.assert_called()



@pytest.mark.asyncio
async def test_patch_runes(mocker):
    patch_obj = NewPatch(patch="15.8.1", hotfix=datetime(2025, 4, 10))
    session = AsyncMock()

    # Mock existing rune
    existing_rune = NewRune(
        rune_id=8126,
        name="Cheap Shot",
        patch="15.8.0",
        hotfix=None,
        tree="Domination",
        tree_id=8100,
        row=0,
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
        "changed": {"Cheap Shot": ["Effect clarified"]},
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
    result = _find_rune("Unseen Rune", [])
    assert result is None



@pytest.mark.asyncio
async def test_patch_summonerspells(mocker):
    patch_obj = NewPatch(patch="15.8.1", hotfix=datetime(2025, 4, 10))
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
        "changed": {"Ghost": ["Cooldown reduced from 210 to 180"]},
        "deleted": []
    }

    await _patch_summonerspells(changes, patch_obj, patch_obj, session)

    mock_load.assert_called_once()
    mock_add.assert_called()

