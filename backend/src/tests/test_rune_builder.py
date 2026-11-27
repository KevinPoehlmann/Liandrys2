import copy
import json
from datetime import datetime
from pathlib import Path

import pytest
from bson import ObjectId

from src.server.loader.champion_source import parse_wiki_pages
from src.server.loader.rune_builder import (RuneEntry, build_rune, loaded_rune, patch_rune, rune_from_document,
                                            shard_entries, tree_entries, unknown_shard, wiki_mismatches)
from src.server.loader.rune_source import WIKI_DATA, load_raw_rune, perk_records, rune_strings
from src.server.models.champion import WikiTemplate
from src.server.models.change import patch_note
from src.server.models.enums import ChangeSource, Stat
from src.server.models.json_validation import RuneTreeJson
from src.server.models.request import Rank
from src.server.models.rune import NewRune, RawRune, Rune
from src.server.simulation.character import Character


CDRAGON = Path(__file__).parent / "static" / "cdragon"
BUILD = "16.23.8406595+branch.releases-16-23.content.release"
PERKS = json.loads((CDRAGON / "runes.bin.json").read_text(encoding="utf-8"))
STRINGS = json.loads((CDRAGON / "runes.strings.json").read_text(encoding="utf-8"))
TREES = [RuneTreeJson(**tree) for tree in json.loads((CDRAGON / "runes.ddragon.json").read_text(encoding="utf-8"))]
WIKI = json.loads((CDRAGON / "runes.wiki.json").read_text(encoding="utf-8"))
ELECTROCUTE = Path(__file__).parent / "static" / "test_group" / "runes" / "electrocute.json"
ELECTROCUTE_ID, CONQUEROR_ID, DEMOLISH_ID, ADAPTIVE_ID, HEALTH_SCALING_ID = 8112, 8010, 8446, 5008, 5001


def entries() -> dict[tuple, RuneEntry]:
    return {entry.key: entry for entry in tree_entries(TREES) + shard_entries(PERKS, STRINGS)}


def entry(rune_id: int = ELECTROCUTE_ID, row: int | None = None) -> RuneEntry:
    return entries()[(rune_id, row)]


def raw(rune_id: int = ELECTROCUTE_ID, record: dict | None = None, patch: str = "16.23.1",
        wiki_name: str | None = "Electrocute") -> RawRune:
    records = perk_records(PERKS) | ({rune_id: record} if record else {})
    pages = parse_wiki_pages(WIKI, [WIKI_DATA.format("Electrocute"), "Electrocute"])
    return load_raw_rune(rune_id, wiki_name, patch, BUILD, records, STRINGS, pages)


def changed_record(rune_id: int = ELECTROCUTE_ID, **amounts: float) -> dict:
    """The perk's record with some script numbers set (an unknown name is added)."""
    record = copy.deepcopy(perk_records(PERKS)[rune_id])
    record["mScript"]["mSpellScriptData"]["mEffectAmount"].update(amounts)
    return record


def stored_electrocute() -> NewRune:
    return NewRune.parse_obj(json.loads(ELECTROCUTE.read_text(encoding="utf-8")) | {"patch": "16.22.1"})


class TestEntries():

    def test_tree_runes_keep_data_dragons_place(self):
        electrocute, conqueror = entry(ELECTROCUTE_ID), entry(CONQUEROR_ID)

        assert (electrocute.tree, electrocute.tree_id, electrocute.row, electrocute.slot) == ("Domination", 8100, 0, 0)
        assert (conqueror.tree, conqueror.row, conqueror.slot) == ("Precision", 0, 3)
        assert electrocute.image == "electrocute.png"


    def test_shards_come_in_three_rows_from_cdragon(self):
        shards = [found for found in entries().values() if found.is_shard]

        assert [(shard.row, shard.slot, shard.name) for shard in shards] == [
            (0, 0, "Adaptive Force (Offense)"), (0, 1, "Attack Speed (Offense)"), (0, 2, "Ability Haste (Offense)"),
            (1, 0, "Adaptive Force (Flex)"), (1, 1, "Move Speed (Flex)"), (1, 2, "Health Scaling (Flex)"),
            (2, 0, "Health (Defense)"), (2, 1, "Tenacity and Slow Resist (Defense)"), (2, 2, "Health Scaling (Defense)")]
        assert {shard.tree_id for shard in shards} == {0}


    def test_a_shard_in_two_rows_has_two_keys(self):
        assert entry(ADAPTIVE_ID, 0).key != entry(ADAPTIVE_ID, 1).key
        assert entry(ELECTROCUTE_ID).key == (ELECTROCUTE_ID, None)


