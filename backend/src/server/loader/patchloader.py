"""Loads new patches and hotfixes. Champions come from CommunityDragon, Data Dragon and the wiki API, on the first
load, when patching forward and in a hotfix; summoner spells, items and runes the same way from CommunityDragon's
shared spells, items and perks."""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable

import aiohttp

import src.server.database as db
from src.server.loader.champion_builder import (SLOTS, LoadedSpell, build_champion, loaded_spells, missing_cooldowns,
                                                wiki_mismatches)
from src.server.loader.champion_patcher import has_changes, keep_earlier_changes, patch_champion, spells_from_document
from src.server.loader.champion_source import (cdragon_version, fetch_build, fetch_champion_data, fetch_strings,
                                               load_raw_champion)
from src.server.loader.helper import SafeSession, info_loader, riot_to_wiki_patch
from src.server.loader.images import (load_champion_images, load_item_image, load_masterwork_border, load_rune_image,
                                     load_rune_tree_icons, load_summonerspell_image)
from src.server.loader.item_builder import (build_item, item_from_document, loaded_item, patch_item, rift_items,
                                            unknown_stat_fields)
from src.server.loader.item_builder import wiki_mismatches as item_wiki_mismatches
from src.server.loader.item_source import fetch_item_data, fetch_item_list, fetch_items_bin, load_raw_item
from src.server.loader.names import DDragonName, NameDictionary, ddragon_notes, load_name_dictionaries
from src.server.loader.patch_notes import fetch_hotfix_dates, fetch_patch_page, hotfix_notes, notes_with_hotfixes
from src.server.loader.patch_source import fetch_patch_list, is_complete, patches_to_load
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.loader.rune_builder import (SHARD_TREE_ID, RuneEntry, build_rune, loaded_rune, patch_rune,
                                            rune_from_document, shard_entries, tree_entries, unknown_shard)
from src.server.loader.rune_builder import wiki_mismatches as rune_wiki_mismatches
from src.server.loader.rune_source import (fetch_perks_bin, fetch_rune_trees, fetch_rune_wiki_pages, load_raw_rune,
                                           perk_records, tree_icons)
from src.server.loader.summonerspell_builder import (build_summonerspell, patch_summonerspell, rift_spells,
                                                     spell_from_document, summoner_spell)
from src.server.loader.summonerspell_builder import wiki_mismatches as spell_wiki_mismatches
from src.server.loader.summonerspell_source import (fetch_shared_bin, fetch_spell_data, fetch_summonerspell_list,
                                                    load_raw_summonerspell)
from src.server.models.change import Change, with_hotfix_lines
from src.server.models.champion import Champion, NewChampion, RawChampion, WikiTemplate
from src.server.models.item import Item, NewItem, RawItem
from src.server.models.json_validation import ChampionJson, ChampionsJson, ItemJson, SummonerspellJson
from src.server.models.patch import NewPatch, Patch
from src.server.models.rune import NewRune, RawRune, Rune
from src.server.models.summonerspell import NewSummonerspell, RawSummonerspell, Summonerspell
from src.server.utils.logger import attach_fallback_logfile, finalize_load_logfile


patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")

DDRAGON = "https://ddragon.leagueoflegends.com/cdn/"
CHAMPION_CONCURRENCY = 5  # the wiki API answers too many parallel requests with 429
ITEM_CONCURRENCY = 10
TIMEOUT = aiohttp.ClientTimeout(total=600)

patch_load_lock = asyncio.Lock()


@dataclass
class SpellSources:
    """What every summoner spell of a load reads, downloaded once."""
    build: str
    shared: dict
    strings: dict[str, str]
    spell_data: dict[str, dict]


@dataclass
class ItemSources:
    """What every item of a load reads, downloaded once."""
    build: str
    items: dict  # items.cdtb.bin.json
    shared: dict  # shared.cdtb.bin.json, for actives whose spell lives there (HextechGunbladeSpell)
    strings: dict[str, str]
    item_data: dict[str, dict]  # Module:ItemData by Data Dragon's id


ItemEntry = tuple[str, ItemJson]  # Data Dragon's id and list entry


@dataclass
class RuneSources:
    """What every rune of a load reads, downloaded once, and every rune with its place (trees and shard rows)."""
    build: str
    records: dict[int, dict]  # perks.cdtb.bin.json's perks by id
    strings: dict[str, str]
    wiki_pages: dict[str, WikiTemplate] | None  # data templates and articles by title; None: the wiki was down
    wiki_names: dict[int, str]  # the wiki page of each tree rune
    entries: list[RuneEntry]
    trees: dict[int, tuple[str, str]] = field(default_factory=dict)  # tree id -> name, icon asset


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
            patches, hotfix = await check_updates()
            latest = await db.fetch_patch_latest()
            if not is_complete(latest):
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
    latest = await db.fetch_patch_latest()
    async with aiohttp.ClientSession(timeout=TIMEOUT) as aio_session:
        session = SafeSession(aio_session)
        patches = patches_to_load(latest, await fetch_patch_list(session))
        return patches, await pending_hotfix(session, latest) if is_complete(latest) else None


