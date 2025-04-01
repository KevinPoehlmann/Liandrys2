import pytest

from src.server.models.dataenums import Stat, Action, ActionType, Actor, DamageSubType, DamageType, HpScaling, StatusType




class TestCharacter():

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 75.45),
        (Stat.MR, 38.334)
    ])
    def test_get_base_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items._get_base_stat(stat)
        assert round(result, 3) == output

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 45),
        (Stat.ARMOR, 65)
    ])
    def test_get_bonus_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items._get_bonus_stat(stat)
        assert result == output

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 120.45),
        (Stat.ABILITY_HASTE, 40),
        (Stat.SECONDS, 0)
    ])
    def test_get_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items._get_stat(stat)
        assert round(result, 3) == output

    def test_get_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items._get_attackspeed()
        assert round(result, 3) == 0.916

    @pytest.mark.parametrize("dmg_sub_type, output", [
        (DamageSubType.PHYSIC, (0, 0)),
        (DamageSubType.MAGIC, (0, 0)),
        (DamageSubType.TRUE, (0, 0)),
    ])
    def test_get_penetration(self, aatrox_with_items, dmg_sub_type, output):
        result = aatrox_with_items._get_penetration(dmg_sub_type)
        assert result == output

    @pytest.mark.parametrize("dmg_sub_type, output", [
        (DamageSubType.PHYSIC, 117.832),
        (DamageSubType.MAGIC, 38.334),
        (DamageSubType.TRUE, 0),
    ])
    def test_get_resistance(self, aatrox_with_items, dmg_sub_type, output):
        result = aatrox_with_items._get_resistance(dmg_sub_type)
        assert round(result, 3) == output

    def test_get_tenacity(self, aatrox_with_items):
        result = aatrox_with_items._get_tenacity()
        assert result == 1

    @pytest.mark.parametrize("slow_list, slow", [
        ([], 1),
        ([(2, 0.2)], 0.8),
        ([(2, 0.2), (3, 0.5), (4, 0.4)], 0.5)
    ])
    def test_get_slow_value(self, aatrox_with_items, slow_list, slow):
        aatrox_with_items.status_effects[StatusType.SLOW] = slow_list
        result = aatrox_with_items._get_slow_value()
        assert result == slow

    @pytest.mark.parametrize("cripple_list, cripple", [
        ([], 1),
        ([(2, 0.2)], 0.8),
        ([(2, 0.2), (3, 0.3)], 0.56),
    ])
    def test_get_cripple_value(self, aatrox_with_items, cripple_list, cripple):
        aatrox_with_items.status_effects[StatusType.CRIPPLE] = cripple_list
        result = aatrox_with_items._get_cripple_value()
        assert round(result, 2) == cripple


    @pytest.mark.parametrize("initial_stati, timer, expected_stati", [
        ({}, 1, {}),
        ({StatusType.STUN: [(2, 0)]}, 1, {StatusType.STUN: [(2, 0)]}),
        ({StatusType.STUN: [(2, 0)]}, 2, {}),
        ({StatusType.STUN: [(2, 0), (3, 0)]}, 2, {StatusType.STUN: [(3, 0)]}),
        ({StatusType.STUN: [(2, 0), (3, 0)], StatusType.SILENCE: [(1, 0)], StatusType.BLIND: [(2.5, 0)]}, 2, {StatusType.STUN: [(3, 0)], StatusType.BLIND: [(2.5, 0)]}),
    ])
    def test_remove_expired_status_effects(self, aatrox_with_items, initial_stati, timer, expected_stati):
        aatrox_with_items.status_effects = initial_stati
        aatrox_with_items._remove_expired_status_effects(timer)
        assert aatrox_with_items.status_effects == expected_stati


    @pytest.mark.parametrize("formula, variables, output", [
        ("20", {}, 20),
        ("400 + 0.3 * ad", {}, 436.135),
        ("-5 + rank * 15 + (0.525 + rank * 0.075) * ad", {"rank": 3}, 130.338)
    ])
    def test_evaluate_formula(self, aatrox_with_items, formula, variables, output):
        result = aatrox_with_items._evaluate_formula(formula, variables)
        assert round(result, 3) == output


    @pytest.mark.parametrize("value, dmg_calc, output", [
        (100, HpScaling.FLAT , 100),
        (0.1, HpScaling.MAX_HP , 130.226),
        (0.1, HpScaling.MISSING_HP , 40.226),
        (0.1, HpScaling.CURRENT_HP , 90)
    ])
    def test_calculate_hp_scaling(self, aatrox_with_items, value, dmg_calc, output):
        aatrox_with_items.hp = 900
        result = aatrox_with_items._calculate_hp_scaling(value, dmg_calc)
        assert round(result, 3) == output


    @pytest.mark.parametrize("processed_damage_props, output", [
        ({
            "val": 100,
            "flat_pen": 10,
            "perc_pen": 0.5,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.PHYSIC,
            "hp_scaling": HpScaling.FLAT
        }, 67.152),
        ({
            "val": 0.1,
            "flat_pen": 18,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.MAGIC,
            "hp_scaling": HpScaling.MAX_HP
        }, 108.22),
        ({
            "val": 0.3,
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE,
            "hp_scaling": HpScaling.MISSING_HP
        }, 120.678),
        ({
            "val": 0.08,
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE,
            "hp_scaling": HpScaling.CURRENT_HP
        }, 72.0)
    ], indirect=["processed_damage_props"])
    def test_calculate_damage(self, aatrox_with_items, processed_damage_props, output):
        aatrox_with_items.hp = 900
        result = aatrox_with_items._calculate_damage(processed_damage_props)
        assert round(result, 3) == output


    @pytest.mark.parametrize("hp_subtraction, processed_heal_list, hp, healed", [
        (100, {"values": [100]}, 1302.26, 100),
        (50, {"values": [20, 40]}, 1302.26, 50),
        (200, {"values": [50, 25, 25]}, 1202.26, 100),
        (100, {"values": []}, 1202.26, 0)
    ], indirect=["processed_heal_list"])
    def test_apply_heals(self, aatrox_with_items, hp_subtraction, processed_heal_list, hp, healed):
        aatrox_with_items.hp -= hp_subtraction
        aatrox_with_items._apply_heals(processed_heal_list)
        assert aatrox_with_items.hp == hp
        assert aatrox_with_items.healed == healed


    @pytest.mark.parametrize("initial_shields, processed_shield_list, expected_shields", [
        ([], {"values":[(3, 50)]}, [(4, 50)]),
        ([(5, 100)], {"values":[(3, 50)]}, [(4, 50), (5, 100)]),
        ([(5, 100)], {"values":[(3, 50), (5, 20)]}, [(4, 50), (5, 100), (6, 20)]),
        ([(0.5, 50), (5, 100)], {"values":[(3, 50)]}, [(4, 50), (5, 100)]),
        ([(3, -10)], {"values":[]}, []),
    ], indirect=["processed_shield_list"])
    def test_apply_shields(self, aatrox_with_items, initial_shields, processed_shield_list, expected_shields):
        aatrox_with_items.shields = initial_shields
        aatrox_with_items._apply_shields(processed_shield_list, 1)
        assert aatrox_with_items.shields == expected_shields

    @pytest.mark.parametrize("initial_shields, processed_damage_list, damage_taken, damage_shielded, hp, expected_shields", [
        ([], {"values":[50, 50]}, 100, 0, 1202.26, []),
        ([(2, 50), (3, 100)], {"values":[200]}, 200, 150, 1252.26, [(2, 0), (3, 0)]),
        ([(2, 50), (3, 100)], {"values":[100]}, 100, 100, 1302.26, [(2, 0), (3, 50)]),
    ], indirect=["processed_damage_list"])
    def test_apply_damages(self, aatrox_with_items, initial_shields, processed_damage_list, damage_taken, damage_shielded, hp, expected_shields):
        aatrox_with_items.shields = initial_shields
        aatrox_with_items._apply_damages(processed_damage_list)
        assert aatrox_with_items.damage_taken == damage_taken
        assert aatrox_with_items.damage_shielded == damage_shielded
        assert aatrox_with_items.hp == hp
        assert aatrox_with_items.shields == expected_shields


    @pytest.mark.parametrize("initial_stati, processed_status_list, expected_stati", [
        ({}, {"values":[(StatusType.STUN, 2)]}, {StatusType.STUN: [(3, 0)]}),
        ({StatusType.STUN: [(2, 0)]}, {"values":[(StatusType.STUN, 2)]}, {StatusType.STUN: [(2, 0), (3, 0)]}),
        ({StatusType.STUN: [(2, 0)]}, {"values":[(StatusType.SILENCE, 2)]}, {StatusType.STUN: [(2, 0)], StatusType.SILENCE: [(3, 0)]}),
    ], ["processed_status_list"])
    def test_apply_status_effects(self, aatrox_with_items, initial_stati, processed_status_list, expected_stati):
        aatrox_with_items.status_effects = initial_stati
        aatrox_with_items._apply_status_effects(processed_status_list, 1)
        assert aatrox_with_items.status_effects == expected_stati


    @pytest.mark.parametrize("cooldown, status_effects, action, delay", [
        (1, {}, ActionType.AA, 1),
        (2, {}, ActionType.AA, 2),
        (1, {StatusType.SILENCE: [(2, 0)]}, ActionType.AA, 1),
        (1, {StatusType.STUN: [(2, 0)]}, ActionType.AA, 2),
        (1.5, {StatusType.STUN: [(2, 0)]}, ActionType.AA, 2),
        (2.5, {StatusType.STUN: [(2, 0)]}, ActionType.AA, 2.5),
        (1, {StatusType.STUN: [(2, 0)], StatusType.DISARM: [(2.5, 0)]}, ActionType.AA, 2.5),
        (1, {StatusType.AIRBORNE: [(2, 0)], StatusType.STUN: [(2.5, 0)]}, ActionType.AA, 2.5),
        (1, {StatusType.STUN: [(2, 0)], StatusType.SILENCE: [(2.5, 0)]}, ActionType.Q, 2.5),
        (1, {StatusType.STUN: [(2, 0)], StatusType.DISARM: [(2.5, 0)]}, ActionType.Q, 2),
    ])
    def test_check_action_delay(self, aatrox_with_items, cooldown, status_effects, action, delay):
        aatrox_with_items.status_effects = status_effects
        aatrox_with_items.cooldowns[action] = cooldown
        result = aatrox_with_items.check_action_delay(action, 1)
        assert result == delay


    def test_basic_attack(self, aatrox_with_items, action_effect_aa, compare_objects):
        result = aatrox_with_items._basic_attack(Actor.RED, 0)
        assert compare_objects(result, action_effect_aa)
        assert round(aatrox_with_items.cooldowns[ActionType.AA], 3) == 1.092


    def test_do_ability(self, aatrox_with_items, action_effect_q, compare_objects):
        aatrox_with_items.cooldowns[ActionType.Q] = 1
        result = aatrox_with_items._do_ability(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), 1)
        assert compare_objects(result, action_effect_q)
        assert round(aatrox_with_items.cooldowns[ActionType.Q], 3) == 3.029


    @pytest.mark.parametrize("action, timer, resolve_fixture", [
        (Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), 0, "action_effect_aa"),
        (Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), 1, "action_effect_q")
    ], indirect=["resolve_fixture"])
    def test_do_action(self, aatrox_with_items, action, timer, resolve_fixture, compare_objects):
        result = aatrox_with_items.do_action(action, timer)
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


    def test_take_effects(self, aatrox_with_items, q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat):
        aatrox_with_items.take_effects([q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat], 0)
        assert round(aatrox_with_items.damage_taken, 3) == 175.372
        assert round(aatrox_with_items.hp, 3) == 1302.26