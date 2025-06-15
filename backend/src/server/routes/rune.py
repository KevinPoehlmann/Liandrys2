from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse



from src.server.database import (
    fetch_short_runes_by_patch,
    fetch_rune_by_id,
    update_rune
)
from src.server.models.rune import ShortRune, Rune

from src.server.routes.helpers import get_required_rune, parse_from_request

router = APIRouter()
admin = APIRouter()



@router.get("/all/{patch}")
async def get_runes(patch: str, hotfix: datetime | None = None) -> list[ShortRune]:
    runes = await fetch_short_runes_by_patch(patch, hotfix)
    if not runes:
        raise HTTPException(status_code=404, detail=f"No runes found for patch. {patch} !")
    return runes


@router.get("/{rune_id}")
async def get_rune(rune_id: str) -> JSONResponse:
    rune = await get_required_rune(rune_id)
    return JSONResponse(content=jsonable_encoder(rune))


@admin.put("/")
async def put_rune(request: Request) -> int:
    rune = await parse_from_request(request, Rune)
    response = await update_rune(rune)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Rune with ID: {rune.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Rune with ID: {rune.id} !")
    return response.modified_count