async def pending_hotfix(session: SafeSession, patch: NewPatch) -> Hotfix | None:
    """A new CommunityDragon build, or a wiki hotfix from a later day than the last load or hotfix run."""
    build = await fetch_build(session, cdragon_version(patch.patch))
    # Wiki hotfixes only carry a day; one added later on the day of a run is missed (CDragon's build still catches it).
    last_run = (patch.updated_at or patch.timestamp).date()
    dates = [date for date in await fetch_hotfix_dates(session, patch.patch) if date.date() > last_run]
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
        items = await fetch_item_list(session, patch_name)
        summonerspells = await fetch_summonerspell_list(session, patch_name)
        runes = await fetch_rune_entries(session, patch_name)
        names = await name_dictionaries(session, champions, items, runes, summonerspells)
        summonerspells = rift_spells(summonerspells)
        sources = await item_sources(session, patch_name)
        items = rift_items(items, sources.item_data)
        rune_data = await rune_sources(session, patch_name, runes, names["runes"])
        patch = await _resumed_or_new_patch(patch_name, NewPatch(
            patch=patch_name, champion_count=len(champions), item_count=len(items),
            rune_count=len(rune_data.entries), summonerspell_count=len(summonerspells)))

        results = await asyncio.gather(
            load_all_champions(champions, session, patch, names["champions"]),
            load_all_items(items, session, patch, sources),
            load_all_runes(session, patch, rune_data),
            load_all_summonerspells(summonerspells, session, patch, names["summonerspells"]),
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
                            runes: list[RuneEntry], summonerspells: list[SummonerspellJson]) -> dict[str, NameDictionary]:
    """Only Summoner's Rift: other modes' objects (Arena vouchers, Poro Toss, ...) keep Data Dragon's name."""
    entries = {
        "champions": [DDragonName(champion.id_, champion.name) for champion in champions],
        "items": [DDragonName(item_id, item.name) for item_id, item in items if item.maps.get("11")],
        "runes": [DDragonName(str(rune.rune_id), rune.name) for rune in runes if not rune.is_shard],
        "summonerspells": [DDragonName(spell.id_, spell.name) for spell in summonerspells if "CLASSIC" in spell.modes],
    }
    try:
        names = await load_name_dictionaries(session, entries, info_loader().wikiNames)
    except (LoadError, RuntimeError) as e:
        # Without the wiki the old behavior stays: Data Dragon's names.
        patch_logger.warning(f"[PATCH] [NAMES] Wiki names not loaded, Data Dragon's names are used: {e}")
        names = {type_: NameDictionary() for type_ in entries}
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
            await _clean_up(patch_name)
            raise


async def _clean_up(patch_name: str) -> None:
    """Removes a failed patch's documents, so the next run starts it over."""
    result = await db.clear_patch(patch_name)
    if not result["cleanup_successful"]:
        patch_logger.error(f"[PATCH] [CLEANUP] [{patch_name}] ❌ Cleanup failed!")
        return
    patch_logger.warning(f"[PATCH] [CLEANUP] [{patch_name}] Cleaned up.")
    for key, count in result.items():
        if key != "cleanup_successful":
            patch_logger.info(f"[PATCH] [CLEANUP] [{patch_name}] - {key}: {count} document(s) removed")


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
        items = await fetch_item_list(session, patch_name)
        summonerspells = await fetch_summonerspell_list(session, patch_name)
        runes = await fetch_rune_entries(session, patch_name)
        names = await name_dictionaries(session, champions, items, runes, summonerspells)
        notes = ddragon_notes(notes, names)
        await patch_all_champions(champions, notes.get("champions", {}), session, patch, old_patch, names["champions"])
        sources = await item_sources(session, patch_name)
        await patch_all_items(rift_items(items, sources.item_data), notes.get("items", {}), session, patch, old_patch,
                              sources)
        await patch_all_runes(notes.get("runes", {}), session, patch, old_patch,
                              await rune_sources(session, patch_name, runes, names["runes"]))
        await patch_all_summonerspells(rift_spells(summonerspells), notes.get("summonerspells", {}), session, patch,
                                       old_patch, names["summonerspells"])
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
        items = await fetch_item_list(session, patch.patch)
        summonerspells = await fetch_summonerspell_list(session, patch.patch)
        runes = await fetch_rune_entries(session, patch.patch)
        names = await name_dictionaries(session, champions, items, runes, summonerspells)
        notes = ddragon_notes(hotfix_notes(wikitext, hotfix.wiki_dates), names)
        champion_notes = notes["champions"]["changed"]
        spell_notes = notes.get("summonerspells", {}).get("changed", {})
        item_notes = notes.get("items", {}).get("changed", {})
        summonerspells = rift_spells(summonerspells)
        sources = await item_sources(session, patch.patch)
        items = rift_items(items, sources.item_data)
        if not hotfix.build_changed:
            champions = [entry for entry in champions if entry.name in champion_notes]
            summonerspells = [entry for entry in summonerspells if entry.name in spell_notes]
            items = [entry for entry in items if entry[1].name in item_notes]
        await hotfix_all_champions(champions, champion_notes, session, patch, hotfixed_at, names["champions"])
        await hotfix_all_summonerspells(summonerspells, spell_notes, session, patch, hotfixed_at,
                                        names["summonerspells"])
        await hotfix_all_items(items, item_notes, session, patch, hotfixed_at, sources)
        rune_count = await hotfix_runes(runes, notes.get("runes", {}).get("changed", {}), session, patch, hotfix,
                                        hotfixed_at, names["runes"])
    patch.build, patch.updated_at = hotfix.build, hotfixed_at
    patch.update_totals()
    await db.upsert_patch(patch)
    load_logger.info(f"[LOAD] Hotfixed {len(champions)} champions, {len(summonerspells)} summoner spells, "
                     f"{len(items)} items and {rune_count} runes in {time.monotonic() - start:.2f} seconds")
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


