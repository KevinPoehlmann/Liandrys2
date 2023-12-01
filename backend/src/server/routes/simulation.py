from fastapi import APIRouter, HTTPException



router = APIRouter()


#TODO add items, runes, combo
@router.post("/dummy")
async def attack_dummy(champion_id: str, lvl: int) -> int:
    pass