from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_summonerspells_by_patch,
    fetch_summonerspell_by_id
)
from src.server.models.summonerspell import ShortSummonerspell, Summonerspell

router = APIRouter()



@router.get("/all/{patch}")
async def get_summonerspells(patch: str) -> list[ShortSummonerspell]:
    summonerspells = await fetch_summonerspells_by_patch(patch)
    if not summonerspells:
        raise HTTPException(status_code=404, detail=f"No summonerspells found for patch. {patch} !")
    return summonerspells


@router.get("/{summoner_id}")
async def get_item(summoner_id: str) -> Summonerspell:
    summoner = await fetch_summonerspell_by_id(summoner_id)
    if not summoner:
        raise HTTPException(status_code=404, detail=f"No summonerspell found with id: {summoner_id} !")
    return summoner