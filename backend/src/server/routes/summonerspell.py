from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse



from src.server.database import (
    fetch_short_summonerspells_by_patch,
    fetch_summonerspell_by_id,
    update_summonerspell
)
from src.server.models.summonerspell import ShortSummonerspell, Summonerspell

from src.server.routes.helpers import get_required_summonerspell, parse_from_request

router = APIRouter()



@router.get("/all/{patch}")
async def get_summonerspells(patch: str, hotfix: datetime | None = None) -> list[ShortSummonerspell]:
    summonerspells = await fetch_short_summonerspells_by_patch(patch, hotfix)
    if not summonerspells:
        raise HTTPException(status_code=404, detail=f"No summonerspells found for patch. {patch} !")
    return summonerspells


@router.get("/{summoner_id}")
async def get_summonerspell(summoner_id: str) -> JSONResponse:
    summonerspell = await get_required_summonerspell(summoner_id)
    return JSONResponse(content=summonerspell.dict())


@router.put("/")
async def put_summonerspell(request: Request) -> int:
    summonerspell = await parse_from_request(request, Summonerspell)
    response = await update_summonerspell(summonerspell)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Summonerspell with ID: {summonerspell.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Summonerspell with ID: {summonerspell.id} !")
    return response.modified_count