
from src.server.models.ability import ChampionAbility
from src.server.models.champion import Champion
from src.server.models.dataenums import (
    ActionEffect,
    ActionType,
    Damage, 
    DamageCalculation,
    DamageSubType,
    DamageType,
    EffectDamage,
    EffectStatus,
    QueueDamage,
    Stat,
    StatusType
)
from src.server.models.item import Item
from src.server.models.request import Rank
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.models.unit import Unit


    


class Dummy():
    def __init__(self, unit: Unit):
        self.unit: Unit = unit
        self.hp:float  = unit.hp
        self.damage_taken: float = 0

    def get_stat(self, stat: Stat) -> float:
        base_stat = getattr(self.unit, stat.value, 0)
        return base_stat

    def get_resistance(self, dmg_sub_type: DamageSubType) -> float:
        if dmg_sub_type == DamageSubType.PHYSIC:
            return self.unit.armor
        elif dmg_sub_type == DamageSubType.MAGIC:
            return self.unit.mr
        else:
            return 0

    def calculate_damage(self, damage: Damage) -> float:
        match damage.dmg_calc:
            case DamageCalculation.MAX_HP:
                damage.value *= self.get_stat(Stat.HP)
            case DamageCalculation.CURRENT_HP:
                damage.value *= self.hp
            case DamageCalculation.MISSING_HP:
                damage.value *= (self.get_stat(Stat.HP) - self.hp)
        resistance = self.get_resistance(damage.dmg_sub_type)
        resistance -= (resistance * damage.percent_pen / 100)
        resistance -= damage.flat_pen
        resistance = max(resistance, 0)
        result = damage.value * (100 / (resistance + 100))
        return result


    def take_damge(self, damage_list: list[Damage]) -> None:
        results = []
        for damage in damage_list:
            results.append(self.calculate_damage(damage))
        result = sum(results)
        result = result
        self.hp = self.hp - result
        self.damage_taken = self.damage_taken + result
    


