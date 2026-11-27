import asyncio
import logging
import requests

from datetime import datetime
from pathlib import Path
from requests.exceptions import RequestException
from urllib.error import URLError, HTTPError

import src.server.database as db
from src.server.loader.champion_source import WIKI_API
from src.server.loader.patch_notes import hotfix_dates, page_text, patch_page_params

from src.server.loader.helper import (
    info_loader,
    patch_sort_key,
    riot_to_wiki_patch,
    SafeSession
)
from src.server.loader.patchexceptions import PatcherError

from src.server.models.json_validation import (
    ItemsJson,
    ItemJson,
    SummonerspellsJson,
    SummonerspellJson
)
from src.server.models.image import Image
from src.server.models.patch import NewPatch, Patch


patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")
debug_logger = logging.getLogger("liandrys.debug")


URLS = info_loader().urls
PATHS = info_loader().paths


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


async def _list_other_data(patch_ver: str, session: SafeSession) -> tuple[list[tuple[str, ItemJson]], list[SummonerspellJson]]:
    """Items and summoner spells; the new patchloader lists champions and runes itself."""
    try:
        items = ItemsJson(**requests.get(URLS.dataLink + patch_ver + URLS.itemList).json())
        item_list = [(item_id, ItemJson(**item_data)) for item_id, item_data in items.data.items()]
    except Exception as e:
        raise PatcherError(f"Failed to fetch items for patch {patch_ver}", str(e))
    
    try:
        summoners = SummonerspellsJson(**requests.get(URLS.dataLink + patch_ver + URLS.summonerspellList).json())
        summoner_list = [SummonerspellJson(**summoner_data) for summoner_data in summoners.data.values()]
    except Exception as e:
        raise PatcherError(f"Failed to fetch summonerspells for patch {patch_ver}", str(e))

    return item_list, summoner_list


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
