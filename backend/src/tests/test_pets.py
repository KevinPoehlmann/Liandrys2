import pytest
from pydantic import ValidationError

from src.server.models.champion import Champion
from src.server.models.dataenums import ActionType, Actor, EffectType, RuleActionType, Target, to_ticks
from src.server.models.pet import Pet
from src.server.models.request import Action, Rank
from src.server.models.rule import Rule
from src.server.simulation.character import Character
from src.server.simulation.pet import PetCharacter
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the patch 15.12.1 fixtures (see test_group_annie.py).
GROWTH_LVL_6 = 3.95
ANNIE_MAX_HP = 560 + 96 * GROWTH_LVL_6
DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6
R_RANK_1_MAGIC_PEN = 0.1

SUMMON_TICK = to_ticks(0.25)  # end of Annie's R cast
LIFETIME = to_ticks(2)
DUMMY = Actor("blue.dummy")


def dummy_pet(**passive) -> dict:
    return {
        "name": "dummy",
        "duration": "2",
        "stats": {"hp": "1000", "attackspeed": "1"},
        "attack": {"scaling": "by_rank(10, 20, 30) + 0.01 * owner_max_hp", "dmg_type": ["Ability damage"],
                   "dmg_sub_type": "Magic", "windup": 0.2},
        "passive": {"name": "Dummy"} | passive,
    }


def rule(trigger: str | None, *actions: dict) -> dict:
    return {"trigger": trigger, "actions": list(actions)}


def action(type_: str, **props) -> dict:
    return {"type_": type_, "props": props}


def without_tibbers(champion: Champion) -> Champion:
    champion.r.pets = []
    for ability in (champion.q, champion.w, champion.e, champion.r):
        for stage in ability.stages:
            for stage_rule in stage.rules:
                stage_rule.actions = [
                    a for a in stage_rule.actions
                    if a.type_ != RuleActionType.SUMMON and getattr(a.props, "target", None) != Target.PET
                ]
    return champion


@pytest.fixture
def annie_with_pet(load_champion):
    def _build(pet: dict | None = None, e_rules: tuple[dict, ...] = ()) -> Character:
        champion = without_tibbers(load_champion("annie"))
        champion.r.pets.append(Pet.parse_obj(pet or dummy_pet()))
        champion.r.stages[0].rules.append(Rule.parse_obj(rule(None, action("Summon", pet="dummy"))))
        champion.e.stages[0].rules.extend(Rule.parse_obj(r) for r in e_rules)
        return Character(champion, 6, Rank(q=1, w=1, e=1, r=1), [])
    return _build


@pytest.fixture
def darius(load_champion) -> Character:
    return Character(load_champion("darius"), 6, Rank(q=1, w=1, e=1, r=1), [])


def combo(*action_types: ActionType) -> list[Action]:
    return [Action(actor=Actor.BLUE, target=Actor.RED, action_type=a) for a in action_types]


def pet_hits(sim: Simulation) -> list[tuple[int, float]]:
    return [
        (event.tick, result.value)
        for event in sim.effect_list
        for result in event.result
        if result.actor == DUMMY and result.type_ == EffectType.DAMAGE
    ]


class TestActorIds():

    @pytest.mark.parametrize("actor_id", ["blue", "red", "blue.tibbers", "red.ghoul#2", "blue.top.tibbers"])
    def test_valid_ids(self, actor_id):
        assert Action(actor=actor_id, target="red", action_type=ActionType.BA).actor == actor_id


    @pytest.mark.parametrize("actor_id", ["green", "Blue", "blue.", "blue.Tibbers", "blue#2"])
    def test_invalid_ids(self, actor_id):
        with pytest.raises(ValidationError):
            Action(actor=actor_id, target="red", action_type=ActionType.BA)


    def test_team_is_the_first_part(self):
        assert Actor("red.ghoul#2").team == Actor.RED


class TestPetModel():

    def test_name_must_fit_into_an_actor_id(self):
        with pytest.raises(ValidationError):
            Pet.parse_obj(dummy_pet() | {"name": "Tibbers"})


    @pytest.mark.parametrize("windup", [0, 1])
    def test_windup_is_a_share_of_the_attack_time(self, windup):
        pet = dummy_pet()
        pet["attack"]["windup"] = windup
        with pytest.raises(ValidationError):
            Pet.parse_obj(pet)


