import pytest

from src.server.models.enums import (
    ActionType,
    Actor,
    EffectType,
    Stat,
    StatusType,
    TICK_SECONDS,
    to_ticks
)
from src.server.simulation.components import ProcessedShieldProperties, QueueComponent
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character, soft_cap_movespeed
from src.server.simulation.pet import PetCharacter
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation
from src.tests.helpers import regenerated_health


# Expected values are calculated by hand from the patch 16.23.1 fixtures, not by the simulation.
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
ANNIE_MAX_HP = 560 + 96 * GROWTH_LVL_6
ANNIE_ARMOR = 23 + 4 * GROWTH_LVL_6
ANNIE_MOVESPEED = 335
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6
VAYNE_AD = 60 + 2.35 * GROWTH_LVL_6
VAYNE_MR = 33 + 1.1 * GROWTH_LVL_6

R_RANK_1_MAGIC_PEN = 0.1
Q_RANK_3 = 170
CAST_TICKS = to_ticks(0.25)
Q_TRAVEL_TICKS = to_ticks(DEFAULT_DISTANCE / 1400)  # 3 ticks
STUN_LVL_6 = 1.5
E_RANK_1_SHIELD = 60
E_RANK_1_REFLECT = 25
MOLTEN_SPEED_LVL_6 = 0.2 + 0.3 * 5 / 17


def magic(raw: float, mr: float = DARIUS_MR * (1 - R_RANK_1_MAGIC_PEN)) -> float:
    return raw * 100 / (100 + mr)


def physical(raw: float, armor: float) -> float:
    return raw * 100 / (100 + armor)


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def hits(sim: Simulation, source: ActionType, target: Actor = Actor.RED) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.source == source and result.target == target and result.type_ == EffectType.DAMAGE
    ]


def annie(load_champion, level: int = 6, rank: Rank = Rank(q=3, w=1, e=1, r=1), **scenario) -> Character:
    return Character(load_champion("annie"), level, rank, [], scenario=scenario)


@pytest.fixture
def vs_darius(load_champion) -> Simulation:
    darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
    return Simulation(annie(load_champion), darius)


class TestPyromania():

    def test_full_stacks_by_default_stun_with_the_first_ability(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.Q))

        darius = vs_darius.actors[Actor.RED]
        assert darius.status_effects[StatusType.STUN] == [(CAST_TICKS + Q_TRAVEL_TICKS + to_ticks(STUN_LVL_6), 0)]
        assert darius.damage_taken == pytest.approx(magic(Q_RANK_3))
        annie = vs_darius.actors[Actor.BLUE]
        assert annie.get_buff_stacks("pyromania") == 0
        assert annie.get_buff_stacks("pyromania_energized") == 0


    @pytest.mark.parametrize("level, stun_seconds", [(1, 1.25), (5, 1.25), (6, 1.5), (11, 1.75), (18, 1.75)])
    def test_stun_duration_by_level(self, load_champion, level, stun_seconds):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie(load_champion, level, Rank(q=1, w=0, e=0, r=0)), darius)

        sim.do_combo(combo(ActionType.Q))

        assert darius.status_effects[StatusType.STUN] == [(CAST_TICKS + Q_TRAVEL_TICKS + to_ticks(stun_seconds), 0)]


    def test_fourth_stack_does_not_stun_the_next_ability_does(self, load_champion):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie(load_champion, pyromania_start=3), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.W))

        [(w_tick, _)] = hits(sim, ActionType.W)
        assert w_tick == 2 * CAST_TICKS
        assert darius.status_effects[StatusType.STUN] == [(w_tick + to_ticks(STUN_LVL_6), 0)]


    def test_four_casts_build_up_to_the_stun(self, load_champion):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie(load_champion, pyromania_start=0), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.W, ActionType.E, ActionType.R, ActionType.W))

        _, (second_w_tick, _) = hits(sim, ActionType.W)
        assert darius.status_effects[StatusType.STUN] == [(second_w_tick + to_ticks(STUN_LVL_6), 0)]


    def test_r_passive_magic_pen_only_while_r_is_learned(self, load_champion):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie(load_champion, rank=Rank(q=3, w=1, e=1, r=0)), darius)

        sim.do_combo(combo(ActionType.Q))

        assert darius.damage_taken == pytest.approx(magic(Q_RANK_3, mr=DARIUS_MR))


class TestMoltenShield():

    @pytest.fixture
    def attacked_by_vayne(self, load_champion) -> Simulation:
        vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=0, e=0, r=0), [])
        sim = Simulation(annie(load_champion), vayne)
        e = Action(actor=Actor.BLUE, target=Actor.BLUE, action_type=ActionType.E)
        aa = Action(actor=Actor.RED, target=Actor.BLUE, action_type=ActionType.BA)
        sim.do_combo([e, aa, aa])
        return sim


    def test_shield_absorbs_damage_after_armor(self, attacked_by_vayne: Simulation):
        annie = attacked_by_vayne.actors[Actor.BLUE]
        two_hits = 2 * physical(VAYNE_AD, ANNIE_ARMOR)

        assert annie.damage_shielded == pytest.approx(E_RANK_1_SHIELD)
        assert annie.current_hp - regenerated_health(attacked_by_vayne, Actor.BLUE) == pytest.approx(ANNIE_MAX_HP - (two_hits - E_RANK_1_SHIELD))


    def test_reflect_once_per_cast_on_the_first_hit(self, attacked_by_vayne: Simulation):
        [(first_hit, _), _] = hits(attacked_by_vayne, ActionType.BA, target=Actor.BLUE)

        assert hits(attacked_by_vayne, ActionType.E) == [(first_hit, pytest.approx(magic(E_RANK_1_REFLECT, mr=VAYNE_MR * 0.9)))]


    def test_shield_that_expires_first_absorbs_first(self, load_champion):
        character = annie(load_champion)
        long, short = (
            QueueComponent(source=source, actor=Actor.BLUE, target=Actor.BLUE, type_=EffectType.SHIELD,
                           props=ProcessedShieldProperties(value=50, duration=duration))
            for source, duration in ((ActionType.E, 100), (ActionType.W, 50))
        )
        character._apply_shields([long, short], 0)

        remaining, results = character._use_shields(60, Actor.BLUE)

        assert remaining == 0
        assert [(result.source, result.value) for result in results] == [(ActionType.W, 50), (ActionType.E, 10)]


    @pytest.mark.parametrize("elapsed_ticks", [0, to_ticks(0.75), to_ticks(1.5)])
    def test_bonus_movement_speed_decays_over_1_5_seconds(self, load_champion, elapsed_ticks):
        character = annie(load_champion)
        character.apply_buff("molten_shield_speed", character, 1, 0)
        character.current_tick = elapsed_ticks

        decay = max(0.0, 1 - elapsed_ticks * TICK_SECONDS / 1.5)
        assert character.get_stat(Stat.MOVESPEED) == pytest.approx(soft_cap_movespeed(ANNIE_MOVESPEED * (1 + MOLTEN_SPEED_LVL_6 * decay)))


