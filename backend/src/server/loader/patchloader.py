import aiohttp
import asyncio
import logging
import requests

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic import ValidationError
from requests_html import HTMLSession
from urllib.error import HTTPError, URLError



import src.server.database as db
import src.server.loader.webscraper as ws

from src.server.loader.helper import info_loader, SafeSession
from src.server.models.patch import Patch, NewPatch
from src.server.models.json_validation import (
    ChampionsJson,
    ItemsJson,
    ItemJson,
    RuneJson,
    RuneTreeJson,
    SummonerspellsJson,
    SummonerspellJson,
    InfoJson,
    PathJson,
    UrlJson
)
from src.server.loader.patchexceptions import (
    PatcherError,
    MuteException,
    EmptyTodoException,
    LoadError,
    ScrapeError
)




logger = logging.getLogger("patch_loader")
handler = logging.FileHandler(filename="src/logs/patch_loader.log")
frm = logging.Formatter(fmt="%(asctime)s - %(levelname)s: %(message)s", datefmt="%d.%m.%Y  %H:%M:%S")
handler.setFormatter(frm)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

debugger = logging.getLogger("debugger")
handler = logging.FileHandler(filename="src/logs/debug.log")
handler.setFormatter(frm)
debugger.addHandler(handler)
debugger.setLevel(logging.INFO)




class TodoType(str, Enum):
    LOAD="Load"
    HOTFIX="Hotfix"
    PATCH="Patch"


@dataclass
class Todo():
    todo_type: TodoType
    patch: str
    hotfix: datetime = None



@dataclass
class RuneClass():
    """Class to gather Rune information"""
    rune: RuneJson
    tree: str
    tree_id: int
    row: int

    def __str__(self) -> str:
        return self.rune.name
    





