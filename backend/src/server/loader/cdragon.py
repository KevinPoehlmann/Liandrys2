"""Turns CommunityDragon spell data into named values: formula strings our simulation can evaluate."""
import re
from dataclasses import dataclass, field

from src.server.simulation.formula import COOLDOWN_MULTIPLIER, ELAPSED_PREFIX, MAX_LEVEL, STACKS_PREFIX, TARGET_PREFIX


# Riot's level formulas are defined up to 18 and continue to 19 and 20 (roles). The bin files only store
# non-default fields, and mScalePastDefaultMaxLevel only ever appears as false, so scaling on is the default.
RIOT_MAX_LEVEL = 18
SIMPLE_TERM = re.compile(r"^-?[\w.]+$")
FUNCTION_NAME = re.compile(r"^\w+(?=\()")
HASHED_NAME = re.compile(r"^\{([0-9a-f]{8})\}$")

# (mStat, mStatFormula) -> our variable. mStatFormula: 0 total, 1 base, 2 bonus.
# Only ids checked against known values; anything else is reported instead of guessed.
STAT_VARIABLES = {
    (0, 0): "ap", (0, 2): "bonus_ap",
    (1, 0): "armor", (1, 2): "bonus_armor",
    (2, 0): "ad", (2, 1): "base_ad", (2, 2): "bonus_ad",
    (4, 2): "bonus_attackspeed",  # Bel'Veth E, Aphelios Severum Q
    (6, 0): "mr", (6, 2): "bonus_mr",
    (7, 0): "movespeed", (7, 2): "bonus_movespeed",  # Hecarim P: 12–24 % bonus MS as AD; Janna P: 30 % as damage
    (8, 0): "crit_chance",  # Caitlyn's headshot, Ashe's passive
    (9, 0): "crit_damage", (9, 2): "bonus_crit_damage",  # Garen E: 1 + CritMod × (stat 9 − 1); Ashe P: × (1 + bonus)
    (12, 0): "max_hp", (12, 1): "base_hp", (12, 2): "bonus_hp",
    (13, 0): "current_hp",  # Kindred W: % of the target's current HP
    (14, 0): "current_hp_percent",  # Zac's costs: HPCost × max HP × stat 14 = 8 % current HP
    (15, 0): "missing_hp",  # Ekko W: % of the target's missing HP
    (16, 0): "missing_hp_percent",  # Olaf W: shield of 17.5 % missing HP = stat 16 × max HP × 0.175
    (18, 0): "life_steal",  # Ambessa R: heal 15–20 % (+ 50 % life steal)
    (29, 0): "lethality",  # Pyke R: 1.5 lethality
    (31, 2): "bonus_attack_range",  # Urgot W: "autonomous attack range scales with bonus attack range"
}
# Set on a stat part that reads the target's stat (Zed P, Aurora P: % of the target's max HP). Name still unknown.
TARGET_STAT_FLAG = "{a8cb9c14}"
# mStatFormula of a resource part -> our variable. Mana is the only resource the simulation knows; every champion
# with such a part in 16.21 uses mana, and the one other resource (Tryndamere's fury, mAbilityResource 4) is reported.
RESOURCE_VARIABLES = {0: "max_mana", 1: "base_mana", 2: "bonus_mana"}

