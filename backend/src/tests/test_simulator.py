import pytest



from src.server.simulation.simulator import V1Simulation



class TestDummySimulation():
    
    def test_attack(self, dummy_sim):
        result = dummy_sim.attack()
        assert result == 80.30


    def test_do_combo(self, dummy_sim):
        result = dummy_sim.do_combo()
        assert result == 160.60


class TestV1Simulator():
    
    def test_attack(self, v1_sim):
        result = v1_sim.attack()
        assert result == 55.29
        assert v1_sim.defender.hp == 1246.97


    def test_do_combo(self, v1_sim):
        result = v1_sim.do_combo()
        assert result.damage == 110
        assert result.time == 2.17
        assert v1_sim.defender.hp == 1191.68