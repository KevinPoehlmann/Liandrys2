from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_runes_by_patch,
    fetch_rune_by_id
)
from src.server.models.rune import ShortRune, Rune



router = APIRouter()



@router.get("/all/{patch}")
async def get_runes(patch: str) -> list[ShortRune]:
    runes = await fetch_runes_by_patch(patch)
    if not runes:
        raise HTTPException(status_code=404, detail=f"No runes found for patch. {patch} !")
    return runes


@router.get("/{rune_id}")
async def get_item(rune_id: str) -> Rune:
    rune = await fetch_rune_by_id(rune_id)
    if not rune:
        raise HTTPException(status_code=404, detail=f"No rune found with id: {rune_id} !")
    return rune