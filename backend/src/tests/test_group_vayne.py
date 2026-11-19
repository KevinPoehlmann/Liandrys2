import math

import pytest

from src.server.models.dataenums import ActionType, Actor, DamageSubType, EffectType, StatusType, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the patch 15.12.1 fixtures, not by the simulation.
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
VAYNE_AD = 60 + 2.35 * GROWTH_LVL_6
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6
ANNIE_ARMOR_LVL_1 = 23

Q_RANK_3 = 0.95
W_RANK_1_PERCENT = 0.06
W_RANK_1_MINIMUM = 50
E_RANK_1 = 50
R_RANK_1_AD = 35


def physical(raw: float, armor: float = DARIUS_ARMOR) -> float:
    return raw * 100 / (100 + armor)


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def true_damage_hits(sim: Simulation) -> list[float]:
    return [
        result.value
        for event in sim.effect_list
        for result in event.result
        if result.type_ == EffectType.DAMAGE and result.damage_sub_type == DamageSubType.TRUE
    ]


@pytest.fixture
def vayne(load_champion) -> Character:
    return Character(load_champion("vayne"), 6, Rank(q=3, w=1, e=1, r=1), [])


@pytest.fixture
def vs_darius(vayne, load_champion) -> Simulation:
    darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
    return Simulation(vayne, darius)


@pytest.fixture
def vs_annie_lvl_1(vayne, load_champion) -> Simulation:
    annie = Character(load_champion("annie"), 1, Rank(q=1, w=0, e=0, r=0), [])
    return Simulation(vayne, annie)


class TestVayne():

    def test_q_empowers_next_attack(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.AA, ActionType.Q, ActionType.AA))

        expected = physical(2 * VAYNE_AD) + physical(Q_RANK_3 * VAYNE_AD)
        assert vs_darius.actors[Actor.RED].damage_taken == pytest.approx(expected)
        assert true_damage_hits(vs_darius) == []


    def test_w_procs_on_third_hit(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.AA, ActionType.Q, ActionType.AA, ActionType.AA))

        w_proc = W_RANK_1_PERCENT * DARIUS_MAX_HP
        expected = physical(3 * VAYNE_AD) + physical(Q_RANK_3 * VAYNE_AD) + w_proc
        assert vs_darius.actors[Actor.RED].damage_taken == pytest.approx(expected)
        assert true_damage_hits(vs_darius) == [pytest.approx(w_proc)]


    def test_w_stacks_reset_after_proc(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(*[ActionType.AA] * 6))

        w_proc = W_RANK_1_PERCENT * DARIUS_MAX_HP
        assert true_damage_hits(vs_darius) == [pytest.approx(w_proc)] * 2
        assert vs_darius.actors[Actor.RED].get_buff_stacks("silver_bolts") == 0


    def test_w_proc_has_minimum_damage(self, vs_annie_lvl_1: Simulation):
        vs_annie_lvl_1.do_combo(combo(ActionType.AA, ActionType.AA, ActionType.AA))

        # 6% of Annie's 560 max HP is 33.6, below the minimum.
        expected = physical(3 * VAYNE_AD, ANNIE_ARMOR_LVL_1) + W_RANK_1_MINIMUM
        assert vs_annie_lvl_1.actors[Actor.RED].damage_taken == pytest.approx(expected)
        assert true_damage_hits(vs_annie_lvl_1) == [pytest.approx(W_RANK_1_MINIMUM)]


    def test_e_applies_silver_bolts(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.E, ActionType.AA, ActionType.AA))

        w_proc = W_RANK_1_PERCENT * DARIUS_MAX_HP
        expected = physical(E_RANK_1) + physical(2 * VAYNE_AD) + w_proc
        assert vs_darius.actors[Actor.RED].damage_taken == pytest.approx(expected)
        assert true_damage_hits(vs_darius) == [pytest.approx(w_proc)]


    def test_final_hour_grants_bonus_ad(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.R, ActionType.AA))

        expected = physical(VAYNE_AD + R_RANK_1_AD)
        assert vs_darius.actors[Actor.RED].damage_taken == pytest.approx(expected)


Q_RANK_3_COOLDOWN_TICKS = to_ticks(4)
Q_CAST_TICKS = to_ticks(300 / (500 + 330))
TUMBLE_TICKS = to_ticks(3)
R_RANK_1_Q_COOLDOWN_REDUCTION = 0.3


def first_hit_tick(sim: Simulation, source: ActionType) -> int:
    return next(
        event.tick
        for event in sim.effect_list
        for result in event.result
        if result.source == source and result.type_ == EffectType.DAMAGE
    )


E_RANK_1_WALL = 75
E_KNOCKBACK_TICKS = to_ticks(475 / 2000)


def hit_ticks(sim: Simulation, source: ActionType) -> list[int]:
    return [
        event.tick
        for event in sim.effect_list
        for result in event.result
        if result.source == source and result.type_ == EffectType.DAMAGE
    ]


class TestVayneTerrain():

    def test_e_stuns_against_a_wall(self, load_champion):
        vayne = Character(load_champion("vayne"), 6, Rank(q=3, w=1, e=1, r=1), [], scenario={"terrain": 1})
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(vayne, darius)

        sim.do_combo(combo(ActionType.E))

        knockback_tick, wall_tick = hit_ticks(sim, ActionType.E)
        assert wall_tick - knockback_tick == E_KNOCKBACK_TICKS
        assert darius.damage_taken == pytest.approx(physical(E_RANK_1) + physical(E_RANK_1_WALL))
        assert StatusType.STUN in darius.status_effects


    def test_e_without_wall_does_not_stun(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.E))

        darius = vs_darius.actors[Actor.RED]
        assert darius.damage_taken == pytest.approx(physical(E_RANK_1))
        assert StatusType.AIRBORNE in darius.status_effects
        assert StatusType.STUN not in darius.status_effects


class TestVayneTiming():

    def test_q_cooldown_starts_when_tumble_is_consumed(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.Q, ActionType.AA))

        hit_tick = first_hit_tick(vs_darius, ActionType.Q)
        assert vs_darius.actors[Actor.BLUE].cooldowns[ActionType.Q] == hit_tick + Q_RANK_3_COOLDOWN_TICKS


    def test_q_cooldown_starts_when_tumble_expires(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.Q))

        expected = Q_CAST_TICKS + TUMBLE_TICKS + Q_RANK_3_COOLDOWN_TICKS
        assert vs_darius.actors[Actor.BLUE].cooldowns[ActionType.Q] == expected


    def test_final_hour_shortens_q_cooldown(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.R, ActionType.Q))

        shortened = round(Q_RANK_3_COOLDOWN_TICKS * (1 - R_RANK_1_Q_COOLDOWN_REDUCTION))
        assert vs_darius.actors[Actor.BLUE].cooldowns[ActionType.Q] == Q_CAST_TICKS + TUMBLE_TICKS + shortened


    def test_final_hour_stealth_starts_on_q_and_ends_on_attack(self, vs_darius: Simulation):
        vayne = vs_darius.actors[Actor.BLUE]
        r, q, aa = combo(ActionType.R, ActionType.Q, ActionType.AA)

        vs_darius.do_action(r)
        vs_darius.do_action(q)
        vs_darius._process_queue()
        assert vayne.get_buff_stacks("final_hour_stealth") == 1

        vs_darius.do_action(aa)
        vs_darius._process_queue()
        assert vayne.get_buff_stacks("final_hour_stealth") == 0
