import aiohttp
import pytest

from datetime import datetime
from io import BufferedWriter
from pathlib import Path
from unittest.mock import Mock

from src.server.loader.helper import SafeSession
from src.server.loader.patchexceptions import MuteException, EmptyTodoException, PatcherError
from src.server.loader.patchloader import Patchloader, Todo, TodoType, RuneClass
from src.server.models.image import Image






@pytest.mark.asyncio
async def test_update_todo_mute(clean_Patchloader):

    Patchloader.mute = True
    with pytest.raises(MuteException):
        l1 = await Patchloader.update_todo()



@pytest.mark.asyncio
async def test_update_todo_bad_varsions(clean_Patchloader, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=[13, 12])
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=None)
    with pytest.raises(PatcherError):
        l1 = await Patchloader.update_todo()



@pytest.mark.asyncio
async def test_update_todo_empty(clean_Patchloader, version1321_json, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=None)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.LOAD, "13.21.1")]



@pytest.mark.asyncio
async def test_update_todo_load_in_todo(clean_Patchloader, version1321_json, mocker):

    Patchloader.todo = [Todo(TodoType.LOAD, "13.21.1")]
    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=None)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.LOAD, "13.21.1")]



@pytest.mark.asyncio
async def test_update_todo_patch_without_hotfix(clean_Patchloader, version1321_json, db_fake_patch, patch1321, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 26)), Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 27))]



@pytest.mark.asyncio
async def test_update_todo_patch_without_hotfix_old_in_todo(clean_Patchloader, version1321_json, db_fake_patch, patch1321, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    Patchloader.todo = [Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 26))]
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 26)), Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 27))]



@pytest.mark.asyncio
async def test_update_todo_patch_with_old_hotfix(clean_Patchloader, version1321_json, db_fake_patch_hotfix, patch1321, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch_hotfix)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 27))]



@pytest.mark.asyncio
async def test_update_todo_patch_uptodate(clean_Patchloader, version1321_json, db_fake_patch_uptodate, patch1321, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch_uptodate)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    l1 = await Patchloader.update_todo()
    assert l1 == []



@pytest.mark.asyncio
async def test_update_todo_old_patch(clean_Patchloader, db_fake_patch_uptodate, patch1321, version1322_json, mocker):

    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch_uptodate)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1322_json)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.PATCH, "13.22.1")]



@pytest.mark.asyncio
async def test_update_todo_old_patch_with_missing_hotfix(clean_Patchloader, db_fake_patch_hotfix, patch1321, version1322_json, mocker):

    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch_hotfix)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1322_json)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(datetime.now().year, 10, 27)), Todo(TodoType.PATCH, "13.22.1")]











@pytest.mark.asyncio
async def test_work_todo(clean_Patchloader, mocker):
    
    load_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_data", return_value=None)
    patch_mock = mocker.patch("src.server.loader.patchloader.Patchloader.patch_data", return_value=None)
    hotfix_mock = mocker.patch("src.server.loader.patchloader.Patchloader.hotfix_data", return_value=None)
    p1 = Patchloader()
    with pytest.raises(EmptyTodoException):
        await p1.work_todo()
    Patchloader.todo = [Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 26)), Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 27)), Todo(TodoType.PATCH, "13.22.1")]
    await p1.work_todo()
    assert load_mock.call_count == 0
    assert patch_mock.call_count == 1
    assert hotfix_mock.call_count == 2
    assert Patchloader.todo == []



@pytest.mark.skip
@pytest.mark.asyncio
async def test_load_image_rune(clean_Patchloader, mocker):
    icon = "perk-images/Styles/7200_Domination.png"
    p1 = Patchloader()
    mocker.patch.object(Path, "mkdir", return_value=None)
    image_mock = mocker.patch("builtins.open", mocker.mock_open())
    session_mock = mocker.patch.object(SafeSession, "read", return_value=None)
    await p1.load_image_rune(icon)
    handle1 = image_mock()
    handle1.write.assert_called_once_with("https://ddragon.leagueoflegends.com/cdn/img/perk-images/Styles/7200_Domination.png")


@pytest.mark.asyncio
async def test_load_rune_tree_images(clean_Patchloader, mocker):
    icons = ["a", "b", "c", "d"]
    rune_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_image_rune", return_value=None)
    p1 = Patchloader()
    await p1.load_rune_tree_images(icons)
    assert rune_mock.call_count == 4


