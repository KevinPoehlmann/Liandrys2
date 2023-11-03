from pydantic import BaseModel, Field
from src.server.models.ability import ChampionAbility
from src.server.models.passive import ChampionPassive
from src.server.models.image import Image

from .pydanticid import PydanticObjectId

from src.server.models.dataenums import RangeType, ResourceType






class NewChampion(BaseModel):
    key: str
    name: str
    champion_id: str
    ready_to_use: bool = False
    patch: str
    last_changed: str

    range_type: RangeType
    resource_type: ResourceType
    hp: float
    hp_per_lvl: int
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
    ad: float
    ad_per_lvl: float
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

    changes: list[str] = []

    image: Image



class Champion(NewChampion):
    id: PydanticObjectId = Field(..., alias="_id")



class ShortChampion(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    champion_id: str
    ready_to_use: bool
    image: Image



