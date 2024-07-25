from src.server.models.unit import Unit
from src.server.models.champion import Champion
from src.server.models.dataenums import ActionType
from src.server.models.item import Item
from src.server.models.request import V1Response
from src.server.simulation.unit import Dummy, Character


class DummySimulation():
    def __init__(self, dummy: Dummy, character: Character, combo: list[ActionType]):
        self.dummy: Dummy = dummy
        self.character: Character = character
        self.combo: list[ActionType] = combo


    def attack(self) -> int:
        dmg = self.character.basic_attack()
        result = self.dummy.take_damge([dmg])
        return result


    def do_combo(self) -> int:
        result = 0
        for action in self.combo:
            match action:
                case ActionType.AA: result += self.attack()
        return result





class V1Simulation():
    def __init__(self, attacker: Character, defender: Character, combo: list[ActionType]):
        self.attacker: Character = attacker
        self.defender: Character = defender
        self.combo: list[ActionType] = combo
    

    def attack(self) -> int:
        dmg = self.attacker.basic_attack()
        result = self.defender.take_damge([dmg])
        return result


    def do_combo(self) -> V1Response:
        result = 0
        timer = 0.0
        for action in self.combo:
            match action:
                case ActionType.AA:
                    result += self.attack()
                    timer += 1 / self.attacker.attackspeed

        return V1Response(damage=result, time=round(timer, 2))