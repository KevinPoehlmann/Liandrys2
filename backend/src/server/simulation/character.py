from collections import defaultdict
from typing import Iterator, NamedTuple
import math

from src.server.models.ability import Ability
from src.server.models.ability import Ability
from src.server.models.dataenums import (
    ActionEffect,
    ActionType,
    Actor,
    CostResource,
    DamageSubType,
    DamageType,
    EffectResult,
    EffectType,
    Origin,
    OriginKind,
    ProcessedCostProperties,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    ProcessedStatusProperties,
    QueueComponent,
    ResourceType,
    RuleActionType,
    Stat,
    StatMode,
    StatusType,
    Target,
    Trigger,
    TICK_SECONDS,
    to_ticks
)
from src.server.models.champion import Champion
from src.server.models.item import Item
from src.server.models.passive import Passive
from src.server.models.pet import Pet
from src.server.models.request import Rank, Action
from src.server.models.rule import (
    Buff as BuffDefinition, DamageAction, DamageProps, Input, PayCostAction, PayCostProps, Rule, Stage, StatModifier
)
from src.server.models.summonerspell import Summonerspell
from src.server.simulation.buff_instance import BuffInstance
from src.server.simulation.events import RuleEvent
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.formula import FormulaContext, evaluate_formula

MULTIPLICATIVE_STATS = {Stat.ARMOR_PEN_P, Stat.MAGIC_PEN_P, Stat.TENACITY_P}
# Damage amplifications from several sources multiply (Hemoplague notes).
COMPOUNDING_STATS = {Stat.DAMAGE_TAKEN_P}

# Health, mana and energy regenerate every 0.5 s (16 engine loops), a tenth of the "per 5 seconds" stat each time.
REGEN_TICKS = to_ticks(0.5)
CASTING_RESOURCES = {ResourceType.MANA: CostResource.MANA, ResourceType.ENERGY: CostResource.ENERGY}

SUMMONER_SLOTS = (ActionType.S1, ActionType.S2)
ITEM_SLOTS = (ActionType.I1, ActionType.I2, ActionType.I3, ActionType.I4, ActionType.I5, ActionType.I6)


class ShieldInstance(NamedTuple):
    expires: int
    value: float
    source: ActionType
    actor: Actor
    origin: Origin | None


SLOT_COOLDOWN_REDUCTION = {
    ActionType.Q: Stat.Q_COOLDOWN_REDUCTION,
    ActionType.W: Stat.W_COOLDOWN_REDUCTION,
    ActionType.E: Stat.E_COOLDOWN_REDUCTION,
    ActionType.R: Stat.R_COOLDOWN_REDUCTION,
}


def soft_cap_movespeed(speed: float) -> float:
    # League's movement speed soft caps (see docs/league-mechanics.md).
    if speed > 490:
        return speed * 0.5 + 230
    if speed > 415:
        return speed * 0.8 + 83
    if speed >= 220:
        return speed
    if speed >= 0:
        return 110 + speed * 0.5
    return 110 + speed * 0.01


