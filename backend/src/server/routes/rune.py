from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_runes_by_patch,
)
from src.server.models.rune import ShortRune

router = APIRouter()



@router.get("/{patch}")
async def get_runes(patch: str) -> list[ShortRune]:
    runes = await fetch_runes_by_patch(patch)
    if not runes:
        raise HTTPException(status_code=404, detail=f"No runes found for patch. {patch} !")
    return runes