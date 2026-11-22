import pytest

from src.server.models.dataenums import ActionType, Actor, EffectType, Origin, OriginKind, StatusType, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation
from src.tests.helpers import regenerated_health


# Expected values are calculated by hand from the fixtures (live wiki values, V25.14).
GROWTH_LVL_6 = 3.95
BOTRK_AD = 40
RIVEN_AD = 64 + 3 * GROWTH_LVL_6 + BOTRK_AD
RIVEN_ATTACKSPEED = 0.625 * (1 + 0.035 * GROWTH_LVL_6 + 0.25)
ATTACK_TICKS = to_ticks(1 / RIVEN_ATTACKSPEED)  # 35
FIRST_HIT = to_ticks(0.16667 / RIVEN_ATTACKSPEED)  # 6
VAYNE_AD = 60 + 2.35 * GROWTH_LVL_6 + BOTRK_AD
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6
THORNMAIL_ARMOR, THORNMAIL_HP = 75, 150
LIFE_STEAL = 0.1
GRIEVOUS_WOUNDS = 0.4

MISTS_EDGE = Origin(kind=OriginKind.ITEM, name="Blade of the Ruined King")
LIFE_STEAL_HEAL = Origin(kind=OriginKind.VAMP, name="life steal")


def physical(raw: float, armor: float = DARIUS_ARMOR) -> float:
    return raw * 100 / (100 + armor)


def blue(action_type: ActionType) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type)


def results(sim: Simulation, origin: Origin, type_: EffectType) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.origin == origin and result.type_ == type_
    ]


@pytest.fixture
def riven(load_champion, load_item) -> Character:
    return Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), [load_item("blade_of_the_ruined_king")])


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


class TestMistsEdge():

    def test_melee_deals_9_percent_of_current_health(self, riven, darius):
        sim = Simulation(riven, darius)

        sim.do_combo([blue(ActionType.BA)])

        assert results(sim, MISTS_EDGE, EffectType.DAMAGE) == [(FIRST_HIT, pytest.approx(physical(0.09 * DARIUS_MAX_HP)))]


    def test_reads_the_health_before_the_attacks_damage(self, riven, darius):
        sim = Simulation(riven, darius)

        sim.do_combo([blue(ActionType.BA), blue(ActionType.BA)])

        # The second hit sees the health after the first hit (attack and Mist's Edge), not after its own attack.
        second_hit = FIRST_HIT + ATTACK_TICKS
        health = (DARIUS_MAX_HP - physical(RIVEN_AD) - physical(0.09 * DARIUS_MAX_HP)
                  + regenerated_health(sim, Actor.RED, until=second_hit))
        assert results(sim, MISTS_EDGE, EffectType.DAMAGE)[1] == (second_hit, pytest.approx(physical(0.09 * health)))


    def test_ranged_deals_6_percent(self, load_champion, load_item, darius):
        vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=1, e=1, r=1), [load_item("blade_of_the_ruined_king")])
        sim = Simulation(vayne, darius)

        sim.do_combo([blue(ActionType.BA)])

        assert [value for _, value in results(sim, MISTS_EDGE, EffectType.DAMAGE)] == [pytest.approx(physical(0.06 * DARIUS_MAX_HP))]


class TestLifeSteal():

    def test_heals_from_the_attack_and_on_hit_damage(self, riven, darius):
        riven.current_hp = 100
        sim = Simulation(riven, darius)

        sim.do_combo([blue(ActionType.BA)])

        heal = LIFE_STEAL * (physical(RIVEN_AD) + physical(0.09 * DARIUS_MAX_HP))
        assert sum(value for _, value in results(sim, LIFE_STEAL_HEAL, EffectType.HEAL)) == pytest.approx(heal)


    def test_abilities_dont_heal(self, riven, darius):
        riven.current_hp = 100
        sim = Simulation(riven, darius)

        sim.do_combo([blue(ActionType.W)])

        assert results(sim, LIFE_STEAL_HEAL, EffectType.HEAL) == []


    def test_spellblade_is_on_hit_damage_too(self, riven, darius, load_item):
        riven.items.append(load_item("sheen"))
        riven_with_sheen = Character(riven.champion, 6, Rank(q=3, w=1, e=1, r=1), riven.items)
        riven_with_sheen.current_hp = 100
        sim = Simulation(riven_with_sheen, darius)

        sim.do_combo([blue(ActionType.Q), blue(ActionType.BA)])

        sheen = Origin(kind=OriginKind.ITEM, name="Sheen", buff="spellblade")
        [(hit, proc)] = results(sim, sheen, EffectType.DAMAGE)
        on_hit_damage = proc + sum(value for tick, value in results(sim, MISTS_EDGE, EffectType.DAMAGE) if tick == hit)
        attack = physical(RIVEN_AD)
        assert sum(value for tick, value in results(sim, LIFE_STEAL_HEAL, EffectType.HEAL) if tick == hit) == pytest.approx(
            LIFE_STEAL * (attack + on_hit_damage))


    def test_thornmails_grievous_wounds_already_reduce_the_first_attack(self, riven, load_champion, load_item):
        thorny_darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [load_item("thornmail")])
        riven.current_hp = 100
        sim = Simulation(riven, thorny_darius)

        sim.do_combo([blue(ActionType.BA)])

        armor = DARIUS_ARMOR + THORNMAIL_ARMOR
        damage = physical(RIVEN_AD, armor) + physical(0.09 * (DARIUS_MAX_HP + THORNMAIL_HP), armor)
        heal = (1 - GRIEVOUS_WOUNDS) * LIFE_STEAL * damage
        assert sum(value for _, value in results(sim, LIFE_STEAL_HEAL, EffectType.HEAL)) == pytest.approx(heal)


class TestClawingShadows():

    def test_third_hit_slows(self, riven, darius):
        sim = Simulation(riven, darius)

        sim.do_combo([blue(ActionType.BA)] * 3)

        third_hit = FIRST_HIT + 2 * ATTACK_TICKS
        assert darius.status_effects[StatusType.SLOW] == [(third_hit + to_ticks(1), 0.3)]


    def test_no_stacks_during_the_15_second_cooldown(self, riven, darius):
        sim = Simulation(riven, darius)

        # Six hits take about 6 s: the hits after the slow fall into the cooldown, so no second slow.
        sim.do_combo([blue(ActionType.BA)] * 6)

        assert len(darius.status_effects[StatusType.SLOW]) == 1
