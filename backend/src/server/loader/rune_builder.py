"""Builds a rune from its raw data and patches it forward like a summoner spell: one slot, the champion patcher's
diff and validation table. The loader owns the named values, the tooltip and a stat shard's stats; the rest of the
passive is hand-made."""
import math
import re
from dataclasses import dataclass, field

from src.server.loader.cdragon import SpellValues, rune_values
from src.server.loader.champion_builder import LoadedSpell
from src.server.loader.champion_patcher import (buff_renames, data_changes, rename_hand_made, spell_diff,
                                                unvalidating_reasons, used_names)
from src.server.models.change import Change
from src.server.models.enums import Stat
from src.server.models.image import Image
from src.server.models.json_validation import RuneTreeJson
from src.server.models.passive import Passive
from src.server.models.rule import StatModifier
from src.server.models.rune import NewRune, RawRune


SLOT = "rune"  # bare names in a rune's formulas belong to the rune
SHARD_TREE, SHARD_TREE_ID = "Stat Shard", 0
SHARD_ROWS = ("offensive", "flex", "defensive")  # the end of a PerkSlot's mSlotLabelKey, in the client's order
# What a shard's numbers mean, by its perk name; CDragon only has the numbers. Percentages are fractions like ours.
SHARD_STATS = {
    "Adaptive": (Stat.AF, "StatGain2"),  # 9 adaptive force; StatGain1 is the same as 5.4 AD
    "AttackSpeed": (Stat.ATTACKSPEED_P, "StatGain / 100"),
    "CDRScaling": (Stat.ABILITY_HASTE, "HasteGain"),
    "MovementSpeed": (Stat.MOVESPEED_P, "StatGain1 / 100"),
    # "10 – 180 (based on level)": linear from level 1 to 18 and on past it, like the other level curves.
    "HealthScaling": (Stat.HP, "StatGainMin + (StatGainMax - StatGainMin) * (level - 1) / 17"),
    "Health": (Stat.HP, "StatGain"),
    "Tenacity": (Stat.TENACITY_P, "StatGain / 100"),  # "and slow resist"; slow resist isn't simulated
}
WIKI_COOLDOWN = re.compile(r"^\|[ \t]*cooldown[ \t]*=[ \t]*([^\n|]*)", re.MULTILINE)  # an empty field stays empty


@dataclass(frozen=True)
class RuneEntry:
    """A rune's place in the client: Data Dragon's trees, or CommunityDragon's shard rows."""
    rune_id: int
    name: str
    tree: str
    tree_id: int
    row: int
    slot: int
    image: str  # the file name of Data Dragon's icon, until the CDragon image is stored

    @property
    def is_shard(self) -> bool:
        return self.tree_id == SHARD_TREE_ID

    @property
    def key(self) -> tuple[int, int | None]:
        # A stat shard can sit in two rows (Adaptive Force in Offense and Flex): one document per row.
        return self.rune_id, self.row if self.is_shard else None


@dataclass
class PatchedRune:
    rune: NewRune
    unvalidated: list[str] = field(default_factory=list)  # why it lost its validation


def tree_entries(trees: list[RuneTreeJson]) -> list[RuneEntry]:
    return [RuneEntry(rune.id_, rune.name, tree.name, tree.id_, row, slot, _file_name(rune.icon))
            for tree in trees for row, runes in enumerate(tree.slots) for slot, rune in enumerate(runes.runes)]


def shard_entries(perks_bin: dict, strings: dict[str, str]) -> list[RuneEntry]:
    """The three shard rows from their PerkSlot records; the name carries the row, so each row is its own document."""
    rows = {}
    for record in perks_bin.values():
        if isinstance(record, dict) and record.get("__type") == "PerkSlot":
            label = record.get("mSlotLabelKey", "")
            for row, ending in enumerate(SHARD_ROWS):
                if label.endswith(ending):
                    rows[row] = (strings.get(label.lower(), ending.title()), record.get("mPerks", []))
    entries = []
    for row, (row_name, paths) in sorted(rows.items()):
        for slot, perk in enumerate(perks_bin.get(path) for path in paths):
            if isinstance(perk, dict) and "mPerkId" in perk:
                name = strings.get(perk.get("mDisplayNameLocalizationKey", "").lower(), perk.get("mPerkName", ""))
                entries.append(RuneEntry(perk["mPerkId"], f"{name} ({row_name})", SHARD_TREE, SHARD_TREE_ID, row,
                                         slot, _file_name(perk.get("mIconTextureName", ""))))
    return entries


def _file_name(icon: str) -> str:
    return icon.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() + ".png" if icon else ""


