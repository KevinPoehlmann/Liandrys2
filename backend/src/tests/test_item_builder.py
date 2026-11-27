import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.server.loader.item_builder import (build_item, item_from_document, loaded_item, masterwork, patch_item,
                                            rift_items, unknown_stat_fields, wiki_mismatches)
from src.server.loader.item_source import item_record, item_spell, item_strings, resolved
from src.server.loader.lua import parse_lua_table
from src.server.models.change import patch_note
from src.server.models.enums import ActiveType, ChangeSource, ItemClass, Map, Stat
from src.server.models.item import NewItem, RawItem
from src.server.models.json_validation import ItemJson


CDRAGON = Path(__file__).parent / "static" / "cdragon"
TEST_GROUP = Path(__file__).parent / "static" / "test_group" / "items"
BUILD = "16.23.8418428+branch.releases-16-23.content.release"
ITEMS = json.loads((CDRAGON / "items.bin.json").read_text(encoding="utf-8"))
SHARED = json.loads((CDRAGON / "items.shared.bin.json").read_text(encoding="utf-8"))
STRINGS = json.loads((CDRAGON / "items.strings.json").read_text(encoding="utf-8"))["entries"]
DDRAGON = json.loads((CDRAGON / "items.ddragon.json").read_text(encoding="utf-8"))["data"]
ITEM_DATA_ENTRIES = parse_lua_table((CDRAGON / "item_data.lua").read_text(encoding="utf-8"))
ITEM_DATA = {str(entry["id"]): resolved(entry, ITEM_DATA_ENTRIES) for entry in ITEM_DATA_ENTRIES.values()}
SHEEN, GUNBLADE, THORNMAIL, TITANIC, POTION, MURAMANA = "3057", "3146", "3075", "3748", "2003", "3042"


def entry(item_id: str) -> ItemJson:
    return ItemJson(**DDRAGON[item_id])


def raw(item_id: str, record: dict | None = None, item_data: dict | None = None, patch: str = "16.23.1") -> RawItem:
    record = record or item_record(ITEMS, item_id)
    return RawItem(item_id=item_id, patch=patch, build=BUILD, fetched_at=datetime(2026, 11, 27), cdragon=record,
                   active=item_spell(record, ITEMS, SHARED), strings=item_strings(STRINGS, item_id),
                   item_data=ITEM_DATA.get(item_id, {}) if item_data is None else item_data)


def stored(name: str) -> NewItem:
    return NewItem.parse_obj(json.loads((TEST_GROUP / f"{name}.json").read_text(encoding="utf-8")))


def changed_record(item_id: str, **values: float) -> dict:
    """The item's record with some data values set (an unknown name is added)."""
    record = copy.deepcopy(item_record(ITEMS, item_id))
    for name, value in values.items():
        found = next((item for item in record["mDataValues"] if item["mName"] == name), None)
        if found is None:
            found = {"mName": name, "__type": "ItemDataValue"}
            record["mDataValues"].append(found)
        found["mValue"] = value
    return record


class TestSource():

    def test_inherited_fields_come_from_the_named_item(self):
        muramana = ITEM_DATA[MURAMANA]
        assert muramana["stats"] == {"ad": 35, "ah": 15, "mana": 1000}  # ad and ah from Manamune
        assert muramana["effects"]["pass"]["name"] == "Awe"
        assert muramana["modes"]["classic sr 5v5"]

    def test_an_unknown_reference_is_nothing(self):
        assert resolved({"stats": "=>Missing"}, {}) == {"stats": None}

    def test_an_unknown_item_is_an_error(self):
        with pytest.raises(KeyError):
            item_record(ITEMS, "9999")

    def test_finds_the_named_spell_in_either_file(self):
        assert item_spell(item_record(ITEMS, TITANIC), ITEMS, SHARED)["mScriptName"] == "3748Active"
        assert item_spell(item_record(ITEMS, GUNBLADE), ITEMS, SHARED)["mScriptName"] == "HextechGunbladeSpell"
        assert item_spell(item_record(ITEMS, SHEEN), ITEMS, SHARED) is None  # names no spell

    def test_keeps_only_the_items_own_strings(self):
        strings = item_strings(STRINGS, SHEEN)
        assert strings and all("_3057_" in key.lower() for key in strings)


