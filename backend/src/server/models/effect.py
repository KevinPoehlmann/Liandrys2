from pydantic import BaseModel
from typing import Union

from src.server.models.dataenums import (
    ConditionType,
    StatusType,
    Stat,
    DamageCalculation,
    DamageSubType, 
    Table
)


class Scaling(BaseModel):
    value: Union["Scaling", "Table"]
    stat: Stat = None

class Status(BaseModel):
    scaling: str = "0"
    type_: StatusType = None
    dmg_calc: DamageCalculation = None
    comment: str = ""

    class Config:
        orm_mode = True


class Condition(BaseModel):
    modality: bool = True
    condition: ConditionType


class Effect(BaseModel):
    text: str
    stati: list[Status] = []
    damage_sub_type: DamageSubType = None
    conditions: list[Condition] = []