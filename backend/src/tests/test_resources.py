import pytest

from src.server.models.champion import Champion
from src.server.models.enums import ActionType, Actor, CostResource, EffectType, ResourceType, to_ticks
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the fixtures (Annie's costs and mana from the live wiki).
# Stat growth at level 6: (6 - 1) * (0.7025 + 0.0175 * (6 - 1)) = 3.95
GROWTH_LVL_6 = 3.95
ANNIE_MAX_MANA = 418 + 25 * GROWTH_LVL_6
ANNIE_MANA_PER_REGEN = (1.6 + 0.16 * GROWTH_LVL_6) * 0.5
DARIUS_HP_PER_REGEN = (2 + 0.19 * GROWTH_LVL_6) * 0.5
REGEN_TICKS = to_ticks(0.5)  # 16 ticks = 0.528 s, the engine's regeneration interval

Q_RANK_3_COST = 70
W_RANK_1_COST = 70
E_RANK_1_COST = 60
CAST_TICKS = to_ticks(0.25)


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def results(sim: Simulation, type_: EffectType, resource: CostResource, target: Actor = Actor.BLUE) -> list[tuple[int, float]]:
    return [
        (event.tick, pytest.approx(result.value))
        for event in sim.effect_list
        for result in event.result
        if result.type_ == type_ and result.resource == resource and result.target == target
    ]


def annie(champion: Champion) -> Character:
    return Character(champion, 6, Rank(q=3, w=1, e=1, r=1), [])


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def energy_champion(load_champion) -> Champion:
    # Annie with an energy bar like Zed or Lee Sin: 200 energy (only the example; the maximum comes from the champion data,
    # Shen has 400), 10 per second, no growth.
    champion = load_champion("annie")
    champion.resource_type = ResourceType.ENERGY
    champion.mana, champion.mana_per_lvl, champion.mana_regen, champion.mana_regen_per_lvl = 200, 0, 10, 0
    for ability in (champion.q, champion.w):
        ability.cost, ability.cost_resource = "50", CostResource.ENERGY
    return champion


class TestMana():

    def test_starts_full(self, load_champion):
        assert annie(load_champion("annie")).current_resource == pytest.approx(ANNIE_MAX_MANA)


    def test_casts_cost_mana_when_the_cast_ends(self, load_champion, darius):
        sim = Simulation(annie(load_champion("annie")), darius)

        sim.do_combo(combo(ActionType.Q, ActionType.W, ActionType.E))

        # Checked when the cast starts, paid when it ends, so an interrupted cast costs nothing. E has no cast time.
        assert results(sim, EffectType.COST, CostResource.MANA) == [
            (CAST_TICKS, Q_RANK_3_COST), (2 * CAST_TICKS, W_RANK_1_COST), (2 * CAST_TICKS, E_RANK_1_COST)
        ]


    def test_regenerates_half_the_mana_per_second_every_half_second(self, load_champion, darius):
        caster = annie(load_champion("annie"))
        sim = Simulation(caster, darius)

        # The simulation runs until Molten Shield ends (3 s after the E at tick 16), regenerating every 16 ticks.
        sim.do_combo(combo(ActionType.Q, ActionType.W, ActionType.E))

        regen = results(sim, EffectType.REGEN, CostResource.MANA)
        last_tick = 2 * CAST_TICKS + to_ticks(3)
        assert regen == [(k * REGEN_TICKS, ANNIE_MANA_PER_REGEN) for k in range(1, last_tick // REGEN_TICKS + 1)]
        spent = Q_RANK_3_COST + W_RANK_1_COST + E_RANK_1_COST
        assert caster.current_resource == pytest.approx(ANNIE_MAX_MANA - spent + len(regen) * ANNIE_MANA_PER_REGEN)


    def test_waits_until_enough_mana_regenerated(self, load_champion, darius):
        caster = annie(load_champion("annie"))
        caster.current_resource = 50
        sim = Simulation(caster, darius)

        sim.do_combo(combo(ActionType.Q))

        # 20 mana missing, 1.116 per regeneration tick: the 18th tick (18 x 16 ticks) brings enough to start.
        assert results(sim, EffectType.COST, CostResource.MANA) == [(18 * REGEN_TICKS + CAST_TICKS, Q_RANK_3_COST)]


    def test_never_enough_mana_is_an_error(self, load_champion, darius):
        champion = load_champion("annie")
        champion.q.cost = "600"  # more than Annie's maximum mana
        sim = Simulation(annie(champion), darius)

        with pytest.raises(SimulationError, match="mana"):
            sim.do_combo(combo(ActionType.Q))


class TestHealthRegeneration():

    def test_regenerates_only_when_not_full(self, load_champion, darius):
        sim = Simulation(annie(load_champion("annie")), darius)

        # Q hits Darius at tick 11, W lands at tick 16 together with the first regeneration tick.
        sim.do_combo(combo(ActionType.Q, ActionType.W))

        assert results(sim, EffectType.REGEN, CostResource.HEALTH, target=Actor.RED) == [(REGEN_TICKS, DARIUS_HP_PER_REGEN)]
        assert results(sim, EffectType.REGEN, CostResource.HEALTH) == []  # Annie is at full health


class TestEnergy():

    def test_energy_costs_and_regeneration(self, load_champion, darius):
        caster = annie(energy_champion(load_champion))
        sim = Simulation(caster, darius)

        sim.do_combo(combo(ActionType.Q, ActionType.W))

        assert results(sim, EffectType.COST, CostResource.ENERGY) == [(CAST_TICKS, 50), (2 * CAST_TICKS, 50)]
        assert results(sim, EffectType.REGEN, CostResource.ENERGY) == [(REGEN_TICKS, 5)]
        assert caster.current_resource == pytest.approx(200 - 100 + 5)


    def test_cost_in_the_wrong_resource_is_an_error(self, load_champion, darius):
        champion = energy_champion(load_champion)
        champion.q.cost_resource = CostResource.MANA
        sim = Simulation(annie(champion), darius)

        with pytest.raises(SimulationError, match="mana"):
            sim.do_combo(combo(ActionType.Q))
