"""Builds an item from its raw data and carries it into a new patch. An item's values belong to the item (its active
and passives share them), so the champion patcher's diff and validation table apply with a single slot."""
import math
from dataclasses import dataclass, field

from src.server.loader.cdragon import SpellValues, format_number, item_values
from src.server.loader.champion_builder import LoadedSpell
from src.server.loader.champion_patcher import (buff_renames, data_changes, rename_hand_made, spell_diff,
                                                unvalidating_reasons, used_names)
from src.server.loader.patch_notes import wikitext_to_text
from src.server.loader.summonerspell_builder import maps
from src.server.models.ability import ItemActive
from src.server.models.change import Change
from src.server.models.enums import ActiveType, ItemClass, Stat
from src.server.models.json_validation import ItemJson
from src.server.models.item import NewItem, RawItem
from src.server.models.passive import ItemPassive


SLOT = "item"  # bare names in an item's formulas belong to the item
RIFT_MODE = "classic sr 5v5"  # Module:ItemData's mode
COOLDOWN = "Cooldown"  # the item's data value; the cooldown in the spell it names is mostly 0 or stale
TOOLTIP = "generatedtip_item_{}_description"  # stats, active and passives in one text
# Percentages are fractions like our stats (0.25 attack speed); regeneration is per second.
STAT_FIELDS = {
    "mFlatPhysicalDamageMod": Stat.AD, "mFlatMagicDamageMod": Stat.AP, "mFlatHPPoolMod": Stat.HP,
    "mFlatArmorMod": Stat.ARMOR, "mFlatSpellBlockMod": Stat.MR, "mAbilityHasteMod": Stat.ABILITY_HASTE,
    "mPercentAttackSpeedMod": Stat.ATTACKSPEED_P, "mFlatCritChanceMod": Stat.CRIT_P,
    "mFlatCritDamageMod": Stat.CRIT_DAMAGE, "PhysicalLethality": Stat.LETHALITY,
    "mPercentArmorPenetrationMod": Stat.ARMOR_PEN_P, "mFlatMagicPenetrationMod": Stat.MAGIC_PEN,
    "mPercentMagicPenetrationMod": Stat.MAGIC_PEN_P, "mPercentLifeStealMod": Stat.LIFE_STEAL_P,
    "PercentOmnivampMod": Stat.OMNIVAMP_P, "flatMPPoolMod": Stat.MANA, "mFlatMovementSpeedMod": Stat.MOVESPEED,
    "mPercentMovementSpeedMod": Stat.MOVESPEED_P, "mPercentBaseHPRegenMod": Stat.HP_REG_P,
    "percentBaseMPRegenMod": Stat.MANA_REG_P, "mFlatHPRegenMod": Stat.HP_REG, "flatMPRegenMod": Stat.MANA_REG,
    "mPercentHealingAmountMod": Stat.HEAL_N_SHIELD_P, "mPercentTenacityItemMod": Stat.TENACITY_P,
    "mPercentSlowResistMod": Stat.SLOW_RESIST_P, "mFlatAttackRangeMod": Stat.ATTACK_RANGE,
}
STAT_FIELD_ENDINGS = ("Mod", "Lethality")
# Module:ItemData's stats in our units: (stat, factor); the wiki writes percentages as 25 and regeneration per 5 s.
WIKI_STATS = {
    "ad": (Stat.AD, 1), "ap": (Stat.AP, 1), "hp": (Stat.HP, 1), "armor": (Stat.ARMOR, 1), "mr": (Stat.MR, 1),
    "ah": (Stat.ABILITY_HASTE, 1), "as": (Stat.ATTACKSPEED_P, 0.01), "crit": (Stat.CRIT_P, 0.01),
    "critdamage": (Stat.CRIT_DAMAGE, 0.01), "lethality": (Stat.LETHALITY, 1), "armpen": (Stat.ARMOR_PEN_P, 0.01),
    "mpenflat": (Stat.MAGIC_PEN, 1), "mpen": (Stat.MAGIC_PEN_P, 0.01), "lifesteal": (Stat.LIFE_STEAL_P, 0.01),
    "omnivamp": (Stat.OMNIVAMP_P, 0.01), "mana": (Stat.MANA, 1), "msflat": (Stat.MOVESPEED, 1),
    "ms": (Stat.MOVESPEED_P, 0.01), "hp5": (Stat.HP_REG_P, 0.01), "mp5": (Stat.MANA_REG_P, 0.01),
    "hp5flat": (Stat.HP_REG, 0.2), "hsp": (Stat.HEAL_N_SHIELD_P, 0.01), "tenacity": (Stat.TENACITY_P, 0.01),
}
WIKI_CLASSES = {
    "Legendary": ItemClass.LEGENDARY, "Epic": ItemClass.EPIC, "Boots": ItemClass.BOOTS, "Basic": ItemClass.BASIC,
    "Starter": ItemClass.STARTER, "Consumable": ItemClass.CONSUMABLE, "Potion": ItemClass.CONSUMABLE,
    "Distributed": ItemClass.DISTRIBUTED, "Trinket": ItemClass.TRINKET, "Turret": ItemClass.TOWER_MINION,
    "Minion": ItemClass.TOWER_MINION,
}
# Ornn's Masterwork (wiki, Living Forge notes): 1000 gold of value shared equally by the upgradeable stats, rounded
# down. Gold per point; attack speed per 1 %, our 0.01.
MASTERWORK_GOLD = 1000
MASTERWORK_STATS = {Stat.ABILITY_HASTE: 31.25, Stat.AP: 20, Stat.AD: 35, Stat.ATTACKSPEED_P: 3000, Stat.ARMOR: 20,
                    Stat.MR: 18}
