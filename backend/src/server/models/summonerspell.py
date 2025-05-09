from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.server.models.ability import Ability
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewSummonerspell(BaseModel):
    key: str
    name: str
    patch: str
    hotfix: datetime = None

    ability: Ability

    validated: bool = False
    changes: list[str] = []
    image: Image

    @classmethod
    def parse_obj(cls, obj: dict) -> "NewSummonerspell":
        if obj.get("ability") is not None:
            obj["ability"] = Ability.parse_obj(obj["ability"])
        return super().parse_obj(obj)


class Summonerspell(NewSummonerspell):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


class ShortSummonerspell(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    validated: bool
    image: Image