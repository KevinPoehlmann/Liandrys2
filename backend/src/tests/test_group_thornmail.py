import pytest

from src.server.models.dataenums import ActionType, Actor, EffectType, Origin, OriginKind, StatusType, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the fixtures (live wiki values).
# Thorns: 20 + 10 % bonus armor; Thornmail's 75 armor is the only bonus armor here, so 27.5 magic damage.
GROWTH_LVL_6 = 3.95
THORNS = 20 + 0.1 * 75
RIVEN_MR = 32 + 2.05 * GROWTH_LVL_6
RIVEN_HIT_TICK = 8  # Riven's attack windup at level 6
GRIEVOUS_WOUNDS_TICKS = to_ticks(3)
THORNMAIL = Origin(kind=OriginKind.ITEM, name="Thornmail")
TIBBERS = Actor("blue.tibbers")


def magic(raw: float, mr: float) -> float:
    return raw * 100 / (100 + mr)


def reflected(sim: Simulation) -> list[tuple[int, Actor, float]]:
    return [
        (event.tick, result.target, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.origin == THORNMAIL and result.type_ == EffectType.DAMAGE
    ]


@pytest.fixture
def thorny_darius(load_champion, load_item) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [load_item("thornmail")])


@pytest.fixture
def riven(load_champion) -> Character:
    return Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), [])


def blue(action_type: ActionType) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type)


class TestThorns():

    def test_basic_attack_is_reflected_at_once(self, riven, thorny_darius):
        sim = Simulation(riven, thorny_darius)

        sim.do_combo([blue(ActionType.BA)])

        assert reflected(sim) == [(RIVEN_HIT_TICK, Actor.BLUE, pytest.approx(magic(THORNS, RIVEN_MR)))]


    def test_attacker_gets_grievous_wounds(self, riven, thorny_darius):
        sim = Simulation(riven, thorny_darius)

        sim.do_combo([blue(ActionType.BA)])

        assert riven.status_effects[StatusType.GRIEVOUS_WOUNDS] == [(RIVEN_HIT_TICK + GRIEVOUS_WOUNDS_TICKS, 0.4)]


    def test_abilities_are_not_reflected(self, riven, thorny_darius):
        sim = Simulation(riven, thorny_darius)

        sim.do_combo([blue(ActionType.Q)])

        assert reflected(sim) == []
        assert StatusType.GRIEVOUS_WOUNDS not in riven.status_effects


    def test_fully_shielded_attack_is_reflected_too(self, load_champion, load_item, riven):
        # Riven's attack (75.85 AD into 113.8 armor = 35.5) stays below Molten Shield's 60.
        annie = Character(load_champion("annie"), 6, Rank(q=3, w=1, e=1, r=1), [load_item("thornmail")])
        sim = Simulation(annie, riven)

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.BLUE, action_type=ActionType.E),
                      Action(actor=Actor.RED, target=Actor.BLUE, action_type=ActionType.BA)])

        assert annie.damage_taken == 0
        assert annie.damage_shielded == pytest.approx((64 + 3 * GROWTH_LVL_6) * 100 / (100 + 23 + 4 * GROWTH_LVL_6 + 75))
        # Annie's R gives 10 % magic penetration from rank 1; it counts for Thorns like for any of her magic damage.
        assert [(target, value) for _, target, value in reflected(sim)] == [(Actor.RED, pytest.approx(magic(THORNS, 0.9 * RIVEN_MR)))]


    def test_pets_take_the_damage_but_no_grievous_wounds(self, load_champion, thorny_darius):
        annie = Character(load_champion("annie"), 6, Rank(q=3, w=1, e=1, r=1), [])
        sim = Simulation(annie, thorny_darius)

        sim.do_combo([blue(ActionType.R)])

        assert reflected(sim)
        assert {target for _, target, _ in reflected(sim)} == {TIBBERS}
        assert StatusType.GRIEVOUS_WOUNDS not in sim.actors[TIBBERS].status_effects
