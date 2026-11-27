from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_short_summonerspells_by_patch,
    update_summonerspell
)
from src.server.models.summonerspell import ShortSummonerspell, Summonerspell
from src.server.models.enums import Map

from src.server.routes.helpers import get_required_summonerspell, reject_preview

router = APIRouter()
admin = APIRouter()



@router.get("/all/{patch}")
async def get_summonerspells(patch: str, map: Map | None = None) -> list[ShortSummonerspell]:
    summonerspells = await fetch_short_summonerspells_by_patch(patch, map)
    if not summonerspells:
        raise HTTPException(status_code=404, detail=f"No summonerspells found for patch. {patch} !")
    return summonerspells


@router.get("/{summoner_id}")
async def get_summonerspell(summoner_id: str) -> Summonerspell:
    return await get_required_summonerspell(summoner_id)


@admin.put("/")
async def put_summonerspell(summonerspell: Summonerspell) -> int:
    await reject_preview(summonerspell.patch)
    response = await update_summonerspell(summonerspell)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Summonerspell with ID: {summonerspell.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Summonerspell with ID: {summonerspell.id} !")
    return response.modified_count