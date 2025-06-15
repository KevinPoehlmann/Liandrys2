import aiohttp
import asyncio
import logging
import requests
import time

from datetime import datetime
from pathlib import Path
from pydantic import ValidationError
from requests.exceptions import RequestException
from urllib.error import URLError, HTTPError

import src.server.database as db
import src.server.loader.webscraper2 as ws

from src.server.loader.helper import (
    info_loader,
    riot_to_wiki_patch,
    RuneClass,
    SafeSession
)
from src.server.loader.patchexceptions import PatcherError, LoadError, ScrapeError

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
from src.server.models.champion import NewChampion
from src.server.models.image import Image
from src.server.models.item import NewItem
from src.server.models.patch import NewPatch, Patch
from src.server.models.rune import NewRune
from src.server.models.summonerspell import NewSummonerspell

from src.server.utils.logger import finalize_load_logfile, attach_fallback_logfile



patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")
debug_logger = logging.getLogger("liandrys.debug")


URLS = info_loader().urls
PATHS = info_loader().paths
ITEM_WIKI_NAMES = info_loader().itemWikiNames
RUNE_WIKI_NAMES = info_loader().runeWikiNames


patch_load_lock = asyncio.Lock()





async def load_data() -> None:
    """Main entry point to check and load new patch data."""
    if patch_load_lock.locked():
        load_logger.info("[LOAD] Patch data is already loading — skipping this call.")
        return

    async with patch_load_lock:
        try:
            _reload_info_loader()
            patches = await check_patch_available()
            if not patches:
                load_logger.info("[LOAD] Patch is up to date, no new data to load.")
                return
            latest_patch = await db.fetch_patch_latest()
            if latest_patch and latest_patch.total_count == latest_patch.loaded_total_count:
                await _load_all_patches(patches, latest_patch)
            else:
                await _load_fresh_database(patches)
        except Exception as e:
            patch_logger.exception(f"[PATCH] [UNEXPECTED] ❌ {type(e).__name__}: {e}")
            load_logger.error(f"[LOAD] Patch load failed!")



async def check_patch_available() -> dict[str, list[datetime]]:
    all_patches = _fetch_riot_patch_list()   
    db_patch = await db.fetch_patch_latest()
    patch_list = _get_newer_patches(db_patch, all_patches)
    hotfixes = await _check_wiki_for_hotfixes(patch_list)
    result = _get_newer_hotfixes(db_patch, hotfixes)
    return result



# --- Internal functions (to be expanded later) ---


def _fetch_riot_patch_list() -> list[str]:
    versions_url = URLS.patches

    try:
        response = requests.get(versions_url)
        response.raise_for_status()
        patches = response.json()
    except RequestException as e:
        raise PatcherError(str(e), "Couldn't fetch versions.json from Riot!") from e
    except ValueError as e:
        raise PatcherError("Invalid JSON received from versions.json", "Couldn't parse version.json") from e

    if not (isinstance(patches, list) and len(patches) >= 2 and isinstance(patches[0], str) and isinstance(patches[1], str)):
        raise PatcherError("Versions.json file is in the wrong shape!", "Couldn't validate version.json!")

    return patches


def _get_newer_patches(db_patch: Patch | None, patches: list[str]) -> list[str]:
    if not db_patch:
        return [patches[0]]
    try:
        index = patches.index(db_patch.patch)
    except ValueError:
        raise PatcherError(
            f"Patch {db_patch.patch} not found in Riot list. Investigate what changed.",
            "Patch not found in patch list."
        )
    return patches[:index+1]


async def _check_wiki_for_hotfixes(patch_list: list[str]) -> dict[str, list[datetime]]:
    hotfix_results = {}

    for patch in patch_list:
        wiki_patch = riot_to_wiki_patch(patch)
        wiki_url = URLS.wiki + wiki_patch

        try:
            response = requests.get(wiki_url)
            response.raise_for_status()
        except requests.RequestException as e:
            raise PatcherError(f"Could not fetch wiki patch: {wiki_url}", "Wiki page not found or unavailable") from e

        hotfix_results[patch] = ws.scrape_hotfix_list(response.text)

    return hotfix_results


