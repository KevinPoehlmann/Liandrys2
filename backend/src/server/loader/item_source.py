"""Downloads everything we keep about an item for one patch: its CommunityDragon record, the spell it names, its
tooltips and its entry in the wiki's Module:ItemData. No article: the module already has the effects' texts."""
from datetime import datetime

from src.server.loader.champion_source import CDRAGON, fetch_wiki_page
from src.server.loader.helper import SafeSession
from src.server.loader.lua import parse_lua_table
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.models.item import RawItem
from src.server.models.json_validation import ItemJson, ItemsJson


DDRAGON_ITEMS = "https://ddragon.leagueoflegends.com/cdn/{}/data/en_GB/item.json"
INHERITED = "=>"  # Module:ItemData's "take this field from that item" (Muramana's stats from Manamune)


async def fetch_item_list(session: SafeSession, patch: str) -> list[tuple[str, ItemJson]]:
    """Data Dragon's list of every mode's items, by id; rift_items keeps Summoner's Rift's."""
    data = await session.get_json(DDRAGON_ITEMS.format(patch))
    if not data:  # SafeSession answers a 404 with ""
        raise PatcherError(f"No item list for patch {patch}", "Data Dragon's item.json is missing")
    return [(item_id, ItemJson(**item)) for item_id, item in ItemsJson(**data).data.items()]


async def fetch_items_bin(session: SafeSession, version: str) -> dict:
    # 16 MB with every item of every mode; fetched once per load.
    url = f"{CDRAGON}{version}/game/items.cdtb.bin.json"
    data = await session.get_json(url)
    if not data:  # SafeSession answers a 404 with ""
        raise LoadError(404, "No items found", url, "items", version)
    return data


async def fetch_item_data(session: SafeSession) -> dict[str, dict]:
    """Module:ItemData/data by Data Dragon's id, with its references resolved."""
    entries = parse_lua_table((await fetch_wiki_page(session, "Module:ItemData/data", "wiki module")).text)
    return {str(entry["id"]): resolved(entry, entries) for entry in entries.values()
            if isinstance(entry, dict) and "id" in entry}


def resolved(entry: dict, entries: dict) -> dict:
    """Replaces every "=>Item" with that item's field at the same place, also inside tables (Muramana's
    `stats.ad = "=>Manamune"`)."""
    return _resolved(entry, entries, (), frozenset())


def _resolved(value, entries: dict, path: tuple[str, ...], seen: frozenset[str]):
    if isinstance(value, dict):
        return {key: _resolved(inner, entries, path + (key,), seen) for key, inner in value.items()}
    if not (isinstance(value, str) and value.startswith(INHERITED)):
        return value
    name = value[len(INHERITED):]
    if name in seen or not isinstance(source := entries.get(name), dict):
        return None
    for key in path:
        source = source.get(key) if isinstance(source, dict) else None
    return _resolved(source, entries, path, seen | {name})


def item_record(items_bin: dict, item_id: str) -> dict:
    record = items_bin.get(f"Items/{item_id}")
    if not isinstance(record, dict):
        raise KeyError(f"No item {item_id} in items.cdtb.bin.json")
    return record


def item_spell(record: dict, *bins: dict) -> dict | None:
    """The spell the item names: an active's cast time and range, but often a dummy (BloodthirsterDummySpell)."""
    if not (name := record.get("spellName")):
        return None
    for records in bins:
        spell = next((spell for spell in records.values()
                      if isinstance(spell, dict) and spell.get("mScriptName") == name and "mSpell" in spell), None)
        if spell is not None:
            return spell
    return None


def item_strings(strings: dict[str, str], item_id: str) -> dict[str, str]:
    # Item_3057_Tooltip and the client's GeneratedTip_Item_3057_Description (stats, active and passives in one).
    prefixes = (f"item_{item_id}_", f"generatedtip_item_{item_id}_")
    return {key: text for key, text in strings.items() if key.lower().startswith(prefixes)}


def load_raw_item(item_id: str, patch: str, build: str, items_bin: dict, shared: dict, strings: dict[str, str],
                  item_data: dict[str, dict]) -> RawItem:
    record = item_record(items_bin, item_id)
    return RawItem(item_id=item_id, patch=patch, build=build, fetched_at=datetime.now(), cdragon=record,
                   active=item_spell(record, items_bin, shared), strings=item_strings(strings, item_id),
                   item_data=item_data.get(item_id, {}))
