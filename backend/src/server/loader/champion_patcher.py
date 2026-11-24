"""Carries a champion into a new patch: the hand-made part stays, the loader part is replaced, and the diff of
CommunityDragon's data decides per ability whether it stays validated (ROADMAP, Phase 3: automatic patching)."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterator

from src.server.loader.cdragon import SpellValues
from src.server.loader.champion_builder import (SLOTS, LoadedSpell, apply_loader_part, champion_stats,
                                                last_changed_patch, loaded_spells)
from src.server.models.ability import Ability
from src.server.models.change import Change, patch_note_changes
from src.server.models.champion import NewChampion, RawChampion
from src.server.models.enums import ChangeSource
from src.server.models.json_validation import ChampionJson
from src.server.models.passive import Passive
from src.server.simulation.formula import SLOT_PREFIXES


LOADED_SLOTS = ("passive",) + SLOTS
# Fields that are text, loader-owned or bookkeeping; everything else is hand-made and may hold formulas.
NOT_HAND_MADE = {"name", "description", "assumptions", "values", "tooltip", "raw_stats", "changes", "validated",
                 "image", "maxrank", "key", "rank_from"}
NAME = re.compile(r"\b(?:([a-z]\w*)\.)?([A-Za-z_]\w*)\b")
CALCULATION_REFERENCES = {"mDataValue", "mModifiedGameCalculation"}


@dataclass
class SpellDiff:
    lines: list[str] = field(default_factory=list)
    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    reshaped: set[str] = field(default_factory=set)  # calculations whose structure changed, not just their numbers
    tooltip_changed: bool = False
    old: SpellValues = field(default_factory=SpellValues)
    new: SpellValues = field(default_factory=SpellValues)


@dataclass
class PatchedChampion:
    champion: NewChampion
    unvalidated: dict[str, list[str]]  # container name -> why it lost its validation

    @property
    def changed(self) -> bool:
        return bool(self.champion.changes) or any(container.changes for _, container in _containers(self.champion))


def patch_champion(old: NewChampion, old_spells: dict[str, LoadedSpell], raw: RawChampion, entry: ChampionJson,
                   patch_notes: dict[str, list[str]]) -> PatchedChampion:
    """`patch_notes` are this champion's wiki lines per ability name; lines under other headings belong to the champion."""
    champion = NewChampion.parse_obj(old.dict(exclude={"id"}))
    champion.patch, champion.hotfix = raw.patch, raw.hotfix
    champion.last_changed = last_changed_patch(raw.champion_data) or old.last_changed
    max_ranks = {slot: spell.maxrank for slot, spell in zip(SLOTS, entry.spells)}
    new_spells = loaded_spells(raw, max_ranks)
    diffs = {slot: spell_diff(old_spells[slot], new_spells[slot]) for slot in LOADED_SLOTS if slot in old_spells}

    notes = dict(patch_notes)
    unvalidated = {}
    champion.changes = _data_changes(_stat_lines(champion, champion_stats(raw.cdragon)))
    for slot, container in _containers(champion):
        diff = diffs.get(slot, SpellDiff())
        lines = _note_lines(notes, container.name)
        if slot in new_spells:
            container.name = new_spells[slot].name or container.name
            lines += _note_lines(notes, container.name)
        if slot in max_ranks:
            _set_max_rank(container, max_ranks[slot], diff)
        container.changes = _data_changes(diff.lines) + patch_note_changes(lines)
        reasons = unvalidating_reasons(slot, used_names(container, slot), diffs)
        if lines and not diff.lines:
            reasons.append("named in the patch notes only")
        if container.validated and reasons:
            container.validated = False
            unvalidated[container.name] = reasons

    champion.changes += patch_note_changes([line for lines in notes.values() for line in lines])
    apply_loader_part(champion, new_spells)
    champion.validated = all(container.validated for _, container in _containers(champion))
    return PatchedChampion(champion, unvalidated)


def _note_lines(notes: dict[str, list[str]], name: str) -> list[str]:
    # Two-part abilities ("Safeguard / Iron Will") appear in the patch notes under either part.
    names = [name] + [part.strip() for part in name.split(" / ")] if " / " in name else [name]
    return [line for alias in names for line in notes.pop(alias, [])]


def spells_from_document(champion: NewChampion) -> dict[str, LoadedSpell]:
    """The fallback when the old patch has no raw data: only the stored values, so structure changes stay unseen."""
    return {slot: LoadedSpell(script_name="", name=getattr(champion, slot).name, tooltip=getattr(champion, slot).tooltip,
                              values=SpellValues(values=dict(getattr(champion, slot).values)), wiki=None)
            for slot in LOADED_SLOTS}


