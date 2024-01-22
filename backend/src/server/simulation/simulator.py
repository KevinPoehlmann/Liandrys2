from src.server.models.unit import Unit
from src.server.models.champion import Champion
from src.server.models.dataenums import ActionType
from src.server.models.item import Item
from src.server.simulation.unit import Dummy, Character


class DummySimulation():
    def __init__(self, champion: Champion, lvl: int, items: list[Item], combo: list[ActionType]):
        self.dummy = Dummy(Unit(hp=1000, armor=50, mr=50))
        self.character = Character(champion, lvl, items)
        self.combo = combo


    def do_combo(self) -> int:
        result = 0
        for action in self.combo:
            match action:
                case ActionType.AA: result += self.attack()
        return result



    def attack(self) -> int:
        dmg = self.character.basic_attack()
        result = self.dummy.take_damge([dmg])
        return round(result)




class V1Simulation():
    def __init__(self, attacker: Champion, alvl: int, combo: list[ActionType]):
        pass