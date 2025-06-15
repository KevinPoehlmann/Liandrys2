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

    loaded_champion_count: int = 0
    loaded_item_count: int = 0
    loaded_rune_count: int = 0
    loaded_summonerspell_count: int = 0
    loaded_total_count: int = 0

    changed_champion_count: int = 0
    changed_item_count: int = 0
    changed_rune_count: int = 0
    changed_summonerspell_count: int = 0
    changed_total_count: int = 0


    @validator("total_count", pre=True, always=True)
    def set_total_count(cls, v, values):
        return values.get("champion_count") + values.get("item_count") + values.get("rune_count") + values.get("summonerspell_count")
    
    @validator("changed_total_count", pre=True, always=True)
    def set_change_count(cls, v, values):
        return values.get("changed_champion_count") + values.get("changed_item_count") + values.get("changed_rune_count") + values.get("changed_summonerspell_count")
    
    @validator("loaded_total_count", pre=True, always=True)
    def set_loaded_total_count(cls, v, values):
        return values.get("loaded_champion_count") + values.get("loaded_item_count") + values.get("loaded_rune_count") + values.get("loaded_summonerspell_count")
    
    def update_totals(self) -> None:
        self.total_count = self.champion_count + self.item_count + self.rune_count + self.summonerspell_count
        self.loaded_total_count = self.loaded_champion_count + self.loaded_item_count + self.loaded_rune_count + self.loaded_summonerspell_count
        self.changed_total_count = self.changed_champion_count + self.changed_item_count + self.changed_rune_count + self.changed_summonerspell_count


class Patch(NewPatch):
    id: PydanticObjectId = Field(..., alias="_id")
