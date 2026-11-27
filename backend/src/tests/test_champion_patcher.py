import copy
from datetime import datetime

import pytest

from src.server.loader.cdragon import field_hash
from src.server.loader.champion_builder import champion_stats, loaded_spells
from src.server.loader.champion_patcher import (_calculation_names, _note_lines, keep_earlier_changes,
                                                patch_champion, recorded_changes, spells_from_document, used_names)
from src.server.models.ability import ExtraAbility
from src.server.models.change import Change, patch_note
from src.server.models.enums import ChangeSource
from src.server.models.json_validation import ChampionJson
from src.server.models.rule import Buff
from src.tests.test_champion_builder import VEIGAR_RANKS, fixture, raw_champion


NEW_PATCH = "16.24.1"


def spell(cdragon: dict, script_name: str) -> dict:
    return next(record["mSpell"] for record in cdragon.values()
                if isinstance(record, dict) and record.get("mScriptName") == script_name)


def data_value(cdragon: dict, script_name: str, name: str) -> dict:
    return next(value for value in spell(cdragon, script_name)["DataValues"] if value["name"] == name)


@pytest.fixture
def old_raw():
    return raw_champion("Veigar")


@pytest.fixture
def new_raw(old_raw):
    raw = copy.deepcopy(old_raw)
    raw.patch = NEW_PATCH
    return raw


@pytest.fixture
def veigar(load_champion, old_raw):
    # In the database the old stats came from the old raw data; the fixture's were filled from the wiki.
    champion = load_champion("veigar").copy(update=champion_stats(old_raw.cdragon))
    for container in (champion, champion.passive, champion.q, champion.w, champion.e, champion.r):
        container.validated = True
    return champion


def patch(veigar, old_raw, new_raw, notes=None, old_spells=None):
    old_spells = old_spells or loaded_spells(old_raw, VEIGAR_RANKS)
    entry = ChampionJson(**fixture("veigar.ddragon.json"))
    return patch_champion(veigar, old_spells, new_raw, entry, notes or {})


def extra_ability(champion) -> ExtraAbility:
    return ExtraAbility(**champion.r.dict() | {"name": "Cougar Pounce", "validated": True}, key="pounce", rank_from="r")


def texts(container) -> list[str]:
    return [change.text for change in container.changes]


def damage_props(ability) -> list:
    return [action.props for stage in ability.stages for rule in stage.rules for action in rule.actions
            if "Damage" in str(getattr(action.props, "amount", ""))]


def hide_name(raw, script_name: str, name: str) -> str:
    """How the old patch looked while CommunityDragon only knew the name's hash."""
    hashed = f"{{{field_hash(name)}}}"
    data_value(raw.cdragon, script_name, name)["name"] = hashed
    for calculation in spell(raw.cdragon, script_name).get("mSpellCalculations", {}).values():
        for part in calculation.get("mFormulaParts", []):
            if part.get("mDataValue") == name:
                part["mDataValue"] = hashed
    return f"h_{field_hash(name)}"


class TestCopyForward():

    def test_unchanged_data_changes_nothing(self, veigar, old_raw, new_raw):
        result = patch(veigar, old_raw, new_raw)

        assert result.champion.patch == NEW_PATCH
        assert result.unvalidated == {}
        assert result.champion.validated
        assert not recorded_changes(result.champion)


    def test_hand_made_part_survives(self, veigar, old_raw, new_raw):
        champion = patch(veigar, old_raw, new_raw).champion

        assert champion.w.rules == veigar.w.rules
        assert champion.w.cooldown == veigar.w.cooldown


    def test_values_come_from_the_new_patch(self, veigar, old_raw, new_raw):
        champion = patch(veigar, old_raw, new_raw).champion

        assert champion.q.values == loaded_spells(new_raw, VEIGAR_RANKS)["q"].values.values


    def test_changes_hold_only_this_patch(self, veigar, old_raw, new_raw):
        veigar.q.changes = [Change(source=ChangeSource.PATCH_NOTES, text="from the last patch")]

        assert patch(veigar, old_raw, new_raw).champion.q.changes == []


HOTFIXED_AT = datetime(2026, 11, 22, 18, 0)