def build_rune(raw: RawRune, entry: RuneEntry) -> NewRune:
    rune = NewRune(rune_id=entry.rune_id, name=entry.name, patch=raw.patch, tree=entry.tree, tree_id=entry.tree_id,
                   row=entry.row, slot=entry.slot, passive=Passive(name=entry.name),
                   image=Image(full=entry.image, group="rune"))
    apply_loader_part(rune, raw, entry, loaded_rune(raw))
    # A shard is only its stats, which the loader builds; nothing to enter by hand.
    rune.validated = entry.is_shard and bool(rune.passive.stats)
    return rune


def loaded_rune(raw: RawRune) -> LoadedSpell:
    tooltip_key = raw.cdragon.get("mTooltipNameLocalizationKey", "").lower()
    return LoadedSpell(script_name=str(raw.rune_id), name="", tooltip=raw.strings.get(tooltip_key, ""),
                       values=rune_values(raw.cdragon), wiki=None)


def apply_loader_part(rune: NewRune, raw: RawRune, entry: RuneEntry, loaded: LoadedSpell) -> None:
    """Overwrites what the loader owns; the passive's hand-made part stays."""
    rune.name = rune.passive.name = entry.name
    rune.tree, rune.tree_id, rune.row, rune.slot = entry.tree, entry.tree_id, entry.row, entry.slot
    rune.passive.values, rune.passive.tooltip = loaded.values.values, loaded.tooltip
    if entry.is_shard:
        rune.passive.stats = shard_stats(raw)


def shard_stats(raw: RawRune) -> list[StatModifier]:
    known = SHARD_STATS.get(raw.cdragon.get("mPerkName", ""))
    return [StatModifier(stat=known[0], formula=known[1])] if known else []


def unknown_shard(raw: RawRune) -> bool:
    return raw.cdragon.get("mPerkName", "") not in SHARD_STATS


def wiki_mismatches(rune: NewRune, raw: RawRune) -> list[str]:
    """The wiki's cooldown against ours, where both are plain numbers. Only logged, like the other cross-checks."""
    if not raw.wiki_data or not (match := WIKI_COOLDOWN.search(raw.wiki_data.text)):
        return []
    wiki = _number(match.group(1))
    ours = {name: number for name, value in rune.passive.values.items()
            if "cooldown" in name.lower() and (number := _number(value)) is not None}
    if wiki is None or not ours or any(math.isclose(wiki, number, abs_tol=1e-3) for number in ours.values()):
        return []
    shown = ", ".join(f"{name} {number:g}" for name, number in sorted(ours.items()))
    return [f"cooldown: wiki {wiki:g}, CDragon {shown}"]


def _number(value) -> float | None:
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def patch_rune(old: NewRune, old_rune: LoadedSpell, raw: RawRune, entry: RuneEntry, notes: list[Change]) -> PatchedRune:
    """The hand-made part stays, the loader part is replaced, and the diff decides the validation (ROADMAP table)."""
    rune = NewRune.parse_obj(old.dict(exclude={"id"}))
    rune.patch = raw.patch
    new_rune = loaded_rune(raw)
    diff = spell_diff(old_rune, new_rune)
    if diff.renamed or diff.renamed_buffs:
        rename_hand_made(rune.passive, SLOT, {SLOT: diff.renamed}, buff_renames(diff.renamed_buffs))

    position = _position_lines(rune, entry)
    apply_loader_part(rune, raw, entry, new_rune)
    # After the loader part, so a shard's own stats count: a value they use that is gone unvalidates it.
    reasons = unvalidating_reasons(SLOT, used_names(rune.passive, SLOT), {SLOT: diff})
    lines = diff.lines + position
    if notes and not lines:
        reasons.append("named in the patch notes only")
    rune.changes = data_changes(lines) + notes
    if not (rune.validated and reasons):
        return PatchedRune(rune)
    rune.validated = False
    return PatchedRune(rune, reasons)


def _position_lines(rune: NewRune, entry: RuneEntry) -> list[str]:
    # Moving to another tree or row changes the choice in the client, not the rune's rules.
    lines = [f"tree: {rune.tree} ⇒ {entry.tree}"] if rune.tree_id != entry.tree_id else []
    if (rune.row, rune.slot) != (entry.row, entry.slot):
        lines.append(f"row, slot: {rune.row}, {rune.slot} ⇒ {entry.row}, {entry.slot}")
    return lines


def rune_from_document(rune: NewRune) -> LoadedSpell:
    """The fallback when the old patch has no raw data: only the stored values, so structure changes stay unseen."""
    return LoadedSpell(script_name=str(rune.rune_id), name="", tooltip=rune.passive.tooltip,
                       values=SpellValues(values=dict(rune.passive.values)), wiki=None)
