from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.server.models.dataenums import ActionType
from src.server.models.rule import Buff

if TYPE_CHECKING:
    from src.server.simulation.character import Character


@dataclass
class BuffInstance:
    definition: Buff
    source: "Character"
    slot: ActionType
    stacks: int
    start: int
    end: int | None
    last_interval: int | None = None
    next_interval: int | None = None
    rate: float = 1.0  # how fast the duration runs out, see Buff.slowed_while
    snapshots: dict[int, float] = field(default_factory=dict)  # values of snapshot stat modifiers, by index
    cast: int | None = None  # the cast instance that applied it last; its interval ticks belong to that cast
