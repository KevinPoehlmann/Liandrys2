from pydantic import BaseModel

from src.server.models.enums import ActionType, Actor, CostResource, DamageSubType, DamageType, EffectType, OriginKind


class Origin(BaseModel):
    """Where a result comes from, for the damage breakdown: champion parts by slot, everything else by name."""
    kind: OriginKind
    name: str  # "Q", "passive", "BA", "Ignite", "Sheen", "health"
    buff: str | None = None  # "hemorrhage", "tibbers_aura"

    class Config:
        frozen = True  # hashable, so results can be grouped by origin


class EffectResult(BaseModel):
    source: ActionType
    actor: Actor
    target: Actor
    type_: EffectType
    value: float
    raw: float = 0
    mitigated: float = 0
    overheal: float = 0
    damage_sub_type: DamageSubType | None = None
    resource: CostResource | None = None  # for costs and regeneration
    origin: Origin | None = None
    dmg_tags: list[DamageType] = []  # for damage: all its tags (Conqueror and Electrocute filter by them)
    cast: int | None = None  # the cast instance (attack, cast, item active) it belongs to


class TickEvent(BaseModel):
    tick: int
    result: list[EffectResult]
