from datetime import datetime
from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_summonerspells_by_patch,
    fetch_summonerspell_by_id,
    update_summonerspell
)
from src.server.models.summonerspell import ShortSummonerspell, Summonerspell

router = APIRouter()



@router.get("/all/{patch}")
async def get_summonerspells(patch: str, hotfix: datetime = None) -> list[ShortSummonerspell]:
    summonerspells = await fetch_summonerspells_by_patch(patch, hotfix)
    if not summonerspells:
        raise HTTPException(status_code=404, detail=f"No summonerspells found for patch. {patch} !")
    return summonerspells


@router.get("/{summoner_id}")
async def get_summonerspell(summoner_id: str) -> Summonerspell:
    summoner = await fetch_summonerspell_by_id(summoner_id)
    if not summoner:
        raise HTTPException(status_code=404, detail=f"No summonerspell found with id: {summoner_id} !")
    return summoner


@router.put("/")
async def put_summonerspell(summonerspell: Summonerspell) -> int:
    response = await update_summonerspell(summonerspell)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Summonerspell with ID: {summonerspell.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Summonerspell with ID: {summonerspell.id} !")
    return response.modified_count