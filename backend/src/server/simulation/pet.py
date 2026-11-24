from dataclasses import replace

from src.server.models.enums import ActionType, CostResource, DamageSubType, RuleActionType, Stat, Target
from src.server.models.result import Origin
from src.server.models.pet import Pet
from src.server.models.rule import DamageAction, DamageProps, Rule
from src.server.simulation.character import Character
from src.server.simulation.formula import FormulaContext, evaluate_formula


class PetCharacter(Character):
    """A summoned unit: stats come from formulas, it has a passive and a basic attack but no abilities."""
    is_champion: bool = False

    @property
    def is_ranged(self) -> bool:
        return self.definition.attack.missile_speed > 0

    def __init__(self, definition: Pet, owner: Character, slot: ActionType) -> None:
        self.definition: Pet = definition
        self.owner: Character = owner
        self.summon_slot: ActionType = slot
        self.name: str = definition.name
        self.passive = definition.passive
        self.expired: bool = False
        self.extra_slots: dict = {}
        self._setup(owner.level, [], {}, {})


    def _casting_resource(self) -> CostResource:
        return CostResource.NONE

    def origin(self, slot: ActionType, buff: str | None = None, active: bool = False) -> Origin:
        # Everything a pet does belongs to the ability that summoned it; the actor id tells the pet apart.
        return self.owner.origin(self.summon_slot, buff, active)

    def formula_context(self, slot: ActionType, target: Character | None = None, stacks: int = 0, elapsed: float = 0.0) -> FormulaContext:
        # Every pet formula uses the rank of the summoning ability (by_rank) and the owner's inputs.
        context = self.owner.formula_context(self.summon_slot, target, stacks, elapsed)
        return replace(context, source=self, owner=self.owner)

    def get_base_stat(self, stat: Stat) -> float:
        formula = self.definition.stats.get(stat)
        return evaluate_formula(formula, self.formula_context(ActionType.PASSIVE)) if formula else 0

    def _get_attackspeed(self) -> float:
        # Pets have no attack speed ratio: bonus attack speed scales the base value.
        base = self.get_base_stat(Stat.ATTACKSPEED_P)
        return base * (1 + self._get_bonus_stat(Stat.ATTACKSPEED_P)) * self._get_cripple_value()

    def get_penetration(self, dmg_sub_type: DamageSubType) -> tuple[float, float]:
        # Tibbers uses Annie's penetration (checked in game).
        return self.owner.get_penetration(dmg_sub_type)

    def windup_time(self, attack_time: float) -> float:
        return attack_time * self.definition.attack.windup

    def _basic_attack_rule(self, blinded: bool) -> Rule:
        attack = self.definition.attack
        damage = DamageAction(type_=RuleActionType.DAMAGE, props=DamageProps(
            target=Target.TARGET,
            amount="0" if blinded else attack.amount,
            dmg_type=attack.dmg_type,
            dmg_sub_type=attack.dmg_sub_type
        ))
        return Rule(actions=[damage], speed=str(attack.missile_speed))
