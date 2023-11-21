from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_summonerspells_by_patch,
)
from src.server.models.summonerspell import ShortSummonerspell

router = APIRouter()



@router.get("/{patch}")
async def get_summonerspells(patch: str) -> list[ShortSummonerspell]:
    summonerspells = await fetch_summonerspells_by_patch(patch)
    if not summonerspells:
        raise HTTPException(status_code=404, detail=f"No summonerspells found for patch. {patch} !")
    return summonerspells