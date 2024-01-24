
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



    def calculate_damage(self, damage: Damage, resistance: float) -> float:
        match damage.dcalc:
            case DamageCalculation.MAX_HP:
                damage.value *= self.unit.hp
            case DamageCalculation.CURRENT_HP:
                damage.value *= self.hp
            case DamageCalculation.MISSING_HP:
                damage.value *= (self.unit.hp - self.hp)
        resistance -= (resistance * damage.perc_pen / 100)
        resistance -= damage.flat_pen
        resistance = max(resistance, 0)
        result = damage.value * (100 / (resistance + 100))
        return result


    def take_damge(self, damages: list[Damage]) -> int:
        results = []
        for damage in damages:
            match damage.dtype:
                case DamageSubType.TRUE:
                    results.append(self.calculate_damage(damage, 0))
                case DamageSubType.PHYSIC:
                    results.append(self.calculate_damage(damage, self.unit.armor))
                case DamageSubType.MAGIC:
                    results.append(self.calculate_damage(damage, self.unit.mr))
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
    def __init__(self, champion: Champion, lvl: int, items: list[Item]) -> None:
        #TODO add runes and summonerspells
        super().__init__(champion)
        self.unit: Champion = champion
        self.level: int = lvl
        self.items: list[Item] = items


    def calculate_stat(self, stat: float, scaling: float) -> float:
        return (stat + scaling * (self.level - 1) * (0.7025 + 0.0175 * (self.level - 1)))
    

    def get_bonus_stat(self, stat: Stat) -> float:
        return sum([item.stats[stat] for item in self.items if stat in item.stats])



    def basic_attack(self) -> Damage:

        dmg = Damage(
            value=self.calculate_stat(self.unit.ad, self.unit.ad_per_lvl) + self.get_bonus_stat(Stat.AD),
            flat_pen=self.get_bonus_stat(Stat.LETHALITY),
            perc_pen=self.get_bonus_stat(Stat.ARMOR_PEN_P),
            dtype=DamageSubType.PHYSIC,
            dcalc=DamageCalculation.FLAT
        )
        return dmg
    

    def take_damge(self, damages: list[Damage]) -> int:
        results = []
        for damage in damages:
            match damage.dtype:
                case DamageSubType.TRUE:
                    results.append(self.calculate_damage(damage, 0))
                case DamageSubType.PHYSIC:
                    armor = self.calculate_stat(self.unit.armor, self.unit.armor_per_lvl) + self.get_bonus_stat(Stat.ARMOR)
                    results.append(self.calculate_damage(damage, armor))
                case DamageSubType.MAGIC:
                    mr = self.calculate_stat(self.unit.mr, self.unit.mr_per_lvl) + self.get_bonus_stat(Stat.MR)
                    results.append(self.calculate_damage(damage, mr))
        result = sum(results)
        self.hp -= result
        return result