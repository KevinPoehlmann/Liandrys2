from pydantic import BaseModel, root_validator
from typing import Union

from src.server.models.dataenums import (
    ConditionType,
    StatusType,
    DamageProperties,
    HealProperties,
    StatusProperties,
)

class Scaling(BaseModel):
    pass

class Status(BaseModel):
    type_: StatusType
    props: StatusProperties
    duration: float = 0.0
    interval: float = 0.0
    delay: float = 0.0
    speed: int = 0
    comment: str = ""

    @root_validator(pre=True)
    def validate_props(cls, values):
        """Ensure props is instantiated as the correct subclass."""
        props_data = values.get("props")
        type_ = values.get("type_")

        if isinstance(props_data, dict):  # If props is a dict, determine the subclass
            if type_ == StatusType.DAMAGE:
                values["props"] = DamageProperties(**props_data)
            elif type_ == StatusType.HEAL:
                values["props"] = HealProperties(**props_data)  # Example for healing
            """ elif type_ == StatusType.SHIELD:
                values["props"] = ShieldProperties(**props_data)  # Example for shields """

        return values


class Condition(BaseModel):
    modality: bool = True
    condition: ConditionType


class Effect(BaseModel):
    text: str
    stati: list[Status] = []
    conditions: list[Condition] = []