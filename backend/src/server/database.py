import os

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import InvalidURI

from src.server.models.patch import NewPatch, Patch





def connect_database() -> AsyncIOMotorDatabase:
    host = os.getenv("MONGODB_HOST", "")
    user = os.getenv("MONGODB_USER", "")
    password = os.getenv("MONGODB_PASSWORD", "")
    port = os.getenv("MONGODB_PORT", "")
    connection = f"mongodb://{user}:{password}@{host}:{port}"

    try:
        client = AsyncIOMotorClient(connection)
    except InvalidURI:
        #for testing
        #TODO Remove at some point
        client= AsyncIOMotorClient("mongodb://localhost:27017")
    database = client.liandrys
    return database

database = connect_database()

patches_collection: AsyncIOMotorCollection = database.patches



async def add_patch(patch: NewPatch) -> str:
    document = patch.dict()
    result = await patches_collection.insert_one(document)
    return result.inserted_id


async def fetch_patch_latest() -> Patch:
    cursor = patches_collection.find().sort("patch", -1)
    async for document in cursor:
        patch = Patch(**document)
        return patch


async def fetch_patch_by_id(id) -> Patch:
    patch = await patches_collection.find_one({"_id": ObjectId(id)})
    if patch:
        return Patch(**patch)
        
    
async def fetch_patch_all() -> list[Patch]:
    patch_list = []
    cursor = patches_collection.find()
    async for document in cursor:
        patch = Patch(**document)
        patch_list.append(patch)
    return patch_list


async def clear_patches_collection() -> bool:
    await patches_collection.delete_many({})
    return True