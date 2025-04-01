from collections import defaultdict
import math

from src.server.models.ability import ChampionAbility
from src.server.models.champion import Champion
from src.server.models.dataenums import (
    Action,
    ActionEffect,
    ActionType,
    HpScaling,
    DamageProperties,
    DamageSubType,
    DamageType,
    EffectComp,
    EffectType,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    ProcessedStatusProperties,
    QueueComponent,
    Stat,
    StatusType,
    Actor
)
from src.server.models.item import Item
from src.server.models.request import Rank
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell

                    
    


class Character():
    def __init__(self, champion: Champion, lvl: int, rank: Rank ,items: list[Item]) -> None:
        self.champion: Champion = champion
        self.level: int = lvl
        self.items: list[Item] = items
        self.hp: float = self._get_stat(Stat.HP)
        self.shields: list[tuple[float, float]] = []
        self.status_effects: dict[StatusType, list[tuple[float, float]]] = defaultdict(list)

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
        self.damage_taken: float = 0
        self.healed: float = 0
        self.damage_shielded: float = 0



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
    
    def _get_stat(self, stat: Stat) -> float:
        if stat == Stat.ATTACKSPEED_P:
            return self._get_attackspeed()
        if stat == Stat.TENACITY_P:
            return self._get_tenacity()
        base_stat = self._get_base_stat(stat)
        bonus_stat = self._get_bonus_stat(stat)
        result = base_stat + bonus_stat
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
    

    def _apply_heals(self, props: list[ProcessedHealProperties]) -> None:
        heal = sum([self._calculate_hp_scaling(prop.value, prop.hp_scaling) for prop in props])
        max_hp = self._get_stat(Stat.HP)
        heal = min(heal, max_hp - self.hp)
        self.healed += heal
        self.hp += heal
    

    def _apply_shields(self, props: list[ProcessedShieldProperties], timestamp: float) -> None:
        self.shields = [(exp, val) for exp, val in self.shields if exp > timestamp and val > 0]
        new_shields = [(prop.duration+timestamp, self._calculate_hp_scaling(prop.value, prop.hp_scaling)) for prop in props]
        self.shields.extend(new_shields)
        self.shields.sort()
    

    def _apply_damages(self, props: list[ProcessedDamageProperties]) -> None:
        damage = sum([self._calculate_damage(prop) for prop in props])
        self.damage_taken += damage
        for i, (exp, shield_val) in enumerate(self.shields):
            absorbed = min(damage, shield_val)
            self.damage_shielded += absorbed
            damage -= absorbed
            self.shields[i] = (exp, shield_val-absorbed)
            if damage <= 0:
                break
        if damage > 0:
            self.hp -= damage


    def _apply_status_effects(self, props: list[ProcessedStatusProperties], timestamp: float) -> None:
        tenacity_affected = {StatusType.BERSERK, StatusType.BLIND, StatusType.CRIPPLE, StatusType.DISARM,
                             StatusType.GROUND, StatusType.KINEMATICS, StatusType.SILENCE, StatusType.SLEEP,
                             StatusType.SLOW, StatusType.STUN, StatusType.SUSPENSION, StatusType.TAUNT}
        for prop in props:
            if prop.type_ in tenacity_affected:
                prop.duration = max(0.3, self._get_tenacity() * prop.duration)
            expiration = timestamp + prop.duration
            self.status_effects.setdefault(prop.type_, []).append((expiration, prop.strength))




    def check_action_delay(self, action_type: ActionType, timestamp: float) -> float:
        timestamp = max(timestamp, self.cooldowns[action_type])
        self._remove_expired_status_effects(timestamp)

        if StatusType.STASIS in self.status_effects:
            timestamp = self.status_effects[StatusType.STASIS]

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


    def _basic_attack(self, target: Actor, timestamp: float) -> ActionEffect:
        attack_time = 1 / self._get_attackspeed()
        self.cooldowns[ActionType.AA] = timestamp + attack_time
        timestamp += attack_time * self.champion.attack_windup
        aa_props = DamageProperties(
            scaling=Stat.AD.value,
            dmg_type=DamageType.BASIC  #TODO check if Basic is right damage type
        )
        if StatusType.BLIND in self.status_effects:
            aa_props.scaling = 0
        dmg = EffectComp(
            source=ActionType.AA,
            target=target,
            type_= EffectType.DAMAGE,
            speed=self.champion.missile_speed,
            props=aa_props
        )
        return ActionEffect(time=timestamp, effect_comps=[dmg])
    

    def _do_ability(self, action: Action, timestamp: float) -> ActionEffect:
        ability: ChampionAbility = self.ability_dict[action.action_type][0]
        cooldown = self._evaluate_formula(ability.cooldown, {"rank": self.ability_dict[action.action_type][1]})
        cooldown *= 100 / (100 + self._get_bonus_stat(Stat.ABILITY_HASTE))
        self.cooldowns[action.action_type] = timestamp + ability.cast_time + cooldown
        action_effect = ActionEffect(time=timestamp + ability.cast_time)
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
        return action_effect
    


    def evaluate(self, queue_comps:list[QueueComponent]) -> list[QueueComponent]:
        component_list = []
        for component in queue_comps:
            if component.type_ == EffectType.SHADOW:
                continue
            variables = {"rank": self.ability_dict[component.source][1]} if component.source in self.ability_dict else {}
            result = self._evaluate_formula(component.props.scaling, variables)
            
            match component.type_:
                case EffectType.DAMAGE:
                    flat_pen, percent_pen = self._get_penetration(component.props.dmg_sub_type)
                    props=ProcessedDamageProperties(
                        value=result,
                        flat_pen=flat_pen,
                        percent_pen=percent_pen,
                        dmg_type=component.props.dmg_type,
                        dmg_sub_type=component.props.dmg_sub_type,
                        hp_scaling=component.props.hp_scaling,
                    )
                case EffectType.HEAL:
                    props=ProcessedHealProperties(
                        value=result,
                        hp_scaling=component.props.hp_scaling
                    )
                case EffectType.SHIELD:
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
            queue_component.props=props
            component_list.append(queue_component)
        return component_list

        

    def take_effects(self, component_list: list[QueueComponent], timestamp: float) -> None:
        damages = []
        heals = []
        shields = []
        stati = []
        for component in component_list:
            match component.type_:
                case EffectType.DAMAGE:
                    damages.append(component.props)
                case EffectType.HEAL:
                    heals.append(component.props)
                case EffectType.SHIELD:
                    shields.append(component.props)
                case EffectType.STATUS:
                    stati.append(component.props)
                case _:
                    pass
        self._apply_shields(shields, timestamp)
        self._apply_damages(damages)
        self._apply_heals(heals)
        self._apply_status_effects(stati, timestamp)