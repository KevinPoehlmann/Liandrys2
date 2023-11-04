import pytest

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from src.server.loader.patchexceptions import MuteException, EmptyTodoException, PatcherError
from src.server.loader.patchloader import Patchloader, Todo, TodoType, RuneClass






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
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 26)), Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 27))]



@pytest.mark.asyncio
async def test_update_todo_patch_without_hotfix_old_in_todo(clean_Patchloader, version1321_json, db_fake_patch, patch1321, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    Patchloader.todo = [Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 26))]
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 26)), Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 27))]



@pytest.mark.asyncio
async def test_update_todo_patch_with_old_hotfix(clean_Patchloader, version1321_json, db_fake_patch_hotfix, patch1321, mocker):

    mocker.patch("src.server.loader.patchloader.Patchloader.get_dict_from_request", return_value=version1321_json)
    mocker.patch("src.server.loader.patchloader.db.fetch_patch_latest", return_value=db_fake_patch_hotfix)
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    l1 = await Patchloader.update_todo()
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 27))]



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
    assert l1 == [Todo(TodoType.HOTFIX, "13.21.1", datetime(2023, 10, 27)), Todo(TodoType.PATCH, "13.22.1")]











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



def test_list_data(clean_Patchloader):

    p1 = Patchloader()
    c_list, i_list, r_list, s_list = p1.list_data("13.21.1")
    assert c_list[2] == "Akali"
    assert i_list[1][0] == "1004"
    assert i_list[2][1].name == "Rejuvenation Bead"
    assert r_list[2].tree == "Domination"
    assert r_list[2].row == 0
    assert r_list[2].rune.key == "DarkHarvest"
    assert s_list[0][0] == "SummonerBarrier"
    assert s_list[1][1].name == "Cleanse"



def testcreate_folder_tree():
    p1 = Patchloader()
    p1.create_folder_tree()
    

    assert Path("src/images/champions").exists()
    assert Path("src/images/items").exists()
    assert Path("src/images/passives").exists()
    assert Path("src/images/runes").exists()
    assert Path("src/images/spells").exists()
    assert Path("src/images/sprites").exists()
    assert Path("src/images/summonerspells").exists()
    
    for child in Path("src/images").iterdir():
        child.rmdir()


@pytest.mark.asyncio
async def test_load_data(patch1321, mocker):
    mocker.patch("src.server.loader.patchloader.Patchloader.get_html_from_request", return_value=patch1321)
    mocker.patch("src.server.loader.patchloader.Patchloader.create_folder_tree", return_value=None)
    champion_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_items", return_value=None)
    item_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_runes", return_value=None)
    rune_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_summonerspells", return_value=None)
    summoner_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_all_champions", return_value=None)

    p1 = Patchloader()
    await p1.load_data("13.21.1")

    assert champion_mock.call_count == 1
    assert item_mock.call_count == 1
    assert rune_mock.call_count == 1
    assert summoner_mock.call_count == 1
    assert p1.patch.patch == "13.21.1"



@pytest.mark.asyncio
async def test_load_all_champions(clean_Patchloader, mocker):
    champion_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_champion", return_value=None)
    p1 = Patchloader()
    champion_list, _, _, _ = p1.list_data("13.21.1")
    await p1.load_all_champions(champion_list)
    assert champion_mock.call_count == 165



@pytest.mark.skip
@pytest.mark.asyncio
async def test_load_champion():
    assert False



@pytest.mark.asyncio
async def test_load_all_items(clean_Patchloader, db_fake_patch_uptodate , mocker):
    item_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_item", return_value=None)
    p1 = Patchloader()
    p1.patch = db_fake_patch_uptodate
    _, item_list, _, _ = p1.list_data("13.21.1")
    await p1.load_all_items(item_list)
    assert item_mock.call_count == 435
    assert p1.patch.item_count == 435



@pytest.mark.skip
@pytest.mark.asyncio
async def test_load_item():
    assert False



@pytest.mark.asyncio
async def test_load_all_runes(clean_Patchloader, mocker):
    rune_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_rune", return_value=None)
    p1 = Patchloader()
    _, _, rune_list, _ = p1.list_data("13.21.1")
    await p1.load_all_runes(rune_list)
    assert rune_mock.call_count == 63



@pytest.mark.skip
@pytest.mark.asyncio
async def test_load_rune():
    assert False



@pytest.mark.asyncio
async def test_load_all_summonerspells(clean_Patchloader, mocker):
    summoner_mock = mocker.patch("src.server.loader.patchloader.Patchloader.load_summonerspell", return_value=None)
    p1 = Patchloader()
    _, _, _, summoner_list = p1.list_data("13.21.1")
    await p1.load_all_summonerspells(summoner_list)
    assert summoner_mock.call_count == 18



@pytest.mark.skip
@pytest.mark.asyncio
async def test_load_summonerspell():
    assert False



@pytest.mark.skip
@pytest.mark.asyncio
async def test_patch_data():
    assert False



@pytest.mark.skip
@pytest.mark.asyncio
async def test_hotfix_data():
    assert False