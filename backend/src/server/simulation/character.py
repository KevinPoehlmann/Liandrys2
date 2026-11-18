from collections import defaultdict
from typing import cast
import math

from src.server.models.ability import ChampionAbility
from src.server.models.champion import Champion
from src.server.models.dataenums import (
    ActionEffect,
    ActionType,
    Buff,
    BuffActionType,
    Condition,
    Comparison,
    DamageProperties,
    DamageSubType,
    DamageType,
    EffectComp,
    EffectProperties,
    EffectResult,
    EffectType,
    HealProperties,
    HpScaling,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    ProcessedStatusProperties,
    QueueComponent,
    ShieldProperties,
    RuleActionType,
    Stat,
    StatMode,
    Target,
    Trigger,
    StatusProperties,
    StatusType,
    Actor,
    TICKRATE
)
from src.server.models.effect import EffectComponent
from src.server.models.item import Item
from src.server.models.passive_effect import BuffProperties, BuffAction, StatProperties, StackProps, EffectProps
from src.server.models.request import Rank, Action
from src.server.models.rule import Buff as BuffDefinition, DamageAction, DamageProps, Rule, Stage, StatModifier
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.simulation.buff_instance import BuffInstance
from src.server.simulation.events import RuleEvent
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.formula import FormulaContext, evaluate_formula

                    
    


SLOT_COOLDOWN_REDUCTION = {
    ActionType.Q: Stat.Q_COOLDOWN_REDUCTION,
    ActionType.W: Stat.W_COOLDOWN_REDUCTION,
    ActionType.E: Stat.E_COOLDOWN_REDUCTION,
    ActionType.R: Stat.R_COOLDOWN_REDUCTION,
}