MASTERWORK_HP = {0: 375, 1: 185, 2: 125, 3: 90}  # health by the number of other upgradeable stats, fixed by Riot


@dataclass
class PatchedItem:
    item: NewItem
    unvalidated: list[str] = field(default_factory=list)  # why it lost its validation


def rift_items(items: list[tuple[str, ItemJson]], item_data: dict[str, dict]) -> list[tuple[str, ItemJson]]:
    """V1 covers Summoner's Rift. Module:ItemData knows the modes; Data Dragon's map 11 also lists the other modes'
    copies (Swiftplay's 32xxxx, the 66xxxx ones), so without the module only its purchasable 4-digit ids count."""
    if item_data:
        return [(item_id, item) for item_id, item in items
                if (item_data.get(item_id, {}).get("modes") or {}).get(RIFT_MODE)]
    return [(item_id, item) for item_id, item in items
            if item.maps.get("11") and item.gold.purchasable and len(item_id) == 4]


def build_item(raw: RawItem, entry: ItemJson) -> NewItem:
    item = NewItem(item_id=raw.item_id, name=entry.name, patch=raw.patch, gold=entry.gold.total, into=entry.into,
                   from_=entry.from_, image=entry.image)
    loaded = loaded_item(raw)
    item.active, item.passives = initial_effects(raw.item_data, entry.name, loaded.values.values)
    item.validated = item.active is None and not item.passives  # stats alone need nothing entered by hand
    apply_loader_part(item, raw, entry, loaded)
    return item


def loaded_item(raw: RawItem) -> LoadedSpell:
    strings = {key.lower(): text for key, text in raw.strings.items()}
    return LoadedSpell(script_name=raw.item_id, name="", tooltip=strings.get(TOOLTIP.format(raw.item_id), ""),
                       values=item_values(raw.cdragon), wiki=None)


def initial_effects(item_data: dict, name: str, values: dict[str, str]) -> tuple[ItemActive | None, list[ItemPassive]]:
    """A newly seen effect starts with its name from Module:ItemData; the rest is hand-made."""
    active, passives = None, []
    for key, effect in (item_data.get("effects") or {}).items():
        if key == "consume":  # potions and elixirs: only a description, named like the item
            active = ItemActive(name=name, type_=ActiveType.CONSUME)
        elif key == "act" and isinstance(effect, dict):
            active = ItemActive(name=effect.get("name") or name, unique=bool(effect.get("unique")),
                                type_=ActiveType.ACTIVE, cooldown=COOLDOWN if COOLDOWN in values else "0")
        elif key.startswith("pass") and isinstance(effect, dict) and effect.get("name"):
            passives.append(ItemPassive(name=effect["name"], unique=bool(effect.get("unique"))))
    return active, passives


