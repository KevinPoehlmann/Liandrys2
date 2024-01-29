from pydantic import BaseModel, Field, validator

from src.server.models.passive import Passive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewRune(BaseModel):
    rune_id: int
    name: str
    patch: str
    tree: str
    tree_id: int
    row: int
    passive: Passive
    ready_to_use: bool = False
    image: Image = None

    """ @validator("ready_to_use", always=True)
    def set_ready_to_use(cls, v, values):
       return values["passive"].ready_to_use """
    

class Rune(NewRune):
    id: PydanticObjectId = Field(..., alias="_id")


class ShortRune(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    rune_id: int
    name: str
    ready_to_use: bool
    image: Image