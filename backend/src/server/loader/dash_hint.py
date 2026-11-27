"""Dash suggestions for the editor. The dash itself lives in Riot's scripts, which CDragon doesn't export, so the
loader only marks dashes (CDragon's spell tag) and translates the wiki's distance and speed where it has them."""
import re

from src.server.models.ability import DashHint
from src.server.models.champion import WikiTemplate


DASH_TAG = "Trait_PlayerSelectedDashDirection"
TOOLTIP = re.compile(r"^\{\{tt\|(.*)\|([^|{}]*)\}\}$")
MOVESPEED = re.compile(r"\{\{as\|([\d.]+)% (bonus )?movement speed\}\}")
FORMULA = re.compile(r"^[\d\s.+*()-]+$")  # no "/": "1000 / 1200" is a list per rank


def dash_hint(spell: dict, wiki: WikiTemplate | None) -> DashHint | None:
    tagged = DASH_TAG in spell.get("mSpellTags", [])
    text = wiki.text if wiki else ""
    distance = _dash_field(text, "range", "Dash distance", tagged)
    speed = _dash_field(text, "speed", "Dash speed", tagged)
    if not tagged and distance is None and speed is None:
        return None
    return DashHint(distance=distance, speed=speed)


def _dash_field(text: str, name: str, label: str, tagged: bool) -> str | None:
    """`{{tt|300|Dash distance}}` counts for any ability, a plain `250` only for a tagged dash (Riven E)."""
    match = re.search(rf"^\|\s*{name}\s*=(.*)$", text, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if tooltip := TOOLTIP.match(value):
        if tooltip.group(2) != label:
            return None
        value = tooltip.group(1)
    elif not tagged:
        return None
    return wiki_formula(value)


def wiki_formula(value: str) -> str | None:
    """`500 + {{as|100% movement speed}}` as `500 + movespeed`; None for anything else (lists, ranks, notes)."""
    variables = []

    def variable(match: re.Match) -> str:
        name = "bonus_movespeed" if match.group(2) else "movespeed"
        percent = float(match.group(1))
        variables.append(name if percent == 100 else f"{percent / 100:g} * {name}")
        return f"@{len(variables) - 1}"

    numbers = MOVESPEED.sub(variable, value)
    if not FORMULA.match(re.sub(r"@\d+", "0", numbers)):
        return None
    return re.sub(r"@(\d+)", lambda match: variables[int(match.group(1))], numbers)
