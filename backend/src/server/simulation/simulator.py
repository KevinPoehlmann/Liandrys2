from src.server.models.unit import Unit
from src.server.models.champion import Champion
from src.server.models.dataenums import ActionType, ActionEffect
from src.server.models.item import Item
from src.server.models.request import V1Response
from src.server.simulation.unit import Dummy, Character


class DummySimulation():
    def __init__(self, dummy: Dummy, character: Character, combo: list[ActionType]):
        self.dummy: Dummy = dummy
        self.character: Character = character
        self.combo: list[ActionType] = combo


    def do_action(self, key: ActionType) -> tuple[int, float]:
        action_effect = self.character.do_action(key)
        result = self.dummy.take_damge(action_effect)
        return (result, action_effect.time)


    def do_combo(self) -> tuple[int, float]:
        result = 0
        timer = 0.0
        for action in self.combo:
            dmg, time = self.do_action(action)
            result += dmg
            timer += time
        return (result, timer)



class V1Simulation():
    def __init__(self, attacker: Character, defender: Character, combo: list[ActionType]):
        self.attacker: Character = attacker
        self.defender: Character = defender
        self.combo: list[ActionType] = combo
    

    def do_action(self, key: ActionType) -> tuple[int, float]:
        action_effect = self.attacker.do_action(key)
        result = self.defender.take_damge(action_effect)
        return (result, action_effect.time)


    def do_combo(self) -> V1Response:
        result = 0
        timer = 0.0
        for action in self.combo:
            dmg, time = self.do_action(action)
            result += dmg
            timer += time
        return V1Response(damage=result, time=timer)