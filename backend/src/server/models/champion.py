from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.server.models.ability import ChampionAbility, ShortChampionAbility
from src.server.models.passive import ChampionPassive
from src.server.models.image import Image

from .pydanticid import PydanticObjectId

from src.server.models.dataenums import RangeType, ResourceType




class NewChampion(BaseModel):
    key: str
    name: str
    champion_id: str
    patch: str
    hotfix: datetime = None
    last_changed: str

    range_type: RangeType
    resource_type: ResourceType
    hp: float
    hp_per_lvl: int
    ad: float
    ad_per_lvl: float
    mana: float
    mana_per_lvl: float
    movementspeed: int
    armor: int
    armor_per_lvl: float
    mr: float
    mr_per_lvl: float
    attackrange: int
    hp_regen: float
    hp_regen_per_lvl: float
    mana_regen: float
    mana_regen_per_lvl: float
    attackspeed: float
    attackspeed_ratio: float
    attackspeed_per_lvl: float
    attack_windup: float
    windup_modifier: float
    missile_speed: int

    passive: ChampionPassive
    q: ChampionAbility
    w: ChampionAbility
    e: ChampionAbility
    r: ChampionAbility

    validated: bool = False
    changes: list[str] = []

    image: Image


    @classmethod
    def parse_obj(cls, obj: dict) -> "Champion":
        if "passive" in obj:
            obj["passive"] = ChampionPassive.parse_obj(obj["passive"])
        for spell in ("q", "w", "e", "r"):
            if spell in obj:
                obj[spell] = ChampionAbility.parse_obj(obj[spell])
        return super().parse_obj(obj)



class Champion(NewChampion):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True



class ShortChampion(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    champion_id: str
    q: ShortChampionAbility
    w: ShortChampionAbility
    e: ShortChampionAbility
    r: ShortChampionAbility
    validated: bool
    image: Image



