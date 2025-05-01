from pydantic import BaseModel

from src.server.models.dataenums import (
    Condition,
    DamageProperties,
    EffectProperties,
    EffectType,
    HealProperties,
    ShieldProperties,
    StatusProperties
)




class EffectComponent(BaseModel):
    type_: EffectType
    props: EffectProperties
    duration: float = 0.0
    interval: float = 0.0
    delay: float = 0.0
    speed: int = 0
    comment: str = ""

    @classmethod
    def parse_obj(cls, obj: dict) -> "EffectComponent":
        type_ = obj.get("type_")
        props = obj.get("props")

        # Fix enum from string if needed
        if isinstance(type_, str):
            type_ = EffectType(type_)
            obj["type_"] = type_

        # Parse the correct props type
        if isinstance(props, dict):
            props_class = EFFECT_PROPERTIES_MAP.get(type_, EffectProperties)
            obj["props"] = props_class(**props)

        return super().parse_obj(obj)


    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d["props"] = self.props.dict() if self.props else None
        return d



class Effect(BaseModel):
    text: str
    effect_components: list[EffectComponent] = []
    conditions: list[Condition] = []


    @classmethod
    def parse_obj(cls, obj: dict) -> "Effect":
        if "effect_components" in obj:
            obj["effect_components"] = [
                EffectComponent.parse_obj(ec)
                for ec in obj["effect_components"]
            ]
        return super().parse_obj(obj)




EFFECT_PROPERTIES_MAP = {
    EffectType.DAMAGE: DamageProperties,
    EffectType.HEAL: HealProperties,
    EffectType.SHIELD: ShieldProperties,
    EffectType.STATUS: StatusProperties,
}