async def load_all_summonerspells(spells: list[SummonerspellJson], session: SafeSession, patch: NewPatch,
                                  names: NameDictionary = NameDictionary()) -> None:
    sources = await _spell_sources(session, patch)
    await _each_summonerspell(spells, lambda entry: load_summonerspell(entry, session, patch, sources, names), "load")


async def _spell_sources(session: SafeSession, patch: NewPatch) -> SpellSources:
    version = cdragon_version(patch.patch)
    return SpellSources(build=await fetch_build(session, version), shared=await fetch_shared_bin(session, version),
                        strings=await fetch_strings(session, version), spell_data=await _spell_data_or_nothing(session))


async def _spell_data_or_nothing(session: SafeSession) -> dict[str, dict]:
    # Only a cross-check; summoner spells load without it.
    try:
        return await fetch_spell_data(session)
    except (LoadError, ValueError, KeyError) as e:
        patch_logger.warning(f"[SUMMONERSPELL] [WIKI] Module:SpellData not loaded, no cross-check: {e}")
        return {}


async def _each_summonerspell(spells: list[SummonerspellJson], load: Callable[[SummonerspellJson], Awaitable[None]],
                              action: str) -> None:
    # Nine spells, one after the other: their wiki requests run next to the champions' and must not add to the 429s.
    for entry in spells:
        try:
            await load(entry)
        except Exception as e:
            _log_error("SUMMONERSPELL", entry.name, e)
            load_logger.error(f"[SUMMONERSPELL] {entry.name} ❌ Failed to {action}")


async def load_summonerspell(entry: SummonerspellJson, session: SafeSession, patch: NewPatch, sources: SpellSources,
                             names: NameDictionary = NameDictionary()) -> None:
    if await db.exists_summonerspell_by_key(entry.id_, patch.patch):
        return
    raw = await _stored_raw_summonerspell(entry, session, patch, sources, names)
    await _store_summonerspell(build_summonerspell(raw, entry), raw, session, patch)
    load_logger.info(f"[SUMMONERSPELL] {entry.name} ✔ Loaded successfully")


async def _stored_raw_summonerspell(entry: SummonerspellJson, session: SafeSession, patch: NewPatch,
                                    sources: SpellSources, names: NameDictionary) -> RawSummonerspell:
    raw = await load_raw_summonerspell(session, entry.id_, names.wiki_name(entry.id_, entry.name), patch.patch,
                                       sources.build, sources.shared, sources.strings, sources.spell_data)
    if not raw.wiki:
        patch_logger.warning(f"[SUMMONERSPELL] [WIKI] [{entry.name}] No wiki article found")
    if not raw.spell_data:
        patch_logger.warning(f"[SUMMONERSPELL] [WIKI] [{entry.name}] Not in Module:SpellData")
    # Stored before building, so a spell the builder can't handle still has its raw data to look at.
    await db.upsert_raw_summonerspell(raw)
    return raw


async def _store_summonerspell(spell: NewSummonerspell, raw: RawSummonerspell, session: SafeSession,
                               patch: NewPatch) -> None:
    await _check_summonerspell(spell, raw, session, patch)
    await db.add_summonerspell(spell)
    patch.loaded_summonerspell_count += 1


async def _check_summonerspell(spell: NewSummonerspell, raw: RawSummonerspell, session: SafeSession,
                               patch: NewPatch) -> None:
    """The wiki cross-check and the image, on a first load, a patch and a hotfix."""
    for mismatch in spell_wiki_mismatches(spell, raw.spell_data):
        patch_logger.warning(f"[SUMMONERSPELL] [WIKI] [{spell.name}] {mismatch}")
    for failure in await load_summonerspell_image(session, spell, raw, cdragon_version(patch.patch)):
        patch_logger.warning(f"[SUMMONERSPELL] [IMAGE] [{spell.name}] {failure}")


