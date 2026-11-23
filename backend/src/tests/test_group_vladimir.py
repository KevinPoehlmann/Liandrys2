import json

import pytest

from src.server.models.enums import (
    ActionType,
    Actor,
    DamageSubType,
    DamageType,
    EffectType,
    Stat,
    StatusType,
    to_ticks
)
from src.server.simulation.components import ProcessedDamageProperties
from src.server.models.item import Item
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character, soft_cap_movespeed
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation
from src.tests.helpers import regenerated_health


# Expected values are calculated by hand from the patch 15.12.1 fixtures (live wiki values), not by the simulation.
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
VLADIMIR_BASE_HP = 607 + 110 * GROWTH_LVL_6
VLADIMIR_MOVESPEED = 330
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6

THORNMAIL_HP = 150
AP_ITEM = 100
HP_TO_AP = 0.03333
AP_TO_HP = 1.6

CAST_TICKS = to_ticks(0.25)
E_TRAVEL_TICKS = to_ticks(DEFAULT_DISTANCE / 4000)  # 1 tick
Q_RANK_3_DAMAGE = 120
Q_RANK_3_HEAL = 30
Q_RANK_3_COOLDOWN_TICKS = to_ticks(6.8)
EMPOWERED_HEAL_LVL_6 = 30 + 10 * 5
SURGE_LVL_6 = 0.2
R_RANK_1 = 150
HEMOPLAGUE = 0.1


def magic(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_MR)


def item(**stats: float) -> Item:
    with open("src/tests/static/test_group/items/thornmail.json", encoding="utf-8") as f:
        data = json.load(f)
    return Item.parse_obj(data | {"stats": stats, "passives": [], "active": None})


def vladimir(load_champion, items: list[Item] | None = None, **scenario) -> Character:
    return Character(load_champion("vladimir"), 6, Rank(q=3, w=1, e=1, r=1), items or [], scenario=scenario)


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def results(sim: Simulation, source: ActionType, type_: EffectType) -> list[tuple[int, float]]:
    # Heals report the raw heal, so full health doesn't hide them.
    return [
        (event.tick, result.raw if type_ == EffectType.HEAL else result.value)
        for event in sim.effect_list
        for result in event.result
        if result.source == source and result.type_ == type_
    ]


class TestCrimsonPact():

    def test_bonus_health_gives_ability_power(self, load_champion):
        vlad = vladimir(load_champion, [item(hp=THORNMAIL_HP)])

        assert vlad.get_stat(Stat.AP) == pytest.approx(HP_TO_AP * THORNMAIL_HP)
        # The AP from the passive doesn't turn into health again.
        assert vlad.get_stat(Stat.HP) == pytest.approx(VLADIMIR_BASE_HP + THORNMAIL_HP)


    def test_ability_power_gives_bonus_health(self, load_champion):
        vlad = vladimir(load_champion, [item(ap=AP_ITEM)])

        assert vlad.get_stat(Stat.HP) == pytest.approx(VLADIMIR_BASE_HP + AP_TO_HP * AP_ITEM)
        # The health from the passive doesn't turn into AP again.
        assert vlad.get_stat(Stat.AP) == pytest.approx(AP_ITEM)


    def test_both_directions_only_from_item_stats(self, load_champion):
        vlad = vladimir(load_champion, [item(ap=AP_ITEM), item(hp=THORNMAIL_HP)])

        assert vlad.get_stat(Stat.AP) == pytest.approx(AP_ITEM + HP_TO_AP * THORNMAIL_HP)
        assert vlad.get_stat(Stat.HP) == pytest.approx(VLADIMIR_BASE_HP + THORNMAIL_HP + AP_TO_HP * AP_ITEM)
        assert vlad.current_hp == pytest.approx(vlad.get_stat(Stat.HP))


