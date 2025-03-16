import pytest


from src.server.models.dataenums import ActionType



class TestDummySimulation():
    
    def test_do_action(self, dummy_sim):
        time = dummy_sim.do_action(ActionType.AA)
        assert time == 0.215
        assert dummy_sim.dummy.hp == 919.70
        assert dummy_sim.dummy.damage_taken == 80.30


    def test_do_combo(self, dummy_sim):
        result = dummy_sim.do_combo()
        assert result.time == 1.31
        assert result.damage == 161
        assert dummy_sim.dummy.hp == 839.40


class TestV1Simulator():
    
    def test_do_action(self, v1_sim):
        time = v1_sim.do_action(ActionType.AA)
        assert time == 0.215
        assert v1_sim.defender.damage_taken == 55.295
        assert v1_sim.defender.hp == 1246.965

    def test_do_combo(self, v1_sim):
        result = v1_sim.do_combo()
        assert result.damage == 111
        assert result.time == 1.31
        assert v1_sim.defender.hp == 1191.67