class TestBuild():

    def test_gunblade_gets_stats_values_and_its_active(self):
        item = build_item(raw(GUNBLADE), entry(GUNBLADE))

        assert (item.name, item.patch, item.gold, item.class_) == ("Hextech Gunblade", "16.23.1", 3000,
                                                                   ItemClass.LEGENDARY)
        assert item.stats == {Stat.AD: 40, Stat.AP: 80, Stat.OMNIVAMP_P: 0.1}
        assert item.values["ActiveDamage"].startswith("by_level(175, ")
        assert item.values["ActiveDamage"].endswith(", 253, 257.588235294, 262.176470588) + 0.3 * ap")
        assert (item.active.name, item.active.type_, item.active.unique) == ("Lightning Bolt", ActiveType.ACTIVE, True)
        assert item.active.cooldown == "Cooldown"  # the item's data value: 60, the spell's own cooldown is 40
        assert "@ActiveDamage@" in item.tooltip
        assert item.passives == []
        assert Map.SR in item.maps

    def test_sheen_gets_its_unique_passive_and_group(self):
        item = build_item(raw(SHEEN), entry(SHEEN))

        assert item.class_ == ItemClass.EPIC
        assert [(passive.name, passive.unique) for passive in item.passives] == [("Spellblade", True)]
        assert item.values["SpellbladeDamage"] == "base_ad"
        assert item.limitations == "Limited to 1 Spellblade item."
        assert item.masterwork == {}  # only legendary items

    def test_thornmail_gets_its_masterwork_bonus(self):
        item = build_item(raw(THORNMAIL), entry(THORNMAIL))

        assert item.masterwork == {Stat.ARMOR: 25, Stat.HP: 185}

    def test_only_items_without_effects_start_validated(self):
        assert not build_item(raw(THORNMAIL), entry(THORNMAIL)).validated  # Thorns isn't entered yet
        assert build_item(raw(THORNMAIL, item_data=ITEM_DATA[THORNMAIL] | {"effects": {}}), entry(THORNMAIL)).validated

    def test_the_ranged_multiplier_halves_titanic_for_ranged(self):
        item = build_item(raw(TITANIC), entry(TITANIC))

        assert item.values["OnHitDamageCalc"] == "(0.01 * max_hp) * (0.5 if ranged > 0 else 1)"

    def test_a_potion_gets_a_consume_active(self):
        item = build_item(raw(POTION), entry(POTION))

        assert (item.active.name, item.active.type_, item.class_) == ("Health Potion", ActiveType.CONSUME,
                                                                      ItemClass.CONSUMABLE)
        assert item.limitations == "Limited to 5 at a time."

    def test_inherited_effects_and_limit(self):
        item = build_item(raw(MURAMANA), entry(MURAMANA))

        assert [passive.name for passive in item.passives] == ["Awe", "Shock"]
        assert item.limitations == "Limited to 1 Manamune."

    def test_without_the_wiki_module_only_cdragon_and_data_dragon_count(self):
        item = build_item(raw(GUNBLADE, item_data={}), entry(GUNBLADE))

        assert (item.class_, item.active, item.stats[Stat.AP]) == (ItemClass.NONE, None, 80)

    def test_the_test_group_matches_the_wiki(self):
        for item_id in ("3057", "3146", "3075", "3153", "6676"):
            item = build_item(raw(item_id), entry(item_id))
            assert wiki_mismatches(item, raw(item_id).item_data) == []
            assert unknown_stat_fields(item_record(ITEMS, item_id)) == []

    def test_a_differing_stat_and_cooldown_are_mismatches(self):
        item = build_item(raw(GUNBLADE, changed_record(GUNBLADE, Cooldown=40)), entry(GUNBLADE))
        item.stats[Stat.AP] = 90

        assert wiki_mismatches(item, ITEM_DATA[GUNBLADE]) == ["ap: wiki 80, CDragon 90", "Cooldown: wiki 60, CDragon 40"]

    def test_an_unmapped_stat_field_is_reported(self):
        record = item_record(ITEMS, SHEEN) | {"mFlatArmorPenetrationMod": 10.0}

        assert unknown_stat_fields(record) == ["mFlatArmorPenetrationMod"]


class TestMasterwork():

    @pytest.mark.parametrize("stats, bonus", [
        ({Stat.AP: 130}, {Stat.AP: 50}),  # Rabadon's Deathcap: all 1000 gold in AP
        ({Stat.AD: 35, Stat.ABILITY_HASTE: 15, Stat.MANA: 1000}, {Stat.AD: 14, Stat.ABILITY_HASTE: 16}),  # no mana
        ({Stat.ATTACKSPEED_P: 0.25, Stat.MOVESPEED_P: 0.04}, {Stat.ATTACKSPEED_P: 0.33}),  # whole percents
        ({Stat.HP: 400}, {Stat.HP: 375}),
        ({Stat.HP: 300, Stat.AD: 40, Stat.ABILITY_HASTE: 20, Stat.ATTACKSPEED_P: 0.3},
         {Stat.HP: 90, Stat.AD: 7, Stat.ABILITY_HASTE: 8, Stat.ATTACKSPEED_P: 0.08}),
        ({Stat.LETHALITY: 18}, {Stat.HP: 375}),  # nothing upgradeable: all health
    ])
    def test_shares_1000_gold_and_rounds_down(self, stats, bonus):
        assert masterwork(stats) == bonus


