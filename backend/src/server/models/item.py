from pydantic import BaseModel, Field, root_validator
from datetime import datetime

from src.server.models.ability import ItemActive
from src.server.models.passive import ItemPassive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId

from src.server.models.dataenums import ItemClass, Map, Stat




class NewItem(BaseModel):
    item_id: str
    name: str
    patch: str
    hotfix: datetime | None = None
    gold: int
    into: list[str]
    from_: list[str]
    class_: ItemClass = ItemClass.ERROR
    validated: bool = True
    stats: dict[Stat, float] = {}
    masterwork: dict[Stat, float] = {}

    active: ItemActive | None = None
    passives: list[ItemPassive] = []
    limitations: str = ""
    requirements: str = ""
    maps: list[Map] = []

    changes: list[str] = []

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