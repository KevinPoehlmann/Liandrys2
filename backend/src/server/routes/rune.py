from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_short_runes_by_patch,
    fetch_rune_by_id,
    update_rune
)
from src.server.models.rune import ShortRune, Rune, RUNE_TREES

from src.server.routes.helpers import get_required_rune

router = APIRouter()
admin = APIRouter()



@router.get("/all/{patch}")
async def get_runes(patch: str) -> list[ShortRune]:
    runes = await fetch_short_runes_by_patch(patch)
    if not runes:
        raise HTTPException(status_code=404, detail=f"No runes found for patch. {patch} !")
    return runes


@router.get("/trees/")
async def get_trees() -> dict[int, dict[str, str]]:
    return RUNE_TREES


@router.get("/{rune_id}")
async def get_rune(rune_id: str) -> Rune:
    return await get_required_rune(rune_id)


@admin.put("/")
async def put_rune(rune: Rune) -> int:
    response = await update_rune(rune)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Rune with ID: {rune.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Rune with ID: {rune.id} !")
    return response.modified_count