class TestTransfusion():

    def test_normal_cast_damages_and_heals(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion, crimson_rush_start=0), darius)

        sim.do_combo(combo(ActionType.Q))

        assert results(sim, ActionType.Q, EffectType.DAMAGE) == [(CAST_TICKS, pytest.approx(magic(Q_RANK_3_DAMAGE)))]
        assert results(sim, ActionType.Q, EffectType.HEAL) == [(CAST_TICKS, pytest.approx(Q_RANK_3_HEAL))]


    def test_full_bar_at_the_start_empowers_the_first_cast(self, load_champion, darius):
        vlad = vladimir(load_champion, crimson_rush_start=2)
        sim = Simulation(vlad, darius)

        sim.do_combo(combo(ActionType.Q))

        assert results(sim, ActionType.Q, EffectType.DAMAGE) == [(CAST_TICKS, pytest.approx(magic(1.85 * Q_RANK_3_DAMAGE)))]
        # Missing health is 0, so the missing-health part adds nothing.
        assert results(sim, ActionType.Q, EffectType.HEAL) == [(CAST_TICKS, pytest.approx(Q_RANK_3_HEAL + EMPOWERED_HEAL_LVL_6))]
        assert vlad.get_buff_stacks("crimson_rush_full") == 0


    def test_every_second_cast_on_cooldown_is_empowered(self, load_champion, darius):
        vlad = vladimir(load_champion)
        sim = Simulation(vlad, darius)

        sim.do_combo(combo(ActionType.Q, ActionType.Q, ActionType.Q))

        # Each stack comes when the cooldown ends, together with the next cast.
        second = CAST_TICKS + Q_RANK_3_COOLDOWN_TICKS + CAST_TICKS
        third = second + Q_RANK_3_COOLDOWN_TICKS + CAST_TICKS
        assert results(sim, ActionType.Q, EffectType.DAMAGE) == [
            (CAST_TICKS, pytest.approx(magic(Q_RANK_3_DAMAGE))),
            (second, pytest.approx(magic(Q_RANK_3_DAMAGE))),
            (third, pytest.approx(magic(1.85 * Q_RANK_3_DAMAGE))),
        ]
        # The empowered cast fills the bar again.
        assert vlad.get_buff_stacks("crimson_rush") == 1


    def test_full_bar_lasts_2_5_seconds(self, load_champion):
        vlad = vladimir(load_champion, crimson_rush_start=0)

        instance = vlad.apply_buff("crimson_rush", vlad, 2, 0)
        assert instance.stacks == 2  # the on_stack rule turns them into the full bar in the simulation

        assert vlad.apply_buff("crimson_rush_full", vlad, 1, 0).end == to_ticks(2.5)


    @pytest.mark.parametrize("elapsed", [0, 0.25, 0.5])
    def test_full_bar_gives_decaying_movement_speed(self, load_champion, elapsed):
        vlad = vladimir(load_champion, crimson_rush_start=0)
        vlad.apply_buff("crimson_rush_full", vlad, 1, 0)
        vlad.current_tick = to_ticks(elapsed)

        decay = max(0.0, 1 - to_ticks(elapsed) * 0.033 / 0.5)
        assert vlad.get_stat(Stat.MOVESPEED) == pytest.approx(soft_cap_movespeed(VLADIMIR_MOVESPEED * (1 + SURGE_LVL_6 * decay)))


class TestHemoplague():

    def test_burst_after_4_seconds_amplifies_itself(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion), darius)

        sim.do_combo(combo(ActionType.R))

        assert results(sim, ActionType.R, EffectType.DAMAGE) == [(to_ticks(4), pytest.approx(magic(R_RANK_1) * (1 + HEMOPLAGUE)))]
        assert results(sim, ActionType.R, EffectType.HEAL) == [(to_ticks(4.4), pytest.approx(R_RANK_1))]


    def test_amplifies_other_damage_while_infected(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion, crimson_rush_start=0), darius)

        sim.do_combo(combo(ActionType.R, ActionType.Q))

        assert results(sim, ActionType.Q, EffectType.DAMAGE) == [(CAST_TICKS, pytest.approx(magic(Q_RANK_3_DAMAGE) * (1 + HEMOPLAGUE)))]


    def test_true_damage_is_not_amplified(self, load_champion, darius):
        vlad = vladimir(load_champion)
        darius.apply_buff("hemoplague", vlad, 1, 0)

        def taken(sub_type: DamageSubType) -> float:
            props = ProcessedDamageProperties(value=100, flat_pen=0, percent_pen=0, dmg_type=DamageType.ABILITY, dmg_sub_type=sub_type)
            return darius._calculate_damage(props)[0]

        assert taken(DamageSubType.TRUE) == pytest.approx(100)
        assert taken(DamageSubType.MAGIC) == pytest.approx(magic(100) * (1 + HEMOPLAGUE))


