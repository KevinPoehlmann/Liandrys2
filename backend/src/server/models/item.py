from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.server.models.ability import ItemActive
from src.server.models.passive import ItemPassive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId

from src.server.models.dataenums import ItemClass, ItemStat, Map, Stat




class NewItem(BaseModel):
    item_id: str
    name: str
    patch: str
    hotfix: datetime = None
    gold: int
    into: list[str]
    from_: list[str]
    class_: ItemClass = None
    validated: bool = True
    stats: dict[Stat, float] = {}
    masterwork: dict[Stat, float] = {}

    active: ItemActive = None
    passives: list[ItemPassive] = []
    limitations: str = ""
    requirements: str = ""
    maps: list[Map] = []

    changes: list[str] = []

    image: Image


    @classmethod
    def parse_obj(cls, obj: dict) -> "NewItem":
        if "passives" in obj:
            obj["passives"] = [
                ItemPassive.parse_obj(p) for p in obj["passives"]
            ]
        if obj.get("active") is not None:
            obj["active"] = ItemActive.parse_obj(obj["active"])
        return super().parse_obj(obj)
    
    
class Item(NewItem):
    id: PydanticObjectId = Field(..., alias="_id")


class ShortItem(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    item_id: str
    name: str
    gold: int
    validated: bool
    image: Image