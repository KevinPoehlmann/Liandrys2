from dataclasses import dataclass, field

from src.server.models.enums import ActionType, Actor
from src.server.models.rule import Rule


@dataclass
class RuleEvent:
    """The actions of one rule, landing together on a tick."""
    rule: Rule
    slot: ActionType
    owner: Actor
    target: Actor
    bearer: Actor | None = None
    buff: str | None = None
    crit: bool | None = None  # an attack's crit choice, shared by its on-hit rules
    cast: int | None = None  # the cast instance; everything that follows from a cast shares it (on-hit, DoT ticks)
    damage_factor: float = 1  # on-hit and on-attack rules of an Attack action (Purge: 0.5)
    values: dict[str, float] = field(default_factory=dict)  # `damage`/`health_damage` in damage-triggered rules


@dataclass
class BuffTick:
    bearer: Actor
    buff: str
    tick: int


@dataclass
class PetAttackDue:
    """The pet attacks as soon as it can, starting at this tick."""
    pet: Actor


@dataclass
class PetExpire:
    pet: Actor


@dataclass
class BuffEnd:
    bearer: Actor
    buff: str
    end: int


@dataclass
class ActionEffect:
    """What an action returns: the tick its cast time ends and the rule events it starts."""
    tick: int
    rule_events: list[RuleEvent] = field(default_factory=list)
    windup_cancel: set = field(default_factory=set)