async def patch_all_summonerspells(spells: list[SummonerspellJson], notes: dict, session: SafeSession,
                                   patch: NewPatch, old_patch: NewPatch, names: NameDictionary = NameDictionary()) -> None:
    """Spells of the old patch are patched forward, new ones get a first load, missing ones are left behind.
    `notes` are the patch notes' {"changed": {spell: [lines]}, ...}, with Data Dragon's names."""
    sources = await _spell_sources(session, patch)
    previous = {spell.key: spell for spell in await db.fetch_summonerspells_by_patch(old_patch.patch)}
    patch.summonerspell_count = len(spells)
    for key in previous.keys() - {entry.id_ for entry in spells}:
        load_logger.info(f"[SUMMONERSPELL] {previous[key].name} ✔ Not in patch {patch.patch} anymore, left behind")

    async def load(entry: SummonerspellJson) -> None:
        if entry.id_ not in previous:
            await load_summonerspell(entry, session, patch, sources, names)
            return
        spell_notes = notes.get("changed", {}).get(entry.name, [])
        await patch_one_summonerspell(entry, previous[entry.id_], spell_notes, session, patch, old_patch, sources, names)

    await _each_summonerspell(spells, load, "patch")


async def patch_one_summonerspell(entry: SummonerspellJson, old_spell: Summonerspell, notes: list[Change],
                                  session: SafeSession, patch: NewPatch, old_patch: NewPatch, sources: SpellSources,
                                  names: NameDictionary = NameDictionary()) -> None:
    if await db.exists_summonerspell_by_key(entry.id_, patch.patch):
        return
    raw = await _stored_raw_summonerspell(entry, session, patch, sources, names)
    result = patch_summonerspell(old_spell, await _old_summoner_spell(old_spell, old_patch), raw, entry, notes)
    if result.unvalidated:
        patch_logger.info(f"[SUMMONERSPELL] [PATCH] [{entry.name}] unvalidated: {'; '.join(result.unvalidated)}")
    await _store_summonerspell(result.summonerspell, raw, session, patch)
    if result.summonerspell.changes:
        patch.changed_summonerspell_count += 1
    load_logger.info(f"[SUMMONERSPELL] {entry.name} ✔ Patched successfully")


async def hotfix_all_summonerspells(spells: list[SummonerspellJson], notes: dict[str, list[Change]],
                                    session: SafeSession, patch: Patch, hotfixed_at: datetime,
                                    names: NameDictionary = NameDictionary()) -> None:
    """`notes` are the hotfixes' {spell: [lines]}, with Data Dragon's names."""
    if not spells:
        return
    sources = await _spell_sources(session, patch)
    current = {spell.key: spell for spell in await db.fetch_summonerspells_by_patch(patch.patch)}

    async def load(entry: SummonerspellJson) -> None:
        if entry.id_ not in current:
            patch_logger.warning(f"[SUMMONERSPELL] [HOTFIX] [{entry.name}] Not in patch {patch.patch}, skipped")
            return
        await hotfix_one_summonerspell(entry, current[entry.id_], notes.get(entry.name, []), session, patch,
                                       hotfixed_at, sources, names)

    await _each_summonerspell(spells, load, "hotfix")


async def hotfix_one_summonerspell(entry: SummonerspellJson, current: Summonerspell, notes: list[Change],
                                   session: SafeSession, patch: Patch, hotfixed_at: datetime, sources: SpellSources,
                                   names: NameDictionary = NameDictionary()) -> None:
    old_spell = await _old_summoner_spell(current, patch)  # read before the new download replaces the raw data
    raw = await _stored_raw_summonerspell(entry, session, patch, sources, names)
    result = patch_summonerspell(current, old_spell, raw, entry, notes)
    if result.unvalidated:
        patch_logger.info(f"[SUMMONERSPELL] [HOTFIX] [{entry.name}] unvalidated: {'; '.join(result.unvalidated)}")
    spell = result.summonerspell
    if spell.changes and not current.changes:
        patch.changed_summonerspell_count += 1
    spell.changes = with_hotfix_lines(current.changes, spell.changes, hotfixed_at)
    await _check_summonerspell(spell, raw, session, patch)
    await db.update_summonerspell(Summonerspell(id=current.id, **spell.dict()))
    load_logger.info(f"[SUMMONERSPELL] {entry.name} ✔ Hotfixed")


