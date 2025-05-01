from pydantic import BaseModel

from src.server.models.effect import Effect
from src.server.models.image import Image

from src.server.models.dataenums import (
    ActiveType,
    Counter
)




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

    @classmethod
    def parse_obj(cls, obj: dict) -> "Ability":
        if "effects" in obj:
            obj["effects"] = [
                Effect.parse_obj(ec)
                for ec in obj["effects"]
            ]
        return super().parse_obj(obj)



class ChampionAbility(Ability):
    maxrank: int
    image: Image


class ItemActive(Ability):
    type_: ActiveType
    unique: bool = False