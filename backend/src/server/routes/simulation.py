from fastapi import APIRouter, HTTPException

from src.server.database import fetch_champion_by_id, fetch_item_by_id
from src.server.simulation.simulator import DummySimulation, V1Simulation
from src.server.simulation.unit import Unit, Dummy, Character
from src.server.models.request import DummyRequest, DummyResponse, ItemRequest, V1Request, V1Response


router = APIRouter()


#TODO add runes, summonerspells
@router.post("/dummy")
async def attack_dummy(dummy_request: DummyRequest) -> DummyResponse:
    champion = await fetch_champion_by_id(dummy_request.champion_id)
    items = []
    for item_id in dummy_request.items:
        item = await fetch_item_by_id(item_id)
        items.append(item)
    dummy = Dummy(Unit(hp=1000, armor=50, mr=50))
    character = Character(champion, dummy_request.lvl, dummy_request.ability_points, items)
    sim = DummySimulation(dummy, character)
    return sim.do_combo(dummy_request.combo)


@router.post("/v1")
async def v1_simulation(v1_request: V1Request) -> V1Response:
    attacker = await fetch_champion_by_id(v1_request.id_attacker)
    defender = await fetch_champion_by_id(v1_request.id_defender)
    items_attacker = []
    for item_id in v1_request.items_attacker:
        item = await fetch_item_by_id(item_id)
        items_attacker.append(item)
    char_a = Character(attacker, v1_request.lvl_attacker, v1_request.ability_points_attacker, items_attacker)
    items_defender = []
    for item_id in v1_request.items_defender:
        item = await fetch_item_by_id(item_id)
        items_defender.append(item)
    char_d = Character(defender, v1_request.lvl_defender, v1_request.ability_points_defender, items_defender)
    sim = V1Simulation(char_a, char_d)
    return sim.do_combo(v1_request.combo)



@router.post("/item")
async def add_item(item_request: ItemRequest) -> bool:
    items = []
    for item_id in item_request.items:
        item = await fetch_item_by_id(item_id)
        items.append(item)
    item = await fetch_item_by_id(item_request.new_item)

    #TODO Add logic here
    if True:
        return True
    else:
        return False
