import logging

from fastapi import APIRouter, HTTPException
from pymongo.results import UpdateResult




from src.server.database import (
    fetch_champions_by_patch,
    fetch_champion_by_id,
    update_champion
)
from src.server.models.champion import ShortChampion, Champion

router = APIRouter()
debugger = logging.getLogger("debugger")



@router.get("/all/{patch}")
async def get_champions(patch: str) -> list[ShortChampion]:
    response = await fetch_champions_by_patch(patch)
    if not response:
        raise HTTPException(status_code=404, detail=f"No champions found for patch. {patch} !")
    return response


@router.get("/{id_}")
async def get_champion_by_id(id_: str) -> Champion:
    response = await fetch_champion_by_id(id_)
    if not response:
        raise HTTPException(status_code=404, detail=f"Could not find Champion with ID: {id_} !")
    return response


@router.put("/")
async def put_champion(champion: Champion) -> int:
    debugger.info(champion.dict())
    response = await update_champion(champion)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Champion with ID: {champion.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Champion with ID: {champion.id} !")
    return response.modified_count