# Part types CommunityDragon only knows as hashes. The names are guesses confirmed by their hash (see decisions).
GUESSED_PART_TYPES = (
    "SpellCalculationCalculationPart",
    "ByCharLevelNamedDataValuesInterpolationCalculationPart",
    "ByCharLevelNamedDataValueBreakpointsCalculationPart",
    "ByCharLevelNamedDataValuesCalculationPart",
    "ExternalNamedDataValueCalculationPart",
)
# Buff names CommunityDragon only knows as hashes, found among the strings of the champion's own data (16.21).
GUESSED_BUFF_NAMES = (
    "ApheliosPBuffAD", "ApheliosPBuffAP", "ApheliosPBuffAS", "AurelionSolPassive", "BelvethPassiveStacks",
    "BelvethVsJax_JaxQuestReward", "DravenPassiveStacks", "EliseR", "Feast", "GarenWPassive", "GwenP",
    "HeightenedLearning", "JaxRPassiveAttack", "JaxW", "KaisaQEvolved", "KarmaMantra", "KhazixEEvo", "KhazixQEvo",
    "KhazixREvo", "KhazixWEvo", "KindredMarkOfTheKindredStackCounter", "KSanteRConversionArmor",
    "KSanteRConversionHealth", "KSanteRConversionMagicResist", "LockeRStack", "NasusQStacks", "RellW_MountUp",
    "SennaPassiveStacks", "ShenSpiritShadowQuestReward", "ShyvanaPassive", "SmolderP", "SmolderQPassive",
    "SonaPassiveAccelerandoCount", "SwainSoulCounter", "ThreshPassiveSoulsGain", "UdyrEActivation",
    "ZedSpiritShadowQuestReward",
)
# Fields of the named level parts: Riot's numeric field -> the field naming the data value that holds the number.
NAMED_INTERPOLATION = {"mStartValue": "StartDataValue", "mEndValue": "EndDataValue"}
NAMED_LINEAR = {"mLevel1Value": "Level1DataValue", "mInitialBonusPerLevel": "BonusPerLevelDataValue"}
NAMED_BREAKPOINTS = {"mLevel1Value": "Level1DataValue", "mInitialBonusPerLevel": "InitialBonusPerLevelDataValue"}
NAMED_BREAKPOINT = {"mAdditionalBonusAtThisLevel": "AdditionalBonusAtThisLevelDataValue",
                    "mBonusPerLevelAtAndAfter": "BonusPerLevelAtAndAfterDataValue"}


# Spell fields kept under Riot's old field names: the fields to read, live first, and the index of rank 1 (mana lists
# have no rank 0). The old lists are stale copies Riot no longer updates (Darius Q in 26.21: cooldownTime 9–5,
# Cooldown and the wiki 9–4); they stay as a fallback.
SPELL_FIELDS = {"cooldownTime": (("Cooldown", "cooldownTime"), 1), "mana": (("manaValues", "mana"), 0)}
# Only read for real charges: many spells carry a leftover recharge time with no or a single ammo (Rengar, Irelia R: -1).
# Hidden ammo is the game's internals, not charges (Karthus Q: 2 hidden, 1 s each, which is its 1 s cooldown in the wiki).
AMMO_FIELDS = {"ammoRechargeTime": (("mAmmoRechargeTime",), 1), "maxAmmo": (("mMaxAmmo",), 1)}


RANGED_CALCULATION = "{e9a3c91d}"  # a GameCalculation with mRangedMultiplier, only in items


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
    if max(_spell_field(spell, ("mMaxAmmo",)) or [0]) >= 2 and not spell.get("mAmmoCountHiddenInUI"):
        for name, (sources, first_rank) in AMMO_FIELDS.items():
            _add(result, name, lambda: _rank_value(_spell_field(spell, sources), max_rank, first_rank))
    effect_amounts = [amount.get("value") for amount in spell.get("mEffectAmount") or []]
    riot_names = [value.get("name", "") for value in spell.get("DataValues") or []]
    _add_calculations(result, spell.get("mSpellCalculations") or {}, riot_names, effect_amounts, max_rank)
    return result


def item_values(record: dict) -> SpellValues:
    """An item's values: data values are single numbers, and its calculations are the spells' (Gunblade's
    ActiveDamage). The item's active and passives share them."""
    result = SpellValues()
    data_values = record.get("mDataValues") or []
    for data_value in data_values:
        _add(result, data_value.get("mName", ""), lambda: format_number(data_value.get("mValue", 0)))
    effect_amounts = [[amount] for amount in record.get("mEffectAmount") or []]
    riot_names = [value.get("mName", "") for value in data_values]
    _add_calculations(result, record.get("mItemCalculations") or {}, riot_names, effect_amounts, 0)
    return result


def rune_values(record: dict) -> SpellValues:
    """A rune's values: its script's named numbers (one each, no ranks) and calculations (Electrocute's TotalDamage).
    Other modes' numbers (mEffectAmountGameMode: ARAM, URF) stay in the raw data."""
    result = SpellValues()
    script = record.get("mScript", {}).get("mSpellScriptData", {})
    amounts = script.get("mEffectAmount") or {}
    for name, amount in amounts.items():
        _add(result, name, lambda: format_number(amount))
    _add_calculations(result, script.get("mCalculations") or {}, list(amounts), [], 0)
    return result


