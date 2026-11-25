"""Wiki page names for Data Dragon's champions, items, runes and summoner spells, and the way back for patch notes.

Data Dragon's names don't always match the wiki's pages: "Nunu & Willump" is a redirect to "Nunu", "Jack Of All Trades"
is "Jack of All Trades" (titles are case-sensitive after the first letter) and the item "Overgrowth" is "Crystalline
Overgrowth". Each name goes through: override from info.json ⇒ Module:ItemData by id (items) ⇒ the wiki's title or
redirect ⇒ a search hit that differs only in case ⇒ Data Dragon's name, with a warning."""
import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urlencode

from src.server.loader.champion_source import WIKI_API
from src.server.loader.helper import SafeSession
from src.server.loader.lua import parse_lua_table
from src.server.loader.patchexceptions import LoadError


patch_logger = logging.getLogger("liandrys.patch")

TITLES_PER_REQUEST = 50  # the API's limit for one query
WIKI_CONCURRENCY = 5  # the wiki API answers too many parallel requests with 429
LABELS = {"champions": "CHAMPION", "items": "ITEM", "runes": "RUNE", "summonerspells": "SUMMONERSPELL"}


@dataclass(frozen=True)
class DDragonName:
    id_: str
    name: str


class NameDictionary:
    """One type's names: Data Dragon id ⇒ wiki page, and any known name or id ⇒ Data Dragon name."""

    def __init__(self, wiki_names: dict[str, str] | None = None, entries: list[DDragonName] = ()) -> None:
        self._wiki_names = wiki_names or {}
        self._ddragon_names: dict[str, str] = {entry.name.casefold(): entry.name for entry in entries}
        # Data Dragon's own names come first, so an alias never hides another entry's real name.
        for entry in entries:
            for alias in (entry.id_, self._wiki_names.get(entry.id_, entry.name)):
                self._ddragon_names.setdefault(alias.casefold(), entry.name)

    def wiki_name(self, ddragon_id: str, fallback: str) -> str:
        return self._wiki_names.get(ddragon_id, fallback)

    def ddragon_name(self, name: str) -> str | None:
        return self._ddragon_names.get(name.casefold())


async def load_name_dictionaries(session: SafeSession, entries: dict[str, list[DDragonName]],
                                 overrides: dict[str, dict[str, str]]) -> dict[str, NameDictionary]:
    semaphore = asyncio.Semaphore(WIKI_CONCURRENCY)
    item_names = await _item_data_names(session) if "items" in entries else {}
    dictionaries = {}
    for type_, named in entries.items():
        known = (item_names if type_ == "items" else {}) | overrides.get(type_, {})
        wiki_names = await _wiki_names(session, semaphore, type_, named, known)
        dictionaries[type_] = NameDictionary(wiki_names, named)
    return dictionaries


async def _wiki_names(session: SafeSession, semaphore: asyncio.Semaphore, type_: str, named: list[DDragonName],
                      known: dict[str, str]) -> dict[str, str]:
    open_names = sorted({entry.name for entry in named if entry.id_ not in known})
    pages = await _page_titles(session, semaphore, open_names)
    missing = [name for name in open_names if pages[name] is None]
    found = await asyncio.gather(*(_search_title(session, semaphore, name) for name in missing))
    pages.update(zip(missing, found))
    wiki_names = {entry.id_: known.get(entry.id_) or pages[entry.name] or entry.name for entry in named}
    _log_names(type_, named, wiki_names, {name for name in missing if pages[name] is None})
    return wiki_names


def _log_names(type_: str, named: list[DDragonName], wiki_names: dict[str, str], unresolved: set[str]) -> None:
    label = LABELS.get(type_, type_.upper())
    for name in sorted(unresolved):
        patch_logger.warning(f"[{label}] [NAMES] [{name}] No wiki page found, Data Dragon's name is used")
    for name, wiki_name in sorted({(entry.name, wiki_names[entry.id_]) for entry in named}):
        if name != wiki_name:
            patch_logger.info(f"[{label}] [NAMES] [{name}] Wiki page: {wiki_name}")


