import logging

from datetime import datetime
from fastapi import APIRouter, HTTPException




from src.server.database import (
    fetch_short_champions_by_patch,
    fetch_champion_by_id,
    update_champion
)
from src.server.models.champion import ShortChampion, Champion
from src.server.models.enums import RangeType, ResourceType

from src.server.routes.helpers import get_required_champion

debug_logger = logging.getLogger("liandrys.debug")

router = APIRouter()
admin = APIRouter()


@router.get("/all/{patch}")
async def get_champions(patch: str, hotfix: datetime | None = None) -> list[ShortChampion]:
    response = await fetch_short_champions_by_patch(patch, hotfix)
    if not response:
        raise HTTPException(status_code=404, detail=f"No champions found for patch. {patch} !")
    return response


@router.get("/rangetype/")
async def get_rangeType() -> list[str]:
    response = [e.value for e in RangeType]
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went horribly wrong!")
    return response


@router.get("/resourcetype/")
async def get_resourceType() -> list[str]:
    response = [e.value for e in ResourceType]
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went horribly wrong!")
    return response


@router.get("/{id_}")
async def get_champion_by_id(id_: str) -> Champion:
    return await get_required_champion(id_)


@admin.put("/")
async def put_champion(champion: Champion) -> Champion:
    response = await update_champion(champion)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Champion with ID: {champion.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Champion with ID: {champion.id} !")
    return champion





#------------------Enums--------------------------------------------------