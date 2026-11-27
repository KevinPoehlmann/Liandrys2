from fastapi import HTTPException

from src.server.database import (fetch_champion_by_id, fetch_item_by_id, fetch_patch_by_name, fetch_rune_by_id,
                                 fetch_summonerspell_by_id)
from src.server.models.champion import Champion
from src.server.models.item import Item
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell


async def reject_preview(patch: str) -> None:
    # Every PBE build and the release replace the preview, so hand-made changes there would be lost.
    found = await fetch_patch_by_name(patch)
    if found and found.preview:
        raise HTTPException(status_code=409,
                            detail=f"Patch {patch} is a PBE preview and read-only, edit the live patch instead")



async def get_required_champion(id_: str) -> Champion:
    champion = await fetch_champion_by_id(id_)
    if not champion:
        raise HTTPException(status_code=404, detail=f"Champion not found: {id_}")
    return champion

async def get_required_item(id_: str) -> Item:
    item = await fetch_item_by_id(id_)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item not found: {id_}")
    return item

async def get_required_rune(id_: str) -> Rune:
    # Assuming a function fetch_rune_by_id exists
    rune = await fetch_rune_by_id(id_)
    if not rune:
        raise HTTPException(status_code=404, detail=f"Rune not found: {id_}")
    return rune

async def get_required_summonerspell(id_: str) -> Summonerspell:
    # Assuming a function fetch_summonerspell_by_id exists
    summonerspell = await fetch_summonerspell_by_id(id_)
    if not summonerspell:
        raise HTTPException(status_code=404, detail=f"Summoner Spell not found: {id_}")
    return summonerspell