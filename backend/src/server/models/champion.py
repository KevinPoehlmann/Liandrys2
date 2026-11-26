from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.server.models.change import Change
from src.server.models.ability import ChampionAbility, ExtraAbility, ShortChampionAbility
from src.server.models.passive import ChampionPassive
from src.server.models.image import Image

from .pydanticid import PydanticObjectId

from src.server.models.enums import AdaptiveType, RangeType, ResourceType




class NewChampion(BaseModel):
    key: str
    name: str
    champion_id: str
    patch: str
    last_changed: str | None = None  # the old wiki scraper's "last changed"; Module:ChampionData will fill it

    range_type: RangeType
    adaptive_type: AdaptiveType | None = None  # entered by hand until the loader scrapes it (Phase 4)
    resource_type: ResourceType
    hp: float
    hp_per_lvl: float
    ad: float
    ad_per_lvl: float
    mana: float
    mana_per_lvl: float
    movementspeed: float
    armor: float
    armor_per_lvl: float
    mr: float
    mr_per_lvl: float
    attackrange: float
    hp_regen: float
    hp_regen_per_lvl: float
    mana_regen: float
    mana_regen_per_lvl: float
    attackspeed: float
    attackspeed_ratio: float
    attackspeed_per_lvl: float
    crit_damage: float = 2.0  # Ashe 1.0; the default keeps documents from before the field loadable
    attack_windup: float
    windup_modifier: float
    missile_speed: float

    passive: ChampionPassive
    q: ChampionAbility
    w: ChampionAbility
    e: ChampionAbility
    r: ChampionAbility
    extra_abilities: list[ExtraAbility] = []

    validated: bool = False
    changes: list[Change] = []

    image: Image





class Champion(NewChampion):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True



class WikiTemplate(BaseModel):
    title: str  # "Template:Data_Veigar/Baleful_Strike"
    revision_id: int  # a newer revision on the wiki means the text changed
    text: str


class RawChampion(BaseModel):
    """Everything the loader downloaded for one champion and patch, unchanged. Never read by the user API."""
    champion_id: str
    patch: str
    build: str  # CommunityDragon's content version, "16.23.8406595+branch.releases-16-23.content.release"
    fetched_at: datetime
    cdragon: dict  # the whole <champion>.bin.json; untyped on purpose, Riot adds fields every patch
    strings: dict[str, str] = {}  # this champion's entries from lol.stringtable.json (tooltips)
    wiki: dict[str, WikiTemplate] = {}  # per template title
    champion_data: dict = {}  # the champion's entry in the wiki's Module:ChampionData/data (cross-check, last change)



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



