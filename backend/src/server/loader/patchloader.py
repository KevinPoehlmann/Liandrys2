"""Loads new patches and hotfixes. Champions come from CommunityDragon, Data Dragon and the wiki API, on the first
load, when patching forward and in a hotfix. Items, runes, summoner spells and patch detection still go through
patchloader2 until they move here."""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable

import aiohttp

import src.server.database as db
import src.server.loader.patchloader2 as old
from src.server.loader.champion_builder import (SLOTS, LoadedSpell, build_champion, loaded_spells, missing_cooldowns,
                                                wiki_mismatches)
from src.server.loader.champion_patcher import has_changes, keep_earlier_changes, patch_champion, spells_from_document
from src.server.loader.champion_source import (cdragon_version, fetch_build, fetch_champion_data, fetch_strings,
                                               load_raw_champion)
from src.server.loader.helper import RuneClass, SafeSession, info_loader, riot_to_wiki_patch
from src.server.loader.images import load_champion_images
from src.server.loader.names import DDragonName, NameDictionary, ddragon_notes, load_name_dictionaries
from src.server.loader.patch_notes import fetch_patch_page, hotfix_notes, notes_with_hotfixes
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.models.change import Change
from src.server.models.champion import Champion, NewChampion, RawChampion
from src.server.models.json_validation import ChampionJson, ChampionsJson, ItemJson, SummonerspellJson
from src.server.models.patch import NewPatch, Patch
from src.server.utils.logger import attach_fallback_logfile, finalize_load_logfile


patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")

DDRAGON = "https://ddragon.leagueoflegends.com/cdn/"
CHAMPION_CONCURRENCY = 5  # the wiki API answers too many parallel requests with 429
TIMEOUT = aiohttp.ClientTimeout(total=600)

patch_load_lock = asyncio.Lock()


@dataclass
class Hotfix:
    build: str
    build_changed: bool
    wiki_dates: list[datetime] = field(default_factory=list)


async def load_data() -> None:
    """Entry point: completes an unfinished first load, or hotfixes the latest patch and loads every newer one."""
    if patch_load_lock.locked():
        load_logger.info("[LOAD] Patch data is already loading — skipping this call.")
        return
    async with patch_load_lock:
        try:
            old._reload_info_loader()
            patches, hotfix = await check_updates()
            latest = await db.fetch_patch_latest()
            if not _complete(latest):
                await load_fresh_database(patches)
                return
            if not patches and not hotfix:
                load_logger.info("[LOAD] Patch is up to date, no new data to load.")
                return
            # The hotfix comes first, so the next patch starts from the corrected data.
            if hotfix:
                latest = await load_hotfix(latest, hotfix)
            if patches:
                await load_patches(patches, latest)
        except Exception as e:
            patch_logger.exception(f"[PATCH] [UNEXPECTED] ❌ {type(e).__name__}: {e}")
            load_logger.error("[LOAD] Patch load failed!")


async def check_updates() -> tuple[list[str], Hotfix | None]:
    patches = await old.check_patch_available()
    latest = await db.fetch_patch_latest()
    return patches, await pending_hotfix(latest) if _complete(latest) else None


def _complete(patch: NewPatch | None) -> bool:
    return patch is not None and patch.loaded_total_count == patch.total_count


async def pending_hotfix(patch: NewPatch) -> Hotfix | None:
    """A new CommunityDragon build, or a wiki hotfix from a later day than the last load or hotfix run."""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as aio_session:
        build = await fetch_build(SafeSession(aio_session), cdragon_version(patch.patch))
    # Wiki hotfixes only carry a day; one added later on the day of a run is missed (CDragon's build still catches it).
    last_run = (patch.updated_at or patch.timestamp).date()
    dates = [date for date in old.wiki_hotfix_dates(patch.patch) if date.date() > last_run]
    if build == patch.build and not dates:
        return None
    return Hotfix(build, build != patch.build, dates)


