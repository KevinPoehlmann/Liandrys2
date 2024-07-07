import aiohttp
import asyncio
import functools
import logging
import requests
import time

from enum import Enum
from pathlib import Path
from pydantic import ValidationError
from requests_html import HTMLSession
from typing import Callable
from urllib.error import HTTPError, URLError



import src.server.database as db
import src.server.loader.webscraper as ws

from src.server.loader.helper import info_loader, SafeSession, Todo, RuneClass, TodoType
from src.server.models.image import Image
from src.server.models.patch import Patch, NewPatch
from src.server.models.json_validation import (
    ChampionsJson,
    ChampionJson,
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
debugger.setLevel(logging.DEBUG)



def time_safely(method: Callable) -> Callable:
        """Decorator to time the loading process and catch uncaught exceptions."""
        @functools.wraps(method)
        async def wrapper(*args, **kwargs) -> None:
            logger.info("--------------------------------------------------------------------------------------------")
            debugger.info("--------------------------------------------------------------------------------------------")
            t = time.time()
            try:
                await method(*args, **kwargs)
            except Exception as e:
                logger.exception(e)
                logger.error(f"Patch {args[0].patch.patch} was not loaded successfully!")
                await args[0].clean_up()
                return
            finally:
                Patchloader.mute = False
            t = time.time()-t
            logger.info(f"Patching took {t} seconds.")
            """ documents = sum([getattr(ref.information, field) for field in ref.information.__dataclass_fields__])
            logger.info(f"Loaded {documents} documents in {t} seconds ({t/documents} per document)") """
        return wrapper




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
        #debugger.info(versions)
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


    @time_safely
    async def load_data(self, patch_ver: str) -> None:
        logger.info(f" Loading patch: {patch_ver}")
        try:
            champion_list, item_list, rune_list, summonerspell_list = await self.list_data(patch_ver)
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
        except LoadError as e:
                logger.error(f"Error {e.code} for {e.type} '{e.name}'!")
                logger.error(e.reason)
                logger.error(f"Could not load information from '{e.url}'")
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
        )
        patch_id = await db.add_patch(p)
        self.patch = await db.fetch_patch_by_id(patch_id)

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
                logger.error(e)
                await self.clean_up()
                return
            except ScrapeError as e:
                logger.error(f"Could not scrape data for {e.type} '{e.name}'")
                logger.error(e.reason)
                logger.error(e)
                await self.clean_up()
                return





    async def list_data(self, patch_ver: str) -> tuple[list[str], list[tuple[str, ItemJson]], list[RuneClass], list[SummonerspellJson]]: 
        champions = ChampionsJson(**requests.get(self.urls.dataLink + patch_ver + self.urls.championList).json())
        items = ItemsJson(**requests.get(self.urls.dataLink + patch_ver + self.urls.itemList).json())
        runes = requests.get(self.urls.dataLink + patch_ver + self.urls.runeList).json()
        summoners = SummonerspellsJson(**requests.get(self.urls.dataLink + patch_ver + self.urls.summonerspellList).json())


        champion_list = list(champions.data.keys())
        item_list = [(item_name, ItemJson(**item_data)) for item_name, item_data in items.data.items()]
        rune_list = []
        tree_icons = []
        for tree in runes:
            rune_tree = RuneTreeJson(**tree)
            tree_icons.append(rune_tree.icon)
            for i, row in enumerate(rune_tree.slots):
                for rune in row.runes:
                    rune_list.append(RuneClass(rune, rune_tree.name, rune_tree.id_, i))
        await self.load_rune_tree_images(tree_icons)
        summoner_list = [SummonerspellJson(**summoner_data) for summoner_data in summoners.data.values()]

        return champion_list, item_list, rune_list, summoner_list



    async def load_all_champions(self, champion_list: list[str]) -> None:
        champion_tasks = [self.load_champion(champion) for champion in champion_list]
        await asyncio.gather(*champion_tasks)
        debugger.debug(f"++++++++++++++ All Champions done")


    async def load_champion(self, champion_id: str) -> None:
        debugger.debug(f"{champion_id} - B - begin")
        try:
            champion_dict = await self.session.json(self.urls.dataLink + self.patch.patch + self.urls.championData + champion_id + ".json")
            debugger.debug(f"{champion_id} - J - json")
            champions_json = ChampionsJson(**champion_dict)
            champion_json = ChampionJson(**champions_json.data.get(champion_id))
            champion_wiki = await self.session.html(self.urls.wiki + champion_json.name + self.urls.championWiki)
            debugger.debug(f"{champion_id} - W - wiki")
        except HTTPError as e:
            raise LoadError(e.code, e.reason, e.url, "Champion", champion_id)
        except URLError as e:
            raise LoadError(e.errno, e.reason, e.filename, "Champion", champion_id)
        except ValidationError as e:
            raise LoadError(9, str(e), "", "Champion", champion_id)
        try:
            champion = ws.create_champion(champion_json, champion_wiki, self.patch.patch)
        except Exception as e:
            logger.critical(champion_id)
            raise
        await self.load_image(champion_json.image)
        await self.load_image(champion_json.passive.image)
        for spell in champion_json.spells:
            await self.load_image(spell.image)
        debugger.debug(f"{champion_id} - I - images downloaded")
        
        await db.add_champion(champion)
        debugger.debug(f"{champion_id} - A - added")
        await db.increment_loaded_documents(self.patch.id)
        debugger.debug(f"{champion_id} - C - counted")




    async def load_all_items(self, item_list: list[tuple[str, ItemJson]]) -> None:
        #TODO do all items have names???
        wiki_names = info_loader().itemWikiNames
        item_tasks = [self.load_item(item_id, item_data, wiki_names) for item_id, item_data in item_list]
        self.patch.item_count = len(item_tasks)
        await asyncio.gather(*item_tasks)
        debugger.debug(f"++++++++++++++ All Items done")


    async def load_item(self, item_id: str, item_json: ItemJson, wiki_names: dict) -> None:
        if len(item_id) > 4:
            #skipping removed Ornn -items
            return
        try:
            item_json.name = wiki_names[item_json.name] if item_json.name in wiki_names else item_json.name
            item_wiki = await self.session.html(self.urls.wiki + item_json.name)
        except HTTPError as e:
            raise LoadError(e.code, e.reason, e.url, "Item", item_json.name)
        except URLError as e:
            raise LoadError(e.errno, e.reason, e.filename, "Item", item_json.name)
        except ValidationError as e:
            raise LoadError(9, str(e), "", "Item", item_json.name)
        
        try:
            item = ws.create_item(item_id, item_json, item_wiki, self.patch.patch, masterwork=False)
            masterwork = ws.is_masterwork(item_wiki)
            if masterwork:
                item_masterwork = ws.create_item(item_id, item_json, item_wiki, self.patch.patch, masterwork=True)
                item_masterwork.name = item_masterwork.name + " - Masterwork"
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Could not scrape data for Item '{item_json.name}'")
            logger.error(e)
            return
        except Exception as e:
            logger.critical(item_json.name)
            raise
        await self.load_image(item_json.image)
        
        await db.add_item(item)
        await db.increment_loaded_documents(self.patch.id)
        if masterwork:
            await db.add_item(item_masterwork)
            await db.increment_loaded_documents(self.patch.id)



    async def load_all_runes(self, rune_list: list[RuneClass]) -> None:
        wiki_names = info_loader().runeWikiNames
        rune_tasks = [self.load_rune(rune, wiki_names) for rune in rune_list]
        await asyncio.gather(*rune_tasks)
        debugger.debug(f"++++++++++++++ All Runes done")


    async def load_rune(self, rune_class: RuneClass, wiki_names: dict) -> None:
        debugger.debug(f"{rune_class.rune.name} - B - begin")
        try:
            rune_class.rune.name = wiki_names[rune_class.rune.name] if rune_class.rune.name in wiki_names else rune_class.rune.name
            rune_wiki = await self.session.html(self.urls.wiki + rune_class.rune.name)
            debugger.debug(f"{rune_class.rune.name} - W - wiki")
        except HTTPError as e:
            raise LoadError(e.code, e.msg, e.url, "Rune", rune_class.rune.name)
        except URLError as e:
            raise LoadError(e.errno, e.reason, e.filename, "Rune", rune_class.rune.name)
        except ValidationError as e:
            raise LoadError(9, str(e), "", "Rune", rune_class.rune.name)

        image = await self.load_image_rune(rune_class.rune.icon)
        debugger.debug(f"{rune_class.rune.name} - I - images downloaded")

        try:
            rune = ws.create_rune(rune_class, rune_wiki, self.patch.patch, image)
            debugger.debug(f"{rune_class.rune.name} - S - scraped")
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Could not scrape data for Rune '{rune_class.rune.name}'")
            logger.error(e)
            return
        except Exception as e:
            logger.critical(rune_class.rune.name)
            raise

        await db.add_rune(rune)
        debugger.debug(f"{rune_class.rune.name} - A - added")
        await db.increment_loaded_documents(self.patch.id)
        debugger.debug(f"{rune_class.rune.name} - C - counted")



    async def load_all_summonerspells(self, summonerspell_list: list[SummonerspellJson]) -> None:
        summonerspell_tasks = [self.load_summonerspell(stats) for stats in summonerspell_list]
        await asyncio.gather(*summonerspell_tasks)
        debugger.debug(f"++++++++++++++ All Summonerspells done")


    async def load_summonerspell(self, summonerspell_json: SummonerspellJson) -> None:
        debugger.debug(f"{summonerspell_json.name} - B - begin")
        try:
            summonerspell_wiki = await self.session.html(self.urls.wiki + summonerspell_json.name)
            debugger.debug(f"{summonerspell_json.name} - W - wiki")
        except HTTPError as e:
            raise LoadError(e.code, e.reason, e.url, "Summonerspell", summonerspell_json.name)
        except URLError as e:
            raise LoadError(e.errno, e.reason, e.filename, "Summonerspell", summonerspell_json.name)
        except ValidationError as e:
            raise LoadError(9, str(e), "", "Summonerspell", summonerspell_json.name)
        try:
            summonerspell = ws.create_summonerspell(summonerspell_json, summonerspell_wiki, self.patch.patch)
            debugger.debug(f"{summonerspell_json.name} - S - scraped")
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Could not scrape data for Summonerspell '{summonerspell_json.name}'")
            logger.error(e)
            return
        except Exception as e:
            logger.critical(summonerspell_json.name)
            raise
        
        await self.load_image(summonerspell_json.image)
        debugger.debug(f"{summonerspell_json.name} - I - images downloaded")
        
        await db.add_summonerspell(summonerspell)
        debugger.debug(f"{summonerspell_json.name} - A - added")
        await db.increment_loaded_documents(self.patch.id)
        debugger.debug(f"{summonerspell_json.name} - C - counted")



    async def patch_data(self, patch: str) -> None:
        pass


    async def hotfix_data(self, hotfix: str) -> None:
        pass


    async def load_image(self, image: Image) -> None:
        paths = info_loader().paths
        img_path = Path(paths.image + image.group + "/" + image.full)
        if not img_path.exists():
            img_path.parent.mkdir(parents=True, exist_ok=True)
            img_url = self.urls.dataLink + self.patch.patch + "/" + self.urls.image + image.group + "/" + image.full
            try:
                with open(img_path, "wb") as img_file:
                    img_file.write(await self.session.read(img_url))
                debugger.info(f"create_image: -> {image.full}")
            except HTTPError as e:
                raise LoadError(e.code, e.reason, e.url, image.group, image.full)
            except URLError as e:
                raise LoadError(e.errno, e.reason, e.filename, image.group, image.full)
            
        if image.sprite and (image.x == image.y == 0):
            sprite_path = Path(paths.sprite + image.sprite)
            sprite_path.parent.mkdir(parents=True, exist_ok=True)
            sprite_url = self.urls.dataLink + self.patch.patch + self.urls.sprite + image.sprite
            try:
                with open(sprite_path, "wb") as sprite_file:
                    sprite_file.write(await self.session.read(sprite_url))
                #debugger.info(f"create_image: -> {image.sprite}")
            except HTTPError as e:
                raise LoadError(e.code, e.reason, e.url, image.group, image.full)
            except URLError as e:
                raise LoadError(e.errno, e.reason, e.filename, image.group, image.full)
            

    async def load_image_rune(self, icon: str) -> Image:
        image = Image(
            full=icon.rsplit("/", 1)[-1],
            group="rune"
        )
        paths = info_loader().paths
        img_path = Path(paths.image + image.group + "/" + image.full)
        if not img_path.exists():
            img_path.parent.mkdir(parents=True, exist_ok=True)
            img_url = self.urls.dataLink + self.urls.image + icon
            try:
                with open(img_path, "wb") as image_file:
                    image_file.write(await self.session.read(img_url))
                debugger.info(f"create_image: -> {image.full}")
            except HTTPError as e:
                raise LoadError(e.code, e.reason, e.url, image.group, image.full)
            except URLError as e:
                raise LoadError(e.errno, e.reason, e.filename, image.group, image.full)
        return image


    async def load_rune_tree_images(self, icon_list: list[str]) -> None:
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = SafeSession(session)
            tasks = [self.load_image_rune(icon) for icon in icon_list]
            await asyncio.gather(*tasks)

    


    async def clean_up(self) -> None:
        await db.clear_patch(self.patch.patch)
        logger.error(f"Successfully cleaned up patch '{self.patch.patch}'!")



    def get_dict_from_request(url: str) -> dict:
        return requests.get(url).json()
    
    def get_html_from_request(url: str) -> bytes:
        session = HTMLSession()
        return session.get(url).content