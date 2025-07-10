from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Self

from src.server.models.passive import Passive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewRune(BaseModel):
    rune_id: int
    name: str
    patch: str
    hotfix: datetime | None = None
    tree: str
    tree_id: int
    row: int
    slot: int
    passive: Passive
    validated: bool = False
    changes: list[str] = []
    image: Image | None = None

    @classmethod
    def parse_obj(cls, obj: dict) -> Self:
        if obj.get("passive") is not None:
            obj["passive"] = Passive.parse_obj(obj["passive"])
        return super().parse_obj(obj)
    

class Rune(NewRune):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


class ShortRune(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    rune_id: int
    name: str
    tree: str
    tree_id: int
    row: int
    slot: int
    validated: bool
    image: Image



RUNE_TREES = {
    8000: {
        "name": "Precision",
        "image": "/images/rune/7201_Precision.png"
    },
    8100: {
        "name": "Domination",
        "image": "/images/rune/7200_Domination.png"
    },
    8200: {
        "name": "Sorcery",
        "image": "/images/rune/7202_Sorcery.png"
    },
    8300: {
        "name": "Inspiration",
        "image": "/images/rune/7203_Whimsy.png"
    },
    8400: {
        "name": "Resolve",
        "image": "/images/rune/7204_Resolve.png"
    }
}