async def _old_summoner_spell(old_spell: NewSummonerspell, old_patch: NewPatch) -> LoadedSpell:
    # Rebuilt from the old raw data with today's translator, so a translator change doesn't look like a patch change.
    old_raw = await db.fetch_raw_summonerspell(old_spell.key, old_patch.patch)
    if old_raw is None:
        patch_logger.warning(f"[SUMMONERSPELL] [PATCH] [{old_spell.name}] No raw data of the old patch, comparing "
                             f"with the stored values (structure changes stay unseen)")
        return spell_from_document(old_spell)
    return summoner_spell(old_raw)


async def item_sources(session: SafeSession, patch_name: str) -> ItemSources:
    version = cdragon_version(patch_name)
    return ItemSources(build=await fetch_build(session, version), items=await fetch_items_bin(session, version),
                       shared=await fetch_shared_bin(session, version), strings=await fetch_strings(session, version),
                       item_data=await _item_data_or_nothing(session))


async def _item_data_or_nothing(session: SafeSession) -> dict[str, dict]:
    # Items load without it, but get no class, effects or limitations, and the Rift filter falls back to Data Dragon.
    try:
        return await fetch_item_data(session)
    except (LoadError, ValueError, KeyError) as e:
        patch_logger.warning(f"[ITEM] [WIKI] Module:ItemData not loaded, no classes, effects or cross-check: {e}")
        return {}


async def load_all_items(items: list[ItemEntry], session: SafeSession, patch: NewPatch, sources: ItemSources) -> None:
    await _load_masterwork_border(session, patch, sources)
    await _each_item(items, lambda entry: load_item(entry, session, patch, sources), "load")


async def _load_masterwork_border(session: SafeSession, patch: NewPatch, sources: ItemSources) -> None:
    for failure in await load_masterwork_border(session, patch, sources.items, cdragon_version(patch.patch)):
        patch_logger.warning(f"[ITEM] [IMAGE] [Masterwork border] {failure}")


async def _each_item(items: list[ItemEntry], load: Callable[[ItemEntry], Awaitable[None]], action: str) -> None:
    # No wiki request per item, only its image, so more run in parallel than champions.
    semaphore = asyncio.Semaphore(ITEM_CONCURRENCY)

    async def limited(entry: ItemEntry) -> None:
        async with semaphore:
            await load(entry)

    results = await asyncio.gather(*(limited(entry) for entry in items), return_exceptions=True)
    for (_, entry), result in zip(items, results):
        if isinstance(result, Exception):
            _log_error("ITEM", entry.name, result)
            load_logger.error(f"[ITEM] {entry.name} ❌ Failed to {action}")


async def load_item(entry: ItemEntry, session: SafeSession, patch: NewPatch, sources: ItemSources) -> None:
    item_id, item_json = entry
    if await db.exists_item_by_item_id(item_id, patch.patch):
        return
    raw = await _stored_raw_item(item_id, item_json, patch, sources)
    await _store_item(build_item(raw, item_json), raw, session, patch)
    load_logger.info(f"[ITEM] {item_json.name} ✔ Loaded successfully")


async def _stored_raw_item(item_id: str, item_json: ItemJson, patch: NewPatch, sources: ItemSources) -> RawItem:
    raw = load_raw_item(item_id, patch.patch, sources.build, sources.items, sources.shared, sources.strings,
                        sources.item_data)
    if sources.item_data and not raw.item_data:
        patch_logger.warning(f"[ITEM] [WIKI] [{item_json.name}] Not in Module:ItemData")
    # Stored before building, so an item the builder can't handle still has its raw data to look at.
    await db.upsert_raw_item(raw)
    return raw


async def _store_item(item: NewItem, raw: RawItem, session: SafeSession, patch: NewPatch) -> None:
    await _check_item(item, raw, session, patch)
    await db.add_item(item)
    patch.loaded_item_count += 1


async def _check_item(item: NewItem, raw: RawItem, session: SafeSession, patch: NewPatch) -> None:
    """The wiki cross-check, unknown stats and the image, on a first load, a patch and a hotfix."""
    for mismatch in item_wiki_mismatches(item, raw.item_data):
        patch_logger.warning(f"[ITEM] [WIKI] [{item.name}] {mismatch}")
    for name in unknown_stat_fields(raw.cdragon):
        patch_logger.warning(f"[ITEM] [STATS] [{item.name}] Unknown stat field {name}: {raw.cdragon[name]}")
    for failure in await load_item_image(session, item, raw, cdragon_version(patch.patch)):
        patch_logger.warning(f"[ITEM] [IMAGE] [{item.name}] {failure}")


