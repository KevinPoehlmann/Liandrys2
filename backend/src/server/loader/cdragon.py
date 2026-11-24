"""Turns CommunityDragon spell data into named values: formula strings our simulation can evaluate."""
import re
from dataclasses import dataclass, field

from src.server.simulation.formula import MAX_LEVEL


# Riot's level formulas end at 18; levels 19 and 20 (roles) keep the level 18 value unless the part says otherwise.
RIOT_MAX_LEVEL = 18
SIMPLE_TERM = re.compile(r"^-?[\w.]+$")
FUNCTION_NAME = re.compile(r"^\w+(?=\()")

# (mStat, mStatFormula) -> our variable. mStatFormula: 0 total, 1 base, 2 bonus.
# Only ids checked against known values; anything else is reported instead of guessed.
STAT_VARIABLES = {
    (0, 0): "ap", (0, 2): "bonus_ap",
    (1, 0): "armor", (1, 2): "bonus_armor",
    (2, 0): "ad", (2, 1): "base_ad", (2, 2): "bonus_ad",
    (6, 0): "mr", (6, 2): "bonus_mr",
    (7, 0): "movespeed",
    (12, 0): "max_hp", (12, 2): "bonus_hp",
}


class UnsupportedCalculation(Exception):
    pass


@dataclass
class SpellValues:
    values: dict[str, str] = field(default_factory=dict)
    unsupported: dict[str, str] = field(default_factory=dict)  # name -> why the loader could not translate it


def spell_values(spell: dict, max_rank: int) -> SpellValues:
    result = SpellValues()
    for data_value in spell.get("DataValues") or []:
        _add(result, data_value.get("name", ""), lambda: _rank_value(data_value.get("values", []), max_rank))
    for name, calculation in (spell.get("mSpellCalculations") or {}).items():
        _add(result, name, lambda: translate_calculation(calculation))
    return result


def _add(result: SpellValues, name: str, translate) -> None:
    if not name.isidentifier():
        return  # hashed names like {7d38e7d6} can't be referenced; they stay in the raw data
    try:
        result.values[name] = translate()
    except UnsupportedCalculation as error:
        result.unsupported[name] = str(error)


def format_number(value: float) -> str:
    # Six significant digits remove float noise (0.44999998807907104 -> 0.45).
    return f"{float(f'{value:.6g}'):g}"


def _rank_value(values: list[float], max_rank: int) -> str:
    # Index 0 is rank 0, so a 5-rank ability uses entries 1-5.
    if not values:
        return "0"
    ranked = values[1:max_rank + 1] if max_rank else values
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
            formula = calculation["mModifiedGameCalculation"]
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
            return part["mDataValue"]
        case "NumberCalculationPart":
            return format_number(part.get("mNumber", 0))
        case "StatByNamedDataValueCalculationPart":
            return f"{part['mDataValue']} * {_stat(part)}"
        case "StatByCoefficientCalculationPart":
            if "mCoefficient" not in part:
                raise UnsupportedCalculation("stat part without coefficient")
            return _scaled(part["mCoefficient"], _stat(part))
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


def _stat(part: dict) -> str:
    key = (part.get("mStat", 0), part.get("mStatFormula", 0))
    if key not in STAT_VARIABLES:
        raise UnsupportedCalculation(f"stat {key[0]} with formula {key[1]}")
    return STAT_VARIABLES[key]


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
    start, end = part.get("mStartValue", 0), part.get("mEndValue", 0)
    step = (end - start) / (RIOT_MAX_LEVEL - 1)
    last_level = MAX_LEVEL if part.get("mScalePastDefaultMaxLevel") else RIOT_MAX_LEVEL
    return [start + step * (min(level, last_level) - 1) for level in range(1, MAX_LEVEL + 1)]


def _breakpoints(part: dict) -> list[float]:
    # A breakpoint either adds a one-time bonus at its level or changes the bonus per level from then on.
    breakpoints = {point["mLevel"]: point for point in part.get("mBreakpoints", [])}
    value = part.get("mLevel1Value", 0)
    per_level = part.get("mInitialBonusPerLevel", 0)
    values = [value]
    for level in range(2, MAX_LEVEL + 1):
        point = breakpoints.get(level, {})
        per_level = point.get("mBonusPerLevelAtAndAfter", per_level)
        value += per_level + point.get("mAdditionalBonusAtThisLevel", 0)
        values.append(value)
    return values


def _by_level(values: list[float]) -> str:
    if len(set(format_number(value) for value in values)) == 1:
        return format_number(values[0])
    return f"by_level({', '.join(format_number(value) for value in values)})"
