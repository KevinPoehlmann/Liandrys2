from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_champions_by_patch,
    fetch_champion_by_id
)
from src.server.models.champion import ShortChampion, Champion

router = APIRouter()



@router.get("/all/{patch}")
async def get_champions(patch: str) -> list[ShortChampion]:
    response = await fetch_champions_by_patch(patch)
    if not response:
        raise HTTPException(status_code=404, detail=f"No champions found for patch. {patch} !")
    return response


@router.get("/{id_}")
async def get_champion_by_id(id_: str) -> Champion:
    response = await fetch_champion_by_id(id_)
    if not response:
        raise HTTPException(status_code=404, detail=f"Could not find Champion with ID: {id_} !")
    return response