class TestSummon():

    def test_pet_attacks_on_its_own_until_it_expires(self, annie_with_pet, darius):
        sim = Simulation(annie_with_pet(), darius)

        sim.do_combo(combo(ActionType.R))

        # Attack time 1 s = 31 ticks, windup 20 % = 7 ticks; a third attack would start after the 2 s lifetime.
        raw = 10 + 0.01 * ANNIE_MAX_HP
        expected = pytest.approx(raw * 100 / (100 + DARIUS_MR * (1 - R_RANK_1_MAGIC_PEN)))
        assert pet_hits(sim) == [(SUMMON_TICK + 7, expected), (SUMMON_TICK + 31 + 7, expected)]
        assert sim.actors[DUMMY].expired


    def test_attack_in_flight_misses_when_the_pet_expires(self, annie_with_pet, darius):
        # Lifetime 1.1 s = 34 ticks: the second attack starts at 31 but would only hit at 38.
        sim = Simulation(annie_with_pet(dummy_pet() | {"duration": "1.1"}), darius)

        sim.do_combo(combo(ActionType.R))

        assert [tick for tick, _ in pet_hits(sim)] == [SUMMON_TICK + 7]


    def test_pet_buff_from_its_passive_changes_its_attacks(self, annie_with_pet, darius):
        frenzy = {"name": "frenzy", "duration": "1", "stats": [{"stat": "attackspeed", "formula": "1"}]}
        pet = dummy_pet(rules=[rule("on_start", action("ApplyBuff", buff="frenzy", target="self"))], buffs=[frenzy])
        sim = Simulation(annie_with_pet(pet), darius)

        sim.do_combo(combo(ActionType.R))

        # Frenzy (1 s = 31 ticks) doubles the attack speed: attack time 16 ticks, windup 4 ticks.
        # The third attack starts after frenzy ended and is slow again.
        assert [tick for tick, _ in pet_hits(sim)] == [SUMMON_TICK + 4, SUMMON_TICK + 16 + 4, SUMMON_TICK + 32 + 7]


    def test_owner_can_target_its_pet(self, annie_with_pet, darius):
        shield_pet = rule(None, action("Shield", target="pet", scaling="50", duration="3"))
        sim = Simulation(annie_with_pet(e_rules=(shield_pet,)), darius)

        sim.do_combo(combo(ActionType.R, ActionType.E))

        assert [shield.value for shield in sim.actors[DUMMY].shields] == [50]


    def test_rule_for_the_pet_does_nothing_without_a_pet(self, annie_with_pet, darius):
        shield_pet = rule(None, action("Shield", target="pet", scaling="50", duration="3"))
        sim = Simulation(annie_with_pet(e_rules=(shield_pet,)), darius)

        sim.do_combo(combo(ActionType.E))

        assert DUMMY not in sim.actors


    def test_pet_can_target_its_owner(self, annie_with_pet, darius):
        pet = dummy_pet(rules=[rule("on_start", action("Shield", target="owner", scaling="30", duration="3"))])
        annie = annie_with_pet(pet)
        sim = Simulation(annie, darius)

        sim.do_combo(combo(ActionType.R))

        assert [(shield.value, shield.actor) for shield in annie.shields] == [(30, DUMMY)]


    def test_owner_knows_the_buffs_of_its_pets(self, annie_with_pet):
        frenzy = {"name": "frenzy", "duration": "1"}
        annie = annie_with_pet(dummy_pet(buffs=[frenzy]))

        assert annie.buff_definitions["frenzy"][1] == ActionType.R


    def test_expiry_ends_the_buffs_the_pet_put_on_others(self, annie_with_pet, darius):
        mark = {"name": "dummy_mark"}  # no duration: only the expiry can end it
        pet = dummy_pet(rules=[rule("on_start", action("ApplyBuff", buff="dummy_mark", target="target"))], buffs=[mark])
        sim = Simulation(annie_with_pet(pet), darius)

        sim.do_combo(combo(ActionType.R))

        assert darius.get_buff_stacks("dummy_mark") == 0


    def test_several_pets_get_numbers(self, annie_with_pet, darius):
        sim = Simulation(annie_with_pet(), darius)

        sim._summon("dummy", Actor.BLUE, 0)
        sim._summon("dummy", Actor.BLUE, 0)

        assert [actor for actor in sim.actors if isinstance(sim.actors[actor], PetCharacter)] == ["blue.dummy", "blue.dummy#2"]