@pytest.mark.asyncio
async def test_list_data(clean_Patchloader, mocker):
    rti = mocker.patch("src.server.loader.patchloader.Patchloader.load_rune_tree_images", return_value=None)
    p1 = Patchloader()
    c_list, i_list, r_list, s_list = await p1.list_data("13.21.1")
    assert c_list[2] == "Akali"
    assert i_list[1][0] == "1004"
    assert i_list[2][1].name == "Rejuvenation Bead"
    assert r_list[2].tree == "Domination"
    assert r_list[2].row == 0
    assert r_list[2].rune.key == "DarkHarvest"
    assert s_list[1].name == "Cleanse"
    call_arg = rti.call_args[0][0]
    assert isinstance(call_arg, list)
    assert isinstance(call_arg[0], str)
    assert call_arg[0] == "perk-images/Styles/7200_Domination.png"


    


@pytest.mark.asyncio
async def test_load_data(clean_Patchloader, patch1321, db_fake_patch_uptodate, mocker):
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    mocker.patch("src.server.loader.patchloader.Patchloader.load_rune_tree_images", return_value=None)
    patch_id_mock = mocker.patch("src.server.loader.patchloader.db.add_patch", return_value="123")
    patch_mock = mocker.patch("src.server.loader.patchloader.db.fetch_patch_by_id", return_value=db_fake_patch_uptodate)
    champion_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_champions", return_value=None)
    item_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_items", return_value=None)
    rune_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_runes", return_value=None)
    summoner_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_summonerspells", return_value=None)

    p1 = Patchloader()
    await p1.load_data("13.21.1")
    
    assert patch_id_mock.call_args[0][0] == db_fake_patch_uptodate
    assert champion_mock.call_count == 1
    assert item_mock.call_count == 1
    assert rune_mock.call_count == 1
    assert rune_mock.call_args[0][0][2].rune.name == "Dark Harvest"
    assert summoner_mock.call_count == 1
    assert p1.patch.patch == "13.21.1"



@pytest.mark.skip
@pytest.mark.asyncio
async def test_load_image(clean_Patchloader, db_fake_patch_uptodate, mocker):
    p1 = Patchloader()
    mocker.patch.object(Path, "mkdir", return_value=None)
    image_mock = mocker.patch("builtins.open", mocker.mock_open())
    sprite_mock = mocker.patch("builtins.open", mocker.mock_open())
    session_mock = mocker.patch.object(SafeSession, "read", return_value=None)
    p1.patch = db_fake_patch_uptodate
    image = Image(
        full= "Aatrox.png",
        sprite= "champion0.png",
        group= "champion",
        x= 0,
        y= 0,
        w= 48,
        h= 48
    )

    await p1.load_image(image)

    handle1 = image_mock()
    handle1.write.assert_called_once_with("https://ddragon.leagueoflegends.com/cdn/13.21.1/img/champion/Aatrox.png")
    handle2 = sprite_mock()
    handle2.write.assert_called_once_with("https://ddragon.leagueoflegends.com/cdn/13.21.1/img/sprite/champion0.png")




@pytest.mark.asyncio
async def test_load_all_champions(clean_Patchloader, mocker):
    champion_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_champion", return_value=None)
    mocker.patch("src.server.loader.patchloader.Patchloader.load_rune_tree_images", return_value=None)
    p1 = Patchloader()
    champion_list, _, _, _ = await p1.list_data("13.21.1")
    await p1.load_all_champions(champion_list)
    assert champion_mock.call_count == 165



@pytest.mark.asyncio
async def test_load_champion(clean_Patchloader, mocker, aatrox_json, db_fake_patch_with_id):
    mocker.patch.object(SafeSession, "json", return_value=aatrox_json)
    session_mock = mocker.patch.object(SafeSession, "html", return_value=None)
    mocker.patch("src.server.loader.patchloader.ws.create_champion", return_value=None)
    image_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_image", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.add_champion", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.increment_loaded_documents", return_value=None)

    p1 = Patchloader()
    p1.patch = db_fake_patch_with_id
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        p1.session = SafeSession(session)
        await p1.load_champion("Aatrox")
    assert image_mock.call_count == 6
    assert session_mock.call_args[0][0] == "https://leagueoflegends.fandom.com/wiki/Aatrox/LoL"



