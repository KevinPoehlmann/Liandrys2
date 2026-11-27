from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_patch_by_name,
    fetch_short_runes_by_patch,
    fetch_rune_by_id,
    update_rune
)
from src.server.models.patch import RuneTree
from src.server.models.rune import ShortRune, Rune

from src.server.routes.helpers import get_required_rune, reject_preview

router = APIRouter()
admin = APIRouter()



@router.get("/all/{patch}")
async def get_runes(patch: str) -> list[ShortRune]:
    runes = await fetch_short_runes_by_patch(patch)
    if not runes:
        raise HTTPException(status_code=404, detail=f"No runes found for patch. {patch} !")
    return runes


@router.get("/trees/{patch}")
async def get_trees(patch: str) -> dict[int, RuneTree]:
    document = await fetch_patch_by_name(patch)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Patch {patch} not found!")
    return document.rune_trees


@router.get("/{rune_id}")
async def get_rune(rune_id: str) -> Rune:
    return await get_required_rune(rune_id)


@admin.put("/")
async def put_rune(rune: Rune) -> int:
    await reject_preview(rune.patch)
    response = await update_rune(rune)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Rune with ID: {rune.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Rune with ID: {rune.id} !")
    return response.modified_count