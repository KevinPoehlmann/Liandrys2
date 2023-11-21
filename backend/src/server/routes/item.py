from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_items_by_patch,
)
from src.server.models.item import ShortItem

router = APIRouter()



@router.get("/{patch}")
async def get_items(patch: str) -> list[ShortItem]:
    items = await fetch_items_by_patch(patch)
    if not items:
        raise HTTPException(status_code=404, detail=f"No items found for patch. {patch} !")
    return items