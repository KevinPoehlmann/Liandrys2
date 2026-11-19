import json
import math

import pytest

from src.server.models.dataenums import ActionType, Actor, DamageSubType, EffectType, Stat, StatusType, TICKRATE
from src.server.models.item import Item
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the patch 15.12.1 fixtures, not by the simulation.
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
DARIUS_AD = 64 + 5 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6
DARIUS_ATTACKSPEED = 0.625 + 0.625 * 0.01 * GROWTH_LVL_6
ATTACK_TICKS = math.ceil(TICKRATE / DARIUS_ATTACKSPEED)
WINDUP_TICKS = math.ceil(0.2 * TICKRATE / DARIUS_ATTACKSPEED)
VAYNE_ARMOR = 23 + 4.6 * GROWTH_LVL_6

E_RANK_1_ARMOR_PEN = 0.2
BLEED_LVL_6 = 18
BLEED_TICK_PER_STACK = BLEED_LVL_6 / 4
BLEED_TICKS = 1.25 * TICKRATE
BLEED_DURATION_TICKS = 5 * TICKRATE
NOXIAN_MIGHT_LVL_6 = 55
Q_RANK_3 = 110 + 1.2 * DARIUS_AD
Q_CAST_TICKS = math.ceil(0.75 * TICKRATE)
Q_HEAL_PERCENT = 0.15
Q_HANDLE = 0.35
Q_RANK_3_COOLDOWN_TICKS = 7 * TICKRATE
W_RANK_1 = 0.4 * DARIUS_AD
W_COOLDOWN_TICKS = 5 * TICKRATE
E_CAST_TICKS = math.ceil(0.25 * TICKRATE)
E_AIRBORNE_TICKS = math.ceil(0.5 * TICKRATE)
R_RANK_1 = 125
R_RANK_1_COOLDOWN_TICKS = 120 * TICKRATE
R_BONUS_PER_STACK = 0.2


def physical(raw: float, armor: float = VAYNE_ARMOR * (1 - E_RANK_1_ARMOR_PEN)) -> float:
    return raw * 100 / (100 + armor)


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def q_with(outcome: str) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q, outcome=outcome)]


def hits(sim: Simulation, source: ActionType) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.source == source and result.type_ == EffectType.DAMAGE
    ]


def bleed_ticks(start: int, end: int) -> list[int]:
    # The bleed keeps the rhythm of its first stack and ticks once more when it ends.
    ticks = []
    k = 1
    while start + math.ceil(k * BLEED_TICKS) <= end:
        ticks.append(start + math.ceil(k * BLEED_TICKS))
        k += 1
    return ticks if ticks[-1] == end else ticks + [end]


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=3, w=1, e=1, r=1), [])


@pytest.fixture
def vs_vayne(darius, load_champion) -> Simulation:
    vayne = Character(load_champion("vayne"), 6, Rank(q=3, w=1, e=1, r=1), [])
    return Simulation(darius, vayne)


class TestDariusHemorrhage():

    def test_attack_applies_a_bleed_over_five_seconds(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.AA))

        hit = WINDUP_TICKS
        assert hits(vs_vayne, ActionType.AA) == [(hit, pytest.approx(physical(DARIUS_AD)))]
        assert [tick for tick, _ in hits(vs_vayne, ActionType.PASSIVE)] == bleed_ticks(hit, hit + BLEED_DURATION_TICKS)
        assert vs_vayne.actors[Actor.RED].damage_taken == pytest.approx(physical(DARIUS_AD + BLEED_LVL_6))


    def test_refresh_keeps_the_rhythm_and_ticks_at_the_end(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.AA, ActionType.AA))

        first_hit, second_hit = WINDUP_TICKS, ATTACK_TICKS + WINDUP_TICKS
        expected_ticks = bleed_ticks(first_hit, second_hit + BLEED_DURATION_TICKS)
        stacks = [1 if tick < second_hit else 2 for tick in expected_ticks]
        bleed = hits(vs_vayne, ActionType.PASSIVE)
        assert [tick for tick, _ in bleed] == expected_ticks
        assert [value for _, value in bleed] == [pytest.approx(physical(BLEED_TICK_PER_STACK * s)) for s in stacks]


    def test_noxian_might_at_five_stacks_and_refreshed_by_each_hit(self, vs_vayne: Simulation):
        # Hits 6 to 9 land more than 5 seconds after the 5th, so the buff only lasts if every hit refreshes it.
        vs_vayne.do_combo(combo(*[ActionType.AA] * 9))

        attacks = [value for _, value in hits(vs_vayne, ActionType.AA)]
        assert attacks[:5] == [pytest.approx(physical(DARIUS_AD))] * 5
        assert attacks[5:] == [pytest.approx(physical(DARIUS_AD + NOXIAN_MIGHT_LVL_6))] * 4


