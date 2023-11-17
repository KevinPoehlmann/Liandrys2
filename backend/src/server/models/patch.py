from pydantic import BaseModel, Field, validator
from datetime import datetime
from src.server.models.pydanticid import PydanticObjectId


class NewPatch(BaseModel):
    patch: str                          #TODO unique?
    timestamp: datetime = datetime.now()
    hotfix: datetime | None = None
    ready_to_use: bool = False
    champion_count: int
    item_count: int
    rune_count: int
    summonerspell_count: int
    document_count: int = 0
    loaded_documents: int = 0

    @validator("document_count", pre=True, always=True)
    def set_document_count(cls, v, values):
        return values.get("champion_count") + values.get("item_count") + values.get("rune_count") + values.get("summonerspell_count")


class Patch(NewPatch):
    id: PydanticObjectId = Field(..., alias="_id")
