from pydantic import BaseModel
from src.server.models.dataenums import ActionType, Actor, TickEvent


class Rank(BaseModel):
    q: int
    w: int
    e: int
    r: int


class Action(BaseModel):
    actor: Actor
    target: Actor
    action_type: ActionType
    outcome: str | None = None
    crit: bool | None = None  # for attacks: True/False picks it, None uses the expected value



class V1Request(BaseModel):
    id_attacker: str
    lvl_attacker: int
    ability_points_attacker: Rank
    items_attacker: list[str]
    id_defender: str
    lvl_defender: int
    ability_points_defender: Rank
    items_defender: list[str]
    combo: list[Action]


class V1Response(BaseModel):
    tick_rate: float
    damage: int
    ticks: int
    last_action_tick: int
    deaths: dict[Actor, int] = {}  # tick at which an actor's health first reached 0
    effect_list: list[TickEvent]


class ItemRequest(BaseModel):
    items: list[str]
    new_item: str

