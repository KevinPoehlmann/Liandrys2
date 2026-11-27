from datetime import datetime

from pydantic import BaseModel, Field, root_validator

from src.server.models.change import Change
from src.server.models.ability import ItemActive
from src.server.models.passive import ItemPassive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId

from src.server.models.enums import ItemClass, Map, Stat




class NewItem(BaseModel):
    item_id: str
    name: str
    patch: str
    gold: int
    into: list[str]
    from_: list[str]
    class_: ItemClass = ItemClass.NONE
    validated: bool = True
    stats: dict[Stat, float] = {}
    masterwork: dict[Stat, float] = {}

    active: ItemActive | None = None
    passives: list[ItemPassive] = []
    limitations: str = ""
    requirements: str = ""
    maps: list[Map] = []
    values: dict[str, str] = {}  # loader-owned named values, shared by the active and the passives (SpellbladeDamage)
    tooltip: str = ""  # loader-owned, Riot's text with @Name@ placeholders for the values

    changes: list[Change] = []

    image: Image


    
    
class Item(NewItem):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


class ShortItem(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    item_id: str
    name: str
    gold: int
    class_: ItemClass
    active: bool
    validated: bool
    maps: list[Map]
    image: Image

    @root_validator(pre=True)
    def convert_active_to_bool(cls, values):
        values["active"] = bool(values.get("active"))
        return values


class RawItem(BaseModel):
    """Everything the loader downloaded for one item and patch, unchanged. Never read by the user API."""
    item_id: str
    patch: str
    build: str
    fetched_at: datetime
    cdragon: dict  # the item's record in items.cdtb.bin.json; untyped on purpose like RawChampion.cdragon
    active: dict | None = None  # the record of the spell it names (spellName), often a dummy; cast time and range
    strings: dict[str, str] = {}  # its entries from lol.stringtable.json (name, tooltips)
    item_data: dict = {}  # its entry in the wiki's Module:ItemData/data, references resolved (class, effects)