TIBBERS = Actor("blue.tibbers")
SUMMON_TICK = CAST_TICKS
TIBBERS_WINDUP = 0.4  # CommunityDragon (annietibbers): 30 % shifted by +0.1
R_RANK_1_TIBBERS_ATTACK = 30
R_RANK_1_AURA = 2.5
ENRAGE_TICKS = to_ticks(3.036)


def attack_ticks(attackspeed: float) -> tuple[int, int]:
    """(attack time, windup) in ticks."""
    return to_ticks(1 / attackspeed), to_ticks(TIBBERS_WINDUP / attackspeed)


def tibbers_hits(sim: Simulation, source: ActionType) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.actor == TIBBERS and result.source == source and result.type_ == EffectType.DAMAGE
    ]


class TestTibbers():

    @pytest.mark.parametrize("level, hp, resistance", [(6, 1275, 30), (11, 1850, 55), (18, 4000, 90)])
    def test_stats_by_level(self, load_champion, level, hp, resistance):
        owner = annie(load_champion, level)
        definition, slot = owner.pet_definitions["tibbers"]
        tibbers = PetCharacter(definition, owner, slot)

        assert tibbers.get_stat(Stat.HP) == pytest.approx(hp)
        assert tibbers.get_stat(Stat.ARMOR) == pytest.approx(resistance)
        assert tibbers.get_stat(Stat.MR) == pytest.approx(resistance)
        assert tibbers.get_stat(Stat.MOVESPEED) == pytest.approx(350)


    def test_enraged_attacks_get_slower_with_each_attack(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.R))

        start, expected_hits = SUMMON_TICK, []
        # The four fast attacks take 92 ticks; the enrage ends on the tick the fifth starts, which still gets it.
        for attackspeed in (1.736, 1.536, 1.307, 1.043, 0.739, 0.625):
            attack_time, windup = attack_ticks(attackspeed)
            expected_hits.append(start + windup)
            start += attack_time
        assert ENRAGE_TICKS == sum(attack_ticks(attackspeed)[0] for attackspeed in (1.736, 1.536, 1.307, 1.043)) == 92
        assert [tick for tick, _ in tibbers_hits(vs_darius, ActionType.BA)][:6] == expected_hits


    def test_attacks_use_annies_magic_pen(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.R))

        _, first_hit = tibbers_hits(vs_darius, ActionType.BA)[0]
        assert first_hit == pytest.approx(magic(R_RANK_1_TIBBERS_ATTACK))


    def test_aura_burns_every_quarter_second_for_45_seconds(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.R))

        aura = tibbers_hits(vs_darius, ActionType.PASSIVE)
        assert len(aura) == 180
        assert aura[0] == (SUMMON_TICK + to_ticks(0.25), pytest.approx(magic(R_RANK_1_AURA)))
        assert aura[-1][0] == SUMMON_TICK + to_ticks(45)


    def test_tibbers_is_gone_after_45_seconds(self, vs_darius: Simulation):
        vs_darius.do_combo(combo(ActionType.R))

        last_attack, _ = tibbers_hits(vs_darius, ActionType.BA)[-1]
        assert last_attack <= SUMMON_TICK + to_ticks(45)
        assert vs_darius.actors[TIBBERS].expired


    def test_pyromania_stun_enrages_tibbers_again(self, load_champion):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie(load_champion, pyromania_start=3), darius)

        # R brings the 4th stack and summons Tibbers, Q stuns when it lands at tick 16.
        sim.do_combo(combo(ActionType.R, ActionType.Q))

        first_time, first_windup = attack_ticks(1.736)
        second_start = SUMMON_TICK + first_time
        assert second_start > 2 * CAST_TICKS
        # Without the stun the second attack would use 1.536.
        second_time, second_windup = attack_ticks(1.736)
        _, third_windup = attack_ticks(1.536)
        hits = [tick for tick, _ in tibbers_hits(sim, ActionType.BA)][:3]
        assert hits == [SUMMON_TICK + first_windup, second_start + second_windup, second_start + second_time + third_windup]


    def test_molten_shield_also_shields_tibbers(self, vs_darius: Simulation):
        r, e = combo(ActionType.R, ActionType.E)
        vs_darius.do_action(r)
        vs_darius.do_action(e)
        vs_darius._process_queue()  # only up to the E, the shield lasts 3 of Tibbers' 45 seconds

        assert [shield.value for shield in vs_darius.actors[TIBBERS].shields] == [E_RANK_1_SHIELD]
