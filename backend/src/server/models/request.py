from pydantic import BaseModel
from src.server.models.dataenums import ActionType


class Rank(BaseModel):
    q: int
    w: int
    e: int
    r: int


class DummyRequest(BaseModel):
    champion_id: str
    lvl: int
    ability_points: Rank
    items: list[str]
    combo: list[ActionType]


class DummyResponse(BaseModel):
    damage: int
    time: float


class V1Request(BaseModel):
    id_attacker: str
    lvl_attacker: int
    ability_points_attacker: Rank
    items_attacker: list[str]
    id_defender: str
    lvl_defender: int
    ability_points_defender: Rank
    items_defender: list[str]
    combo: list[ActionType]


class V1Response(BaseModel):
    damage: int
    time: float


class ItemRequest(BaseModel):
    items: list[str]
    new_item: str

