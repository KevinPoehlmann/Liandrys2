import pytest
from collections import defaultdict

from src.server.models.enums import (
    Stat,
    ActionType,
    Actor,
    DamageSubType,
    DamageType,
    EffectType,
    StatusType
)
from src.server.simulation.components import ProcessedDamageProperties, QueueComponent
from src.server.models.request import Action
from src.server.simulation.character import soft_cap_movespeed




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
        result = aatrox_with_items._get_bonus_stat(stat)
        assert result == output

    @pytest.mark.parametrize("stat, output", [
        (Stat.AD, 120.45),
        (Stat.ABILITY_HASTE, 40),
    ])
    def test_get_stat(self, aatrox_with_items, stat, output):
        result = aatrox_with_items.get_stat(stat)
        assert round(result, 3) == output

    def test_get_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items._get_attackspeed()
        assert round(result, 3) == 0.916

    def test_bonus_attackspeed_includes_the_growth_per_level(self, aatrox_with_items):
        champion = aatrox_with_items.champion
        bonus = aatrox_with_items.get_stat(Stat.BONUS_ATTACKSPEED_P)

        assert bonus > aatrox_with_items._get_bonus_stat(Stat.ATTACKSPEED_P)
        assert champion.attackspeed + champion.attackspeed_ratio * bonus == pytest.approx(0.916, abs=0.001)

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
        result = aatrox_with_items._get_resistance(dmg_sub_type)
        assert round(result, 3) == output

    def test_cc_duration_factor_without_tenacity(self, aatrox_with_items):
        assert aatrox_with_items._cc_duration_factor() == 1

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


    @pytest.mark.parametrize("processed_damage_props, output_res, output_raw, output_mit", [
        ({
            "val": 100,
            "flat_pen": 10,
            "perc_pen": 0.5,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.PHYSIC
        }, 67.152, 100, 32.848),
        ({
            "val": 130.226,  # 10 % of 1302.26 maximum health
            "flat_pen": 18,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.MAGIC
        }, 108.22, 130.226, 22.006),
        ({
            "val": 120.678,  # 30 % of 402.26 missing health
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE
        }, 120.678, 120.678, 0),
        ({
            "val": 72.0,  # 8 % of 900 current health
            "flat_pen": 0,
            "perc_pen": 0,
            "dmg_type": DamageType.BASIC,
            "dmg_sub_type": DamageSubType.TRUE
        }, 72.0, 72.0, 0)
    ], indirect=["processed_damage_props"])
    def test_calculate_damage(self, aatrox_with_items, processed_damage_props, output_res, output_raw, output_mit):
        aatrox_with_items.current_hp = 900
        result, raw, mitigated = aatrox_with_items._calculate_damage(processed_damage_props)
        assert round(result, 3) == output_res
        assert round(raw, 3) == output_raw
        assert round(mitigated, 3) == output_mit



    @pytest.mark.parametrize("input, expected_damage, expected_shields, expected_absorbed", [
        (120, 0, (0, 30), (50, 70)),
        (200, 50, (0, 0), (50, 100)),
    ])
    def test_use_shields(self, aatrox_with_items, input, expected_damage, expected_shields, expected_absorbed):
        aatrox_with_items.shields = [(60, 50, ActionType.Q, Actor.BLUE, None), (90, 100, ActionType.W, Actor.BLUE, None)]
        damage, results = aatrox_with_items._use_shields(input, Actor.BLUE)
        assert damage == expected_damage
        assert results[0].value == expected_absorbed[0]
        assert results[1].value == expected_absorbed[1]
        assert aatrox_with_items.shields == [(60, expected_shields[0], ActionType.Q, Actor.BLUE, None), (90, expected_shields[1], ActionType.W, Actor.BLUE, None)]

    @pytest.mark.parametrize("hp_subtraction, queue_heal_list, hp, healed", [
        (100, {"values": [100]}, 1302.26, 100),
        (50, {"values": [20, 40]}, 1302.26, 50),
        (200, {"values": [50, 25, 25]}, 1202.26, 100),
        (100, {"values": []}, 1202.26, 0)
    ], indirect=["queue_heal_list"])
    def test_apply_heals(self, aatrox_with_items, hp_subtraction, queue_heal_list, hp, healed):
        aatrox_with_items.current_hp -= hp_subtraction
        aatrox_with_items._apply_heals(queue_heal_list)
        assert aatrox_with_items.current_hp == hp
        assert aatrox_with_items.healed == healed


    @pytest.mark.parametrize("hp_subtraction, queue_heal_list, heals, overheals", [
        (60, {"values": [50, 25, 25]}, [50, 10, 0], [0, 15, 25]),
        (0, {"values": [30]}, [0], [30]),
    ], indirect=["queue_heal_list"])
    def test_apply_heals_results(self, aatrox_with_items, hp_subtraction, queue_heal_list, heals, overheals):
        aatrox_with_items.current_hp -= hp_subtraction
        results = aatrox_with_items._apply_heals(queue_heal_list)
        assert [round(result.value, 3) for result in results] == heals
        assert [round(result.overheal, 3) for result in results] == overheals


    @pytest.mark.parametrize("initial_shields, queue_shield_list, expected_shields", [
        ([], {"values":[(90, 50)]}, [(120, 50, ActionType.W, Actor.BLUE, None)]),
        ([(150, 100, ActionType.W, Actor.BLUE, None)], {"values":[(90, 50)]}, [(120, 50, ActionType.W, Actor.BLUE, None), (150, 100, ActionType.W, Actor.BLUE, None)]),
        ([(150, 100, ActionType.W, Actor.BLUE, None)], {"values":[(90, 50), (150, 20)]}, [(120, 50, ActionType.W, Actor.BLUE, None), (150, 100, ActionType.W, Actor.BLUE, None), (180, 20, ActionType.W, Actor.BLUE, None)]),
        ([(15, 50, ActionType.W, Actor.BLUE, None), (150, 100, ActionType.W, Actor.BLUE, None)], {"values":[(90, 50)]}, [(120, 50, ActionType.W, Actor.BLUE, None), (150, 100, ActionType.W, Actor.BLUE, None)]),
        ([(90, -10, ActionType.W, Actor.BLUE, None)], {"values":[]}, []),
    ], indirect=["queue_shield_list"])
    def test_apply_shields(self, aatrox_with_items, initial_shields, queue_shield_list, expected_shields):
        aatrox_with_items.shields = initial_shields
        aatrox_with_items._apply_shields(queue_shield_list, 30)
        assert aatrox_with_items.shields == expected_shields

    @pytest.mark.parametrize("initial_shields, queue_damage_list, damage_taken, damage_shielded, hp, expected_shields", [
        ([], {"values":[50, 50]}, 100, 0, 1202.26, []),
        ([(60, 50, ActionType.Q, Actor.BLUE, None), (90, 100, ActionType.W, Actor.BLUE, None)], {"values":[200]}, 50, 150, 1252.26, [(60, 0, ActionType.Q, Actor.BLUE, None), (90, 0, ActionType.W, Actor.BLUE, None)]),
        ([(60, 50, ActionType.Q, Actor.BLUE, None), (90, 100, ActionType.W, Actor.BLUE, None)], {"values":[100]}, 0, 100, 1302.26, [(60, 0, ActionType.Q, Actor.BLUE, None), (90, 50, ActionType.W, Actor.BLUE, None)]),
    ], indirect=["queue_damage_list"])
    def test_apply_damages(self, aatrox_with_items, initial_shields, queue_damage_list, damage_taken, damage_shielded, hp, expected_shields):
        aatrox_with_items.shields = initial_shields
        queue_res, effect_res = aatrox_with_items._apply_damages(queue_damage_list)
        assert aatrox_with_items.damage_taken == damage_taken
        assert aatrox_with_items.damage_shielded == damage_shielded
        assert aatrox_with_items.current_hp == hp
        assert aatrox_with_items.shields == expected_shields
        assert queue_res == []
        assert effect_res[0].raw == queue_damage_list[0].props.value

    def test_apply_damages_reports_health_damage_after_shields(self, aatrox_with_items):
        aatrox_with_items.shields = [(60, 70, ActionType.W, Actor.BLUE, None)]
        queue_damage_list = [
            QueueComponent(ActionType.Q, Actor.RED, Actor.BLUE, EffectType.DAMAGE, ProcessedDamageProperties(
                value=value, flat_pen=0, percent_pen=0, dmg_type=DamageType.BASIC, dmg_sub_type=DamageSubType.TRUE))
            for value in [50, 50]
        ]
        _, results = aatrox_with_items._apply_damages(queue_damage_list)
        assert [(result.type_, result.value) for result in results] == [
            (EffectType.DAMAGE, 0), (EffectType.SHIELD, 50),
            (EffectType.DAMAGE, 30), (EffectType.SHIELD, 20),
        ]
        assert aatrox_with_items.damage_taken == 30

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


    @pytest.mark.parametrize("factor, duration, expected", [
        (1, 60, 60),
        (0.5, 60, 30),
        (0.1, 60, 10),  # floor of 0.3 seconds
        (0.1, 6, 6),  # already shorter than 0.3 seconds
    ])
    def test_apply_tenacity(self, aatrox_with_items, monkeypatch, factor, duration, expected):
        monkeypatch.setattr(aatrox_with_items, "_cc_duration_factor", lambda: factor)
        assert aatrox_with_items._apply_tenacity(duration) == expected


    @pytest.mark.parametrize("cooldown, status_effects, action, delay", [
        (30, {}, ActionType.BA, 30),
        (60, {}, ActionType.BA, 60),
        (30, {StatusType.SILENCE: [(60, 0)]}, ActionType.BA, 30),
        (30, {StatusType.STUN: [(60, 0)]}, ActionType.BA, 60),
        (45, {StatusType.STUN: [(60, 0)]}, ActionType.BA, 60),
        (75, {StatusType.STUN: [(60, 0)]}, ActionType.BA, 75),
        (30, {StatusType.STUN: [(60, 0)], StatusType.DISARM: [(75, 0)]}, ActionType.BA, 75),
        (30, {StatusType.AIRBORNE: [(60, 0)], StatusType.STUN: [(75, 0)]}, ActionType.BA, 75),
        (30, {StatusType.STUN: [(60, 0)], StatusType.SILENCE: [(75, 0)]}, ActionType.Q, 75),
        (30, {StatusType.STUN: [(60, 0)], StatusType.DISARM: [(75, 0)]}, ActionType.Q, 60),
    ])
    def test_check_action_delay(self, aatrox_with_items, cooldown, status_effects, action, delay):
        aatrox_with_items.status_effects = defaultdict(list, status_effects)
        aatrox_with_items.cooldowns[action] = cooldown
        result = aatrox_with_items.check_action_delay(action, 30)
        assert result == delay


    def test_basic_attack(self, aatrox_with_items, action_effect_aa, compare_objects):
        result = aatrox_with_items._basic_attack(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA), 0)
        assert compare_objects(result, action_effect_aa)
        assert aatrox_with_items.cooldowns[ActionType.BA] == 34


    def test_do_action(self, aatrox_with_items, action_effect_aa, compare_objects):
        result = aatrox_with_items.do_action(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.BA), 0)
        assert compare_objects(result, action_effect_aa)


    def test_take_effects_ignores_expired_shield(self, aatrox_with_items, q_processed_ad_flat):
        aatrox_with_items.shields = [(30, 1000, ActionType.W, Actor.BLUE, None)]
        aatrox_with_items.take_effects([q_processed_ad_flat], 60)
        assert aatrox_with_items.damage_shielded == 0
        assert aatrox_with_items.damage_taken > 0


    def test_take_effects(self, aatrox_with_items, q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat):
        aatrox_with_items.take_effects([q_processed_ad_flat, q_processed_ap_maxhp, q_processed_heal_flat], 0)
        assert round(aatrox_with_items.damage_taken, 3) == 175.372
        assert round(aatrox_with_items.current_hp, 3) == 1302.26

    @pytest.mark.parametrize("stat, sub_type", [
        (Stat.ARMOR_PEN_P, DamageSubType.PHYSIC),
        (Stat.MAGIC_PEN_P, DamageSubType.MAGIC)
    ])
    def test_percent_penetration_stacks_multiplicatively(self, aatrox_with_items, stat, sub_type):
        aatrox_with_items.items = [
            item.copy(update={"stats": {stat: value}})
            for item, value in zip(aatrox_with_items.items, [0.4, 0.3])
        ]
        _, percent_pen = aatrox_with_items.get_penetration(sub_type)
        assert percent_pen == pytest.approx(1 - 0.6 * 0.7)


@pytest.mark.parametrize("raw, capped", [
    (600, 530),  # wiki example
    (450, 443),
    (415, 415),
    (300, 300),
    (220, 220),
    (180, 200),  # wiki example
    (0, 110),
    (-10000, 10),  # wiki example
])
def test_soft_cap_movespeed(raw, capped):
    assert soft_cap_movespeed(raw) == pytest.approx(capped)
