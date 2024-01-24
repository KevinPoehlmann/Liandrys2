from pydantic import BaseModel
from src.server.models.dataenums import ActionType


class DummyRequest(BaseModel):
    champion_id: str
    lvl: int
    items: list[str]
    combo: list[ActionType]


class V1Request(BaseModel):
    id_attacker: str
    lvl_attacker: int
    items_attacker: list[str]
    id_defender: str
    lvl_defender: int
    items_defender: list[str]
    combo: list[ActionType]


class ItemRequest(BaseModel):
    items: list[str]
    new_item: str