class TestHotfix():

    def test_keeps_the_lines_its_patch_brought(self, veigar, old_raw, new_raw):
        veigar.changes = [patch_note("Base health increased")]
        veigar.q.changes = [patch_note("Cooldown reduced")]
        data_value(new_raw.cdragon, "VeigarBalefulStrike", "BaseDamage")["values"][1] = 90

        champion = patch(veigar, old_raw, new_raw).champion
        keep_earlier_changes(champion, veigar, HOTFIXED_AT)

        assert texts(champion) == ["Base health increased"]
        assert texts(champion.q) == ["Cooldown reduced",
                                     "BaseDamage: by_rank(80, 120, 160, 200, 240) ⇒ by_rank(90, 120, 160, 200, 240)"]


    def test_a_line_seen_twice_is_kept_once(self, veigar, old_raw, new_raw):
        veigar.q.changes = [patch_note("Damage increased")]

        champion = patch(veigar, old_raw, new_raw, notes={"Baleful Strike": [patch_note("Damage increased")]}).champion
        keep_earlier_changes(champion, veigar, HOTFIXED_AT)

        assert texts(champion.q) == ["Damage increased"]


    def test_marks_only_the_new_lines_with_the_run(self, veigar, old_raw, new_raw):
        earlier_run = datetime(2026, 11, 21, 18, 0)
        veigar.q.changes = [patch_note("Cooldown reduced"), patch_note("Mana cost reduced").copy(
            update={"hotfix": earlier_run})]
        notes = {"Baleful Strike": [patch_note("Mana cost reduced"), patch_note("Range increased")]}

        champion = patch(veigar, old_raw, new_raw, notes=notes).champion
        keep_earlier_changes(champion, veigar, HOTFIXED_AT)

        assert [(change.text, change.hotfix) for change in champion.q.changes] == [
            ("Cooldown reduced", None), ("Mana cost reduced", earlier_run), ("Range increased", HOTFIXED_AT)]


    def test_recorded_changes_look_into_every_container(self, veigar):
        assert recorded_changes(veigar) == []
        veigar.e.changes = [patch_note("Radius increased")]
        assert recorded_changes(veigar) == [patch_note("Radius increased")]


