from pydantic import BaseModel, Field, validator

from src.server.models.ability import Ability
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewSummonerspell(BaseModel):
    key: str
    name: str
    patch: str

    ability: Ability

    ready_to_use: bool = False
    image: Image

    """ @validator("ready_to_use", always=True)
    def set_ready_to_use(cls, v, values):
        return values["ability"].ready_to_use """


class Summonerspell(NewSummonerspell):
    id: PydanticObjectId = Field(..., alias="_id")


class ShortSummonerspell(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    ready_to_use: bool
    image: Image