from fastapi import APIRouter, HTTPException

from src.server.database import fetch_champion_by_id, fetch_item_by_id
from src.server.simulation.simulator import DummySimulation
from src.server.models.request import DummyRequest


router = APIRouter()


#TODO add items, runes, summonerspells
@router.post("/dummy")
async def attack_dummy(dummy_request: DummyRequest) -> int:
    champion = await fetch_champion_by_id(dummy_request.champion_id)
    items = []
    for item_id in dummy_request.items:
        item = await fetch_item_by_id(item_id)
        items.append(item)
    sim = DummySimulation(champion, dummy_request.lvl, dummy_request.combo, items)
    return sim.do_combo()