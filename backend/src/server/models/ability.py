from pydantic import BaseModel

from src.server.models.effect import Effect
from src.server.models.image import Image

from src.server.models.dataenums import (
    AbilityCosts,
    AbilityStat,
    ActiveType,
    Counter,
    DamageType,
    DamageSubType,
    Table
)




#TODO add aggro?
class Ability(BaseModel):
    name: str
    description: str = ""
    effects: list[Effect] = []
    cast_time: float = 0
    cooldown: Table = None
    costs: AbilityCosts = None
    ability_stats: list[AbilityStat] = []
    damage_type: DamageType = None
    damage_sub_type: list[DamageSubType] = None
    counters: list[Counter] = []
    ready_to_use: bool = False
    changes: list[str] = []

    class Config:  
        use_enum_values = True



class ChampionAbility(Ability):
    maxrank: int
    image: Image


class ItemActive(Ability):
    type_: ActiveType
    unique: bool = False