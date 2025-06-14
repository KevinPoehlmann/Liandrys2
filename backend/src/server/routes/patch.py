from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import ValidationError


from src.server.database import (
    fetch_patch_latest,
    fetch_patch_all,
    clear_patches_collection,
    clear_patch 
)

from src.server.loader.patchloader2 import load_data, check_patch_available, patch_load_lock
from src.server.models.patch import NewPatch, Patch


router = APIRouter()
admin = APIRouter()


@router.get("/")
async def get_latest_patch() -> Patch:
    try:
        response = await fetch_patch_latest()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="PATCH_SCHEMA_INVALID")
    if not response:
        raise HTTPException(status_code=404, detail="No patches loaded.")
    return response


@router.get("/all")
async def get_all_patches() -> list[Patch]:
    patch_list = await fetch_patch_all()
    return patch_list


@admin.get("/status")
async def get_status() -> dict:
    try:
        patches = await check_patch_available()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Patch check failed: {e}")

    msg = "Updates available!" if patches else "Everything is up to date!"
    return {
        "patches": patches,
        "msg": msg
    }


@admin.get("/load/status")
async def get_load_status() -> dict:
    return {"loading": patch_load_lock.locked()}


@admin.delete("/")
async def delete_all_patches() -> bool:
    response = await clear_patches_collection()
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went wrong")
    return response


@admin.delete("/{patch}")
async def delete_patch(patch: str, hotfix: datetime | None = None):
    response = await clear_patch(patch, hotfix)
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went wrong")
    return response


@admin.post("/")
async def load(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(load_data)
    return {"msg": "Update triggered in background!"}


