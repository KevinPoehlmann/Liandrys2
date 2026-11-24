import json
from pathlib import Path

import pytest

from src.server.loader.cdragon import format_number, spell_values, translate_calculation


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


    def test_breakpoints_add_one_time_bonuses(self):
        values = spell_values(load_spell("annie", "AnniePassive"), max_rank=0).values

        assert values["StunDuration"] == f"by_level({', '.join(['1.25'] * 5 + ['1.5'] * 5 + ['1.75'] * 10)})"


    def test_base_and_bonus_stats(self):
        values = spell_values(load_spell("annie", "AnnieR"), max_rank=3).values

        assert values["TibbersTotalHP"].startswith("by_level(1275,")
        assert values["TibbersTotalHP"].endswith(") * TibbersModeSpecificHPMod + 0.5 * ap + 1.5 * bonus_hp")


    def test_unknown_parts_are_reported_not_guessed(self):
        spell = {"mSpellCalculations": {
            "Stacks": {"__type": "GameCalculation", "mFormulaParts": [{"__type": "BuffCounterByCoefficientCalculationPart"}]},
            "Shred": {"__type": "GameCalculation", "mFormulaParts": [
                {"__type": "StatByCoefficientCalculationPart", "mStat": 29, "mCoefficient": 1.0}]},
        }}

        result = spell_values(spell, max_rank=5)

        assert "Stacks" not in result.values and "Shred" not in result.values
        assert result.unsupported == {"Stacks": "part type BuffCounterByCoefficientCalculationPart",
                                      "Shred": "stat 29 with formula 0"}


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
