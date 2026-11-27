import asyncio
import logging
import requests

from datetime import datetime
from pathlib import Path
from pydantic import ValidationError
from requests.exceptions import RequestException
from urllib.error import URLError, HTTPError

import src.server.database as db
import src.server.loader.webscraper2 as ws
from src.server.loader.champion_source import WIKI_API
from src.server.loader.names import NameDictionary
from src.server.loader.patch_notes import hotfix_dates, page_text, patch_page_params

from src.server.loader.helper import (
    info_loader,
    patch_sort_key,
    riot_to_wiki_patch,
    RuneClass,
    SafeSession
)
from src.server.loader.patchexceptions import PatcherError, LoadError

from src.server.models.json_validation import (
    ItemsJson,
    ItemJson,
    RuneTreeJson,
    SummonerspellsJson,
    SummonerspellJson
)
from src.server.models.change import with_hotfix_lines
from src.server.models.enums import Stat
from src.server.models.image import Image
from src.server.models.patch import NewPatch, Patch
from src.server.models.passive import Passive
from src.server.models.rule import StatModifier
from src.server.models.rune import NewRune


patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")
debug_logger = logging.getLogger("liandrys.debug")


URLS = info_loader().urls
PATHS = info_loader().paths
WIKI_NAMES: dict[str, NameDictionary] = {}  # set by patchloader for each load
RUNE_STAT_SHARDS = info_loader().runeStatShards


async def check_patch_available() -> list[str]:
    """The patches to load, oldest first: the ones newer than the database, plus an unfinished one to resume."""
    db_patch = await db.fetch_patch_latest()
    patches = _get_newer_patches(db_patch, _fetch_riot_patch_list())
    if db_patch and db_patch.loaded_total_count == db_patch.total_count:
        patches.remove(db_patch.patch)
    return sorted(patches, key=patch_sort_key)


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


def wiki_hotfix_dates(patch: str) -> list[datetime]:
    wiki_patch = riot_to_wiki_patch(patch)
    try:
        response = requests.get(WIKI_API, params=patch_page_params(wiki_patch))
        response.raise_for_status()
        text = page_text(response.json())
    except (requests.RequestException, ValueError) as e:
        raise PatcherError(f"Could not fetch wiki patch: {wiki_patch}", "Wiki page not found or unavailable") from e
    if text is None:
        raise PatcherError(f"No wiki patch page: {wiki_patch}", "Wiki page not found or unavailable")
    return hotfix_dates(text)


async def _list_other_data(patch_ver: str, session: SafeSession) -> tuple[list[tuple[str, ItemJson]], list[RuneClass], list[SummonerspellJson]]:
    """Items, runes and summoner spells; the new patchloader lists champions itself."""
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
                for j, rune in enumerate(row.runes):
                    rune_list.append(RuneClass(rune, rune_tree.name, rune_tree.id_, i, j))
        await _load_rune_tree_images(tree_icons, session)
    except Exception as e:
        raise PatcherError(f"Failed to fetch runes for patch {patch_ver}", str(e))

    try:
        summoners = SummonerspellsJson(**requests.get(URLS.dataLink + patch_ver + URLS.summonerspellList).json())
        summoner_list = [SummonerspellJson(**summoner_data) for summoner_data in summoners.data.values()]
    except Exception as e:
        raise PatcherError(f"Failed to fetch summonerspells for patch {patch_ver}", str(e))

    return item_list, rune_list, summoner_list


async def _load_all_runes(rune_list: list[RuneClass], session: SafeSession, patch: NewPatch) -> None:
    rune_tasks = [
        _load_rune(rune, session, patch)
        for rune in rune_list
    ]
    rune_tasks.append(_load_rune_stat_shards(patch))
    await asyncio.gather(*rune_tasks)


async def _load_rune(rune_class: RuneClass, session: SafeSession, patch: NewPatch) -> None:
    if await db.exists_rune_by_name(rune_class.rune.name, patch.patch):
        return
    
    rune_wiki = await _fetch_wiki_html(_wiki_name("runes", str(rune_class.rune.id_), rune_class.rune.name), "Rune", patch, session)
    if not rune_wiki:
        return
    try:
        image = await _load_image_rune(rune_class.rune.icon, session)
    except Exception as e:
        patch_logger.exception(f"[RUNE] [IMAGE] [{rune_class.rune.name}] ❌ Failed to load image: {e}")
    try:
        rune = ws.scrape_rune(rune_class, rune_wiki, image, patch.patch)
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


async def _load_rune_stat_shards(patch: NewPatch) -> None:
    patch.rune_count += len(RUNE_STAT_SHARDS)
    for shard in RUNE_STAT_SHARDS:
        if await db.exists_rune_by_name(shard.name, patch.patch):
            continue
        rune = NewRune(
            rune_id=shard.rune_id,
            name=shard.name,
            patch=patch.patch,
            tree="Stat Shard",
            tree_id=0,
            row=shard.row,
            slot=shard.slot,
            passive=Passive(
                name=shard.name,
                stats=[StatModifier(stat=shard.stat.stat, formula=shard.stat.scaling)],
            ),
            image=Image(
                full=shard.image,
                group="rune"
            )
        )
        await db.add_rune(rune)
        patch.loaded_rune_count += 1
        load_logger.info(f"[RUNE] {rune.name} ✔ Loaded successfully")


