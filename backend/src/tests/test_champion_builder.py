import json
from datetime import datetime
from pathlib import Path

import pytest

from src.server.loader.champion_builder import (apply_loader_part, build_champion, champion_stats, initial_structure,
                                                loaded_spells, wiki_mismatches)
from src.server.loader.champion_source import champion_strings, parse_champion_data, parse_wiki_templates
from src.server.models.champion import RawChampion
from src.server.models.enums import AdaptiveType, RangeType, ResourceType
from src.server.models.json_validation import ChampionJson


CDRAGON = Path(__file__).parent / "static" / "cdragon"
VEIGAR_RANKS = {"q": 5, "w": 5, "e": 5, "r": 3}


def fixture(name: str) -> dict:
    return json.loads((CDRAGON / name).read_text(encoding="utf-8"))


def raw_champion(champion_id: str, wiki: bool = False) -> RawChampion:
    name = champion_id.lower()
    return RawChampion(
        champion_id=champion_id, patch="16.23.1", build="16.23.1", fetched_at=datetime(2026, 11, 24),
        cdragon=fixture(f"{name}.bin.json"), strings=fixture(f"{name}.strings.json")["entries"],
        wiki=parse_wiki_templates(fixture(f"{name}.wiki.json")) if wiki else {},
    )


@pytest.fixture
def veigar_spells():
    return loaded_spells(raw_champion("Veigar", wiki=True), VEIGAR_RANKS)


class TestLoadedSpells():

    def test_slots_come_from_the_champion_record(self, veigar_spells):
        assert {slot: spell.script_name for slot, spell in veigar_spells.items()} == {
            "q": "VeigarBalefulStrike", "w": "VeigarDarkMatter", "e": "VeigarEventHorizon", "r": "VeigarR",
            "passive": "VeigarPassive"}


    def test_name_and_tooltip(self, veigar_spells):
        strike = veigar_spells["q"]

        assert strike.name == "Baleful Strike"
        assert "<magicDamage>@TotalDamage@ magic damage</magicDamage>" in strike.tooltip


    def test_tooltip_key_may_differ_from_the_spell(self):
        # Darius Q is the spell DariusCleave, its texts are Spell_DariusQ_*.
        spells = loaded_spells(raw_champion("Darius"), {"q": 5, "w": 5, "e": 5, "r": 3})

        assert spells["q"].script_name == "DariusCleave"
        assert spells["q"].name == "Decimate"
        assert spells["q"].tooltip


    def test_values_use_each_slots_ranks(self, veigar_spells):
        assert veigar_spells["r"].values.values["BaseDamage"] == "by_rank(175, 250, 325)"
        assert veigar_spells["passive"].values.values["APPerStack"] == "1"


    def test_wiki_template_per_slot(self, veigar_spells):
        assert veigar_spells["q"].wiki.title == "Template:Data Veigar/Baleful Strike"
        assert veigar_spells["passive"].wiki.title == "Template:Data Veigar/Phenomenal Evil Power"


    def test_missing_wiki_blocks_nothing(self):
        spells = loaded_spells(raw_champion("Veigar"), VEIGAR_RANKS)

        assert spells["q"].wiki is None
        assert spells["q"].values.values


class TestBuildChampion():

    @pytest.fixture
    def veigar(self):
        return build_champion(raw_champion("Veigar", wiki=True), ChampionJson(**fixture("veigar.ddragon.json")))


    def test_list_data_comes_from_data_dragon(self, veigar):
        assert (veigar.key, veigar.name, veigar.champion_id) == ("45", "Veigar", "Veigar")
        assert veigar.resource_type == ResourceType.MANA
        assert [veigar.q.maxrank, veigar.r.maxrank] == [5, 3]
        assert veigar.image.full == "Veigar.png"
        assert veigar.r.image.full == "VeigarR.png"


    def test_stats_and_values_come_from_cdragon(self, veigar):
        assert veigar.hp == champion_stats(fixture("veigar.bin.json"))["hp"]
        assert veigar.q.values["BaseDamage"] == "by_rank(80, 120, 160, 200, 240)"
        assert "@TotalDamage@" in veigar.q.tooltip
        assert veigar.passive.values["APPerStack"] == "1"


    def test_names_come_from_cdragon(self):
        entry = ChampionJson(**fixture("veigar.ddragon.json"))
        entry.passive.name = entry.spells[0].name = "Data Dragon name"

        veigar = build_champion(raw_champion("Veigar"), entry)

        assert [veigar.passive.name, veigar.q.name] == ["Phenomenal Evil Power", "Baleful Strike"]


    def test_patch_comes_from_the_raw_data(self, veigar):
        assert veigar.patch == "16.23.1"


    def test_abilities_start_with_the_default_structure_and_no_rules(self, veigar):
        assert (veigar.q.cost, veigar.q.cooldown) == ("mana", "cooldownTime")
        assert veigar.q.stages == [] and veigar.q.rules == []
        assert not veigar.validated and not veigar.q.validated


    def test_missing_cdragon_name_falls_back_to_data_dragon(self):
        raw = raw_champion("Veigar")
        raw.strings = {}

        veigar = build_champion(raw, ChampionJson(**fixture("veigar.ddragon.json")))

        assert veigar.q.name == "Baleful Strike"
        assert veigar.passive.name == "Phenomenal Evil Power"


