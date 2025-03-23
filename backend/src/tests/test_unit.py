import pytest

from src.server.models.dataenums import Stat, ActionType, DamageSubType, DamageType, DamageCalculation



class TestDummy():

    @pytest.mark.parametrize("input, output", [
        (Stat.HP, 1000),
        (Stat.AD, 0)
    ])
    def test_get_stat(self, dummy, input, output):
        result = dummy.get_stat(input)
        assert result == output

    @pytest.mark.parametrize("input, output", [
        (DamageSubType.PHYSIC, 100),
        (DamageSubType.MAGIC, 50),
        (DamageSubType.TRUE, 0)
    ])
    def test_get_resistance(self, dummy, input, output):
        result = dummy.get_resistance(input)
        assert result == output

    
    @pytest.mark.parametrize("resolve_fixture, output", [
        ("damage_ad_flat", 71.429),
        ("damage_ap_maxhp", 75.758),
        ("damage_true_missinghp", 30.0),
        ("damage_true_currenthp", 72.0)
    ], indirect=["resolve_fixture"])
    def test_calculate_damage(self, dummy, resolve_fixture, output):
        dummy.hp = 900
        result = dummy.calculate_damage(resolve_fixture)
        assert round(result, 3) == output


    def test_take_damage(self, dummy, damage_ad_flat, damage_ap_maxhp):
        dummy.take_damge([damage_ad_flat, damage_ap_maxhp])
        assert round(dummy.damage_taken, 3) == 147.186
        assert round(dummy.hp, 3) == 852.814


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
        ("-5 + rank * 15 + (0.525 + rank * 0.075) * ad", {"rank": 3}, 130.338)
    ])
    def test_evaluate_formula(self, aatrox_with_items, formula, variables, output):
        result = aatrox_with_items.evaluate_formula(formula, variables)
        assert round(result, 3) == output


    def test_take_damage(self, aatrox_with_items, damage_ad_flat, damage_ap_maxhp):
        aatrox_with_items.take_damge([damage_ad_flat, damage_ap_maxhp])
        assert round(aatrox_with_items.damage_taken, 3) == 175.372
        assert round(aatrox_with_items.hp, 3) == 1126.888


    def test_basic_attack(self, aatrox_with_items):
        result = aatrox_with_items.basic_attack(0)
        assert len(result.damages) == 1
        assert round(result.time, 3) == 0.215
        assert round(aatrox_with_items.cooldowns[ActionType.AA], 3) == 1.092
        assert result.damages[0].source == ActionType.AA
        assert result.damages[0].scaling == "ad"
        assert result.damages[0].dmg_type == DamageType.BASIC
        assert result.damages[0].dmg_sub_type == DamageSubType.PHYSIC
        assert result.damages[0].dmg_calc == DamageCalculation.FLAT
        assert result.damages[0].duration == 0
        assert result.damages[0].interval == 0
        assert result.stati == []


    def test_do_ability(self, aatrox_with_items):
        aatrox_with_items.cooldowns[ActionType.Q] = 1
        result = aatrox_with_items.do_ability(ActionType.Q, 0)
        assert result.time == 1.6
        assert len(result.damages) == 1
        assert round(aatrox_with_items.cooldowns[ActionType.Q], 3) == 3.029
        assert result.damages[0].source == ActionType.Q
        assert result.damages[0].scaling == "-5 + rank * 15 + (0.525 + rank * 0.075) * ad"
        assert result.damages[0].dmg_type == DamageType.AOE
        assert result.damages[0].dmg_sub_type == DamageSubType.PHYSIC
        assert result.damages[0].dmg_calc == DamageCalculation.FLAT
        assert result.stati == []


    def test_do_action(self, aatrox_with_items):
        result = aatrox_with_items.do_action(ActionType.AA, 1)
        assert len(result.damages) == 1
        assert round(result.time, 3) == 1.215
        assert result.damages[0].source == ActionType.AA
        assert result.damages[0].scaling == "ad"


    @pytest.mark.parametrize("resolve_fixture, output", [
        ("q_damage_aa", 120.45),
        ("q_damage_q", 130.338)
    ], indirect=["resolve_fixture"])
    def test_evaluate_scaling(self, aatrox_with_items, resolve_fixture, output):
        result = aatrox_with_items.evaluate_scaling([resolve_fixture])
        assert len(result) == 1
        assert round(result[0].value, 3) == output
        assert result[0].flat_pen == 0
        assert result[0].percent_pen == 0
