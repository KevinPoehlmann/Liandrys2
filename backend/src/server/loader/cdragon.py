"""Turns CommunityDragon spell data into named values: formula strings our simulation can evaluate."""
import re
from dataclasses import dataclass, field

from src.server.simulation.formula import MAX_LEVEL


# Riot's level formulas are defined up to 18 and continue to 19 and 20 (roles). The bin files only store
# non-default fields, and mScalePastDefaultMaxLevel only ever appears as false, so scaling on is the default.
RIOT_MAX_LEVEL = 18
SIMPLE_TERM = re.compile(r"^-?[\w.]+$")
FUNCTION_NAME = re.compile(r"^\w+(?=\()")

# (mStat, mStatFormula) -> our variable. mStatFormula: 0 total, 1 base, 2 bonus.
# Only ids checked against known values; anything else is reported instead of guessed.
STAT_VARIABLES = {
    (0, 0): "ap", (0, 2): "bonus_ap",
    (1, 0): "armor", (1, 2): "bonus_armor",
    (2, 0): "ad", (2, 1): "base_ad", (2, 2): "bonus_ad",
    (4, 2): "bonus_attackspeed",  # Bel'Veth E, Aphelios Severum Q
    (6, 0): "mr", (6, 2): "bonus_mr",
    (7, 0): "movespeed",
    (8, 0): "crit_chance",  # Caitlyn's headshot, Ashe's passive
    (9, 0): "crit_damage", (9, 2): "bonus_crit_damage",  # Garen E: 1 + CritMod × (stat 9 − 1); Ashe P: × (1 + bonus)
    (12, 0): "max_hp", (12, 1): "base_hp", (12, 2): "bonus_hp",
    (29, 0): "lethality",  # Pyke R: 1.5 lethality
}
# mStatFormula of a resource part -> our variable. Mana is the only resource the simulation knows; every champion
# with such a part in 16.21 uses mana, and the one other resource (Tryndamere's fury, mAbilityResource 4) is reported.
RESOURCE_VARIABLES = {0: "max_mana", 1: "base_mana", 2: "bonus_mana"}


# Spell fields kept under Riot's old field names: the fields to read, live first, and the index of rank 1 (mana lists
# have no rank 0). The old lists are stale copies Riot no longer updates (Darius Q in 26.21: cooldownTime 9–5,
# Cooldown and the wiki 9–4); they stay as a fallback.
SPELL_FIELDS = {"cooldownTime": (("Cooldown", "cooldownTime"), 1), "mana": (("manaValues", "mana"), 0)}


class UnsupportedCalculation(Exception):
    pass


@dataclass
class SpellValues:
    values: dict[str, str] = field(default_factory=dict)
    unsupported: dict[str, str] = field(default_factory=dict)  # name -> why the loader could not translate it
    calculations: dict[str, dict] = field(default_factory=dict)  # Riot's mSpellCalculations, to compare their structure


def spell_values(spell: dict, max_rank: int) -> SpellValues:
    result = SpellValues()
    for data_value in spell.get("DataValues") or []:
        _add(result, data_value.get("name", ""), lambda: _rank_value(data_value.get("values", []), max_rank))
    for name, (sources, first_rank) in SPELL_FIELDS.items():
        # Always present, so `cooldown: "cooldownTime"` and `cost: "mana"` resolve even for free spells.
        _add(result, name, lambda: _rank_value(_spell_field(spell, sources), max_rank, first_rank))
    for name, calculation in (spell.get("mSpellCalculations") or {}).items():
        _add(result, name, lambda: translate_calculation(calculation))
        if name.isidentifier():
            result.calculations[name] = calculation
    return result


def _spell_field(spell: dict, sources: tuple[str, ...]) -> list[float]:
    for source in sources:
        value = spell.get(source)
        values = value.get("values") if isinstance(value, dict) else value
        if values:
            return values
    return []


def _add(result: SpellValues, name: str, translate) -> None:
    if not name.isidentifier():
        return  # hashed names like {7d38e7d6} can't be referenced; they stay in the raw data
    try:
        result.values[name] = translate()
    except UnsupportedCalculation as error:
        result.unsupported[name] = str(error)


def bin_field(record: dict, name: str, default=None):
    """A field by its name, or by its hash where CommunityDragon doesn't know the name yet ({726ee5cd} = arBaseModifiable)."""
    return record.get(name, record.get(f"{{{field_hash(name)}}}", default))


def field_hash(name: str) -> str:
    # FNV-1a (32 bit) of the lowercased name, the hash Riot's bin files use for field names.
    value = 0x811C9DC5
    for byte in name.lower().encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f"{value:08x}"


def format_number(value: float) -> str:
    # Six significant digits remove float noise (0.44999998807907104 -> 0.45).
    return f"{float(f'{value:.6g}'):g}"


def _rank_value(values: list[float], max_rank: int, first_rank: int = 1) -> str:
    # DataValues start at rank 0, so a 5-rank ability uses entries 1-5.
    if not values:
        return "0"
    ranked = values[first_rank:first_rank + max_rank] if max_rank else values
    if len(set(format_number(value) for value in ranked)) == 1:
        return format_number(ranked[0])
    if not max_rank:
        raise UnsupportedCalculation("values differ by rank, but the container has no ranks")
    return f"by_rank({', '.join(format_number(value) for value in ranked)})"


