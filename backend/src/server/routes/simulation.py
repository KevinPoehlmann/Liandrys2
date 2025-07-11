from fastapi import APIRouter, HTTPException

from src.server.database import fetch_champion_by_id, fetch_item_by_id
from src.server.simulation.simulation import Simulation
from src.server.simulation.character import Character
from src.server.simulation.exceptions import SimulationError
from src.server.models.request import ItemRequest, V1Request, V1Response
from src.server.routes.helpers import get_required_champion, get_required_item


router = APIRouter()




@router.post("/v1")
async def v1_simulation(v1_request: V1Request) -> V1Response:
    try:
        attacker = await get_required_champion(v1_request.id_attacker)
        defender = await get_required_champion(v1_request.id_defender)
        items_attacker = []
        for item_id in v1_request.items_attacker:
            item = await get_required_item(item_id)
            items_attacker.append(item)
        char_a = Character(attacker, v1_request.lvl_attacker, v1_request.ability_points_attacker, items_attacker)
        items_defender = []
        for item_id in v1_request.items_defender:
            item = await get_required_item(item_id)
            items_defender.append(item)
        char_d = Character(defender, v1_request.lvl_defender, v1_request.ability_points_defender, items_defender)
        sim = Simulation(char_a, char_d)
        return sim.do_combo(v1_request.combo)
    except HTTPException:
        raise
    except SimulationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



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
