from fastapi import APIRouter, HTTPException



from src.server.database import (
    fetch_champions_patch,
)
from src.server.models.champion import ShortChampion

router = APIRouter()



@router.get("/{patch}")
async def get_champions(patch: str) -> list[ShortChampion]:
    champions = await fetch_champions_patch(patch)
    if not champions:
        raise HTTPException(status_code=404, detail=f"No champions found for patch. {patch} !")
    return champions