class TestSource():

    def test_strings_include_the_texts_a_text_includes(self):
        # Electrocute's tooltip names the adaptive damage keyword, Dark Harvest's {{perk_substring_..._@f2@}} its parts.
        strings = rune_strings(STRINGS, perk_records(PERKS)[ELECTROCUTE_ID])

        assert "perk_tooltip_electrocute" in strings
        assert "perk_displayname_electrocute" in strings
        assert all(key.startswith(("perk_", "buff_")) for key in strings)


    def test_included_text_with_a_placeholder_matches_by_prefix(self):
        strings = {"perk_tooltip_x": "deals {{perk_substring_xadaptive_@f2@}}",
                   "perk_substring_xadaptive_0": "physical", "perk_substring_xadaptive_1": "magic", "other": ""}

        found = rune_strings(strings, {"mTooltipNameLocalizationKey": "perk_tooltip_X"})

        assert set(found) == {"perk_tooltip_x", "perk_substring_xadaptive_0", "perk_substring_xadaptive_1"}


    def test_raw_data_has_the_record_texts_and_wiki_pages(self):
        found = raw()

        assert found.cdragon["mPerkName"] == "Electrocute"
        assert found.wiki_data.title == "Template:Rune data Electrocute"
        assert "== Notes ==" in found.wiki.text


    def test_a_shard_has_no_wiki_pages(self):
        found = raw(ADAPTIVE_ID, wiki_name=None)

        assert (found.wiki_data, found.wiki) == (None, None)


    def test_unknown_rune_is_an_error(self):
        with pytest.raises(KeyError):
            raw(9999)


    def test_wiki_pages_follow_normalization_and_redirects(self):
        response = {"query": {
            "normalized": [{"from": "Template:Rune_data_Aery", "to": "Template:Rune data Aery"}],
            "redirects": [{"from": "Template:Rune data Aery", "to": "Template:Rune data Summon Aery"}],
            "pages": [{"title": "Template:Rune data Summon Aery", "revisions": [{"revid": 7, "slots": {"main": {"content": "x"}}}]},
                      {"title": "Missing", "missing": True}]}}

        pages = parse_wiki_pages(response, ["Template:Rune_data_Aery", "Missing"])

        assert list(pages) == ["Template:Rune_data_Aery"]
        assert (pages["Template:Rune_data_Aery"].title, pages["Template:Rune_data_Aery"].revision_id) == (
            "Template:Rune data Summon Aery", 7)


class TestBuild():

    def test_values_and_tooltip_go_on_the_passive(self):
        rune = build_rune(raw(), entry())

        assert rune.passive.values["TotalDamage"].startswith("by_level(70, 80, 90")
        assert rune.passive.values["TotalDamage"].endswith("+ APRatio * ap + BonusADRatio * bonus_ad")
        assert "@TotalDamage@" in rune.passive.tooltip
        assert (rune.name, rune.passive.name, rune.tree_id) == ("Electrocute", "Electrocute", 8100)


    def test_a_tree_rune_starts_unvalidated(self):
        rune = build_rune(raw(), entry())

        assert not rune.validated and not rune.passive.rules


    def test_melee_and_ranged_values_translate(self):
        # Demolish picks its damage by range type (IsMeleeCastRequirement).
        rune = build_rune(raw(DEMOLISH_ID, wiki_name=None), entry(DEMOLISH_ID))

        assert rune.passive.values["DamageCalc"].endswith("if 1 - ranged > 0 else h_4e3f20aa")


    @pytest.mark.parametrize(("rune_id", "row", "stat", "formula"), [
        (ADAPTIVE_ID, 0, Stat.AF, "StatGain2"),
        (HEALTH_SCALING_ID, 1, Stat.HP, "StatGainMin + (StatGainMax - StatGainMin) * (level - 1) / 17"),
        (5005, 0, Stat.ATTACKSPEED_P, "StatGain / 100"),
    ])
    def test_a_shard_gets_its_stats_and_starts_validated(self, rune_id, row, stat, formula):
        rune = build_rune(raw(rune_id, wiki_name=None), entry(rune_id, row))

        assert [(modifier.stat, modifier.formula) for modifier in rune.passive.stats] == [(stat, formula)]
        assert rune.validated


    @pytest.mark.parametrize(("level", "bonus"), [(1, 10), (6, 10 + 170 * 5 / 17), (18, 180)])
    def test_health_scaling_grows_with_level_in_the_simulation(self, load_champion, level, bonus):
        shard = build_rune(raw(HEALTH_SCALING_ID, wiki_name=None), entry(HEALTH_SCALING_ID, 1))
        rank = Rank(q=0, w=0, e=0, r=0)
        plain = Character(load_champion("riven"), level, rank, [])

        riven = Character(load_champion("riven"), level, rank, [], runes=[Rune(id=ObjectId(), **shard.dict())])

        assert riven.get_stat(Stat.HP) - plain.get_stat(Stat.HP) == pytest.approx(bonus)


    def test_an_unknown_shard_has_no_stats(self):
        record = changed_record(ADAPTIVE_ID) | {"mPerkName": "Lethality"}
        found = raw(ADAPTIVE_ID, record, wiki_name=None)

        rune = build_rune(found, entry(ADAPTIVE_ID, 0))

        assert unknown_shard(found)
        assert not rune.passive.stats and not rune.validated


    def test_wiki_cooldown_matches(self):
        assert wiki_mismatches(build_rune(raw(), entry()), raw()) == []


    def test_wiki_cooldown_mismatch_is_reported(self):
        found = raw(record=changed_record(Cooldown=25.0, CooldownMin=25.0))

        assert wiki_mismatches(build_rune(found, entry()), found) == ["cooldown: wiki 20, CDragon Cooldown 25, CooldownMin 25"]


    def test_wiki_cooldown_that_is_text_is_not_compared(self):
        found = raw()
        found.wiki_data = WikiTemplate(title="t", revision_id=1, text="|cooldown = {{pp|20 to 10}}\n")

        assert wiki_mismatches(build_rune(found, entry()), found) == []


