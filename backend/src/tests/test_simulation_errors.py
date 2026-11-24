import pytest

from src.server.models.enums import ActionType, Actor, to_ticks
from src.server.models.request import Action, Rank
from src.server.models.rule import Rule
from src.server.simulation.character import Character
from src.server.simulation.exceptions import ComboError, DataError, SimulationError
from src.server.simulation.simulation import Simulation


def with_passive_rule(load_champion, name: str, rule: dict) -> Character:
    champion = load_champion(name)
    champion.passive.rules.append(Rule.parse_obj(rule))
    return Character(champion, 6, Rank(q=1, w=1, e=1, r=1), [])


def attacks(count: int) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA) for _ in range(count)]


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def broken_rule_after(seconds: float) -> dict:
    return {"trigger": "on_start", "delay": str(seconds), "actions": [{"type_": "Damage", "props": {
        "target": "target", "amount": "unknown_variable", "dmg_sub_type": "True"}}]}


class TestEndlessRules:
    def test_a_rule_triggering_itself_in_the_same_tick_stops(self, load_champion, darius):
        # Every damage dealt deals damage again, without a delay: the tick never ends.
        vayne = with_passive_rule(load_champion, "vayne", {"trigger": "on_damage_dealt", "actions": [{"type_": "Damage", "props": {
            "target": "target", "amount": "1", "dmg_sub_type": "True"}}]})

        with pytest.raises(SimulationError) as error:
            Simulation(vayne, darius).do_combo(attacks(1))

        assert error.value.phase == "effect"
        assert error.value.tick is not None
        assert "passive" in str(error.value)

    def test_a_long_but_finite_chain_in_one_tick_is_fine(self, load_champion, darius):
        # Three bounces of a reaction, then the condition stops it.
        vayne = with_passive_rule(load_champion, "vayne", {
            "trigger": "on_damage_dealt",
            "conditions": [{"actor": "target", "key": "missing_hp", "comparison": "Less than", "value": "3"}],
            "actions": [{"type_": "Damage", "props": {"target": "target", "amount": "1", "dmg_sub_type": "True"}}]})
        Simulation(vayne, darius).do_combo(attacks(1))


class TestErrorsInQueuedEffects:
    def test_an_error_after_the_last_action_is_a_simulation_error(self, load_champion, darius):
        vayne = with_passive_rule(load_champion, "vayne", broken_rule_after(2))

        with pytest.raises(SimulationError) as error:
            Simulation(vayne, darius).do_combo(attacks(1))

        assert error.value.phase == "effect"
        assert error.value.tick == to_ticks(2)
        assert error.value.action_index is None
        assert "passive" in str(error.value) and "unknown_variable" in str(error.value)

    def test_an_error_during_a_later_action_is_not_blamed_on_that_action(self, load_champion, darius):
        vayne = with_passive_rule(load_champion, "vayne", broken_rule_after(0.1))

        with pytest.raises(SimulationError) as error:
            Simulation(vayne, darius).do_combo(attacks(3))

        assert error.value.phase == "effect"
        assert error.value.action_index is None
        assert error.value.tick == to_ticks(0.1)

    def test_an_error_while_casting_names_the_action(self, load_champion, darius):
        vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=1, e=1, r=1), [])
        no_item = Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.I1)

        with pytest.raises(SimulationError) as error:
            Simulation(vayne, darius).do_combo(attacks(1) + [no_item])

        assert isinstance(error.value, ComboError)
        assert error.value.phase == "cast"
        assert error.value.action_index == 1


class TestUnknownNames:
    @pytest.mark.parametrize("action_type", ["ApplyBuff", "RemoveBuff"])
    def test_an_unknown_buff_is_a_data_error(self, load_champion, darius, action_type):
        vayne = with_passive_rule(load_champion, "vayne", {"trigger": "on_start", "actions": [{"type_": action_type, "props": {
            "buff": "no_such_buff", "target": "target"}}]})

        with pytest.raises(DataError, match="Unknown buff 'no_such_buff'") as error:
            Simulation(vayne, darius).do_combo(attacks(1))

        assert error.value.champion == "Vayne"
        assert error.value.rule == f"rule {len(vayne.passive.rules)}"
