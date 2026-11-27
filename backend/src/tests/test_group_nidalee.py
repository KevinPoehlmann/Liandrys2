import pytest

from src.server.models.enums import ActionType, Actor, EffectType, OriginKind, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation
from src.tests.helpers import regenerated_health


# Expected values are calculated by hand from the fixture (live wiki values, V26.21).
GROWTH_LVL_6 = 3.95
NIDALEE_AD = 58 + 3.5 * GROWTH_LVL_6
ATTACK_TIME = 1 / (0.638 * (1 + 0.0322 * GROWTH_LVL_6))
ATTACK_TICKS = to_ticks(ATTACK_TIME)  # 43
WINDUP_TICKS = to_ticks(0.15 * ATTACK_TIME)  # 7; the same windup in both forms (owner: both attacks come out fast)
MISSILE_TICKS = to_ticks(DEFAULT_DISTANCE / 2500)  # 2, human form only
JAVELIN_CAST = to_ticks(0.25)
R_COOLDOWN = to_ticks(3)
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6


def physical(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_ARMOR)


def magic(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_MR)


def takedown(rank: int) -> float:
    return [5, 30, 55, 80][rank - 1] + 0.75 * NIDALEE_AD  # Darius at full health: no missing-health bonus


def blue(action_type: ActionType, crit: bool | None = None) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type, crit=crit)


def nidalee(load_champion, r: int = 2, items=()) -> Character:
    return Character(load_champion("nidalee"), 6, Rank(q=1, w=0, e=1, r=r), list(items))


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def hits(sim: Simulation, kind: OriginKind, name: str | None = None, buff: str | None = None) -> list[tuple[int, float]]:
    return [(event.tick, result.value) for event in sim.effect_list for result in event.result
            if result.type_ == EffectType.DAMAGE and result.actor == Actor.BLUE and result.origin.kind == kind
            and (name is None or result.origin.name == name) and (buff is None or result.origin.buff == buff)]


def attack_ticks(sim: Simulation) -> list[int]:
    return [tick for tick, _ in hits(sim, OriginKind.ATTACK)]


class TestAspectOfTheCougar():

    def test_cougar_attacks_are_melee(self, load_champion, darius):
        human = Simulation(nidalee(load_champion), darius)
        human.do_combo([blue(ActionType.BA)])
        cougar = Simulation(nidalee(load_champion), Character(darius.champion, 6, Rank(q=1, w=1, e=1, r=1), []))
        cougar.do_combo([blue(ActionType.R), blue(ActionType.BA)])

        assert attack_ticks(human) == [WINDUP_TICKS + MISSILE_TICKS]
        assert attack_ticks(cougar) == [WINDUP_TICKS]


    @pytest.mark.parametrize("rank", [1, 2])
    def test_q_becomes_takedown_ranked_by_r(self, load_champion, darius, rank):
        sim = Simulation(nidalee(load_champion, r=rank), darius)

        # Takedown resets the attack timer, so the attack starts at once.
        sim.do_combo([blue(ActionType.R), blue(ActionType.Q), blue(ActionType.BA)])

        assert hits(sim, OriginKind.ABILITY, buff="takedown") == [(WINDUP_TICKS, pytest.approx(magic(takedown(rank))))]
        assert hits(sim, OriginKind.ATTACK) == [(WINDUP_TICKS, pytest.approx(physical(NIDALEE_AD)))]


    def test_takedown_crits_with_the_attack(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.R), blue(ActionType.Q), blue(ActionType.BA, crit=True)])

        assert [value for _, value in hits(sim, OriginKind.ABILITY, buff="takedown")] == [pytest.approx(magic(2 * takedown(2)))]


    def test_each_form_has_its_own_cooldowns(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        # Javelin Toss is on cooldown, but Takedown is free right after turning into a cougar.
        sim.do_combo([blue(ActionType.Q), blue(ActionType.R), blue(ActionType.Q), blue(ActionType.BA)])

        assert [tick for tick, _ in hits(sim, OriginKind.ABILITY, buff="takedown")] == [JAVELIN_CAST + WINDUP_TICKS]


    def test_turning_isnt_an_ability_cast(self, load_champion, load_item, darius):
        sim = Simulation(nidalee(load_champion, items=[load_item("sheen")]), darius)

        sim.do_combo([blue(ActionType.R), blue(ActionType.BA)])

        assert hits(sim, OriginKind.ITEM, name="Sheen") == []


    def test_turning_doesnt_reset_the_attack_timer(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.BA), blue(ActionType.R), blue(ActionType.BA)])

        assert attack_ticks(sim) == [WINDUP_TICKS + MISSILE_TICKS, ATTACK_TICKS + WINDUP_TICKS]


    def test_turning_human_drops_takedown(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.R), blue(ActionType.Q), blue(ActionType.R), blue(ActionType.BA)])

        assert hits(sim, OriginKind.ABILITY, buff="takedown") == []
        assert attack_ticks(sim) == [R_COOLDOWN + WINDUP_TICKS + MISSILE_TICKS]


POUNCE_DASH = 10  # measured in the practice tool: the damage lands about 0.33 s after the cast
HUNTED_POUNCE_DASH = 14  # about 0.47 s at a Hunted target from range
POUNCE_LANDING_LOCK = 3  # the rest of the 13-frame animation (0.433 s)


