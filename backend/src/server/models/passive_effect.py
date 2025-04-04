from pydantic import BaseModel, root_validator

from src.server.models.dataenums import (
    ActionType,
    Buff,
    BuffActionType,
    Condition,
    Stat
)
from src.server.models.effect import EffectComponent



class BuffActionProps(BaseModel):
    pass

class StackProps(BuffActionProps):
    stack_key: ActionType
    amount: str

class EffectProps(BuffActionProps):
    effect: EffectComponent



class BuffAction(BaseModel):
    type_: BuffActionType
    props: BuffActionProps

    @root_validator(pre=True)
    def validate_props(cls, values):
        """Ensure props is instantiated as the correct subclass."""
        props_data = values.get("props")
        type_ = values.get("type_")

        if isinstance(props_data, dict):  # If props is a dict, determine the subclass
            match type_:
                case BuffActionType.STACK:
                    values["props"] = StackProps(**props_data)
                case BuffActionType.EFFECT:
                    values["props"] = EffectProps(**props_data)

        return values



class BuffProperties(BaseModel):
    condition: Condition = None

class StatProperties(BuffProperties):
    stat: Stat
    scaling: str = ""

class ActionProperties(BuffProperties):
    trigger: list[ActionType]
    actions: list[BuffAction]

class HitProperties(BuffProperties):
    pass

class GetHitProperties(BuffProperties):
    pass




class PassiveEffect(BaseModel):
    buff: Buff
    props: BuffProperties

    @root_validator(pre=True)
    def validate_props(cls, values):
        """Ensure props is instantiated as the correct subclass."""
        props_data = values.get("props")
        buff = values.get("buff")

        if isinstance(props_data, dict):  # If props is a dict, determine the subclass
            match buff:
                case Buff.STATS:
                    values["props"] = StatProperties(**props_data)
                case Buff.CAST:
                    values["props"] = ActionProperties(**props_data)
                case Buff.HIT:
                    values["props"] = HitProperties(**props_data)
                case Buff.GET_HIT:
                    values["props"] = GetHitProperties(**props_data)

        return values