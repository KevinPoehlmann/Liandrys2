"""Patch notes from the wiki's patch page, read as wikitext through the wiki API.

The page is structured: `;{{ci|Darius}}` starts an entry, `* {{ai|Decimate|Darius}}` names an ability (or `* Stats`),
`** …` is a change line, `*** …` a detail of the line above. Templates become readable text; the per-rank numbers they compute are not needed, because
our numbers come from CommunityDragon."""
import html
import logging
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlencode

from src.server.loader.champion_source import WIKI_API
from src.server.loader.helper import (SafeSession, datetime_to_wiki, riot_to_wiki_patch, wiki_release_to_datetime,
                                      wiki_to_datetime)
from src.server.loader.patchexceptions import LoadError, ScrapeError
from src.server.models.change import Change, patch_note


patch_logger = logging.getLogger("liandrys.patch")

SECTIONS = {"champions": "Champions", "items": "Items", "runes": "Runes", "summonerspells": "Summoner Spells"}
TYPE_TEMPLATES = {"ci": "champions", "ii": "items", "ri": "runes", "si": "summonerspells"}
GENERAL = "General"

HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$", re.M)
REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S)
FILE_LINK = re.compile(r"\[\[File:[^\]]*\]\]")
LINK = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
RANK_COUNT = re.compile(r"^(\S+ to \S+) \d+$")  # {{ap|150 to 550 3}}: the 3 is the number of ranks


def patch_page_params(wiki_patch: str) -> dict:
    return {"action": "query", "titles": wiki_patch, "prop": "revisions", "rvprop": "ids|content", "rvslots": "main",
            "format": "json", "formatversion": 2}


def page_text(response: dict) -> str | None:
    page = response.get("query", {}).get("pages", [{}])[0]
    if "revisions" not in page:
        return None
    return page["revisions"][0]["slots"]["main"]["content"]


async def fetch_patch_page(session: SafeSession, wiki_patch: str) -> str:
    url = f"{WIKI_API}?{urlencode(patch_page_params(wiki_patch))}"
    text = page_text(await session.get_json(url) or {})
    if text is None:
        raise LoadError(404, "No patch page", url, "Patch", wiki_patch)
    return text


async def fetch_hotfix_dates(session: SafeSession, riot_patch: str) -> list[datetime]:
    return hotfix_dates(await fetch_patch_page(session, riot_to_wiki_patch(riot_patch)))


def parse_patch_notes(wikitext: str, hotfix: datetime | None = None) -> dict[str, dict]:
    """{"champions": {"new": [names], "changed": {name: {ability: [Change]}}, "deleted": [names]},
    "items": {… "changed": {name: [Change]} …}, …}"""
    if hotfix is not None:
        return _hotfix_notes(wikitext, hotfix)
    sections: dict[str, str] = {}
    for level, title, body in _sections(wikitext):
        if level == 3:
            sections.setdefault(title, body)  # the main part comes before the hotfixes
    notes = {}
    for type_, title in SECTIONS.items():
        notes[type_] = _empty_notes()
        for _, name, status, lines in _entries(sections.get(title, "")):
            _add_entry(notes[type_], type_, name, status, lines)
    return notes


def notes_with_hotfixes(wikitext: str) -> dict[str, dict]:
    """A patch loaded after its hotfixes already has their numbers, so their lines come with it."""
    notes = parse_patch_notes(wikitext)
    for hotfix in hotfix_dates(wikitext):
        _merge_changes(notes, parse_patch_notes(wikitext, hotfix))
    return notes


def hotfix_notes(wikitext: str, hotfixes: list[datetime]) -> dict[str, dict]:
    """Several hotfixes in one set of notes; an object named in two of them keeps the lines of both."""
    notes = {type_: _empty_notes() for type_ in SECTIONS}
    for hotfix in sorted(hotfixes):
        _merge_changes(notes, parse_patch_notes(wikitext, hotfix))
    return notes


def _merge_changes(notes: dict[str, dict], other: dict[str, dict]) -> None:
    for type_, type_notes in other.items():
        changed = notes[type_]["changed"]
        for name, changes in type_notes["changed"].items():
            if isinstance(changes, dict):  # champions: per ability
                for label, lines in changes.items():
                    changed.setdefault(name, {}).setdefault(label, []).extend(lines)
            else:
                changed.setdefault(name, []).extend(changes)


def hotfix_dates(wikitext: str) -> list[datetime]:
    titles = list(_hotfix_sections(wikitext))
    if not titles:
        return []
    release = release_date(wikitext)
    return [wiki_to_datetime(title, release) for title in titles]


def release_date(wikitext: str) -> datetime:
    match = re.search(r"^\|\s*Release\s*=(.*)$", wikitext, re.M)
    if not match:
        raise ScrapeError("Release date not found on patch page", "Patch", "Release")
    return wiki_release_to_datetime(wikitext_to_text(match.group(1)))


def _hotfix_notes(wikitext: str, hotfix: datetime) -> dict[str, dict]:
    notes = {type_: _empty_notes() for type_ in SECTIONS}
    title = datetime_to_wiki(hotfix)
    body = _hotfix_sections(wikitext).get(title)
    if body is None:
        patch_logger.error(f"[HOTFIX] [SCRAPE] [{hotfix}] Hotfix '{title}' not found on the patch page")
        return notes
    for type_, name, _, lines in _entries(body):
        # Hotfixes mix all types in one list, so the entry's template tells the type; lines like ";Client" are skipped.
        if type_:
            _add_entry(notes[type_], type_, name, "changed", lines)
    return notes