W_RANK_1_TICK = 20
W_TICKS = [0, to_ticks(0.5), to_ticks(1), to_ticks(1.5)]
POOL_TICKS = to_ticks(2)
E_RANK_1_MIN = 30 + 0.015 * VLADIMIR_BASE_HP
E_RANK_1_MAX = 60 + 0.06 * VLADIMIR_BASE_HP
E_COST_STEP = 0.02 * VLADIMIR_BASE_HP


def red(action_type: ActionType) -> Action:
    return Action(actor=Actor.RED, target=Actor.BLUE, action_type=action_type)


def hits_on_vladimir(sim: Simulation, source: ActionType) -> list[int]:
    return [
        event.tick for event in sim.effect_list for result in event.result
        if result.target == Actor.BLUE and result.source == source and result.type_ == EffectType.DAMAGE
    ]


class TestSanguinePool():

    def test_costs_15_percent_of_current_health_and_heals_30_percent_of_the_damage(self, load_champion, darius):
        vlad = vladimir(load_champion)
        sim = Simulation(vlad, darius)

        sim.do_combo(combo(ActionType.W))

        assert results(sim, ActionType.W, EffectType.COST) == [(0, pytest.approx(0.15 * VLADIMIR_BASE_HP))]
        assert results(sim, ActionType.W, EffectType.DAMAGE) == [(tick, pytest.approx(magic(W_RANK_1_TICK))) for tick in W_TICKS]
        # 30 % of the damage before mitigation.
        assert results(sim, ActionType.W, EffectType.HEAL) == [(tick, pytest.approx(0.3 * W_RANK_1_TICK)) for tick in W_TICKS]
        assert vlad.current_hp - regenerated_health(sim, Actor.BLUE) == pytest.approx(0.85 * VLADIMIR_BASE_HP + 4 * 0.3 * W_RANK_1_TICK)


    def test_no_attacks_or_abilities_while_pooled(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion), darius)

        sim.do_combo(combo(ActionType.W, ActionType.Q))

        assert results(sim, ActionType.Q, EffectType.DAMAGE)[0][0] == POOL_TICKS + CAST_TICKS


    def test_enemy_hits_miss_while_pooled(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion), darius)

        sim.do_combo([*combo(ActionType.W), red(ActionType.BA), red(ActionType.BA), red(ActionType.BA)])

        attacks = hits_on_vladimir(sim, ActionType.BA)
        assert attacks and all(tick >= POOL_TICKS for tick in attacks)


    def test_running_debuffs_keep_ticking_while_pooled(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion), darius)

        # Darius' attack puts his bleed on Vladimir before the pool starts.
        sim.do_combo([red(ActionType.BA), *combo(ActionType.W)])

        [attack] = hits_on_vladimir(sim, ActionType.BA)
        bleed = hits_on_vladimir(sim, ActionType.PASSIVE)
        assert any(attack < tick < attack + POOL_TICKS for tick in bleed)


    def test_auras_miss_while_pooled(self, load_champion):
        annie = Character(load_champion("annie"), 6, Rank(q=1, w=1, e=1, r=1), [], scenario={"pyromania_start": 0})
        sim = Simulation(annie, vladimir(load_champion))

        # Tibbers comes at the end of Annie's R; Vladimir pools in the same tick.
        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.R),
                      Action(actor=Actor.RED, target=Actor.BLUE, action_type=ActionType.W)])

        pool_end = CAST_TICKS + POOL_TICKS
        tibbers = [
            (event.tick, result.source) for event in sim.effect_list for result in event.result
            if result.actor == "blue.tibbers" and result.type_ == EffectType.DAMAGE
        ]
        assert {source for _, source in tibbers} == {ActionType.BA, ActionType.PASSIVE}  # attacks and aura
        assert all(tick >= pool_end for tick, _ in tibbers)