def apply_loader_part(item: NewItem, raw: RawItem, entry: ItemJson, loaded: LoadedSpell) -> None:
    """Overwrites what the loader owns; the active's and passives' hand-made parts stay."""
    item.name, item.gold, item.into, item.from_ = entry.name, entry.gold.total, entry.into, entry.from_
    item.maps = maps([map_id for map_id, available in entry.maps.items() if available])
    item.values, item.tooltip = loaded.values.values, loaded.tooltip
    item.stats = item_stats(raw.cdragon)
    item.class_ = item_class(raw.item_data)
    item.masterwork = masterwork(item.stats) if item.class_ == ItemClass.LEGENDARY else {}
    item.limitations = limitations(raw.item_data)
    item.requirements = requirements(raw.item_data)


def item_stats(record: dict) -> dict[Stat, float]:
    return {stat: float(format_number(record[name])) for name, stat in STAT_FIELDS.items() if record.get(name)}


def unknown_stat_fields(record: dict) -> list[str]:
    """Number fields that look like stats but aren't mapped (mFlatArmorPenetrationMod in other modes)."""
    return [name for name, value in record.items() if name.endswith(STAT_FIELD_ENDINGS) and name not in STAT_FIELDS
            and isinstance(value, (int, float)) and not isinstance(value, bool) and value]


def item_class(item_data: dict) -> ItemClass:
    # A list like ["Distributed", "Special", "Prismatic"]: the first type we know decides.
    types = item_data.get("type") or []
    return next((WIKI_CLASSES[type_] for type_ in types if type_ in WIKI_CLASSES), ItemClass.NONE)


def masterwork(stats: dict[Stat, float]) -> dict[Stat, float]:
    """The bonus an Ornn upgrade adds: Thornmail's 75 armor and 150 health get +25 armor and +185 health."""
    upgradeable = [stat for stat in MASTERWORK_STATS if stat in stats]
    shares = len(upgradeable) + (Stat.HP in stats)
    bonus = {stat: _rounded_down(MASTERWORK_GOLD / shares / MASTERWORK_STATS[stat], stat) for stat in upgradeable}
    if Stat.HP in stats or not upgradeable:  # without upgradeable stats, all 1000 gold become health
        bonus[Stat.HP] = MASTERWORK_HP[min(len(upgradeable), 3)]
    return bonus


def _rounded_down(points: float, stat: Stat) -> float:
    if stat == Stat.ATTACKSPEED_P:  # whole percents
        return math.floor(points * 100 + 1e-9) / 100
    return math.floor(points + 1e-9)


def limitations(item_data: dict) -> str:
    # `limit` is the wiki's own sentence; `itemlimit` only names the group ("Spellblade").
    if text := item_data.get("limit"):
        return wikitext_to_text(text)
    groups = [item_data[key] for key in ("itemlimit", "itemlimit2") if isinstance(item_data.get(key), str)]
    return " ".join(f"Limited to 1 {group} item." for group in groups)


def requirements(item_data: dict) -> str:
    requirement = item_data.get("req") or item_data.get("champion") or ""
    if isinstance(requirement, list):  # Black Spear: ["Kalista", "Sylas"]
        return ", ".join(requirement)
    return wikitext_to_text(requirement)


