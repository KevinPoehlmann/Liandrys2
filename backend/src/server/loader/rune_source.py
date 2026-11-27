"""Downloads everything we keep about a rune for one patch: its CommunityDragon perk record, its texts, the wiki's
Template:Rune data <name> (description, cooldown) and the wiki article (notes). Stat shards have no wiki pages."""
import re
from datetime import datetime
from typing import Iterator

from src.server.loader.champion_source import CDRAGON, fetch_wiki_pages
from src.server.loader.helper import SafeSession
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.models.champion import WikiTemplate
from src.server.models.json_validation import RuneTreeJson
from src.server.models.rune import RawRune


DDRAGON_RUNES = "https://ddragon.leagueoflegends.com/cdn/{}/data/en_GB/runesReforged.json"
WIKI_DATA = "Template:Rune data {}"
# A text that includes another one: {{perk_displayname_DarkHarvest}}, or with a placeholder the client fills in,
# {{perk_substring_DarkHarvestadaptive_@f2@}} => perk_substring_darkharvestadaptive_0 and _1.
INCLUDED_TEXT = re.compile(r"\{\{\s*(\w+)")


async def fetch_rune_trees(session: SafeSession, patch: str) -> list[RuneTreeJson]:
    """Data Dragon's list: the five trees with their rows, the runes' names and icons. Without the stat shards."""
    data = await session.get_json(DDRAGON_RUNES.format(patch))
    if not data:  # SafeSession answers a 404 with ""
        raise PatcherError(f"No rune list for patch {patch}", "Data Dragon's runesReforged.json is missing")
    return [RuneTreeJson(**tree) for tree in data]


async def fetch_perks_bin(session: SafeSession, version: str) -> dict:
    # 2 MB with every rune, stat shard and their visual effects; fetched once per load.
    url = f"{CDRAGON}{version}/game/perks.cdtb.bin.json"
    data = await session.get_json(url)
    if not data:
        raise LoadError(404, "No runes found", url, "runes", version)
    return data


def perk_records(perks_bin: dict) -> dict[int, dict]:
    return {record["mPerkId"]: record for record in perks_bin.values()
            if isinstance(record, dict) and record.get("__type") == "Perk" and "mPerkId" in record}


def tree_icons(perks_bin: dict, strings: dict[str, str]) -> dict[int, tuple[str, str]]:
    """Each tree's name and icon asset from its PerkStyle record."""
    return {record["mPerkStyleId"]: (strings.get(record.get("mDisplayNameLocalizationKey", "").lower(),
                                                 record.get("mPerkStyleName", "")),
                                     record.get("mIconTextureName", ""))
            for record in perks_bin.values()
            if isinstance(record, dict) and record.get("__type") == "PerkStyle" and "mPerkStyleId" in record}


async def fetch_rune_wiki_pages(session: SafeSession, wiki_names: list[str]) -> dict[str, WikiTemplate]:
    """Every rune's data template and article in a few requests, next to the champions' wiki requests."""
    titles = [title for name in wiki_names for title in (WIKI_DATA.format(name), name)]
    return await fetch_wiki_pages(session, titles, "rune wiki pages")


def rune_strings(strings: dict[str, str], record: dict) -> dict[str, str]:
    """The texts the record names (tooltip, descriptions, buff texts) and the ones those texts include.
    The string table's keys are lowercase."""
    keys = {text.lower() for text in _texts(record) if text.lower() in strings}
    for key in list(keys):
        for name in INCLUDED_TEXT.findall(strings[key]):
            prefix = name.lower()
            keys |= {prefix} if prefix in strings else {other for other in strings if other.startswith(prefix)}
    return {key: strings[key] for key in sorted(keys)}


def _texts(value) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            yield from _texts(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _texts(inner)


def load_raw_rune(rune_id: int, wiki_name: str | None, patch: str, build: str, records: dict[int, dict],
                  strings: dict[str, str], wiki_pages: dict[str, WikiTemplate]) -> RawRune:
    """`wiki_name` is None for a stat shard."""
    record = records.get(rune_id)
    if record is None:
        raise KeyError(f"No rune {rune_id} in perks.cdtb.bin.json")
    return RawRune(rune_id=rune_id, patch=patch, build=build, fetched_at=datetime.now(), cdragon=record,
                   strings=rune_strings(strings, record),
                   wiki_data=wiki_pages.get(WIKI_DATA.format(wiki_name)) if wiki_name else None,
                   wiki=wiki_pages.get(wiki_name) if wiki_name else None)