class TestTidesOfBlood():

    def test_full_charge_deals_max_damage_and_slows(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion), darius)

        sim.do_combo(combo(ActionType.E))

        assert results(sim, ActionType.E, EffectType.DAMAGE) == [(to_ticks(1) + E_TRAVEL_TICKS, pytest.approx(magic(E_RANK_1_MAX)))]
        assert darius.status_effects[StatusType.SLOW] == [(to_ticks(1) + E_TRAVEL_TICKS + to_ticks(0.5), 0.4)]


    def test_health_cost_is_paid_while_charging(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion), darius)

        sim.do_combo(combo(ActionType.E))

        # 2 % right away and every 0.25 s, 8 % in total after 0.75 s.
        cost_ticks = [0, to_ticks(0.25), to_ticks(0.5), to_ticks(0.75)]
        assert results(sim, ActionType.E, EffectType.COST) == [(tick, pytest.approx(E_COST_STEP)) for tick in cost_ticks]


    @pytest.mark.parametrize("per_cast", [False, True])
    def test_half_charge(self, load_champion, darius, per_cast):
        # The charge is a per-cast parameter; the scenario value is the default for every cast.
        if per_cast:
            sim = Simulation(vladimir(load_champion), darius)
            sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.E, params={"tides_charge": 0.5})])
        else:
            sim = Simulation(vladimir(load_champion, tides_charge=0.5), darius)
            sim.do_combo(combo(ActionType.E))

        half = E_RANK_1_MIN + (E_RANK_1_MAX - E_RANK_1_MIN) * 0.5
        assert results(sim, ActionType.E, EffectType.DAMAGE) == [(to_ticks(0.5) + E_TRAVEL_TICKS, pytest.approx(magic(half)))]
        assert len(results(sim, ActionType.E, EffectType.COST)) == 3
        assert StatusType.SLOW not in darius.status_effects


    def test_no_health_cost_below_12_percent(self, load_champion, darius):
        vlad = vladimir(load_champion)
        vlad.current_hp = 0.1 * VLADIMIR_BASE_HP
        sim = Simulation(vlad, darius)

        sim.do_combo(combo(ActionType.E))

        assert vlad.current_hp - regenerated_health(sim, Actor.BLUE) == pytest.approx(0.1 * VLADIMIR_BASE_HP)


    def test_hemoplague_cast_at_the_release_amplifies_the_bolts(self, load_champion, darius):
        # The bolts fly at 4000 units/s, so they land after Hemoplague is on the target.
        sim = Simulation(vladimir(load_champion), darius, distance=400)

        sim.do_combo(combo(ActionType.E, ActionType.R))

        assert results(sim, ActionType.E, EffectType.DAMAGE) == [
            (to_ticks(1) + to_ticks(400 / 4000), pytest.approx(magic(E_RANK_1_MAX) * (1 + HEMOPLAGUE)))
        ]


class TestCosts():

    def test_crimson_rush_drains_slower_in_pool_and_channel(self, load_champion, darius):
        sim = Simulation(vladimir(load_champion, crimson_rush_start=2, tides_charge=1.5), darius)

        sim.do_combo(combo(ActionType.W, ActionType.E, ActionType.Q))

        # Without the slower drain the full bar ends after 2.5 s (83 ticks); Q only starts after pool and channel (107).
        # Full bar end: 83 -> 332 (pool starts) -> 129 (pool ends) -> 333 (channel starts) -> 164 (channel ends).
        q_start = POOL_TICKS + to_ticks(1.5)
        assert q_start > to_ticks(2.5)
        assert results(sim, ActionType.Q, EffectType.DAMAGE) == [(q_start + CAST_TICKS, pytest.approx(magic(1.85 * Q_RANK_3_DAMAGE)))]


    def test_not_enough_health_blocks_the_cast(self, load_champion, darius):
        champion = load_champion("vladimir")
        champion.w.cost = "2000"  # a fixed health cost like Dr. Mundo's Q
        sim = Simulation(Character(champion, 6, Rank(q=3, w=1, e=1, r=1), []), darius)

        with pytest.raises(SimulationError, match="health"):
            sim.do_combo(combo(ActionType.W))
