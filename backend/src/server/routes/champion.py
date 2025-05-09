import logging

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse




from src.server.database import (
    fetch_champions_by_patch,
    fetch_champion_by_id,
    update_champion
)
from src.server.models.champion import ShortChampion, Champion
from src.server.models.dataenums import RangeType, ResourceType

from src.server.utils.request_parsing import parse_from_request

router = APIRouter()
debugger = logging.getLogger("debugger")



@router.get("/all/{patch}")
async def get_champions(patch: str, hotfix: datetime | None = None) -> list[ShortChampion]:
    response = await fetch_champions_by_patch(patch, hotfix)
    if not response:
        raise HTTPException(status_code=404, detail=f"No champions found for patch. {patch} !")
    return response


@router.get("/{id_}", response_model=Champion)
async def get_champion_by_id(id_: str) -> Champion:
    response = await fetch_champion_by_id(id_)
    if not response:
        raise HTTPException(status_code=404, detail=f"Could not find Champion with ID: {id_} !")
    return JSONResponse(content=response.dict())


@router.put("/")
async def put_champion(request: Request) -> Champion:
    champion = parse_from_request(request, Champion)
    response = await update_champion(champion)
    if response.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Could not find Champion with ID: {champion.id} !")
    if response.modified_count == 0:
        raise HTTPException(status_code=400, detail=f"Nothing changed for Champion with ID: {champion.id} !")
    return champion





#------------------Enums--------------------------------------------------

@router.get("/rangetype/")
async def get_rangeType() -> list[RangeType]:
    response = [e.value for e in RangeType]
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went horribly wrong!")
    return response


@router.get("/resourcetype/")
async def get_resourceType() -> list[ResourceType]:
    response = [e.value for e in ResourceType]
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went horribly wrong!")
    return response