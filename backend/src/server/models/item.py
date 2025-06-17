from pydantic import BaseModel, Field
from datetime import datetime
from typing import Self

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


    @classmethod
    def parse_obj(cls, obj: dict) -> Self:
        if "passives" in obj:
            obj["passives"] = [
                ItemPassive.parse_obj(p) for p in obj["passives"]
            ]
        if obj.get("active") is not None:
            obj["active"] = ItemActive.parse_obj(obj["active"])

        if "stats" in obj:
            obj["stats"] = {
                Stat.from_str(k): v for k, v in obj["stats"].items()
            }
        if "masterwork" in obj:
            obj["masterwork"] = {
                Stat.from_str(k): v for k, v in obj["masterwork"].items()
            }
        return super().parse_obj(obj)
    
    
class Item(NewItem):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


class ShortItem(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    item_id: str
    name: str
    gold: int
    validated: bool
    image: Image