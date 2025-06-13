from pydantic import BaseModel, Field, validator
from datetime import datetime
from src.server.models.pydanticid import PydanticObjectId


class NewPatch(BaseModel):
    patch: str
    timestamp: datetime = datetime.now()
    hotfix: datetime | None = None
    validated: bool = False

    cached_documents: int = 0

    champion_count: int = 0
    item_count: int = 0
    rune_count: int = 0
    summonerspell_count: int = 0
    total_count: int = 0

    change_count_champions: int = 0
    change_count_items: int = 0
    change_count_runes: int = 0
    change_count_summonerspells: int = 0
    change_count_total: int = 0


    @validator("total_count", pre=True, always=True)
    def set_total_count(cls, v, values):
        return values.get("champion_count") + values.get("item_count") + values.get("rune_count") + values.get("summonerspell_count")
    
    @validator("change_count_total", pre=True, always=True)
    def set_change_count(cls, v, values):
        return values.get("change_count_champions") + values.get("change_count_items") + values.get("change_count_runes") + values.get("change_count_summonerspells")


class Patch(NewPatch):
    id: PydanticObjectId = Field(..., alias="_id")
