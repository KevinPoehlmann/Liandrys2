import pytest

from src.server.models.dataenums import ActionType, Actor, EffectType, Origin, OriginKind, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the fixtures (live wiki values).
# Riven at level 6 without Q cancel: Q hits 8 ticks after its start and locks her 8 ticks longer,
# her attack takes 43 ticks with an 8-tick windup.
GROWTH_LVL_6 = 3.95
RIVEN_BASE_AD = 64 + 3 * GROWTH_LVL_6
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
ATTACK_TICKS = 43
WINDUP_TICKS = 8
SPELLBLADE_COOLDOWN_TICKS = to_ticks(1.5)  # 46
SPELLBLADE = Origin(kind=OriginKind.ITEM, name="Sheen", buff="spellblade")


def physical(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_ARMOR)


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def riven(load_champion, items) -> Character:
    return Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), items)


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def procs(sim: Simulation) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.origin == SPELLBLADE and result.type_ == EffectType.DAMAGE
    ]


class TestSpellblade():

    def test_next_attack_after_a_cast_deals_base_ad(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen")]), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.BA))

        assert procs(sim) == [(24, pytest.approx(physical(RIVEN_BASE_AD)))]


    def test_casts_during_the_cooldown_give_nothing(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen")]), darius)

        # The cooldown runs from the hit at 24 to 70; the second and third Q start at 24 and 48.
        sim.do_combo(combo(ActionType.Q, ActionType.BA, ActionType.Q, ActionType.BA, ActionType.Q, ActionType.BA))

        assert [tick for tick, _ in procs(sim)] == [24]


    def test_a_cast_after_the_cooldown_empowers_again(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen")]), darius)

        # Attacks hit at 24, 67, 110 and 153; W starts at 110 (after the third windup), after the cooldown ended at 70.
        sim.do_combo(combo(ActionType.Q, ActionType.BA, ActionType.BA, ActionType.BA, ActionType.W, ActionType.BA))

        assert [tick for tick, _ in procs(sim)] == [24, 153]


    def test_granted_at_the_start_of_the_cast_time(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen")]), darius)

        # R starts at 67, before the cooldown ends at 70, and its cast time ends at 75, after it: no empowerment.
        sim.do_combo(combo(ActionType.Q, ActionType.BA, ActionType.BA, ActionType.R, ActionType.BA))

        assert [tick for tick, _ in procs(sim)] == [24]
        assert 24 + SPELLBLADE_COOLDOWN_TICKS == 70


    def test_two_spellblade_items_give_it_once(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen"), load_item("sheen")]), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.BA))

        assert procs(sim) == [(24, pytest.approx(physical(RIVEN_BASE_AD)))]


    def test_no_empowerment_without_a_cast(self, load_champion, load_item, darius):
        sim = Simulation(riven(load_champion, [load_item("sheen")]), darius)

        sim.do_combo(combo(ActionType.BA, ActionType.BA))

        assert procs(sim) == []
