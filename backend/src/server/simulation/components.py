from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel

from src.server.models.enums import ActionType, Actor, CostResource, DamageSubType, DamageType, EffectType, StatusType
from src.server.models.result import Origin


class EffectProperties(BaseModel):
    pass


class ProcessedDamageProperties(EffectProperties):
    value: float
    flat_pen: float
    percent_pen: float
    dmg_type: DamageType
    dmg_sub_type: DamageSubType = cast(DamageSubType, DamageSubType.PHYSIC)
    vamp: float = 0
    life_steal: float = 0
    omnivamp: float = 0
    tags: list[DamageType] = []
    execute: bool = False  # takes all remaining health, past shields (The Collector)


class ProcessedHealProperties(EffectProperties):
    value: float


class ProcessedShieldProperties(EffectProperties):
    value: float
    duration: int
    dmg_sub_type: DamageSubType = cast(DamageSubType, DamageSubType.TRUE)


class ProcessedStatusProperties(EffectProperties):
    type_: StatusType
    duration: int
    strength: float = 0.0


class ProcessedCostProperties(EffectProperties):
    resource: CostResource
    value: float


@dataclass
class QueueComponent():
    source: ActionType
    actor: Actor
    target: Actor
    type_: EffectType
    props: EffectProperties | None = None
    origin: Origin | None = None
    cast: int | None = None  # the cast instance it belongs to
