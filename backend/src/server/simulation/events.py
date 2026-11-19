from dataclasses import dataclass

from src.server.models.dataenums import ActionType, Actor
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


@dataclass
class BuffTick:
    bearer: Actor
    buff: str
    tick: int


@dataclass
class BuffEnd:
    bearer: Actor
    buff: str
    end: int
