from pydantic import BaseModel

from src.server.models.effect import Effect
from src.server.models.image import Image

from src.server.models.dataenums import (
    ActiveType,
    Counter
)




#TODO add aggro?
class Ability(BaseModel):
    name: str
    description: str = ""
    cost: str = "0"
    cooldown: str = "0"
    cast_time: str = "0"
    recharge: str = "0"
    effects: list[Effect] = []
    raw_stats: dict[str, str] = {}
    changes: list[str] = []
    validated: bool = False

    class Config:  
        use_enum_values = True



class ChampionAbility(Ability):
    maxrank: int
    image: Image


class ItemActive(Ability):
    type_: ActiveType
    unique: bool = False