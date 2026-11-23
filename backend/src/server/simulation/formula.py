import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from src.server.models.enums import ActionType, Stat
from src.server.simulation.exceptions import SimulationError


# Top laners can reach level 20 on newer patches, so tables always cover 20 levels.
MAX_LEVEL = 20
TARGET_PREFIX = "target_"
OWNER_PREFIX = "owner_"
STACKS_PREFIX = "stacks_"


class FormulaError(SimulationError):
    pass


class StatSource(Protocol):
    level: int
    current_hp: float
    is_champion: bool
    is_ranged: bool

    def get_stat(self, stat: Stat) -> float: ...
    def get_base_stat(self, stat: Stat) -> float: ...
    def get_rank(self, slot: ActionType) -> int: ...
    def get_buff_stacks(self, buff: str) -> int: ...
    def get_cooldown(self, slot: ActionType) -> float: ...


def _total(stat: Stat) -> Callable[[StatSource], float]:
    return lambda source: source.get_stat(stat)

def _base(stat: Stat) -> Callable[[StatSource], float]:
    return lambda source: source.get_base_stat(stat)

# Bonus is everything that is not base: items, runes and buffs alike.
def _bonus(stat: Stat) -> Callable[[StatSource], float]:
    return lambda source: source.get_stat(stat) - source.get_base_stat(stat)

def _missing_hp(source: StatSource) -> float:
    return source.get_stat(Stat.HP) - source.current_hp

def _missing_hp_percent(source: StatSource) -> float:
    return _missing_hp(source) / source.get_stat(Stat.HP)


STAT_VARIABLES: dict[str, Callable[[StatSource], float]] = {
    "ad": _total(Stat.AD), "base_ad": _base(Stat.AD), "bonus_ad": _bonus(Stat.AD),
    "ap": _total(Stat.AP), "bonus_ap": _bonus(Stat.AP),
    "armor": _total(Stat.ARMOR), "bonus_armor": _bonus(Stat.ARMOR),
    "mr": _total(Stat.MR), "bonus_mr": _bonus(Stat.MR),
    "max_hp": _total(Stat.HP), "bonus_hp": _bonus(Stat.HP),
    "current_hp": lambda source: source.current_hp,
    "missing_hp": _missing_hp,
    "missing_hp_percent": _missing_hp_percent,
    "max_mana": _total(Stat.MANA),
    "attackspeed": _total(Stat.ATTACKSPEED_P),
    "lethality": _total(Stat.LETHALITY),
    "armor_pen_percent": _total(Stat.ARMOR_PEN_P),
    "magic_pen": _total(Stat.MAGIC_PEN),
    "magic_pen_percent": _total(Stat.MAGIC_PEN_P),
    "ability_haste": _total(Stat.ABILITY_HASTE),
    "crit_chance": _total(Stat.CRIT_P),
    "movespeed": _total(Stat.MOVESPEED),
    "is_champion": lambda source: 1 if source.is_champion else 0,  # 0 for pets (Thornmail's Grievous Wounds)
    "ranged": lambda source: 1 if source.is_ranged else 0,  # melee/ranged values (Mist's Edge)
}

RANK_VARIABLES = {f"rank_{slot.value.lower()}": slot for slot in (ActionType.Q, ActionType.W, ActionType.E, ActionType.R)}


@dataclass
class FormulaContext:
    source: StatSource
    target: StatSource | None = None
    owner: StatSource | None = None  # the summoner, inside pet formulas
    rank: int = 0
    max_rank: int = 0
    stacks: int = 0
    elapsed: float = 0.0
    slot: ActionType | None = None
    scenario: dict[str, float] = field(default_factory=dict)
    event_values: dict[str, float] = field(default_factory=dict)
    distance: float = 0  # between the two champions, set by the simulation (Javelin Toss)


class FormulaNamespace(Mapping[str, float]):
    """Resolves variables lazily, so a formula only computes the stats it uses."""

    def __init__(self, context: FormulaContext) -> None:
        self._context = context
        self._fixed = self._fixed_values(context)

    @staticmethod
    def _fixed_values(context: FormulaContext) -> dict[str, float]:
        ranks = {name: context.source.get_rank(slot) for name, slot in RANK_VARIABLES.items()}
        return {
            "level": context.source.level,
            "rank": context.rank,
            "stacks": context.stacks,
            "elapsed": context.elapsed,
            "distance": context.distance,
        } | ranks | context.scenario | context.event_values

    def __getitem__(self, name: str) -> float:
        if name in self._fixed:
            return self._fixed[name]
        if name == "cooldown":
            return self._cooldown()
        if name.startswith(TARGET_PREFIX):
            return self._read_other(self._context.target, TARGET_PREFIX, name)
        if name.startswith(OWNER_PREFIX):
            return self._read_other(self._context.owner, OWNER_PREFIX, name)
        return self._read(self._context.source, name)

    def _cooldown(self) -> float:
        # Seconds after haste and cooldown reduction, e.g. Vladimir's Crimson Rush fills with Transfusion's cooldown.
        if self._context.slot is None:
            raise KeyError("cooldown")
        return self._context.source.get_cooldown(self._context.slot)

    def _read_other(self, actor: StatSource | None, prefix: str, name: str) -> float:
        if actor is None:
            raise KeyError(name)
        return self._read(actor, name.removeprefix(prefix))

    @staticmethod
    def _read(actor: StatSource, name: str) -> float:
        if name.startswith(STACKS_PREFIX):
            return actor.get_buff_stacks(name.removeprefix(STACKS_PREFIX))
        if name in STAT_VARIABLES:
            return STAT_VARIABLES[name](actor)
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        return iter(self._fixed)

    def __len__(self) -> int:
        return len(self._fixed)


def _by_rank(context: FormulaContext) -> Callable[..., float]:
    def by_rank(*values: float) -> float:
        if context.max_rank == 0:
            raise FormulaError("by_rank is only available in abilities")
        if len(values) != context.max_rank:
            raise FormulaError(f"by_rank needs {context.max_rank} values (one per rank), got {len(values)}")
        if not 1 <= context.rank <= context.max_rank:
            raise FormulaError(f"by_rank used at rank {context.rank}, the ability is not learned")
        return values[context.rank - 1]
    return by_rank


def _by_level(context: FormulaContext) -> Callable[..., float]:
    def by_level(*values: float) -> float:
        if len(values) != MAX_LEVEL:
            raise FormulaError(f"by_level needs {MAX_LEVEL} values (one per level), got {len(values)}")
        return values[context.source.level - 1]
    return by_level


def evaluate_formula(formula: str, context: FormulaContext) -> float:
    # An empty __builtins__ keeps eval away from open/import; only these functions are callable.
    functions = {
        "__builtins__": {},
        "min": min,
        "max": max,
        "floor": math.floor,
        "inf": math.inf,
        "by_rank": _by_rank(context),
        "by_level": _by_level(context),
    }
    try:
        return float(eval(formula, functions, FormulaNamespace(context)))
    except FormulaError as error:
        raise FormulaError(f"{error.message} in formula '{formula}'") from error
    except NameError as error:
        raise FormulaError(f"Unknown variable in formula '{formula}': {error}") from error
    except (SyntaxError, TypeError, ZeroDivisionError) as error:
        raise FormulaError(f"Invalid formula '{formula}': {error}") from error
