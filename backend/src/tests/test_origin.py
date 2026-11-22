import json

import pytest

from src.server.models.dataenums import ActionType, Actor, CostResource, EffectType, Origin, OriginKind
from src.server.models.request import Action, Rank
from src.server.models.summonerspell import Summonerspell
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


def origins(sim: Simulation, type_: EffectType = EffectType.DAMAGE) -> set[tuple[str, Origin]]:
    return {(result.actor, result.origin) for event in sim.effect_list for result in event.result if result.type_ == type_}


def origin(kind: OriginKind, name: str, buff: str | None = None) -> Origin:
    return Origin(kind=kind, name=name, buff=buff)


def blue(action_type: ActionType) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type)


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


class TestOrigin():

    def test_basic_attack_and_passive_debuff(self, darius, load_champion):
        vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(darius, vayne)

        sim.do_combo([blue(ActionType.BA)])

        assert origins(sim) == {
            (Actor.BLUE, origin(OriginKind.ATTACK, "BA")),
            (Actor.BLUE, origin(OriginKind.PASSIVE, "passive", "hemorrhage")),
        }


    def test_ability_and_its_cost(self, darius, load_champion):
        annie = Character(load_champion("annie"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie, darius)

        sim.do_combo([blue(ActionType.Q)])

        assert origins(sim) == {(Actor.BLUE, origin(OriginKind.ABILITY, "Q"))}
        assert origins(sim, EffectType.COST) == {(Actor.BLUE, origin(OriginKind.ABILITY, "Q"))}


    def test_pet_attacks_and_aura_belong_to_the_summoning_ability(self, darius, load_champion):
        annie = Character(load_champion("annie"), 6, Rank(q=1, w=1, e=1, r=1), [], scenario={"pyromania_start": 0})
        sim = Simulation(annie, darius)

        sim.do_combo([blue(ActionType.R)])

        tibbers = Actor("blue.tibbers")
        assert origins(sim) == {
            (Actor.BLUE, origin(OriginKind.ABILITY, "R")),
            (tibbers, origin(OriginKind.ABILITY, "R")),
            (tibbers, origin(OriginKind.ABILITY, "R", "tibbers_aura")),
        }


    def test_summoner_spell_by_name(self, darius, load_champion):
        with open("src/tests/static/test_group/summonerspells/ignite.json", encoding="utf-8") as f:
            ignite = Summonerspell.parse_obj(json.load(f))
        vayne = Character(load_champion("vayne"), 6, Rank(q=1, w=1, e=1, r=1), [], summonerspells=[ignite])
        sim = Simulation(vayne, darius)

        sim.do_combo([blue(ActionType.S1)])

        assert origins(sim) == {(Actor.BLUE, origin(OriginKind.SUMMONER, "Ignite", "ignite"))}


    def test_regeneration(self, darius, load_champion):
        annie = Character(load_champion("annie"), 6, Rank(q=1, w=1, e=1, r=1), [])
        sim = Simulation(annie, darius)

        sim.do_combo([blue(ActionType.Q), blue(ActionType.W)])

        regen = {(result.resource, result.origin) for event in sim.effect_list for result in event.result
                 if result.type_ == EffectType.REGEN}
        assert regen == {
            (CostResource.MANA, origin(OriginKind.REGEN, "mana")),
            (CostResource.HEALTH, origin(OriginKind.REGEN, "health")),
        }
