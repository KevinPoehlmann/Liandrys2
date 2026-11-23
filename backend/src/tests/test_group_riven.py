import json

import pytest

from src.server.models.enums import ActionType, Actor, EffectType, Stat, StatusType, to_ticks
from src.server.models.item import Item
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation
from src.tests.helpers import regenerated_health


# Expected values are calculated by hand from the fixtures (live wiki values, Riven's cast times from CommunityDragon).
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
RIVEN_AD = 64 + 3 * GROWTH_LVL_6
RIVEN_ATTACKSPEED = 0.625 * (1 + 0.035 * GROWTH_LVL_6)
ATTACK_TICKS = to_ticks(1 / RIVEN_ATTACKSPEED)  # 43
WINDUP_TICKS = to_ticks(0.16667 / RIVEN_ATTACKSPEED)  # 8
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6

Q_CAST_TICKS = to_ticks(0.25)
Q_UNCANCELED_EXTRA = to_ticks(0.25)
Q_RANK_3 = 105
Q_COOLDOWN_TICKS = to_ticks(13)
PASSIVE_LVL_6 = (0.3 + 0.15 * 5 / 17) * RIVEN_AD
W_RANK_1 = 65
E_RANK_1_SHIELD = 70
R_BONUS_AD = 0.2 * RIVEN_AD
WIND_SLASH_RANK_1 = 100 + 0.55 * R_BONUS_AD


def physical(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_ARMOR)


def riven(load_champion, items: list[Item] | None = None, **scenario) -> Character:
    return Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), items or [], scenario=scenario)


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def hits(sim: Simulation, source: ActionType) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.source == source and result.type_ == EffectType.DAMAGE and result.target == Actor.RED
    ]


def ticks(sim: Simulation, source: ActionType) -> list[int]:
    return [tick for tick, _ in hits(sim, source)]


Q_BA_Q_BA_Q_BA = (ActionType.Q, ActionType.BA, ActionType.Q, ActionType.BA, ActionType.Q, ActionType.BA)


