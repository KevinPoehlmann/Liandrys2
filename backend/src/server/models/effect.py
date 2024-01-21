from pydantic import BaseModel
from typing import Union

from src.server.models.dataenums import ConditionType, StatusType, Stat, DamageType, DamageSubType, Table


class Formula(BaseModel):
    formula: str



class Scaling(BaseModel):
    value: Union["Scaling", "Table", "Formula"]
    stat: Stat = None



class Status(BaseModel):
    scalings: list[Scaling] = []
    type_: StatusType = None
    comment: str = ""

    class Config:
        orm_mode = True


class Condition(BaseModel):
    modality: str
    condition: ConditionType


class Effect(BaseModel):
    text: str
    stati: list[Status] = []
    conditions: list[Condition] = []