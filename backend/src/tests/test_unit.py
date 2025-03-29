import pytest

from src.server.models.dataenums import Stat, ActionType, DamageSubType, DamageType, DamageCalculation




class TestCharacter():

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 75.45),
        (Stat.MR, 38.334)
    ])
    def test_get_base_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items.get_base_stat(stat)
        assert round(result, 3) == output

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 45),
        (Stat.ARMOR, 65)
    ])
    def test_get_bonus_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items.get_bonus_stat(stat)
        assert result == output

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 120.45),
        (Stat.ABILITY_HASTE, 40),
        (Stat.SECONDS, 0)
    ])
    def test_get_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items.get_stat(stat)
        assert round(result, 3) == output

    def test_get_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items.get_attackspeed()
        assert round(result, 3) == 0.916

    @pytest.mark.parametrize("dmg_sub_type, output", [
        (DamageSubType.PHYSIC, (0, 0)),
        (DamageSubType.MAGIC, (0, 0)),
        (DamageSubType.TRUE, (0, 0)),
    ])
    def test_get_penetration(self, aatrox_with_items, dmg_sub_type, output):
        result = aatrox_with_items.get_penetration(dmg_sub_type)
        assert result == output

    @pytest.mark.parametrize("dmg_sub_type, output", [
        (DamageSubType.PHYSIC, 117.832),
        (DamageSubType.MAGIC, 38.334),
        (DamageSubType.TRUE, 0),
    ])
    def test_get_resistance(self, aatrox_with_items, dmg_sub_type, output):
        result = aatrox_with_items.get_resistance(dmg_sub_type)
        assert round(result, 3) == output




    @pytest.mark.parametrize("formula, variables, output", [
        ("20", {}, 20),
        ("400 + 0.3 * ad", {}, 436.135),
        ("-5 + rank * 15 + (0.525 + rank * 0.075) * ad", {"rank": 3}, 130.338)
    ])
    def test_evaluate_formula(self, aatrox_with_items, formula, variables, output):
        result = aatrox_with_items.evaluate_formula(formula, variables)
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


    @pytest.mark.parametrize("processed_damage_props, output", [
        ({
            "val": 100,
            "flat_pen": 10,
            "perc_pen": 50,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.PHYSIC,
            "dmg_calc": DamageCalculation.FLAT
        }, 67.152),
        ({
            "val": 0.1,
            "flat_pen": 18,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.MAGIC,
            "dmg_calc": DamageCalculation.MAX_HP
        }, 108.22),
        ({
            "val": 0.3,
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE,
            "dmg_calc": DamageCalculation.MISSING_HP
        }, 120.678),
        ({
            "val": 0.08,
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE,
            "dmg_calc": DamageCalculation.CURRENT_HP
        }, 72.0)
    ], indirect=["processed_damage_props"])
    def test_calculate_damage(self, aatrox_with_items, processed_damage_props, output):
        aatrox_with_items.hp = 900
        result = aatrox_with_items.calculate_damage(processed_damage_props)
        assert round(result, 3) == output


    @pytest.mark.parametrize("hp_subtraction, values, hp, healed", [
        (100, [100], 1302.26, 100),
        (50, [20, 40], 1302.26, 50),
        (200, [50, 25, 25], 1202.26, 100),
        (100, [], 1202.26, 0)
    ])
    def test_apply_heals(self, aatrox_with_items, hp_subtraction, values, hp, healed):
        aatrox_with_items.hp -= hp_subtraction
        aatrox_with_items.apply_heals(values)
        assert aatrox_with_items.hp == hp
        assert aatrox_with_items.healed == healed


    @pytest.mark.parametrize("initial_shields, new_shields, expected_shields", [
        ([], [(3, 50)], [(4, 50)]),
        ([(5, 100)], [(3, 50)], [(4, 50), (5, 100)]),
        ([(5, 100)], [(3, 50), (5, 20)], [(4, 50), (5, 100), (6, 20)]),
        ([(0.5, 50), (5, 100)], [(3, 50)], [(4, 50), (5, 100)]),
        ([(3, -10)], [], []),
    ])
    def test_apply_shields(self, aatrox_with_items, initial_shields, new_shields, expected_shields):
        aatrox_with_items.shields = initial_shields
        aatrox_with_items.apply_shields(new_shields, 1)
        assert aatrox_with_items.shields == expected_shields

    @pytest.mark.parametrize("initial_shields, damages, damage_taken, damage_shielded, hp, expected_shields", [
        ([], [50, 50], 100, 0, 1202.26, []),
        ([(2, 50), (3, 100)], [200], 200, 150, 1252.26, [(2, 0), (3, 0)]),
        ([(2, 50), (3, 100)], [100], 100, 100, 1302.26, [(2, 0), (3, 50)]),
    ])
    def test_apply_damages(self, aatrox_with_items, initial_shields, damages, damage_taken, damage_shielded, hp, expected_shields):
        aatrox_with_items.shields = initial_shields
        aatrox_with_items.apply_damages(damages)
        assert aatrox_with_items.damage_taken == damage_taken
        assert aatrox_with_items.damage_shielded == damage_shielded
        assert aatrox_with_items.hp == hp
        assert aatrox_with_items.shields == expected_shields




    def test_basic_attack(self, aatrox_with_items, action_effect_aa, compare_objects):
        result = aatrox_with_items.basic_attack(0)
        assert compare_objects(result, action_effect_aa)
        assert round(aatrox_with_items.cooldowns[ActionType.AA], 3) == 1.092


    def test_do_ability(self, aatrox_with_items, action_effect_q, compare_objects):
        aatrox_with_items.cooldowns[ActionType.Q] = 1
        result = aatrox_with_items.do_ability(ActionType.Q, 0)
        assert compare_objects(result, action_effect_q)
        assert round(aatrox_with_items.cooldowns[ActionType.Q], 3) == 3.029


    @pytest.mark.parametrize("action_type, timer, resolve_fixture", [
        (ActionType.AA, 0, "action_effect_aa"),
        (ActionType.Q, 1, "action_effect_q")
    ], indirect=["resolve_fixture"])
    def test_do_action(self, aatrox_with_items, action_type, timer, resolve_fixture, compare_objects):
        result = aatrox_with_items.do_action(action_type, timer)
        assert compare_objects(result, resolve_fixture)


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
        aatrox_with_items.take_stati([q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat], 0)
        assert round(aatrox_with_items.damage_taken, 3) == 175.372
        assert round(aatrox_with_items.hp, 3) == 1302.26