class TestPounce():

    def test_damage_lands_after_the_dash(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.R), blue(ActionType.W)])

        assert [tick for tick, _ in hits(sim, OriginKind.ABILITY, name="W")] == [POUNCE_DASH]


    def test_attack_waits_for_the_landing_animation(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.R), blue(ActionType.W), blue(ActionType.BA)])

        assert attack_ticks(sim) == [POUNCE_DASH + POUNCE_LANDING_LOCK + WINDUP_TICKS]


DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6
JAVELIN_TRAVEL = to_ticks(DEFAULT_DISTANCE / 1300)  # 3
JAVELIN_HIT = JAVELIN_CAST + JAVELIN_TRAVEL  # 11: Darius is Hunted from here
R_AFTER_THE_HIT = 0.1  # seconds after Javelin Toss's cast time, so the form swap comes after the hit


class TestHunt():

    def test_takedown_deals_30_percent_more_against_a_hunted_target(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.R, delay=R_AFTER_THE_HIT),
                      blue(ActionType.Q), blue(ActionType.BA)])

        [(hit, value)] = hits(sim, OriginKind.ABILITY, buff="takedown")
        missing = (magic(70) - regenerated_health(sim, Actor.RED, until=hit)) / DARIUS_MAX_HP
        assert value == pytest.approx(magic(takedown(2) * (1 + 1.25 * missing) * 1.3))


    def test_pounce_cooldown_drops_against_a_hunted_target(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        sim.do_combo([blue(ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.R, delay=R_AFTER_THE_HIT),
                      blue(ActionType.W), blue(ActionType.W)])

        # The first Pounce (rank 2) uses the Hunt: 2.5 s instead of 6 s, and leaps further, so it lands later.
        first = JAVELIN_CAST + to_ticks(R_AFTER_THE_HIT)
        assert [tick for tick, _ in hits(sim, OriginKind.ABILITY, name="W")] == [
            first + HUNTED_POUNCE_DASH, first + to_ticks(2.5) + POUNCE_DASH]


    def test_a_hunt_in_human_form_resets_the_form_swap(self, load_champion, darius):
        caster = nidalee(load_champion)
        sim = Simulation(caster, darius)

        # Back to human at 3 s, Javelin Toss hits 11 ticks later and resets Aspect of the Cougar.
        sim.do_combo([blue(ActionType.R), blue(ActionType.R), blue(ActionType.Q), blue(ActionType.R)])

        third_swap = R_COOLDOWN + JAVELIN_HIT
        assert caster.cooldowns[ActionType.R] == third_swap + R_COOLDOWN
        assert "cougar" in caster.active_buffs


    # +45 % per full 155 units beyond 525, at most 225 % (from 1300 on).
    @pytest.mark.parametrize("distance, bonus", [(100, 0), (525, 0), (679, 0), (680, 0.45), (912.5, 0.9), (1300, 2.25), (1500, 2.25)])
    def test_javelin_grows_in_steps_with_the_distance(self, load_champion, darius, distance, bonus):
        sim = Simulation(nidalee(load_champion), darius, distance=distance)

        sim.do_combo([blue(ActionType.Q)])

        assert [value for _, value in hits(sim, OriginKind.ABILITY, name="Q")] == [pytest.approx(magic(70 * (1 + bonus)))]


    def test_bushwhack_hits_four_times_once_armed(self, load_champion, darius):
        trap = Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.W, outcome="hit")
        rank_1 = Character(load_champion("nidalee"), 6, Rank(q=1, w=1, e=1, r=2), [])
        sim = Simulation(rank_1, darius)

        sim.do_combo([trap])

        armed = JAVELIN_CAST + to_ticks(1.5)
        assert hits(sim, OriginKind.ABILITY, name="W") == [(armed + to_ticks(k), pytest.approx(magic(10))) for k in (1, 2, 3, 4)]


class TestTraps():

    @staticmethod
    def trap_hits(sim: Simulation) -> list[int]:
        return [tick for tick, _ in hits(sim, OriginKind.ABILITY, name="W")]


    def test_step_in_time_per_cast(self, load_champion, darius):
        sim = Simulation(Character(load_champion("nidalee"), 6, Rank(q=1, w=1, e=1, r=2), []), darius)
        trap = Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.W, outcome="hit", params={"bushwhack_step_in": 3})

        sim.do_combo([trap])

        stepped_in = JAVELIN_CAST + to_ticks(3)
        assert self.trap_hits(sim) == [stepped_in + to_ticks(k) for k in (1, 2, 3, 4)]


    def test_traps_placed_before_the_fight(self, load_champion, darius):
        caster = Character(load_champion("nidalee"), 6, Rank(q=1, w=1, e=1, r=2), [], scenario={"bushwhack_preplaced": [0.5, 5]})
        sim = Simulation(caster, darius)

        sim.do_combo([blue(ActionType.BA)])

        assert self.trap_hits(sim) == [to_ticks(step_in) + to_ticks(k) for step_in in (0.5, 5) for k in (1, 2, 3, 4)]


    def test_unknown_parameter_is_rejected(self, load_champion, darius):
        sim = Simulation(nidalee(load_champion), darius)

        with pytest.raises(Exception, match="Unknown parameters"):
            sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q, params={"bushwhack_step_in": 3})])
