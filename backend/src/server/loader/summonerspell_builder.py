"""Builds a summoner spell from its raw data and carries it into a new patch. A summoner spell is one spell, so the
champion patcher's diff and validation table apply as they are, with a single slot."""
import math
from dataclasses import dataclass, field

from src.server.loader.cdragon import SpellValues
from src.server.loader.champion_builder import LoadedSpell, initial_structure, loaded_spell
from src.server.loader.champion_patcher import (buff_renames, data_changes, rename_hand_made, spell_diff,
                                                unvalidating_reasons, used_names)
from src.server.models.ability import Ability
from src.server.models.change import Change
from src.server.models.enums import Map
from src.server.models.json_validation import SummonerspellJson
from src.server.models.summonerspell import NewSummonerspell, RawSummonerspell


SLOT = "spell"  # bare names in a summoner spell's formulas belong to its one spell
RIFT_MODE = "CLASSIC"
# Data Dragon names maps by id (items) and by game mode (summoner spells).
GAME_MAPS = {
    "11": Map.SR, "CLASSIC": Map.SR, "12": Map.HA, "ARAM": Map.HA, "21": Map.NB, "22": Map.TFT,
    "30": Map.AR, "CHERRY": Map.AR, "33": Map.SW, "35": Map.BR, "BRAWL": Map.BR, "SWIFTPLAY": Map.SP,
}
# Module:SpellData's fields and the value they should match.
WIKI_FIELDS = {"cooldown": "cooldownTime", "charges": "maxAmmo", "recharge": "ammoRechargeTime"}


@dataclass
class PatchedSummonerspell:
    summonerspell: NewSummonerspell
    unvalidated: list[str] = field(default_factory=list)  # why it lost its validation


def rift_spells(spells: list[SummonerspellJson]) -> list[SummonerspellJson]:
    """V1 covers Summoner's Rift; other modes' spells (Clarity, Mark, Swiftplay's _Jade copies) are left out."""
    return [spell for spell in spells if RIFT_MODE in spell.modes]


def build_summonerspell(raw: RawSummonerspell, entry: SummonerspellJson) -> NewSummonerspell:
    spell = summoner_spell(raw)
    ability = Ability(name=spell.name or entry.name)
    initial_structure(ability, spell.values.values)
    ability.cost = "0"  # summoner spells cost nothing
    summonerspell = NewSummonerspell(key=raw.key, name=entry.name, patch=raw.patch, ability=ability,
                                     maps=maps(entry.modes), image=entry.image)
    apply_loader_part(summonerspell, spell)
    return summonerspell


def summoner_spell(raw: RawSummonerspell) -> LoadedSpell:
    strings = {key.lower(): text for key, text in raw.strings.items()}
    return loaded_spell(raw.cdragon, 0, strings, raw.wiki)


def maps(modes: list[str]) -> list[Map]:
    # Most modes are events we don't model (URF, ULTBOOK, ...).
    return list(dict.fromkeys(GAME_MAPS[mode.upper()] for mode in modes if mode.upper() in GAME_MAPS))


def apply_loader_part(summonerspell: NewSummonerspell, spell: LoadedSpell) -> None:
    summonerspell.ability.values = spell.values.values
    summonerspell.ability.tooltip = spell.tooltip


def wiki_mismatches(summonerspell: NewSummonerspell, spell_data: dict) -> list[str]:
    """Where our CDragon numbers differ from the wiki. Only logged, like the champions' cross-check."""
    mismatches = []
    for wiki_field, name in WIKI_FIELDS.items():
        wiki, ours = _number(spell_data.get(wiki_field)), _number(summonerspell.ability.values.get(name))
        if wiki is not None and ours is not None and not math.isclose(wiki, ours, abs_tol=1e-3):
            mismatches.append(f"{name}: wiki {wiki:g}, CDragon {ours:g}")
    return mismatches


def _number(value) -> float | None:
    # Wiki fields are often text ("15 ({{sti|cd|reduced}} ...)"), values formulas; only plain numbers compare.
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def patch_summonerspell(old: NewSummonerspell, old_spell: LoadedSpell, raw: RawSummonerspell,
                        entry: SummonerspellJson, notes: list[Change]) -> PatchedSummonerspell:
    """The hand-made part stays, the loader part is replaced, and the diff decides the validation (ROADMAP table)."""
    summonerspell = NewSummonerspell.parse_obj(old.dict(exclude={"id"}))
    summonerspell.patch, summonerspell.name, summonerspell.maps = raw.patch, entry.name, maps(entry.modes)
    new_spell = summoner_spell(raw)
    diff = spell_diff(old_spell, new_spell)
    ability = summonerspell.ability
    ability.name = new_spell.name or ability.name
    if diff.renamed or diff.renamed_buffs:
        rename_hand_made(ability, SLOT, {SLOT: diff.renamed}, buff_renames(diff.renamed_buffs))

    reasons = unvalidating_reasons(SLOT, used_names(ability, SLOT), {SLOT: diff})
    if notes and not diff.lines:
        reasons.append("named in the patch notes only")
    summonerspell.changes = data_changes(diff.lines) + notes
    apply_loader_part(summonerspell, new_spell)
    if not (summonerspell.validated and reasons):
        return PatchedSummonerspell(summonerspell)
    summonerspell.validated = False
    return PatchedSummonerspell(summonerspell, reasons)


def spell_from_document(summonerspell: NewSummonerspell) -> LoadedSpell:
    """The fallback when the old patch has no raw data: only the stored values, so structure changes stay unseen."""
    ability = summonerspell.ability
    return LoadedSpell(script_name="", name=ability.name, tooltip=ability.tooltip,
                       values=SpellValues(values=dict(ability.values)), wiki=None)
