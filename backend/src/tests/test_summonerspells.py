import json
import math

import pytest

from src.server.models.dataenums import ActionType, Actor, CostResource, EffectType, Stat, StatusType, to_ticks
from src.server.models.item import Item
from src.server.models.request import Action, Rank
from src.server.models.summonerspell import Summonerspell
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the live wiki (Ignite) and the fixtures.
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
IGNITE_TICKS = [to_ticks(k * 1.056) for k in range(5)]  # 0, 32, 64, 96, 128
GRIEVOUS_WOUNDS = 0.4
GRIEVOUS_END = to_ticks(5)
VLADIMIR_HP_PER_REGEN = (7 + 0.6 * GROWTH_LVL_6) / 10
VLADIMIR_Q_RANK_3_HEAL = 30
CAST_TICKS = to_ticks(0.25)


@pytest.fixture
def ignite() -> Summonerspell:
    with open("src/tests/static/test_group/summonerspells/ignite.json", encoding="utf-8") as f:
        return Summonerspell.parse_obj(json.load(f))


def vayne(load_champion, ignite: Summonerspell, level: int = 6) -> Character:
    return Character(load_champion("vayne"), level, Rank(q=1, w=1, e=1, r=1), [], summonerspells=[ignite])


def results(sim: Simulation, type_: EffectType, target: Actor = Actor.RED) -> list:
    return [(event.tick, result) for event in sim.effect_list for result in event.result
            if result.type_ == type_ and result.target == target]


class TestIgnite():

    def test_five_ticks_every_1_056_seconds_the_first_right_away(self, load_champion, ignite):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(vayne(load_champion, ignite), darius)

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.S1)])

        # 175 true damage at level 6, a fifth per tick; nothing at the end of the 5 s.
        assert [(tick, pytest.approx(result.value)) for tick, result in results(sim, EffectType.DAMAGE)] == [
            (tick, pytest.approx(35)) for tick in IGNITE_TICKS
        ]


    @pytest.mark.parametrize("level, per_tick", [(1, 14), (5, 30), (6, 35), (18, 95), (20, 105)])
    def test_damage_by_level(self, load_champion, ignite, level, per_tick):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(vayne(load_champion, ignite, level), darius)

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.S1)])

        assert results(sim, EffectType.DAMAGE)[0][1].value == pytest.approx(per_tick)


    def test_cooldown(self, load_champion, ignite):
        assert vayne(load_champion, ignite).get_cooldown(ActionType.S1) == pytest.approx(180)


class TestGrievousWounds():

    @pytest.fixture
    def ignited_vladimir(self, load_champion, ignite) -> Simulation:
        vladimir = Character(load_champion("vladimir"), 6, Rank(q=3, w=1, e=1, r=1), [])
        sim = Simulation(vayne(load_champion, ignite), vladimir)
        # Ignite's first tick leaves Vladimir 35 below full health before his Q heals at tick 8.
        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.S1),
                      Action(actor=Actor.RED, target=Actor.BLUE, action_type=ActionType.Q)])
        return sim


    def test_reduces_heals_by_40_percent(self, ignited_vladimir: Simulation):
        [(tick, heal)] = results(ignited_vladimir, EffectType.HEAL)

        assert tick == CAST_TICKS
        assert heal.raw == pytest.approx(VLADIMIR_Q_RANK_3_HEAL)
        assert heal.value == pytest.approx(VLADIMIR_Q_RANK_3_HEAL * (1 - GRIEVOUS_WOUNDS))


    def test_reduces_health_regeneration_while_it_lasts(self, ignited_vladimir: Simulation):
        regen = [(tick, result.value) for tick, result in results(ignited_vladimir, EffectType.REGEN)
                 if result.resource == CostResource.HEALTH]

        reduced = [value for tick, value in regen if tick < GRIEVOUS_END]
        full = [value for tick, value in regen if tick >= GRIEVOUS_END]
        assert reduced and all(value == pytest.approx(VLADIMIR_HP_PER_REGEN * (1 - GRIEVOUS_WOUNDS)) for value in reduced)
        assert full and all(value == pytest.approx(VLADIMIR_HP_PER_REGEN) for value in full)