def spell_diff(old: LoadedSpell, new: LoadedSpell) -> SpellDiff:
    diff = SpellDiff(old=old.values, new=new.values)
    old_names, new_names = _names(old.values), _names(new.values)
    diff.added, diff.removed = new_names - old_names, old_names - new_names
    diff.reshaped = {name for name in old_names & new_names
                     if name in old.values.calculations and name in new.values.calculations
                     and _shape(old.values.calculations[name]) != _shape(new.values.calculations[name])}
    for name in sorted(old_names | new_names):
        before, after = _shown(old.values, name), _shown(new.values, name)
        if name in diff.added:
            diff.lines.append(f"{name}: new ({after})")
        elif name in diff.removed:
            diff.lines.append(f"{name}: removed (was {before})")
        elif before != after:
            diff.lines.append(f"{name}: {before} ⇒ {after}")
        elif name in diff.reshaped:  # e.g. an untranslated calculation whose parts changed
            diff.lines.append(f"{name}: calculation changed ({after})")
    diff.tooltip_changed = old.tooltip != new.tooltip
    if diff.tooltip_changed:
        diff.lines.append("Tooltip changed")
    return diff


def unvalidating_reasons(own_slot: str, used: dict[str, set[str]], diffs: dict[str, SpellDiff]) -> list[str]:
    """The rows of the ROADMAP's table that make a container unvalidated. Only numbers changing never does."""
    reasons = []
    if own := diffs.get(own_slot):
        if own.added:
            reasons.append(f"new values: {', '.join(sorted(own.added))}")
        if own.tooltip_changed:
            reasons.append("tooltip changed")
    for slot, names in used.items():
        diff = diffs.get(slot)
        if not diff:
            continue
        prefix = "" if slot == own_slot else f"{slot}."
        reasons += [f"{prefix}{name} is gone" for name in sorted(names & diff.removed)]
        reasons += [f"{prefix}{name} changed its structure" for name in sorted(diff.reshaped)
                    if _breaks_rules(name, names, diff)]
    return reasons


def _breaks_rules(name: str, used: set[str], diff: SpellDiff) -> bool:
    # A rule that uses the calculation by name follows it, if the translator understood it. A rule that rebuilt it
    # from its parts by hand doesn't.
    if name in used:
        return name in diff.new.unsupported
    parts = _calculation_names(diff.old.calculations[name]) | _calculation_names(diff.new.calculations[name])
    return bool(parts & used)


def used_names(container: Ability | Passive, own_slot: str) -> dict[str, set[str]]:
    """Every name the hand-made formulas mention, per slot: a bare name is the container's own, `q.X` is Q's.
    Words that aren't value names (enum texts, buff names) don't matter, they never match a diff."""
    used = defaultdict(set)
    for text in _strings(container.dict(exclude=NOT_HAND_MADE)):
        for prefix, name in NAME.findall(text):
            if prefix in SLOT_PREFIXES:
                used[prefix].add(name)
            else:
                used[own_slot].update(filter(None, (prefix, name)))
    return dict(used)


def _strings(value) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _names(values: SpellValues) -> set[str]:
    return set(values.values) | set(values.unsupported)


def _shown(values: SpellValues, name: str) -> str:
    if name in values.values:
        return values.values[name]
    return f"not translated: {values.unsupported.get(name, '')}"


def _shape(value):
    """The calculation without its numbers: equal shapes mean only numbers changed."""
    if isinstance(value, bool) or not isinstance(value, (int, float, dict, list)):
        return value
    if isinstance(value, dict):
        return {key: _shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shape(item) for item in value]
    return None


def _calculation_names(calculation) -> set[str]:
    if isinstance(calculation, dict):
        names = {value for key, value in calculation.items() if key in CALCULATION_REFERENCES and isinstance(value, str)}
        return names.union(*(_calculation_names(value) for value in calculation.values()))
    if isinstance(calculation, list):
        return set().union(*(_calculation_names(item) for item in calculation))
    return set()


def _containers(champion: NewChampion) -> list[tuple[str, Ability | Passive]]:
    extras = [(f"x{index}", ability) for index, ability in enumerate(champion.extra_abilities, start=1)]
    return [(slot, getattr(champion, slot)) for slot in LOADED_SLOTS] + extras


def _set_max_rank(ability, max_rank: int, diff: SpellDiff) -> None:
    if ability.maxrank != max_rank:
        diff.lines.append(f"Max rank: {ability.maxrank} ⇒ {max_rank}")
        ability.maxrank = max_rank


def _stat_lines(champion: NewChampion, stats: dict) -> list[str]:
    """Sets the new stats. Only lines, never a validation: nothing hand-made depends on them."""
    lines = []
    for name, value in stats.items():
        before = getattr(champion, name)
        if before != value:
            lines.append(f"{name}: {_format(before)} ⇒ {_format(value)}")
            setattr(champion, name, value)
    return lines


def _format(value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(getattr(value, "value", value))


def _data_changes(lines: list[str]) -> list[Change]:
    return [Change(source=ChangeSource.DATA, text=line) for line in lines]
