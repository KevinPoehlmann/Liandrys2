"""Carries a champion into a new patch: the hand-made part stays, the loader part is replaced, and the diff of
CommunityDragon's data decides per ability whether it stays validated (ROADMAP, Phase 3: automatic patching)."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterator

from pydantic import BaseModel

from src.server.loader.cdragon import (NAMED_BREAKPOINT, NAMED_BREAKPOINTS, NAMED_INTERPOLATION, NAMED_LINEAR,
                                       SpellValues, field_hash, name_hash, value_name)
from src.server.loader.champion_builder import (SLOTS, LoadedSpell, apply_loader_part, champion_stats,
                                                last_changed_patch, loaded_spells)
from src.server.models.ability import Ability, ExtraAbility
from src.server.models.change import Change, with_hotfix_lines
from src.server.models.champion import NewChampion, RawChampion
from src.server.models.enums import ChangeSource
from src.server.models.json_validation import ChampionJson
from src.server.models.passive import Passive
from src.server.simulation.formula import ELAPSED_PREFIX, OWNER_PREFIX, SLOT_PREFIXES, STACKS_PREFIX, TARGET_PREFIX


LOADED_SLOTS = ("passive",) + SLOTS
# Fields that are text, loader-owned or bookkeeping; everything else is hand-made and may hold formulas.
NOT_HAND_MADE = {"name", "description", "assumptions", "values", "tooltip", "raw_stats", "changes", "validated",
                 "image", "maxrank", "key", "rank_from"}
NAME = re.compile(r"\b(?:([a-z]\w*)\.)?([A-Za-z_]\w*)\b")
BUFF_COUNTER = re.compile(rf"\b(?:{STACKS_PREFIX}|{ELAPSED_PREFIX})(\w+)")
# Fields that name another value of the same spell, by hash because some are only known as hashes ({91d404a5}).
CALCULATION_REFERENCES = {field_hash(name) for name in (
    "mDataValue", "mModifiedGameCalculation", "mSpellCalculationKey", *NAMED_INTERPOLATION.values(),
    *NAMED_LINEAR.values(), *NAMED_BREAKPOINTS.values(), *NAMED_BREAKPOINT.values())}


@dataclass
class SpellDiff:
    lines: list[str] = field(default_factory=list)
    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    reshaped: set[str] = field(default_factory=set)  # calculations whose structure changed, not just their numbers
    renamed: dict[str, str] = field(default_factory=dict)  # h_<hash> -> the name CDragon learned for it
    renamed_buffs: dict[str, str] = field(default_factory=dict)  # the same for buffs the formulas count
    tooltip_changed: bool = False
    old: SpellValues = field(default_factory=SpellValues)
    new: SpellValues = field(default_factory=SpellValues)


@dataclass
class PatchedChampion:
    champion: NewChampion
    unvalidated: dict[str, list[str]]  # container name -> why it lost its validation

    @property
    def changed(self) -> bool:
        return has_changes(self.champion)


def has_changes(champion: NewChampion) -> bool:
    return bool(champion.changes) or any(container.changes for _, container in _containers(champion))


def keep_earlier_changes(champion: NewChampion, earlier: NewChampion, hotfixed_at: datetime) -> None:
    """A hotfix adds its lines to the ones its patch already brought."""
    champion.changes = with_hotfix_lines(earlier.changes, champion.changes, hotfixed_at)
    before = dict(_containers(earlier))
    for slot, container in _containers(champion):
        if slot in before:
            container.changes = with_hotfix_lines(before[slot].changes, container.changes, hotfixed_at)


def patch_champion(old: NewChampion, old_spells: dict[str, LoadedSpell], raw: RawChampion, entry: ChampionJson,
                   patch_notes: dict[str, list[Change]]) -> PatchedChampion:
    """`patch_notes` are this champion's patch note changes per ability name; lines under other headings belong to the champion."""
    champion = NewChampion.parse_obj(old.dict(exclude={"id"}))
    champion.patch = raw.patch
    champion.last_changed = last_changed_patch(raw.champion_data) or old.last_changed
    max_ranks = {slot: spell.maxrank for slot, spell in zip(SLOTS, entry.spells)}
    new_spells = loaded_spells(raw, max_ranks)
    diffs = {slot: spell_diff(old_spells[slot], new_spells[slot]) for slot in LOADED_SLOTS if slot in old_spells}
    renames = {slot: diff.renamed for slot, diff in diffs.items() if diff.renamed}
    # Buffs belong to the champion, not a slot: Q's values may count a buff the passive applies.
    buffs = buff_renames({old: new for diff in diffs.values() for old, new in diff.renamed_buffs.items()})

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
        container.changes = _data_changes(diff.lines) + lines
        if renames or buffs:
            _rename_hand_made(container, slot, renames, buffs)
        reasons = unvalidating_reasons(slot, used_names(container, slot), diffs)
        if lines and not _data_lines_behind(container, diff, diffs):
            reasons.append("named in the patch notes only")
        if container.validated and reasons:
            container.validated = False
            unvalidated[container.name] = reasons

    champion.changes += [line for lines in notes.values() for line in lines]
    apply_loader_part(champion, new_spells)
    champion.validated = all(container.validated for _, container in _containers(champion))
    return PatchedChampion(champion, unvalidated)


