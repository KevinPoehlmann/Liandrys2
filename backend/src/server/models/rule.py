from typing import Annotated, Literal, Union

from pydantic import BaseModel, Extra, Field, validator

from src.server.models.dataenums import (
    ActionType,
    Comparison,
    DamageSubType,
    DamageType,
    RuleActionType,
    Stat,
    StatMode,
    StatusType,
    Target,
    Trigger
)


class StrictModel(BaseModel):
    class Config:
        extra = Extra.forbid


class DamageProps(StrictModel):
    target: Target
    scaling: str
    dmg_type: list[DamageType] = [DamageType.ABILITY]
    dmg_sub_type: DamageSubType = DamageSubType.PHYSIC
    vamp: float = 0.0

class HealProps(StrictModel):
    target: Target
    scaling: str

class ShieldProps(StrictModel):
    target: Target
    scaling: str
    duration: str
    dmg_sub_type: DamageSubType = DamageSubType.TRUE

class StatusProps(StrictModel):
    target: Target
    status: StatusType
    duration: str
    strength: str = "0"

class ApplyBuffProps(StrictModel):
    buff: str
    target: Target
    stacks: str = "1"

class RemoveBuffProps(StrictModel):
    buff: str
    target: Target

class ResetAttackProps(StrictModel):
    pass

class ModifyCooldownProps(StrictModel):
    slot: ActionType
    amount: str = "0"
    reset: bool = False

class CustomProps(StrictModel):
    function: str
    args: dict[str, str] = {}


class DamageAction(StrictModel):
    type_: Literal[RuleActionType.DAMAGE]
    props: DamageProps

class HealAction(StrictModel):
    type_: Literal[RuleActionType.HEAL]
    props: HealProps

class ShieldAction(StrictModel):
    type_: Literal[RuleActionType.SHIELD]
    props: ShieldProps

class StatusAction(StrictModel):
    type_: Literal[RuleActionType.STATUS]
    props: StatusProps

class ApplyBuffAction(StrictModel):
    type_: Literal[RuleActionType.APPLY_BUFF]
    props: ApplyBuffProps

class RemoveBuffAction(StrictModel):
    type_: Literal[RuleActionType.REMOVE_BUFF]
    props: RemoveBuffProps

class ResetAttackAction(StrictModel):
    type_: Literal[RuleActionType.RESET_ATTACK]
    props: ResetAttackProps = ResetAttackProps()

class ModifyCooldownAction(StrictModel):
    type_: Literal[RuleActionType.MODIFY_COOLDOWN]
    props: ModifyCooldownProps

class CustomAction(StrictModel):
    type_: Literal[RuleActionType.CUSTOM]
    props: CustomProps


# The discriminator picks the action class by `type_`, so nested parsing needs no custom parse_obj.
RuleAction = Annotated[
    Union[
        DamageAction, HealAction, ShieldAction, StatusAction, ApplyBuffAction,
        RemoveBuffAction, ResetAttackAction, ModifyCooldownAction, CustomAction
    ],
    Field(discriminator="type_")
]


class TriggerFilter(StrictModel):
    source: list[ActionType] | None = None


class Condition(StrictModel):
    actor: Target
    key: str
    comparison: Comparison
    value: str


class Rule(StrictModel):
    trigger: Trigger | None = None
    filter: TriggerFilter | None = None
    outcome: str | None = None
    conditions: list[Condition] = []
    actions: list[RuleAction] = []
    delay: str = "0"
    speed: str = "0"
    cooldown: str = "0"


class StatModifier(StrictModel):
    stat: Stat
    formula: str
    mode: StatMode = StatMode.FLAT
    conversion: bool = False


class Buff(StrictModel):
    name: str
    duration: str = "0"
    max_stacks: int = Field(1, ge=1)
    refresh: bool = True
    interval: str = "0"
    # Slots that may start during the windup of an attack made while this buff is active; the hit still lands.
    windup_cancel: list[ActionType] = []
    stats: list[StatModifier] = []
    rules: list[Rule] = []

    @validator("name")
    def name_is_identifier(cls, name: str) -> str:
        # Formulas read stacks as `stacks_<name>`, so the name must be a valid Python identifier.
        if not name.isidentifier():
            raise ValueError(f"Buff name '{name}' must be a valid identifier, e.g. 'silver_bolts'")
        return name


class Stage(StrictModel):
    recast_window: str = "0"
    outcomes: list[str] = []
    rules: list[Rule] = []

    @validator("rules")
    def outcomes_are_declared(cls, rules: list[Rule], values: dict) -> list[Rule]:
        declared = values.get("outcomes", [])
        for rule in rules:
            if rule.outcome is not None and rule.outcome not in declared:
                raise ValueError(f"Outcome '{rule.outcome}' is not one of the stage's outcomes {declared}")
        return rules
