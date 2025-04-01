from pydantic import BaseModel, root_validator

from src.server.models.dataenums import (
    ConditionType,
    EffectType,
    DamageProperties,
    HealProperties,
    ShieldProperties,
    EffectProperties,
)

class Scaling(BaseModel):
    pass

class EffectComponent(BaseModel):
    type_: EffectType
    props: EffectProperties
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
            if type_ == EffectType.DAMAGE:
                values["props"] = DamageProperties(**props_data)
            elif type_ == EffectType.HEAL:
                values["props"] = HealProperties(**props_data)  # Example for healing
            elif type_ == EffectType.SHIELD:
                values["props"] = ShieldProperties(**props_data)  # Example for shields

        return values


class Condition(BaseModel):
    modality: bool = True
    condition: ConditionType


class Effect(BaseModel):
    text: str
    effect_components: list[EffectComponent] = []
    conditions: list[Condition] = []