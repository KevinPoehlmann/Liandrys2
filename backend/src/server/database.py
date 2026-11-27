import asyncio
import logging
import os

from bson import ObjectId
from motor.core import AgnosticCollection, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.collation import Collation
from pymongo.errors import DuplicateKeyError, InvalidURI
from pymongo.results import UpdateResult

from src.server.models.patch import NewPatch, Patch
from src.server.models.champion import NewChampion, Champion, RawChampion, ShortChampion
from src.server.models.item import NewItem, Item, RawItem, ShortItem
from src.server.models.rune import NewRune, RawRune, Rune, ShortRune
from src.server.models.summonerspell import NewSummonerspell, RawSummonerspell, Summonerspell, ShortSummonerspell
from src.server.models.enums import Map




patch_logger = logging.getLogger("patch_logger")

# Patches are strings, so without numeric ordering "15.9.1" sorts after "15.10.1".
PATCH_ORDER = {"sort": [("patch", -1)], "collation": Collation(locale="en", numericOrdering=True)}


def connect_database() -> AgnosticDatabase:
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


async def setup_indexes() -> None:
    await _unique_index(patch_collection, ["patch"], "patch_index")
    await _unique_index(champion_collection, ["name", "patch"], "champion_index")
    await _unique_index(item_collection, ["item_id", "patch"], "item_index")
    await _unique_index(rune_collection, ["name", "patch"], "rune_index")
    await _unique_index(summonerspell_collection, ["key", "patch"], "summonerspell_index")
    await _unique_index(raw_champion_collection, ["champion_id", "patch"], "raw_champion_index")
    await _unique_index(raw_summonerspell_collection, ["key", "patch"], "raw_summonerspell_index")
    await _unique_index(raw_item_collection, ["item_id", "patch"], "raw_item_index")
    await _unique_index(raw_rune_collection, ["rune_id", "patch"], "raw_rune_index")


async def _unique_index(collection: AgnosticCollection, fields: list[str], name: str) -> None:
    keys = [(field, 1) for field in fields]
    existing = (await collection.index_information()).get(name)
    if existing and existing["key"] != keys:
        # Until 16.23 the hotfix was part of every key; a hotfix now overwrites its patch.
        await collection.drop_index(name)
    try:
        await collection.create_index(keys, unique=True, name=name)
    except DuplicateKeyError:
        patch_logger.error(f"[DB] {collection.name} has several documents per {fields} (old hotfix copies), "
                           f"index {name} not created. Clear the old patches.")



database = connect_database()

patch_collection: AgnosticCollection = database.patches
champion_collection: AgnosticCollection = database.champions
item_collection: AgnosticCollection = database.items
rune_collection: AgnosticCollection = database.runes
summonerspell_collection: AgnosticCollection = database.summonerspells
raw_champion_collection: AgnosticCollection = database.raw_champions
raw_summonerspell_collection: AgnosticCollection = database.raw_summonerspells
raw_item_collection: AgnosticCollection = database.raw_items
raw_rune_collection: AgnosticCollection = database.raw_runes