def champion_data(champion_id: str) -> dict:
    return parse_champion_data((CDRAGON / "champion_data.lua").read_text(encoding="utf-8"))[champion_id]


def veigar_with_champion_data():
    raw = raw_champion("Veigar")
    raw.champion_data = champion_data("Veigar")
    return build_champion(raw, ChampionJson(**fixture("veigar.ddragon.json")))


class TestWikiCrossCheck():

    def test_last_changed_is_our_patch_format(self):
        assert veigar_with_champion_data().last_changed == "16.7.1"  # wiki: V26.07


    def test_no_champion_data_no_last_change(self):
        assert build_champion(raw_champion("Veigar"), ChampionJson(**fixture("veigar.ddragon.json"))).last_changed is None


    def test_matching_champion_has_no_mismatches(self):
        assert wiki_mismatches(veigar_with_champion_data(), champion_data("Veigar")) == []


    def test_stats_are_compared_in_our_units(self):
        veigar = veigar_with_champion_data()
        veigar.hp_regen *= 5  # the wiki has per 5 seconds, we per second

        assert wiki_mismatches(veigar, champion_data("Veigar")) == ["hp_regen: wiki 1.3, CDragon 6.5"]


    def test_windup_from_the_cast_offset(self):
        veigar = veigar_with_champion_data()
        veigar.attack_windup = 0.3

        assert wiki_mismatches(veigar, champion_data("Veigar")) == ["attack_windup: wiki 0.190937, CDragon 0.3"]  # 0.3 - 0.109


    def test_range_and_adaptive_type(self):
        veigar = veigar_with_champion_data()
        veigar.range_type, veigar.adaptive_type = RangeType.MELEE, AdaptiveType.PHYSICAL

        assert wiki_mismatches(veigar, champion_data("Veigar")) == [
            "range_type: wiki Ranged, CDragon Melee", "adaptive_type: wiki Magic, CDragon physical"]


    def test_found_a_real_difference(self):
        # Vayne's attack speed ratio: 0.67 in CDragon, the wiki has her base attack speed 0.658 (as of 2026-11-24).
        stats = champion_stats(fixture("vayne.bin.json"))
        vayne = veigar_with_champion_data().copy(update=stats)

        assert wiki_mismatches(vayne, champion_data("Vayne")) == ["attackspeed_ratio: wiki 0.658, CDragon 0.67"]


    def test_without_champion_data_nothing_is_compared(self):
        assert wiki_mismatches(veigar_with_champion_data(), {}) == []


class TestApplyLoaderPart():

    def test_overwrites_values_and_tooltips_only(self, load_champion, veigar_spells):
        veigar = load_champion("veigar")
        veigar.q.values = {"BaseDamage": "1"}
        rules_before = veigar.q.stages[0].rules
        w_cooldown = veigar.w.cooldown

        apply_loader_part(veigar, veigar_spells)

        assert veigar.q.values["BaseDamage"] == "by_rank(80, 120, 160, 200, 240)"
        assert veigar.q.tooltip == veigar_spells["q"].tooltip
        assert veigar.q.stages[0].rules == rules_before
        assert veigar.w.cooldown == w_cooldown


    def test_initial_structure_points_to_the_loaded_values(self, load_champion):
        ability = load_champion("veigar").q

        initial_structure(ability, {})

        assert (ability.cost, ability.cooldown) == ("mana", "cooldownTime")
        assert (ability.charges, ability.recharge) == ("0", "0")


    def test_initial_structure_points_to_loaded_charges(self, load_champion):
        ability = load_champion("veigar").q

        initial_structure(ability, {"maxAmmo": "2", "ammoRechargeTime": "by_rank(16, 14.5, 13, 11.5, 10)"})

        assert (ability.charges, ability.recharge) == ("maxAmmo", "ammoRechargeTime")


