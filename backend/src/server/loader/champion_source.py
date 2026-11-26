"""Downloads everything we keep about a champion for one patch: CommunityDragon's data, tooltips and wiki templates."""
from datetime import datetime
from urllib.parse import urlencode

from src.server.loader.helper import SafeSession
from src.server.loader.lua import parse_lua_table
from src.server.loader.patchexceptions import LoadError
from src.server.models.champion import RawChampion, WikiTemplate


CDRAGON = "https://raw.communitydragon.org/"
WIKI_API = "https://wiki.leagueoflegends.com/en-us/api.php"


def cdragon_version(patch: str) -> str:
    """Data Dragon's "16.23.1" is CommunityDragon's folder "16.23"."""
    major, minor, *_ = patch.split(".")
    return f"{major}.{minor}"


async def fetch_build(session: SafeSession, version: str) -> str:
    metadata = await _get_json(session, f"{CDRAGON}{version}/content-metadata.json", "build", version)
    return metadata["version"]


async def fetch_strings(session: SafeSession, version: str) -> dict[str, str]:
    # 32 MB with every text of the game; fetched once per load and filtered per champion.
    table = await _get_json(session, f"{CDRAGON}{version}/game/en_us/data/menu/en_us/lol.stringtable.json", "strings", version)
    return table["entries"]


async def fetch_champion_bin(session: SafeSession, version: str, champion_id: str) -> dict:
    name = champion_id.lower()
    return await _get_json(session, f"{CDRAGON}{version}/game/data/characters/{name}/{name}.bin.json", "champion", champion_id)


def champion_strings(strings: dict[str, str], cdragon: dict) -> dict[str, str]:
    """The entries that belong to one of the champion's spells: named after a spell (spell_veigarbalefulstrike_tooltip)
    or listed in a spell's tooltip keys (Darius' DariusCleave uses Spell_DariusQ_Tooltip)."""
    spells = [record for record in cdragon.values() if isinstance(record, dict) and record.get("mScriptName")]
    scripts = {record["mScriptName"].lower() for record in spells}
    keys = {key.lower() for record in spells for key in loc_keys(record).values()}
    return {key: text for key, text in strings.items() if key.lower() in keys or _belongs_to(key.lower(), scripts)}


def loc_keys(record: dict) -> dict[str, str]:
    """A spell's text keys: keyName, keyTooltip, keySummary, ..."""
    return record.get("mSpell", {}).get("mClientData", {}).get("mTooltipData", {}).get("mLocKeys", {})


def _belongs_to(key: str, scripts: set[str]) -> bool:
    return any(part in scripts for part in key.split("_"))


async def fetch_wiki_templates(session: SafeSession, champion_name: str) -> dict[str, WikiTemplate]:
    # One request lists every "Template:Data <Champion>/..." page with its text and revision.
    query = urlencode({
        "action": "query", "generator": "allpages", "gapnamespace": 10, "gapprefix": f"Data {champion_name}/",
        "gaplimit": 50, "prop": "revisions", "rvprop": "ids|content", "rvslots": "main",
        "format": "json", "formatversion": 2,
    })
    response = await _get_json(session, f"{WIKI_API}?{query}", "wiki templates", champion_name)
    return parse_wiki_templates(response)


def parse_wiki_templates(response: dict) -> dict[str, WikiTemplate]:
    templates = {}
    for page in response.get("query", {}).get("pages", []):
        revision = page["revisions"][0]
        templates[page["title"]] = WikiTemplate(title=page["title"], revision_id=revision["revid"],
                                                text=revision["slots"]["main"]["content"])
    return templates


async def fetch_champion_data(session: SafeSession) -> dict[str, dict]:
    """Module:ChampionData/data: every champion's wiki stats and last change, keyed by Data Dragon id (`apiname`)."""
    query = urlencode({"action": "query", "titles": "Module:ChampionData/data", "prop": "revisions",
                       "rvprop": "content", "rvslots": "main", "format": "json", "formatversion": 2})
    response = await _get_json(session, f"{WIKI_API}?{query}", "wiki module", "ChampionData")
    page = response["query"]["pages"][0]
    if "revisions" not in page:
        raise LoadError(404, "No module text", WIKI_API, "wiki module", "ChampionData")
    return parse_champion_data(page["revisions"][0]["slots"]["main"]["content"])


def parse_champion_data(text: str) -> dict[str, dict]:
    # The module is keyed by display name ("Wukong"), we by Data Dragon id ("MonkeyKing").
    return {entry["apiname"]: entry for entry in parse_lua_table(text).values() if "apiname" in entry}


async def load_raw_champion(session: SafeSession, patch: str, champion_id: str, champion_name: str,
                            build: str, strings: dict[str, str], champion_data: dict | None = None) -> RawChampion:
    cdragon = await fetch_champion_bin(session, cdragon_version(patch), champion_id)
    return RawChampion(
        champion_id=champion_id, patch=patch, build=build, fetched_at=datetime.now(),
        cdragon=cdragon, strings=champion_strings(strings, cdragon),
        wiki=await fetch_wiki_templates(session, champion_name), champion_data=champion_data or {},
    )


async def _get_json(session: SafeSession, url: str, what: str, name: str) -> dict:
    data = await session.get_json(url)
    if not data:  # SafeSession answers a 404 with ""
        raise LoadError(404, f"No {what} found", url, what, name)
    return data
