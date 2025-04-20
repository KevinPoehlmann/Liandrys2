from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.server.models.ability import ItemActive
from src.server.models.passive import Passive
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
    passives: list[Passive] = []
    limitations: str = ""
    requirements: str = ""
    maps: list[Map] = []

    changes: list[str] = []

    image: Image

    
    
class Item(NewItem):
    id: PydanticObjectId = Field(..., alias="_id")


class ShortItem(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    item_id: str
    name: str
    gold: int
    validated: bool
    image: Image