def _wiki_name(type_: str, ddragon_id: str, name: str) -> str:
    names = WIKI_NAMES.get(type_)
    return names.wiki_name(ddragon_id, name) if names else name


async def _fetch_wiki_html(name: str, type_: str, patch: NewPatch, session: SafeSession) -> str:
    """`name` is the wiki page."""
    wiki_url = URLS.wiki + name

    try:
        html = _load_cached_html(type_, name, patch)
        _delete_cached_html(type_, name, patch)
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
        img_url = f"{URLS.dataLink}{patch.patch}/{URLS.image}{image.group}/{image.full}"
        try:
            if not await _download_file(img_url, img_path, session):
                raise LoadError(404, "Image not found", img_url, image.group, image.full)
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
        img_url = f"{URLS.dataLink}{URLS.image}{icon}"
        try:
            if not await _download_file(img_url, img_path, session):
                patch_logger.error(f"[RUNE] [IMAGE] [{icon}] ❌ Image not found")
        except (HTTPError, URLError) as e:
            patch_logger.error(f"[RUNE] [IMAGE] [{icon}] ❌ Failed to load image: {e}")

    return image


async def _download_file(url: str, path: Path, session: SafeSession) -> bool:
    content = await session.get_bytes(url)
    if not content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return True


async def _load_rune_tree_images(icon_list: list[str], session: SafeSession) -> None:
    tasks = [_load_image_rune(icon, session) for icon in icon_list]
    await asyncio.gather(*tasks)


async def _patch_runes(changes: dict, new_patch: NewPatch, old_patch: NewPatch, session: SafeSession) -> None:
    all_runes = await db.fetch_runes_by_patch(old_patch.patch)

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
            for j, rune in enumerate(row.runes):
                if rune.name == rune_name:
                    return RuneClass(rune, rune_tree.name, rune_tree.id_, i, j)
    return None


async def _add_changes_rune(rune: NewRune, diff: list) -> None:
    rune.changes.extend(diff)
    rune.validated = False


async def hotfix_others(notes: dict, patch: NewPatch, hotfixed_at: datetime) -> None:
    """Runes named in a hotfix get its lines and lose their validation, in place."""
    types = {"runes": (db.fetch_runes_by_patch, db.update_rune)}
    for type_, (fetch, update) in types.items():
        type_notes = notes.get(type_, {})
        for status in ("new", "deleted"):
            for name in type_notes.get(status, []):
                patch_logger.warning(f"[{type_.upper()}] [HOTFIX] [{name}] {status} in a hotfix, not supported")
        changed = type_notes.get("changed", {})
        for document in await fetch(patch.patch):
            if document.name not in changed:
                continue
            if not document.changes:
                counter = f"changed_{type_[:-1]}_count"
                setattr(patch, counter, getattr(patch, counter) + 1)
            document.changes = with_hotfix_lines(document.changes, changed[document.name], hotfixed_at)
            document.validated = False
            await update(document)
            load_logger.info(f"[{type_.upper()}] {document.name} ✔ Hotfixed")


async def _clean_up(patch: NewPatch) -> None:
    result = await db.clear_patch(patch.patch)
    for handler in patch_logger.handlers:
        handler.flush()
    
    if not result["cleanup_successful"]:
        patch_logger.error(f"[PATCH] [CLEANUP] [{patch.patch}] ❌ Cleanup failed!")
    else:
        patch_logger.warning(f"[PACTH] [PATCH] [{patch.patch}] Cleaned up.")
        for key, count in result.items():
            if key != "cleanup_successful":
                patch_logger.info(f"[PATCH] [CLEANUP] [{patch.patch}] - {key}: {count} document(s) removed")


def _reload_info_loader() -> None:
    """Reloads the info_loader module to refresh URLs and paths."""
    global URLS, PATHS
    info = info_loader()
    URLS = info.urls
    PATHS = info.paths


def _cache_filename(type_: str, name: str, patch: NewPatch) -> Path:
    safe_name = name.replace(" ", "_").replace("'", "")
    filename = f"{safe_name}__{patch.patch}.html"
    return Path(PATHS.cache) / type_ / filename


def _load_cached_html(type_: str, name: str, patch: NewPatch) -> str:
    path = _cache_filename(type_, name, patch)
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError

def _save_cached_html(type_: str, name: str, patch: NewPatch, html: str) -> None:
    path = _cache_filename(type_, name, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    patch.cached_documents += 1

def _delete_cached_html(type_: str, name: str, patch: NewPatch) -> None:
    path = _cache_filename(type_, name, patch)
    if path.exists():
        patch.cached_documents -= 1
        path.unlink()


def load_local_html(name: str) -> str:
    filename = name.lower().replace(" ", "_") + ".html"
    file_path = Path("src/tests/static/html") / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Local HTML file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")

