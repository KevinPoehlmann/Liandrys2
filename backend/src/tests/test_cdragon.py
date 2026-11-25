import json
from pathlib import Path

import pytest

from src.server.loader.cdragon import bin_field, field_hash, format_number, spell_values, translate_calculation


CDRAGON = Path(__file__).parent / "static" / "cdragon"


def load_spell(champion: str, script_name: str) -> dict:
    data = json.loads((CDRAGON / f"{champion}.bin.json").read_text(encoding="utf-8"))
    return next(record["mSpell"] for record in data.values()
                if isinstance(record, dict) and record.get("mScriptName") == script_name)


class TestFormatNumber():

    @pytest.mark.parametrize("raw, expected", [
        (0.44999998807907104, "0.45"),
        (0.000500000023748, "0.0005"),
        (80.0, "80"),
        (-0.1, "-0.1"),
    ])
    def test_removes_float_noise(self, raw, expected):
        assert format_number(raw) == expected


class TestRankValues():

    def test_rank_lists_skip_rank_zero(self):
        values = spell_values(load_spell("veigar", "VeigarBalefulStrike"), max_rank=5).values

        assert values["BaseDamage"] == "by_rank(80, 120, 160, 200, 240)"
        assert values["APRatio"] == "by_rank(0.5, 0.55, 0.6, 0.65, 0.7)"


    def test_ultimate_uses_three_ranks(self):
        values = spell_values(load_spell("vayne", "VayneInquisition"), max_rank=3).values

        assert values["TumbleCDReduction"] == "by_rank(30, 40, 50)"


    def test_equal_values_become_a_constant(self):
        values = spell_values(load_spell("annie", "AnniePassive"), max_rank=0).values

        assert values["MaxStacks"] == "4"


    def test_empty_values_are_zero(self):
        values = spell_values(load_spell("vayne", "VayneSilveredBolts"), max_rank=5).values

        assert values["APRatio"] == "0"


    def test_differing_values_without_ranks_are_reported(self):
        spell = {"DataValues": [{"name": "Damage", "values": [1, 2, 3, 4, 5, 6, 7]}]}

        result = spell_values(spell, max_rank=0)

        assert "Damage" not in result.values
        assert "no ranks" in result.unsupported["Damage"]


    def test_cooldown_starts_at_rank_zero_and_mana_at_rank_one(self):
        values = spell_values(load_spell("veigar", "VeigarBalefulStrike"), max_rank=5).values

        # Wiki: cooldown 6 to 4, cost 30 to 50
        assert values["cooldownTime"] == "by_rank(6, 5.5, 5, 4.5, 4)"
        assert values["mana"] == "by_rank(30, 35, 40, 45, 50)"


    def test_cooldown_and_mana_come_from_the_live_fields(self):
        # cooldownTime still says 9 / 8 / 7 / 6 / 5; Riot only updates the Cooldown object (26.21, wiki: 9 to 4)
        values = spell_values(load_spell("darius", "DariusCleave"), max_rank=5).values

        assert values["cooldownTime"] == "by_rank(9, 7.75, 6.5, 5.25, 4)"


    def test_old_spell_fields_are_the_fallback(self):
        values = spell_values({"cooldownTime": [0, 8, 7], "mana": [40, 50]}, max_rank=2).values

        assert (values["cooldownTime"], values["mana"]) == ("by_rank(8, 7)", "by_rank(40, 50)")


    def test_spell_fields_are_always_present(self):
        values = spell_values({}, max_rank=5).values

        assert values == {"cooldownTime": "0", "mana": "0"}


    def test_hashed_names_are_skipped(self):
        spell = {"DataValues": [{"name": "{7d38e7d6}", "values": [1] * 7}]}

        assert "{7d38e7d6}" not in spell_values(spell, max_rank=5).values