def _add_calculations(result: SpellValues, calculations: dict, riot_names: list[str],
                      effect_amounts: list[list[float] | None], max_rank: int) -> None:
    for index in sorted(_effect_indices(calculations)):
        _add(result, _effect_name(index), lambda: _rank_value(_effect_amount(effect_amounts, index), max_rank))
    data_values = DataValues(dict(result.values), riot_names)
    for name, calculation in calculations.items():
        _add(result, name, lambda: translate_calculation(data_values.resolve(calculation)))
        if readable := value_name(name):
            result.calculations[readable] = calculation


def _spell_field(spell: dict, sources: tuple[str, ...]) -> list[float]:
    for source in sources:
        value = spell.get(source)
        values = value.get("values") if isinstance(value, dict) else value
        if values:
            return values
    return []


def _effect_indices(node) -> set[int]:
    """Indices into mEffectAmount, Riot's old per-rank lists, that a calculation reads (Fizz Q: index 1)."""
    if isinstance(node, list):
        return set().union(*(_effect_indices(item) for item in node))
    if not isinstance(node, dict):
        return set()
    own = {node.get("mEffectIndex", 0)} if part_type(node) == "EffectValueCalculationPart" else set()
    return own.union(*(_effect_indices(value) for value in node.values()))


def _effect_name(index: int) -> str:
    # Riot's tooltips call mEffectAmount[0] @Effect1Amount@.
    return f"Effect{index}Amount"


def _effect_amount(amounts: list[list[float] | None], index: int) -> list[float]:
    if not 1 <= index <= len(amounts) or not (values := amounts[index - 1]):
        raise UnsupportedCalculation(f"refers to the missing effect amount {index}")
    return values


def _add(result: SpellValues, name: str, translate) -> None:
    if not (name := value_name(name)):
        return
    try:
        result.values[name] = translate()
    except UnsupportedCalculation as error:
        result.unsupported[name] = str(error)


def value_name(name: str) -> str | None:
    """The name formulas use: Riot's name, or h_<hash> where CommunityDragon only knows the hash ({097cda4f}).
    A name starting with a digit gets a leading underscore (Kled W's _4HitMaxHealthDamage)."""
    if name.isidentifier():
        return name
    if name[:1].isdigit() and f"_{name}".isidentifier():
        return f"_{name}"
    if hashed := HASHED_NAME.match(name):
        return f"h_{hashed[1]}"
    return None


def bin_field(record: dict, name: str, default=None):
    """A field by its name, or by its hash where CommunityDragon doesn't know the name yet ({726ee5cd} = arBaseModifiable)."""
    return record.get(name, record.get(f"{{{field_hash(name)}}}", default))


def name_hash(name: str) -> str:
    """Riot's hash of a name, also for names CommunityDragon only knows as the hash ({097cda4f})."""
    return hashed[1] if (hashed := HASHED_NAME.match(name)) else field_hash(name)


def field_hash(name: str) -> str:
    # FNV-1a (32 bit) of the lowercased name, the hash Riot's bin files use for field names.
    value = 0x811C9DC5
    for byte in name.lower().encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f"{value:08x}"


PART_TYPES_BY_HASH = {f"{{{field_hash(name)}}}": name for name in GUESSED_PART_TYPES}
BUFF_NAMES_BY_HASH = {f"{{{field_hash(name)}}}": name for name in GUESSED_BUFF_NAMES}


def part_type(part: dict) -> str | None:
    """The part's type by name, also where CommunityDragon only knows its hash ({4ce08984})."""
    return PART_TYPES_BY_HASH.get(part.get("__type"), part.get("__type"))


