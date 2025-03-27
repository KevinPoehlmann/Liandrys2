import pytest

from src.server.models.dataenums import Stat, ActionType, DamageSubType, DamageType, DamageCalculation




class TestCharacter():

    @pytest.mark.parametrize("input, output", [
        (Stat.AD, 75.45),
        (Stat.MR, 38.334)
    ])
    def test_get_base_stat(self, aatrox_with_items, input, output):
        result = aatrox_with_items.get_base_stat(input)
        assert round(result, 3) == output

    @pytest.mark.parametrize("input, output", [
        (Stat.AD, 45),
        (Stat.ARMOR, 65)
    ])
    def test_get_bonus_stat(self, aatrox_with_items, input, output):
        result = aatrox_with_items.get_bonus_stat(input)
        assert result == output

    @pytest.mark.parametrize("input, output", [
        (Stat.AD, 120.45),
        (Stat.ABILITY_HASTE, 40),
        (Stat.SECONDS, 0)
    ])
    def test_get_stat(self, aatrox_with_items, input, output):
        result = aatrox_with_items.get_stat(input)
        assert round(result, 3) == output

    def test_get_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items.get_attackspeed()
        assert round(result, 3) == 0.916

    @pytest.mark.parametrize("input, output", [
        (DamageSubType.PHYSIC, (0, 0)),
        (DamageSubType.MAGIC, (0, 0)),
        (DamageSubType.TRUE, (0, 0)),
    ])
    def test_get_penetration(self, aatrox_with_items, input, output):
        result = aatrox_with_items.get_penetration(input)
        assert result == output

    @pytest.mark.parametrize("input, output", [
        (DamageSubType.PHYSIC, 117.832),
        (DamageSubType.MAGIC, 38.334),
        (DamageSubType.TRUE, 0),
    ])
    def test_get_resistance(self, aatrox_with_items, input, output):
        result = aatrox_with_items.get_resistance(input)
        assert round(result, 3) == output


    @pytest.mark.parametrize("formula, variables, output", [
        ("20", {}, 20),
        ("400 + 0.3 * ad", {}, 436.135),
        ("-5 + rank * 15 + (0.525 + rank * 0.075) * ad", {"rank": 3}, 130.338)
    ])
    def test_evaluate_formula(self, aatrox_with_items, formula, variables, output):
        result = aatrox_with_items.evaluate_formula(formula, variables)
        assert round(result, 3) == output


    @pytest.mark.parametrize("resolve_fixture, output", [
        ("damage_ad_flat", 67.152),
        ("damage_ap_maxhp", 108.22),
        ("damage_true_missinghp", 120.678),
        ("damage_true_currenthp", 72.0)
    ], indirect=["resolve_fixture"])
    def test_calculate_damage(self, aatrox_with_items, resolve_fixture, output):
        aatrox_with_items.hp = 900
        result = aatrox_with_items.calculate_damage(resolve_fixture)
        assert round(result, 3) == output


    @pytest.mark.parametrize("resolve_fixture, output", [
        ("damage_ad_flat", 67.152),
        ("damage_ap_maxhp", 108.22),
        ("damage_true_missinghp", 120.678),
        ("damage_true_currenthp", 72.0)
    ], indirect=["resolve_fixture"])
    def test_calculate_damage(self, aatrox_with_items, resolve_fixture, output):
        aatrox_with_items.hp = 900
        result = aatrox_with_items.calculate_damage(resolve_fixture)
        assert round(result, 3) == output


    @pytest.mark.parametrize("value, dmg_calc, output", [
        (100, DamageCalculation.FLAT , 100),
        (0.1, DamageCalculation.MAX_HP , 130.226),
        (0.1, DamageCalculation.MISSING_HP , 40.226),
        (0.1, DamageCalculation.CURRENT_HP , 90)
    ])
    def test_calculate_hp_scaling(self, aatrox_with_items, value, dmg_calc, output):
        aatrox_with_items.hp = 900
        result = aatrox_with_items.calculate_hp_scaling(value, dmg_calc)
        assert round(result, 3) == output


    def test_basic_attack(self, aatrox_with_items):
        result = aatrox_with_items.basic_attack(0)
        assert len(result.stati) == 1
        assert round(result.time, 3) == 0.215
        assert round(aatrox_with_items.cooldowns[ActionType.AA], 3) == 1.092
        assert result.stati[0].source == ActionType.AA
        assert result.stati[0].props.scaling == "ad"
        assert result.stati[0].props.dmg_type == DamageType.BASIC
        assert result.stati[0].props.dmg_sub_type == DamageSubType.PHYSIC
        assert result.stati[0].props.dmg_calc == DamageCalculation.FLAT
        assert result.stati[0].duration == 0
        assert result.stati[0].interval == 0


    def test_do_ability(self, aatrox_with_items):
        aatrox_with_items.cooldowns[ActionType.Q] = 1
        result = aatrox_with_items.do_ability(ActionType.Q, 0)
        assert result.time == 1.6
        assert len(result.stati) == 1
        assert round(aatrox_with_items.cooldowns[ActionType.Q], 3) == 3.029
        assert result.stati[0].source == ActionType.Q
        assert result.stati[0].props.scaling == "-5 + rank * 15 + (0.525 + rank * 0.075) * ad"
        assert result.stati[0].props.dmg_type == DamageType.AOE
        assert result.stati[0].props.dmg_sub_type == DamageSubType.PHYSIC
        assert result.stati[0].props.dmg_calc == DamageCalculation.FLAT


    def test_do_action(self, aatrox_with_items):
        result = aatrox_with_items.do_action(ActionType.AA, 1)
        assert len(result.stati) == 1
        assert round(result.time, 3) == 1.215
        assert result.stati[0].source == ActionType.AA
        assert result.stati[0].props.scaling == "ad"


    @pytest.mark.parametrize("resolve_fixture, output", [
        ("q_damage_aa", 120.45),
        ("q_damage_q", 130.338),
        ("q_heal_e", 436.135)
    ], indirect=["resolve_fixture"])
    def test_evaluate(self, aatrox_with_items, resolve_fixture, output):
        result = aatrox_with_items.evaluate([resolve_fixture])
        assert len(result) == 1
        assert round(result[0].props.value, 3) == output


    def test_take_stati(self, aatrox_with_items, q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat):
        aatrox_with_items.take_stati([q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat])
        assert round(aatrox_with_items.damage_taken, 3) == 175.372
        assert round(aatrox_with_items.hp, 3) == 1302.26