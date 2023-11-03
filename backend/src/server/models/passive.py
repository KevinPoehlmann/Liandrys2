from pydantic import BaseModel

from src.server.models.effect import Effect
from src.server.models.image import Image

from src.server.models.dataenums import (
    AbilityStat,
    DamageType,
    DamageSubType,
    Counter
)


class Passive(BaseModel):
    name: str
    description: str = ""
    effects: list[Effect] = []
    ability_stats: list[AbilityStat] = []
    damage_type: DamageType = None
    damage_sub_type: list[DamageSubType] = None
    counters: list[Counter] = []
    ready_to_use: bool = False
    changes: list[str] = []


class ChampionPassive(Passive):
    image: Image


class ItemPassive(Passive):
    unique: bool