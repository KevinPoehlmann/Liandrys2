import math

import pytest

from src.server.models.dataenums import ActionType, Actor, DamageSubType, EffectType, Stat, to_ticks
from src.server.models.request import Action, Rank
from src.server.models.rule import Buff, Rule
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


    def test_buff_uses_the_rank_of_its_source(self, vayne, load_champion):
        vayne_rank_3 = Character(load_champion("vayne"), 16, Rank(q=5, w=5, e=5, r=3), [])

        vayne.apply_buff("final_hour", vayne_rank_3, 1, 0)

        assert vayne.active_buffs["final_hour"].end == to_ticks(12)


IGNITE_INTERVAL = 1.056
IGNITE_TICK = 14


@pytest.fixture
def vayne_with_ignite_on_hit(load_champion) -> Character:
    # Placeholder until the real Ignite (test_group/summonerspells) runs in the new system:
    # first tick on application, no tick at the end.
    champion = load_champion("vayne")
    champion.passive.buffs.append(Buff.parse_obj({
        "name": "burn", "duration": "5", "interval": str(IGNITE_INTERVAL), "tick_on_apply": True,
        "rules": [{"trigger": "on_interval", "actions": [{"type_": "Damage", "props": {
            "target": "bearer", "scaling": str(IGNITE_TICK), "dmg_type": ["Proc damage"], "dmg_sub_type": "True"}}]}]
    }))
    champion.passive.rules.append(Rule.parse_obj({
        "trigger": "on_hit", "actions": [{"type_": "ApplyBuff", "props": {"buff": "burn", "target": "target"}}]
    }))
    return Character(champion, 6, Rank(q=3, w=0, e=1, r=1), [])


class TestIntervalBuffs():

    def test_tick_on_apply_without_tick_on_end(self, vayne_with_ignite_on_hit, darius):
        sim = Simulation(vayne_with_ignite_on_hit, darius)

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)])

        burn_ticks = [
            event.tick
            for event in sim.effect_list
            for result in event.result
            if result.type_ == EffectType.DAMAGE and result.damage_sub_type == DamageSubType.TRUE
        ]
        [hit] = [event.tick for event in sim.effect_list for result in event.result if result.source == ActionType.AA]
        assert burn_ticks == [hit + to_ticks(k * IGNITE_INTERVAL) for k in range(5)]