async def patch_all_items(items: list[ItemEntry], notes: dict, session: SafeSession, patch: NewPatch,
                          old_patch: NewPatch, sources: ItemSources) -> None:
    """Items of the old patch are patched forward, new ones get a first load, missing ones are left behind.
    `notes` are the patch notes' {"changed": {item: [lines]}, ...}, with Data Dragon's names."""
    previous = {item.item_id: item for item in await db.fetch_items_by_patch(old_patch.patch)}
    patch.item_count = len(items)
    await _load_masterwork_border(session, patch, sources)
    for item_id in previous.keys() - {item_id for item_id, _ in items}:
        load_logger.info(f"[ITEM] {previous[item_id].name} ✔ Not in patch {patch.patch} anymore, left behind")

    async def load(entry: ItemEntry) -> None:
        item_id, item_json = entry
        if item_id not in previous:
            await load_item(entry, session, patch, sources)
            return
        item_notes = notes.get("changed", {}).get(item_json.name, [])
        await patch_one_item(entry, previous[item_id], item_notes, session, patch, old_patch, sources)

    await _each_item(items, load, "patch")


async def patch_one_item(entry: ItemEntry, old_item: Item, notes: list[Change], session: SafeSession,
                         patch: NewPatch, old_patch: NewPatch, sources: ItemSources) -> None:
    item_id, item_json = entry
    if await db.exists_item_by_item_id(item_id, patch.patch):
        return
    raw = await _stored_raw_item(item_id, item_json, patch, sources)
    result = patch_item(old_item, await _old_item(old_item, old_patch), raw, item_json, notes)
    if result.unvalidated:
        patch_logger.info(f"[ITEM] [PATCH] [{item_json.name}] unvalidated: {'; '.join(result.unvalidated)}")
    await _store_item(result.item, raw, session, patch)
    if result.item.changes:
        patch.changed_item_count += 1
    load_logger.info(f"[ITEM] {item_json.name} ✔ Patched successfully")


async def hotfix_all_items(items: list[ItemEntry], notes: dict[str, list[Change]], session: SafeSession,
                           patch: Patch, hotfixed_at: datetime, sources: ItemSources) -> None:
    """`notes` are the hotfixes' {item: [lines]}, with Data Dragon's names."""
    current = {item.item_id: item for item in await db.fetch_items_by_patch(patch.patch)}
    await _load_masterwork_border(session, patch, sources)

    async def load(entry: ItemEntry) -> None:
        item_id, item_json = entry
        if item_id not in current:
            patch_logger.warning(f"[ITEM] [HOTFIX] [{item_json.name}] Not in patch {patch.patch}, skipped")
            return
        await hotfix_one_item(entry, current[item_id], notes.get(item_json.name, []), session, patch, hotfixed_at,
                              sources)

    await _each_item(items, load, "hotfix")


async def hotfix_one_item(entry: ItemEntry, current: Item, notes: list[Change], session: SafeSession, patch: Patch,
                          hotfixed_at: datetime, sources: ItemSources) -> None:
    item_id, item_json = entry
    old_item = await _old_item(current, patch)  # read before the new download replaces the raw data
    raw = await _stored_raw_item(item_id, item_json, patch, sources)
    result = patch_item(current, old_item, raw, item_json, notes)
    if result.unvalidated:
        patch_logger.info(f"[ITEM] [HOTFIX] [{item_json.name}] unvalidated: {'; '.join(result.unvalidated)}")
    item = result.item
    if item.changes and not current.changes:
        patch.changed_item_count += 1
    item.changes = with_hotfix_lines(current.changes, item.changes, hotfixed_at)
    await _check_item(item, raw, session, patch)
    await db.update_item(Item(id=current.id, **item.dict()))
    load_logger.info(f"[ITEM] {item_json.name} ✔ Hotfixed")


async def _old_item(old_item: NewItem, old_patch: NewPatch) -> LoadedSpell:
    # Rebuilt from the old raw data with today's translator, so a translator change doesn't look like a patch change.
    old_raw = await db.fetch_raw_item(old_item.item_id, old_patch.patch)
    if old_raw is None:
        patch_logger.warning(f"[ITEM] [PATCH] [{old_item.name}] No raw data of the old patch, comparing with the "
                             f"stored values (structure changes stay unseen)")
        return item_from_document(old_item)
    return loaded_item(old_raw)


async def fetch_rune_entries(session: SafeSession, patch_name: str) -> list[RuneEntry]:
    """Data Dragon's five trees; the stat shards come with the sources (CommunityDragon)."""
    return tree_entries(await fetch_rune_trees(session, patch_name))


async def rune_sources(session: SafeSession, patch_name: str, entries: list[RuneEntry],
                       names: NameDictionary = NameDictionary()) -> RuneSources:
    version = cdragon_version(patch_name)
    perks, strings = await fetch_perks_bin(session, version), await fetch_strings(session, version)
    wiki_names = {entry.rune_id: names.wiki_name(str(entry.rune_id), entry.name) for entry in entries}
    return RuneSources(build=await fetch_build(session, version), records=perk_records(perks), strings=strings,
                       wiki_pages=await _rune_wiki_pages_or_nothing(session, list(wiki_names.values())),
                       wiki_names=wiki_names, entries=entries + shard_entries(perks, strings),
                       trees=tree_icons(perks, strings))