class Character():
    def __init__(self, champion: Champion, lvl: int, rank: Rank ,items: list[Item], scenario: dict[str, float] | None = None) -> None:
        self.champion: Champion = champion
        self.scenario: dict[str, float] = scenario or {}
        self.level: int = lvl
        self.items: list[Item] = items
        self.shields: list[tuple[int, float, ActionType, Actor]] = []
        self.status_effects: dict[StatusType, list[tuple[int, float]]] = defaultdict(list)
        self.buffs: dict[Buff, list[BuffProperties]] = self._initialize_buffs()
        self.stacks: dict[ActionType, int] = defaultdict(int)

        self.evaluating_stat: set = set()

        self.ability_dict: dict[ActionType, tuple[ChampionAbility, int]] = {
            ActionType.Q: (self.champion.q, rank.q),
            ActionType.W: (self.champion.w, rank.w),
            ActionType.E: (self.champion.e, rank.e),
            ActionType.R: (self.champion.r, rank.r)
        }
        self.cooldowns: dict[ActionType, int] = {
            ActionType.AA: 0,
            ActionType.Q: 0,
            ActionType.W: 0,
            ActionType.E: 0,
            ActionType.R: 0,
        }
        self.buff_definitions: dict[str, tuple[BuffDefinition, ActionType]] = self._collect_buff_definitions()
        self.active_buffs: dict[str, BuffInstance] = {}
        self.pending_cooldowns: dict[str, tuple[ActionType, int]] = {}
        self.locked_until: int = 0
        self.lock_exceptions: set[ActionType] = set()
        self.current_hp: float = self.get_stat(Stat.HP)
        self.damage_taken: float = 0
        self.healed: float = 0
        self.damage_shielded: float = 0


    def _initialize_buffs(self) -> dict[Buff, list[BuffProperties]]:
        buffs = defaultdict(list)
        for effect in self.champion.passive.effects:
            buffs[effect.buff].append(effect.props)
        return buffs


    def _collect_buff_definitions(self) -> dict[str, tuple[BuffDefinition, ActionType]]:
        containers = [(self.champion.passive, ActionType.PASSIVE)]
        containers += [(ability, slot) for slot, (ability, _) in self.ability_dict.items()]
        definitions = {}
        for container, slot in containers:
            for buff in container.buffs:
                if buff.name in definitions:
                    raise ValueError(f"Buff '{buff.name}' is defined twice for {self.champion.name}")
                definitions[buff.name] = (buff, slot)
        return definitions


    def get_rank(self, slot: ActionType) -> int:
        return self.ability_dict[slot][1] if slot in self.ability_dict else 0

    def get_buff_stacks(self, buff: str) -> int:
        instance = self.active_buffs.get(buff)
        return instance.stacks if instance else 0

    def formula_context(self, slot: ActionType, target: "Character | None" = None, stacks: int = 0) -> FormulaContext:
        max_rank = self.ability_dict[slot][0].maxrank if slot in self.ability_dict else 0
        return FormulaContext(source=self, target=target, rank=self.get_rank(slot), max_rank=max_rank, stacks=stacks, scenario=self.scenario)


    def apply_buff(self, name: str, source: "Character", stacks: int, tick: int) -> BuffInstance:
        definition, slot = source.buff_definitions[name]
        end = self._buff_end(definition, source.formula_context(slot), tick)
        instance = self.active_buffs.get(name)
        if instance is None:
            instance = BuffInstance(definition, source, slot, 0, tick, end)
            self.active_buffs[name] = instance
        elif definition.refresh:
            instance.end = end
        instance.stacks = min(instance.stacks + stacks, definition.max_stacks)
        return instance

    @staticmethod
    def _buff_end(definition: BuffDefinition, context: FormulaContext, tick: int) -> int | None:
        duration = evaluate_formula(definition.duration, context)
        return tick + math.ceil(duration * TICKRATE) if duration > 0 else None

    def remove_buff(self, name: str, tick: int) -> None:
        if self.active_buffs.pop(name, None) and name in self.pending_cooldowns:
            slot, cooldown_ticks = self.pending_cooldowns.pop(name)
            self.cooldowns[slot] = tick + cooldown_ticks

    def expire_buff(self, name: str, end: int) -> None:
        # A refresh moves `end`, so an end event of an older `end` is outdated and ignored.
        instance = self.active_buffs.get(name)
        if instance and instance.end == end:
            self.remove_buff(name, end)


    def triggered_rules(self, trigger: Trigger, source: ActionType) -> list[tuple[Rule, ActionType, "Character"]]:
        candidates = [(rule, ActionType.PASSIVE, self) for rule in self.champion.passive.rules]
        candidates += [
            (rule, slot, self)
            for slot, (ability, rank) in self.ability_dict.items() if rank > 0
            for rule in ability.rules
        ]
        candidates += [
            (rule, instance.slot, instance.source)
            for instance in self.active_buffs.values()
            for rule in instance.definition.rules
        ]
        return [
            (rule, slot, owner) for rule, slot, owner in candidates
            if rule.trigger == trigger and self._passes_filter(rule, source)
        ]

    @staticmethod
    def _passes_filter(rule: Rule, source: ActionType) -> bool:
        return rule.filter is None or rule.filter.source is None or source in rule.filter.source

    def reset_attack(self, tick: int) -> None:
        self.cooldowns[ActionType.AA] = tick

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
        return sum([item.stats[stat] for item in self.items if stat in item.stats])
    
    def _get_buff_stat(self, stat: Stat) -> float:
        result = 0
        for stat_property in self.buffs[Buff.STATS]:
            assert isinstance(stat_property, StatProperties)
            if stat_property.stat == stat and self._evaluate_condition(stat_property.condition):
                formula = stat_property.scaling
                result += self._evaluate_formula(formula)
        for instance in self.active_buffs.values():
            for modifier in instance.definition.stats:
                if modifier.stat == stat:
                    result += self._evaluate_modifier(modifier, instance)
        return result

    @staticmethod
    def _evaluate_modifier(modifier: StatModifier, instance: BuffInstance) -> float:
        if modifier.mode != StatMode.FLAT or modifier.conversion:
            raise NotImplementedError(f"Stat modifier mode '{modifier.mode}' (conversion={modifier.conversion}) is not supported yet")
        context = instance.source.formula_context(instance.slot, stacks=instance.stacks)
        return evaluate_formula(modifier.formula, context)


    def get_stat(self, stat: Stat) -> float:
        if stat.value.startswith("bonus "):
            return self._get_bonus_stat(Stat.from_str(stat.value.removeprefix("bonus ")))
        
        if stat == Stat.ATTACKSPEED_P:
            return self._get_attackspeed()
        if stat == Stat.TENACITY_P:
            return self._get_tenacity()
        
        base_stat = self.get_base_stat(stat)
        bonus_stat = self._get_bonus_stat(stat)
        buff_stat = 0
        # A buff formula evaluates all stats, including the one being buffed. The guard stops that recursion.
        if stat not in self.evaluating_stat:
            self.evaluating_stat.add(stat)
            try:
                buff_stat = self._get_buff_stat(stat)
            finally:
                self.evaluating_stat.discard(stat)

        result = base_stat + bonus_stat + buff_stat

        if stat == Stat.MOVESPEED:
            result *= self._get_slow_value()
        return result

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
        
    def _get_tenacity(self) -> float:
        return math.prod(1 - item.stats[Stat.TENACITY_P] for item in self.items if Stat.TENACITY_P in item.stats)
        
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


        
    def _evaluate_formula(self, formula: str, additional_keywords: dict = {}) -> float:
        variables = {
            stat.value: self.get_stat(stat) for stat in Stat
        } | {
            "level": self.level
        } | {
            stack_key: self.stacks[stack_key] for stack_key in ActionType
        } | additional_keywords
        return eval(formula, {}, variables)
    

    def _calculate_hp_scaling(self, value: float, hp_scaling: HpScaling) -> float:
        match hp_scaling:
            case HpScaling.MAX_HP:
                return value * self.get_stat(Stat.HP)
            case HpScaling.CURRENT_HP:
                return value * self.current_hp
            case HpScaling.MISSING_HP:
                return value * (self.get_stat(Stat.HP) - self.current_hp)
        return value


    def _calculate_damage(self, damage: ProcessedDamageProperties) -> tuple[float, float, float]:
        value = self._calculate_hp_scaling(damage.value, damage.hp_scaling)
        resistance = self._get_resistance(damage.dmg_sub_type)
        resistance -= (resistance * damage.percent_pen)
        resistance -= damage.flat_pen
        resistance = max(resistance, 0)
        result = value * (100 / (resistance + 100))
        return result, value, value - result
    

    def _do_action_buff(self, action: BuffAction) -> EffectComponent | None:
        match action.type_:
            case BuffActionType.STACK:
                assert isinstance(action.props, StackProps)
                self.stacks[action.props.stack_key] += int(self._evaluate_formula(action.props.amount))
            case BuffActionType.EFFECT:
                assert isinstance(action.props, EffectProps)
                return action.props.effect

    def _evaluate_condition(self, condition: Condition | None) -> bool:
        if condition is None:
            return True
        match condition.comparison:
            case Comparison.GT:
                return self._evaluate_formula(condition.key) > condition.value
            case Comparison.LT:
                return self._evaluate_formula(condition.key) < condition.value
            case Comparison.EQ:
                return self._evaluate_formula(condition.key) == condition.value


    """ def _check_buffs(self, action_type: ActionType, buff: Buff) -> list[EffectComponent]: #TODO
        if not self.buffs[buff]:
            return []
        effect_components = []
        for action_property in self.buffs[buff]:
            if action_type in action_property.trigger and self._evaluate_condition(action_property.condition):
                for buff_action in action_property.actions:
                    comp = self._do_action_buff(buff_action)
                    if comp:
                        effect_components.append(comp)
        return effect_components """

    

    def _use_shields(self, damage: float, target: Actor) -> tuple[float, list[EffectResult]]:
        results = []
        for i, (exp, shield_val, source, actor) in enumerate(self.shields):
            if damage <= 0:
                break
            if shield_val <= 0:
                continue
            absorbed = min(damage, shield_val)
            self.damage_shielded += absorbed
            damage -= absorbed
            self.shields[i] = (exp, shield_val-absorbed, source, actor)
            results.append(EffectResult(
                source=source,
                actor=actor,
                target=target,
                type_=EffectType.SHIELD,
                value=absorbed
            ))
        return damage, results


    def _apply_heals(self, components: list[QueueComponent]) -> list[EffectResult]:
        total_heal = 0
        missing_hp = self.get_stat(Stat.HP) - self.current_hp
        results = []
        for component in components:
            try:
                assert isinstance(component.props, ProcessedHealProperties), "Heal component must have ProcessedHealProperties"
                raw_heal = self._calculate_hp_scaling(component.props.value, component.props.hp_scaling)
                heal = min(raw_heal, max(missing_hp - total_heal, 0))
                total_heal += heal
                results.append(EffectResult(
                    source=component.source,
                    actor=component.actor,
                    target=component.target,
                    type_=EffectType.HEAL,
                    value=heal,
                    raw=raw_heal,
                    overheal=raw_heal - heal
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
        self.shields = [(exp, val, source, actor) for exp, val, source, actor in self.shields if exp > tick and val > 0]
        for component in components:
            try:
                assert isinstance(component.props, ProcessedShieldProperties), "Shield component must have ProcessedShieldProperties"
                shield = (component.props.duration + tick, self._calculate_hp_scaling(component.props.value, component.props.hp_scaling), component.source, component.actor)
                self.shields.append(shield)
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="shield application"
                ) from e
        self.shields.sort()
    

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
                    damage_sub_type=component.props.dmg_sub_type
                ))
                results.extend(shield_results)
                if component.props.vamp > 0:
                    vamp = damage * component.props.vamp
                    vamps.append(QueueComponent(
                        source=component.source,
                        actor=component.actor,
                        target=component.actor,
                        type_=EffectType.HEAL,
                        props=ProcessedHealProperties(value=vamp)
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



    def _apply_status_effects(self, components: list[QueueComponent], tick: int) -> None:
        tenacity_affected = {StatusType.BERSERK, StatusType.BLIND, StatusType.CRIPPLE, StatusType.DISARM,
                             StatusType.GROUND, StatusType.KINEMATICS, StatusType.SILENCE, StatusType.SLEEP,
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
        min_duration = min(duration, math.ceil(0.3 * TICKRATE))
        return max(min_duration, math.ceil(self._get_tenacity() * duration))



    def check_action_delay(self, action_type: ActionType, tick: int) -> int:
        tick = max(tick, self.cooldowns[action_type])
        if action_type not in self.lock_exceptions:
            tick = max(tick, self.locked_until)
        self._remove_expired_status_effects(tick)

        if StatusType.STASIS in self.status_effects:
            tick = self.status_effects[StatusType.STASIS][0][0]

        if StatusType.SUPPRESSION in self.status_effects:
            supression_delay = max(supression[0] for supression in self.status_effects[StatusType.SUPPRESSION])
            tick = max(tick, supression_delay)

        stuns = {StatusType.STUN, StatusType.SUSPENSION, StatusType.SLEEP, StatusType.AIRBORNE}
        stun_delays = [max(effect[0] for effect in self.status_effects[stun]) for stun in stuns if stun in self.status_effects]
        if stun_delays:
            tick = max(tick, max(stun_delays))

        if action_type == ActionType.AA and StatusType.DISARM in self.status_effects:
            disarm_delay = max(disarm[0] for disarm in self.status_effects[StatusType.DISARM])
            tick = max(tick, disarm_delay)
        
        if action_type in self.ability_dict:
            silences = {StatusType.BERSERK, StatusType.SILENCE, StatusType.TAUNT}
            silence_delay = [max(effect[0] for effect in self.status_effects[silence]) for silence in silences if silence in self.status_effects]
            if silence_delay:
                tick = max(tick, max(silence_delay))

        return tick



    def do_action(self, action: Action, tick: int) -> ActionEffect:
        if action.action_type == ActionType.AA:
            return self._basic_attack(action, tick)
        elif action.action_type in self.ability_dict:
            return self._do_ability(action, tick)
        else:
            raise NotImplementedError(f"ActionType '{action.action_type}' not implemented in do_action()")



    def _basic_attack(self, action: Action, tick: int) -> ActionEffect:
        attack_time = 1 / self._get_attackspeed()
        self.cooldowns[ActionType.AA] = tick + math.ceil(attack_time * TICKRATE)
        windup_ticks = math.ceil(attack_time * self.champion.attack_windup * TICKRATE)
        rule = self._basic_attack_rule(blinded=StatusType.BLIND in self.status_effects)
        event = RuleEvent(rule=rule, slot=ActionType.AA, owner=action.actor, target=action.target)
        return ActionEffect(tick=tick + windup_ticks, rule_events=[event], windup_cancel=self._windup_cancels())

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
        ability: ChampionAbility = self.ability_dict[action.action_type][0]
        if not ability.validated:
            raise NotImplementedError(f"Ability {action.action_type} is not implemented yet for {self.champion.name}")
        if ability.stages:
            return self._cast_stage(action, ability, tick)
        cooldown = self._evaluate_formula(ability.cooldown, {"rank": self.ability_dict[action.action_type][1]})
        cooldown *= 100 / (100 + self._get_bonus_stat(Stat.ABILITY_HASTE))
        cast_time = self._evaluate_formula(ability.cast_time,  {"rank": self.ability_dict[action.action_type][1]})
        cast_ticks = math.ceil(cast_time * TICKRATE)
        cooldown_ticks = math.ceil((cooldown) * TICKRATE)
        self.cooldowns[action.action_type] = tick + cooldown_ticks + cast_ticks
        action_effect = ActionEffect(tick=tick + cast_ticks)
        for effect in ability.effects:
            for component in effect.effect_components:
                effect_comp = EffectComp(
                    source=action.action_type,
                    target=action.target,
                    type_=component.type_,
                    duration=math.ceil(component.duration * TICKRATE),
                    interval=component.interval * TICKRATE,
                    delay=math.ceil(component.delay * TICKRATE),
                    speed=component.speed,
                    props=component.props
                )
                action_effect.effect_comps.append(effect_comp)
                """ action_effect.effect_comps.extend(self._check_buffs(action.action_type, Buff.CAST)) """
        return action_effect
    


    def _cast_stage(self, action: Action, ability: ChampionAbility, tick: int) -> ActionEffect:
        slot = action.action_type
        context = self.formula_context(slot)
        cast_ticks = math.ceil(evaluate_formula(ability.cast_time, context) * TICKRATE)
        cooldown_ticks = self._cooldown_ticks(ability, slot)
        cooldown_start = tick if ability.cooldown_starts_on_cast else tick + cast_ticks
        self.cooldowns[slot] = cooldown_start + cooldown_ticks
        if ability.cooldown_starts_after:
            self._defer_cooldown(ability.cooldown_starts_after, slot, cooldown_ticks, tick + cast_ticks)
        stage = ability.stages[0]
        outcome = self._outcome(action, stage)
        rule_events = [
            RuleEvent(rule=rule, slot=action.action_type, owner=action.actor, target=action.target)
            for rule in stage.rules if rule.outcome in (None, outcome)
        ]
        return ActionEffect(tick=tick + cast_ticks, rule_events=rule_events)

    @staticmethod
    def _outcome(action: Action, stage: Stage) -> str | None:
        if action.outcome is None:
            return stage.outcomes[0] if stage.outcomes else None
        if action.outcome not in stage.outcomes:
            raise ValueError(f"Outcome '{action.outcome}' is not possible for {action.action_type}, choose one of {stage.outcomes}")
        return action.outcome


    def _cooldown_ticks(self, ability: ChampionAbility, slot: ActionType) -> int:
        cooldown = evaluate_formula(ability.cooldown, self.formula_context(slot))
        haste = 100 / (100 + self._get_bonus_stat(Stat.ABILITY_HASTE))
        reduction = 1 - self.get_stat(SLOT_COOLDOWN_REDUCTION[slot])
        return math.ceil(cooldown * haste * reduction * TICKRATE)

    def _defer_cooldown(self, buff: str, slot: ActionType, cooldown_ticks: int, cast_end: int) -> None:
        # Until the buff is gone the cooldown can't start; its latest possible start is the end of the buff's full duration.
        definition, buff_slot = self.buff_definitions[buff]
        buff_end = self._buff_end(definition, self.formula_context(buff_slot), cast_end)
        if buff_end is None:
            raise ValueError(f"cooldown_starts_after needs a buff with a duration, '{buff}' has none")
        self.pending_cooldowns[buff] = (slot, cooldown_ticks)
        self.cooldowns[slot] = buff_end + cooldown_ticks


    def evaluate(self, queue_comps:list[QueueComponent]) -> list[QueueComponent]:
        component_list = []
        for component in queue_comps:
            if component.type_ == EffectType.STATUS:
                component_list.append(self._process_status(component))
                continue
            variables = {"rank": self.ability_dict[component.source][1]} if component.source in self.ability_dict else {}
            assert isinstance(component.props, (DamageProperties, HealProperties, ShieldProperties)), \
                "Component properties must be one of DamageProperties, HealProperties, ShieldProperties"
            result = self._evaluate_formula(component.props.scaling, variables)

            match component.type_:
                case EffectType.DAMAGE:
                    """ self._check_buffs(component.source, Buff.HIT) """
                    assert isinstance(component.props, DamageProperties), "Damage component must have DamageProperties"
                    flat_pen, percent_pen = self.get_penetration(component.props.dmg_sub_type)
                    props=ProcessedDamageProperties(
                        value=result,
                        flat_pen=flat_pen,
                        percent_pen=percent_pen,
                        dmg_type=component.props.dmg_type,
                        dmg_sub_type=component.props.dmg_sub_type,
                        hp_scaling=component.props.hp_scaling,
                        vamp=component.props.vamp
                    )
                case EffectType.HEAL:
                    assert isinstance(component.props, HealProperties), "Heal component must have ProcessedHealProperties"
                    props=ProcessedHealProperties(
                        value=result,
                        hp_scaling=component.props.hp_scaling
                    )
                case EffectType.SHIELD:
                    assert isinstance(component.props, ShieldProperties), "Shield component must have ShieldProperties"
                    props=ProcessedShieldProperties(
                        value=result,
                        duration=math.ceil(component.props.duration * TICKRATE),
                        dmg_sub_type=component.props.dmg_sub_type,
                        hp_scaling=component.props.hp_scaling
                    )
                case _:
                   raise ValueError(f"Unhandled EffectType: {component.type_}")  # Catch future issues early

            queue_component = QueueComponent(
                source=component.source,
                actor=component.actor,
                target=component.target,
                type_=component.type_,
                props=props
            )
            component_list.append(queue_component)
        return component_list


    def _process_status(self, component: QueueComponent) -> QueueComponent:
        assert isinstance(component.props, StatusProperties), "Status component must have StatusProperties"
        props = ProcessedStatusProperties(
            type_=component.props.type_,
            duration=math.ceil(component.props.duration * TICKRATE),
            strength=component.props.strength
        )
        return QueueComponent(
            source=component.source,
            actor=component.actor,
            target=component.target,
            type_=component.type_,
            props=props
        )

        

    def take_effects(self, component_list: list[QueueComponent], tick: int) -> tuple[list[QueueComponent], list[EffectResult]]:
        damages = []
        heals = []
        shields = []
        stati = []
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
                case _:
                    pass
        self._apply_shields(shields, tick)
        vamps, results = self._apply_damages(damages)
        results.extend(self._apply_heals(heals))
        self._apply_status_effects(stati, tick)
        return vamps, results