async def load_fresh_database(patches: list[str]) -> None:
    patch_name = patches[-1]
    _log_section(f"Loading fresh database for patch {patch_name}")
    start = time.monotonic()

    async with aiohttp.ClientSession(timeout=TIMEOUT) as aio_session:
        session = SafeSession(aio_session)
        champions = await fetch_champion_list(session, patch_name)
        items, runes, summonerspells = await old._list_other_data(patch_name, session)
        names = await name_dictionaries(session, champions, items, runes, summonerspells)
        patch = await _resumed_or_new_patch(patch_name, NewPatch(
            patch=patch_name, champion_count=len(champions), item_count=len(items),
            rune_count=len(runes), summonerspell_count=len(summonerspells)))

        results = await asyncio.gather(
            load_all_champions(champions, session, patch, names["champions"]),
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


async def _resumed_or_new_patch(patch_name: str, new_patch: NewPatch) -> NewPatch:
    # An unfinished load of the same patch keeps its counters; existing objects are skipped.
    latest = await db.fetch_patch_latest()
    if latest and latest.patch == patch_name:
        return latest
    return new_patch


async def fetch_champion_list(session: SafeSession, patch: str) -> list[ChampionJson]:
    """Data Dragon's list: key, max ranks, resource type and images, which CommunityDragon's champion file lacks."""
    data = await session.get_json(f"{DDRAGON}{patch}/data/en_GB/championFull.json")
    if not data:
        raise PatcherError(f"No champion list for patch {patch}", "Data Dragon's championFull.json is missing")
    return [ChampionJson(**champion) for champion in ChampionsJson(**data).data.values()]


async def name_dictionaries(session: SafeSession, champions: list[ChampionJson], items: list[tuple[str, ItemJson]],
                            runes: list[RuneClass], summonerspells: list[SummonerspellJson]) -> dict[str, NameDictionary]:
    """Also handed to patchloader2, which loads items, runes and summoner spells for now.
    Only Summoner's Rift: other modes' objects (Arena vouchers, Poro Toss, ...) keep Data Dragon's name."""
    entries = {
        "champions": [DDragonName(champion.id_, champion.name) for champion in champions],
        "items": [DDragonName(item_id, item.name) for item_id, item in items if item.maps.get("11")],
        "runes": [DDragonName(str(rune.rune.id_), rune.rune.name) for rune in runes],
        "summonerspells": [DDragonName(spell.id_, spell.name) for spell in summonerspells if "CLASSIC" in spell.modes],
    }
    try:
        names = await load_name_dictionaries(session, entries, info_loader().wikiNames)
    except (LoadError, RuntimeError) as e:
        # Without the wiki the old behavior stays: Data Dragon's names.
        patch_logger.warning(f"[PATCH] [NAMES] Wiki names not loaded, Data Dragon's names are used: {e}")
        names = {type_: NameDictionary() for type_ in entries}
    old.WIKI_NAMES = names
    return names


async def load_all_champions(champions: list[ChampionJson], session: SafeSession, patch: NewPatch,
                             names: NameDictionary = NameDictionary()) -> None:
    version = cdragon_version(patch.patch)
    build = patch.build = await fetch_build(session, version)
    strings = await fetch_strings(session, version)
    champion_data = await _champion_data_or_nothing(session)

    async def load(entry: ChampionJson) -> None:
        await load_champion(entry, session, patch, build, strings, champion_data.get(entry.id_, {}),
                            names.wiki_name(entry.id_, entry.name))

    await _each_champion(champions, load, "load")


async def _each_champion(champions: list[ChampionJson], load: Callable[[ChampionJson], Awaitable[None]],
                         action: str) -> None:
    semaphore = asyncio.Semaphore(CHAMPION_CONCURRENCY)

    async def limited(entry: ChampionJson) -> None:
        async with semaphore:
            await load(entry)

    results = await asyncio.gather(*(limited(entry) for entry in champions), return_exceptions=True)
    for entry, result in zip(champions, results):
        if isinstance(result, Exception):
            _log_error("CHAMPION", entry.name, result)
            load_logger.error(f"[CHAMPION] {entry.name} ❌ Failed to {action}")


async def _champion_data_or_nothing(session: SafeSession) -> dict[str, dict]:
    # Only a cross-check and the last change; champions load without it.
    try:
        return await fetch_champion_data(session)
    except (LoadError, ValueError, KeyError) as e:
        patch_logger.warning(f"[CHAMPION] [WIKI] Module:ChampionData not loaded, no cross-check: {e}")
        return {}


async def load_champion(entry: ChampionJson, session: SafeSession, patch: NewPatch, build: str,
                        strings: dict[str, str], champion_data: dict | None = None, wiki_name: str | None = None) -> None:
    if await db.exists_champion_by_name(entry.name, patch.patch):
        return
    raw = await _stored_raw_champion(entry, session, patch, build, strings, champion_data, wiki_name)
    await _store_champion(build_champion(raw, entry), raw, session, patch)
    load_logger.info(f"[CHAMPION] {entry.name} ✔ Loaded successfully")


async def _stored_raw_champion(entry: ChampionJson, session: SafeSession, patch: NewPatch, build: str,
                               strings: dict[str, str], champion_data: dict | None, wiki_name: str | None) -> RawChampion:
    raw = await load_raw_champion(session, patch.patch, entry.id_, wiki_name or entry.name, build, strings,
                                  champion_data)
    if not raw.wiki:
        patch_logger.warning(f"[CHAMPION] [WIKI] [{entry.name}] No wiki data templates found")
    if not raw.champion_data:
        patch_logger.warning(f"[CHAMPION] [WIKI] [{entry.name}] Not in Module:ChampionData")
    # Stored before building, so a champion the builder can't handle still has its raw data to look at.
    await db.upsert_raw_champion(raw)
    return raw


async def _store_champion(champion: NewChampion, raw: RawChampion, session: SafeSession, patch: NewPatch) -> None:
    _warn_missing_cooldowns(champion)
    for mismatch in wiki_mismatches(champion, raw.champion_data):
        patch_logger.warning(f"[CHAMPION] [WIKI] [{champion.name}] {mismatch}")
    for failure in await load_champion_images(session, champion, raw, cdragon_version(patch.patch)):
        patch_logger.warning(f"[CHAMPION] [IMAGE] [{champion.name}] {failure}")
    await db.add_champion(champion)
    patch.loaded_champion_count += 1


def _warn_missing_cooldowns(champion: NewChampion) -> None:
    for slot in missing_cooldowns(champion):
        patch_logger.warning(f"[CHAMPION] [COOLDOWN] [{champion.name}] {slot.upper()} {getattr(champion, slot).name}: "
                             f"CDragon has no cooldown, enter it by hand (\"0\" if it has none)")


async def load_patches(patches: list[str], latest: NewPatch) -> None:
    """Patches forward one patch at a time, each from the one before."""
    for patch_name in patches:
        finalize_load_logfile(latest.patch)
        try:
            latest = await load_patch(patch_name, latest)
        except Exception as e:
            patch_logger.exception(f"[PATCH] [PATCH] [{patch_name}] ❌ Failed to load patch: {e}")
            await old._clean_up(NewPatch(patch=patch_name))
            raise


async def load_patch(patch_name: str, old_patch: NewPatch) -> NewPatch:
    _log_section(f"Loading patch {patch_name}")
    start = time.monotonic()
    async with aiohttp.ClientSession(timeout=TIMEOUT) as aio_session:
        session = SafeSession(aio_session)
        notes = notes_with_hotfixes(await fetch_patch_page(session, riot_to_wiki_patch(patch_name)))
        patch = NewPatch(patch=patch_name, champion_count=old_patch.champion_count,
                         item_count=old_patch.item_count, rune_count=old_patch.rune_count,
                         summonerspell_count=old_patch.summonerspell_count)
        champions = await fetch_champion_list(session, patch_name)
        names = await name_dictionaries(session, champions, *await old._list_other_data(patch_name, session))
        notes = ddragon_notes(notes, names)
        await patch_all_champions(champions, notes.get("champions", {}), session, patch, old_patch, names["champions"])
        await old._patch_items(notes.get("items", {}), patch, old_patch, session)
        await old._patch_runes(notes.get("runes", {}), patch, old_patch, session)
        await old._patch_summonerspells(notes.get("summonerspells", {}), patch, old_patch, session)
    patch.update_totals()
    await db.upsert_patch(patch)
    load_logger.info(f"[LOAD] Patched {patch.loaded_total_count} / {patch.total_count} objects "
                     f"in {time.monotonic() - start:.2f} seconds")
    return patch


async def patch_all_champions(champions: list[ChampionJson], notes: dict, session: SafeSession, patch: NewPatch,
                              old_patch: NewPatch, names: NameDictionary = NameDictionary()) -> None:
    """Champions of the old patch are patched forward, new ones get a first load.
    `notes` are the patch notes' {"changed": {champion: {ability: [lines]}}}, with Data Dragon's names."""
    version = cdragon_version(patch.patch)
    build = patch.build = await fetch_build(session, version)
    strings = await fetch_strings(session, version)
    champion_data = await _champion_data_or_nothing(session)
    previous = {champion.champion_id: champion
                for champion in await db.fetch_champions_by_patch(old_patch.patch)}
    patch.champion_count = len(champions)

    async def load(entry: ChampionJson) -> None:
        data = champion_data.get(entry.id_, {})
        wiki_name = names.wiki_name(entry.id_, entry.name)
        if entry.id_ not in previous:
            await load_champion(entry, session, patch, build, strings, data, wiki_name)
            return
        champion_notes = notes.get("changed", {}).get(entry.name, {})
        await patch_one_champion(entry, previous[entry.id_], champion_notes, session, patch, old_patch, build,
                                 strings, data, wiki_name)

    await _each_champion(champions, load, "patch")


async def patch_one_champion(entry: ChampionJson, old_champion: Champion, notes: dict[str, list[Change]],
                             session: SafeSession, patch: NewPatch, old_patch: NewPatch, build: str,
                             strings: dict[str, str], champion_data: dict, wiki_name: str | None = None) -> None:
    if await db.exists_champion_by_name(entry.name, patch.patch):
        return
    raw = await _stored_raw_champion(entry, session, patch, build, strings, champion_data, wiki_name)
    result = patch_champion(old_champion, await _old_spells(old_champion, old_patch), raw, entry, notes)
    for name, reasons in result.unvalidated.items():
        patch_logger.info(f"[CHAMPION] [PATCH] [{entry.name}] {name} unvalidated: {'; '.join(reasons)}")
    await _store_champion(result.champion, raw, session, patch)
    if result.changed:
        patch.changed_champion_count += 1
    load_logger.info(f"[CHAMPION] {entry.name} ✔ Patched successfully")


async def load_hotfix(patch: Patch, hotfix: Hotfix) -> Patch:
    """Overwrites the patch: champions are compared with their own raw data, the other types get the wiki's lines."""
    _log_section(f"Hotfix for patch {patch.patch}: build {hotfix.build}, wiki hotfixes {hotfix.wiki_dates}")
    start, hotfixed_at = time.monotonic(), datetime.now()
    async with aiohttp.ClientSession(timeout=TIMEOUT) as aio_session:
        session = SafeSession(aio_session)
        wikitext = await fetch_patch_page(session, riot_to_wiki_patch(patch.patch))
        champions = await fetch_champion_list(session, patch.patch)
        names = await name_dictionaries(session, champions, *await old._list_other_data(patch.patch, session))
        notes = ddragon_notes(hotfix_notes(wikitext, hotfix.wiki_dates), names)
        champion_notes = notes["champions"]["changed"]
        if not hotfix.build_changed:
            champions = [entry for entry in champions if entry.name in champion_notes]
        await hotfix_all_champions(champions, champion_notes, session, patch, hotfixed_at, names["champions"])
        await old.hotfix_others(notes, patch, hotfixed_at)
    patch.build, patch.updated_at = hotfix.build, hotfixed_at
    patch.update_totals()
    await db.upsert_patch(patch)
    load_logger.info(f"[LOAD] Hotfixed {len(champions)} champions in {time.monotonic() - start:.2f} seconds")
    return patch


async def hotfix_all_champions(champions: list[ChampionJson], notes: dict, session: SafeSession, patch: Patch,
                               hotfixed_at: datetime, names: NameDictionary = NameDictionary()) -> None:
    """`notes` are the hotfixes' {champion: {ability: [lines]}}, with Data Dragon's names."""
    version = cdragon_version(patch.patch)
    build = await fetch_build(session, version)
    strings = await fetch_strings(session, version)
    champion_data = await _champion_data_or_nothing(session)
    current = {champion.champion_id: champion for champion in await db.fetch_champions_by_patch(patch.patch)}

    async def load(entry: ChampionJson) -> None:
        if entry.id_ not in current:
            patch_logger.warning(f"[CHAMPION] [HOTFIX] [{entry.name}] Not in patch {patch.patch}, skipped")
            return
        await hotfix_one_champion(entry, current[entry.id_], notes.get(entry.name, {}), session, patch, hotfixed_at,
                                  build, strings, champion_data.get(entry.id_, {}),
                                  names.wiki_name(entry.id_, entry.name))

    await _each_champion(champions, load, "hotfix")


async def hotfix_one_champion(entry: ChampionJson, current: Champion, notes: dict[str, list[Change]],
                              session: SafeSession, patch: Patch, hotfixed_at: datetime, build: str,
                              strings: dict[str, str], champion_data: dict, wiki_name: str | None = None) -> None:
    old_spells = await _old_spells(current, patch)  # read before the new download replaces the raw data
    raw = await _stored_raw_champion(entry, session, patch, build, strings, champion_data, wiki_name)
    result = patch_champion(current, old_spells, raw, entry, notes)
    for name, reasons in result.unvalidated.items():
        patch_logger.info(f"[CHAMPION] [HOTFIX] [{entry.name}] {name} unvalidated: {'; '.join(reasons)}")
    if result.changed and not has_changes(current):
        patch.changed_champion_count += 1
    _warn_missing_cooldowns(result.champion)
    keep_earlier_changes(result.champion, current, hotfixed_at)
    await db.update_champion(Champion(id=current.id, **result.champion.dict()))
    load_logger.info(f"[CHAMPION] {entry.name} ✔ Hotfixed")


async def _old_spells(old_champion: Champion, old_patch: NewPatch) -> dict[str, LoadedSpell]:
    # Rebuilt from the old raw data with today's translator, so a translator change doesn't look like a patch change.
    old_raw = await db.fetch_raw_champion(old_champion.champion_id, old_patch.patch)
    if old_raw is None:
        patch_logger.warning(f"[CHAMPION] [PATCH] [{old_champion.name}] No raw data of the old patch, comparing with "
                             f"the stored values (structure changes stay unseen)")
        return spells_from_document(old_champion)
    return loaded_spells(old_raw, {slot: getattr(old_champion, slot).maxrank for slot in SLOTS})


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
