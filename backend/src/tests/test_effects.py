import pytest

from src.server.models.enums import ActionType, Actor, EffectType, OriginKind, to_ticks
from src.server.models.result import Origin
from src.server.models.request import Action, Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import DEFAULT_DISTANCE, Simulation


# Expected values are calculated by hand from the fixtures. Stat growth at level 6: 3.95
DARIUS_MR = 32 + 2.05 * 3.95
Q_RANK_3 = 160
Q_HIT_TICK = to_ticks(0.25) + to_ticks(DEFAULT_DISTANCE / 1400)


def test_vamp_heals_a_share_of_the_damage_after_mitigation(load_champion):
    champion = load_champion("annie")
    damage_rule = champion.q.stages[0].rules[2]
    damage_rule.actions[0].props.vamp = 0.5
    annie = Character(champion, 6, Rank(q=3, w=1, e=1, r=0), [], scenario={"pyromania_start": 0})
    annie.current_hp -= 200
    darius = Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])
    sim = Simulation(annie, darius)

    sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q)])

    heals = [(event.tick, result) for event in sim.effect_list for result in event.result if result.type_ == EffectType.HEAL]
    [(tick, heal)] = heals
    assert tick == Q_HIT_TICK
    assert heal.raw == pytest.approx(0.5 * Q_RANK_3 * 100 / (100 + DARIUS_MR))
    assert heal.origin == Origin(kind=OriginKind.ABILITY, name="Q")