class Patchloader():
    mute: bool = False
    todo: list[Todo] = []

    def __init__(self) -> None:
        
        
        self.patch: Patch = None
        self.urls: UrlJson = info_loader().urls
        self.session: SafeSession = None


    @staticmethod
    async def update_todo() -> list[Todo]:
        if Patchloader.mute:
            raise MuteException("Already loading updates!")

        Patchloader.mute = True
        urls = info_loader().urls
        versions = urls.patches
        debugger.info(versions)
        try:
            patches = Patchloader.get_dict_from_request(versions)
        except (HTTPError, URLError) as e:
            Patchloader.mute = False
            raise PatcherError("Failed loading Versions.json file!", e)
        
        con1 = type(patches) == list
        con2 = len(patches) > 0
        con3 = type(patches[0]) == str
        if not(con1 and con2 and con3):
            raise PatcherError("Versions.json file is in the wrong shape!", "Couldn't validate version.json!")
        
        db_patch = await db.fetch_patch_latest()

        ### ------------- Empty database
        if not db_patch:
            do = Todo(TodoType.LOAD, patches[0])
            Patchloader.todo = [do]
            Patchloader.mute = False
            return Patchloader.todo
        
        patch_list = []
        while db_patch.patch != patches[0]:
            patch_list.insert(0, patches.pop(0))
        else:
            try:
                html = Patchloader.get_html_from_request(urls.wiki + "V" + patches[0].rstrip(".1"))
                hotfix_list = ws.get_hotfix_list(html)
            except (HTTPError, URLError, ValueError, AttributeError) as e:
                raise PatcherError("Failed loading Hotfix information!", e, patches[0])
            
            if db_patch.hotfix:
                while hotfix_list and db_patch.hotfix >= hotfix_list[0]:
                    hotfix_list.pop(0)

            for hot in hotfix_list:
                do = Todo(TodoType.HOTFIX, db_patch.patch, hot)
                if do not in Patchloader.todo:
                    Patchloader.todo.append(do)

        for p in patch_list:
            do = Todo(TodoType.PATCH, p)
            if do not in Patchloader.todo:
                Patchloader.todo.append(do)
                
        Patchloader.mute = False
        return Patchloader.todo



    async def work_todo(self) -> None:
        if Patchloader.mute:
            raise MuteException("Patchloader already occupied!")
        Patchloader.mute = True
        if not Patchloader.todo:
            Patchloader.mute = False
            raise EmptyTodoException("No patches to load!")
            
        while Patchloader.todo:
            do = Patchloader.todo.pop(0)
            match do.todo_type:
                case TodoType.LOAD: await self.load_data(do.patch)
                case TodoType.PATCH: await self.patch_data(do.patch)
                case TodoType.HOTFIX: await self.hotfix_data(do.hotfix)
            
        Patchloader.mute = False



    async def load_data(self, patch_ver: str) -> None:
        logger.info(f" Loading patch: {patch_ver}")
        try:
            champion_list, item_list, rune_list, summonerspell_list = self.list_data(patch_ver)
        except HTTPError as e:
            logger.error(f"Error {e.code}: Failed loading data dicts!")
            logger.error(e.reason)
            logger.error(f"Could not load information from '{e.url}'!")
            return
        except URLError as e:
            logger.error(f"Failed loading data dicts!")
            logger.error(e.reason)
            return
        except ValidationError as e:
            logger.error(f"Error validating patch_data: {e}")
            return
        
        try:
            html = Patchloader.get_html_from_request(self.urls.wiki + "V" + patch_ver.rstrip(".1"))
            hotfix_list = ws.get_hotfix_list(html)
        except (HTTPError, URLError, ValueError, AttributeError) as e:
            raise PatcherError("Failed loading Hotfix information!", e, patch_ver)
        
        p = NewPatch(
            patch=patch_ver,
            hotfix=hotfix_list[-1] if hotfix_list else None,
            champion_count=len(champion_list),
            item_count=len(item_list),
            rune_count=len(rune_list),
            summonerspell_count=len(summonerspell_list),
            document_count= len(champion_list)+len(item_list)+len(rune_list)+len(summonerspell_list)
        )
        patch_id = await db.add_patch(p)
        self.patch = await db.fetch_patch_by_id(patch_id)

        self.create_folder_tree()

        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = SafeSession(session)
            try:
                await asyncio.gather(
                    self.load_all_champions(champion_list),
                    self.load_all_items(item_list),
                    self.load_all_runes(rune_list),
                    self.load_all_summonerspells(summonerspell_list)
                )
            except LoadError as e:
                logger.error(f"Error {e.code} for {e.type} '{e.name}'!")
                logger.error(e.reason)
                logger.error(f"Could not load information from '{e.url}'")
                await self.cleanup()
                return
            except ScrapeError as e:
                logger.error(f"Could not scrape data for {e.type} '{e.name}'")
                logger.error(e.reason)
                await self.cleanup()
                return





    def list_data(self, patch_ver: str) -> tuple[list[str], list[tuple[str, ItemJson]], list[RuneClass], list[tuple[str, SummonerspellJson]]]: 
        champions = ChampionsJson(**requests.get(self.urls.dataLink + patch_ver + self.urls.championList).json())
        items = ItemsJson(**requests.get(self.urls.dataLink + patch_ver + self.urls.itemList).json())
        runes = requests.get(self.urls.dataLink + patch_ver + self.urls.runeList).json()
        summoners = SummonerspellsJson(**requests.get(self.urls.dataLink + patch_ver + self.urls.summonerspellList).json())


        champion_list = list(champions.data.keys())
        item_list = [(item_name, ItemJson(**item_data)) for item_name, item_data in items.data.items()]
        rune_list = []
        for tree in runes:
            rune_tree = RuneTreeJson(**tree)
            for i, row in enumerate(rune_tree.slots):
                for rune in row.runes:
                    rune_list.append(RuneClass(rune, rune_tree.name, rune_tree.id_, i))
        summoner_list = [(summoner_name, SummonerspellJson(**summoner_data)) for summoner_name, summoner_data in summoners.data.items()]

        return champion_list, item_list, rune_list, summoner_list


    def create_folder_tree(self) -> None:
        """Creates directory structure for static images, if not existing yet."""
        paths = info_loader().paths
        paths.championImage.mkdir(parents=True, exist_ok=True)
        paths.itemImage.mkdir(parents=True, exist_ok=True)
        paths.passiveImage.mkdir(parents=True, exist_ok=True)
        paths.runeImage.mkdir(parents=True, exist_ok=True)
        paths.spellImage.mkdir(parents=True, exist_ok=True)
        paths.sprite.mkdir(parents=True, exist_ok=True)
        paths.summonerspellImage.mkdir(parents=True, exist_ok=True)



    async def load_all_champions(self, champion_list: list[str]) -> None:
        champion_tasks = [self.load_champion(champion) for champion in champion_list]
        await asyncio.gather(*champion_tasks)


    async def load_champion(self, champion: str) -> None:
        pass



    async def load_all_items(self, item_list: list[tuple[str, ItemJson]]) -> None:
        #TODO look at old code
        item_tasks = [self.load_item(item_id, item_data) for item_id, item_data in item_list]
        self.patch.item_count = len(item_tasks)
        await asyncio.gather(*item_tasks)


    async def load_item(self, item_id: str, item_data: ItemJson) -> None:
        pass



    async def load_all_runes(self, rune_list: list[RuneClass]) -> None:
        rune_tasks = [self.load_rune(rune) for rune in rune_list]
        await asyncio.gather(*rune_tasks)


    async def load_rune(self, rune: RuneClass) -> None:
        pass



    async def load_all_summonerspells(self, summonerspell_list: list[tuple[str, SummonerspellJson]]) -> None:
        summonerspell_tasks = [self.load_summonerspell(name, stats) for name, stats in summonerspell_list]
        await asyncio.gather(*summonerspell_tasks)


    async def load_summonerspell(self, name: str, stats: SummonerspellJson) -> None:
        pass



    async def patch_data(self, patch: str) -> None:
        pass


    async def hotfix_data(self, hotfix: str) -> None:
        pass



    def get_dict_from_request(url: str) -> dict:
        return requests.get(url).json()
    
    def get_html_from_request(url: str) -> bytes:
        session = HTMLSession()
        return session.get(url).content