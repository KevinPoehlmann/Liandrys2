import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.server.loader.lua import parse_lua_table
from src.server.loader.summonerspell_builder import (build_summonerspell, maps, patch_summonerspell, rift_spells,
                                                     spell_from_document, summoner_spell, wiki_mismatches)
from src.server.loader.summonerspell_source import spell_record, spell_strings
from src.server.models.change import patch_note
from src.server.models.enums import ChangeSource, Map
from src.server.models.json_validation import SummonerspellJson
from src.server.models.summonerspell import NewSummonerspell, RawSummonerspell


CDRAGON = Path(__file__).parent / "static" / "cdragon"
BUILD = "16.23.8406595+branch.releases-16-23.content.release"
SHARED = json.loads((CDRAGON / "summonerspells.bin.json").read_text(encoding="utf-8"))
STRINGS = json.loads((CDRAGON / "summonerspells.strings.json").read_text(encoding="utf-8"))["entries"]
SPELL_DATA = parse_lua_table((CDRAGON / "spell_data.lua").read_text(encoding="utf-8"))
IGNITE = Path(__file__).parent / "static" / "test_group" / "summonerspells" / "ignite.json"
WIKI_NAMES = {"SummonerDot": "Ignite", "SummonerSmite": "Smite", "SummonerFlash": "Flash"}


def entry(key: str = "SummonerDot", modes: list[str] | None = None) -> SummonerspellJson:
    """Data Dragon's list entry; only id, name, modes and image matter to the loader."""
    name = WIKI_NAMES[key]
    return SummonerspellJson(
        id=key, name=name, description="", tooltip="", maxrank=1, cooldown=[0], cooldownBurn="0", cost=[0],
        costBurn="0", datavalues={}, effect=[], effectBurn=[], vars=[], key="14", summonerLevel=1,
        modes=modes or ["CLASSIC", "ARAM", "BRAWL", "URF"], costType="", maxammo="-1", range=[600], rangeBurn="600",
        resource="",
        image={"full": f"{key}.png", "sprite": "spell0.png", "group": "spell", "x": 0, "y": 0, "w": 48, "h": 48})


def raw(key: str = "SummonerDot", record: dict | None = None, patch: str = "16.23.1") -> RawSummonerspell:
    record = record or spell_record(SHARED, key)
    return RawSummonerspell(key=key, patch=patch, build=BUILD, fetched_at=datetime(2026, 11, 26),
                            cdragon=record, strings=spell_strings(STRINGS, record),
                            spell_data=SPELL_DATA.get(WIKI_NAMES[key], {}))


def changed_record(key: str = "SummonerDot", **values: float) -> dict:
    """The spell's record with some DataValues set (an unknown name is added)."""
    record = copy.deepcopy(spell_record(SHARED, key))
    data_values = record["mSpell"]["DataValues"]
    for name, value in values.items():
        found = next((item for item in data_values if item["name"] == name), None)
        if found is None:
            found = {"name": name, "__type": "SpellDataValue"}
            data_values.append(found)
        found["values"] = [value] * 7
    return record


class TestSource():

    def test_finds_the_record_by_script_name(self):
        assert spell_record(SHARED, "SummonerSmite")["mScriptName"] == "SummonerSmite"

    def test_an_unknown_spell_is_an_error(self):
        with pytest.raises(KeyError):
            spell_record(SHARED, "SummonerUnknown")

    def test_keeps_only_the_spells_own_strings(self):
        strings = spell_strings(STRINGS, spell_record(SHARED, "SummonerDot"))
        assert {key.lower() for key in strings} == {"spell_summonerdot_name", "spell_summonerdot_tooltip",
                                                    "spell_summonerdot_summary"}