def wiki_mismatches(item: NewItem, item_data: dict) -> list[str]:
    """Where our numbers differ from the wiki's module. Only logged, like the champions' cross-check."""
    mismatches = []
    wiki_stats = {stat: number * factor for key, (stat, factor) in WIKI_STATS.items()
                  if (number := _number((item_data.get("stats") or {}).get(key))) is not None}
    for stat in wiki_stats.keys() | item.stats.keys():
        wiki, ours = wiki_stats.get(stat), item.stats.get(stat)
        if wiki is not None and not math.isclose(wiki, ours or 0, abs_tol=1e-3):
            mismatches.append(f"{stat.value}: wiki {wiki:g}, CDragon {ours or 0:g}")
    if (buy := _number(item_data.get("buy"))) is not None and buy != item.gold:
        mismatches.append(f"gold: wiki {buy:g}, Data Dragon {item.gold}")
    active = (item_data.get("effects") or {}).get("act")
    wiki_cooldown = _number(active.get("cd")) if isinstance(active, dict) else None
    ours = _number(item.values.get(COOLDOWN))
    if wiki_cooldown is not None and ours is not None and not math.isclose(wiki_cooldown, ours, abs_tol=1e-3):
        mismatches.append(f"{COOLDOWN}: wiki {wiki_cooldown:g}, CDragon {ours:g}")
    return mismatches


def _number(value) -> float | None:
    # Wiki fields are often text ("{{tip|er|icononly=true}} 700"); only plain numbers compare.
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def patch_item(old: NewItem, old_item: LoadedSpell, raw: RawItem, entry: ItemJson, notes: list[Change]) -> PatchedItem:
    """The hand-made part stays, the loader part is replaced, and the diff decides the validation (ROADMAP table)."""
    item = NewItem.parse_obj(old.dict(exclude={"id"}))
    item.patch = raw.patch
    new_item = loaded_item(raw)
    diff = spell_diff(old_item, new_item)
    containers = [*([item.active] if item.active else []), *item.passives]
    if diff.renamed or diff.renamed_buffs:
        for container in containers:
            rename_hand_made(container, SLOT, {SLOT: diff.renamed}, buff_renames(diff.renamed_buffs))

    used: dict[str, set[str]] = {SLOT: set()}
    for container in containers:
        used[SLOT] |= used_names(container, SLOT).get(SLOT, set())
    reasons = unvalidating_reasons(SLOT, used, {SLOT: diff})
    reasons += _effect_changes(item, raw.item_data, new_item.values.values)
    old_stats = dict(item.stats)
    apply_loader_part(item, raw, entry, new_item)
    lines = diff.lines + _stat_lines(old_stats, item.stats) + _gold_lines(old.gold, item.gold)
    if notes and not lines:
        reasons.append("named in the patch notes only")
    item.changes = data_changes(lines) + notes
    if not (item.validated and reasons):
        return PatchedItem(item)
    item.validated = False
    return PatchedItem(item, reasons)


def _effect_changes(item: NewItem, item_data: dict, values: dict[str, str]) -> list[str]:
    """New effects get their container; one that is gone keeps its hand-made part, but its rules may be wrong."""
    if not item_data:  # without the module nothing is known about the effects
        return []
    active, passives = initial_effects(item_data, item.name, values)
    reasons = []
    if active and not item.active:
        item.active = active
        reasons.append(f"new active {active.name}")
    elif item.active and not active:
        reasons.append(f"active {item.active.name} not in the wiki anymore")
    known = {passive.name for passive in item.passives}
    for passive in passives:
        if passive.name not in known:
            item.passives.append(passive)
            reasons.append(f"new passive {passive.name}")
    for name in known - {passive.name for passive in passives}:
        reasons.append(f"passive {name} not in the wiki anymore")
    return reasons


def _stat_lines(old: dict[Stat, float], new: dict[Stat, float]) -> list[str]:
    return [f"{stat.value}: {old.get(stat, 0):g} ⇒ {new.get(stat, 0):g}"
            for stat in sorted(old.keys() | new.keys(), key=lambda stat: stat.value)
            if not math.isclose(old.get(stat, 0), new.get(stat, 0), abs_tol=1e-6)]


def _gold_lines(old: int, new: int) -> list[str]:
    return [f"gold: {old} ⇒ {new}"] if old != new else []


def item_from_document(item: NewItem) -> LoadedSpell:
    """The fallback when the old patch has no raw data: only the stored values, so structure changes stay unseen."""
    return LoadedSpell(script_name=item.item_id, name="", tooltip=item.tooltip,
                       values=SpellValues(values=dict(item.values)), wiki=None)
