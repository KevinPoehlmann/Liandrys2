import copy

import pytest

from src.server.loader.champion_builder import champion_stats, loaded_spells
from src.server.loader.champion_patcher import _note_lines, patch_champion, spells_from_document, used_names
from src.server.models.ability import Ability
from src.server.models.change import Change
from src.server.models.enums import ChangeSource
from src.server.models.json_validation import ChampionJson
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


def texts(container) -> list[str]:
    return [change.text for change in container.changes]


class TestCopyForward():

    def test_unchanged_data_changes_nothing(self, veigar, old_raw, new_raw):
        result = patch(veigar, old_raw, new_raw)

        assert result.champion.patch == NEW_PATCH
        assert result.unvalidated == {}
        assert result.champion.validated
        assert not result.changed


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
        result = patch(veigar, old_raw, new_raw, {"Baleful Strike": ["Now pierces"], "General": ["Splash art updated"]})

        assert result.unvalidated["Baleful Strike"] == ["named in the patch notes only"]
        assert result.champion.q.changes == [Change(source=ChangeSource.PATCH_NOTES, text="Now pierces")]
        assert texts(result.champion) == ["Splash art updated"]


    def test_two_part_abilities_match_either_name(self):
        # 26.21: Lee Sin's "Safeguard / Iron Will" appears as "Safeguard"
        notes = {"Safeguard": ["Cooldown increased"], "Iron Will": ["Bug fix"], "Tempest": ["Other"]}

        assert _note_lines(notes, "Safeguard / Iron Will") == ["Cooldown increased", "Bug fix"]
        assert notes == {"Tempest": ["Other"]}


    def test_an_unvalidated_ability_stays_unvalidated(self, veigar, old_raw, new_raw):
        veigar.e.validated = False

        result = patch(veigar, old_raw, new_raw)

        assert not result.champion.e.validated
        assert not result.champion.validated


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
    veigar.q.description = "BaseDamage is great"
    veigar.q.rules = []

    assert "BaseDamage" not in used_names(veigar.q, "q").get("q", set())


def test_old_documents_hold_plain_lines():
    assert Ability(name="Q", changes=["Damage increased"]).changes == [
        Change(source=ChangeSource.PATCH_NOTES, text="Damage increased")]