@pytest.mark.asyncio
async def test_load_all_items(clean_Patchloader, db_fake_patch_uptodate , mocker):
    item_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_item", return_value=None)
    mocker.patch("src.server.loader.patchloader.Patchloader.load_rune_tree_images", return_value=None)
    p1 = Patchloader()
    p1.patch = db_fake_patch_uptodate
    _, item_list, _, _ = await p1.list_data("13.21.1")
    await p1.load_all_items(item_list)
    assert item_mock.call_count == 435
    assert p1.patch.item_count == 435



@pytest.mark.asyncio
async def test_load_item(clean_Patchloader, mocker, youmuusJson, db_fake_patch_with_id):
    session_mock = mocker.patch.object(SafeSession, "html", return_value=None)
    mocker.patch("src.server.loader.patchloader.ws.create_item", return_value=None)
    image_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_image", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.add_item", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.increment_loaded_documents", return_value=None)

    p1 = Patchloader()
    p1.patch = db_fake_patch_with_id
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        p1.session = SafeSession(session)
        await p1.load_item("3142", youmuusJson, {
        "Blade of The Ruined King": "Blade of the Ruined King",
        "Kalista's Black Spear": "Black Spear",
        "Slightly Magical Footwear": "Slightly Magical Boots"
    })
    #assert image_mock.call_count == 1
    assert session_mock.call_args[0][0] == "https://leagueoflegends.fandom.com/wiki/Youmuu's Ghostblade"



@pytest.mark.asyncio
async def test_load_all_runes(clean_Patchloader, mocker):
    rune_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_rune", return_value=None)
    mocker.patch("src.server.loader.patchloader.Patchloader.load_rune_tree_images", return_value=None)
    p1 = Patchloader()
    _, _, rune_list, _ = await p1.list_data("13.21.1")
    await p1.load_all_runes(rune_list)
    assert rune_mock.call_count == 63



@pytest.mark.asyncio
async def test_load_rune(clean_Patchloader, mocker, db_fake_patch_with_id, electrocute):
    session_mock = mocker.patch.object(SafeSession, "html", return_value=None)
    mocker.patch("src.server.loader.patchloader.ws.create_rune", return_value=None)
    image_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_image_rune", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.add_rune", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.increment_loaded_documents", return_value=None)

    p1 = Patchloader()
    p1.patch = db_fake_patch_with_id
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        p1.session = SafeSession(session)
        await p1.load_rune(electrocute, {
        "Grasp of the Undying": "Grasp of the Undying_(Rune)",
        "Jack Of All Trades": "Jack of All Trades",
        "Triple Tonic": "Triple Tonic_(Rune)"
    })
    assert image_mock.call_count == 1
    assert session_mock.call_args[0][0] == "https://leagueoflegends.fandom.com/wiki/Electrocute"



@pytest.mark.asyncio
async def test_load_all_summonerspells(clean_Patchloader, mocker):
    summoner_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_summonerspell", return_value=None)
    mocker.patch("src.server.loader.patchloader.Patchloader.load_rune_tree_images", return_value=None)
    p1 = Patchloader()
    _, _, _, summoner_list = await p1.list_data("13.21.1")
    await p1.load_all_summonerspells(summoner_list)
    assert summoner_mock.call_count == 18



@pytest.mark.asyncio
async def test_load_summonerspell(clean_Patchloader, mocker, db_fake_patch_with_id, ignite_json):
    session_mock = mocker.patch.object(SafeSession, "html", return_value=None)
    mocker.patch("src.server.loader.patchloader.ws.create_summonerspell", return_value=None)
    image_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_image", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.add_summonerspell", return_value=None)
    mocker.patch("src.server.loader.patchloader.db.increment_loaded_documents", return_value=None)

    p1 = Patchloader()
    p1.patch = db_fake_patch_with_id
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        p1.session = SafeSession(session)
        await p1.load_summonerspell(ignite_json)
    assert image_mock.call_count == 1
    assert session_mock.call_args[0][0] == "https://leagueoflegends.fandom.com/wiki/Ignite"



@pytest.mark.skip
@pytest.mark.asyncio
async def test_patch_data():
    assert False



@pytest.mark.skip
@pytest.mark.asyncio
async def test_hotfix_data():
    assert False