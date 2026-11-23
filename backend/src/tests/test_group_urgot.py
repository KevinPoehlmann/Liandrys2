import json

import pytest

from src.server.models.dataenums import ActionType, Actor, EffectType, Origin, OriginKind, to_ticks
from src.server.models.request import Action, Rank
from src.server.models.rune import Rune
from src.server.simulation.character import Character
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation


# Expected values are calculated by hand from the fixture (live wiki values, V25.06).
GROWTH_LVL_6, GROWTH_LVL_9 = 3.95, 6.74
URGOT_AD_LVL_6 = 63 + 4 * GROWTH_LVL_6
URGOT_AD_LVL_9 = 63 + 4 * GROWTH_LVL_9
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6
# Interval ticks are counted from the start (start + to_ticks(k / 3)), so rounding doesn't add up: 0, 11, 21, 31, ...
def shot(k: int) -> int:
    return to_ticks(k / 3)
PURGE_TICKS = to_ticks(4)  # 122
MISSILE_TICKS = to_ticks(DEFAULT_DISTANCE / 2500)  # 2
# A shot is an attack: 15 % windup of the fixed 3.0 attack speed (0.05 s), then the 2500 missile.
SHOT_FLIGHT = to_ticks(0.15 / 3) + MISSILE_TICKS  # 4

PURGE = Origin(kind=OriginKind.ABILITY, name="W", buff="purge")


def physical(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_ARMOR)


def windup_ticks(growth: float) -> int:
    attack_time = 1 / (0.625 * (1 + 0.0375 * growth))
    return to_ticks(0.15 * attack_time)


def blue(action_type: ActionType, delay: float = 0) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type, delay=delay)


def hits(sim: Simulation, origin: Origin) -> list[tuple[int, float]]:
    return [(event.tick, result.value) for event in sim.effect_list for result in event.result
            if result.origin == origin and result.type_ == EffectType.DAMAGE]


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def urgot(load_champion, level=6, w=1, items=(), runes=()) -> Character:
    return Character(load_champion("urgot"), level, Rank(q=1, w=w, e=1, r=0), list(items), runes=list(runes))


class TestPurge():

    def test_13_shots_in_4_seconds_then_the_cooldown(self, load_champion, darius):
        caster = urgot(load_champion)
        sim = Simulation(caster, darius)

        sim.do_combo([blue(ActionType.W)])

        shot_damage = physical(12 + 0.2 * URGOT_AD_LVL_6)
        shot_starts = [shot(k) for k in range(13)]  # the 13th starts at 4 s, as the buff ends
        assert shot_starts[-1] == PURGE_TICKS
        expected_ticks = [start + SHOT_FLIGHT for start in shot_starts]
        assert hits(sim, PURGE) == [(tick, pytest.approx(shot_damage)) for tick in expected_ticks]
        assert caster.cooldowns[ActionType.W] == PURGE_TICKS + to_ticks(12)


    def test_attacks_wait_until_purge_is_over(self, load_champion, darius):
        sim = Simulation(urgot(load_champion), darius)

        sim.do_combo([blue(ActionType.W), blue(ActionType.BA)])

        assert [tick for tick, _ in hits(sim, Origin(kind=OriginKind.ATTACK, name="BA"))] == [
            PURGE_TICKS + windup_ticks(GROWTH_LVL_6) + MISSILE_TICKS]


    def test_rank_5_weave(self, load_champion, darius):
        # The known rank 5 pattern: attack, Purge for 3 shots, Purge off, attack, Purge for 3 shots, off.
        sim = Simulation(urgot(load_champion, level=9, w=5), darius)
        windup = windup_ticks(GROWTH_LVL_9)  # 6
        attack_ticks = to_ticks(1 / (0.625 * (1 + 0.0375 * GROWTH_LVL_9)))  # 39

        sim.do_combo([blue(ActionType.BA), blue(ActionType.W), blue(ActionType.W, delay=0.75),
                      blue(ActionType.BA), blue(ActionType.W), blue(ActionType.W, delay=0.75)])

        # Purge starts after each windup; the toggle off comes 0.75 s later, after the third shot started.
        first, second = windup, attack_ticks + windup
        shot_ticks = [start + shot(k) + SHOT_FLIGHT for start in (first, second) for k in range(3)]
        assert [tick for tick, _ in hits(sim, PURGE)] == shot_ticks
        assert [tick for tick, _ in hits(sim, Origin(kind=OriginKind.ATTACK, name="BA"))] == [
            windup + MISSILE_TICKS, attack_ticks + windup + MISSILE_TICKS]


class TestShotsAreAttacks():

    def test_on_hit_effects_at_50_percent(self, load_champion, load_item, darius):
        sim = Simulation(urgot(load_champion, items=[load_item("sheen")]), darius)

        # Casting Purge grants Spellblade; the first shot uses it at half strength.
        sim.do_combo([blue(ActionType.W)])

        sheen = Origin(kind=OriginKind.ITEM, name="Sheen", buff="spellblade")
        assert hits(sim, sheen) == [(SHOT_FLIGHT, pytest.approx(physical(0.5 * URGOT_AD_LVL_6)))]


    def test_every_shot_is_its_own_cast_for_electrocute(self, load_champion, darius):
        with open("src/tests/static/test_group/runes/electrocute.json", encoding="utf-8") as f:
            electrocute = Rune.parse_obj(json.load(f))
        sim = Simulation(urgot(load_champion, runes=[electrocute]), darius)

        sim.do_combo([blue(ActionType.W)])

        strikes = [event.tick for event in sim.effect_list for result in event.result
                   if result.origin.name == "Electrocute" and result.type_ == EffectType.DAMAGE]
        assert strikes == [shot(2) + SHOT_FLIGHT + to_ticks(0.25)]