def _data_lines_behind(container: Ability | Passive, diff: SpellDiff, diffs: dict[str, SpellDiff]) -> list[str]:
    # An extra ability has no spell of its own: CDragon keeps its numbers in the spell it ranks with
    # (Nidalee's Pounce damage is R's PounceDamage).
    if isinstance(container, ExtraAbility):
        return diffs.get(container.rank_from.value, SpellDiff()).lines
    return diff.lines


def _note_lines(notes: dict[str, list[Change]], name: str) -> list[Change]:
    # Two-part abilities ("Safeguard / Iron Will") appear in the patch notes under either part.
    names = [name] + [part.strip() for part in name.split(" / ")] if " / " in name else [name]
    return [line for alias in names for line in notes.pop(alias, [])]


def spells_from_document(champion: NewChampion) -> dict[str, LoadedSpell]:
    """The fallback when the old patch has no raw data: only the stored values, so structure changes stay unseen."""
    return {slot: LoadedSpell(script_name="", name=getattr(champion, slot).name, tooltip=getattr(champion, slot).tooltip,
                              values=SpellValues(values=dict(getattr(champion, slot).values)), wiki=None)
            for slot in LOADED_SLOTS}


def spell_diff(old: LoadedSpell, new: LoadedSpell) -> SpellDiff:
    renamed = _renames(_names(old.values), _names(new.values))
    renamed_buffs = _renames(_buffs(old.values), _buffs(new.values))
    diff = SpellDiff(old=_with_renames(old.values, renamed, renamed_buffs), new=new.values, renamed=renamed,
                     renamed_buffs=renamed_buffs)
    diff.lines = [f"{hashed}: renamed to {name}" for hashed, name in sorted(renamed.items())]
    diff.lines += [f"Buff {hashed}: renamed to {name}" for hashed, name in sorted(renamed_buffs.items())]
    old_names, new_names = _names(diff.old), _names(diff.new)
    diff.added, diff.removed = new_names - old_names, old_names - new_names
    diff.reshaped = {name for name in old_names & new_names
                     if name in diff.old.calculations and name in diff.new.calculations
                     and _shape(diff.old.calculations[name]) != _shape(diff.new.calculations[name])}
    for name in sorted(old_names | new_names):
        before, after = _shown(diff.old, name), _shown(diff.new, name)
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


def _renames(old_names: set[str], new_names: set[str]) -> dict[str, str]:
    # CDragon learned a name it only knew as a hash: the new name hashes to the old h_<hash>.
    by_hash = {f"h_{field_hash(name)}": name for name in new_names - old_names}
    return {name: by_hash[name] for name in old_names - new_names if name in by_hash}


