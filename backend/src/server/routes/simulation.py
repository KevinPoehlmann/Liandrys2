from fastapi import APIRouter

from src.server.database import fetch_item_by_id
from src.server.simulation.simulation import Simulation
from src.server.simulation.character import Character
from src.server.errors import simulation_failed
from src.server.models.request import ItemRequest, V1Request, V1Response
from src.server.routes.helpers import get_required_champion, get_required_item


router = APIRouter()




@router.post("/v1")
async def v1_simulation(v1_request: V1Request) -> V1Response:
    attacker = await get_required_champion(v1_request.id_attacker)
    defender = await get_required_champion(v1_request.id_defender)
    items_attacker = [await get_required_item(item_id) for item_id in v1_request.items_attacker]
    items_defender = [await get_required_item(item_id) for item_id in v1_request.items_defender]
    try:
        char_a = Character(attacker, v1_request.lvl_attacker, v1_request.ability_points_attacker, items_attacker)
        char_d = Character(defender, v1_request.lvl_defender, v1_request.ability_points_defender, items_defender)
        return Simulation(char_a, char_d).do_combo(v1_request.combo)
    except Exception as error:
        return simulation_failed(v1_request, error)



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
