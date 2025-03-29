from src.server.models.ability import ChampionAbility
from src.server.models.champion import Champion
from src.server.models.dataenums import (
    ActionEffect,
    ActionType,
    DamageCalculation,
    DamageProperties,
    DamageSubType,
    DamageType,
    EffectDamage,
    EffectStatus,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    QueueStatus,
    Stat,
    StatusType,
    Target
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
        self.hp: float = self.get_stat(Stat.HP)
        self.damage_taken: float = 0
        self.healed: float = 0
        self.damage_shielded: float = 0
        self.shields: list[tuple[float, float]] = []

        self.ability_dict: dict[ActionType, tuple[ChampionAbility, int]] = {
            ActionType.Q: (self.champion.q, rank.q),
            ActionType.W: (self.champion.w, rank.w),
            ActionType.E: (self.champion.e, rank.e),
            ActionType.R: (self.champion.r, rank.r)
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
        base_value = getattr(self.champion, stat_name, None)
        if base_value is None:
            return 0    
        scaling_attr = f"{stat_name}_per_lvl"
        scaling_value = getattr(self.champion, scaling_attr, 0)
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
        bonus = self.champion.attackspeed_per_lvl * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1))
        bonus += self.get_bonus_stat(Stat.ATTACKSPEED_P)
        result = self.champion.attackspeed + self.champion.attackspeed_ratio * bonus / 100
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
    



    def calculate_hp_scaling(self, value: float, dmg_calc: DamageCalculation) -> float:
        match dmg_calc:
            case DamageCalculation.MAX_HP:
                return value * self.get_stat(Stat.HP)
            case DamageCalculation.CURRENT_HP:
                return value * self.hp
            case DamageCalculation.MISSING_HP:
                return value * (self.get_stat(Stat.HP) - self.hp)
        return value


    def calculate_damage(self, damage: ProcessedDamageProperties) -> float:
        value = self.calculate_hp_scaling(damage.value, damage.dmg_calc)
        resistance = self.get_resistance(damage.dmg_sub_type)
        resistance -= (resistance * damage.percent_pen / 100)
        resistance -= damage.flat_pen
        resistance = max(resistance, 0)
        result = value * (100 / (resistance + 100))
        return result
    

    def apply_heals(self, values: list[float]) -> None:
        heal = sum(values)
        max_hp = self.get_stat(Stat.HP)
        heal = min(heal, max_hp - self.hp)
        self.healed += heal
        self.hp += heal
    

    def apply_shields(self, values: list[tuple[float, float]], timestamp: float) -> None:
        self.shields = [(exp, val) for exp, val in self.shields if exp > timestamp and val > 0]
        new_shields = [(duration+timestamp, val) for duration, val in values]
        self.shields.extend(new_shields)
        self.shields.sort()
    

    def apply_damages(self, values: list[float]) -> None:
        damage = sum(values)
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




    def do_action(self, key: ActionType, timestamp: float) -> ActionEffect:
        if key == ActionType.AA:
            return self.basic_attack(timestamp)
        elif key in self.ability_dict:
            return self.do_ability(key, timestamp)


    def basic_attack(self, timestamp: float) -> ActionEffect:
        attack_time = 1 / self.get_attackspeed()
        time = max(self.cooldowns[ActionType.AA], timestamp)
        self.cooldowns[ActionType.AA] = time + attack_time
        #TODO delete /100 again
        time += attack_time * self.champion.attack_windup/100
        aa_props = DamageProperties(
            scaling=Stat.AD.value,
            dmg_type=DamageType.BASIC  #TODO check if Basic is right damage type
        )
        dmg = EffectDamage(
            source=ActionType.AA,
            target=Target.DEFENDER,
            type_= StatusType.DAMAGE,
            speed=self.champion.missile_speed,
            props=aa_props
        )
        self.last_action = ActionType.AA
        return ActionEffect(time=time, stati=[dmg])
    

    def do_ability(self, key: ActionType, timestamp: float) -> ActionEffect:
        ability: ChampionAbility = self.ability_dict[key][0]
        time = max(self.cooldowns[key], timestamp)
        cooldown = self.evaluate_formula(ability.cooldown, {"rank": self.ability_dict[key][1]})
        cooldown *= 100 / (100 + self.get_bonus_stat(Stat.ABILITY_HASTE))
        self.cooldowns[key] = time + ability.cast_time + cooldown
        action_effect = ActionEffect(time=time + ability.cast_time)
        self.last_action = key
        for effect in ability.effects:
            for status in effect.stati:
                effect_status = EffectStatus(
                    source=key,
                    target=Target.DEFENDER,
                    type_=status.type_,
                    duration=status.duration,
                    interval=status.interval,
                    delay=status.delay,
                    speed=status.speed,
                    props=status.props
                )
                if status.type_ in [StatusType.HEAL, StatusType.SHIELD]:
                    effect_status.target=Target.ATTACKER
                action_effect.stati.append(effect_status)
        return action_effect
    


    def evaluate(self, queue_stati:list[QueueStatus]) -> list[QueueStatus]:
        status_list = []
        for status in queue_stati:
            if status.type_ == StatusType.SHADOW:
                continue
            variables = {"rank": self.ability_dict[status.source][1]} if status.source in self.ability_dict else {}
            result = self.evaluate_formula(status.props.scaling, variables)
            
            match status.type_:
                case StatusType.DAMAGE:
                    flat_pen, percent_pen = self.get_penetration(status.props.dmg_sub_type)
                    props=ProcessedDamageProperties(
                        value=result,
                        flat_pen=flat_pen,
                        percent_pen=percent_pen,
                        dmg_type=status.props.dmg_type,
                        dmg_sub_type=status.props.dmg_sub_type,
                        dmg_calc=status.props.dmg_calc,
                    )
                case StatusType.HEAL:
                    props=ProcessedHealProperties(
                        value=result,
                        dmg_calc=status.props.dmg_calc
                    )
                case StatusType.SHIELD:
                    props=ProcessedShieldProperties(
                        value=result,
                        duration=status.props.duration,
                        dmg_sub_type=status.props.dmg_sub_type,
                        dmg_calc=status.props.dmg_calc
                    )
                case _:
                   raise ValueError(f"Unhandled StatusType: {status.type_}")  # Catch future issues early

            queue_status = QueueStatus(
                source=status.source,
                type_=status.type_,
                target=status.target,
                props=props
        )
            queue_status.props=props
            status_list.append(queue_status)
        return status_list

        

    def take_stati(self, status_list: list[QueueStatus], timestamp: float) -> None:
        damages = []
        heals = []
        shields = []
        for status in status_list:
            match status.type_:
                case StatusType.DAMAGE:
                    damages.append(self.calculate_damage(status.props))
                case StatusType.HEAL:
                    heals.append(self.calculate_hp_scaling(status.props.value, status.props.dmg_calc))
                case StatusType.SHIELD:
                    shields.append((status.props.duration, self.calculate_hp_scaling(status.props.value, status.props.dmg_calc)))
                case _:
                    pass
        self.apply_shields(shields, timestamp)
        self.apply_damages(damages)
        self.apply_heals(heals)