class TestDariusAbilities():

    def test_q_blade_damages_heals_and_bleeds(self, vs_vayne: Simulation):
        darius = vs_vayne.actors[Actor.BLUE]
        darius.current_hp = DARIUS_MAX_HP - 400

        vs_vayne.do_combo(combo(ActionType.Q))

        assert hits(vs_vayne, ActionType.Q) == [(Q_CAST_TICKS, pytest.approx(physical(Q_RANK_3)))]
        assert darius.current_hp == pytest.approx(DARIUS_MAX_HP - 400 + Q_HEAL_PERCENT * 400)
        assert vs_vayne.actors[Actor.RED].damage_taken == pytest.approx(physical(Q_RANK_3 + BLEED_LVL_6))


    def test_q_handle_deals_reduced_damage_without_heal_or_bleed(self, vs_vayne: Simulation):
        darius = vs_vayne.actors[Actor.BLUE]
        darius.current_hp = DARIUS_MAX_HP - 400

        vs_vayne.do_combo(q_with("handle"))

        assert vs_vayne.actors[Actor.RED].damage_taken == pytest.approx(physical(Q_HANDLE * Q_RANK_3))
        assert darius.current_hp == pytest.approx(DARIUS_MAX_HP - 400)


    def test_q_miss_deals_nothing_but_starts_cooldown(self, vs_vayne: Simulation):
        vs_vayne.do_combo(q_with("miss"))

        assert vs_vayne.actors[Actor.RED].damage_taken == 0
        assert vs_vayne.actors[Actor.BLUE].cooldowns[ActionType.Q] == Q_CAST_TICKS + Q_RANK_3_COOLDOWN_TICKS


    def test_unknown_outcome_is_rejected(self, vs_vayne: Simulation):
        with pytest.raises(SimulationError, match="sweetspot"):
            vs_vayne.do_combo(q_with("sweetspot"))


    def test_attack_windup_delays_q(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.AA, ActionType.Q))

        [(q_tick, _)] = hits(vs_vayne, ActionType.Q)
        assert q_tick == WINDUP_TICKS + Q_CAST_TICKS


    def test_q_cancels_the_windup_of_the_w_attack(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.W, ActionType.AA, ActionType.Q))

        [(aa_tick, _)] = hits(vs_vayne, ActionType.AA)
        [(q_tick, _)] = hits(vs_vayne, ActionType.Q)
        assert aa_tick == WINDUP_TICKS
        assert q_tick == Q_CAST_TICKS
        assert len(hits(vs_vayne, ActionType.W)) == 1


    def test_w_attack_windup_still_delays_e(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.W, ActionType.AA, ActionType.E))

        landing = WINDUP_TICKS + E_CAST_TICKS + E_AIRBORNE_TICKS
        assert vs_vayne.actors[Actor.RED].status_effects[StatusType.AIRBORNE] == [(landing, 0)]


    def test_w_empowers_next_attack_and_starts_cooldown_on_hit(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.AA, ActionType.W, ActionType.AA))

        [(w_tick, w_damage)] = hits(vs_vayne, ActionType.W)
        assert w_damage == pytest.approx(physical(W_RANK_1))
        assert vs_vayne.actors[Actor.BLUE].cooldowns[ActionType.W] == w_tick + W_COOLDOWN_TICKS
        assert vs_vayne.actors[Actor.RED].status_effects[StatusType.SLOW] == [(w_tick + TICKRATE, pytest.approx(0.9))]


    def test_e_passive_penetrates_armor(self, load_champion):
        without_e = Character(load_champion("darius"), 6, Rank(q=3, w=1, e=0, r=1), [])
        vayne = Character(load_champion("vayne"), 6, Rank(q=3, w=1, e=1, r=1), [])
        sim = Simulation(without_e, vayne)

        sim.do_combo(combo(ActionType.AA))

        assert hits(sim, ActionType.AA) == [(WINDUP_TICKS, pytest.approx(physical(DARIUS_AD, armor=VAYNE_ARMOR)))]


    def test_e_armor_pen_stacks_multiplicatively_with_items(self, load_champion):
        with open("src/tests/static/json/triforce.json", encoding="utf-8") as f:
            item = Item.parse_obj(json.load(f)).copy(update={"stats": {Stat.ARMOR_PEN_P: 0.3}})
        darius = Character(load_champion("darius"), 6, Rank(q=3, w=1, e=1, r=1), [item])

        _, percent_pen = darius.get_penetration(DamageSubType.PHYSIC)
        assert percent_pen == pytest.approx(1 - (1 - E_RANK_1_ARMOR_PEN) * (1 - 0.3))


    def test_e_knocks_up_then_slows(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.E))

        vayne = vs_vayne.actors[Actor.RED]
        landing = E_CAST_TICKS + E_AIRBORNE_TICKS
        assert vayne.status_effects[StatusType.AIRBORNE] == [(landing, 0)]
        assert vayne.status_effects[StatusType.SLOW] == [(landing + TICKRATE, pytest.approx(0.4))]
        assert vayne.damage_taken == 0


    def test_r_scales_with_bleed_stacks(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.AA, ActionType.AA, ActionType.R))

        [(_, r_damage)] = hits(vs_vayne, ActionType.R)
        assert r_damage == pytest.approx(R_RANK_1 * (1 + 2 * R_BONUS_PER_STACK))


    def test_r_cooldown_starts_on_cast(self, vs_vayne: Simulation):
        vs_vayne.do_combo(combo(ActionType.R))

        assert vs_vayne.actors[Actor.BLUE].cooldowns[ActionType.R] == R_RANK_1_COOLDOWN_TICKS
