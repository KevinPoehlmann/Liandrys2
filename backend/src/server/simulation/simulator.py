from src.server.models.unit import Unit
from src.server.models.champion import Champion
from src.server.simulation.unit import Dummy, Character


class DummySimulation():
    def __init__(self, champion: Champion, lvl: int):
        self.dummy = Dummy(Unit(hp=1000, armor=50, mr=50))
        self.character = Character(champion, lvl)


    def attack(self) -> int:
        dmg = self.character.basic_attack()
        result = self.dummy.take_damge([dmg])
        return round(result)
