from pydantic import BaseModel, Field
from datetime import datetime
from src.server.models.pydanticid import PydanticObjectId


class NewPatch(BaseModel):
    patch: str                          #TODO unique?
    timestamp: datetime = datetime.now()
    hotfix: datetime = None
    ready_to_use: bool = False
    champion_count: int
    item_count: int
    rune_count: int
    summonerspell_count: int
    document_count: int
    loaded_documents: int = 0


class Patch(NewPatch):
    id: PydanticObjectId = Field(..., alias="_id")
