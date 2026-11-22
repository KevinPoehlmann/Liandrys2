import json

import pytest

from src.server.models.dataenums import ActionType, Actor, EffectType, OriginKind, Stat
from src.server.models.request import Action, Rank
from src.server.models.rune import Rune
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation


# Expected values are calculated by hand from the fixtures (live wiki values).
# Adaptive force: 1 point = 0.6 bonus AD or 1 AP, whichever the champion has more bonus of; a tie goes by adaptive type.
GROWTH_LVL_6 = 3.95
SHARDS = 2 * 9
RIVEN_AD = 64 + 3 * GROWTH_LVL_6
VAYNE_AD = 60 + 2.35 * GROWTH_LVL_6
VEIGAR_AD = 52 + 2.7 * GROWTH_LVL_6
DARIUS_ARMOR = 37 + 5.2 * GROWTH_LVL_6
CONQUEROR_FORCE_LVL_6 = 1.8 + 2.46 * 5 / 17  # per stack, assumed linear from level 1 to 18


def load_rune(name: str) -> Rune:
    with open(f"src/tests/static/test_group/runes/{name}.json", encoding="utf-8") as f:
        return Rune.parse_obj(json.load(f))


def shards() -> list[Rune]:
    return [load_rune("offence_adaptive_force"), load_rune("flex_adaptive_force")]


def physical(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_ARMOR)


def character(load_champion, name: str, items=(), runes=(), **scenario) -> Character:
    return Character(load_champion(name), 6, Rank(q=1, w=1, e=1, r=1), list(items), scenario=scenario, runes=list(runes))


class TestAdaptiveForce():

    def test_physical_champion_without_bonus_gets_ad(self, load_champion):
        riven = character(load_champion, "riven", runes=shards())

        assert riven.get_stat(Stat.AD) == pytest.approx(RIVEN_AD + 0.6 * SHARDS)
        assert riven.get_stat(Stat.AP) == 0


    def test_magic_champion_without_bonus_gets_ap(self, load_champion):
        annie = character(load_champion, "annie", runes=shards())

        assert annie.get_stat(Stat.AP) == pytest.approx(SHARDS)


    def test_more_bonus_ap_than_ad_gives_ap(self, load_champion, load_item):
        # Gunblade: 40 AD, 80 AP.
        riven = character(load_champion, "riven", items=[load_item("hextech_gunblade")], runes=shards())

        assert riven.get_stat(Stat.AP) == pytest.approx(80 + SHARDS)
        assert riven.get_stat(Stat.AD) == pytest.approx(RIVEN_AD + 40)


    def test_champion_passive_ap_doesnt_count(self, load_champion, load_item):
        # 100 Phenomenal Evil stacks are 100 AP from Veigar's passive; BotRK's 40 AD wins the comparison.
        veigar = character(load_champion, "veigar", items=[load_item("blade_of_the_ruined_king")], runes=shards())
        veigar.apply_buff("phenomenal_evil", veigar, 100, 0)

        assert veigar.get_stat(Stat.AD) == pytest.approx(VEIGAR_AD + 40 + 0.6 * SHARDS)
        assert veigar.get_stat(Stat.AP) == pytest.approx(100)


    def test_tie_without_adaptive_type_is_an_error(self, load_champion):
        champion = load_champion("riven")
        champion.adaptive_type = None
        riven = Character(champion, 6, Rank(q=1, w=1, e=1, r=1), [], runes=shards())

        with pytest.raises(ValueError, match="adaptive type"):
            riven.get_stat(Stat.AD)


class TestConqueror():

    @pytest.mark.parametrize("name, ad, stacks_per_hit", [("riven", RIVEN_AD, 2), ("vayne", VAYNE_AD, 1)])
    def test_attacks_stack_melee_2_ranged_1(self, load_champion, name, ad, stacks_per_hit):
        # Ranks 0: no Vayne W proc, no Riven abilities.
        attacker = Character(load_champion(name), 6, Rank(q=0, w=0, e=0, r=0), [], runes=[load_rune("conqueror")])
        sim = Simulation(attacker, character(load_champion, "darius"))

        sim.do_combo([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA)] * 2)

        # The first hit gives the stacks, the second already uses them.
        attacks = [result.value for event in sim.effect_list for result in event.result
                   if result.origin.name == "BA" and result.type_ == EffectType.DAMAGE]
        assert attacks == [pytest.approx(physical(ad)), pytest.approx(physical(ad + 0.6 * stacks_per_hit * CONQUEROR_FORCE_LVL_6))]