class TestBrokenWings():

    def test_three_casts_with_attacks_without_animation_cancel(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        sim.do_combo(combo(*Q_BA_Q_BA_Q_BA))

        # Each cast hits after 0.25 s and locks Riven 0.25 s longer; then she attacks at once (the cast reset the timer).
        assert hits(sim, ActionType.Q) == [(tick, pytest.approx(physical(Q_RANK_3))) for tick in (8, 32, 56)]
        assert ticks(sim, ActionType.BA) == [24, 48, 72]


    def test_animation_cancel_saves_the_lock_after_each_hit(self, load_champion, darius):
        sim = Simulation(riven(load_champion, riven_q_cancel=1), darius)

        sim.do_combo(combo(*Q_BA_Q_BA_Q_BA))

        assert ticks(sim, ActionType.Q) == [8, 24, 40]
        assert ticks(sim, ActionType.BA) == [16, 32, 48]


    def test_third_cast_knocks_up_for_half_a_second(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        sim.do_combo(combo(*Q_BA_Q_BA_Q_BA))

        assert darius.status_effects[StatusType.AIRBORNE] == [(56 + to_ticks(0.5), 0)]


    def test_cooldown_starts_with_the_first_cast(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.Q, ActionType.Q, ActionType.Q))

        # The recasts come as soon as the lock allows (16, 32); the fourth cast starts over after 13 s from tick 0.
        assert ticks(sim, ActionType.Q) == [8, 24, 40, Q_COOLDOWN_TICKS + Q_CAST_TICKS]


    def test_recast_window_runs_out_after_4_seconds(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        # Four attacks take longer than 4 s, so the next cast is a first cast again and waits for the cooldown.
        sim.do_combo(combo(ActionType.Q, ActionType.BA, ActionType.BA, ActionType.BA, ActionType.BA, ActionType.Q))

        assert ticks(sim, ActionType.Q) == [8, Q_COOLDOWN_TICKS + Q_CAST_TICKS]
        assert StatusType.AIRBORNE not in darius.status_effects


class TestRunicBlade():

    def test_each_cast_charges_the_next_attack(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        sim.do_combo(combo(*Q_BA_Q_BA_Q_BA))

        assert hits(sim, ActionType.PASSIVE) == [(tick, pytest.approx(physical(PASSIVE_LVL_6))) for tick in (24, 48, 72)]


    def test_at_most_three_charges(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        # Four casts, four attacks (starting at 32, then every 43 ticks): only the first three are charged.
        sim.do_combo(combo(ActionType.Q, ActionType.W, ActionType.E, ActionType.R,
                           ActionType.BA, ActionType.BA, ActionType.BA, ActionType.BA))

        first_hit = 32 + WINDUP_TICKS
        assert ticks(sim, ActionType.BA) == [first_hit + k * ATTACK_TICKS for k in range(4)]
        assert ticks(sim, ActionType.PASSIVE) == [first_hit + k * ATTACK_TICKS for k in range(3)]


class TestKiBurstAndValor():

    def test_ki_burst_hits_and_stuns_before_its_cast_time(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        sim.do_combo(combo(ActionType.W, ActionType.Q))

        assert hits(sim, ActionType.W) == [(0, pytest.approx(physical(W_RANK_1)))]
        assert darius.status_effects[StatusType.STUN] == [(to_ticks(0.75), 0)]
        assert ticks(sim, ActionType.Q) == [to_ticks(0.25) + Q_CAST_TICKS]  # Q waits for W's cast time


    def test_valor_shields(self, load_champion, darius):
        caster = riven(load_champion)
        sim = Simulation(caster, darius)

        sim.do_action(combo(ActionType.E)[0])
        sim._process_queue()

        assert [(shield.value, shield.expires) for shield in caster.shields] == [(E_RANK_1_SHIELD, to_ticks(1.5))]


class TestBladeOfTheExile():

    def test_bonus_ad_is_fixed_at_the_cast(self, load_champion):
        long_sword = Item.parse_obj(json.load(open("src/tests/static/test_group/items/thornmail.json", encoding="utf-8"))
                                    | {"stats": {"ad": 100}, "passives": [], "active": None})
        caster = riven(load_champion)
        caster.apply_buff("blade_of_the_exile", caster, 1, 0)
        assert caster.get_stat(Stat.AD) == pytest.approx(RIVEN_AD + R_BONUS_AD)

        caster.items.append(long_sword)

        assert caster.get_stat(Stat.AD) == pytest.approx(RIVEN_AD + 100 + R_BONUS_AD)


    def test_bonus_starts_0_5_seconds_after_the_cast(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)

        # W right after the cast time (tick 8) is before the bonus (tick 16); Q after W's cast time hits at tick 24.
        sim.do_combo(combo(ActionType.R, ActionType.W, ActionType.Q))

        assert hits(sim, ActionType.W) == [(8, pytest.approx(physical(W_RANK_1)))]
        assert hits(sim, ActionType.Q) == [(24, pytest.approx(physical(Q_RANK_3 + 0.7 * R_BONUS_AD)))]


    @pytest.mark.parametrize("missing", [0, 0.5, 0.8])
    def test_wind_slash_scales_with_missing_health_up_to_three_times(self, load_champion, darius, missing):
        darius.current_hp = DARIUS_MAX_HP * (1 - missing)
        sim = Simulation(riven(load_champion), darius)

        sim.do_combo(combo(ActionType.R, ActionType.R))

        # Wind Slash from 0.5 s after the first cast, 0.25 s cast time, then 2 ticks of travel at 1600 units/s.
        hit_tick = to_ticks(0.5) + to_ticks(0.25) + to_ticks(DEFAULT_DISTANCE / 1600)
        missing_percent = (DARIUS_MAX_HP * missing - regenerated_health(sim, Actor.RED, until=hit_tick)) / DARIUS_MAX_HP
        multiplier = 1 + min(2, 8 / 3 * missing_percent)
        assert hits(sim, ActionType.R) == [(hit_tick, pytest.approx(physical(WIND_SLASH_RANK_1 * multiplier)))]


class TestPerCastParameters():

    def test_cancel_only_the_first_cast(self, load_champion, darius):
        sim = Simulation(riven(load_champion), darius)
        canceled = Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q, params={"riven_q_cancel": 1})

        sim.do_combo([canceled] + combo(ActionType.BA, ActionType.Q, ActionType.BA))

        # Canceled: the attack follows the hit at once; the second cast keeps its 0.25 s lock.
        assert ticks(sim, ActionType.Q) == [8, 24]
        assert ticks(sim, ActionType.BA) == [16, 40]