async def _rune_wiki_pages_or_nothing(session: SafeSession, wiki_names: list[str]) -> dict[str, WikiTemplate] | None:
    # Only the description, cooldown and notes for the editor; runes load without them.
    try:
        return await fetch_rune_wiki_pages(session, wiki_names)
    except (LoadError, RuntimeError, KeyError) as e:
        patch_logger.warning(f"[RUNE] [WIKI] Rune wiki pages not loaded: {e}")
        return None


async def load_all_runes(session: SafeSession, patch: NewPatch, sources: RuneSources) -> None:
    await _load_rune_tree_icons(session, patch, sources)
    await _each_rune(sources.entries, lambda entry: load_rune(entry, session, patch, sources), "load")


async def _load_rune_tree_icons(session: SafeSession, patch: NewPatch, sources: RuneSources) -> None:
    for failure in await load_rune_tree_icons(session, patch, sources.trees, cdragon_version(patch.patch)):
        patch_logger.warning(f"[RUNE] [IMAGE] [Tree] {failure}")


async def _each_rune(entries: list[RuneEntry], load: Callable[[RuneEntry], Awaitable[None]], action: str) -> None:
    # The wiki pages are already there, only images load per rune. A shard in two rows shares its raw document,
    # so its second row waits for the first instead of racing it on the same key.
    seen: set[int] = set()
    first, repeated = [], []
    for entry in entries:
        (repeated if entry.rune_id in seen else first).append(entry)
        seen.add(entry.rune_id)
    semaphore = asyncio.Semaphore(ITEM_CONCURRENCY)

    async def limited(entry: RuneEntry) -> None:
        async with semaphore:
            await load(entry)

    for group in (first, repeated):
        results = await asyncio.gather(*(limited(entry) for entry in group), return_exceptions=True)
        for entry, result in zip(group, results):
            if isinstance(result, Exception):
                _log_error("RUNE", entry.name, result)
                load_logger.error(f"[RUNE] {entry.name} ❌ Failed to {action}")


async def load_rune(entry: RuneEntry, session: SafeSession, patch: NewPatch, sources: RuneSources) -> None:
    if await db.exists_rune(entry.rune_id, patch.patch, entry.key[1]):
        return
    raw = await _stored_raw_rune(entry, patch, sources)
    await _store_rune(build_rune(raw, entry), raw, session, patch)
    load_logger.info(f"[RUNE] {entry.name} ✔ Loaded successfully")


async def _stored_raw_rune(entry: RuneEntry, patch: NewPatch, sources: RuneSources) -> RawRune:
    wiki_name = None if entry.is_shard else sources.wiki_names.get(entry.rune_id, entry.name)
    raw = load_raw_rune(entry.rune_id, wiki_name, patch.patch, sources.build, sources.records, sources.strings,
                        sources.wiki_pages or {})
    checked = sources.wiki_pages is not None and wiki_name  # without the wiki, one warning for all is enough
    if checked and not raw.wiki_data:
        patch_logger.warning(f"[RUNE] [WIKI] [{entry.name}] No Template:Rune data {wiki_name}")
    if checked and not raw.wiki:
        patch_logger.warning(f"[RUNE] [WIKI] [{entry.name}] No wiki article found")
    # Stored before building, so a rune the builder can't handle still has its raw data to look at.
    await db.upsert_raw_rune(raw)
    return raw


async def _store_rune(rune: NewRune, raw: RawRune, session: SafeSession, patch: NewPatch) -> None:
    await _check_rune(rune, raw, session, patch)
    await db.add_rune(rune)
    patch.loaded_rune_count += 1


async def _check_rune(rune: NewRune, raw: RawRune, session: SafeSession, patch: NewPatch) -> None:
    """The wiki cross-check, an unknown shard and the image, on a first load, a patch and a hotfix."""
    for mismatch in rune_wiki_mismatches(rune, raw):
        patch_logger.warning(f"[RUNE] [WIKI] [{rune.name}] {mismatch}")
    if rune.tree_id == SHARD_TREE_ID and unknown_shard(raw):
        patch_logger.warning(f"[RUNE] [STATS] [{rune.name}] Unknown stat shard {raw.cdragon.get('mPerkName')}, "
                             f"its stats need entering by hand: {rune.passive.values}")
    for failure in await load_rune_image(session, rune, raw, cdragon_version(patch.patch)):
        patch_logger.warning(f"[RUNE] [IMAGE] [{rune.name}] {failure}")


def _rune_key(rune: NewRune) -> tuple[int, int | None]:
    return rune.rune_id, rune.row if rune.tree_id == SHARD_TREE_ID else None