def _hotfix_sections(wikitext: str) -> dict[str, str]:
    # A hotfix's own subsections (==== Swiftplay ====) are mode changes and end its body.
    sections, inside = {}, False
    for level, title, body in _sections(wikitext):
        if level == 2:
            inside = title == "Hotfixes"
        elif inside and level == 3:
            sections[title] = body
    return sections


def _sections(wikitext: str) -> list[tuple[int, str, str]]:
    headings = list(HEADING.finditer(wikitext))
    ends = [heading.start() for heading in headings[1:]] + [len(wikitext)]
    return [(len(heading.group(1)), wikitext_to_text(heading.group(2)), wikitext[heading.end():end])
            for heading, end in zip(headings, ends)]


def _empty_notes() -> dict:
    return {"new": [], "changed": {}, "deleted": []}


def _entries(body: str) -> list[tuple[str | None, str, str, list[str]]]:
    """(type from the template, name, new/changed/deleted, list lines) per `;` entry."""
    entries = []
    for line in body.splitlines():
        if line.startswith(";"):
            entries.append((*_entry_header(line[1:]), []))
        elif line.startswith("*") and entries:
            entries[-1][3].append(line)
    return entries


def _entry_header(header: str) -> tuple[str | None, str, str]:
    name, _, suffix = REF.sub("", header).partition(" - ")
    template = re.match(r"\s*\{\{\s*(\w+)\s*\|", name)
    type_ = TYPE_TEMPLATES.get(template.group(1).lower()) if template else None
    if suffix.startswith(("New", "Re-added")):
        status = "new"
    elif suffix.startswith("Removed"):
        status = "deleted"
    else:
        status = "changed"
    return type_, wikitext_to_text(name), status


def _add_entry(notes: dict, type_: str, name: str, status: str, lines: list[str]) -> None:
    if status != "changed":
        notes[status].append(name)
    elif type_ == "champions":
        notes["changed"][name] = _ability_changes(lines)
    else:
        notes["changed"][name] = _changes(_list_items(lines), line_depth=1)


def _ability_changes(lines: list[str]) -> dict[str, list[Change]]:
    """`* label` groups the deeper lines; a `*` line without deeper lines is a change itself."""
    groups: dict[str, list[tuple[int, str]]] = {}
    label = GENERAL
    for depth, text in _list_items(lines):
        if depth == 1:
            label = text
            groups.setdefault(label, [])
        else:
            groups.setdefault(label, []).append((depth, text))
    changes: dict[str, list[Change]] = {}
    for label, items in groups.items():
        if items:
            changes.setdefault(label, []).extend(_changes(items, line_depth=2))
        else:
            changes.setdefault(GENERAL, []).append(patch_note(label))
    return changes


def _changes(items: list[tuple[int, str]], line_depth: int) -> list[Change]:
    # Lines deeper than a change line add details to the change above them.
    changes: list[Change] = []
    for depth, text in items:
        if depth > line_depth and changes:
            changes[-1].details.append(text)
        else:
            changes.append(patch_note(text))
    return changes


def _list_items(lines: list[str]) -> list[tuple[int, str]]:
    items = []
    for line in lines:
        stripped = line.lstrip("*")
        text = wikitext_to_text(stripped)
        if text:
            items.append((len(line) - len(stripped), text))
    return items


def wikitext_to_text(wikitext: str) -> str:
    text = FILE_LINK.sub("", REF.sub("", wikitext))
    text = LINK.sub(lambda link: link.group(2) or link.group(1), text)
    while True:  # innermost templates first, until none are left
        rendered = TEMPLATE.sub(lambda match: _render_template(match.group(1)), text)
        if rendered == text:
            break
        text = rendered
    text = html.unescape(text.replace("'''", "").replace("''", ""))
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _render_template(content: str) -> str:
    name, *params = [part.strip() for part in content.split("|")]
    positional = [param for param in params if "=" not in param]
    named = dict(param.split("=", 1) for param in params if "=" in param)
    renderer = TEMPLATE_RENDERERS.get(name.lower())
    if renderer:
        return renderer(positional, named)
    return positional[0] if positional else ""


def _per_rank(positional: list[str], named: dict) -> str:
    if len(positional) > 1:
        return " / ".join(positional)
    return RANK_COUNT.sub(r"\1", positional[0]) if positional else ""


def _per_level(positional: list[str], named: dict) -> str:
    # {{pp|key=%|60 to 80 for 3|1 to 13}} ⇒ "60% to 80% (based on level)"
    values = re.sub(r" for \d+$", "", positional[0]) if positional else ""
    key = named.get("key", "")
    values = " to ".join(part + key for part in values.split(" to "))
    return f"{values} (based on {named.get('type', 'level')})"


def _melee_ranged(positional: list[str], named: dict) -> str:
    melee, ranged = (positional + ["", ""])[:2]
    return f"{melee} (melee) / {ranged} (ranged)"


def _display_name(positional: list[str], named: dict) -> str:
    # {{ai|Captive Audience|Jhin|Lotus Trap}}: the third parameter is the shown text
    return positional[2] if len(positional) > 2 else (positional[0] if positional else "")


def _tip(positional: list[str], named: dict) -> str:
    return positional[-1] if positional else ""


def _possessive(positional: list[str], named: dict) -> str:
    name = positional[0] if positional else ""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _nothing(positional: list[str], named: dict) -> str:
    return ""


TEMPLATE_RENDERERS = {
    "ap": _per_rank, "pp": _per_level, "rd": _melee_ranged, "ai": _display_name, "tip": _tip,
    "iis": _possessive, "sis": _possessive, "ais": _possessive, "cais": _possessive, "uis": _possessive,
    "times": lambda positional, named: "×", "anchor": _nothing, "references": _nothing,
}