class TestChampionStats():
    # The fixtures were filled from the wiki; their base stats are still current for these three.
    STATS = ["hp", "hp_per_lvl", "ad", "ad_per_lvl", "mana", "mana_per_lvl", "movementspeed", "armor", "armor_per_lvl", "mr",
             "mr_per_lvl", "attackrange", "hp_regen", "hp_regen_per_lvl", "mana_regen", "mana_regen_per_lvl", "attackspeed",
             "attackspeed_ratio", "attackspeed_per_lvl", "crit_damage", "attack_windup", "missile_speed", "range_type",
             "adaptive_type"]

    @pytest.mark.parametrize("champion", ["veigar", "darius", "riven"])
    def test_match_the_wiki(self, load_champion, champion):
        stats = champion_stats(fixture(f"{champion}.bin.json"))
        expected = load_champion(champion)

        for name in self.STATS:
            assert stats[name] == pytest.approx(getattr(expected, name), abs=1e-4), name


    def test_windup_from_cast_and_total_time(self):
        # Vladimir: 0.3 s of 1.52 s
        assert champion_stats(fixture("vladimir.bin.json"))["attack_windup"] == pytest.approx(0.19737, abs=1e-5)


    def test_missing_cast_offset_is_the_default_zero(self):
        # Riot leaves out default values: Alistar, Fiddlesticks and Volibear have no offset, the wiki says 0.
        cdragon = fixture("veigar.bin.json")
        cdragon["Characters/Veigar/CharacterRecords/Root"]["basicAttack"] = {}

        assert champion_stats(cdragon)["attack_windup"] == 0.3


    def test_missile_of_a_named_attack_in_other_case(self):
        # Fiddlesticks: record `Fiddlesticks`, attack named in `mAttackName` as `FiddleSticksBasicAttack`.
        cdragon = fixture("veigar.bin.json")
        cdragon["Characters/Veigar/CharacterRecords/Root"]["basicAttack"] = {"mAttackName": "VEIGARBasicAttack"}

        assert champion_stats(cdragon)["missile_speed"] == 1500


    def test_missile_speed_of_accelerating_and_instant_attacks(self):
        cdragon = fixture("veigar.bin.json")
        spell = next(r for r in cdragon.values() if isinstance(r, dict) and r.get("mScriptName") == "VeigarBasicAttack")["mSpell"]
        spell["mMissileSpec"]["movementComponent"] = {"mInitialSpeed": 2000.0, "mMaxSpeed": 3000.0, "mAcceleration": -15000.0}
        assert champion_stats(cdragon)["missile_speed"] == 2000  # Ivern

        del spell["mMissileSpec"]
        spell["missileSpeed"] = 1000.0
        assert champion_stats(cdragon)["missile_speed"] == 0  # Thresh: no missile, the old field is stale


    def test_form_champion_is_ranged_only_with_a_missile(self):
        # Jayce and Nidalee both list Ranged and Melee; Jayce's record is his hammer.
        nidalee = fixture("nidalee.bin.json")
        assert champion_stats(nidalee)["range_type"] == RangeType.RANGED

        attack = next(r for r in nidalee.values() if isinstance(r, dict) and r.get("mScriptName") == "NidaleeBasicAttack")
        del attack["mSpell"]["mMissileSpec"]
        assert champion_stats(nidalee)["range_type"] == RangeType.MELEE


    def test_crit_damage_per_champion(self):
        # Ashe's crits deal no extra damage (1.0 in 16.21); everyone else has 2.0.
        cdragon = fixture("veigar.bin.json")
        cdragon["Characters/Veigar/CharacterRecords/Root"]["critDamageMultiplier"] = 1.0

        assert champion_stats(cdragon)["crit_damage"] == 1.0


    def test_windup_modifier_defaults_to_one(self):
        # The old loader divided it by 100 (fixtures: 0.01 and 0.005).
        assert champion_stats(fixture("veigar.bin.json"))["windup_modifier"] == 1.0
        assert champion_stats(fixture("darius.bin.json"))["windup_modifier"] == 0.5


def test_raw_strings_are_filtered_like_the_loader_does():
    # The fixtures were cut from the 32 MB table with champion_strings; this keeps them in sync with it.
    darius = raw_champion("Darius")

    assert champion_strings(darius.strings, darius.cdragon) == darius.strings
    assert "spell_dariusq_tooltip" in darius.strings
