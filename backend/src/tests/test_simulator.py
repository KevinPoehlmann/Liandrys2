import pytest


from src.server.models.dataenums import ActionType
from src.server.simulation.simulator import V1Simulation



class TestDummySimulation():
    
    def test_do_action(self, dummy_sim):
        damage, time = dummy_sim.do_action(ActionType.AA)
        assert damage == 80.30


    def test_do_combo(self, dummy_sim):
        damage, time = dummy_sim.do_combo()
        assert damage == 160.60


class TestV1Simulator():
    
    def test_do_action(self, v1_sim):
        damage, time = v1_sim.do_action(ActionType.AA)
        assert damage == 55.3
        assert v1_sim.defender.hp == 1246.96

    def test_do_combo(self, v1_sim):
        result = v1_sim.do_combo()
        assert result.damage == 110
        assert result.time == 1.3
        assert v1_sim.defender.hp == 1191.66