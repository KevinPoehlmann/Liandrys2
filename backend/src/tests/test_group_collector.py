import pytest

from src.server.models.enums import ActionType, Actor, EffectType, OriginKind, to_ticks
from src.server.models.result import Origin
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the fixtures (live wiki values).
# The Collector: 50 AD, 10 lethality (flat armor penetration), 25 % crit chance; crits deal 200 %.
GROWTH_LVL_6 = 3.95
COLLECTOR_AD, LETHALITY, CRIT_CHANCE = 50, 10, 0.25
EXPECTED_CRIT = 1 + CRIT_CHANCE * (2 - 1)
RIVEN_BASE_AD = 64 + 3 * GROWTH_LVL_6
RIVEN_AD = RIVEN_BASE_AD + COLLECTOR_AD
RIVEN_MAX_HP = 630 + 100 * GROWTH_LVL_6
RIVEN_ARMOR = 33 + 4.4 * GROWTH_LVL_6
DARIUS_AD = 64 + 5 * GROWTH_LVL_6 + COLLECTOR_AD
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6
VAYNE_AD = 60 + 2.35 * GROWTH_LVL_6 + COLLECTOR_AD
VAYNE_ARMOR = 23 + 4.6 * GROWTH_LVL_6
ANNIE_ARMOR = 23 + 4 * GROWTH_LVL_6
ANNIE_MAX_HP = 560 + 96 * GROWTH_LVL_6
THORNMAIL_ARMOR, THORNMAIL_HP = 75, 150
RIVEN_HIT_TICK = 8

DEATH = Origin(kind=OriginKind.ITEM, name="The Collector")


def physical(raw: float, armor: float) -> float:
    return raw * 100 / (100 + armor - LETHALITY)


def action(action_type: ActionType, crit: bool | None = None, actor: Actor = Actor.BLUE) -> Action:
    target = Actor.RED if actor == Actor.BLUE else Actor.BLUE
    return Action(actor=actor, target=target, action_type=action_type, crit=crit)


def damage(sim: Simulation, kind: OriginKind, name: str) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.origin.kind == kind and result.origin.name == name and result.type_ == EffectType.DAMAGE
    ]


@pytest.fixture
def riven(load_champion, load_item) -> Character:
    return Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), [load_item("the_collector")])


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


class TestCriticalStrikes():

    @pytest.mark.parametrize("crit, factor", [(None, EXPECTED_CRIT), (True, 2), (False, 1)])
    def test_attack_crits_by_choice_or_expected_value(self, riven, darius, crit, factor):
        sim = Simulation(riven, darius)

        sim.do_combo([action(ActionType.BA, crit)])

        assert damage(sim, OriginKind.ATTACK, "BA") == [(RIVEN_HIT_TICK, pytest.approx(physical(factor * RIVEN_AD, DARIUS_ARMOR)))]


    def test_on_hit_damage_doesnt_crit(self, load_champion, load_item, darius):
        riven = Character(load_champion("riven"), 6, Rank(q=3, w=1, e=1, r=1), [load_item("the_collector"), load_item("sheen")])
        sim = Simulation(riven, darius)

        sim.do_combo([action(ActionType.Q), action(ActionType.BA, crit=True)])

        [(_, proc)] = damage(sim, OriginKind.ITEM, "Sheen")
        assert proc == pytest.approx(physical(RIVEN_BASE_AD, DARIUS_ARMOR))


    def test_crippling_strike_crits_with_the_attack(self, load_champion, load_item):
        darius = Character(load_champion("darius"), 6, Rank(q=0, w=1, e=0, r=0), [load_item("the_collector")])
        vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(darius, vayne)

        sim.do_combo([action(ActionType.W), action(ActionType.BA, crit=True)])

        assert [value for _, value in damage(sim, OriginKind.ABILITY, "W")] == [pytest.approx(physical(2 * 0.4 * DARIUS_AD, VAYNE_ARMOR))]


    def test_tumble_doesnt_crit(self, load_champion, load_item, darius):
        vayne = Character(load_champion("vayne"), 6, Rank(q=3, w=0, e=0, r=0), [load_item("the_collector")])
        sim = Simulation(vayne, darius)

        sim.do_combo([action(ActionType.Q), action(ActionType.BA, crit=True)])

        assert [value for _, value in damage(sim, OriginKind.ABILITY, "Q")] == [pytest.approx(physical(0.95 * VAYNE_AD, DARIUS_ARMOR))]
        assert [value for _, value in damage(sim, OriginKind.ATTACK, "BA")] == [pytest.approx(physical(2 * VAYNE_AD, DARIUS_ARMOR))]


class TestDeath():

    ATTACK = physical(RIVEN_AD, DARIUS_ARMOR)

    def test_executes_below_5_percent(self, riven, darius):
        darius.current_hp = self.ATTACK + 0.04 * DARIUS_MAX_HP
        sim = Simulation(riven, darius)

        sim.do_combo([action(ActionType.BA, crit=False)])

        assert damage(sim, OriginKind.ITEM, "The Collector") == [(RIVEN_HIT_TICK, pytest.approx(0.04 * DARIUS_MAX_HP))]
        assert sim.deaths[Actor.RED] == RIVEN_HIT_TICK


    def test_no_execute_above_5_percent(self, riven, darius):
        darius.current_hp = self.ATTACK + 0.06 * DARIUS_MAX_HP
        sim = Simulation(riven, darius)

        sim.do_combo([action(ActionType.BA, crit=False)])

        assert damage(sim, OriginKind.ITEM, "The Collector") == []


    def test_damage_over_time_executes_too(self, load_champion, load_item):
        # E rank 0: its passive armor penetration would change the numbers.
        darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=0, r=1), [load_item("the_collector")])
        riven = Character(load_champion("riven"), 6, Rank(q=1, w=1, e=1, r=1), [])
        # After the attack Riven is 1 health above 5 %; her regeneration until the first bleed tick (about 2 health)
        # is less than the bleed tick ((18 + 0.3 * 50) / 4 = 8.25 raw, about 5.9 after armor).
        riven.current_hp = physical(DARIUS_AD, RIVEN_ARMOR) + 0.05 * RIVEN_MAX_HP + 1
        sim = Simulation(darius, riven)

        sim.do_combo([action(ActionType.BA, crit=False)])

        bleed_ticks = [tick for tick, _ in damage(sim, OriginKind.PASSIVE, "passive")]
        [(execute_tick, _)] = damage(sim, OriginKind.ITEM, "The Collector")
        assert execute_tick == bleed_ticks[0]


    def test_damage_only_to_a_shield_doesnt_execute(self, load_champion, load_item):
        # Vayne's attack (119.3 AD into 103.8 armor = 58.5) stays below Molten Shield's 60; Annie is below 5 % already.
        vayne = Character(load_champion("vayne"), 6, Rank(q=0, w=0, e=0, r=0), [load_item("the_collector")])
        annie = Character(load_champion("annie"), 6, Rank(q=3, w=1, e=1, r=1), [load_item("thornmail")])
        annie.current_hp = 0.04 * (ANNIE_MAX_HP + THORNMAIL_HP)
        sim = Simulation(vayne, annie)

        sim.do_combo([Action(actor=Actor.RED, target=Actor.RED, action_type=ActionType.E), action(ActionType.BA, crit=False)])

        assert annie.damage_shielded == pytest.approx(physical(VAYNE_AD, ANNIE_ARMOR + THORNMAIL_ARMOR))
        assert damage(sim, OriginKind.ITEM, "The Collector") == []
