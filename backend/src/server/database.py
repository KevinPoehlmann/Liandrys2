import asyncio
import os

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import InvalidURI

from src.server.models.patch import NewPatch, Patch
from src.server.models.champion import NewChampion, Champion, ShortChampion
from src.server.models.item import NewItem, Item, ShortItem
from src.server.models.rune import NewRune, Rune, ShortRune
from src.server.models.summonerspell import NewSummonerspell, Summonerspell, ShortSummonerspell





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

patch_collection: AsyncIOMotorCollection = database.patches
champion_collection: AsyncIOMotorCollection = database.champions
item_collection: AsyncIOMotorCollection = database.items
rune_collection: AsyncIOMotorCollection = database.runes
summonerspell_collection: AsyncIOMotorCollection = database.summonerspells



async def clear_patch(patch: str) -> None:
    del_patch = await patch_collection.delete_one({"patch": patch})
    await asyncio.gather(
        champion_collection.delete_many({"patch": patch}),
        item_collection.delete_many({"patch": patch}),
        rune_collection.delete_many({"patch": patch}),
        summonerspell_collection.delete_many({"patch": patch})
    )


#------------------Patch--------------------------------------------------

async def add_patch(patch: NewPatch) -> str:
    document = patch.dict()
    result = await patch_collection.insert_one(document)
    return result.inserted_id


async def fetch_patch_latest() -> Patch:
    cursor = patch_collection.find().sort("patch", -1)
    async for document in cursor:
        patch = Patch(**document)
        return patch


async def fetch_patch_by_id(id_) -> Patch:
    patch = await patch_collection.find_one({"_id": ObjectId(id_)})
    if patch:
        return Patch(**patch)
        
    
async def fetch_patch_all() -> list[Patch]:
    patch_list = []
    cursor = patch_collection.find()
    async for document in cursor:
        patch = Patch(**document)
        patch_list.append(patch)
    return patch_list


async def clear_patches_collection() -> bool:
    await patch_collection.delete_many({})
    return True



async def increment_loaded_documents(id_: str) -> None:
    await patch_collection.update_one({"_id":ObjectId(id_)}, {"$inc":{"loaded_documents":1}})




#--------Champion-----------------------------


async def add_champion(champion: NewChampion) -> str:
    document = champion.dict()
    result = await champion_collection.insert_one(document)
    return result.inserted_id


async def fetch_champions_by_patch(patch: str) -> list[ShortChampion]:
    champions = []
    cursor = champion_collection.find({"patch":patch}, sort=[("name", 1)])
    async for document in cursor:
        champion = ShortChampion(**document)
        champions.append(champion)
    return champions


async def fetch_champion_by_id(id_: str) -> Champion:
    document = await champion_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Champion(**document)


#--------Item-----------------------------


async def add_item(item: NewItem) -> str:
    document = item.dict()
    result = await item_collection.insert_one(document)
    return result.inserted_id


async def fetch_items_by_patch(patch: str) -> list[ShortItem]:
    items = []
    cursor = item_collection.find({"patch":patch}, sort=[("name", 1)])
    async for document in cursor:
        item = ShortItem(**document)
        items.append(item)
    return items


async def fetch_item_by_id(id_: str) -> Item:
    document = await item_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Item(**document)

#--------Rune-----------------------------


async def add_rune(rune: NewRune) -> str:
    document = rune.dict()
    result = await rune_collection.insert_one(document)
    return result.inserted_id


async def fetch_runes_by_patch(patch: str) -> list[ShortRune]:
    runes = []
    cursor = rune_collection.find({"patch":patch}, sort=[("name", 1)])
    async for document in cursor:
        rune = ShortRune(**document)
        runes.append(rune)
    return runes


async def fetch_rune_by_id(id_: str) -> Rune:
    document = await rune_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Rune(**document)

#--------Summonerspell-----------------------------


async def add_summonerspell(summonerspell: NewSummonerspell) -> str:
    document = summonerspell.dict()
    result = await summonerspell_collection.insert_one(document)
    return result.inserted_id


async def fetch_summonerspells_by_patch(patch: str) -> list[ShortSummonerspell]:
    summonerspells = []
    cursor = summonerspell_collection.find({"patch":patch}, sort=[("name", 1)])
    async for document in cursor:
        summonerspell = ShortSummonerspell(**document)
        summonerspells.append(summonerspell)
    return summonerspells


async def fetch_summonerspell_by_id(id_: str) -> Summonerspell:
    document = await summonerspell_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Summonerspell(**document)