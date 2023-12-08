from fastapi import APIRouter, HTTPException

from src.server.database import fetch_champion_by_id
from src.server.simulation.simulator import DummySimulation
from src.server.models.request import DummyRequest


router = APIRouter()


#TODO add items, runes, combo
@router.post("/dummy")
async def attack_dummy(dummy_request: DummyRequest) -> int:
    champion = await fetch_champion_by_id(dummy_request.champion_id)
    sim = DummySimulation(champion, dummy_request.lvl)
    return sim.attack()