class TestBuild():

    def test_ignite_gets_its_values_and_tooltip(self):
        spell = build_summonerspell(raw(), entry())

        ability = spell.ability
        assert (spell.key, spell.name, spell.patch, ability.name) == ("SummonerDot", "Ignite", "16.23.1", "Ignite")
        assert ability.values["DamagePerSecond"] == "TooltipTrueDamageCalculation * InverseDuration"
        assert ability.values["TooltipTrueDamageCalculation"].startswith("by_level(70, 90, 110, 130, 150, 175")
        assert "@TooltipTrueDamageCalculation@" in ability.tooltip
        assert (ability.cooldown, ability.cost, ability.charges) == ("cooldownTime", "0", "0")
        assert not spell.validated

    def test_smite_gets_charges(self):
        ability = build_summonerspell(raw("SummonerSmite"), entry("SummonerSmite")).ability

        assert (ability.charges, ability.recharge) == ("maxAmmo", "ammoRechargeTime")
        assert (ability.values["maxAmmo"], ability.values["ammoRechargeTime"]) == ("2", "90")

    def test_maps_come_from_data_dragons_modes(self):
        assert maps(["CLASSIC", "ARAM", "BRAWL", "URF", "SWIFTPLAY"]) == [Map.SR, Map.HA, Map.BR, Map.SP]

    def test_only_summoners_rift_spells_are_loaded(self):
        clarity = entry("SummonerFlash", modes=["ARAM", "KIWI"])
        assert rift_spells([entry(), clarity]) == [entry()]


class TestWikiMismatches():

    def test_real_data_matches(self):
        for key in WIKI_NAMES:
            assert wiki_mismatches(build_summonerspell(raw(key), entry(key)), raw(key).spell_data) == []

    def test_a_different_cooldown_is_reported(self):
        spell = build_summonerspell(raw(), entry())
        assert wiki_mismatches(spell, {"cooldown": "210"}) == ["cooldownTime: wiki 210, CDragon 180"]

    def test_text_is_not_compared(self):
        spell = build_summonerspell(raw(), entry())
        assert wiki_mismatches(spell, {"cooldown": "15 ({{sti|cd|reduced}} by 2)"}) == []


class TestPatch():

    @pytest.fixture
    def ignite(self):
        """Last patch's Ignite: the test group's, entered by hand with Riot's names and validated."""
        spell = NewSummonerspell.parse_obj(json.loads(IGNITE.read_text(encoding="utf-8")))
        spell.patch = "16.22.1"
        return spell

    def patched(self, ignite, record=None, notes=None):
        return patch_summonerspell(ignite, summoner_spell(raw(patch="16.22.1")), raw(record=record), entry(), notes or [])

    def test_nothing_changed_keeps_everything(self, ignite):
        result = self.patched(ignite)

        assert result.summonerspell.patch == "16.23.1"
        assert result.summonerspell.validated and result.unvalidated == []
        assert result.summonerspell.changes == []

    def test_only_numbers_changing_stays_validated(self, ignite):
        result = self.patched(ignite, changed_record(GrievousAmount=0.6))

        spell = result.summonerspell
        assert spell.validated
        assert [(change.source, change.text) for change in spell.changes] == [(ChangeSource.DATA, "GrievousAmount: 0.4 ⇒ 0.6")]
        assert spell.ability.values["GrievousAmount"] == "0.6"

    def test_a_new_value_unvalidates(self, ignite):
        result = self.patched(ignite, changed_record(ExtraDamage=10))

        assert not result.summonerspell.validated
        assert result.unvalidated == ["new values: ExtraDamage"]

    def test_a_used_value_that_is_gone_unvalidates(self, ignite):
        record = copy.deepcopy(spell_record(SHARED, "SummonerDot"))
        record["mSpell"]["DataValues"] = [value for value in record["mSpell"]["DataValues"]
                                          if value["name"] != "GrievousAmount"]

        result = self.patched(ignite, record)

        assert "GrievousAmount is gone" in result.unvalidated

    def test_patch_notes_without_data_unvalidate(self, ignite):
        result = self.patched(ignite, notes=[patch_note("Now also slows")])

        assert result.unvalidated == ["named in the patch notes only"]
        assert [change.text for change in result.summonerspell.changes] == ["Now also slows"]

    def test_patch_notes_with_data_stay_validated(self, ignite):
        result = self.patched(ignite, changed_record(GrievousAmount=0.6), [patch_note("Grievous Wounds 40% ⇒ 60%")])

        assert result.summonerspell.validated
        assert [change.source for change in result.summonerspell.changes] == [ChangeSource.DATA, ChangeSource.PATCH_NOTES]

    def test_an_unvalidated_spell_reports_no_reasons(self, ignite):
        ignite.validated = False
        assert self.patched(ignite, changed_record(ExtraDamage=10)).unvalidated == []

    def test_the_fallback_compares_the_stored_values(self, ignite):
        old = spell_from_document(ignite)
        result = patch_summonerspell(ignite, old, raw(record=changed_record(GrievousAmount=0.6)), entry(), [])

        assert [change.text for change in result.summonerspell.changes] == ["GrievousAmount: 0.4 ⇒ 0.6"]
