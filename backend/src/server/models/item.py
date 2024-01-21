from pydantic import BaseModel, Field, validator

from src.server.models.ability import ItemActive
from src.server.models.passive import Passive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId

from src.server.models.dataenums import ItemClass, ItemStat, Map




class NewItem(BaseModel):
    item_id: str
    name: str
    patch: str
    gold: int
    into: list[str]
    from_: list[str]
    class_: ItemClass = None
    ready_to_use: bool = True
    stats: list[ItemStat] = []

    active: ItemActive = None
    passives: list[Passive] = []
    limitations: str = ""
    requirements: str = ""
    maps: list[Map] = []

    changes: list[str] = []

    image: Image

    @validator("ready_to_use", always=True)
    def set_ready_to_use(cls, v, values):
        result = False
        if "acttive" in values:
            result = values["acitve"].ready_to_use
        if "passives" in values:
            result = all((result, *[passive.ready_to_use for passive in values["passives"]]))
        return result
    
    
class Item(NewItem):
    id: PydanticObjectId = Field(..., alias="_id")


class ShortItem(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    item_id: str
    name: str
    ready_to_use: bool
    image: Image