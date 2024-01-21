
from abc import ABC, abstractmethod

from src.server.models.dataenums import Damage, DamageCalculation, DamageSubType, Stat
from src.server.models.champion import Champion
from src.server.models.item import Item
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.models.unit import Unit, Fighter


    


class Dummy():
    def __init__(self, unit: Unit):
        self.unit: Unit = unit
        self.hp = unit.hp



    def calculate_damage(self, value: float, resistance: float, dcalc: DamageCalculation) -> float:
        #TODO add Penetration
        match dcalc:
            case DamageCalculation.MAX_HP:
                value *= self.unit.hp
            case DamageCalculation.CURRENT_HP:
                value *= self.hp
            case DamageCalculation.MISSING_HP:
                value *= (self.unit.hp - self.hp)
        result = value * (100 / (resistance + 100))
        return result


    def take_damge(self, damages: list[Damage]) -> int:
        results = []
        for damage in damages:
            match damage.dtype:
                case DamageSubType.TRUE:
                    results.append(self.calculate_damage(damage.value, 0, damage.dcalc))
                case DamageSubType.PHYSIC:
                    results.append(self.calculate_damage(damage.value, self.unit.armor, damage.dcalc))
                case DamageSubType.MAGIC:
                    results.append(self.calculate_damage(damage.value, self.unit.mr, damage.dcalc))
        result = sum(results)
        self.hp -= result
        return result




class Attacker(Dummy):
    def __init__(self, fighter: Fighter):
        super().__init__(unit=fighter)
        self.unit: Fighter = fighter


    @abstractmethod
    def basic_attack(self) -> None:
        pass


class Character(Attacker):
    #TODO Level Scaling
    def __init__(self, champion: Champion, lvl: int, items: list[Item]) -> None:
        #TODO add items, runes and summonerspells
        super().__init__(champion)
        self.unit: Champion = champion
        self.level: int = lvl
        self.items: list[Item] = items


    def calculate_stat(self, stat: float, scaling: float) -> float:
        return (stat + scaling * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1)))
    

    def get_bonus_stat(self, stat: Stat) -> float:
        bonus_stat = 0
        for item in self.items:
            for st in item.stats:
                if st.stat == stat:
                    bonus_stat += st.value
                    break
        return bonus_stat



    def basic_attack(self) -> Damage:
        #TODO add Penetration
        base_ad = self.calculate_stat(self.unit.ad, self.unit.ad_per_lvl)
        bonus_ad = self.get_bonus_stat(Stat.AD)
        return Damage(base_ad + bonus_ad, DamageSubType.PHYSIC, DamageCalculation.FLAT)