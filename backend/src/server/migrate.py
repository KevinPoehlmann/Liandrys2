import src.server.database as db
from src.server.models.migration import MigrationResult, MigrationRequest




async def migrate(req: MigrationRequest) -> MigrationResult:
    result = MigrationResult()
    
    if req.patch:
        try:
            result.updated_patches = await _migrate_patch_schema()
        except Exception as e:
            result.errors.append(f"Patch: {e}")

    return result



async def _migrate_patch_schema() -> int:
    cursor = db.patch_collection.find({"cached_documents": {"$exists": False}})
    updated = 0

    async for doc in cursor:
        await db.patch_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"cached_documents": 0}, "$unset": {"loaded_documents": ""}}
        )
        updated += 1
    return updated