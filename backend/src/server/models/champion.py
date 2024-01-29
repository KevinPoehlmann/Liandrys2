from pydantic import BaseModel, Field, validator
from src.server.models.ability import ChampionAbility
from src.server.models.passive import ChampionPassive
from src.server.models.image import Image

from .pydanticid import PydanticObjectId

from src.server.models.dataenums import RangeType, ResourceType
from src.server.models.unit import Fighter





class NewChampion(Fighter):
    key: str
    name: str
    champion_id: str
    patch: str
    last_changed: str

    range_type: RangeType
    resource_type: ResourceType
    hp_per_lvl: int
    mana: float
    mana_per_lvl: float
    movementspeed: int
    armor_per_lvl: float
    mr_per_lvl: float
    attackrange: int
    hp_regen: float
    hp_regen_per_lvl: float
    mana_regen: float
    mana_regen_per_lvl: float
    ad_per_lvl: float
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

    ready_to_use: bool = False
    changes: list[str] = []

    image: Image

"""     @validator("ready_to_use", always=True)
    def set_ready_to_use(cls, v, values):
        return all((values["passive"].ready_to_use, values["q"].ready_to_use, values["w"].ready_to_use, values["e"].ready_to_use, values["r"].ready_to_use)) """



class Champion(NewChampion):
    id: PydanticObjectId = Field(..., alias="_id")



class ShortChampion(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    champion_id: str
    ready_to_use: bool
    image: Image



