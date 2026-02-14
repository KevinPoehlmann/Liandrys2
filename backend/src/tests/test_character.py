import pytest
from collections import defaultdict

from src.server.models.dataenums import Stat, ActionType, Actor, DamageSubType, DamageType, HpScaling, StatusType
from src.server.models.request import Action




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
        ([(60, 0.2)], 0.8),
        ([(60, 0.2), (90, 0.5), (120, 0.4)], 0.5)
    ])
    def test_get_slow_value(self, aatrox_with_items, slow_list, slow):
        aatrox_with_items.status_effects[StatusType.SLOW] = slow_list
        result = aatrox_with_items._get_slow_value()
        assert result == slow

    @pytest.mark.parametrize("cripple_list, cripple", [
        ([], 1),
        ([(60, 0.2)], 0.8),
        ([(60, 0.2), (90, 0.3)], 0.56),
    ])
    def test_get_cripple_value(self, aatrox_with_items, cripple_list, cripple):
        aatrox_with_items.status_effects[StatusType.CRIPPLE] = cripple_list
        result = aatrox_with_items._get_cripple_value()
        assert round(result, 2) == cripple


    @pytest.mark.parametrize("initial_stati, tick, expected_stati", [
        ({}, 1, {}),
        ({StatusType.STUN: [(60, 1)]}, 30, {StatusType.STUN: [(60, 1)]}),
        ({StatusType.STUN: [(60, 1)]}, 60, {}),
        ({StatusType.STUN: [(60, 1), (90, 1)]}, 60, {StatusType.STUN: [(90, 1)]}),
        ({StatusType.STUN: [(60, 1), (90, 1)], StatusType.SILENCE: [(30, 1)], StatusType.BLIND: [(75, 1)]}, 60, {StatusType.STUN: [(90, 1)], StatusType.BLIND: [(75, 1)]}),
    ])
    def test_remove_expired_status_effects(self, aatrox_with_items, initial_stati, tick, expected_stati):
        aatrox_with_items.status_effects = defaultdict(list, initial_stati)
        aatrox_with_items._remove_expired_status_effects(tick)
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


    @pytest.mark.parametrize("processed_damage_props, output_res, output_raw, output_mit", [
        ({
            "val": 100,
            "flat_pen": 10,
            "perc_pen": 0.5,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.PHYSIC,
            "hp_scaling": HpScaling.FLAT
        }, 67.152, 100, 32.848),
        ({
            "val": 0.1,
            "flat_pen": 18,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.MAGIC,
            "hp_scaling": HpScaling.MAX_HP
        }, 108.22, 130.226, 22.006),
        ({
            "val": 0.3,
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE,
            "hp_scaling": HpScaling.MISSING_HP
        }, 120.678, 120.678, 0),
        ({
            "val": 0.08,
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE,
            "hp_scaling": HpScaling.CURRENT_HP
        }, 72.0, 72.0, 0)
    ], indirect=["processed_damage_props"])
    def test_calculate_damage(self, aatrox_with_items, processed_damage_props, output_res, output_raw, output_mit):
        aatrox_with_items.hp = 900
        result, raw, mitigated = aatrox_with_items._calculate_damage(processed_damage_props)
        assert round(result, 3) == output_res
        assert round(raw, 3) == output_raw
        assert round(mitigated, 3) == output_mit



    @pytest.mark.parametrize("input, expected_damage, expected_shields, expected_absorbed", [
        (120, 0, (0, 30), (50, 70)),
        (200, 50, (0, 0), (50, 100)),
    ])
    def test_use_shields(self, aatrox_with_items, input, expected_damage, expected_shields, expected_absorbed):
        aatrox_with_items.shields = [(60, 50, ActionType.Q, Actor.BLUE), (90, 100, ActionType.W, Actor.BLUE)]
        damage, results = aatrox_with_items._use_shields(input, Actor.BLUE)
        assert damage == expected_damage
        assert results[0].value == expected_absorbed[0]
        assert results[1].value == expected_absorbed[1]
        assert aatrox_with_items.shields == [(60, expected_shields[0], ActionType.Q, Actor.BLUE), (90, expected_shields[1], ActionType.W, Actor.BLUE)]

    @pytest.mark.parametrize("hp_subtraction, queue_heal_list, hp, healed", [
        (100, {"values": [100]}, 1302.26, 100),
        (50, {"values": [20, 40]}, 1302.26, 50),
        (200, {"values": [50, 25, 25]}, 1202.26, 100),
        (100, {"values": []}, 1202.26, 0)
    ], indirect=["queue_heal_list"])
    def test_apply_heals(self, aatrox_with_items, hp_subtraction, queue_heal_list, hp, healed):
        aatrox_with_items.hp -= hp_subtraction
        aatrox_with_items._apply_heals(queue_heal_list)
        assert aatrox_with_items.hp == hp
        assert aatrox_with_items.healed == healed


    @pytest.mark.parametrize("initial_shields, queue_shield_list, expected_shields", [
        ([], {"values":[(90, 50)]}, [(120, 50, ActionType.W, Actor.BLUE)]),
        ([(150, 100, ActionType.W, Actor.BLUE)], {"values":[(90, 50)]}, [(120, 50, ActionType.W, Actor.BLUE), (150, 100, ActionType.W, Actor.BLUE)]),
        ([(150, 100, ActionType.W, Actor.BLUE)], {"values":[(90, 50), (150, 20)]}, [(120, 50, ActionType.W, Actor.BLUE), (150, 100, ActionType.W, Actor.BLUE), (180, 20, ActionType.W, Actor.BLUE)]),
        ([(15, 50, ActionType.W, Actor.BLUE), (150, 100, ActionType.W, Actor.BLUE)], {"values":[(90, 50)]}, [(120, 50, ActionType.W, Actor.BLUE), (150, 100, ActionType.W, Actor.BLUE)]),
        ([(90, -10, ActionType.W, Actor.BLUE)], {"values":[]}, []),
    ], indirect=["queue_shield_list"])
    def test_apply_shields(self, aatrox_with_items, initial_shields, queue_shield_list, expected_shields):
        aatrox_with_items.shields = initial_shields
        aatrox_with_items._apply_shields(queue_shield_list, 30)
        assert aatrox_with_items.shields == expected_shields

    @pytest.mark.parametrize("initial_shields, queue_damage_list, damage_taken, damage_shielded, hp, expected_shields", [
        ([], {"values":[50, 50]}, 100, 0, 1202.26, []),
        ([(60, 50, ActionType.Q, Actor.BLUE), (90, 100, ActionType.W, Actor.BLUE)], {"values":[200]}, 50, 150, 1252.26, [(60, 0, ActionType.Q, Actor.BLUE), (90, 0, ActionType.W, Actor.BLUE)]),
        ([(60, 50, ActionType.Q, Actor.BLUE), (90, 100, ActionType.W, Actor.BLUE)], {"values":[100]}, 0, 100, 1302.26, [(60, 0, ActionType.Q, Actor.BLUE), (90, 50, ActionType.W, Actor.BLUE)]),
    ], indirect=["queue_damage_list"])
    def test_apply_damages(self, aatrox_with_items, initial_shields, queue_damage_list, damage_taken, damage_shielded, hp, expected_shields):
        aatrox_with_items.shields = initial_shields
        queue_res, effect_res = aatrox_with_items._apply_damages(queue_damage_list)
        assert aatrox_with_items.damage_taken == damage_taken
        assert aatrox_with_items.damage_shielded == damage_shielded
        assert aatrox_with_items.hp == hp
        assert aatrox_with_items.shields == expected_shields
        assert queue_res == []
        assert effect_res[0].raw == queue_damage_list[0].props.value

    def test_apply_vamps(self, aatrox_with_items, q_processed_vamp, q_processed_vamp_heal, compare_objects):
        queue_results, effect_results = aatrox_with_items._apply_damages([q_processed_vamp])
        assert compare_objects(queue_results[0], q_processed_vamp_heal)

    @pytest.mark.parametrize("initial_stati, queue_status_list, expected_stati", [
        ({}, {"values":[(StatusType.STUN, 60)]}, {StatusType.STUN: [(90, 0)]}),
        ({StatusType.STUN: [(60, 0)]}, {"values":[(StatusType.STUN, 60)]}, {StatusType.STUN: [(60, 0), (90, 0)]}),
        ({StatusType.STUN: [(60, 0)]}, {"values":[(StatusType.SILENCE, 60)]}, {StatusType.STUN: [(60, 0)], StatusType.SILENCE: [(90, 0)]}),
    ], indirect=["queue_status_list"])
    def test_apply_status_effects(self, aatrox_with_items, initial_stati, queue_status_list, expected_stati):
        aatrox_with_items.status_effects = defaultdict(list, initial_stati)
        aatrox_with_items._apply_status_effects(queue_status_list, 30)
        assert aatrox_with_items.status_effects == expected_stati


    @pytest.mark.parametrize("cooldown, status_effects, action, delay", [
        (30, {}, ActionType.AA, 30),
        (60, {}, ActionType.AA, 60),
        (30, {StatusType.SILENCE: [(60, 0)]}, ActionType.AA, 30),
        (30, {StatusType.STUN: [(60, 0)]}, ActionType.AA, 60),
        (45, {StatusType.STUN: [(60, 0)]}, ActionType.AA, 60),
        (75, {StatusType.STUN: [(60, 0)]}, ActionType.AA, 75),
        (30, {StatusType.STUN: [(60, 0)], StatusType.DISARM: [(75, 0)]}, ActionType.AA, 75),
        (30, {StatusType.AIRBORNE: [(60, 0)], StatusType.STUN: [(75, 0)]}, ActionType.AA, 75),
        (30, {StatusType.STUN: [(60, 0)], StatusType.SILENCE: [(75, 0)]}, ActionType.Q, 75),
        (30, {StatusType.STUN: [(60, 0)], StatusType.DISARM: [(75, 0)]}, ActionType.Q, 60),
    ])
    def test_check_action_delay(self, aatrox_with_items, cooldown, status_effects, action, delay):
        aatrox_with_items.status_effects = defaultdict(list, status_effects)
        aatrox_with_items.cooldowns[action] = cooldown
        result = aatrox_with_items.check_action_delay(action, 30)
        assert result == delay


    def test_basic_attack(self, aatrox_with_items, action_effect_aa, compare_objects):
        result = aatrox_with_items._basic_attack(Actor.RED, 0)
        assert compare_objects(result, action_effect_aa)
        assert aatrox_with_items.cooldowns[ActionType.AA] == 33


    def test_do_ability(self, aatrox_with_items, action_effect_q, compare_objects):
        aatrox_with_items.cooldowns[ActionType.Q] = 30
        result = aatrox_with_items._do_ability(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), 30)
        assert compare_objects(result, action_effect_q)
        assert aatrox_with_items.cooldowns[ActionType.Q] == 91


    @pytest.mark.parametrize("action, timer, resolve_fixture", [
        (Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), 0, "action_effect_aa"),
        (Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), 30, "action_effect_q")
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