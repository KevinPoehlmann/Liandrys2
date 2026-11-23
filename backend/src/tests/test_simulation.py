from dataclasses import replace

import pytest

from src.server.models.enums import ActionType, Actor
from src.server.models.request import Action
from src.server.simulation.simulation import Simulation
from src.tests.helpers import regenerated_health


class TestSimulation():

    def test_cast(self, sim: Simulation, action_effect_aa):
        sim._cast(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA))
        assert sim.tick == 7
        assert list(sim.queue.keys())[0] == 7
        # The queued attack carries its cast instance (the first cast of the simulation).
        assert list(sim.queue.values())[0][0] == replace(action_effect_aa.rule_events[0], cast=1)


    @pytest.mark.parametrize("input, output", [
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA)], (55, 7, 1246.965)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA)], (111, 41, 1191.67)),
    ])
    def test_do_combo(self, sim: Simulation, input, output):
        result = sim.do_combo(input)
        assert result.damage == output[0]
        assert result.ticks == output[1]
        assert round(sim.actors[Actor.RED].current_hp - regenerated_health(sim, Actor.RED), 3) == output[2]
