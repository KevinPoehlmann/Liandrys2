import asyncio
import logging
import os

from bson import ObjectId
from datetime import datetime
from motor.core import AgnosticCollection
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import InvalidURI
from pymongo.results import UpdateResult

from src.server.models.patch import NewPatch, Patch
from src.server.models.champion import NewChampion, Champion, ShortChampion
from src.server.models.item import NewItem, Item, ShortItem
from src.server.models.rune import NewRune, Rune, ShortRune
from src.server.models.summonerspell import NewSummonerspell, Summonerspell, ShortSummonerspell





def connect_database() -> AgnosticCollection:
    host = os.getenv("MONGODB_HOST", "")
    user = os.getenv("MONGODB_USER", "")
    password = os.getenv("MONGODB_PASSWORD", "")
    port = os.getenv("MONGODB_PORT", "")

    if not all([host, user, password, port]):
        connection = "mongodb://localhost:27017"
    else:
        connection = f"mongodb://{user}:{password}@{host}:{port}"
    
    client = AsyncIOMotorClient(connection)

    database = client.liandrys
    return database

database = connect_database()

patch_collection: AgnosticCollection = database.patches
champion_collection: AgnosticCollection = database.champions
item_collection: AgnosticCollection = database.items
rune_collection: AgnosticCollection = database.runes
summonerspell_collection: AgnosticCollection = database.summonerspells





async def clear_patch(patch: str, hotfix: datetime) -> dict[str, int]:
    #TODO add hotfix on delete_many
    champion_result, item_result, rune_result, spell_result, patch_result = await asyncio.gather(
        champion_collection.delete_many({"patch": patch, "hotfix": hotfix}),
        item_collection.delete_many({"patch": patch, "hotfix": hotfix}),
        rune_collection.delete_many({"patch": patch, "hotfix": hotfix}),
        summonerspell_collection.delete_many({"patch": patch, "hotfix": hotfix}),
        patch_collection.delete_one({"patch": patch, "hotfix": hotfix})
    )
    # Then: double check nothing is left
    champion_left, item_left, rune_left, spell_left, patch_left = await asyncio.gather(
        champion_collection.count_documents({"patch": patch, "hotfix": hotfix}),
        item_collection.count_documents({"patch": patch, "hotfix": hotfix}),
        rune_collection.count_documents({"patch": patch, "hotfix": hotfix}),
        summonerspell_collection.count_documents({"patch": patch, "hotfix": hotfix}),
        patch_collection.count_documents({"patch": patch, "hotfix": hotfix})
    )

    cleanup_successful = all(x == 0 for x in [champion_left, item_left, rune_left, spell_left])

    return {
        "champions_deleted": champion_result.deleted_count,
        "items_deleted": item_result.deleted_count,
        "runes_deleted": rune_result.deleted_count,
        "summonerspells_deleted": spell_result.deleted_count,
        "patch_deleted": patch_result.deleted_count,
        "cleanup_successful": cleanup_successful,
    }


#------------------Patch--------------------------------------------------

async def add_patch(patch: NewPatch) -> str:
    document = patch.dict()
    result = await patch_collection.insert_one(document)
    return result.inserted_id


async def fetch_patch_latest() -> Patch:
    patch = await patch_collection.find_one(sort=[("patch", -1), ("hotfix", -1)])
    if patch:
        return Patch(**patch)
    return None


async def fetch_patch_by_id(id_) -> Patch:
    patch = await patch_collection.find_one({"_id": ObjectId(id_)})
    if patch:
        return Patch(**patch)
    return None
        
    
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




#--------Champion-----------------------------


async def add_champion(champion: NewChampion) -> str:
    document = champion.dict()
    result = await champion_collection.insert_one(document)
    return result.inserted_id


async def fetch_champions_by_patch(patch: str, hotfix: datetime) -> list[ShortChampion]:
    champions = []
    cursor = champion_collection.find({"patch":patch, "hotfix":hotfix}, sort=[("name", 1)])
    async for document in cursor:
        champion = ShortChampion(**document)
        champions.append(champion)
    return champions


async def fetch_champion_by_id(id_: str) -> Champion:
    document = await champion_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Champion(**document)


async def update_champion(champion: Champion) -> UpdateResult:
    result = await champion_collection.update_one({"_id":ObjectId(champion.id)}, {"$set": champion.dict()})
    return result



#--------Item-----------------------------


async def add_item(item: NewItem) -> str:
    document = item.dict()
    result = await item_collection.insert_one(document)
    return result.inserted_id


async def fetch_items_by_patch(patch: str, hotfix: datetime) -> list[ShortItem]:
    items = []
    cursor = item_collection.find({"patch":patch, "hotfix":hotfix}, sort=[("name", 1)])
    async for document in cursor:
        item = ShortItem(**document)
        items.append(item)
    return items


async def fetch_item_by_id(id_: str) -> Item:
    document = await item_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Item(**document)


async def update_item(item: Item):
    result = await item_collection.update_one({"_id":ObjectId(item.id)}, {"$set": item.dict()})
    return result


#--------Rune-----------------------------


async def add_rune(rune: NewRune) -> str:
    document = rune.dict()
    result = await rune_collection.insert_one(document)
    return result.inserted_id


async def fetch_runes_by_patch(patch: str, hotfix: datetime) -> list[ShortRune]:
    runes = []
    cursor = rune_collection.find({"patch":patch, "hotfix":hotfix}, sort=[("name", 1)])
    async for document in cursor:
        rune = ShortRune(**document)
        runes.append(rune)
    return runes


async def fetch_rune_by_id(id_: str) -> Rune:
    document = await rune_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Rune(**document)


async def update_rune(rune: Rune):
    result = await rune_collection.update_one({"_id":ObjectId(rune.id)}, {"$set": rune.dict()})
    return result


#--------Summonerspell-----------------------------


async def add_summonerspell(summonerspell: NewSummonerspell) -> str:
    document = summonerspell.dict()
    result = await summonerspell_collection.insert_one(document)
    return result.inserted_id


async def fetch_summonerspells_by_patch(patch: str, hotfix: datetime) -> list[ShortSummonerspell]:
    summonerspells = []
    cursor = summonerspell_collection.find({"patch":patch, "hotfix":hotfix}, sort=[("name", 1)])
    async for document in cursor:
        summonerspell = ShortSummonerspell(**document)
        summonerspells.append(summonerspell)
    return summonerspells


async def fetch_summonerspell_by_id(id_: str) -> Summonerspell:
    document = await summonerspell_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Summonerspell(**document)
    

async def update_summonerspell(summonerspell: Summonerspell):
    result = await summonerspell_collection.update_one({"_id":ObjectId(summonerspell.id)}, {"$set": summonerspell.dict()})
    return result