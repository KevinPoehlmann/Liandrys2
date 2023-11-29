from fastapi import APIRouter, HTTPException, BackgroundTasks


from src.server.database import (
    fetch_patch_latest,
    fetch_patch_all,
    clear_patches_collection,
    clear_patch 
)

from src.server.loader.patchloader import Patchloader
from src.server.loader.patchexceptions import PatcherError, MuteException, EmptyTodoException
from src.server.models.patch import NewPatch, Patch


router = APIRouter()


@router.get("/")
async def get_latest_patch():
    response = await fetch_patch_latest()
    if not response:
        return {"patch": "No patches loaded!"}
    return response


@router.get("/all")
async def get_all_patches():
    patch_list = await fetch_patch_all()
    return patch_list


@router.get("/status")
async def get_patches_status():
    try:
        todos = await Patchloader.update_todo()
    except MuteException as e:
        response = {
            "todo": Patchloader.todo,
            "msg": "Already loading updates!"
        }
        return response
    except PatcherError as e:
        raise HTTPException(status_code=400, detail=f"{e.error}\n - {e.message}")
    except Exception as e:
        Patchloader.mute = False
        raise HTTPException(status_code=400, detail=e)
    
    msg = "Updates available!" if todos else "Everything is up to date!"
    response =  {
        "todo": todos,
        "msg": msg
    }
    return response


@router.delete("/")
async def delete_all_patches():
    response = await clear_patches_collection()
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went wrong")
    return response


@router.delete("/{patch}")
async def delete_patch(patch: str):
    response = await clear_patch(patch)
    if not response:
        raise HTTPException(status_code=400, detail=f"Something went wrong")
    return response


@router.post("/")
async def update_patches(background_tasks: BackgroundTasks) -> dict:
    try:
        pl = Patchloader()
    except MuteException as e:
        return {"msg": "Already loading updates!"}
    except EmptyTodoException as e:
        return {"msg": "Everything is up to date!"}
    
    #background_tasks.add_task(pl.work_todo)
    await pl.work_todo()
    return {"msg": "Updating...!"}


