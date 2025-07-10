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
    EffectType,
    HealProperties,
    HpScaling,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    ProcessedStatusProperties,
    QueueComponent,
    ShieldProperties,
    Stat,
    StatusProperties,
    StatusType,
    Actor
)
from src.server.models.effect import EffectComponent
from src.server.models.item import Item
from src.server.models.passive_effect import BuffProperties, BuffAction, StatProperties, StackProps, EffectProps
from src.server.models.request import Rank, Action
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.simulation.exceptions import SimulationError

                    
    


class Character():
    def __init__(self, champion: Champion, lvl: int, rank: Rank ,items: list[Item]) -> None:
        self.champion: Champion = champion
        self.level: int = lvl
        self.items: list[Item] = items
        self.shields: list[tuple[float, float]] = []
        self.status_effects: dict[StatusType, list[tuple[float, float]]] = defaultdict(list)
        self.buffs: dict[Buff, list[BuffProperties]] = self._initialize_buffs()
        self.stacks: dict[ActionType, int] = defaultdict(int)

        self.evaluating_stat: set = set()

        self.ability_dict: dict[ActionType, tuple[ChampionAbility, int]] = {
            ActionType.Q: (self.champion.q, rank.q),
            ActionType.W: (self.champion.w, rank.w),
            ActionType.E: (self.champion.e, rank.e),
            ActionType.R: (self.champion.r, rank.r)
        }
        self.cooldowns: dict[ActionType, float] = {
            ActionType.AA: 0,
            ActionType.Q: 0,
            ActionType.W: 0,
            ActionType.E: 0,
            ActionType.R: 0,
        }
        self.hp: float = self._get_stat(Stat.HP)
        self.damage_taken: float = 0
        self.healed: float = 0
        self.damage_shielded: float = 0


    def _initialize_buffs(self) -> dict[Buff, list[BuffProperties]]:
        buffs = defaultdict(list)
        for effect in self.champion.passive.effects:
            buffs[effect.buff].append(effect.props)
        return buffs


    def _get_base_stat(self, stat: Stat) -> float:
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
        if not self.buffs[Buff.STATS]:
            return result
        for stat_property in self.buffs[Buff.STATS]:
            assert isinstance(stat_property, StatProperties)
            if self._evaluate_condition(stat_property.condition):
                formula = stat_property.scaling
                result += self._evaluate_formula(formula)
        return result


    def _get_stat(self, stat: Stat) -> float:
        if stat.value.startswith("bonus "):
            return self._get_bonus_stat(Stat.from_str(stat.value.removeprefix("bonus ")))
        
        if stat == Stat.ATTACKSPEED_P:
            return self._get_attackspeed()
        if stat == Stat.TENACITY_P:
            return self._get_tenacity()
        
        base_stat = self._get_base_stat(stat)
        bonus_stat = self._get_bonus_stat(stat)
        buff_stat = 0
        if stat not in self.evaluating_stat:
            self.evaluating_stat.add(stat)
            buff_stat = self._get_buff_stat(stat)

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
    
    def _get_penetration(self, dmg_sub_type: DamageSubType) -> tuple[float, float]:
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
            return self._get_stat(Stat.ARMOR)
        elif dmg_sub_type == DamageSubType.MAGIC:
            return self._get_stat(Stat.MR)
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
        

    def _remove_expired_status_effects(self, timestamp: float) -> None:
        for status, effects in list(self.status_effects.items()):
            self.status_effects[status] = [(exp, strength) for exp, strength in effects if exp > timestamp]
            if not self.status_effects[status]:
                del self.status_effects[status]


        
    def _evaluate_formula(self, formula: str, additional_keywords: dict = {}) -> float:
        variables = {
            stat.value: self._get_stat(stat) for stat in Stat
        } | {
            "level": self.level
        } | {
            stack_key: self.stacks[stack_key] for stack_key in ActionType
        } | additional_keywords
        return eval(formula, {}, variables)
    

    def _calculate_hp_scaling(self, value: float, hp_scaling: HpScaling) -> float:
        match hp_scaling:
            case HpScaling.MAX_HP:
                return value * self._get_stat(Stat.HP)
            case HpScaling.CURRENT_HP:
                return value * self.hp
            case HpScaling.MISSING_HP:
                return value * (self._get_stat(Stat.HP) - self.hp)
        return value


    def _calculate_damage(self, damage: ProcessedDamageProperties) -> float:
        value = self._calculate_hp_scaling(damage.value, damage.hp_scaling)
        resistance = self._get_resistance(damage.dmg_sub_type)
        resistance -= (resistance * damage.percent_pen)
        resistance -= damage.flat_pen
        resistance = max(resistance, 0)
        result = value * (100 / (resistance + 100))
        return result
    

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



    def _apply_heals(self, components: list[QueueComponent]) -> None:
        total_heal = 0
        for component in components:
            try:
                assert isinstance(component.props, ProcessedHealProperties), "Heal component must have ProcessedHealProperties"
                heal = self._calculate_hp_scaling(component.props.value, component.props.hp_scaling)
                total_heal += heal
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="heal application"
                ) from e
        max_hp = self._get_stat(Stat.HP)
        total_heal = min(total_heal, max_hp - self.hp)
        self.healed += total_heal
        self.hp += total_heal
    

    def _apply_shields(self, components: list[QueueComponent], timestamp: float) -> None:
        self.shields = [(exp, val) for exp, val in self.shields if exp > timestamp and val > 0]
        for component in components:
            try:
                assert isinstance(component.props, ProcessedShieldProperties), "Shield component must have ProcessedShieldProperties"
                shield = (component.props.duration+timestamp, self._calculate_hp_scaling(component.props.value, component.props.hp_scaling))
                self.shields.append(shield)
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="shield application"
                ) from e
        self.shields.sort()
    

    def _apply_damages(self, components: list[QueueComponent]) -> list[QueueComponent]:
        total_damage = 0
        vamps = []
        for component in components:
            try:
                assert isinstance(component.props, ProcessedDamageProperties), "Damage component must have ProcessedDamageProperties"
                damage = self._calculate_damage(component.props)
                total_damage += damage
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
        for i, (exp, shield_val) in enumerate(self.shields):
            absorbed = min(total_damage, shield_val)
            self.damage_shielded += absorbed
            total_damage -= absorbed
            self.shields[i] = (exp, shield_val-absorbed)
            if total_damage <= 0:
                break
        if total_damage > 0:
            self.hp -= total_damage
        return vamps


    def _apply_status_effects(self, components: list[QueueComponent], timestamp: float) -> None:
        tenacity_affected = {StatusType.BERSERK, StatusType.BLIND, StatusType.CRIPPLE, StatusType.DISARM,
                             StatusType.GROUND, StatusType.KINEMATICS, StatusType.SILENCE, StatusType.SLEEP,
                             StatusType.SLOW, StatusType.STUN, StatusType.SUSPENSION, StatusType.TAUNT}
        for component in components:
            try:
                assert isinstance(component.props, ProcessedStatusProperties), "Status component must have ProcessedStatusProperties"
                if component.props.type_ in tenacity_affected:
                    component.props.duration = max(0.3, self._get_tenacity() * component.props.duration)
                expiration = timestamp + component.props.duration
                self.status_effects[component.props.type_].append((expiration, component.props.strength))
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_type=component.source,
                    actor=component.actor,
                    phase="status application"
                ) from e




    def check_action_delay(self, action_type: ActionType, timestamp: float) -> float:
        timestamp = max(timestamp, self.cooldowns[action_type])
        self._remove_expired_status_effects(timestamp)

        if StatusType.STASIS in self.status_effects:
            timestamp = self.status_effects[StatusType.STASIS][0][0]

        if StatusType.SUPPRESSION in self.status_effects:
            supression_delay = max(supression[0] for supression in self.status_effects[StatusType.SUPPRESSION])
            timestamp = max(timestamp, supression_delay)

        stuns = {StatusType.STUN, StatusType.SUSPENSION, StatusType.SLEEP, StatusType.AIRBORNE}
        stun_delays = [max(effect[0] for effect in self.status_effects[stun]) for stun in stuns if stun in self.status_effects]
        if stun_delays:
            timestamp = max(timestamp, max(stun_delays))

        if action_type == ActionType.AA and StatusType.DISARM in self.status_effects:
            disarm_delay = max(disarm[0] for disarm in self.status_effects[StatusType.DISARM])
            timestamp = max(timestamp, disarm_delay)
        
        if action_type in self.ability_dict:
            silences = {StatusType.BERSERK, StatusType.SILENCE, StatusType.TAUNT}
            silence_delay = [max(effect[0] for effect in self.status_effects[silence]) for silence in silences if silence in self.status_effects]
            if silence_delay:
                timestamp = max(timestamp, max(silence_delay))

        return timestamp



    def do_action(self, action: Action, timestamp: float) -> ActionEffect:
        if action.action_type == ActionType.AA:
            return self._basic_attack(action.target, timestamp)
        elif action.action_type in self.ability_dict:
            return self._do_ability(action, timestamp)
        else:
            raise NotImplementedError(f"ActionType '{action.action_type}' not implemented in do_action()")



    def _basic_attack(self, target: Actor, timestamp: float) -> ActionEffect:
        attack_time = 1 / self._get_attackspeed()
        self.cooldowns[ActionType.AA] = timestamp + attack_time
        timestamp += attack_time * self.champion.attack_windup
        aa_props = DamageProperties(
            scaling=Stat.AD.value,
            dmg_type=DamageType.BASIC  #TODO check if Basic is right damage type
        )
        if StatusType.BLIND in self.status_effects:
            aa_props.scaling = "0"
        dmg = EffectComp(
            source=ActionType.AA,
            target=target,
            type_= EffectType.DAMAGE,
            speed=self.champion.missile_speed,
            props=aa_props
        )
        effect_components = [dmg]
        """ effect_components.extend(self._check_buffs(ActionType.AA, Buff.CAST)) """
        return ActionEffect(time=timestamp, effect_comps=effect_components)
    

    def _do_ability(self, action: Action, timestamp: float) -> ActionEffect:
        ability: ChampionAbility = self.ability_dict[action.action_type][0]
        if not ability.validated:
            raise NotImplementedError(f"Ability {action.action_type} is not implemented yet for {self.champion.name}")
        cooldown = self._evaluate_formula(ability.cooldown, {"rank": self.ability_dict[action.action_type][1]})
        cooldown *= 100 / (100 + self._get_bonus_stat(Stat.ABILITY_HASTE))
        cast_time = self._evaluate_formula(ability.cast_time,  {"rank": self.ability_dict[action.action_type][1]})
        self.cooldowns[action.action_type] = timestamp + cast_time + cooldown
        action_effect = ActionEffect(time=timestamp + cast_time)
        for effect in ability.effects:
            for component in effect.effect_components:
                effect_comp = EffectComp(
                    source=action.action_type,
                    target=action.target,
                    type_=component.type_,
                    duration=component.duration,
                    interval=component.interval,
                    delay=component.delay,
                    speed=component.speed,
                    props=component.props
                )
                action_effect.effect_comps.append(effect_comp)
                """ action_effect.effect_comps.extend(self._check_buffs(action.action_type, Buff.CAST)) """
        return action_effect
    


    def evaluate(self, queue_comps:list[QueueComponent]) -> list[QueueComponent]:
        component_list = []
        for component in queue_comps:
            if component.type_ == EffectType.SHADOW:
                continue

            variables = {"rank": self.ability_dict[component.source][1]} if component.source in self.ability_dict else {}
            assert isinstance(component.props, (DamageProperties, HealProperties, ShieldProperties)), \
                "Component properties must be one of DamageProperties, HealProperties, ShieldProperties"
            result = self._evaluate_formula(component.props.scaling, variables)
            
            match component.type_:
                case EffectType.DAMAGE:
                    """ self._check_buffs(component.source, Buff.HIT) """
                    assert isinstance(component.props, DamageProperties), "Damage component must have DamageProperties"
                    flat_pen, percent_pen = self._get_penetration(component.props.dmg_sub_type)
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
                        duration=component.props.duration,
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

        

    def take_effects(self, component_list: list[QueueComponent], timestamp: float) -> list[QueueComponent]:
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
        self._apply_shields(shields, timestamp)
        vamps = self._apply_damages(damages)
        self._apply_heals(heals)
        self._apply_status_effects(stati, timestamp)
        return vamps