class TestValidation():

    def test_only_numbers_stay_validated(self, veigar, old_raw, new_raw):
        data_value(new_raw.cdragon, "VeigarBalefulStrike", "BaseDamage")["values"][1] = 90

        champion = patch(veigar, old_raw, new_raw).champion

        assert champion.q.validated
        assert texts(champion.q) == ["BaseDamage: by_rank(80, 120, 160, 200, 240) ⇒ by_rank(90, 120, 160, 200, 240)"]
        assert champion.q.changes[0].source == ChangeSource.DATA


    def test_a_used_name_that_is_gone_unvalidates(self, veigar, old_raw, new_raw):
        # Veigar W's cooldown reads passive.DarkMatterCDRIncrement.
        data_value(new_raw.cdragon, "VeigarPassive", "DarkMatterCDRIncrement")["name"] = "Renamed"

        result = patch(veigar, old_raw, new_raw)

        assert not result.champion.w.validated
        assert "passive.DarkMatterCDRIncrement is gone" in result.unvalidated["Dark Matter"]
        assert "DarkMatterCDRIncrement: removed (was 0.1)" in texts(result.champion.passive)


    def test_a_new_name_unvalidates(self, veigar, old_raw, new_raw):
        spell(new_raw.cdragon, "VeigarEventHorizon")["DataValues"].append({"name": "NewMechanic", "values": [1] * 7})

        result = patch(veigar, old_raw, new_raw)

        assert result.unvalidated["Event Horizon"] == ["new values: NewMechanic"]
        assert not result.champion.validated


    def test_a_changed_tooltip_unvalidates(self, veigar, old_raw, new_raw):
        key = next(key for key in new_raw.strings if key.lower() == "spell_veigarbalefulstrike_tooltip")
        new_raw.strings[key] += " Now also stuns."

        result = patch(veigar, old_raw, new_raw)

        assert result.unvalidated["Baleful Strike"] == ["tooltip changed"]
        assert texts(result.champion.q) == ["Tooltip changed"]


    def test_a_restructured_calculation_used_by_name_follows(self, veigar, old_raw, new_raw):
        total = spell(new_raw.cdragon, "VeigarBalefulStrike")["mSpellCalculations"]["TotalDamage"]
        total["mFormulaParts"].append({"__type": "NumberCalculationPart", "mNumber": 10})

        champion = patch(veigar, old_raw, new_raw).champion

        assert champion.q.validated
        assert champion.q.values["TotalDamage"] == "BaseDamage + APRatio * ap + 10"
        assert texts(champion.q) == ["TotalDamage: BaseDamage + APRatio * ap ⇒ BaseDamage + APRatio * ap + 10"]


    def test_a_restructured_calculation_rebuilt_by_hand_unvalidates(self, veigar, old_raw, new_raw):
        for rule in (rule for stage in veigar.q.stages for rule in stage.rules):
            for action in rule.actions:
                if getattr(action.props, "amount", None) == "TotalDamage":
                    action.props.amount = "BaseDamage + APRatio * ap"
        total = spell(new_raw.cdragon, "VeigarBalefulStrike")["mSpellCalculations"]["TotalDamage"]
        total["mFormulaParts"].append({"__type": "NumberCalculationPart", "mNumber": 10})

        result = patch(veigar, old_raw, new_raw)

        assert result.unvalidated["Baleful Strike"] == ["TotalDamage changed its structure"]


    def test_a_used_calculation_the_translator_doesnt_know_unvalidates(self, veigar, old_raw, new_raw):
        total = spell(new_raw.cdragon, "VeigarBalefulStrike")["mSpellCalculations"]["TotalDamage"]
        total["mFormulaParts"].append({"__type": "SomethingNewCalculationPart"})

        result = patch(veigar, old_raw, new_raw)

        assert result.unvalidated["Baleful Strike"] == ["TotalDamage changed its structure"]
        assert texts(result.champion.q) == [
            "TotalDamage: BaseDamage + APRatio * ap ⇒ not translated: part type SomethingNewCalculationPart"]


    def test_named_in_the_patch_notes_only_unvalidates(self, veigar, old_raw, new_raw):
        result = patch(veigar, old_raw, new_raw, {"Baleful Strike": [patch_note("Now pierces")], "General": [patch_note("Splash art updated")]})

        assert result.unvalidated["Baleful Strike"] == ["named in the patch notes only"]
        assert result.champion.q.changes == [Change(source=ChangeSource.PATCH_NOTES, text="Now pierces")]
        assert texts(result.champion) == ["Splash art updated"]


    def test_an_extra_ability_is_backed_by_the_data_of_the_slot_it_ranks_with(self, veigar, old_raw, new_raw):
        # 16.21: Nidalee's Pounce damage changed in R's PounceDamage
        veigar.extra_abilities = [extra_ability(veigar)]
        data_value(new_raw.cdragon, "VeigarR", "BaseDamage")["values"][1] = 200

        result = patch(veigar, old_raw, new_raw, {"Cougar Pounce": [patch_note("Base damage reduced")]})

        assert result.champion.extra_abilities[0].validated
        assert texts(result.champion.extra_abilities[0]) == ["Base damage reduced"]


    def test_an_extra_ability_named_in_the_patch_notes_only_unvalidates(self, veigar, old_raw, new_raw):
        veigar.extra_abilities = [extra_ability(veigar)]
        data_value(new_raw.cdragon, "VeigarBalefulStrike", "BaseDamage")["values"][1] = 90

        result = patch(veigar, old_raw, new_raw, {"Cougar Pounce": [patch_note("Now pierces")]})

        assert result.unvalidated["Cougar Pounce"] == ["named in the patch notes only"]


    def test_two_part_abilities_match_either_name(self):
        # 26.21: Lee Sin's "Safeguard / Iron Will" appears as "Safeguard"
        notes = {"Safeguard": [patch_note("Cooldown increased")], "Iron Will": [patch_note("Bug fix")], "Tempest": [patch_note("Other")]}

        assert _note_lines(notes, "Safeguard / Iron Will") == [patch_note("Cooldown increased"), patch_note("Bug fix")]
        assert notes == {"Tempest": [patch_note("Other")]}


    def test_an_unvalidated_ability_stays_unvalidated(self, veigar, old_raw, new_raw):
        veigar.e.validated = False

        result = patch(veigar, old_raw, new_raw)

        assert not result.champion.e.validated
        assert not result.champion.validated


