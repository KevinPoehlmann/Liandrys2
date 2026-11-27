from datetime import datetime

from pydantic import BaseModel, Field

from src.server.models.change import Change
from src.server.models.ability import Ability
from src.server.models.champion import WikiTemplate
from src.server.models.enums import Map
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewSummonerspell(BaseModel):
    key: str
    name: str
    patch: str

    ability: Ability

    validated: bool = False
    maps: list[Map] = []
    changes: list[Change] = []
    image: Image



class Summonerspell(NewSummonerspell):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


class ShortSummonerspell(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    validated: bool
    maps: list[Map]
    image: Image


class RawSummonerspell(BaseModel):
    """Everything the loader downloaded for one summoner spell and patch, unchanged. Never read by the user API."""
    key: str  # Data Dragon's id, which is CommunityDragon's script name ("SummonerDot")
    patch: str
    build: str
    fetched_at: datetime
    cdragon: dict  # the spell's record in shared.cdtb.bin.json; untyped on purpose like RawChampion.cdragon
    strings: dict[str, str] = {}  # its entries from lol.stringtable.json (name, tooltip)
    spell_data: dict = {}  # its entry in the wiki's Module:SpellData/data (cross-check)
    wiki: WikiTemplate | None = None  # the wiki article's wikitext, for its notes