class DataValues:
    """A spell's data values as calculations refer to them. Riot finds them by the hash of the lowercased name,
    so Fiora Q's `BADRatio` reads her `bADRatio`; an exact name wins (Lissandra has `slowDuration` and `SlowDuration`)."""

    def __init__(self, values: dict[str, str], riot_names: list[str]) -> None:
        self.values = values
        self.names: dict[str, str] = {}
        for riot_name in riot_names:
            if (name := value_name(riot_name)) in values:
                self.names.setdefault(f"{{{name_hash(riot_name)}}}", name)
                self.names[riot_name] = name

    def name(self, riot_name: str) -> str:
        if name := self.names.get(riot_name) or self.names.get(f"{{{name_hash(riot_name)}}}"):
            return name
        raise UnsupportedCalculation(f"refers to the missing data value {riot_name}")

    def resolve(self, node):
        """References become the data value's own name. Riot's named level parts are its level parts with their
        numbers stored as data values (Gnar P, Akali P); replacing the names by the numbers lets them translate."""
        if isinstance(node, list):
            return [self.resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        node = {key: self.resolve(value) for key, value in node.items()}
        if "mDataValue" in node:
            node["mDataValue"] = self.name(node["mDataValue"])
        match part_type(node):
            case "ByCharLevelNamedDataValuesInterpolationCalculationPart":
                return {"__type": "ByCharLevelInterpolationCalculationPart"} | self._numbers(node, NAMED_INTERPOLATION)
            case "ByCharLevelNamedDataValuesCalculationPart":
                return {"__type": "ByCharLevelBreakpointsCalculationPart"} | self._numbers(node, NAMED_LINEAR)
            case "ByCharLevelNamedDataValueBreakpointsCalculationPart":
                breakpoints = [{"mLevel": point.get("level", 1)} | self._numbers(point, NAMED_BREAKPOINT, {"level"})
                               for point in bin_field(node, "DataValueBreakpoints", [])]
                return ({"__type": "ByCharLevelBreakpointsCalculationPart", "mBreakpoints": breakpoints}
                        | self._numbers(node, NAMED_BREAKPOINTS, {"DataValueBreakpoints"}))
        return node

    def _numbers(self, node: dict, fields: dict[str, str], other_fields: frozenset[str] = frozenset()) -> dict:
        names = (*fields.values(), *other_fields)
        known = {"__type"} | {key for name in names for key in (name, f"{{{field_hash(name)}}}")}
        if unknown := [key for key in node if key not in known]:
            raise UnsupportedCalculation(f"{part_type(node)} with unknown field {unknown[0]}")
        return {numeric: self._number(name) for numeric, field_name in fields.items()
                if (name := bin_field(node, field_name)) is not None}

    def _number(self, riot_name: str) -> float:
        try:
            return float(self.values[self.name(riot_name)])
        except ValueError:
            raise UnsupportedCalculation(f"level formula with {riot_name}, which differs by rank") from None


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
        case "GameCalculationConditional":
            formula = _conditional(calculation)
        case calculation_type if calculation_type == RANGED_CALCULATION:
            # Its name doesn't hash from any guess; its fields tell what it does (Titanic Hydra: 1 %, ranged 0.5 %).
            ranged = _part(calculation["mRangedMultiplier"])
            formula = f"{_factor(_sum(calculation.get('mFormulaParts', [])))} * ({ranged} if ranged > 0 else 1)"
        case other:
            raise UnsupportedCalculation(f"calculation type {other}")
    if "mMultiplier" in calculation:
        formula = f"{_factor(formula)} * {_factor(_part(calculation['mMultiplier']))}"
    return formula


def _conditional(calculation: dict) -> str:
    # The caster's buff or range type picks the calculation (Jax W while empowered, Runaan's for ranged);
    # without a default the other side is 0.
    if unknown := [name for name in calculation if name.startswith("{")]:
        raise UnsupportedCalculation(f"conditional calculation with unknown field {unknown[0]}")
    requirement = calculation.get("mConditionalCalculationRequirements", {})
    match requirement.get("__type"):
        case "HasBuffCastRequirement":
            condition = _buff_stacks(requirement)
        case "IsRangedCastRequirement":
            condition = "ranged"
        case "IsMeleeCastRequirement":  # Demolish
            condition = "1 - ranged"
        case other:
            raise UnsupportedCalculation(f"condition {other}")
    comparison = "== 0" if requirement.get("mInvertResult") else "> 0"
    default = calculation.get("mDefaultGameCalculation")
    return (f"{_name(calculation['mConditionalGameCalculation'])} if {condition} {comparison} "
            f"else {_name(default) if default else '0'}")


def _sum(parts: list[dict]) -> str:
    if not parts:
        return "0"
    return " + ".join(_part(part) for part in parts)


def _part(part: dict) -> str:
    match part_type(part):
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
        case "ByCharLevelFormulaCalculationPart":
            return _by_level(_level_list(part))
        case "EffectValueCalculationPart":
            return _effect_name(part.get("mEffectIndex", 0))
        case "SpellCalculationCalculationPart":  # another calculation of the same spell
            return _name(part["mSpellCalculationKey"])
        case "BuffCounterByNamedDataValueCalculationPart":
            return f"{_name(part['mDataValue'])} * {_buff_stacks(part)}"
        case "BuffCounterByCoefficientCalculationPart":
            if "mCoefficient" not in part:
                raise UnsupportedCalculation("buff counter without coefficient")
            return _scaled(part["mCoefficient"], _buff_stacks(part))
        case "PercentageOfBuffNameElapsed":  # Rell W ramps up over the first half of her mount buff
            return _scaled(part.get("Coefficient", 0), _buff_elapsed(part))
        case "CooldownMultiplierCalculationPart":  # Riot's haste factor, values with it are already hasted
            return COOLDOWN_MULTIPLIER
        case "ExternalNamedDataValueCalculationPart":
            spell = part.get("SourceObject", "").rsplit("/", 1)[-1]
            raise UnsupportedCalculation(f"refers to {part.get('DataValue')} of another spell ({spell})")
        case other:
            raise UnsupportedCalculation(f"part type {other}")


def _name(name: str) -> str:
    if not (translated := value_name(name)):
        raise UnsupportedCalculation(f"refers to the unreadable name {name}")
    return translated


def _stat(part: dict) -> str:
    key = (part.get("mStat", 0), part.get("mStatFormula", 0))
    if key not in STAT_VARIABLES:
        raise UnsupportedCalculation(f"stat {key[0]} with formula {key[1]}")
    # A hashed field could change whose stat is read, like the target flag did.
    unknown = [name for name in part if name.startswith("{") and name != TARGET_STAT_FLAG]
    if unknown:
        raise UnsupportedCalculation(f"stat part with unknown field {unknown[0]}")
    prefix = TARGET_PREFIX if part.get(TARGET_STAT_FLAG) else ""
    return prefix + STAT_VARIABLES[key]


def _buff_stacks(part: dict) -> str:
    # mIconKey and mScalingTagKey only style the tooltip. A hashed field could make it count another unit's buff.
    if unknown := [name for name in part if name.startswith("{")]:
        raise UnsupportedCalculation(f"buff counter with unknown field {unknown[0]}")
    return STACKS_PREFIX + _buff_name(part["mBuffName"])


def _buff_elapsed(part: dict) -> str:
    if unknown := [name for name in part if name.startswith("{")]:
        raise UnsupportedCalculation(f"elapsed buff part with unknown field {unknown[0]}")
    return ELAPSED_PREFIX + _buff_name(part["buffName"])


def _buff_name(buff: str) -> str:
    return _name(BUFF_NAMES_BY_HASH.get(buff, buff))


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


def _level_list(part: dict) -> list[float]:
    # A ready value per level, indexed by the level itself: entry 0 is unused (Lux P 30–200 = entries 1–18).
    values = part.get("values", [])
    if len(values) <= MAX_LEVEL:
        raise UnsupportedCalculation(f"level list with only {len(values)} entries")
    return [_clean(value) for value in values[1:MAX_LEVEL + 1]]


def _clean(value: float) -> float:
    return float(format_number(value))


def _by_level(values: list[float]) -> str:
    # The inputs are already cleaned, so more digits keep interpolated steps (0.3 -> 0.45 in 17 steps) exact.
    formatted = [f"{value:.12g}" for value in values]
    if len(set(formatted)) == 1:
        return formatted[0]
    return f"by_level({', '.join(formatted)})"