class TestRenames():

    def test_a_learned_name_is_a_rename(self, veigar, old_raw, new_raw):
        hashed = hide_name(old_raw, "VeigarBalefulStrike", "BaseDamage")

        result = patch(veigar, old_raw, new_raw)

        assert result.champion.q.validated
        assert texts(result.champion.q) == [f"{hashed}: renamed to BaseDamage"]


    def test_hand_made_formulas_follow_the_rename(self, veigar, old_raw, new_raw):
        hashed = hide_name(old_raw, "VeigarBalefulStrike", "BaseDamage")
        for props in damage_props(veigar.q):
            props.amount = f"{hashed} + APRatio * ap"

        result = patch(veigar, old_raw, new_raw)

        assert result.champion.q.validated
        assert {props.amount for props in damage_props(result.champion.q)} == {"BaseDamage + APRatio * ap"}


    def test_other_slots_follow_the_rename(self, veigar, old_raw, new_raw):
        hashed = hide_name(old_raw, "VeigarPassive", "DarkMatterCDRIncrement")
        veigar.w.cooldown = veigar.w.cooldown.replace("passive.DarkMatterCDRIncrement", f"passive.{hashed}")

        result = patch(veigar, old_raw, new_raw)

        assert result.champion.w.validated
        assert "passive.DarkMatterCDRIncrement * floor(" in result.champion.w.cooldown


    def test_a_learned_buff_name_is_a_rename(self, veigar, old_raw, new_raw):
        hashed = count_buff(old_raw, new_raw, "VeigarPhenomenalEvil")

        result = patch(veigar, old_raw, new_raw)

        assert result.champion.q.validated
        assert texts(result.champion.q) == [f"Buff {hashed}: renamed to VeigarPhenomenalEvil"]
        assert result.champion.q.values["TotalDamage"].endswith("+ stacks_VeigarPhenomenalEvil")


    def test_hand_made_buffs_follow_the_rename_in_every_slot(self, veigar, old_raw, new_raw):
        hashed = count_buff(old_raw, new_raw, "VeigarPhenomenalEvil")
        veigar.passive.buffs = [Buff(name=hashed)]
        for props in damage_props(veigar.q):
            props.amount = f"TotalDamage + target_stacks_{hashed} + elapsed_{hashed}"

        result = patch(veigar, old_raw, new_raw)

        assert [buff.name for buff in result.champion.passive.buffs] == ["VeigarPhenomenalEvil"]
        assert {props.amount for props in damage_props(result.champion.q)} == {
            "TotalDamage + target_stacks_VeigarPhenomenalEvil + elapsed_VeigarPhenomenalEvil"}


def count_buff(old_raw, new_raw, buff: str) -> str:
    """Veigar Q's TotalDamage counts the buff, which the old patch only knew as a hash."""
    for raw, name in ((old_raw, f"{{{field_hash(buff)}}}"), (new_raw, buff)):
        total = spell(raw.cdragon, "VeigarBalefulStrike")["mSpellCalculations"]["TotalDamage"]
        total["mFormulaParts"].append({"__type": "BuffCounterByCoefficientCalculationPart", "mBuffName": name,
                                       "mCoefficient": 1.0})
    return f"h_{field_hash(buff)}"


class TestStats():

    def test_stat_changes_are_lines_but_keep_validation(self, veigar, old_raw, new_raw):
        record = next(r for r in new_raw.cdragon.values() if isinstance(r, dict) and r.get("__type") == "CharacterRecord")
        record["baseHPModifiable"]["baseValue"] = veigar.hp + 20

        result = patch(veigar, old_raw, new_raw)

        assert result.champion.hp == veigar.hp + 20
        assert texts(result.champion) == [f"hp: {veigar.hp:g} ⇒ {veigar.hp + 20:g}"]
        assert result.champion.validated


def test_without_old_raw_data_the_stored_values_are_compared(veigar, old_raw, new_raw):
    veigar.q.values = loaded_spells(old_raw, VEIGAR_RANKS)["q"].values.values | {"BaseDamage": "by_rank(1, 2, 3, 4, 5)"}

    champion = patch(veigar, old_raw, new_raw, old_spells=spells_from_document(veigar)).champion

    assert "BaseDamage: by_rank(1, 2, 3, 4, 5) ⇒ by_rank(80, 120, 160, 200, 240)" in texts(champion.q)


def test_used_names_per_slot(veigar):
    used = used_names(veigar.w, "w")

    assert {"BaseCooldown", "TotalDamage"} <= used["w"]
    assert {"DarkMatterCDRIncrement", "PStacksPerDarkMatterCDR"} <= used["passive"]


def test_used_names_skip_texts(veigar):
    veigar.q.assumptions = ["BaseDamage is great"]
    veigar.q.rules = []

    assert "BaseDamage" not in used_names(veigar.q, "q").get("q", set())


def test_named_level_parts_reference_their_data_values():
    # Akali P in 16.23, the fields only known by hash.
    part = {"{91d404a5}": "Level1MS", "{bbd778a2}": "PerLevel", "__type": "{4ce08984}",
            "{9823b29a}": [{"level": 6, "{ae9b464d}": "Bonus", "{b0d8b2ac}": "PerLevel", "__type": "{0333530c}"}]}

    assert _calculation_names({"mFormulaParts": [part]}) == {"Level1MS", "PerLevel", "Bonus"}