DARIUS_MR = 32 + 2.05 * GROWTH_LVL_6
DARIUS_MAX_HP = 652 + 114 * GROWTH_LVL_6
ANNIE_R_PEN = 0.1
TIBBERS = Actor("blue.tibbers")


def magic(raw: float) -> float:
    return raw * 100 / (100 + DARIUS_MR * (1 - ANNIE_R_PEN))


def blue(action_type: ActionType) -> Action:
    return Action(actor=Actor.BLUE, target=Actor.RED, action_type=action_type)


def damage_values(sim: Simulation, name: str, actor: Actor = Actor.BLUE) -> list[float]:
    return [result.value for event in sim.effect_list for result in event.result
            if result.origin.name == name and result.actor == actor and result.type_ == EffectType.DAMAGE]


class TestConquerorStacks():

    def test_every_cast_stacks(self, load_champion):
        riven = Character(load_champion("riven"), 6, Rank(q=3, w=0, e=0, r=0), [], runes=[load_rune("conqueror")])
        sim = Simulation(riven, character(load_champion, "darius"))

        sim.do_combo([blue(ActionType.Q)] * 3 + [blue(ActionType.BA)])

        # Three Broken Wings casts are three cast instances: 2 stacks each.
        assert damage_values(sim, "BA") == [pytest.approx(physical(RIVEN_AD + 0.6 * 6 * CONQUEROR_FORCE_LVL_6))]


    def test_one_cast_stacks_once_every_4_seconds_and_pet_attacks_dont_stack(self, load_champion):
        # Summer's Last Tibbers: R's hit gives 2 stacks; the aura shares R's cast instance (no stacks within 4 s),
        # Tibbers' attacks are pet basic damage (none). So Q, cast right after R, sees 2 stacks (AP: Annie is magic).
        annie = Character(load_champion("annie"), 6, Rank(q=3, w=1, e=1, r=1), [], runes=[load_rune("conqueror")])
        sim = Simulation(annie, character(load_champion, "darius"))

        sim.do_combo([blue(ActionType.R), blue(ActionType.Q)])

        assert damage_values(sim, "Q") == [pytest.approx(magic(160 + 0.8 * 2 * CONQUEROR_FORCE_LVL_6))]


    def test_heals_from_the_hit_after_the_12th_stack(self, load_champion):
        riven = Character(load_champion("riven"), 6, Rank(q=0, w=0, e=0, r=0), [], runes=[load_rune("conqueror")])
        riven.apply_buff("conqueror", riven, 10, 0)
        riven.current_hp = 100
        sim = Simulation(riven, character(load_champion, "darius"))

        sim.do_combo([blue(ActionType.BA)] * 2)

        second_attack = physical(RIVEN_AD + 0.6 * 12 * CONQUEROR_FORCE_LVL_6)
        heals = [result.value for event in sim.effect_list for result in event.result
                 if result.origin.kind == OriginKind.RUNE and result.type_ == EffectType.HEAL]
        assert heals == [pytest.approx(0.08 * second_attack)]


class TestPetDamageForTheOwner():

    def test_tibbers_triggers_the_collectors_execute(self, load_champion, load_item):
        annie = Character(load_champion("annie"), 6, Rank(q=3, w=1, e=1, r=1), [load_item("the_collector")])
        darius = character(load_champion, "darius")
        # After R's hit (150 magic) Darius is 8 health above 5 %; Tibbers' first attack (30 magic) takes him below.
        darius.current_hp = magic(150) + 0.05 * DARIUS_MAX_HP + 8
        sim = Simulation(annie, darius)

        sim.do_combo([blue(ActionType.R)])

        executes = [event.tick for event in sim.effect_list for result in event.result if result.origin.name == "The Collector"]
        pet_hits = {event.tick for event in sim.effect_list for result in event.result
                    if result.actor == TIBBERS and result.type_ == EffectType.DAMAGE}
        assert len(executes) == 1 and executes[0] in pet_hits