STUN_LVL_6_END = to_ticks(0.25) + to_ticks(100 / 1400) + to_ticks(1.5)  # Annie's Q: cast, travel, 1.5 s stun


@pytest.fixture
def cleanse() -> Summonerspell:
    with open("src/tests/static/test_group/summonerspells/cleanse.json", encoding="utf-8") as f:
        return Summonerspell.parse_obj(json.load(f))


def red(action_type: ActionType) -> Action:
    return Action(actor=Actor.RED, target=Actor.BLUE, action_type=action_type)


def blue(action_type: ActionType) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type)


class TestCleanse():

    def test_usable_while_stunned_and_removes_the_stun(self, load_champion, cleanse):
        annie = Character(load_champion("annie"), 6, Rank(q=1, w=1, e=1, r=1), [])
        cleansing_vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=1, e=1, r=1), [], summonerspells=[cleanse])
        sim = Simulation(annie, cleansing_vayne)

        # Annie's Q stuns Vayne at tick 11; Vayne cleanses at tick 16, during the stun, and attacks right away.
        sim.do_combo([blue(ActionType.Q), blue(ActionType.W), red(ActionType.S1), red(ActionType.AA)])

        [(attack, _)] = [(tick, result) for tick, result in results(sim, EffectType.DAMAGE, target=Actor.BLUE)]
        assert attack < STUN_LVL_6_END
        assert sim.last_action_tick == 2 * CAST_TICKS


    def test_removes_ignites_damage_but_not_its_grievous_wounds(self, load_champion, ignite, cleanse):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [], summonerspells=[cleanse])
        sim = Simulation(vayne(load_champion, ignite), darius)

        sim.do_combo([blue(ActionType.S1), red(ActionType.S1)])

        assert [tick for tick, _ in results(sim, EffectType.DAMAGE)] == [0]  # only the first tick
        assert darius.status_effects[StatusType.GRIEVOUS_WOUNDS] == [(GRIEVOUS_END, GRIEVOUS_WOUNDS)]


    def test_airborne_stays(self, load_champion, ignite, cleanse):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [], summonerspells=[cleanse])
        darius.status_effects[StatusType.AIRBORNE] = [(100, 0)]
        darius.status_effects[StatusType.SLOW] = [(100, 0.3)]
        sim = Simulation(vayne(load_champion, ignite), darius)

        sim.do_combo([red(ActionType.S1)])

        assert sim.last_action_tick == 0  # airborne doesn't block Cleanse
        assert StatusType.AIRBORNE in darius.status_effects
        assert StatusType.SLOW not in darius.status_effects


    def test_suppression_blocks_it(self, load_champion, ignite, cleanse):
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [], summonerspells=[cleanse])
        darius.status_effects[StatusType.SUPPRESSION] = [(50, 0)]
        sim = Simulation(vayne(load_champion, ignite), darius)

        sim.do_combo([red(ActionType.S1)])

        assert sim.last_action_tick == 50


    def test_75_percent_tenacity_for_3_seconds_stacking_multiplicatively(self, load_champion, cleanse):
        mercurys = Item.parse_obj(json.load(open("src/tests/static/test_group/items/thornmail.json", encoding="utf-8"))
                                  | {"stats": {"tenacity percent": 0.3}, "passives": [], "active": None})
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [mercurys], summonerspells=[cleanse])

        instance = darius.apply_buff("cleanse_tenacity", darius, 1, 0)

        assert instance.end == to_ticks(3)
        assert darius.get_stat(Stat.TENACITY_P) == pytest.approx(1 - (1 - 0.75) * (1 - 0.3))
        assert darius._apply_tenacity(to_ticks(2)) == math.ceil(0.25 * 0.7 * to_ticks(2))
