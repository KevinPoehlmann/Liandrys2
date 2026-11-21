import pytest

from src.server.models.dataenums import ActionType, Actor, Stat, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


FINAL_HOUR_RANK_1_TICKS = to_ticks(8)


@pytest.fixture
def vayne(load_champion) -> Character:
    return Character(load_champion("vayne"), 6, Rank(q=3, w=1, e=1, r=1), [])

@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


class TestBuffInstances():

    def test_buff_stats_count_while_active(self, vayne):
        base_ad = vayne.get_stat(Stat.AD)

        vayne.apply_buff("final_hour", vayne, 1, 0)

        assert vayne.get_stat(Stat.AD) == pytest.approx(base_ad + 35)


    def test_buff_ends_after_its_duration(self, vayne, darius):
        sim = Simulation(vayne, darius)

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.R)])

        assert sim.tick == FINAL_HOUR_RANK_1_TICKS
        assert vayne.get_buff_stacks("final_hour") == 0


    def test_refresh_ignores_the_outdated_end(self, vayne):
        vayne.apply_buff("final_hour", vayne, 1, 0)
        vayne.apply_buff("final_hour", vayne, 1, 60)

        vayne.expire_buff("final_hour", FINAL_HOUR_RANK_1_TICKS)
        assert vayne.get_buff_stacks("final_hour") == 1

        vayne.expire_buff("final_hour", 60 + FINAL_HOUR_RANK_1_TICKS)
        assert vayne.get_buff_stacks("final_hour") == 0


    def test_stacks_are_capped_at_max_stacks(self, vayne, darius):
        for _ in range(4):
            darius.apply_buff("silver_bolts", vayne, 1, 0)

        assert darius.get_buff_stacks("silver_bolts") == 3


    def test_removing_stacks_ends_the_buff_at_zero(self, vayne, darius):
        darius.apply_buff("silver_bolts", vayne, 3, 0)

        darius.remove_stacks("silver_bolts", 1, 0)
        assert darius.get_buff_stacks("silver_bolts") == 2

        darius.remove_stacks("silver_bolts", 2, 0)
        assert "silver_bolts" not in darius.active_buffs


    def test_buff_uses_the_rank_of_its_source(self, vayne, load_champion):
        vayne_rank_3 = Character(load_champion("vayne"), 16, Rank(q=5, w=5, e=5, r=3), [])

        vayne.apply_buff("final_hour", vayne_rank_3, 1, 0)

        assert vayne.active_buffs["final_hour"].end == to_ticks(12)
