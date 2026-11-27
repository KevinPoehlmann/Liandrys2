"""Downloads everything we keep about a summoner spell for one patch: its CommunityDragon record, tooltips, its entry
in the wiki's Module:SpellData and the wiki article (notes)."""
from datetime import datetime

from src.server.loader.champion_source import CDRAGON, fetch_wiki_page, loc_keys
from src.server.loader.helper import SafeSession
from src.server.loader.lua import parse_lua_table
from src.server.loader.patchexceptions import LoadError, PatcherError
from src.server.models.json_validation import SummonerspellJson, SummonerspellsJson
from src.server.models.summonerspell import RawSummonerspell


DDRAGON_SPELLS = "https://ddragon.leagueoflegends.com/cdn/{}/data/en_GB/summoner.json"


async def fetch_summonerspell_list(session: SafeSession, patch: str) -> list[SummonerspellJson]:
    """Data Dragon's list of every mode's summoner spells; rift_spells keeps Summoner's Rift's."""
    data = await session.get_json(DDRAGON_SPELLS.format(patch))
    if not data:  # SafeSession answers a 404 with ""
        raise PatcherError(f"No summoner spell list for patch {patch}", "Data Dragon's summoner.json is missing")
    return [SummonerspellJson(**spell) for spell in SummonerspellsJson(**data).data.values()]


async def fetch_shared_bin(session: SafeSession, version: str) -> dict:
    # 9 MB with every shared spell (summoner spells, item actives); fetched once per load.
    url = f"{CDRAGON}{version}/game/shared.cdtb.bin.json"
    data = await session.get_json(url)
    if not data:  # SafeSession answers a 404 with ""
        raise LoadError(404, "No shared spells found", url, "shared spells", version)
    return data


async def fetch_spell_data(session: SafeSession) -> dict[str, dict]:
    """Module:SpellData/data: every summoner spell's wiki cooldown, range and effect, keyed by its wiki name."""
    return parse_lua_table((await fetch_wiki_page(session, "Module:SpellData/data", "wiki module")).text)


def spell_record(shared: dict, key: str) -> dict:
    """Data Dragon's id (SummonerDot) is the record's script name; the path (Shared/Spells/SummonerDot) usually too."""
    record = next((record for record in shared.values()
                   if isinstance(record, dict) and record.get("mScriptName") == key and "mSpell" in record), None)
    if record is None:
        raise KeyError(f"No spell {key} in shared.cdtb.bin.json")
    return record


def spell_strings(strings: dict[str, str], record: dict) -> dict[str, str]:
    keys = {key.lower() for key in loc_keys(record).values()}
    return {key: text for key, text in strings.items() if key.lower() in keys}


async def load_raw_summonerspell(session: SafeSession, key: str, wiki_name: str, patch: str, build: str,
                                 shared: dict, strings: dict[str, str], spell_data: dict[str, dict]) -> RawSummonerspell:
    record = spell_record(shared, key)
    return RawSummonerspell(
        key=key, patch=patch, build=build, fetched_at=datetime.now(), cdragon=record,
        strings=spell_strings(strings, record), spell_data=spell_data.get(wiki_name, {}),
        wiki=await _article_or_nothing(session, wiki_name),
    )


async def _article_or_nothing(session: SafeSession, wiki_name: str):
    # Only notes for the editor; the spell loads without them.
    try:
        return await fetch_wiki_page(session, wiki_name, "wiki article")
    except LoadError:
        return None
