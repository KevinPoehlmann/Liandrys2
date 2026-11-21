from dataclasses import replace

from src.server.models.dataenums import ActionType, CostResource, DamageSubType, Origin, RuleActionType, Stat, Target
from src.server.models.pet import Pet
from src.server.models.rule import DamageAction, DamageProps, Rule
from src.server.simulation.character import Character
from src.server.simulation.formula import FormulaContext, evaluate_formula


class PetCharacter(Character):
    """A summoned unit: stats come from formulas, it has a passive and a basic attack but no abilities."""

    def __init__(self, definition: Pet, owner: Character, slot: ActionType) -> None:
        self.definition: Pet = definition
        self.owner: Character = owner
        self.summon_slot: ActionType = slot
        self.name: str = definition.name
        self.passive = definition.passive
        self.expired: bool = False
        self._setup(owner.level, [], {}, {})


    def _casting_resource(self) -> CostResource:
        return CostResource.NONE

    def origin(self, slot: ActionType, buff: str | None = None) -> Origin:
        # Everything a pet does belongs to the ability that summoned it; the actor id tells the pet apart.
        return self.owner.origin(self.summon_slot, buff)

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

    def _attack_windup(self) -> float:
        return self.definition.attack.windup

    def _basic_attack_rule(self, blinded: bool) -> Rule:
        attack = self.definition.attack
        damage = DamageAction(type_=RuleActionType.DAMAGE, props=DamageProps(
            target=Target.TARGET,
            scaling="0" if blinded else attack.scaling,
            dmg_type=attack.dmg_type,
            dmg_sub_type=attack.dmg_sub_type
        ))
        return Rule(actions=[damage], speed=str(attack.missile_speed))