class Character():
    is_champion: bool = True
    def __init__(self, champion: Champion, lvl: int, rank: Rank ,items: list[Item], scenario: dict[str, float] | None = None,
                 summonerspells: list[Summonerspell] | None = None) -> None:
        self.champion: Champion = champion
        self.name: str = champion.name
        self.passive: Passive = champion.passive
        ability_dict = {
            ActionType.Q: (champion.q, rank.q),
            ActionType.W: (champion.w, rank.w),
            ActionType.E: (champion.e, rank.e),
            ActionType.R: (champion.r, rank.r)
        }
        # Summoner spells run like abilities in the slots S1 and S2, always at rank 1.
        spells = dict(zip(SUMMONER_SLOTS, summonerspells or []))
        ability_dict |= {slot: (spell.ability, 1) for slot, spell in spells.items()}
        self.summoner_names: dict[ActionType, str] = {slot: spell.name for slot, spell in spells.items()}
        self._setup(lvl, items, ability_dict, scenario or {})


    def _setup(self, level: int, items: list[Item], ability_dict: dict[ActionType, tuple[Ability, int]], scenario: dict[str, float]) -> None:
        self.current_tick: int = 0
        self.level: int = level
        self.items: list[Item] = items
        self.shields: list[ShieldInstance] = []
        self.status_effects: dict[StatusType, list[tuple[int, float]]] = defaultdict(list)

        self.evaluating_stat: set = set()
        self.ignoring_conversions: bool = False

        self.ability_dict: dict[ActionType, tuple[Ability, int]] = ability_dict
        self.item_slots: dict[ActionType, Item] = dict(zip(ITEM_SLOTS, items))
        self.item_passives: list[tuple[Passive, ActionType]] = self._item_passives()
        self.scenario: dict[str, float] = self._scenario(scenario)
        self.cooldowns: dict[ActionType, int] = {
            ActionType.BA: 0,
            ActionType.Q: 0,
            ActionType.W: 0,
            ActionType.E: 0,
            ActionType.R: 0,
        } | {slot: 0 for slot in ability_dict}
        self.pet_definitions: dict[str, tuple[Pet, ActionType]] = {
            pet.name: (pet, slot) for slot, (ability, _) in self.ability_dict.items() for pet in ability.pets
        }
        self.buff_definitions: dict[str, tuple[BuffDefinition, ActionType]] = self._collect_buff_definitions()
        self.active_buffs: dict[str, BuffInstance] = {}
        self.pending_cooldowns: dict[str, tuple[ActionType, int]] = {}
        self.locked_until: int = 0
        # Slot -> (index of the next stage, tick of the previous cast) while a recast is possible.
        self.recasts: dict[ActionType, tuple[int, int]] = {}
        self.lock_exceptions: set[ActionType] = set()
        self.current_hp: float = self.get_stat(Stat.HP)
        self.resource: CostResource = self._casting_resource()
        self.current_resource: float = self._max_resource()
        self.last_regen_tick: int = 0
        self.damage_taken: float = 0
        self.healed: float = 0
        self.damage_shielded: float = 0


    def _item_passives(self) -> list[tuple[Passive, ActionType]]:
        # A unique passive is a shared named effect (Spellblade): several items give it only once.
        passives, unique_names = [], set()
        for slot, item in self.item_slots.items():
            for passive in item.passives:
                if passive.unique:
                    if passive.name in unique_names:
                        continue
                    unique_names.add(passive.name)
                passives.append((passive, slot))
        return passives

    def _collect_buff_definitions(self) -> dict[str, tuple[BuffDefinition, ActionType]]:
        containers = [(self.passive, ActionType.PASSIVE)]
        containers += [(ability, slot) for slot, (ability, _) in self.ability_dict.items()]
        containers += self.item_passives
        # The owner can apply its pets' buffs too, e.g. Annie's stun enrages Tibbers.
        containers += [(pet.passive, slot) for pet, slot in self.pet_definitions.values()]
        definitions = {}
        for container, slot in containers:
            for buff in container.buffs:
                if buff.name in definitions:
                    raise ValueError(f"Buff '{buff.name}' is defined twice for {self.name}")
                definitions[buff.name] = (buff, slot)
        return definitions


    def _scenario(self, given: dict[str, float]) -> dict[str, float]:
        inputs = {declared.name: declared for declared in self._declared_inputs()}
        unknown = set(given) - set(inputs)
        if unknown:
            raise ValueError(f"Unknown scenario inputs for {self.name}: {sorted(unknown)}")
        for name, value in given.items():
            declared = inputs[name]
            if (declared.min is not None and value < declared.min) or (declared.max is not None and value > declared.max):
                raise ValueError(f"Scenario input '{name}' must be between {declared.min} and {declared.max}, got {value}")
        return {name: given.get(name, declared.default) for name, declared in inputs.items()}

    def _declared_inputs(self) -> list[Input]:
        containers = [self.passive] + [ability for ability, _ in self.ability_dict.values()]
        containers += [passive for passive, _ in self.item_passives]
        return [declared for container in containers for declared in container.inputs]


    def get_rank(self, slot: ActionType) -> int:
        return self.ability_dict[slot][1] if slot in self.ability_dict else 0

    def get_buff_stacks(self, buff: str) -> int:
        instance = self.active_buffs.get(buff)
        return instance.stacks if instance else 0

    def formula_context(self, slot: ActionType, target: "Character | None" = None, stacks: int = 0, elapsed: float = 0.0) -> FormulaContext:
        max_rank = getattr(self.ability_dict[slot][0], "maxrank", 0) if slot in self.ability_dict else 0
        return FormulaContext(source=self, target=target, rank=self.get_rank(slot), max_rank=max_rank,
                              stacks=stacks, elapsed=elapsed, slot=slot, scenario=self.scenario)

    def buff_elapsed(self, instance: BuffInstance) -> float:
        return (self.current_tick - instance.start) * TICK_SECONDS


    def apply_buff(self, name: str, source: "Character", stacks: int, tick: int) -> BuffInstance:
        definition, slot = source.buff_definitions[name]
        end = self._buff_end(definition, source.formula_context(slot), tick)
        instance = self.active_buffs.get(name)
        if instance is None:
            instance = BuffInstance(definition, source, slot, 0, tick, end)
            self.active_buffs[name] = instance
        elif definition.refresh:
            instance.end = end
            instance.rate = 1.0
        instance.stacks += stacks
        if definition.max_stacks:
            instance.stacks = min(instance.stacks, definition.max_stacks)
        self._take_snapshots(instance)
        return instance

    def _take_snapshots(self, instance: BuffInstance) -> None:
        # Evaluated without the buff's own snapshot values, so `0.2 * ad` doesn't count itself on a refresh.
        instance.snapshots = {}
        context = instance.source.formula_context(instance.slot, stacks=instance.stacks)
        instance.snapshots = {
            index: self._evaluate_modifier(modifier, context)
            for index, modifier in enumerate(instance.definition.stats) if modifier.snapshot
        }

    @staticmethod
    def _buff_end(definition: BuffDefinition, context: FormulaContext, tick: int) -> int | None:
        duration = evaluate_formula(definition.duration, context)
        return tick + to_ticks(duration) if duration > 0 else None

    def remove_buff(self, name: str, tick: int) -> None:
        if self.active_buffs.pop(name, None) and name in self.pending_cooldowns:
            slot, cooldown_ticks = self.pending_cooldowns.pop(name)
            self.cooldowns[slot] = tick + cooldown_ticks

    def remove_stacks(self, name: str, stacks: int, tick: int) -> None:
        instance = self.active_buffs.get(name)
        if instance is None:
            return
        instance.stacks -= stacks
        if instance.stacks <= 0:
            self.remove_buff(name, tick)

    def expire_buff(self, name: str, end: int) -> None:
        # A refresh moves `end`, so an end event of an older `end` is outdated and ignored.
        instance = self.active_buffs.get(name)
        if instance and instance.end == end:
            self.remove_buff(name, end)


    def triggered_rules(self, trigger: Trigger, source: ActionType) -> list[tuple[Rule, ActionType, "Character", str | None]]:
        candidates = [(rule, ActionType.PASSIVE, self, None) for rule in self.passive.rules]
        candidates += [
            (rule, slot, self, None)
            for slot, (ability, rank) in self.ability_dict.items() if rank > 0
            for rule in ability.rules
        ]
        candidates += [(rule, slot, self, None) for passive, slot in self.item_passives for rule in passive.rules]
        candidates += [
            (rule, instance.slot, instance.source, name)
            for name, instance in self.active_buffs.items()
            for rule in instance.definition.rules
        ]
        return [
            candidate for candidate in candidates
            if candidate[0].trigger == trigger and self._passes_filter(candidate[0], source)
        ]

    @staticmethod
    def _passes_filter(rule: Rule, source: ActionType) -> bool:
        return rule.filter is None or rule.filter.source is None or source in rule.filter.source

    def reset_attack(self, tick: int) -> None:
        self.cooldowns[ActionType.BA] = tick

    def origin(self, slot: ActionType, buff: str | None = None) -> Origin:
        if slot == ActionType.BA:
            return Origin(kind=OriginKind.ATTACK, name="BA", buff=buff)
        if slot == ActionType.PASSIVE:
            return Origin(kind=OriginKind.PASSIVE, name="passive", buff=buff)
        if slot in self.summoner_names:
            return Origin(kind=OriginKind.SUMMONER, name=self.summoner_names[slot], buff=buff)
        if slot in self.item_slots:
            return Origin(kind=OriginKind.ITEM, name=self.item_slots[slot].name, buff=buff)
        return Origin(kind=OriginKind.ABILITY, name=slot.value.upper(), buff=buff)

    def _healing_factor(self, tick: int) -> float:
        # Grievous Wounds doesn't stack, the strongest counts. It reduces heals and health regeneration, not shields.
        reductions = [strength for end, strength in self.status_effects.get(StatusType.GRIEVOUS_WOUNDS, []) if end > tick]
        return 1 - max(reductions, default=0)

    def cleanse(self, statuses: list[StatusType], buff_tags: list[str], tick: int) -> None:
        for status in statuses:
            self.status_effects.pop(status, None)
        for name, instance in list(self.active_buffs.items()):
            if set(instance.definition.tags) & set(buff_tags):
                self.remove_buff(name, tick)

    def is_untargetable(self, tick: int) -> bool:
        return any(end > tick for end, _ in self.status_effects.get(StatusType.UNTARGETABLE, []))

    def _casting_resource(self) -> CostResource:
        return CASTING_RESOURCES.get(self.champion.resource_type, CostResource.NONE)

    def _max_resource(self) -> float:
        # Mana and energy share the champion's mana fields (Shen's 400 energy comes from the data).
        return self.get_stat(Stat.MANA) if self.resource != CostResource.NONE else 0

    def _pool(self, resource: CostResource) -> tuple[float, float, float]:
        """Current value, maximum and gain per regeneration tick."""
        if resource == CostResource.HEALTH:
            return self.current_hp, self.get_stat(Stat.HP), self._regen_per_tick(Stat.HP_REG, Stat.HP_REG_P)
        if resource != self.resource:
            raise ValueError(f"{self.name} has no {resource.value} (uses {self.resource.value})")
        return self.current_resource, self._max_resource(), self._regen_per_tick(Stat.MANA_REG, Stat.MANA_REG_P)

    def _regen_per_tick(self, stat: Stat, base_percent: Stat) -> float:
        per_5_seconds = self.get_base_stat(stat) * (1 + self._get_bonus_stat(base_percent)) + self._get_bonus_stat(stat)
        return per_5_seconds / 10

    @staticmethod
    def _enough(resource: CostResource, amount: float, value: float) -> bool:
        # A health cost can't kill: without more health than it costs the cast isn't possible (Dr. Mundo).
        return value > amount if resource == CostResource.HEALTH else value >= amount

    def regenerate(self, tick: int, actor: Actor) -> list[tuple[int, EffectResult]]:
        results = []
        while self.last_regen_tick + REGEN_TICKS <= tick:
            self.last_regen_tick += REGEN_TICKS
            pools = [CostResource.HEALTH] + ([self.resource] if self.resource != CostResource.NONE else [])
            for resource in pools:
                value, maximum, gain = self._pool(resource)
                if resource == CostResource.HEALTH:
                    gain *= self._healing_factor(self.last_regen_tick)
                gain = min(gain, maximum - value)  # nothing at full
                if gain > 0:
                    self._change_pool(resource, gain)
                    result = EffectResult(source=ActionType.PASSIVE, actor=actor, target=actor, type_=EffectType.REGEN, value=gain,
                                          resource=resource, origin=Origin(kind=OriginKind.REGEN, name=resource.value))
                    results.append((self.last_regen_tick, result))
        return results

    def _change_pool(self, resource: CostResource, amount: float) -> None:
        if resource == CostResource.HEALTH:
            self.current_hp += amount
        else:
            self.current_resource += amount

    def ability_cost(self, slot: ActionType) -> tuple[CostResource, float] | None:
        ability = self.ability_dict[slot][0] if slot in self.ability_dict else None
        if ability is None or ability.cost_resource == CostResource.NONE:
            return None
        return ability.cost_resource, evaluate_formula(ability.cost, self.formula_context(slot))

    def resource_ready(self, slot: ActionType, tick: int) -> int:
        """The first tick from `tick` on with enough resource for the slot's cost, counting regeneration."""
        cost = self.ability_cost(slot)
        if cost is None:
            return tick
        resource, amount = cost
        value, maximum, gain = self._pool(resource)
        if not self._enough(resource, amount, maximum) or (gain <= 0 and not self._enough(resource, amount, value)):
            raise ValueError(f"{slot.value} costs {amount:.0f} {resource.value}, {self.name} can never have that much")
        regen_tick = self.last_regen_tick + REGEN_TICKS
        while regen_tick <= tick:
            value, regen_tick = min(maximum, value + gain), regen_tick + REGEN_TICKS
        while not self._enough(resource, amount, value):
            value, tick, regen_tick = min(maximum, value + gain), regen_tick, regen_tick + REGEN_TICKS
        return tick

    def pay_cost(self, resource: CostResource, amount: float, source: ActionType, actor: Actor, origin: Origin | None = None) -> EffectResult:
        value, _, _ = self._pool(resource)
        if amount > 0 and not self._enough(resource, amount, value):
            raise ValueError(f"Not enough {resource.value} for {source.value}: it costs {amount:.0f}, {self.name} has {value:.0f}")
        self._change_pool(resource, -amount)
        return EffectResult(source=source, actor=actor, target=actor, type_=EffectType.COST, value=amount, resource=resource, origin=origin)

    def _cost_event(self, action: Action) -> list[RuleEvent]:
        # Checked when the cast starts, paid when it ends, so an interrupted cast costs nothing.
        ability = self.ability_dict[action.action_type][0]
        if ability.cost_resource == CostResource.NONE:
            return []
        pay = PayCostAction(type_=RuleActionType.PAY_COST, props=PayCostProps(resource=ability.cost_resource, amount=ability.cost))
        return [RuleEvent(rule=Rule(actions=[pay]), slot=action.action_type, owner=action.actor, target=action.target)]

    def lock(self, until: int, exceptions: set[ActionType]) -> None:
        self.locked_until = until
        self.lock_exceptions = exceptions


    def get_base_stat(self, stat: Stat) -> float:
        stat_name = stat.value
        base_value = getattr(self.champion, stat_name, None)
        if base_value is None:
            return 0    
        scaling_attr = f"{stat_name}_per_lvl"
        scaling_value = getattr(self.champion, scaling_attr, 0)
        return base_value + scaling_value * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1))

    def _get_bonus_stat(self, stat: Stat) -> float:
        values = [item.stats[stat] for item in self.items if stat in item.stats]
        # A modifier formula evaluates all stats, including the one being modified. The guard stops that recursion.
        if stat not in self.evaluating_stat:
            self.evaluating_stat.add(stat)
            try:
                values += self._modifier_values(stat)
            finally:
                self.evaluating_stat.discard(stat)
        if stat in MULTIPLICATIVE_STATS:
            # Percent penetration from several sources stacks multiplicatively (Darius E notes).
            return 1 - math.prod(1 - value for value in values)
        if stat in COMPOUNDING_STATS:
            return math.prod(1 + value for value in values) - 1
        return sum(values)

    def _modifier_values(self, stat: Stat) -> list[float]:
        return [
            fixed if fixed is not None else self._evaluate_modifier(modifier, context)
            for modifier, context, fixed in self._active_modifiers()
            if modifier.stat == stat and not (modifier.conversion and self.ignoring_conversions)
        ]

    def _active_modifiers(self) -> Iterator[tuple[StatModifier, FormulaContext | None, float | None]]:
        """Modifier, the context to evaluate it in, or its fixed value (snapshot)."""
        for modifier in self.passive.stats:
            yield modifier, self.formula_context(ActionType.PASSIVE), None
        for slot, (ability, rank) in self.ability_dict.items():
            if rank > 0:
                for modifier in ability.stats:
                    yield modifier, self.formula_context(slot), None
        for passive, slot in self.item_passives:
            for modifier in passive.stats:
                yield modifier, self.formula_context(slot), None
        for instance in self.active_buffs.values():
            for index, modifier in enumerate(instance.definition.stats):
                if modifier.snapshot:
                    if index in instance.snapshots:
                        yield modifier, None, instance.snapshots[index]
                    continue
                yield modifier, instance.source.formula_context(instance.slot, stacks=instance.stacks, elapsed=self.buff_elapsed(instance)), None

    def _evaluate_modifier(self, modifier: StatModifier, context: FormulaContext) -> float:
        if modifier.mode != StatMode.FLAT:
            raise NotImplementedError(f"Stat modifier mode '{modifier.mode}' is not supported yet")
        if not modifier.conversion:
            return evaluate_formula(modifier.formula, context)
        # A conversion only sees stats without conversions, so two of them can't feed each other (Vladimir's passive).
        outer, self.ignoring_conversions = self.ignoring_conversions, True
        try:
            return evaluate_formula(modifier.formula, context)
        finally:
            self.ignoring_conversions = outer


    def get_stat(self, stat: Stat) -> float:
        if stat.value.startswith("bonus "):
            return self._get_bonus_stat(Stat.from_str(stat.value.removeprefix("bonus ")))
        
        if stat == Stat.ATTACKSPEED_P:
            return self._get_attackspeed()
        if stat == Stat.MOVESPEED:
            return self._get_movespeed()
        
        result = self.get_base_stat(stat) + self._get_bonus_stat(stat)
        return result

    def _get_movespeed(self) -> float:
        flat = self.get_base_stat(Stat.MOVESPEED) + self._get_bonus_stat(Stat.MOVESPEED)
        raw = flat * (1 + self._get_bonus_stat(Stat.MOVESPEED_P)) * self._get_slow_value()
        return soft_cap_movespeed(raw)

    def _get_attackspeed(self) -> float:
        bonus = self.champion.attackspeed_per_lvl * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1))
        bonus += self._get_bonus_stat(Stat.ATTACKSPEED_P)
        result = self.champion.attackspeed + self.champion.attackspeed_ratio * bonus
        result *= self._get_cripple_value()
        return result
    
    def get_penetration(self, dmg_sub_type: DamageSubType) -> tuple[float, float]:
        if dmg_sub_type == DamageSubType.PHYSIC:
            flat_pen = self._get_bonus_stat(Stat.LETHALITY)
            percent_pen = self._get_bonus_stat(Stat.ARMOR_PEN_P)
        elif dmg_sub_type == DamageSubType.MAGIC:
            flat_pen = self._get_bonus_stat(Stat.MAGIC_PEN)
            percent_pen = self._get_bonus_stat(Stat.MAGIC_PEN_P)
        else:
            flat_pen = 0
            percent_pen = 0
        return (flat_pen, percent_pen)
    
    def _get_resistance(self, dmg_sub_type: DamageSubType) -> float:
        if dmg_sub_type == DamageSubType.PHYSIC:
            return self.get_stat(Stat.ARMOR)
        elif dmg_sub_type == DamageSubType.MAGIC:
            return self.get_stat(Stat.MR)
        else:
            return 0
        
    def _cc_duration_factor(self) -> float:
        # Tenacity from several sources stacks multiplicatively, like percent penetration.
        return 1 - self.get_stat(Stat.TENACITY_P)
        
    def _get_slow_value(self) -> float:
        #self.remove_expired_status_effects()
        if not self.status_effects[StatusType.SLOW]:
            return 1.0
        return 1 - max(effect[1] for effect in self.status_effects[StatusType.SLOW])

    def _get_cripple_value(self) -> float:
        #self.remove_expired_status_effects()
        if not self.status_effects[StatusType.CRIPPLE]:
            return 1.0
        return math.prod(1 - effect[1] for effect in self.status_effects[StatusType.CRIPPLE])
        

    def _remove_expired_status_effects(self, tick: int) -> None:
        for status, effects in list(self.status_effects.items()):
            self.status_effects[status] = [(exp, strength) for exp, strength in effects if exp > tick]
            if not self.status_effects[status]:
                del self.status_effects[status]


        
    def _calculate_damage(self, damage: ProcessedDamageProperties) -> tuple[float, float, float]:
        value = damage.value
        resistance = self._get_resistance(damage.dmg_sub_type)
        resistance -= (resistance * damage.percent_pen)
        resistance -= damage.flat_pen
        resistance = max(resistance, 0)
        result = value * (100 / (resistance + 100))
        if damage.dmg_sub_type != DamageSubType.TRUE:
            # True damage isn't amplified (wiki: Hemoplague, probably an old state of the ability).
            result *= 1 + self.get_stat(Stat.DAMAGE_TAKEN_P)
        return result, value, value - result
    

    def _use_shields(self, damage: float, target: Actor) -> tuple[float, list[EffectResult]]:
        results = []
        for i, (exp, shield_val, source, actor, origin) in enumerate(self.shields):
            if damage <= 0:
                break
            if shield_val <= 0:
                continue
            absorbed = min(damage, shield_val)
            self.damage_shielded += absorbed
            damage -= absorbed
            self.shields[i] = ShieldInstance(exp, shield_val - absorbed, source, actor, origin)
            results.append(EffectResult(
                source=source,
                actor=actor,
                target=target,
                type_=EffectType.SHIELD,
                value=absorbed,
                origin=origin
            ))
        return damage, results


    def _apply_heals(self, components: list[QueueComponent], tick: int | None = None) -> list[EffectResult]:
        total_heal = 0
        missing_hp = self.get_stat(Stat.HP) - self.current_hp
        factor = self._healing_factor(self.current_tick if tick is None else tick)
        results = []
        for component in components:
            try:
                assert isinstance(component.props, ProcessedHealProperties), "Heal component must have ProcessedHealProperties"
                raw_heal = component.props.value
                reduced = raw_heal * factor
                heal = min(reduced, max(missing_hp - total_heal, 0))
                total_heal += heal
                results.append(EffectResult(
                    source=component.source,
                    actor=component.actor,
                    target=component.target,
                    type_=EffectType.HEAL,
                    value=heal,
                    raw=raw_heal,
                    overheal=reduced - heal,
                    origin=component.origin
                ))
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="heal application"
                ) from e
        self.healed += total_heal
        self.current_hp += total_heal
        return results
    

    def _apply_shields(self, components: list[QueueComponent], tick: int) -> None:
        self.shields = [shield for shield in self.shields if shield[0] > tick and shield[1] > 0]
        for component in components:
            try:
                assert isinstance(component.props, ProcessedShieldProperties), "Shield component must have ProcessedShieldProperties"
                self.shields.append(ShieldInstance(component.props.duration + tick, component.props.value, component.source, component.actor, component.origin))
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="shield application"
                ) from e
        self.shields.sort(key=lambda shield: (shield[0], shield[1]))
    

    def _apply_damages(self, components: list[QueueComponent]) -> tuple[list[QueueComponent], list[EffectResult]]:
        if not components:
            return [], []
        total_damage = 0
        vamps = []
        results = []
        for component in components:
            try:
                assert isinstance(component.props, ProcessedDamageProperties), "Damage component must have ProcessedDamageProperties"
                damage, raw_dmg, mitigated = self._calculate_damage(component.props)
                health_damage, shield_results = self._use_shields(damage, component.target)
                total_damage += health_damage
                results.append(EffectResult(
                    source=component.source,
                    actor=component.actor,
                    target=component.target,
                    type_=EffectType.DAMAGE,
                    value=health_damage,
                    raw=raw_dmg,
                    mitigated=mitigated,
                    damage_sub_type=component.props.dmg_sub_type,
                    origin=component.origin
                ))
                results.extend(shield_results)
                if component.props.vamp > 0:
                    vamp = damage * component.props.vamp
                    vamps.append(QueueComponent(
                        source=component.source,
                        actor=component.actor,
                        target=component.actor,
                        type_=EffectType.HEAL,
                        props=ProcessedHealProperties(value=vamp),
                        origin=component.origin
                    ))
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="damage application"
                ) from e
        self.damage_taken += total_damage
        self.current_hp -= total_damage
        return vamps, results



    def _apply_costs(self, components: list[QueueComponent]) -> list[EffectResult]:
        results = []
        for component in components:
            assert isinstance(component.props, ProcessedCostProperties), "Cost component must have ProcessedCostProperties"
            results.append(self.pay_cost(component.props.resource, component.props.value, component.source, component.actor, component.origin))
        return results


    def _apply_status_effects(self, components: list[QueueComponent], tick: int) -> None:
        tenacity_affected = {StatusType.BERSERK, StatusType.BLIND, StatusType.CRIPPLE, StatusType.DISARM,
                             StatusType.GROUND, StatusType.SILENCE, StatusType.SLEEP,
                             StatusType.SLOW, StatusType.STUN, StatusType.SUSPENSION, StatusType.TAUNT}
        for component in components:
            try:
                assert isinstance(component.props, ProcessedStatusProperties), "Status component must have ProcessedStatusProperties"
                duration = component.props.duration
                if component.props.type_ in tenacity_affected:
                    duration = self._apply_tenacity(duration)
                expiration = tick + duration
                self.status_effects[component.props.type_].append((expiration, component.props.strength))
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="status application"
                ) from e


    def _apply_tenacity(self, duration: int) -> int:
        # Tenacity can't reduce a CC below 0.3 seconds, but a CC that is already shorter stays as it is.
        min_duration = min(duration, to_ticks(0.3))
        return max(min_duration, math.ceil(self._cc_duration_factor() * duration))



    def _usable_during_cc(self, slot: ActionType) -> bool:
        return slot in self.ability_dict and getattr(self.ability_dict[slot][0], "usable_during_cc", False)

    def check_action_delay(self, action_type: ActionType, tick: int) -> int:
        # A pending recast ignores the cooldown, but only if it can start inside its window; otherwise it starts over.
        recast = self._recast_window(action_type)
        if recast is not None:
            earliest, window_end = recast
            ready = self._action_delay(action_type, max(tick, earliest))
            if ready <= window_end:
                return ready
        return self._action_delay(action_type, max(tick, self.cooldowns[action_type]))

    def _recast_window(self, slot: ActionType) -> tuple[int, int] | None:
        if slot not in self.recasts:
            return None
        index, previous_cast = self.recasts[slot]
        ability = self.ability_dict[slot][0]
        stage, context = ability.stages[index], self.formula_context(slot)
        earliest = previous_cast + to_ticks(evaluate_formula(stage.recast_delay, context))
        return earliest, previous_cast + to_ticks(evaluate_formula(stage.recast_window, context))

    def _action_delay(self, action_type: ActionType, tick: int) -> int:
        if action_type not in self.lock_exceptions:
            tick = max(tick, self.locked_until)
        self._remove_expired_status_effects(tick)

        if StatusType.STASIS in self.status_effects:
            tick = self.status_effects[StatusType.STASIS][0][0]

        if StatusType.SUPPRESSION in self.status_effects:
            supression_delay = max(supression[0] for supression in self.status_effects[StatusType.SUPPRESSION])
            tick = max(tick, supression_delay)

        if self._usable_during_cc(action_type):
            return tick

        stuns = {StatusType.STUN, StatusType.SUSPENSION, StatusType.SLEEP, StatusType.AIRBORNE}
        stun_delays = [max(effect[0] for effect in self.status_effects[stun]) for stun in stuns if stun in self.status_effects]
        if stun_delays:
            tick = max(tick, max(stun_delays))

        if action_type == ActionType.BA and StatusType.DISARM in self.status_effects:
            disarm_delay = max(disarm[0] for disarm in self.status_effects[StatusType.DISARM])
            tick = max(tick, disarm_delay)
        
        if action_type in SLOT_COOLDOWN_REDUCTION:  # summoner spells can be used while silenced
            silences = {StatusType.BERSERK, StatusType.SILENCE, StatusType.TAUNT}
            silence_delay = [max(effect[0] for effect in self.status_effects[silence]) for silence in silences if silence in self.status_effects]
            if silence_delay:
                tick = max(tick, max(silence_delay))

        return tick



    def do_action(self, action: Action, tick: int) -> ActionEffect:
        if action.action_type == ActionType.BA:
            return self._basic_attack(action, tick)
        elif action.action_type in self.ability_dict:
            return self._do_ability(action, tick)
        else:
            raise NotImplementedError(f"ActionType '{action.action_type}' not implemented in do_action()")



    def _basic_attack(self, action: Action, tick: int) -> ActionEffect:
        attack_time = 1 / self._get_attackspeed()
        self.cooldowns[ActionType.BA] = tick + to_ticks(attack_time)
        windup_ticks = to_ticks(attack_time * self._attack_windup())
        rule = self._basic_attack_rule(blinded=StatusType.BLIND in self.status_effects)
        event = RuleEvent(rule=rule, slot=ActionType.BA, owner=action.actor, target=action.target)
        return ActionEffect(tick=tick + windup_ticks, rule_events=[event], windup_cancel=self._windup_cancels())

    def _attack_windup(self) -> float:
        return self.champion.attack_windup

    def _windup_cancels(self) -> set[ActionType]:
        return {
            slot
            for instance in self.active_buffs.values() if instance.source is self
            for slot in instance.definition.windup_cancel
        }

    def _basic_attack_rule(self, blinded: bool) -> Rule:
        damage = DamageAction(type_=RuleActionType.DAMAGE, props=DamageProps(
            target=Target.TARGET,
            scaling="0" if blinded else "ad",
            dmg_type=[DamageType.BASIC],
            dmg_sub_type=DamageSubType.PHYSIC
        ))
        return Rule(actions=[damage], speed=str(self.champion.missile_speed))
    

    def _do_ability(self, action: Action, tick: int) -> ActionEffect:
        ability = self.ability_dict[action.action_type][0]
        if not ability.validated or not ability.stages:
            raise NotImplementedError(f"Ability {action.action_type} is not entered yet for {self.name}")
        return self._cast_stage(action, ability, tick)
    def _cast_stage(self, action: Action, ability: Ability, tick: int) -> ActionEffect:
        slot = action.action_type
        context = self.formula_context(slot)
        cast_ticks = to_ticks(evaluate_formula(ability.cast_time, context))
        index = self._stage_index(slot, tick)
        if index == 0:
            # Only the first cast starts the cooldown; recasts live in their window (Riven Q, Wind Slash).
            cooldown_ticks = self._cooldown_ticks(ability, slot)
            cooldown_start = tick if ability.cooldown_starts_on_cast else tick + cast_ticks
            self.cooldowns[slot] = cooldown_start + cooldown_ticks
            if ability.cooldown_starts_after:
                self._defer_cooldown(ability.cooldown_starts_after, slot, cooldown_ticks, tick + cast_ticks)
        if index + 1 < len(ability.stages):
            self.recasts[slot] = (index + 1, tick)
        else:
            self.recasts.pop(slot, None)
        stage = ability.stages[index]
        outcome = self._outcome(action, stage)
        rule_events = self._cost_event(action) + [
            RuleEvent(rule=rule, slot=action.action_type, owner=action.actor, target=action.target)
            for rule in stage.rules if rule.outcome in (None, outcome)
        ]
        return ActionEffect(tick=tick + cast_ticks, rule_events=rule_events)

    def _stage_index(self, slot: ActionType, tick: int) -> int:
        recast = self._recast_window(slot)
        if recast is not None and recast[0] <= tick <= recast[1]:
            return self.recasts[slot][0]
        return 0

    @staticmethod
    def _outcome(action: Action, stage: Stage) -> str | None:
        if action.outcome is None:
            return stage.outcomes[0] if stage.outcomes else None
        if action.outcome not in stage.outcomes:
            raise ValueError(f"Outcome '{action.outcome}' is not possible for {action.action_type}, choose one of {stage.outcomes}")
        return action.outcome


    def _cooldown_ticks(self, ability: Ability, slot: ActionType) -> int:
        return to_ticks(self.get_cooldown(slot))

    def get_cooldown(self, slot: ActionType) -> float:
        if slot not in self.ability_dict:
            raise ValueError(f"{slot} has no cooldown")
        ability = self.ability_dict[slot][0]
        cooldown = evaluate_formula(ability.cooldown, self.formula_context(slot))
        if slot in SUMMONER_SLOTS:
            return cooldown * 100 / (100 + self._get_bonus_stat(Stat.SUMMONER_HASTE))
        haste = 100 / (100 + self._get_bonus_stat(Stat.ABILITY_HASTE))
        reduction = 1 - self.get_stat(SLOT_COOLDOWN_REDUCTION[slot])
        return cooldown * haste * reduction

    def _defer_cooldown(self, buff: str, slot: ActionType, cooldown_ticks: int, cast_end: int) -> None:
        # Until the buff is gone the cooldown can't start; its latest possible start is the end of the buff's full duration.
        definition, buff_slot = self.buff_definitions[buff]
        buff_end = self._buff_end(definition, self.formula_context(buff_slot), cast_end)
        if buff_end is None:
            raise ValueError(f"cooldown_starts_after needs a buff with a duration, '{buff}' has none")
        self.pending_cooldowns[buff] = (slot, cooldown_ticks)
        self.cooldowns[slot] = buff_end + cooldown_ticks


    def take_effects(self, component_list: list[QueueComponent], tick: int) -> tuple[list[QueueComponent], list[EffectResult]]:
        damages = []
        heals = []
        shields = []
        stati = []
        costs = []
        for component in component_list:
            match component.type_:
                case EffectType.DAMAGE:
                    damages.append(component)
                case EffectType.HEAL:
                    heals.append(component)
                case EffectType.SHIELD:
                    shields.append(component)
                case EffectType.STATUS:
                    stati.append(component)
                case EffectType.COST:
                    costs.append(component)
                case _:
                    pass
        self._apply_shields(shields, tick)
        vamps, results = self._apply_damages(damages)
        results.extend(self._apply_heals(heals, tick))
        results.extend(self._apply_costs(costs))
        self._apply_status_effects(stati, tick)
        return vamps, results