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
    effects: list[Effect] = []
    cast_time: float = 0
    cooldown: str = "0"
    costs: str = "0"
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