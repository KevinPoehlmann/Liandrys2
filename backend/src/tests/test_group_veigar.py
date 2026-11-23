import pytest

from src.server.models.enums import ActionType, Actor, EffectType, StatusType, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation, travel_time
from src.tests.helpers import regenerated_health


# Expected values are calculated by hand from the fixtures (live wiki values, R missile from CommunityDragon).
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6

CAST_TICKS = to_ticks(0.25)
Q_TRAVEL_TICKS = to_ticks(DEFAULT_DISTANCE / 2200)  # 2
W_DELAY_TICKS = to_ticks(1.221 - 0.25)  # 30, counted from the cast's end
E_DELAY_TICKS = to_ticks(0.5)
# s = 500 t + 4000 t² / 2 = 100  ->  t = (-500 + sqrt(500² + 2 * 4000 * 100)) / 4000 = 0.1312 s
R_TRAVEL_TICKS = to_ticks((-500 + (500 ** 2 + 2 * 4000 * DEFAULT_DISTANCE) ** 0.5) / 4000)  # 4


def magic(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_MR)


def veigar(load_champion, stacks: int = 0) -> Character:
    return Character(load_champion("veigar"), 6, Rank(q=3, w=1, e=1, r=1), [], scenario={"veigar_stacks": stacks})


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


class TestTravelTime():

    @pytest.mark.parametrize("speed, acceleration, max_speed, seconds", [
        (0, 0, 0, 0),
        (2200, 0, 0, 100 / 2200),
        (500, 4000, 4000, 0.131174),  # max speed not reached on 100 units
        # 500 -> 1000 units/s takes 0.125 s and 93.75 units; the other 6.25 units take 0.00625 s
        (500, 4000, 1000, 0.13125),
        (500, 4000, 0, 0.131174),  # 0 = no cap
    ])
    def test_travel_time(self, speed, acceleration, max_speed, seconds):
        assert travel_time(100, speed, acceleration, max_speed) == pytest.approx(seconds, abs=1e-6)


class TestPhenomenalEvil():

    def test_start_stacks_give_ap_without_cap(self, load_champion, darius):
        sim = Simulation(veigar(load_champion, stacks=500), darius)

        sim.do_combo(combo(ActionType.Q))

        assert hits(sim, ActionType.Q) == [(CAST_TICKS + Q_TRAVEL_TICKS, pytest.approx(magic(160 + 0.6 * 500)))]


    def test_every_ability_hit_gives_a_stack(self, load_champion, darius):
        caster = veigar(load_champion, stacks=100)
        sim = Simulation(caster, darius)

        sim.do_combo(combo(ActionType.Q, ActionType.W, ActionType.E, ActionType.R))

        assert caster.get_buff_stacks("phenomenal_evil") == 104


    def test_the_stack_counts_from_the_next_hit_on(self, load_champion, darius):
        sim = Simulation(veigar(load_champion, stacks=100), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.Q))

        # The cooldown starts after the cast time.
        second_hit = CAST_TICKS + to_ticks(5) + CAST_TICKS + Q_TRAVEL_TICKS
        assert hits(sim, ActionType.Q) == [
            (CAST_TICKS + Q_TRAVEL_TICKS, pytest.approx(magic(160 + 0.6 * 100))),
            (second_hit, pytest.approx(magic(160 + 0.6 * 101))),
        ]


class TestDarkMatter():

    def test_strikes_1_221_seconds_after_the_cast_starts(self, load_champion, darius):
        sim = Simulation(veigar(load_champion, stacks=100), darius)

        sim.do_combo(combo(ActionType.W))

        # 1.221 s would be 37 ticks; cast time and delay are rounded up to ticks separately, so 38.
        assert hits(sim, ActionType.W) == [(CAST_TICKS + W_DELAY_TICKS, pytest.approx(magic(85 + 0.7 * 100)))]


    def test_cooldown_starts_with_the_cast(self, load_champion, darius):
        sim = Simulation(veigar(load_champion), darius)

        sim.do_combo(combo(ActionType.W, ActionType.W))

        assert [tick for tick, _ in hits(sim, ActionType.W)] == [
            CAST_TICKS + W_DELAY_TICKS, to_ticks(8) + CAST_TICKS + W_DELAY_TICKS]


    @pytest.mark.parametrize("stacks, cooldown", [(0, 8), (49, 8), (50, 7.2), (99, 7.2), (100, 6.4), (500, 0)])
    def test_cooldown_drops_10_percent_every_50_stacks(self, load_champion, stacks, cooldown):
        caster = veigar(load_champion)
        caster.apply_buff("phenomenal_evil", caster, stacks, 0)

        assert caster.get_cooldown(ActionType.W) == pytest.approx(cooldown)


class TestEventHorizon():

    def test_cage_stuns_0_5_seconds_after_the_cast(self, load_champion, darius):
        sim = Simulation(veigar(load_champion), darius)

        sim.do_combo(combo(ActionType.E))

        stun_start = CAST_TICKS + E_DELAY_TICKS
        assert darius.status_effects[StatusType.STUN] == [(stun_start + to_ticks(1.5), 0)]


    def test_missed_cage_gives_no_stun_and_no_stack(self, load_champion, darius):
        caster = veigar(load_champion)
        sim = Simulation(caster, darius)

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.E, outcome="miss")])

        assert StatusType.STUN not in darius.status_effects
        assert caster.get_buff_stacks("phenomenal_evil") == 0


class TestPrimordialBurst():

    def test_accelerating_missile(self, load_champion, darius):
        sim = Simulation(veigar(load_champion), darius)

        sim.do_combo(combo(ActionType.R))

        assert [tick for tick, _ in hits(sim, ActionType.R)] == [CAST_TICKS + R_TRAVEL_TICKS]


    @pytest.mark.parametrize("missing", [0, 0.3, 0.8])
    def test_damage_grows_with_missing_health_up_to_double(self, load_champion, darius, missing):
        darius.current_hp = DARIUS_MAX_HP * (1 - missing)
        sim = Simulation(veigar(load_champion, stacks=100), darius)

        sim.do_combo(combo(ActionType.R))

        hit_tick = CAST_TICKS + R_TRAVEL_TICKS
        missing_percent = (DARIUS_MAX_HP * missing - regenerated_health(sim, Actor.RED, until=hit_tick)) / DARIUS_MAX_HP
        multiplier = 1 + min(1, 1.5 * missing_percent)
        assert hits(sim, ActionType.R) == [(hit_tick, pytest.approx(magic((175 + 0.65 * 100) * multiplier)))]
