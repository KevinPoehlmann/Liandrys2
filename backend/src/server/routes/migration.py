from fastapi import APIRouter, HTTPException, Body

from src.server.migrate import migrate
from src.server.models.migration import MigrationResult, MigrationRequest


admin = APIRouter()


@admin.post("/")
async def run_migration(request: MigrationRequest) -> MigrationResult:
    return await migrate(request)