class Character(Dummy):
    def __init__(self, champion: Champion, lvl: int, rank: Rank ,items: list[Item]) -> None:
        #TODO add runes and summonerspells
        super().__init__(champion)
        self.unit: Champion = champion
        self.level: int = lvl
        self.items: list[Item] = items
        self.hp: float = self.get_stat(Stat.HP)

        self.ability_dict: dict[ActionType, tuple[ChampionAbility, int]] = {
            ActionType.Q: (self.unit.q, rank.q),
            ActionType.W: (self.unit.w, rank.w),
            ActionType.E: (self.unit.e, rank.e),
            ActionType.R: (self.unit.r, rank.r)
        }
        self.last_action: ActionType = None
        self.cooldowns: dict[ActionType, float] = {
            ActionType.AA: 0,
            ActionType.Q: 0,
            ActionType.W: 0,
            ActionType.E: 0,
            ActionType.R: 0,
        }



    def get_base_stat(self, stat: Stat) -> float:
        stat_name = stat.value
        base_value = getattr(self.unit, stat_name, None)
        if base_value is None:
            return 0    
        scaling_attr = f"{stat_name}_per_lvl"
        scaling_value = getattr(self.unit, scaling_attr, 0)
        return base_value + scaling_value * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1))

    def get_bonus_stat(self, stat: Stat) -> float:
        return sum([item.stats[stat] for item in self.items if stat in item.stats])
    
    def get_stat(self, stat: Stat) -> float:
        if stat == Stat.ATTACKSPEED_P:
            return self.get_attackspeed()
        base_stat = self.get_base_stat(stat)
        bonus_stat = self.get_bonus_stat(stat)
        result = base_stat + bonus_stat
        return result

    def get_attackspeed(self) -> float:
        bonus = self.unit.attackspeed_per_lvl * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1))
        bonus += self.get_bonus_stat(Stat.ATTACKSPEED_P)
        result = self.unit.attackspeed + self.unit.attackspeed_ratio * bonus / 100
        return result
    
    def get_penetration(self, dmg_sub_type: DamageSubType) -> tuple[float, float]:
        if dmg_sub_type == DamageSubType.PHYSIC:
            flat_pen = self.get_bonus_stat(Stat.LETHALITY)
            percent_pen = self.get_bonus_stat(Stat.ARMOR_PEN_P)
        elif dmg_sub_type == DamageSubType.MAGIC:
            flat_pen = self.get_bonus_stat(Stat.MAGIC_PEN)
            percent_pen = self.get_bonus_stat(Stat.MAGIC_PEN_P)
        else:
            flat_pen = 0
            percent_pen = 0
        return (flat_pen, percent_pen)
    
    def get_resistance(self, dmg_sub_type: DamageSubType) -> float:
        if dmg_sub_type == DamageSubType.PHYSIC:
            return self.get_stat(Stat.ARMOR)
        elif dmg_sub_type == DamageSubType.MAGIC:
            return self.get_stat(Stat.MR)
        else:
            return 0
        
    def evaluate_formula(self, formula: str, additional_keywords: dict = {}) -> float:
        variables = {
            stat.value: self.get_stat(stat) for stat in Stat
        } | {
            "level": self.level
        } | additional_keywords
        return eval(formula, {}, variables)



    def do_action(self, key: ActionType, timer: float) -> ActionEffect:
        if key == ActionType.AA:
            return self.basic_attack(timer)
        elif key in self.ability_dict:
            return self.do_ability(key, timer)


    def basic_attack(self, timer: float) -> ActionEffect:
        attack_time = 1 / self.get_attackspeed()
        time = max(self.cooldowns[ActionType.AA], timer)
        self.cooldowns[ActionType.AA] = time + attack_time
        #TODO delete /100 again
        time += attack_time * self.unit.attack_windup/100
        dmg = EffectDamage(
            source=ActionType.AA,
            scaling=Stat.AD.value,
            dmg_type=DamageType.BASIC  #TODO check actual damage type for basic attacks
        )
        self.last_action = ActionType.AA
        return ActionEffect(time=time, damages=[dmg])
    

    def do_ability(self, key: ActionType, timer: float) -> ActionEffect:
        ability: ChampionAbility = self.ability_dict[key][0]
        time = max(self.cooldowns[key], timer)
        cooldown = self.evaluate_formula(ability.cooldown, {"rank": self.ability_dict[key][1]})
        cooldown *= 100 / (100 + self.get_bonus_stat(Stat.ABILITY_HASTE))
        self.cooldowns[key] = time + ability.cast_time + cooldown
        action_effect = ActionEffect(time=time + ability.cast_time)
        self.last_action = key
        for effect in ability.effects:
            for status in effect.stati:
                if status.type_ == StatusType.DAMAGE:
                    action_effect.damages.append(EffectDamage(
                        source=key,
                        scaling=status.scaling,
                        dmg_type=ability.damage_type,
                        dmg_sub_type=effect.damage_sub_type,
                        dmg_calc=status.dmg_calc,
                ))
                else:
                    action_effect.stati.append(EffectStatus(
                        source=key,
                        scaling=status.scaling,
                        type_=status.type_
                    ))
        return action_effect


    def evaluate_scaling(self, queue_damages: list[QueueDamage]) -> list[Damage]:
        """ variables = {
            stat.value: self.get_stat(stat) for stat in Stat
        } | {
            "level": self.level
        } """
        damage_list = []
        for damage in queue_damages:
            if damage.scaling == "shadow":
                continue
            variables = {"rank": self.ability_dict[damage.source][1]} if damage.source in self.ability_dict else {}
            result = self.evaluate_formula(damage.scaling, variables)
            """ if damage.source in self.ability_dict:
                variables["rank"] = self.ability_dict[damage.source][1] """
            flat_pen, percent_pen = self.get_penetration(damage.dmg_sub_type)
            """ result = eval(damage.scaling, {}, variables) """
            damage_list.append(Damage(
                value=result,
                flat_pen=flat_pen,
                percent_pen=percent_pen,
                dmg_type=damage.dmg_type,
                dmg_sub_type=damage.dmg_sub_type,
                dmg_calc=damage.dmg_calc,
                source=damage.source
            ))
        return damage_list
        