from pydantic import BaseModel
from src.server.models.dataenums import ActionType


class DummyRequest(BaseModel):
    champion_id: str
    lvl: int
    items: list[str]
    combo: list[ActionType]