def _get_newer_hotfixes(db_patch: Patch | None, hotfixes: dict[str, list[datetime]]) -> dict[str, list[datetime]]:
    if not db_patch:
        for patch, hotfix_list in hotfixes.items():
            if hotfix_list:
                hotfixes[patch] = [max(hotfix_list)]
        return hotfixes

    if db_patch.hotfix:
        hotfixes[db_patch.patch] = [hotfix for hotfix in hotfixes[db_patch.patch] if hotfix > db_patch.hotfix or (hotfix == db_patch.hotfix and db_patch.total_count > db_patch.loaded_total_count)]
    if not hotfixes[db_patch.patch] and db_patch.loaded_total_count == db_patch.total_count:
        del hotfixes[db_patch.patch]
    return hotfixes





async def _load_fresh_database(hotfixes_to_process: dict[str, list[datetime]]) -> None:
    patch, hotfix_list = next(iter(hotfixes_to_process.items()))
    hotfix = hotfix_list[-1] if hotfix_list else None
    attach_fallback_logfile()
    patch_logger.info("-" * 60)
    patch_logger.info(f"Loading fresh database for patch {patch}, hotfix: {hotfix}")
    load_logger.info("-" * 60)
    load_logger.info(f"Loading fresh database for patch {patch}, hotfix: {hotfix}")
    start_time = time.monotonic()

    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as aio_session:
        session = SafeSession(aio_session)

        champion_list, item_list, rune_list, summonerspell_list = await _list_data(patch, session)
        
        latest_patch = await db.fetch_patch_latest()
        if latest_patch and latest_patch.patch == patch and latest_patch.hotfix == hotfix:
            new_patch = latest_patch
        else:
        
            new_patch = NewPatch(
                patch=patch,
                hotfix=hotfix,
                champion_count=len(champion_list),
                item_count=len(item_list),
                rune_count=len(rune_list),
                summonerspell_count=len(summonerspell_list),
            )

        tasks = [
            _load_all_champions(champion_list, session, new_patch),
            _load_all_items(item_list, session, new_patch),
            _load_all_runes(rune_list, session, new_patch),
            _load_all_summonerspells(summonerspell_list, session, new_patch)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        load_errors = [r for r in results if isinstance(r, LoadError)]
        unexpected_errors = [r for r in results if isinstance(r, Exception) and not isinstance(r, LoadError)]

        new_patch.update_totals()
        patch_id = await db.upsert_patch(new_patch)
        duration = time.monotonic() - start_time

        if load_errors or unexpected_errors:
            for e in load_errors:
                name = e.name.upper() or "?"
                type_ = e.type.upper() or "?"
                url = e.url or "?"
                patch_logger.error(f"[{type_.upper()}] [LOAD] [{name}] ❌ Error {e.code}: {e.reason} — Failed to load from {url}")

            for e in unexpected_errors:
                patch_logger.exception(f"[PATCH] [UNEXPECTED] ❌ {type(e).__name__}: {e}")

            load_logger.error(f"[LOAD] [Patch] Failed to load  patch {patch} with hotfix {hotfix}.")
            load_logger.error(f"[LOAD] [Patch] Loaded {new_patch.loaded_total_count} / {new_patch.total_count} objects.")
            load_logger.error(f"[LOAD] [Patch] Duration: {duration:.2f} seconds")
            return

    load_logger.info(f"Finished loading fresh database for patch {patch}, hotfix: {hotfix}")
    load_logger.info(f"Total duration: {duration:.2f} seconds")
    load_logger.info("-" * 60)



async def _list_data(patch_ver: str, session: SafeSession) -> tuple[list[ChampionJson], list[tuple[str, ItemJson]], list[RuneClass], list[SummonerspellJson]]: 
    try:
        champions = ChampionsJson(**requests.get(URLS.dataLink + patch_ver + URLS.championFull).json())
        champion_list = [ChampionJson(**data) for data in champions.data.values()]
    except Exception as e:
        raise PatcherError(f"Failed to fetch champions for patch {patch_ver}", str(e))
    
    try:
        items = ItemsJson(**requests.get(URLS.dataLink + patch_ver + URLS.itemList).json())
        item_list = [(item_id, ItemJson(**item_data)) for item_id, item_data in items.data.items()]
    except Exception as e:
        raise PatcherError(f"Failed to fetch items for patch {patch_ver}", str(e))
    
    try:
        runes = requests.get(URLS.dataLink + patch_ver + URLS.runeList).json()
        rune_list = []
        tree_icons = []
        for tree in runes:
            rune_tree = RuneTreeJson(**tree)
            tree_icons.append(rune_tree.icon)
            for i, row in enumerate(rune_tree.slots):
                for rune in row.runes:
                    rune_list.append(RuneClass(rune, rune_tree.name, rune_tree.id_, i))
        await _load_rune_tree_images(tree_icons, session)
    except Exception as e:
        raise PatcherError(f"Failed to fetch runes for patch {patch_ver}", str(e))

    try:
        summoners = SummonerspellsJson(**requests.get(URLS.dataLink + patch_ver + URLS.summonerspellList).json())
        summoner_list = [SummonerspellJson(**summoner_data) for summoner_data in summoners.data.values()]
    except Exception as e:
        raise PatcherError(f"Failed to fetch summonerspells for patch {patch_ver}", str(e))

    return champion_list, item_list, rune_list, summoner_list


async def _load_all_champions(champion_list: list[ChampionJson], session: SafeSession, patch: NewPatch) -> None:
    tasks = [
        _load_champion(champion_json, session, patch)
        for champion_json in champion_list
    ]
    await asyncio.gather(*tasks)


async def _load_all_items(item_list: list[tuple[str, ItemJson]], session: SafeSession, patch: NewPatch) -> None:
    tasks = [
        _load_item(item_id, item_data, session, patch)
        for item_id, item_data in item_list
    ]
    await asyncio.gather(*tasks)


async def _load_all_runes(rune_list: list[RuneClass], session: SafeSession, patch: NewPatch) -> None:
    rune_tasks = [
        _load_rune(rune, session, patch)
        for rune in rune_list
    ]
    await asyncio.gather(*rune_tasks)


async def _load_all_summonerspells(summonerspell_list: list[SummonerspellJson], session: SafeSession, patch: NewPatch) -> None:
    summonerspell_tasks = [
        _load_summonerspell(stats, session, patch)
        for stats in summonerspell_list
    ]
    await asyncio.gather(*summonerspell_tasks)



async def _load_champion(champion_json: ChampionJson, session: SafeSession, patch: NewPatch) -> None:
    if await db.exists_champion_by_name(champion_json.name, patch.patch, patch.hotfix):
        return
    champion_wiki = await _fetch_wiki_html(champion_json.name, "Champion", patch, session)
    if not champion_wiki:
        return
    try:
        # Use webscraper to create the Champion object
        champion = ws.scrape_champion(champion_json, champion_wiki, patch.patch, patch.hotfix)
        if not champion:
            _save_cached_html("champion", champion_json.name, patch, champion_wiki)
            patch_logger.error(f"[CHAMPION] [LOAD] [{champion_json.name}] ❌ Failed to create object")
            load_logger.error(f"[CHAMPION] {champion_json.name} ❌ Failed to load")
            return
    except Exception as e:
        _save_cached_html("champion", champion_json.name, patch, champion_wiki)
        patch_logger.exception(f"[CHAMPION] [LOAD] [{champion_json.name}] ❌ Failed to create object: {e}")
        load_logger.error(f"[CHAMPION] {champion_json.name} ❌ Failed to load")
        raise

    # Download associated images
    try:
        await _load_image(champion_json.image, session, patch)
        await _load_image(champion_json.passive.image, session, patch)
        for spell in champion_json.spells:
            await _load_image(spell.image, session, patch)
    except Exception as e:
        patch_logger.exception(f"[CHAMPION] [IMAGE] [{champion_json.name}] ❌ Failed to load images: {e}")

    # Save to database
    await db.add_champion(champion)
    patch.loaded_champion_count += 1
    load_logger.info(f"[CHAMPION] {champion.name} ✔ Loaded successfully")


async def _load_item(item_id: str, item_json: ItemJson, session: SafeSession, patch: NewPatch) -> None:
    if await db.exists_item_by_name(item_json.name, patch.patch, patch.hotfix):
        return
    
    item_wiki = await _fetch_wiki_html(item_json.name, "Item", patch, session)
    if not item_wiki:
        return
    try:
        item = ws.scrape_item(item_id, item_json, item_wiki, patch.patch, patch.hotfix)
        if not item:
            _save_cached_html("item", item_id, patch, item_wiki)
            patch_logger.error(f"[ITEM] [LOAD] [{item_json.name}] ❌ Failed to create object")
            load_logger.error(f"[ITEM] {item_json.name} ❌ Failed to load")
            return

    except Exception as e:
        _save_cached_html("item", item_id, patch, item_wiki)
        patch_logger.exception(f"[ITEM] [LOAD] [{item_json.name}] ❌ Failed to create object: {e}")
        load_logger.error(f"[ITEM] {item_json.name} ❌ Failed to load")
        raise
    try:
        await _load_image(item_json.image, session, patch)
    except Exception as e:
        patch_logger.warning(f"[ITEM] [IMAGE] [{item_json.name}] ❌ Failed loading image: {e}")

    await db.add_item(item)
    patch.loaded_item_count += 1
    load_logger.info(f"[ITEM] {item.name} ✔ Loaded successfully")


async def _load_rune(rune_class: RuneClass, session: SafeSession, patch: NewPatch) -> None:
    if await db.exists_rune_by_name(rune_class.rune.name, patch.patch, patch.hotfix):
        return
    
    rune_wiki = await _fetch_wiki_html(rune_class.rune.name, "Rune", patch, session)
    if not rune_wiki:
        return
    try:
        image = await _load_image_rune(rune_class.rune.icon, session)
    except Exception as e:
        patch_logger.exception(f"[RUNE] [IMAGE] [{rune_class.rune.name}] ❌ Failed to load image: {e}")
    try:
        rune = ws.scrape_rune(rune_class, rune_wiki, image, patch.patch, patch.hotfix)
        if not rune:
            _save_cached_html("rune", rune_class.rune.name, patch, rune_wiki)
            patch_logger.error(f"[RUNE] [LOAD] [{rune_class.rune.name}] ❌ Failed to create object")
            load_logger.error(f"[RUNE] {rune_class.rune.name} ❌ Failed to load")
            return
    except Exception as e:
        _save_cached_html("rune", rune_class.rune.name, patch, rune_wiki)
        patch_logger.exception(f"[RUNE] [LOAD] [{rune_class.rune.name}] ❌ Failed to create object: {e}")
        load_logger.error(f"[RUNE] {rune_class.rune.name} ❌ Failed to load")
        raise

    await db.add_rune(rune)
    patch.loaded_rune_count += 1
    load_logger.info(f"[RUNE] {rune.name} ✔ Loaded successfully")


async def _load_summonerspell(summonerspell_json: SummonerspellJson, session: SafeSession, patch: NewPatch) -> None:
    if await db.exists_summonerspell_by_name(summonerspell_json.name, patch.patch, patch.hotfix):
        return
    
    summonerspell_wiki = await _fetch_wiki_html(summonerspell_json.name, "Summonerspell", patch, session)
    if not summonerspell_wiki:
        return
    try:
        summonerspell = ws.scrape_summonerspell(summonerspell_json, summonerspell_wiki, patch.patch, patch.hotfix)
        if not summonerspell:
            _save_cached_html("summonerspell", summonerspell_json.name, patch, summonerspell_wiki)
            patch_logger.error(f"[SUMMONERSPELL] [LOAD] [{summonerspell_json.name}] ❌ Failed to create object")
            load_logger.error(f"[SUMMONERSPELL] {summonerspell_json.name} ❌ Failed to load")
            return
    except Exception as e:
        _save_cached_html("summonerspell", summonerspell_json.name, patch, summonerspell_wiki)
        patch_logger.exception(f"[SUMMONERSPELL] [LOAD] [{summonerspell_json.name}] ❌ Failed to create object: {e}")
        load_logger.error(f"[SUMMONERSPELL] {summonerspell_json.name} ❌ Failed to load")
        raise
    
    try:
        await _load_image(summonerspell_json.image, session, patch)
    except Exception as e:
        patch_logger.exception(f"[SUMMONERSPELL] [IMAGE] [{summonerspell_json.name}] ❌ Failed to load image: {e}")

    await db.add_summonerspell(summonerspell)
    patch.loaded_summonerspell_count += 1
    load_logger.info(f"[SUMMONERSPELL] {summonerspell.name} ✔ Loaded successfully")



async def _fetch_wiki_html(name: str, type_: str, patch: NewPatch, session: SafeSession) -> str:
    wiki_names_map = {
        "Item": ITEM_WIKI_NAMES,
        "Rune": RUNE_WIKI_NAMES,
    }

    resolved_name = wiki_names_map.get(type_, {}).get(name, name)
    wiki_url = URLS.wiki + resolved_name

    try:
        html = _load_cached_html(type_, resolved_name, patch)
        _delete_cached_html(type_, resolved_name, patch)
        return html
    except FileNotFoundError:
        pass

    try:
        return await session.get_html(wiki_url)
    except HTTPError as e:
        raise LoadError(e.code, e.reason, e.url, type_, name)
    except URLError as e:
        raise LoadError(
            code=getattr(e, "errno", -1),
            reason=str(getattr(e, "reason", "Unknown error")),
            url=e.filename,
            type=type_,
            name=name)
    except ValidationError as e:
        raise LoadError(9, str(e), "", type_, name)




async def _load_image(image: Image, session: SafeSession, patch: NewPatch, force_reload: bool = False) -> None:
    img_path = Path(PATHS.image) / image.group / image.full

    if not img_path.exists() or force_reload:
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_url = f"{URLS.dataLink}{patch.patch}/{URLS.image}{image.group}/{image.full}"
        try:
            with open(img_path, "wb") as img_file:
                img_file.write(await session.get_bytes(img_url))
        except HTTPError as e:
            raise LoadError(e.code, e.reason, e.url, image.group, image.full)
        except URLError as e:
            raise LoadError(
                code=getattr(e, "errno", -1),
                reason=str(getattr(e, "reason", "Unknown error")),
                url=e.filename,
                type=image.group,
                name=image.full)

    # Download the sprite only if present and x/y are 0 (as Riot does it)
    if image.sprite and (image.x == image.y == 0):
        sprite_path = Path(PATHS.sprite) / image.sprite
        if not sprite_path.exists() or force_reload:
            sprite_path.parent.mkdir(parents=True, exist_ok=True)
            sprite_url = f"{URLS.dataLink}{patch.patch}{URLS.sprite}{image.sprite}"
            try:
                with open(sprite_path, "wb") as sprite_file:
                    sprite_file.write(await session.get_bytes(sprite_url))
            except HTTPError as e:
                raise LoadError(e.code, e.reason, e.url, image.group, image.full)
            except URLError as e:
                raise LoadError(
                    code=getattr(e, "errno", -1),
                    reason=str(getattr(e, "reason", "Unknown error")),
                    url=e.filename,
                    type=image.group,
                    name=image.full)


async def _load_image_rune(icon: str, session: SafeSession) -> Image:
    image = Image(
        full=icon.rsplit("/", 1)[-1],
        group="rune"
    )
    img_path = Path(PATHS.image) / image.group / image.full

    if not img_path.exists():
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_url = f"{URLS.dataLink}{URLS.image}{icon}"
        try:
            with open(img_path, "wb") as image_file:
                image_file.write(await session.get_bytes(img_url))
        except (HTTPError, URLError) as e:
            patch_logger.error(f"[RUNE] [IMAGE] [{icon}] ❌ Failed to load image: {e}")

    return image


async def _load_rune_tree_images(icon_list: list[str], session: SafeSession) -> None:
    tasks = [_load_image_rune(icon, session) for icon in icon_list]
    await asyncio.gather(*tasks)




async def _load_all_patches(hotfixes_to_process: dict[str, list[datetime]], old_patch: NewPatch) -> None:
    for patch_str in sorted(hotfixes_to_process.keys()):
        hotfix_list = sorted(hotfixes_to_process[patch_str])
        hotfix_list = hotfix_list or [None]

        for hotfix in hotfix_list:
            finalize_load_logfile(old_patch.patch, old_patch.hotfix)
            try:
                await _load_patch(patch_str, hotfix, old_patch)
                new_patch = await db.fetch_patch_latest()
                if new_patch is None:
                    raise LoadError(-1, "Patch not found after loading", "", "patch", f"{patch_str} - {hotfix}")
                old_patch = new_patch
            except Exception as e:
                patch_logger.exception(f"[PATCH] [PATCH] [{patch_str} - {hotfix}] ❌ Failed to load patch: {e}")
                new_patch = NewPatch(patch=patch_str, hotfix=hotfix)
                await _clean_up(new_patch)
                raise


async def _load_patch(patch_str: str, hotfix: datetime | None, old_patch: NewPatch) -> None:
    attach_fallback_logfile()
    patch_logger.info("-" * 60)
    patch_logger.info(f"Loading patch {patch_str}, hotfix: {hotfix}")
    load_logger.info("-" * 60)
    load_logger.info(f"Loading patch {patch_str}, hotfix {hotfix}")
    start_time = time.monotonic()

    patch = riot_to_wiki_patch(patch_str)
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as aio_session:
        session = SafeSession(aio_session)
        patch_wiki = await _fetch_wiki_html(patch, "Patch", old_patch, session)
        changes = ws.scrape_patch(patch_wiki, hotfix)

        new_patch = NewPatch(
            patch=patch_str,
            hotfix=hotfix,
            champion_count=old_patch.champion_count,
            item_count=old_patch.item_count,
            rune_count=old_patch.rune_count,
            summonerspell_count=old_patch.summonerspell_count
        )
            
        await _patch_champions(changes.get("champions", {}), new_patch, old_patch, session)
        await _patch_items(changes.get("items", {}), new_patch, old_patch, session)
        await _patch_runes(changes.get("runes", {}), new_patch, old_patch, session)
        await _patch_summonerspells(changes.get("summonerspells", {}), new_patch, old_patch, session)

    new_patch.update_totals()
    patch_id = await db.upsert_patch(new_patch)
    duration = time.monotonic() - start_time
    load_logger.info(f"Finished loading patch {patch}, hotfix: {hotfix}")
    load_logger.info(f"Total duration: {duration:.2f} seconds")
    load_logger.info("-" * 60)



async def _patch_champions(changes: dict, new_patch: NewPatch, old_patch: NewPatch, session: SafeSession) -> None:
    all_champions = await db.fetch_champions_by_patch(old_patch.patch, old_patch.hotfix)  # or old_patch.patch

    for name in changes.get("new", []):
        new_patch.champion_count += 1
        try:
            json_data = await session.get_json(URLS.dataLink + new_patch.patch + URLS.championData + name)
            champion_json = ChampionJson(**json_data)
            await _load_champion(champion_json, session, new_patch)
        except Exception as e:
            patch_logger.exception(f"[CHAMPION] [PATCH] [{name}] ❌ Failed to load new champion: {e}")
            load_logger.error(f"[CHAMPION] {name} ❌ Failed to load")

    for champion in all_champions:
        champion.patch = new_patch.patch
        champion.hotfix = new_patch.hotfix

        if champion.name in changes.get("changed", {}):
            new_patch.changed_champion_count += 1
            diff = changes["changed"][champion.name]
            try:
                await _add_changes_champion(champion, diff)
                load_logger.info(f"[CHAMPION] {champion.name} ✔ Patched successfully")
            except Exception as e:
                patch_logger.exception(f"[CHAMPION] [PATCH] [{champion.name}] ❌ Failed to apply changes: {e}")
                load_logger.error(f"[CHAMPION] {champion.name} ❌ Failed to patch")

        await db.add_champion(champion)
        new_patch.loaded_champion_count += 1


async def _add_changes_champion(champion: NewChampion, diff: dict[str, list[str]]) -> None:
    if champion.passive.name in diff:
        champion.passive.changes.extend(diff.pop(champion.passive.name))
        champion.passive.validated = False
    if champion.q.name in diff:
        champion.q.changes.extend(diff.pop(champion.q.name))
        champion.q.validated = False
    if champion.w.name in diff:
        champion.w.changes.extend(diff.pop(champion.w.name))
        champion.w.validated = False
    if champion.e.name in diff: 
        champion.e.changes.extend(diff.pop(champion.e.name))
        champion.e.validated = False
    if champion.r.name in diff:
        champion.r.changes.extend(diff.pop(champion.r.name))
        champion.r.validated = False
    champion.changes.extend([line for lines in diff.values() for line in lines])
    champion.validated = False




async def _patch_items(changes: dict, new_patch: NewPatch, old_patch: NewPatch, session: SafeSession) -> None:
    all_items = await db.fetch_items_by_patch(old_patch.patch, old_patch.hotfix)

    try:
        items_data = await session.get_json(URLS.dataLink + new_patch.patch + URLS.itemList)
        items = ItemsJson(**items_data)
        new_items = [(item_id, ItemJson(**item_data)) for item_id, item_data in items.data.items() if item_data["name"] in changes.get("new", [])]
        
        for new_item_id, new_item_json in new_items:
            new_patch.item_count += 1
            try:
                await _load_item(new_item_id, new_item_json, session, new_patch)
                changes["new"].remove(new_item_json.name)
            except Exception as e:
                patch_logger.error(f"[ITEM] [PATCH] [{new_item_json.name}] ❌ Failed to load new item: {e}")
                load_logger.error(f"[ITEM] {new_item_json.name} ❌ Failed to load")

        for item_name in changes.get("new", []):
            patch_logger.error(f"[ITEM] [PATCH] [{item_name}] ❌ Item not found in the new patch data!")
            load_logger.error(f"[ITEM] {item_name} ❌ Item not found in the new patch data!")
    except Exception as e:
        patch_logger.exception(f"[ITEM] [PATCH] ❌ Failed to patch NEW items: {e}")
        load_logger.error(f"[ITEM] ❌ Failed to patch NEW items: {e}")

    for item in all_items:
        if item.name in changes.get("deleted", []):
            new_patch.item_count -= 1
            load_logger.info(f"[ITEM] {item.name} ✔ Deleted successfully")
            continue 
        item.patch = new_patch.patch
        item.hotfix = new_patch.hotfix
        if item.name in changes.get("changed", {}):
            new_patch.changed_item_count += 1
            diff = changes["changed"][item.name]
            try:
                await _add_changes_item(item, diff)
                load_logger.info(f"[ITEM] {item.name} ✔ Patched successfully")
            except Exception as e:
                patch_logger.exception(f"[ITEM] [PATCH] [{item.name}] ❌ Failed to apply changes: {e}")
                load_logger.error(f"[ITEM] {item.name} ❌ Failed to patch")

        await db.add_item(item)
        new_patch.loaded_item_count += 1


async def _add_changes_item(item: NewItem, diff: list) -> None:
    item.changes.extend(diff)
    item.validated = False



async def _patch_runes(changes: dict, new_patch: NewPatch, old_patch: NewPatch, session: SafeSession) -> None:
    all_runes = await db.fetch_runes_by_patch(old_patch.patch, old_patch.hotfix)

    try:
        runes_data = await session.get_json(URLS.dataLink + new_patch.patch + URLS.runeList)
        for rune_name in changes.get("new", []):
            new_patch.rune_count += 1
            rune_class = _find_rune(rune_name, runes_data)
            if rune_class:
                try:
                    await _load_rune(rune_class, session, new_patch)
                except Exception as e:
                    patch_logger.exception(f"[RUNE] [PATCH] [{rune_name}] ❌ Failed to load new rune: {e}")
                    load_logger.error(f"[RUNE] {rune_name} ❌ Failed to load")
            else:
                patch_logger.error(f"[RUNE] [PATCH] [{rune_name}] ❌ Rune not found in the new patch data!")
                load_logger.error(f"[RUNE] {rune_name} ❌ Rune not found in the new patch data!")
    except Exception as e:
        patch_logger.exception(f"[RUNE] [PATCH] ❌ Failed to patch NEW runes: {e}")
        load_logger.error(f"[RUNE] ❌ Failed to patch NEW runes: {e}")    

    for rune in all_runes:
        if rune.name in changes.get("deleted", []):
            new_patch.rune_count -= 1
            load_logger.info(f"[RUNE] {rune.name} ✔ Deleted successfully")
            continue  # optional: log & skip

        rune.patch = new_patch.patch
        rune.hotfix = new_patch.hotfix
        if rune.name in changes.get("changed", {}):
            new_patch.changed_rune_count += 1
            try:
                diff = changes["changed"][rune.name]
                await _add_changes_rune(rune, diff)
                load_logger.info(f"[RUNE] {rune.name} ✔ Patched successfully")
            except Exception as e:
                patch_logger.exception(f"[RUNE] [PATCH] [{rune.name}] ❌ Failed to apply changes: {e}")
                load_logger.error(f"[RUNE] {rune.name} ❌ Failed to patch")

        await db.add_rune(rune)
        new_patch.loaded_rune_count += 1


def _find_rune(rune_name: str, runes_data: dict) -> RuneClass | None:
    for tree in runes_data:
        rune_tree = RuneTreeJson(**tree)
        for i, row in enumerate(rune_tree.slots):
            for rune in row.runes:
                if rune.name == rune_name:
                    return RuneClass(rune, rune_tree.name, rune_tree.id_, i)
    return None



async def _add_changes_rune(rune: NewRune, diff: list) -> None:
    rune.changes.extend(diff)
    rune.validated = False


async def _patch_summonerspells(changes: dict, new_patch: NewPatch, old_patch: NewPatch, session: SafeSession) -> None:
    all_spells = await db.fetch_summonerspells_by_patch(old_patch.patch, old_patch.hotfix)

    try:
        summoners_data = await session.get_json(URLS.dataLink + new_patch.patch + URLS.summonerspellList)
        summoners = SummonerspellsJson(**summoners_data)
        new_summoners = [SummonerspellJson(**summoner_data) for summoner_data in summoners.data.values() if summoner_data["name"] in changes.get("new", [])]

        for new_summoner_json in new_summoners:
            new_patch.summonerspell_count += 1
            try:
                await _load_summonerspell(new_summoner_json, session, new_patch)
                changes["new"].remove(new_summoner_json.name)
            except Exception as e:
                patch_logger.exception(f"[SUMMONERSPELL] [PATCH] [{new_summoner_json.name}] ❌ Failed to load new summonerspell: {e}")
                load_logger.error(f"[SUMMONERSPELL] {new_summoner_json.name} ❌ Failed to load")

        for summoner_name in changes.get("new", []):
            patch_logger.error(f"[SUMMONERSPELL] [PATCH] [{summoner_name}] ❌ Summonerspell not found in the new patch data!")
            load_logger.error(f"[SUMMONERSPELL] {summoner_name} ❌ Summonerspell not found in the new patch data!")
    except Exception as e:
        patch_logger.exception(f"[SUMMONERSPELL] [PATCH] ❌ Failed to patch NEW summonerspells: {e}")
        load_logger.error(f"[SUMMONERSPELL] ❌ Failed to patch NEW summonerspells: {e}")

    for spell in all_spells:
        if spell.name in changes.get("deleted", []):
            new_patch.summonerspell_count -= 1
            load_logger.info(f"[SUMMONERSPELL] {spell.name} ✔ Deleted successfully")
            continue  # optional: log & skip

        spell.patch = new_patch.patch
        spell.hotfix = new_patch.hotfix
        if spell.name in changes.get("changed", {}):
            new_patch.changed_summonerspell_count += 1
            diff = changes["changed"][spell.name]
            try:
                await _add_changes_summonerspell(spell, diff)
                load_logger.info(f"[SUMMONERSPELL] {spell.name} ✔ Patched successfully")
            except Exception as e:
                patch_logger.exception(f"[SUMMONERSPELL] [PATCH] [{spell.name}] ❌ Failed to apply changes: {e}")
                load_logger.error(f"[SUMMONERSPELL] {spell.name} ❌ Failed to patch")

        await db.add_summonerspell(spell)
        new_patch.loaded_summonerspell_count += 1


async def _add_changes_summonerspell(spell: NewSummonerspell, diff: list) -> None:
    spell.changes.extend(diff)
    spell.validated = False




async def _clean_up(patch: NewPatch) -> None:
    result = await db.clear_patch(patch.patch, patch.hotfix)
    for handler in patch_logger.handlers:
        handler.flush()
    
    if not result["cleanup_successful"]:
        patch_logger.error(f"[PATCH] [CLEANUP] [{patch.patch} - {patch.hotfix}] ❌ Cleanup failed!")
    else:
        patch_logger.warning(f"[PACTH] [PATCH] [{patch.patch} - {patch.hotfix}] Cleaned up.")
        for key, count in result.items():
            if key != "cleanup_successful":
                patch_logger.info(f"[PATCH] [CLEANUP] [{patch.patch} - {patch.hotfix}] - {key}: {count} document(s) removed")



def _reload_info_loader() -> None:
    """Reloads the info_loader module to refresh URLs and paths."""
    global URLS, PATHS, ITEM_WIKI_NAMES, RUNE_WIKI_NAMES
    info = info_loader()
    URLS = info.urls
    PATHS = info.paths
    ITEM_WIKI_NAMES = info.itemWikiNames
    RUNE_WIKI_NAMES = info.runeWikiNames



def _cache_filename(type_: str, name: str, patch: NewPatch) -> Path:
    safe_name = name.replace(" ", "_").replace("'", "")
    hotfix_str = patch.hotfix.isoformat().replace(":", "-") if patch.hotfix else "none"
    filename = f"{safe_name}__{patch.patch}__{hotfix_str}.html"
    return Path(PATHS.cache) / type_ / filename


def _load_cached_html(type_: str, name: str, patch: NewPatch) -> str:
    path = _cache_filename(name, type_, patch)
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError

def _save_cached_html(type_: str, name: str, patch: NewPatch, html: str) -> None:
    path = _cache_filename(name, type_, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    patch.cached_documents += 1

def _delete_cached_html(type_: str, name: str, patch: NewPatch) -> None:
    path = _cache_filename(name, type_, patch)
    if path.exists():
        patch.cached_documents -= 1
        path.unlink()



def load_local_html(name: str) -> str:
    filename = name.lower().replace(" ", "_") + ".html"
    file_path = Path("src/tests/static/html") / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Local HTML file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")

