import pytest

from src.server.models.enums import ActionType, Actor, EffectType, Stat, to_ticks
from src.server.models.request import Action, Rank
from src.server.models.rule import Buff, Rule
from src.server.simulation.character import Character
from src.server.simulation.simulation import MAX_SECONDS_AFTER_LAST_ACTION, Simulation


def vayne_with_burn(load_champion, damage: str, duration: str) -> Character:
    # A burn on the enemy from the start, ticking every second.
    champion = load_champion("vayne")
    champion.passive.buffs.append(Buff.parse_obj({
        "name": "burn", "duration": duration, "interval": "1",
        "rules": [{"trigger": "on_interval", "actions": [{"type_": "Damage", "props": {
            "target": "bearer", "amount": damage, "dmg_sub_type": "True"}}]}],
    }))
    champion.passive.rules.append(Rule.parse_obj({
        "trigger": "on_start", "actions": [{"type_": "ApplyBuff", "props": {"buff": "burn", "target": "target"}}],
    }))
    return Character(champion, 6, Rank(q=1, w=1, e=1, r=1), [])


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def damage_ticks(sim: Simulation) -> list[int]:
    return [event.tick for event in sim.effect_list for result in event.result if result.type_ == EffectType.DAMAGE]


def test_last_action_tick_is_the_start_of_the_last_action(load_champion, darius):
    annie = Character(load_champion("annie"), 6, Rank(q=1, w=1, e=1, r=1), [])
    sim = Simulation(annie, darius)

    response = sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in (ActionType.Q, ActionType.W)])

    assert response.last_action_tick == to_ticks(0.25)  # W starts when Q's cast ends


def test_endless_effects_stop_after_the_cap(load_champion, darius):
    sim = Simulation(vayne_with_burn(load_champion, "1", duration="1000"), darius)

    response = sim.do_combo([])

    assert damage_ticks(sim)[-1] == to_ticks(MAX_SECONDS_AFTER_LAST_ACTION)
    assert response.ticks == to_ticks(MAX_SECONDS_AFTER_LAST_ACTION)
    assert not sim.queue


def test_death_is_recorded_once_and_the_simulation_goes_on(load_champion, darius):
    sim = Simulation(vayne_with_burn(load_champion, "600", duration="5"), darius)
    assert 600 < darius.get_stat(Stat.HP) < 1200

    response = sim.do_combo([])

    assert response.deaths == {Actor.RED: to_ticks(2)}
    assert len(damage_ticks(sim)) == 5  # overkill stays visible
    assert '"deaths": {"red": 61}' in response.json()


def test_no_deaths_without_a_kill(load_champion, darius):
    sim = Simulation(vayne_with_burn(load_champion, "1", duration="5"), darius)

    assert sim.do_combo([]).deaths == {}