async def patch_all_runes(notes: dict, session: SafeSession, patch: NewPatch, old_patch: NewPatch,
                          sources: RuneSources) -> None:
    """Runes of the old patch are patched forward, new ones get a first load, missing ones are left behind.
    `notes` are the patch notes' {"changed": {rune: [lines]}, ...}, with Data Dragon's names."""
    previous = {_rune_key(rune): rune for rune in await db.fetch_runes_by_patch(old_patch.patch)}
    patch.rune_count = len(sources.entries)
    await _load_rune_tree_icons(session, patch, sources)
    for key in previous.keys() - {entry.key for entry in sources.entries}:
        load_logger.info(f"[RUNE] {previous[key].name} ✔ Not in patch {patch.patch} anymore, left behind")

    async def load(entry: RuneEntry) -> None:
        if entry.key not in previous:
            await load_rune(entry, session, patch, sources)
            return
        rune_notes = notes.get("changed", {}).get(entry.name, [])
        await patch_one_rune(entry, previous[entry.key], rune_notes, session, patch, old_patch, sources)

    await _each_rune(sources.entries, load, "patch")


async def patch_one_rune(entry: RuneEntry, old_rune: Rune, notes: list[Change], session: SafeSession,
                         patch: NewPatch, old_patch: NewPatch, sources: RuneSources) -> None:
    if await db.exists_rune(entry.rune_id, patch.patch, entry.key[1]):
        return
    raw = await _stored_raw_rune(entry, patch, sources)
    result = patch_rune(old_rune, await _old_rune(old_rune, old_patch), raw, entry, notes)
    if result.unvalidated:
        patch_logger.info(f"[RUNE] [PATCH] [{entry.name}] unvalidated: {'; '.join(result.unvalidated)}")
    await _store_rune(result.rune, raw, session, patch)
    if result.rune.changes:
        patch.changed_rune_count += 1
    load_logger.info(f"[RUNE] {entry.name} ✔ Patched successfully")


async def hotfix_all_runes(entries: list[RuneEntry], notes: dict[str, list[Change]], session: SafeSession,
                           patch: Patch, hotfixed_at: datetime, sources: RuneSources) -> None:
    """`notes` are the hotfixes' {rune: [lines]}, with Data Dragon's names."""
    current = {_rune_key(rune): rune for rune in await db.fetch_runes_by_patch(patch.patch)}
    await _load_rune_tree_icons(session, patch, sources)

    async def load(entry: RuneEntry) -> None:
        if entry.key not in current:
            patch_logger.warning(f"[RUNE] [HOTFIX] [{entry.name}] Not in patch {patch.patch}, skipped")
            return
        await hotfix_one_rune(entry, current[entry.key], notes.get(entry.name, []), session, patch, hotfixed_at,
                              sources)

    await _each_rune(entries, load, "hotfix")


async def hotfix_one_rune(entry: RuneEntry, current: Rune, notes: list[Change], session: SafeSession, patch: Patch,
                          hotfixed_at: datetime, sources: RuneSources) -> None:
    old_rune = await _old_rune(current, patch)  # read before the new download replaces the raw data
    raw = await _stored_raw_rune(entry, patch, sources)
    result = patch_rune(current, old_rune, raw, entry, notes)
    if result.unvalidated:
        patch_logger.info(f"[RUNE] [HOTFIX] [{entry.name}] unvalidated: {'; '.join(result.unvalidated)}")
    rune = result.rune
    if rune.changes and not current.changes:
        patch.changed_rune_count += 1
    rune.changes = with_hotfix_lines(current.changes, rune.changes, hotfixed_at)
    await _check_rune(rune, raw, session, patch)
    await db.update_rune(Rune(id=current.id, **rune.dict()))
    load_logger.info(f"[RUNE] {entry.name} ✔ Hotfixed")


async def _old_rune(old_rune: NewRune, old_patch: NewPatch) -> LoadedSpell:
    # Rebuilt from the old raw data with today's translator, so a translator change doesn't look like a patch change.
    old_raw = await db.fetch_raw_rune(old_rune.rune_id, old_patch.patch)
    if old_raw is None:
        patch_logger.warning(f"[RUNE] [PATCH] [{old_rune.name}] No raw data of the old patch, comparing with the "
                             f"stored values (structure changes stay unseen)")
        return rune_from_document(old_rune)
    return loaded_rune(old_raw)


async def hotfix_runes(runes: list[RuneEntry], notes: dict[str, list[Change]], session: SafeSession, patch: Patch,
                       hotfix: Hotfix, hotfixed_at: datetime, names: NameDictionary = NameDictionary()) -> int:
    """All runes on a new build, else only the named ones; their sources are only downloaded when needed."""
    if not hotfix.build_changed and not any(entry.name in notes for entry in runes):
        return 0
    sources = await rune_sources(session, patch.patch, runes, names)
    entries = [entry for entry in sources.entries if hotfix.build_changed or entry.name in notes]
    await hotfix_all_runes(entries, notes, session, patch, hotfixed_at, sources)
    return len(entries)


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