class TestPatch():

    def test_numbers_change_and_the_hand_made_part_stays(self):
        old = stored_electrocute()
        new_raw = raw(record=changed_record(WindowDuration=4.0))

        result = patch_rune(old, loaded_rune(raw(patch="16.22.1")), new_raw, entry(), [])

        rune = result.rune
        assert (rune.patch, rune.validated, result.unvalidated) == ("16.23.1", True, [])
        assert rune.passive.values["WindowDuration"] == "4"
        assert rune.passive.rules == old.passive.rules
        assert [(change.source, change.text) for change in rune.changes] == [(ChangeSource.DATA, "WindowDuration: 3 ⇒ 4")]


    def test_a_used_value_that_is_gone_unvalidates(self):
        record = changed_record()
        del record["mScript"]["mSpellScriptData"]["mEffectAmount"]["WindowDuration"]

        result = patch_rune(stored_electrocute(), loaded_rune(raw(patch="16.22.1")), raw(record=record), entry(), [])

        assert not result.rune.validated
        assert result.unvalidated == ["WindowDuration is gone"]


    def test_patch_notes_only_unvalidate(self):
        notes = [patch_note("Damage type logic fixed")]

        result = patch_rune(stored_electrocute(), loaded_rune(raw(patch="16.22.1")), raw(), entry(), notes)

        assert result.unvalidated == ["named in the patch notes only"]
        assert result.rune.changes == notes


    def test_moving_rows_is_a_change_line_but_keeps_validation(self):
        moved = RuneEntry(ELECTROCUTE_ID, "Electrocute", "Domination", 8100, 0, 2, "electrocute.png")

        result = patch_rune(stored_electrocute(), loaded_rune(raw(patch="16.22.1")), raw(), moved, [])

        assert (result.rune.slot, result.rune.validated) == (2, True)
        assert [change.text for change in result.rune.changes] == ["row, slot: 0, 0 ⇒ 0, 2"]


    def test_a_shard_value_its_stats_use_that_is_gone_unvalidates(self):
        old = build_rune(raw(ADAPTIVE_ID, wiki_name=None), entry(ADAPTIVE_ID, 0))
        record = changed_record(ADAPTIVE_ID)
        del record["mScript"]["mSpellScriptData"]["mEffectAmount"]["StatGain2"]

        result = patch_rune(old, loaded_rune(raw(ADAPTIVE_ID, wiki_name=None)),
                            raw(ADAPTIVE_ID, record, wiki_name=None), entry(ADAPTIVE_ID, 0), [])

        assert result.unvalidated == ["StatGain2 is gone"]


    def test_fallback_compares_with_the_stored_values(self):
        stored = stored_electrocute()

        loaded = rune_from_document(stored)

        assert loaded.values.values == stored.passive.values
        assert loaded.tooltip == stored.passive.tooltip
