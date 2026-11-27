import json
from pathlib import Path

import pytest

from src.server.loader.cdragon import (BUFF_NAMES_BY_HASH, bin_field, field_hash, format_number, item_values, part_type,
                                       spell_values, translate_calculation)


CDRAGON = Path(__file__).parent / "static" / "cdragon"


def load_spell(champion: str, script_name: str) -> dict:
    data = json.loads((CDRAGON / f"{champion}.bin.json").read_text(encoding="utf-8"))
    return next(record["mSpell"] for record in data.values()
                if isinstance(record, dict) and record.get("mScriptName") == script_name)


def named_level_spell(part: dict, data_values: dict) -> dict:
    """A spell whose calculation "Calc" is one part reading data values; a number stands for all ranks."""
    def values(value):
        return [value] * 7 if isinstance(value, (int, float)) else value
    return {"DataValues": [{"name": name, "values": values(value)} for name, value in data_values.items()],
            "mSpellCalculations": {"Calc": {"__type": "GameCalculation", "mFormulaParts": [part]}}}


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


    def test_charges_are_read_like_the_cooldown(self):
        # 16.21 Zyra W
        spell = {"mAmmoRechargeTime": [17.5, 16, 14.5, 13, 11.5, 10, 8.5], "mMaxAmmo": [2] * 7}

        values = spell_values(spell, max_rank=5).values

        assert (values["ammoRechargeTime"], values["maxAmmo"]) == ("by_rank(16, 14.5, 13, 11.5, 10)", "2")


    def test_a_recharge_time_without_charges_is_left_out(self):
        # 16.21 Rengar Q: a single ammo is just the cooldown
        spell = {"mAmmoRechargeTime": [6, 6, 5.5, 5, 4.5, 4, 4], "mMaxAmmo": [1] * 7}

        assert "ammoRechargeTime" not in spell_values(spell, max_rank=5).values


    def test_hidden_ammo_is_no_charges(self):
        # 16.21 Karthus Q: the wiki has a 1 s cooldown and no charges
        spell = {"mAmmoRechargeTime": [1] * 7, "mMaxAmmo": [2] * 7, "mAmmoCountHiddenInUI": True}

        values = spell_values(spell, max_rank=5).values

        assert "maxAmmo" not in values and "ammoRechargeTime" not in values


    def test_spell_fields_are_always_present(self):
        values = spell_values({}, max_rank=5).values

        assert values == {"cooldownTime": "0", "mana": "0"}


    def test_hashed_names_get_a_readable_name(self):
        spell = {"DataValues": [{"name": "{7d38e7d6}", "values": [1] * 7}]}

        assert spell_values(spell, max_rank=5).values == {"h_7d38e7d6": "1", "cooldownTime": "0", "mana": "0"}


    def test_names_starting_with_a_digit_get_an_underscore(self):
        # Kled W in 16.21
        spell = {"DataValues": [{"name": "4HitMaxHealthDamage", "values": [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]}],
                 "mSpellCalculations": {"PercentDamage": {"__type": "GameCalculation", "mFormulaParts": [
                     {"mDataValue": "4HitMaxHealthDamage", "__type": "NamedDataValueCalculationPart"}]}}}

        values = spell_values(spell, max_rank=5).values

        assert values["_4HitMaxHealthDamage"] == "by_rank(4.5, 5, 5.5, 6, 6.5)"
        assert values["PercentDamage"] == "_4HitMaxHealthDamage"


    def test_names_that_stay_unreadable(self):
        spell = {"DataValues": [{"name": "", "values": [1] * 7}, {"name": "Max Damage", "values": [1] * 7}]}

        assert spell_values(spell, max_rank=5).values == {"cooldownTime": "0", "mana": "0"}


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


    def test_buff_counters(self):
        # Draven P (gold × 1), Kindred's marks (× 0.05) and Thresh W (ShieldPerSoul × souls) in 16.21.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "BuffCounterByCoefficientCalculationPart", "mBuffName": "DravenPassiveGoldEarned",
             "mCoefficient": 1.0},
            {"__type": "BuffCounterByCoefficientCalculationPart", "mBuffName": "{64290302}",
             "mCoefficient": 0.05000000074505806, "mIconKey": "%i:kindredPassiveIcon%"},
            {"__type": "BuffCounterByNamedDataValueCalculationPart", "mBuffName": "{5fbfbf13}",
             "mDataValue": "ShieldPerSoul", "mScalingTagKey": "font color='#0bf7de'"}]}

        assert translate_calculation(calculation) == "stacks_DravenPassiveGoldEarned + " \
            "0.05 * stacks_KindredMarkOfTheKindredStackCounter + ShieldPerSoul * stacks_ThreshPassiveSoulsGain"


    def test_cooldown_multiplier(self):
        # Miss Fortune's Love Tap refund (as multiplier) and Rakan Q's cooldown (as part) in 16.21.
        refund = {"__type": "GameCalculation", "mMultiplier": {"__type": "CooldownMultiplierCalculationPart"},
                  "mFormulaParts": [{"__type": "NamedDataValueCalculationPart", "mDataValue": "LoveTapBaseRefund"}]}
        cooldown = {"__type": "GameCalculation", "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart",
            "mPart1": {"__type": "NamedDataValueCalculationPart", "mDataValue": "BaseCDActual"},
            "mPart2": {"__type": "CooldownMultiplierCalculationPart"}}]}

        assert translate_calculation(refund) == "LoveTapBaseRefund * cooldown_multiplier"
        assert translate_calculation(cooldown) == "BaseCDActual * cooldown_multiplier"


    def test_unknown_buff_hashes_get_hashed_names(self):
        # K'Sante E's shield on an ally; no string in his data hashes to the buff.
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "BuffCounterByCoefficientCalculationPart", "mBuffName": "{7a26bd77}", "mCoefficient": 0.1}]}

        assert translate_calculation(calculation) == "0.1 * stacks_h_7a26bd77"


    def test_guessed_buff_names_match_their_hashes(self):
        # Guards against typos: each guess must hash to a buff hash seen in 16.21 (counters, conditions, elapsed parts).
        assert set(BUFF_NAMES_BY_HASH) == {
            "{eb906dca}", "{f79080ae}", "{f6907f1b}", "{c9372c6b}", "{7f3c01cf}", "{a8a3dd7a}", "{577427b5}",
            "{8682fc00}", "{9e10ce18}", "{9d0c98ec}", "{79ba1a32}", "{64290302}", "{6244221a}", "{5eb30a0d}",
            "{e3b83f84}", "{b5c3348f}", "{1b1d7345}", "{e88568f8}", "{bba88b2a}", "{098531db}", "{32bcea5d}",
            "{1705b20f}", "{0dc6979e}", "{5fbfbf13}", "{93251bfb}", "{1e75ffdf}", "{12395d09}", "{89ae79fa}",
            "{752d125a}", "{0f374711}", "{99a499bd}", "{7bcf22fa}", "{ff849683}", "{7dfdcd99}", "{ecbd8e2e}",
            "{5a8747c2}", "{c295b00e}"}


    def test_unknown_fields_on_buff_counters_are_reported(self):
        spell = {"mSpellCalculations": {"Damage": {"__type": "GameCalculation", "mFormulaParts": [
            {"__type": "BuffCounterByCoefficientCalculationPart", "mBuffName": "Stacks", "mCoefficient": 1.0,
             "{12345678}": True}]}}}

        assert spell_values(spell, max_rank=5).unsupported == {"Damage": "buff counter with unknown field {12345678}"}


    def test_unknown_parts_are_reported_not_guessed(self):
        spell = {"mSpellCalculations": {
            "Stacks": {"__type": "GameCalculation", "mFormulaParts": [{"__type": "{12345678}"}]},
            "Shred": {"__type": "GameCalculation", "mFormulaParts": [
                {"__type": "StatByCoefficientCalculationPart", "mStat": 10, "mCoefficient": 1.0}]},
        }}

        result = spell_values(spell, max_rank=5)

        assert "Stacks" not in result.values and "Shred" not in result.values
        assert result.unsupported == {"Stacks": "part type {12345678}",
                                      "Shred": "stat 10 with formula 0"}


    def test_references_to_hashed_names_use_the_readable_name(self):
        values = spell_values(load_spell("vladimir", "VladimirQ"), max_rank=5)

        assert values.values["EmpoweredHealTooltip"] == "h_097cda4f * 1"
        assert values.values["h_097cda4f"].startswith("by_level(30, ")
        assert "h_097cda4f" in values.calculations


    def test_references_to_other_calculations(self):
        # Zed P: % of the target's max HP, the percent itself is a hashed calculation.
        spell = {"DataValues": [{"name": "PercentDamage", "values": [0.1] * 7}], "mSpellCalculations": {
            "{6a1a62e9}": {"__type": "GameCalculation", "mFormulaParts": [
                {"__type": "NamedDataValueCalculationPart", "mDataValue": "PercentDamage"}]},
            "TotalDamage": {"__type": "GameCalculation", "mFormulaParts": [
                {"__type": "StatBySubPartCalculationPart", "mStat": 12, "{a8cb9c14}": True,
                 "mSubpart": {"__type": "{f3cbe7b2}", "mSpellCalculationKey": "{6a1a62e9}"}}]}}}

        values = spell_values(spell, max_rank=5).values

        assert values["TotalDamage"] == "h_6a1a62e9 * target_max_hp"
        assert values["h_6a1a62e9"] == "PercentDamage"


    def test_named_interpolation(self):
        # Kayn P in 16.23 (wiki: 20 to 40 % by level), with rounder numbers.
        spell = named_level_spell({"StartDataValue": "Min", "EndDataValue": "Max", "__type": "{ee18a47b}"},
                                  {"Min": 10, "Max": 61})

        assert spell_values(spell, max_rank=0).values["Calc"] == f"by_level({', '.join(map(str, range(10, 68, 3)))})"


    def test_named_linear_by_level(self):
        # Irelia P in 16.23; wiki: 10 to 61 by level (+ 20 % bonus AD).
        spell = named_level_spell({"{91d404a5}": "OnHitBaseDamage", "{b2cd0eb0}": "OnHitPerLevel", "__type": "{b22609db}"},
                                  {"OnHitBaseDamage": 10, "OnHitPerLevel": 3})

        assert spell_values(spell, max_rank=0).values["Calc"] == f"by_level({', '.join(map(str, range(10, 68, 3)))})"


    def test_named_breakpoints(self):
        # Gragas P's cooldown in 16.23; wiki: 12 to 6 at levels 1, 6, 11 and 16. The empty value counts as 0.
        breakpoints = [{"level": level, "{ae9b464d}": "Bonus", "{b0d8b2ac}": "PerLevel", "__type": "{0333530c}"}
                       for level in (6, 11, 16)]
        spell = named_level_spell({"{91d404a5}": "Level1Value", "{bbd778a2}": "PerLevel", "{9823b29a}": breakpoints,
                                   "__type": "{4ce08984}"}, {"Level1Value": 12, "Bonus": -2, "PerLevel": None})

        expected = ["12"] * 5 + ["10"] * 5 + ["8"] * 5 + ["6"] * 5
        assert spell_values(spell, max_rank=0).values["Calc"] == f"by_level({', '.join(expected)})"


    def test_named_level_parts_need_one_value_for_all_ranks(self):
        spell = named_level_spell({"StartDataValue": "Min", "EndDataValue": "Max", "__type": "{ee18a47b}"},
                                  {"Min": 10, "Max": [61, 62, 63, 64, 65, 66, 67]})

        assert spell_values(spell, max_rank=5).unsupported == {"Calc": "level formula with Max, which differs by rank"}


    def test_unknown_fields_on_named_level_parts_are_reported(self):
        spell = named_level_spell({"StartDataValue": "Min", "EndDataValue": "Max", "{12345678}": False,
                                   "__type": "{ee18a47b}"}, {"Min": 10, "Max": 61})

        assert spell_values(spell, max_rank=0).unsupported == {
            "Calc": "ByCharLevelNamedDataValuesInterpolationCalculationPart with unknown field {12345678}"}


    def test_values_of_other_spells_are_reported(self):
        # Elise R in 16.23 reads a value of her spider form's E.
        spell = named_level_spell({"SourceObject": "Characters/Elise/Spells/EliseSpiderEAbility/EliseSpiderEInitial",
                                   "DataValue": "PBonusIncrease", "__type": "{9e9e2e5c}"}, {})

        assert spell_values(spell, max_rank=0).unsupported == {
            "Calc": "refers to PBonusIncrease of another spell (EliseSpiderEInitial)"}


    def test_level_list(self):
        # Lux P in 16.21: entry 0 is unused, levels 1–18 are 30–200 like the wiki, and the list continues to 20.
        part = {"values": [20.0 + 10 * index for index in range(31)], "__type": "ByCharLevelFormulaCalculationPart"}

        formula = translate_calculation({"__type": "GameCalculation", "mFormulaParts": [part]})

        assert formula == f"by_level({', '.join(map(str, range(30, 230, 10)))})"


    def test_short_level_lists_are_reported(self):
        spell = named_level_spell({"values": [1.0] * 19, "__type": "ByCharLevelFormulaCalculationPart"}, {})

        assert spell_values(spell, max_rank=0).unsupported == {"Calc": "level list with only 19 entries"}


    def test_effect_amounts_become_named_values(self):
        # Fizz Q in 16.21 (wiki: 10/25/40/55/70 + 55 % AP). Unreferenced effect amounts are stale and stay out.
        spell = named_level_spell({"mEffectIndex": 1, "__type": "EffectValueCalculationPart"}, {})
        spell["mEffectAmount"] = [{"value": [0.0, 10.0, 25.0, 40.0, 55.0, 70.0, 85.0]}, {},
                                  {"value": [550.0, 650.0, 750.0, 850.0, 950.0, 1050.0, 1150.0]}]

        values = spell_values(spell, max_rank=5).values

        assert values["Calc"] == "Effect1Amount"
        assert values["Effect1Amount"] == "by_rank(10, 25, 40, 55, 70)"
        assert "Effect3Amount" not in values


    def test_missing_effect_amounts_are_reported(self):
        spell = named_level_spell({"mEffectIndex": 2, "__type": "EffectValueCalculationPart"}, {})
        spell["mEffectAmount"] = [{"value": [1.0] * 7}, {}]

        assert spell_values(spell, max_rank=5).unsupported == {"Effect2Amount": "refers to the missing effect amount 2"}


    def test_conditional_picks_a_calculation_by_buff(self):
        # Shen P in 16.21 (Shen vs. Zed quest reward); Jax W has no default, the other side is 0.
        requirement = {"mBuffName": "{7dfdcd99}", "__type": "HasBuffCastRequirement"}
        shen = {"mSimpleTooltipCalculationDisplay": 5, "mDefaultGameCalculation": "Base",
                "mConditionalGameCalculation": "Empowered", "mConditionalCalculationRequirements": requirement,
                "__type": "GameCalculationConditional"}
        jax = {"mConditionalGameCalculation": "TotalDamage",
               "mConditionalCalculationRequirements": requirement | {"mInvertResult": True},
               "__type": "GameCalculationConditional"}

        assert translate_calculation(shen) == "Empowered if stacks_ShenSpiritShadowQuestReward > 0 else Base"
        assert translate_calculation(jax) == "TotalDamage if stacks_ShenSpiritShadowQuestReward == 0 else 0"


    def test_conditional_picks_a_calculation_by_range_type(self):
        # Blade of the Ruined King in 16.23: its hashed calculations for melee and ranged.
        calculation = {"mDefaultGameCalculation": "{d96e60e3}", "mConditionalGameCalculation": "{42565e68}",
                       "mConditionalCalculationRequirements": {"__type": "IsRangedCastRequirement"},
                       "__type": "GameCalculationConditional"}

        assert translate_calculation(calculation) == "h_42565e68 if ranged > 0 else h_d96e60e3"


    def test_ranged_multiplier_scales_only_ranged(self):
        # Titanic Hydra in 16.23: 1 % maximum health, 0.5 % for ranged (wiki).
        calculation = {"mFormulaParts": [{"mStat": 12, "mCoefficient": 0.01, "__type": "StatByCoefficientCalculationPart"}],
                       "mRangedMultiplier": {"mNumber": 0.5, "__type": "NumberCalculationPart"},
                       "__type": "{e9a3c91d}"}

        assert translate_calculation(calculation) == "(0.01 * max_hp) * (0.5 if ranged > 0 else 1)"


    def test_item_values_are_single_numbers(self):
        # Sheen in 16.23: the item's data values have one mValue, not one per rank.
        record = {"mDataValues": [{"mName": "SpellbladeCooldown", "mValue": 1.5}],
                  "mItemCalculations": {"SpellbladeDamage": {"__type": "GameCalculation", "mFormulaParts": [
                      {"mStat": 2, "mStatFormula": 1, "mCoefficient": 1.0, "__type": "StatByCoefficientCalculationPart"}]}}}

        assert item_values(record).values == {"SpellbladeCooldown": "1.5", "SpellbladeDamage": "base_ad"}


    def test_elapsed_share_of_a_buff(self):
        # Rell W in 16.21: ramps from 20 % to 100 % over the first half of her mount buff.
        elapsed = {"buffName": "{5a8747c2}", "Coefficient": 2.0, "__type": "PercentageOfBuffNameElapsed"}
        calculation = {"__type": "GameCalculation", "mFormulaParts": [
            {"mCeiling": 1.0, "mFloor": 0.2, "mSubparts": [elapsed], "__type": "ClampSubPartsCalculationPart"}]}

        assert translate_calculation(calculation) == "min(max(2 * elapsed_RellW_MountUp, 0.2), 1)"


    def test_unknown_fields_on_elapsed_parts_are_reported(self):
        part = {"buffName": "Buff", "Coefficient": 2.0, "{12345678}": True, "__type": "PercentageOfBuffNameElapsed"}
        spell = {"mSpellCalculations": {"Ramp": {"__type": "GameCalculation", "mFormulaParts": [part]}}}

        assert spell_values(spell, max_rank=0).unsupported == {"Ramp": "elapsed buff part with unknown field {12345678}"}


    def test_data_values_are_found_like_riot_finds_them(self):
        # Riot compares the hash of the lowercased name: Fiora Q's calculation reads `BADRatio`, the value is `bADRatio`.
        spell = {"DataValues": [{"name": "bADRatio", "values": [1] * 7}, {"name": "slowDuration", "values": [1] * 7},
                                {"name": "SlowDuration", "values": [2] * 7}],
                 "mSpellCalculations": {name: {"__type": "GameCalculation", "mFormulaParts": [
                     {"__type": "NamedDataValueCalculationPart", "mDataValue": name}]}
                     for name in ("BADRatio", "SlowDuration", "Missing")}}

        result = spell_values(spell, max_rank=5)

        assert result.values["BADRatio"] == "bADRatio"
        assert result.values["SlowDuration"] == "SlowDuration"
        assert result.unsupported == {"Missing": "refers to the missing data value Missing"}


    def test_combined_conditions_are_reported(self):
        # Zed P in 16.21: no cooldown buff and the target below a health percent.
        spell = {"mSpellCalculations": {"FinalDamage": {
            "mConditionalGameCalculation": "TotalDamage",
            "mConditionalCalculationRequirements": {"__type": "HasAllSubRequirementsCastRequirement"},
            "__type": "GameCalculationConditional"}}}

        assert spell_values(spell, max_rank=0).unsupported == {
            "FinalDamage": "condition HasAllSubRequirementsCastRequirement"}


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


    def test_guessed_part_type_names(self):
        assert part_type({"__type": "{4ce08984}"}) == "ByCharLevelNamedDataValueBreakpointsCalculationPart"
        assert part_type({"__type": "NumberCalculationPart"}) == "NumberCalculationPart"