class TestRiftItems():

    def test_the_wiki_module_decides(self):
        items = [(item_id, entry(item_id)) for item_id in (SHEEN, "322065")]
        item_data = {SHEEN: ITEM_DATA[SHEEN], "322065": {"modes": {"swiftplay": True}}}

        assert [item_id for item_id, _ in rift_items(items, item_data)] == [SHEEN]

    def test_champion_upgrades_bought_without_gold_are_left_out(self):
        upgrade, black_spear = entry(SHEEN).copy(deep=True), entry(SHEEN).copy(deep=True)
        upgrade.gold.purchasable = False  # Gangplank's Fire at Will costs Silver Serpents
        items = [("3901", upgrade), ("3599", black_spear)]
        rift = {"modes": {"classic sr 5v5": True}}
        item_data = {"3901": {**rift, "champion": ["Gangplank"]}, "3599": {**rift, "champion": ["Kalista", "Sylas"]}}

        assert [item_id for item_id, _ in rift_items(items, item_data)] == ["3599"]

    def test_without_the_module_data_dragon_decides(self):
        items = [(item_id, entry(item_id)) for item_id in (SHEEN, "322065")]  # Swiftplay's copy also lists map 11

        assert [item_id for item_id, _ in rift_items(items, {})] == [SHEEN]


class TestPatch():

    def test_unchanged_item_stays_validated(self):
        old = stored("thornmail")

        result = patch_item(old, loaded_item(raw(THORNMAIL, patch="16.22.1")), raw(THORNMAIL), entry(THORNMAIL), [])

        assert result.item.validated and result.unvalidated == []
        assert result.item.changes == []
        assert result.item.passives == old.passives  # the hand-made part stays

    def test_only_numbers_changing_keeps_the_validation(self):
        new = raw(THORNMAIL, changed_record(THORNMAIL, BaseDamage=25))

        result = patch_item(stored("thornmail"), loaded_item(raw(THORNMAIL)), new, entry(THORNMAIL), [])

        assert result.item.validated
        assert [(change.source, change.text) for change in result.item.changes] == [(ChangeSource.DATA,
                                                                                      "BaseDamage: 20 ⇒ 25")]

    def test_a_missing_name_a_rule_uses_unvalidates(self):
        record = copy.deepcopy(item_record(ITEMS, THORNMAIL))
        record["mDataValues"] = [value for value in record["mDataValues"] if value["mName"] != "GrievousDuration"]

        result = patch_item(stored("thornmail"), loaded_item(raw(THORNMAIL)), raw(THORNMAIL, record),
                            entry(THORNMAIL), [])

        assert not result.item.validated
        assert any("GrievousDuration" in reason for reason in result.unvalidated)

    def test_stat_and_gold_changes_are_lines_only(self):
        record = item_record(ITEMS, THORNMAIL) | {"mFlatArmorMod": 80.0}
        new_entry = entry(THORNMAIL).copy(update={"gold": entry(THORNMAIL).gold.copy(update={"total": 2500})})

        result = patch_item(stored("thornmail"), loaded_item(raw(THORNMAIL)), raw(THORNMAIL, record), new_entry, [])

        assert result.item.validated
        assert [change.text for change in result.item.changes] == ["armor: 75 ⇒ 80", "gold: 2450 ⇒ 2500"]
        assert result.item.masterwork == {Stat.ARMOR: 25, Stat.HP: 185}

    def test_patch_notes_only_unvalidates(self):
        notes = [patch_note("Thorns damage changed")]

        result = patch_item(stored("thornmail"), loaded_item(raw(THORNMAIL)), raw(THORNMAIL), entry(THORNMAIL), notes)

        assert not result.item.validated
        assert result.unvalidated == ["named in the patch notes only"]
        assert result.item.changes == notes

    def test_a_new_passive_gets_a_container(self):
        item_data = copy.deepcopy(ITEM_DATA[THORNMAIL])
        item_data["effects"]["pass2"] = {"name": "Spikes", "unique": True}

        result = patch_item(stored("thornmail"), loaded_item(raw(THORNMAIL)), raw(THORNMAIL, item_data=item_data),
                            entry(THORNMAIL), [])

        assert [passive.name for passive in result.item.passives] == ["Thorns", "Spikes"]
        assert result.unvalidated == ["new passive Spikes"]

    def test_a_removed_passive_keeps_its_container(self):
        item_data = copy.deepcopy(ITEM_DATA[THORNMAIL])
        item_data["effects"] = {}

        result = patch_item(stored("thornmail"), loaded_item(raw(THORNMAIL)), raw(THORNMAIL, item_data=item_data),
                            entry(THORNMAIL), [])

        assert [passive.name for passive in result.item.passives] == ["Thorns"]
        assert result.unvalidated == ["passive Thorns not in the wiki anymore"]

    def test_without_old_raw_data_the_stored_values_are_compared(self):
        old = stored("thornmail")

        result = patch_item(old, item_from_document(old), raw(THORNMAIL), entry(THORNMAIL), [])

        assert result.item.validated and result.item.changes == []