def translate_calculation(calculation: dict) -> str:
    match calculation.get("__type"):
        case "GameCalculation":
            formula = _sum(calculation.get("mFormulaParts", []))
        case "GameCalculationModified":
            formula = _name(calculation["mModifiedGameCalculation"])
        case other:
            raise UnsupportedCalculation(f"calculation type {other}")
    if "mMultiplier" in calculation:
        formula = f"{_factor(formula)} * {_factor(_part(calculation['mMultiplier']))}"
    return formula


def _sum(parts: list[dict]) -> str:
    if not parts:
        return "0"
    return " + ".join(_part(part) for part in parts)


def _part(part: dict) -> str:
    match part.get("__type"):
        case "NamedDataValueCalculationPart":
            return _name(part["mDataValue"])
        case "NumberCalculationPart":
            return format_number(part.get("mNumber", 0))
        case "StatByNamedDataValueCalculationPart":
            return f"{_name(part['mDataValue'])} * {_stat(part)}"
        case "StatByCoefficientCalculationPart":
            if "mCoefficient" not in part:
                raise UnsupportedCalculation("stat part without coefficient")
            return _scaled(part["mCoefficient"], _stat(part))
        case "AbilityResourceByCoefficientCalculationPart":
            return _scaled(part.get("mCoefficient", 0), _resource(part))
        case "StatBySubPartCalculationPart":
            return f"{_factor(_part(part['mSubpart']))} * {_stat(part)}"
        case "ProductOfSubPartsCalculationPart":
            return f"{_factor(_part(part['mPart1']))} * {_factor(_part(part['mPart2']))}"
        case "SumOfSubPartsCalculationPart":
            return f"({_sum(part.get('mSubparts', []))})"
        case "ClampSubPartsCalculationPart":
            return _clamp(part)
        case "ByCharLevelInterpolationCalculationPart":
            return _by_level(_interpolation(part))
        case "ByCharLevelBreakpointsCalculationPart":
            return _by_level(_breakpoints(part))
        case other:
            raise UnsupportedCalculation(f"part type {other}")


def _name(name: str) -> str:
    if not name.isidentifier():
        raise UnsupportedCalculation(f"refers to the hashed name {name}")
    return name


def _stat(part: dict) -> str:
    key = (part.get("mStat", 0), part.get("mStatFormula", 0))
    if key not in STAT_VARIABLES:
        raise UnsupportedCalculation(f"stat {key[0]} with formula {key[1]}")
    return STAT_VARIABLES[key]


def _resource(part: dict) -> str:
    resource, formula = part.get("mAbilityResource", 0), part.get("mStatFormula", 0)
    if resource != 0 or formula not in RESOURCE_VARIABLES:
        raise UnsupportedCalculation(f"ability resource {resource} with formula {formula}")
    return RESOURCE_VARIABLES[formula]


def _scaled(coefficient: float, variable: str) -> str:
    if format_number(coefficient) == "1":
        return variable
    return f"{format_number(coefficient)} * {variable}"


def _factor(expression: str) -> str:
    if SIMPLE_TERM.match(expression) or _is_wrapped(expression):
        return expression
    return f"({expression})"


def _is_wrapped(expression: str) -> bool:
    """True for "(a + b)" and "by_level(…)", False for "(a) + (b)"."""
    expression = FUNCTION_NAME.sub("", expression)
    if not expression.startswith("("):
        return False
    depth = 0
    for index, char in enumerate(expression):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0:
            return index == len(expression) - 1
    return False


def _clamp(part: dict) -> str:
    formula = _sum(part.get("mSubparts", []))
    if "mFloor" in part:
        formula = f"max({formula}, {format_number(part['mFloor'])})"
    if "mCeiling" in part:
        formula = f"min({formula}, {format_number(part['mCeiling'])})"
    return formula


def _interpolation(part: dict) -> list[float]:
    start, end = _clean(part.get("mStartValue", 0)), _clean(part.get("mEndValue", 0))
    step = (end - start) / (RIOT_MAX_LEVEL - 1)
    last_level = MAX_LEVEL if part.get("mScalePastDefaultMaxLevel", True) else RIOT_MAX_LEVEL
    return [start + step * (min(level, last_level) - 1) for level in range(1, MAX_LEVEL + 1)]


def _breakpoints(part: dict) -> list[float]:
    # A breakpoint either adds a one-time bonus at its level or changes the bonus per level from then on.
    # Riot leaves out the default level 1, which sets the bonus per level from the start (Yone W against minions).
    breakpoints = {point.get("mLevel", 1): point for point in part.get("mBreakpoints", [])}
    value = _clean(part.get("mLevel1Value", 0))
    per_level = _clean(breakpoints.get(1, {}).get("mBonusPerLevelAtAndAfter", part.get("mInitialBonusPerLevel", 0)))
    values = [value]
    for level in range(2, MAX_LEVEL + 1):
        point = breakpoints.get(level, {})
        per_level = _clean(point.get("mBonusPerLevelAtAndAfter", per_level))
        value += per_level + _clean(point.get("mAdditionalBonusAtThisLevel", 0))
        values.append(value)
    return values


def _clean(value: float) -> float:
    return float(format_number(value))


def _by_level(values: list[float]) -> str:
    # The inputs are already cleaned, so more digits keep interpolated steps (0.3 -> 0.45 in 17 steps) exact.
    formatted = [f"{value:.12g}" for value in values]
    if len(set(formatted)) == 1:
        return formatted[0]
    return f"by_level({', '.join(formatted)})"