async def _item_data_names(session: SafeSession) -> dict[str, str]:
    """Module:ItemData/data is keyed by the wiki's item name and lists Data Dragon's id."""
    query = urlencode({"action": "query", "titles": "Module:ItemData/data", "prop": "revisions",
                       "rvprop": "content", "rvslots": "main", "format": "json", "formatversion": 2})
    response = await session.get_json(f"{WIKI_API}?{query}")
    try:
        return parse_item_data(response["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"])
    except (TypeError, KeyError, IndexError, ValueError) as e:
        patch_logger.warning(f"[ITEM] [NAMES] Module:ItemData not loaded, item names only from titles: {e!r}")
        return {}


def parse_item_data(text: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for name, entry in parse_lua_table(text).items():
        if isinstance(entry, dict) and "id" in entry:
            names.setdefault(str(entry["id"]), name)
    return names


async def _page_titles(session: SafeSession, semaphore: asyncio.Semaphore, names: list[str]) -> dict[str, str | None]:
    batches = [names[i:i + TITLES_PER_REQUEST] for i in range(0, len(names), TITLES_PER_REQUEST)]
    titles: dict[str, str | None] = {}
    for batch, response in zip(batches, await asyncio.gather(*(_titles_query(session, semaphore, batch)
                                                              for batch in batches))):
        titles |= parse_page_titles(response, batch)
    return titles


async def _titles_query(session: SafeSession, semaphore: asyncio.Semaphore, names: list[str]) -> dict:
    query = urlencode({"action": "query", "titles": "|".join(names), "redirects": 1, "format": "json",
                       "formatversion": 2})
    url = f"{WIKI_API}?{query}"
    async with semaphore:
        response = await session.get_json(url)
    if not response:  # SafeSession answers a 404 with ""
        raise LoadError(404, "No answer to a title query", url, "wiki names", names[0])
    return response


def parse_page_titles(response: dict, names: list[str]) -> dict[str, str | None]:
    """name ⇒ the article it leads to (after the API's normalization and redirects), None if there is none."""
    query = response.get("query", {})
    normalized = {entry["from"]: entry["to"] for entry in query.get("normalized", [])}
    redirects = {entry["from"]: entry["to"] for entry in query.get("redirects", [])}
    # Only articles: Data Dragon's "Kalista's Black Spear" redirects to the Legends of Runeterra page "LoR:Kalista".
    articles = {page["title"] for page in query.get("pages", [])
                if page.get("ns") == 0 and not page.get("missing") and not page.get("invalid")}
    titles = {}
    for name in names:
        title = normalized.get(name, name)
        seen = set()
        while title in redirects and title not in seen:
            seen.add(title)
            title = redirects[title]
        titles[name] = title if title in articles else None
    return titles


async def _search_title(session: SafeSession, semaphore: asyncio.Semaphore, name: str) -> str | None:
    query = urlencode({"action": "opensearch", "search": name, "limit": 10, "namespace": 0,
                       "redirects": "resolve", "format": "json"})
    async with semaphore:
        response = await session.get_json(f"{WIKI_API}?{query}")
    return same_title_but_case(response, name)


def same_title_but_case(response: list | str, name: str) -> str | None:
    # The search is fuzzy ("Anti-tower Socks" finds "Siege minion"); only a title that differs in case is the same page.
    titles = response[1] if isinstance(response, list) and len(response) > 1 else []
    return next((title for title in titles if title.casefold() == name.casefold()), None)


def ddragon_notes(notes: dict[str, dict], names: dict[str, NameDictionary]) -> dict[str, dict]:
    """The patch notes with Data Dragon's names, so they match the documents ({{ci|Nunu}} ⇒ "Nunu & Willump")."""
    return {type_: _ddragon_type_notes(type_, type_notes, names.get(type_, NameDictionary()))
            for type_, type_notes in notes.items()}


def _ddragon_type_notes(type_: str, notes: dict, names: NameDictionary) -> dict:
    label = LABELS.get(type_, type_.upper())

    def renamed(name: str, warn: bool = True) -> str:
        ddragon_name = names.ddragon_name(name)
        if ddragon_name is None and warn:
            patch_logger.warning(f"[{label}] [NAMES] [{name}] Patch notes name not in Data Dragon")
        return ddragon_name or name

    # A removed object is no longer in Data Dragon's list, so not finding it is expected.
    return {"new": [renamed(name) for name in notes.get("new", [])],
            "changed": {renamed(name): changes for name, changes in notes.get("changed", {}).items()},
            "deleted": [renamed(name, warn=False) for name in notes.get("deleted", [])]}
