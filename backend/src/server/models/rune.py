from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.server.models.passive import Passive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewRune(BaseModel):
    rune_id: int
    name: str
    patch: str
    hotfix: datetime = None
    tree: str
    tree_id: int
    row: int
    passive: Passive
    validated: bool = False
    image: Image = None

    @classmethod
    def parse_obj(cls, obj: dict) -> "NewRune":
        if obj.get("passive") is not None:
            obj["passive"] = Passive.parse_obj(obj["passive"])
        return super().parse_obj(obj)
    

class Rune(NewRune):
    id: PydanticObjectId = Field(..., alias="_id")


class ShortRune(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    rune_id: int
    name: str
    validated: bool
    image: Image