async def clear_patch(patch: str) -> dict[str, int]:
    champion_result, item_result, rune_result, spell_result, patch_result = await asyncio.gather(
        champion_collection.delete_many({"patch": patch}),
        item_collection.delete_many({"patch": patch}),
        rune_collection.delete_many({"patch": patch}),
        summonerspell_collection.delete_many({"patch": patch}),
        patch_collection.delete_one({"patch": patch})
    )
    # Then: double check nothing is left
    champion_left, item_left, rune_left, spell_left, patch_left = await asyncio.gather(
        champion_collection.count_documents({"patch": patch}),
        item_collection.count_documents({"patch": patch}),
        rune_collection.count_documents({"patch": patch}),
        summonerspell_collection.count_documents({"patch": patch}),
        patch_collection.count_documents({"patch": patch})
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


async def upsert_patch(patch: NewPatch) -> str:
    result = await patch_collection.update_one(
        {"patch": patch.patch},
        {"$set": patch.dict(exclude={"id"})},
        upsert=True
    )

    if result.upserted_id:
        return result.upserted_id
    else:
        # Find the existing document to get its _id
        doc = await patch_collection.find_one({"patch": patch.patch})
        assert doc is not None
        return doc["_id"]


async def fetch_patch_latest() -> Patch | None:
    document = await patch_collection.find_one(**PATCH_ORDER)
    if not document:
        return None
    return Patch(**document)


async def fetch_patch_by_name(patch: str) -> Patch | None:
    document = await patch_collection.find_one({"patch": patch})
    return Patch(**document) if document else None


async def fetch_patch_by_id(id_) -> Patch | None:
    patch = await patch_collection.find_one({"_id": ObjectId(id_)})
    if patch:
        return Patch(**patch)
    return None
        
    
async def fetch_patch_all() -> list[Patch]:
    patch_list = []
    cursor = patch_collection.find(**PATCH_ORDER)
    async for document in cursor:
        patch = Patch(**document)
        patch_list.append(patch)
    return patch_list


async def clear_patches_collection() -> bool:
    await patch_collection.delete_many({})
    return True




#--------Champion-----------------------------


async def upsert_raw_champion(raw: RawChampion) -> None:
    # A reload of the same patch (hotfix build, newer wiki revision) replaces the old download.
    key = {"champion_id": raw.champion_id, "patch": raw.patch}
    await raw_champion_collection.replace_one(key, raw.dict(), upsert=True)


async def fetch_raw_champion(champion_id: str, patch: str) -> RawChampion | None:
    document = await raw_champion_collection.find_one({"champion_id": champion_id, "patch": patch})
    return RawChampion.parse_obj(document) if document else None



async def add_champion(champion: NewChampion) -> str:
    document = champion.dict()
    result = await champion_collection.insert_one(document)
    return result.inserted_id


async def exists_champion_by_name(name: str, patch: str) -> bool:
    count = await champion_collection.count_documents({"name": name, "patch": patch}, limit=1)
    return count > 0


async def fetch_champions_by_patch(patch: str) -> list[Champion]:
    champions = []
    cursor = champion_collection.find(
        {"patch": patch},
        sort=[("name", 1)])
    async for document in cursor:
        champion = Champion.parse_obj(document)
        champions.append(champion)
    return champions


async def fetch_short_champions_by_patch(patch: str) -> list[ShortChampion]:
    champions = []
    cursor = champion_collection.find(
        {"patch": patch},
        {
            "_id": 1,
            "name": 1,
            "key": 1,
            "champion_id": 1,
            "validated": 1,
            "image": 1,
            "q.name": 1,
            "q.maxrank": 1,
            "q.image": 1,
            "q.validated": 1,
            "w.name": 1,
            "w.maxrank": 1,
            "w.image": 1,
            "w.validated": 1,
            "e.name": 1,
            "e.maxrank": 1,
            "e.image": 1,
            "e.validated": 1,
            "r.name": 1,
            "r.maxrank": 1,
            "r.image": 1,
            "r.validated": 1
        }
,
        sort=[("name", 1)])
    async for document in cursor:
        champion = ShortChampion(**document)
        champions.append(champion)
    return champions


async def fetch_champion_by_id(id_: str) -> Champion | None:
    document = await champion_collection.find_one({"_id":ObjectId(id_)})
    if document:
        champion = Champion.parse_obj(document)
        return champion
    return None


async def update_champion(champion: Champion) -> UpdateResult:
    result = await champion_collection.update_one({"_id":ObjectId(champion.id)}, {"$set": champion.dict()})
    return result



#--------Item-----------------------------


async def upsert_raw_item(raw: RawItem) -> None:
    key = {"item_id": raw.item_id, "patch": raw.patch}
    await raw_item_collection.replace_one(key, raw.dict(), upsert=True)


async def fetch_raw_item(item_id: str, patch: str) -> RawItem | None:
    document = await raw_item_collection.find_one({"item_id": item_id, "patch": patch})
    return RawItem.parse_obj(document) if document else None


async def add_item(item: NewItem) -> str:
    document = item.dict()
    result = await item_collection.insert_one(document)
    return result.inserted_id


async def exists_item_by_item_id(item_id: str, patch: str) -> bool:
    count = await item_collection.count_documents({"item_id": item_id, "patch": patch}, limit=1)
    return count > 0


async def fetch_items_by_patch(patch: str) -> list[Item]:
    items = []
    cursor = item_collection.find(
        {"patch": patch},
        sort=[("name", 1)])
    async for document in cursor:
        item = Item.parse_obj(document)
        items.append(item)
    return items


async def fetch_short_items_by_patch(patch: str, map: Map | None = None) -> list[ShortItem]:
    query = {"patch": patch}
    if map:
        query["maps"] = map.value

    cursor = item_collection.find(
        query,
        {"_id": 1, "item_id": 1, "name": 1, "gold": 1, "active": 1, "class_": 1, "validated": 1, "maps": 1, "image": 1},
        sort=[("name", 1)])
    items = [ShortItem(**doc) async for doc in cursor]
    return items


async def fetch_item_by_id(id_: str) -> Item | None:
    document = await item_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Item.parse_obj(document)
    return None


async def update_item(item: Item):
    result = await item_collection.update_one({"_id":ObjectId(item.id)}, {"$set": item.dict()})
    return result


#--------Rune-----------------------------


async def add_rune(rune: NewRune) -> str:
    document = rune.dict()
    result = await rune_collection.insert_one(document)
    return result.inserted_id


async def exists_rune(rune_id: int, patch: str, row: int | None = None) -> bool:
    """`row` only for a stat shard, which has one document per row."""
    query = {"rune_id": rune_id, "patch": patch} | ({"row": row} if row is not None else {})
    count = await rune_collection.count_documents(query, limit=1)
    return count > 0


async def upsert_raw_rune(raw: RawRune) -> None:
    key = {"rune_id": raw.rune_id, "patch": raw.patch}
    await raw_rune_collection.replace_one(key, raw.dict(), upsert=True)


async def fetch_raw_rune(rune_id: int, patch: str) -> RawRune | None:
    document = await raw_rune_collection.find_one({"rune_id": rune_id, "patch": patch})
    return RawRune.parse_obj(document) if document else None


async def fetch_runes_by_patch(patch: str) -> list[Rune]:
    runes = []
    cursor = rune_collection.find(
        {"patch": patch},
        sort=[("name", 1)])
    async for document in cursor:
        rune = Rune.parse_obj(document)
        runes.append(rune)
    return runes


async def fetch_short_runes_by_patch(patch: str) -> list[ShortRune]:
    runes = []
    cursor = rune_collection.find(
        {"patch": patch},
        {"_id": 1, "rune_id": 1, "name": 1, "tree": 1, "tree_id": 1, "row": 1, "slot": 1, "validated": 1, "image": 1},
        sort=[("name", 1)])
    async for document in cursor:
        rune = ShortRune(**document)
        runes.append(rune)
    return runes


async def fetch_rune_by_id(id_: str) -> Rune | None:
    document = await rune_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Rune.parse_obj(document)
    return None


async def update_rune(rune: Rune):
    result = await rune_collection.update_one({"_id":ObjectId(rune.id)}, {"$set": rune.dict()})
    return result


#--------Summonerspell-----------------------------


async def upsert_raw_summonerspell(raw: RawSummonerspell) -> None:
    key = {"key": raw.key, "patch": raw.patch}
    await raw_summonerspell_collection.replace_one(key, raw.dict(), upsert=True)


async def fetch_raw_summonerspell(key: str, patch: str) -> RawSummonerspell | None:
    document = await raw_summonerspell_collection.find_one({"key": key, "patch": patch})
    return RawSummonerspell.parse_obj(document) if document else None


async def add_summonerspell(summonerspell: NewSummonerspell) -> str:
    document = summonerspell.dict()
    result = await summonerspell_collection.insert_one(document)
    return result.inserted_id


async def exists_summonerspell_by_key(key: str, patch: str) -> bool:
    count = await summonerspell_collection.count_documents({"key": key, "patch": patch}, limit=1)
    return count > 0


async def fetch_summonerspells_by_patch(patch: str) -> list[Summonerspell]:
    summonerspells = []
    cursor = summonerspell_collection.find(
        {"patch": patch},
        sort=[("name", 1)])
    async for document in cursor:
        summonerspell = Summonerspell.parse_obj(document)
        summonerspells.append(summonerspell)
    return summonerspells


async def fetch_short_summonerspells_by_patch(patch: str, map: Map | None = None) -> list[ShortSummonerspell]:
    query = {"patch": patch}
    if map:
        query["maps"] = map.value

    cursor = summonerspell_collection.find(
        query,
        {"_id": 1, "key": 1, "name": 1, "validated": 1, "maps": 1, "image": 1},
        sort=[("name", 1)])
    summonerspells = [ShortSummonerspell(**doc) async for doc in cursor]
    return summonerspells


async def fetch_summonerspell_by_id(id_: str) -> Summonerspell | None:
    document = await summonerspell_collection.find_one({"_id":ObjectId(id_)})
    if document:
        return Summonerspell.parse_obj(document)
    return None
    

async def update_summonerspell(summonerspell: Summonerspell):
    result = await summonerspell_collection.update_one({"_id":ObjectId(summonerspell.id)}, {"$set": summonerspell.dict()})
    return result