class TestCalculations():

    def test_named_values_with_stat_ratio(self):
        values = spell_values(load_spell("veigar", "VeigarBalefulStrike"), max_rank=5).values

        assert values["TotalDamage"] == "BaseDamage + APRatio * ap"


    def test_modified_calculation_references_the_other_by_name(self):
        values = spell_values(load_spell("veigar", "VeigarR"), max_rank=3).values

        assert values["MaxDamage"] == "MinDamage * 2"


    def test_level_interpolation_continues_past_18(self):
        values = spell_values(load_spell("darius", "DariusHemoMarker"), max_rank=0).values

        # Wiki: 13 to 30 over levels 1-18, then 31 and 32
        levels = ", ".join(str(level) for level in range(13, 33))
        assert values["BleedDamagePerStack"] == f"by_level({levels}) + 0.3 * bonus_ad"


    def test_level_interpolation_can_stop_at_18(self):
        part = {"__type": "ByCharLevelInterpolationCalculationPart", "mStartValue": 1, "mEndValue": 18,
                "mScalePastDefaultMaxLevel": False}

        formula = translate_calculation({"__type": "GameCalculation", "mFormulaParts": [part]})

        assert formula.endswith("17, 18, 18, 18)")


    def test_breakpoints_change_the_bonus_per_level(self):
        values = spell_values(load_spell("darius", "DariusHemoMarker"), max_rank=0).values

        # Wiki: 30 + 5 per level until 10, then + 10 per level until 13, then + 25 per level
        assert values["NoxianMightBonusAD"] == (
            "by_level(30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 85, 95, 105, 130, 155, 180, 205, 230, 255, 280)")


    def test_breakpoint_without_level_starts_at_level_one(self):
        # Yone W against minions; wiki: 30 + 10 per level until 8, then + 20 per level until 13, then + 40 per level
        part = {"__type": "ByCharLevelBreakpointsCalculationPart", "mLevel1Value": 30.0, "mBreakpoints": [
            {"mBonusPerLevelAtAndAfter": 10.0}, {"mLevel": 9, "mBonusPerLevelAtAndAfter": 20.0},
            {"mLevel": 14, "mBonusPerLevelAtAndAfter": 40.0}]}

        formula = translate_calculation({"__type": "GameCalculation", "mFormulaParts": [part]})

        assert formula == "by_level(30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 240, 280, 320, 360, 400, 440, 480)"


    def test_breakpoints_add_one_time_bonuses(self):
        values = spell_values(load_spell("annie", "AnniePassive"), max_rank=0).values

        assert values["StunDuration"] == f"by_level({', '.join(['1.25'] * 5 + ['1.5'] * 5 + ['1.75'] * 10)})"


    def test_base_and_bonus_stats(self):
        values = spell_values(load_spell("annie", "AnnieR"), max_rank=3).values

        assert values["TibbersTotalHP"].startswith("by_level(1275,")
        assert values["TibbersTotalHP"].endswith(") * TibbersModeSpecificHPMod + 0.5 * ap + 1.5 * bonus_hp")


    def test_mana_ratios(self):
        # Ryze W in 16.21: BaseDamage + 0.6 AP + 3 % bonus mana.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "NamedDataValueCalculationPart", "mDataValue": "BaseDamage"},
            {"__type": "StatByCoefficientCalculationPart", "mCoefficient": 0.6000000238418579},
            {"__type": "AbilityResourceByCoefficientCalculationPart", "mCoefficient": 0.029999999329447746, "mStatFormula": 2},
            {"__type": "AbilityResourceByCoefficientCalculationPart", "mCoefficient": 0.019999999552965164}]}

        assert translate_calculation(calculation) == "BaseDamage + 0.6 * ap + 0.03 * bonus_mana + 0.02 * max_mana"


    def test_crit_chance_lethality_and_bonus_attackspeed(self):
        # Shapes from Caitlyn's headshot, Pyke R and Bel'Veth E in 16.21.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "StatByNamedDataValueCalculationPart", "mStat": 8, "mDataValue": "CriticalStrikeScaling"},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 29, "mCoefficient": 1.5},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 4, "mStatFormula": 2, "mCoefficient": 0.4000000059604645}]}

        assert translate_calculation(calculation) == \
            "CriticalStrikeScaling * crit_chance + 1.5 * lethality + 0.4 * bonus_attackspeed"


    def test_crit_damage(self):
        # Shapes from Garen E (crit: 1 + CritMod × (stat 9 − 1)) and Ashe P (crit chance × (1 + bonus stat 9)) in 16.21.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "StatByCoefficientCalculationPart", "mStat": 9, "mCoefficient": 1},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 9, "mStatFormula": 2, "mCoefficient": 1}]}

        assert translate_calculation(calculation) == "crit_damage + bonus_crit_damage"


    def test_health_life_steal_movespeed_and_range_stats(self):
        # Shapes from Zac's costs, Olaf W, Ambessa R, Hecarim P and Urgot W in 16.21.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "StatByCoefficientCalculationPart", "mStat": 14, "mCoefficient": 1.0},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 16, "mCoefficient": 1.0},
            {"__type": "StatByNamedDataValueCalculationPart", "mStat": 18, "mDataValue": "LifeStealScaling"},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 7, "mStatFormula": 2, "mCoefficient": 0.3},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 31, "mStatFormula": 2, "mCoefficient": 1.0}]}

        assert translate_calculation(calculation) == "current_hp_percent + missing_hp_percent + " \
            "LifeStealScaling * life_steal + 0.3 * bonus_movespeed + bonus_attack_range"


    def test_target_stats(self):
        # Kindred W (target's current HP), Ekko W (target's missing HP) and Zed P (target's max HP) in 16.21.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "StatByCoefficientCalculationPart", "mStat": 13, "mCoefficient": 0.01, "{a8cb9c14}": True},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 15, "mCoefficient": 0.03, "{a8cb9c14}": True},
            {"__type": "StatByCoefficientCalculationPart", "mStat": 12, "mCoefficient": 0.02, "{a8cb9c14}": True}]}

        assert translate_calculation(calculation) == \
            "0.01 * target_current_hp + 0.03 * target_missing_hp + 0.02 * target_max_hp"


    def test_unknown_fields_on_stat_parts_are_reported(self):
        spell = {"mSpellCalculations": {"Damage": {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "StatByCoefficientCalculationPart", "mStat": 12, "mCoefficient": 0.1, "{12345678}": True}]}}}

        assert spell_values(spell, max_rank=5).unsupported == {"Damage": "stat part with unknown field {12345678}"}


    def test_other_resources_than_mana_are_reported(self):
        # Tryndamere Q heals per fury.
        spell = {"mSpellCalculations": {"MaximumHeal": {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "AbilityResourceByCoefficientCalculationPart", "mCoefficient": 1.0, "mAbilityResource": 4}]}}}

        assert spell_values(spell, max_rank=5).unsupported == {"MaximumHeal": "ability resource 4 with formula 0"}


    def test_unknown_parts_are_reported_not_guessed(self):
        spell = {"mSpellCalculations": {
            "Stacks": {"__type": "GameCalculation", "mFormulaParts": [{"__type": "BuffCounterByCoefficientCalculationPart"}]},
            "Shred": {"__type": "GameCalculation", "mFormulaParts": [
                {"__type": "StatByCoefficientCalculationPart", "mStat": 10, "mCoefficient": 1.0}]},
        }}

        result = spell_values(spell, max_rank=5)

        assert "Stacks" not in result.values and "Shred" not in result.values
        assert result.unsupported == {"Stacks": "part type BuffCounterByCoefficientCalculationPart",
                                      "Shred": "stat 10 with formula 0"}


    def test_references_to_hashed_names_are_reported(self):
        values = spell_values(load_spell("vladimir", "VladimirQ"), max_rank=5)

        assert "EmpoweredHealTooltip" not in values.values
        assert values.unsupported["EmpoweredHealTooltip"] == "refers to the hashed name {097cda4f}"


    def test_sums_inside_products_keep_their_parentheses(self):
        sum_part = {"__type": "SumOfSubPartsCalculationPart", "mSubparts": [
            {"__type": "NamedDataValueCalculationPart", "mDataValue": "A"},
            {"__type": "NamedDataValueCalculationPart", "mDataValue": "B"}]}
        product = {"__type": "ProductOfSubPartsCalculationPart", "mPart1": sum_part,
                   "mPart2": {"__type": "NumberCalculationPart", "mNumber": 2}}

        formula = translate_calculation({"__type": "GameCalculation", "mFormulaParts": [product]})

        assert formula == "(A + B) * 2"


class TestHashedFields():

    def test_hash_of_a_known_name(self):
        # From CommunityDragon's hashes.binfields.txt
        assert field_hash("baseHPModifiable") == "8662cf12"


    def test_field_by_name_or_hash(self):
        record = {"baseHPModifiable": 1, "{726ee5cd}": 2}

        assert bin_field(record, "baseHPModifiable") == 1
        assert bin_field(record, "arBaseModifiable") == 2
        assert bin_field(record, "arPerLevelModifiable", 0) == 0
