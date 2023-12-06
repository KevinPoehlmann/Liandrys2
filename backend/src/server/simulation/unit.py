
from abc import ABC, abstractmethod

from src.server.models.dataenums import Damage, DamageCalculation, DamageSubType
from src.server.models.champion import Champion
from src.server.models.item import Item
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.models.unit import Unit, Fighter


    


class Dummy(ABC):
    def __init__(self, unit: Unit):
        self.unit: Unit = unit
        self.hp = unit.hp



    def calculate_damage(self, value: float, resistance: int, dcalc: DamageCalculation) -> int:
        #TODO add Penetration
        match dcalc:
            case DamageCalculation.MAX_HP:
                value *= self.unit.hp
            case DamageCalculation.CURRENT_HP:
                value *= self.hp
            case DamageCalculation.MISSING_HP:
                value *= (self.unit.hp - self.hp)
        result = value * (100 / (resistance + 100))
        return round(result)


    def take_damge(self, damages: list[Damage]) -> int:
        results = []
        for damage in damages:
            match damage.dtype:
                case DamageSubType.TRUE:
                    results.append(self.calculate_damage(damage.value, 0, damage.dcalc))
                case DamageSubType.PHYSIC:
                    results.append(self.calculate_damage(damage.value, self.ARMOR, damage.dcalc))
                case DamageSubType.MAGIC:
                    results.append(self.calculate_damage(damage.value, self.MR, damage.dcalc))
        result = sum(results)
        self.hp -= result
        return result




class Attacker(Dummy):
    def __init__(self, fighter: Fighter):
        super().__init__(unit=fighter)
        self.unit: Fighter = fighter


    @abstractmethod
    def attack(self) -> None:
        pass


class Character(Attacker):
    
    def __init__(self, champion: Champion, lvl: int):
        #TODO add items, runes and summonerspells
        super().__init__(champion.hp, champion.armor, champion.mr)
        self.unit: Champion = champion



    def attack(self) -> None:
        pass