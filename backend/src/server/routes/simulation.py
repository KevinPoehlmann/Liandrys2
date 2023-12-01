from fastapi import APIRouter, HTTPException



router = APIRouter()


@router.get("/dummy")
async def attack_dummy():
    pass