def _buffs(values: SpellValues) -> set[str]:
    return {match[1] for formula in values.values.values() for match in BUFF_COUNTER.finditer(formula)}


def buff_renames(renamed: dict[str, str]) -> dict[str, str]:
    """Every word that names a renamed buff: the buff itself (`Buff.name`, `ApplyBuff.buff`) and the formula
    variables that read it, also on the target or owner."""
    return renamed | {f"{owner}{kind}{old}": f"{owner}{kind}{new}" for old, new in renamed.items()
                      for owner in ("", TARGET_PREFIX, OWNER_PREFIX) for kind in (STACKS_PREFIX, ELAPSED_PREFIX)}


def _with_renames(values: SpellValues, renamed: dict[str, str], renamed_buffs: dict[str, str]) -> SpellValues:
    if not renamed and not renamed_buffs:
        return values
    renames, buffs = {None: renamed}, buff_renames(renamed_buffs)
    return SpellValues(values={renamed.get(name, name): rename_names(formula, renames, buffs=buffs)
                               for name, formula in values.values.items()},
                       unsupported={renamed.get(name, name): why for name, why in values.unsupported.items()},
                       calculations={renamed.get(name, name): calc for name, calc in values.calculations.items()})


def rename_names(text: str, renames: dict[str | None, dict[str, str]], own_slot: str | None = None,
                 buffs: dict[str, str] | None = None) -> str:
    """Renames the value names in a formula: a bare name belongs to `own_slot`, `q.X` to Q. `buffs` (from
    `buff_renames`) hold for every slot."""
    def rename(match: re.Match) -> str:
        prefix, name = match[1], match[2]
        if prefix and prefix not in SLOT_PREFIXES:
            return match[0]
        new = renames.get(prefix or own_slot, {}).get(name, name)
        if prefix:
            return f"{prefix}.{new}"
        return (buffs or {}).get(new, new)
    return NAME.sub(rename, text)


def _rename_hand_made(container: Ability | Passive, slot: str, renames: dict[str, dict[str, str]],
                      buffs: dict[str, str]) -> None:
    for name in container.__fields__.keys() - NOT_HAND_MADE:
        _set_if_changed(container, name, _renamed(getattr(container, name), slot, renames, buffs))


def _renamed(value, slot: str, renames: dict[str, dict[str, str]], buffs: dict[str, str]):
    if isinstance(value, Enum):  # str enums are strings too, but never formulas
        return value
    if isinstance(value, str):
        return rename_names(value, renames, slot, buffs)
    if isinstance(value, list):
        return [_renamed(item, slot, renames, buffs) for item in value]
    if isinstance(value, dict):
        return {key: _renamed(item, slot, renames, buffs) for key, item in value.items()}
    if isinstance(value, BaseModel):
        for name in value.__fields__:
            _set_if_changed(value, name, _renamed(getattr(value, name), slot, renames, buffs))
    return value


def _set_if_changed(model: BaseModel, name: str, value) -> None:
    if getattr(model, name) != value:
        setattr(model, name, value)


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
    """The calculation without its numbers: equal shapes mean only numbers changed. Names and fields count by their
    hash, so a name CDragon just learned ({6a1a62e9} ⇒ PercentDamage) doesn't change the shape either."""
    if isinstance(value, str):
        return name_hash(value)
    if isinstance(value, bool) or not isinstance(value, (int, float, dict, list)):
        return value
    if isinstance(value, dict):
        return {name_hash(key): _shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shape(item) for item in value]
    return None


def _calculation_names(calculation) -> set[str]:
    if isinstance(calculation, dict):
        names = {value_name(value) for key, value in calculation.items()
                 if name_hash(key) in CALCULATION_REFERENCES and isinstance(value, str)} - {None}
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
