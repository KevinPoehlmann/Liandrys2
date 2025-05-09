from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse



from src.server.database import (
    fetch_items_by_patch,
    fetch_item_by_id,
    update_item
)
from src.server.models.item import ShortItem, Item
from src.server.models.dataenums import ItemClass, Map

from src.server.utils.request_parsing import parse_from_request


router = APIRouter()



@router.get("/all/{patch}")
async def get_items(patch: str, hotfix: datetime | None = None) -> list[ShortItem]:
    items = await fetch_items_by_patch(patch, hotfix)
    if not items:
        raise HTTPException(status_code=404, detail=f"No items found for patch: {patch} !")
    return items


@router.get("/{item_id}")
async def get_item(item_id: str) -> Item:
    response = await fetch_item_by_id(item_id)
    if not response:
        raise HTTPException(status_code=404, detail=f"No item found with id: {item_id} !")
    return JSONResponse(content=response.dict())


@router.put("/")
async def put_item(request: Request) -> int:
    item = await parse_from_request(request, Item)
    response = await update_item(item)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Item with ID: {item.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Item with ID: {item.id} !")
    return response.modified_count




#------------------Enums--------------------------------------------------

@router.get("/itemclass/")
async def get_item_class() -> list[ItemClass]:
    response = [e.value for e in ItemClass]
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went horribly wrong!")
    return response


@router.get("/map/")
async def get_map() -> list[Map]:
    response = [e.value for e in Map]
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went horribly wrong!")
    return response