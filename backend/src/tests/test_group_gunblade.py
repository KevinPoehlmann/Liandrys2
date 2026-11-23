import json

import pytest

from src.server.models.enums import ActionType, Actor, EffectType, OriginKind, StatusType, to_ticks
from src.server.models.result import Origin
from src.server.models.request import Action, Rank
from src.server.models.summonerspell import Summonerspell
from src.server.simulation.character import Character
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the fixtures (live wiki values, V26.01).
GROWTH_LVL_6 = 3.95
GUNBLADE_AD, GUNBLADE_AP, OMNIVAMP = 40, 80, 0.1
RIVEN_AD = 64 + 3 * GROWTH_LVL_6 + GUNBLADE_AD
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6
# 175 - 253 based on level, assumed linear from level 1 to 18.
LIGHTNING_BOLT_LVL_6 = 175 + 78 * 5 / 17 + 0.3 * GUNBLADE_AP
COOLDOWN_TICKS = to_ticks(60)

LIGHTNING_BOLT = Origin(kind=OriginKind.ITEM, name="Hextech Gunblade", buff="Lightning Bolt")
OMNIVAMP_HEAL = Origin(kind=OriginKind.VAMP, name="omnivamp")


def magic(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_MR)


def physical(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_ARMOR)


def blue(action_type: ActionType) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type)


def results(sim: Simulation, origin: Origin, type_: EffectType) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.origin == origin and result.type_ == type_
    ]


def riven(load_champion, items, summonerspells=None) -> Character:
    return Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), items, summonerspells=summonerspells)


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


class TestLightningBolt():

    def test_hits_and_slows_at_once(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("hextech_gunblade")]), darius)

        sim.do_combo([blue(ActionType.I1)])

        assert results(sim, LIGHTNING_BOLT, EffectType.DAMAGE) == [(0, pytest.approx(magic(LIGHTNING_BOLT_LVL_6)))]
        assert darius.status_effects[StatusType.SLOW] == [(to_ticks(1.5), 0.25)]


    def test_the_slot_follows_the_item_order(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen"), load_item("hextech_gunblade")]), darius)

        sim.do_combo([blue(ActionType.I2)])

        assert [tick for tick, _ in results(sim, LIGHTNING_BOLT, EffectType.DAMAGE)] == [0]


    def test_item_without_an_active_is_rejected(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen"), load_item("hextech_gunblade")]), darius)

        with pytest.raises(SimulationError, match="Sheen has no active"):
            sim.do_combo([blue(ActionType.I1)])


    def test_ability_haste_doesnt_shorten_the_cooldown(self, load_champion, load_item, darius):
        # Sheen gives 10 ability haste; item actives only know item haste.
        sim = Simulation(riven(load_champion, [load_item("sheen"), load_item("hextech_gunblade")]), darius)

        sim.do_combo([blue(ActionType.I2), blue(ActionType.I2)])

        assert [tick for tick, _ in results(sim, LIGHTNING_BOLT, EffectType.DAMAGE)] == [0, COOLDOWN_TICKS]


class TestOmnivamp():

    def test_heals_from_the_active(self, load_champion, load_item, darius):
        caster = riven(load_champion, [load_item("hextech_gunblade")])
        caster.current_hp = 100
        sim = Simulation(caster, darius)

        sim.do_combo([blue(ActionType.I1)])

        assert results(sim, OMNIVAMP_HEAL, EffectType.HEAL) == [(0, pytest.approx(OMNIVAMP * magic(LIGHTNING_BOLT_LVL_6)))]


    def test_heals_from_attacks_and_abilities(self, load_champion, load_item, darius):
        caster = riven(load_champion, [load_item("hextech_gunblade")])
        caster.current_hp = 100
        sim = Simulation(caster, darius)

        sim.do_combo([blue(ActionType.W), blue(ActionType.BA)])

        # Ki Burst rank 1: 65 + 100 % bonus AD; the cast charges Runic Blade, whose proc heals too.
        w_damage = physical(65 + GUNBLADE_AD)
        runic_blade = physical((0.3 + 0.15 * 5 / 17) * RIVEN_AD)
        assert [value for _, value in results(sim, OMNIVAMP_HEAL, EffectType.HEAL)] == [
            pytest.approx(OMNIVAMP * w_damage), pytest.approx(OMNIVAMP * physical(RIVEN_AD)), pytest.approx(OMNIVAMP * runic_blade)]


    def test_ignite_doesnt_heal(self, load_champion, load_item, darius):
        with open("src/tests/static/test_group/summonerspells/ignite.json", encoding="utf-8") as f:
            ignite = Summonerspell.parse_obj(json.load(f))
        caster = riven(load_champion, [load_item("hextech_gunblade")], summonerspells=[ignite])
        caster.current_hp = 100
        sim = Simulation(caster, darius)

        sim.do_combo([blue(ActionType.S1)])

        assert results(sim, OMNIVAMP_HEAL, EffectType.HEAL) == []
