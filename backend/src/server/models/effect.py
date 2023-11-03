from pydantic import BaseModel

from src.server.models.dataenums import ConditionType, StatusType, Stat, Table




class ScaleScale(BaseModel):
    value: float
    stat: Stat


class Scaling(BaseModel):
    value: list[float]
    stat: Stat
    scalescale: list[ScaleScale] = []


class Status(BaseModel):
    type_: StatusType
    duration: float = 0


class EffectStat(BaseModel):
    flat: Table = None
    scalings: list[Scaling] = []
    status: Status = None
    comment: str = ""


class Condition(BaseModel):
    modality: str
    condition: ConditionType


class Effect(BaseModel):
    text: str
    stats: list[EffectStat] = []
    conditions: list[Condition] = []