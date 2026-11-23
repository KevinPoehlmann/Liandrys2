from typing import Annotated, Literal, Union

from pydantic import BaseModel, Extra, Field, validator

from src.server.models.dataenums import (
    ActionType,
    Comparison,
    CostResource,
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
    can_crit: bool = False  # crits with the attack it belongs to (Crippling Strike yes, Tumble no)

class ExecuteProps(StrictModel):
    target: Target

class AttackProps(StrictModel):
    """An attack an ability makes on its own (Urgot's Purge): its own cast instance, on-attack and on-hit effects, basic damage."""
    target: Target
    scaling: str
    can_crit: bool = False
    on_hit_factor: str = "1"  # on-hit and on-attack damage of this attack (Purge: 50 %)
    attack_speed: str | None = None  # sets the windup; None = the champion's attack speed (Purge: fixed 3.0)

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
    stacks: str | None = None  # None removes the whole buff

class ResetAttackProps(StrictModel):
    pass

class ModifyCooldownProps(StrictModel):
    slot: ActionType
    amount: str = "0"
    reset: bool = False

class SummonProps(StrictModel):
    pet: str

class PayCostProps(StrictModel):
    resource: CostResource
    amount: str

class CleanseProps(StrictModel):
    """Removes the listed status types and every buff with one of the tags (Cleanse, QSS and Mikael's differ in both)."""
    target: Target
    statuses: list[StatusType] = []
    buff_tags: list[str] = []

class LockProps(StrictModel):
    """The owner can't attack or cast for `duration` seconds, except the listed slots (Sanguine Pool: summoners, items)."""
    duration: str
    exceptions: list[ActionType] = []

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

class SummonAction(StrictModel):
    type_: Literal[RuleActionType.SUMMON]
    props: SummonProps

class PayCostAction(StrictModel):
    type_: Literal[RuleActionType.PAY_COST]
    props: PayCostProps

class CleanseAction(StrictModel):
    type_: Literal[RuleActionType.CLEANSE]
    props: CleanseProps

class LockAction(StrictModel):
    type_: Literal[RuleActionType.LOCK]
    props: LockProps

class ExecuteAction(StrictModel):
    type_: Literal[RuleActionType.EXECUTE]
    props: ExecuteProps

class AttackAction(StrictModel):
    type_: Literal[RuleActionType.ATTACK]
    props: AttackProps

class CustomAction(StrictModel):
    type_: Literal[RuleActionType.CUSTOM]
    props: CustomProps


# The discriminator picks the action class by `type_`, so nested parsing needs no custom parse_obj.
RuleAction = Annotated[
    Union[
        DamageAction, HealAction, ShieldAction, StatusAction, ApplyBuffAction,
        RemoveBuffAction, ResetAttackAction, ModifyCooldownAction, SummonAction, PayCostAction, LockAction, CleanseAction, ExecuteAction, AttackAction, CustomAction
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
    speed: str = "0"  # missile start speed, 0 = instant
    acceleration: str = "0"
    max_speed: str = "0"  # 0 = no cap
    cooldown: str = "0"
    # Seconds before the same cast instance can trigger this rule again on the same target; "inf" = once (Electrocute).
    cast_cooldown: str | None = None


class StatModifier(StrictModel):
    stat: Stat
    formula: str
    mode: StatMode = StatMode.FLAT
    conversion: bool = False
    snapshot: bool = False  # on a buff: evaluated once when the buff is applied (Riven R's bonus AD)


class SlowedWhile(StrictModel):
    """While `buff` is on the bearer, this buff's time runs at `rate` (Crimson Rush drains 75% slower in Sanguine Pool)."""
    buff: str
    rate: float = Field(..., gt=0, lt=1)


class Buff(StrictModel):
    name: str
    duration: str = "0"
    max_stacks: int = Field(1, ge=0)  # 0 = unlimited (Veigar's Phenomenal Evil)
    refresh: bool = True
    interval: str = "0"
    tick_on_apply: bool = False
    tick_on_end: bool = False
    # Slots that may start during the windup of an attack made while this buff is active; the hit still lands.
    windup_cancel: list[ActionType] = []
    slowed_while: list[SlowedWhile] = []
    tags: list[str] = []  # e.g. "summoner_debuff", for Cleanse
    blocks: list[ActionType] = []  # slots its bearer can't use while it is active; they wait (no attacks during Purge)
    stats: list[StatModifier] = []
    rules: list[Rule] = []

    @validator("name")
    def name_is_identifier(cls, name: str) -> str:
        # Formulas read stacks as `stacks_<name>`, so the name must be a valid Python identifier.
        if not name.isidentifier():
            raise ValueError(f"Buff name '{name}' must be a valid identifier, e.g. 'silver_bolts'")
        return name


class Input(StrictModel):
    """A value the user chooses for the scenario, e.g. Annie's Pyromania stacks at the start."""
    name: str
    default: float = 0
    min: float | None = None
    max: float | None = None
    description: str = ""

    @validator("name")
    def name_is_identifier(cls, name: str) -> str:
        # Formulas read the input by its name.
        if not name.isidentifier():
            raise ValueError(f"Input name '{name}' must be a valid identifier, e.g. 'pyromania_start'")
        return name


class Stage(StrictModel):
    recast_window: str = "0"  # seconds after the previous stage's cast to cast this one, else the ability starts over
    recast_delay: str = "0"  # earliest seconds after the previous stage's cast (Riven Q: 0.3125)
    outcomes: list[str] = []
    rules: list[Rule] = []

    @validator("rules")
    def outcomes_are_declared(cls, rules: list[Rule], values: dict) -> list[Rule]:
        declared = values.get("outcomes", [])
        for rule in rules:
            if rule.outcome is not None and rule.outcome not in declared:
                raise ValueError(f"Outcome '{rule.outcome}' is not one of the stage's outcomes {declared}")
        return rules
