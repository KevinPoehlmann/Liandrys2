"""Builds the loader's part of a champion from its raw data: named values and tooltips per ability."""
import re
from dataclasses import dataclass

from src.server.loader.cdragon import SpellValues, spell_values
from src.server.loader.champion_source import loc_keys
from src.server.models.ability import Ability
from src.server.models.champion import NewChampion, RawChampion, WikiTemplate
from src.server.models.passive import Passive


SLOTS = ("q", "w", "e", "r")
WIKI_SLOTS = {"Q": "q", "W": "w", "E": "e", "R": "r", "I": "passive"}  # the wiki calls the passive "I" (innate)
REDIRECT = re.compile(r"#REDIRECT \[\[(.+?)\]\]")


@dataclass
class LoadedSpell:
    script_name: str
    name: str
    tooltip: str
    values: SpellValues
    wiki: WikiTemplate | None


def loaded_spells(raw: RawChampion, max_ranks: dict[str, int]) -> dict[str, LoadedSpell]:
    """Q, W, E, R and the passive, found through the champion's own record (the passive has no ranks)."""
    record = next(r for r in raw.cdragon.values() if isinstance(r, dict) and r.get("__type") == "CharacterRecord")
    paths = dict(zip(SLOTS, record["spells"])) | {"passive": record["mCharacterPassiveSpell"]}
    strings = {key.lower(): text for key, text in raw.strings.items()}
    templates = _wiki_by_slot(raw.wiki)
    return {slot: _loaded_spell(raw.cdragon[path], max_ranks.get(slot, 0), strings, templates.get(slot))
            for slot, path in paths.items()}


def _loaded_spell(record: dict, max_rank: int, strings: dict[str, str], wiki: WikiTemplate | None) -> LoadedSpell:
    keys = loc_keys(record)
    return LoadedSpell(
        script_name=record["mScriptName"],
        name=strings.get(keys.get("keyName", "").lower(), ""),
        tooltip=strings.get(keys.get("keyTooltip", "").lower(), ""),
        values=spell_values(record["mSpell"], max_rank),
        wiki=wiki,
    )


def _wiki_by_slot(templates: dict[str, WikiTemplate]) -> dict[str, WikiTemplate]:
    # "Template:Data Veigar/Q" redirects to "Template:Data Veigar/Baleful Strike".
    by_slot = {}
    for title, template in templates.items():
        slot = WIKI_SLOTS.get(title.rsplit("/", 1)[-1])
        target = REDIRECT.match(template.text)
        if slot and target and target.group(1) in templates:
            by_slot[slot] = templates[target.group(1)]
    return by_slot


def apply_loader_part(champion: NewChampion, spells: dict[str, LoadedSpell]) -> None:
    """Overwrites what the loader owns; rules, buffs, stages and formula fields stay as they are."""
    for slot, spell in spells.items():
        container: Ability | Passive = getattr(champion, slot)
        container.values = spell.values.values
        container.tooltip = spell.tooltip


def initial_structure(ability: Ability) -> None:
    """A newly loaded ability starts with the defaults that fit almost every ability; afterwards they are hand-owned."""
    ability.cost = "mana"
    ability.cooldown = "cooldownTime"
