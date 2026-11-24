"""Loads new patches. Champions come from CommunityDragon, Data Dragon and the wiki API. Items, runes, summoner spells
and patching forward still go through patchloader2 until they move here."""
import asyncio
import logging
import time
from datetime import datetime

import aiohttp

import src.server.database as db
import src.server.loader.patchloader2 as old
from src.server.loader.champion_builder import build_champion, wiki_mismatches
from src.server.loader.champion_source import (cdragon_version, fetch_build, fetch_champion_data, fetch_strings,
                                               load_raw_champion)
from src.server.loader.helper import SafeSession
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.models.json_validation import ChampionJson, ChampionsJson
from src.server.models.patch import NewPatch
from src.server.utils.logger import attach_fallback_logfile


patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")

DDRAGON = "https://ddragon.leagueoflegends.com/cdn/"
CHAMPION_CONCURRENCY = 5  # the wiki API answers too many parallel requests with 429

patch_load_lock = asyncio.Lock()


async def load_data() -> None:
    """Entry point: loads every patch that is newer than the database, or completes an unfinished first load."""
    if patch_load_lock.locked():
        load_logger.info("[LOAD] Patch data is already loading — skipping this call.")
        return
    async with patch_load_lock:
        try:
            old._reload_info_loader()
            patches = await old.check_patch_available()
            if not patches:
                load_logger.info("[LOAD] Patch is up to date, no new data to load.")
                return
            latest = await db.fetch_patch_latest()
            if latest and latest.total_count == latest.loaded_total_count:
                await old._load_all_patches(patches, latest)
            else:
                await load_fresh_database(patches)
        except Exception as e:
            patch_logger.exception(f"[PATCH] [UNEXPECTED] ❌ {type(e).__name__}: {e}")
            load_logger.error("[LOAD] Patch load failed!")


async def load_fresh_database(patches: dict[str, list[datetime]]) -> None:
    patch_name, hotfixes = next(iter(patches.items()))
    hotfix = hotfixes[-1] if hotfixes else None
    _log_section(f"Loading fresh database for patch {patch_name}, hotfix: {hotfix}")
    start = time.monotonic()

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as aio_session:
        session = SafeSession(aio_session)
        champions = await fetch_champion_list(session, patch_name)
        items, runes, summonerspells = await old._list_other_data(patch_name, session)
        patch = await _resumed_or_new_patch(patch_name, hotfix, NewPatch(
            patch=patch_name, hotfix=hotfix, champion_count=len(champions), item_count=len(items),
            rune_count=len(runes), summonerspell_count=len(summonerspells)))

        results = await asyncio.gather(
            load_all_champions(champions, session, patch),
            old._load_all_items(items, session, patch),
            old._load_all_runes(runes, session, patch),
            old._load_all_summonerspells(summonerspells, session, patch),
            return_exceptions=True,
        )

    for result in results:
        if isinstance(result, Exception):
            _log_error("PATCH", patch_name, result)
    patch.update_totals()
    await db.upsert_patch(patch)
    load_logger.info(f"[LOAD] Loaded {patch.loaded_total_count} / {patch.total_count} objects "
                     f"in {time.monotonic() - start:.2f} seconds")


async def _resumed_or_new_patch(patch_name: str, hotfix: datetime | None, new_patch: NewPatch) -> NewPatch:
    # An unfinished load of the same patch keeps its counters; existing objects are skipped.
    latest = await db.fetch_patch_latest()
    if latest and latest.patch == patch_name and latest.hotfix == hotfix:
        return latest
    return new_patch


async def fetch_champion_list(session: SafeSession, patch: str) -> list[ChampionJson]:
    """Data Dragon's list: key, max ranks, resource type and images, which CommunityDragon's champion file lacks."""
    data = await session.get_json(f"{DDRAGON}{patch}/data/en_GB/championFull.json")
    if not data:
        raise PatcherError(f"No champion list for patch {patch}", "Data Dragon's championFull.json is missing")
    return [ChampionJson(**champion) for champion in ChampionsJson(**data).data.values()]


async def load_all_champions(champions: list[ChampionJson], session: SafeSession, patch: NewPatch) -> None:
    version = cdragon_version(patch.patch)
    build = await fetch_build(session, version)
    strings = await fetch_strings(session, version)
    champion_data = await _champion_data_or_nothing(session)
    semaphore = asyncio.Semaphore(CHAMPION_CONCURRENCY)

    async def load(entry: ChampionJson) -> None:
        async with semaphore:
            await load_champion(entry, session, patch, build, strings, champion_data.get(entry.id_, {}))

    results = await asyncio.gather(*(load(entry) for entry in champions), return_exceptions=True)
    for entry, result in zip(champions, results):
        if isinstance(result, Exception):
            _log_error("CHAMPION", entry.name, result)
            load_logger.error(f"[CHAMPION] {entry.name} ❌ Failed to load")


async def _champion_data_or_nothing(session: SafeSession) -> dict[str, dict]:
    # Only a cross-check and the last change; champions load without it.
    try:
        return await fetch_champion_data(session)
    except (LoadError, ValueError, KeyError) as e:
        patch_logger.warning(f"[CHAMPION] [WIKI] Module:ChampionData not loaded, no cross-check: {e}")
        return {}


async def load_champion(entry: ChampionJson, session: SafeSession, patch: NewPatch, build: str,
                        strings: dict[str, str], champion_data: dict | None = None) -> None:
    if await db.exists_champion_by_name(entry.name, patch.patch, patch.hotfix):
        return
    raw = await load_raw_champion(session, patch.patch, patch.hotfix, entry.id_, entry.name, build, strings, champion_data)
    if not raw.wiki:
        patch_logger.warning(f"[CHAMPION] [WIKI] [{entry.name}] No wiki data templates found")
    if not raw.champion_data:
        patch_logger.warning(f"[CHAMPION] [WIKI] [{entry.name}] Not in Module:ChampionData")
    # Stored before building, so a champion the builder can't handle still has its raw data to look at.
    await db.upsert_raw_champion(raw)
    champion = build_champion(raw, entry)
    for mismatch in wiki_mismatches(champion, raw.champion_data):
        patch_logger.warning(f"[CHAMPION] [WIKI] [{entry.name}] {mismatch}")
    await db.add_champion(champion)
    patch.loaded_champion_count += 1
    load_logger.info(f"[CHAMPION] {entry.name} ✔ Loaded successfully")


def _log_error(type_: str, name: str, error: Exception) -> None:
    if isinstance(error, LoadError):
        patch_logger.error(f"[{type_}] [LOAD] [{name}] ❌ Error {error.code}: {error.reason} — {error.url}")
    else:
        patch_logger.error(f"[{type_}] [LOAD] [{name}] ❌ {type(error).__name__}: {error}", exc_info=error)


def _log_section(message: str) -> None:
    attach_fallback_logfile()
    for logger in (patch_logger, load_logger):
        logger.info("-" * 60)
        logger.info(message)
