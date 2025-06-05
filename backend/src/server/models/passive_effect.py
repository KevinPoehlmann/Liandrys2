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

    @classmethod
    def parse_obj(cls, obj: dict) -> "EffectProps":
        if obj.get("effect") is not None:
            obj["effect"] = EffectComponent.parse_obj(obj["effect"])
        return super().parse_obj(obj)



BUFF_ACTION_PROPERTIES_MAP = {
    BuffActionType.STACK: StackProps,
    BuffActionType.EFFECT: EffectProps,
}


class BuffAction(BaseModel):
    type_: BuffActionType
    props: BuffActionProps

    @classmethod
    def parse_obj(cls, obj: dict) -> "BuffAction":
        type_ = obj.get("type_")
        props = obj.get("props")

        if isinstance(type_, str):
            type_ = BuffActionType(type_)
            obj["type_"] = type_

        if isinstance(props, dict) and isinstance(type_, BuffActionType):
            props_class = BUFF_ACTION_PROPERTIES_MAP.get(type_, BuffActionProps)
            obj["props"] = props_class.parse_obj(props)

        return super().parse_obj(obj)
    

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d["props"] = self.props.dict() if self.props else None
        return d



class BuffProperties(BaseModel):
    condition: Condition | None = None

class StatProperties(BuffProperties):
    stat: Stat
    scaling: str = ""

class ActionProperties(BuffProperties):
    trigger: list[ActionType]
    actions: list[BuffAction]

    @classmethod
    def parse_obj(cls, obj: dict) -> "ActionProperties":
        if "actions" in obj:
            obj["actions"] = [
                BuffAction.parse_obj(ec)
                for ec in obj["actions"]
            ]
        return super().parse_obj(obj)

class HitProperties(BuffProperties):
    pass

class GetHitProperties(BuffProperties):
    pass



PASSIVE_PROPERTIES_MAP = {
    Buff.STATS: StatProperties,
    Buff.CAST: ActionProperties,
    Buff.HIT: HitProperties,
    Buff.GET_HIT: GetHitProperties,
}




class PassiveEffect(BaseModel):
    buff: Buff
    props: BuffProperties

    @classmethod
    def parse_obj(cls, obj: dict) -> "PassiveEffect":
        buff = obj.get("buff")
        props = obj.get("props")

        if isinstance(buff, str):
            try:
                buff = Buff(buff)
                obj["buff"] = buff
            except ValueError:
                raise ValueError(f"Invalid Buff: {buff}")

        if isinstance(props, dict) and isinstance(buff, Buff):
            props_class = PASSIVE_PROPERTIES_MAP.get(buff, BuffProperties)
            obj["props"] = props_class.parse_obj(props)

        return super().parse_obj(obj)
    

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d["props"] = self.props.dict() if self.props else None
        return d