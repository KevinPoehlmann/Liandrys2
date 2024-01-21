from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_items_by_patch,
    fetch_item_by_id
)
from src.server.models.item import ShortItem, Item

router = APIRouter()



@router.get("/all/{patch}")
async def get_items(patch: str) -> list[ShortItem]:
    items = await fetch_items_by_patch(patch)
    if not items:
        raise HTTPException(status_code=404, detail=f"No items found for patch: {patch} !")
    return items


@router.get("/{item_id}")
async def get_item(item_id: str) -> Item:
    item = await fetch_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"No item found with id: {item_id} !")
    return item