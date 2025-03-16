import pytest

from src.server.models.dataenums import Stat, ActionType, DamageSubType, DamageType, DamageCalculation



class TestDummy():

    def test_get_stat(self, dummy):
        result = dummy.get_stat(Stat.HP)
        assert result == 1000
        result = dummy.get_stat(Stat.AD)
        assert result == 0


    def test_get_resistance(self, dummy):
        result = dummy.get_resistance(DamageSubType.PHYSIC)
        assert result == 100
        result = dummy.get_resistance(DamageSubType.MAGIC)
        assert result == 50
        result = dummy.get_resistance(DamageSubType.TRUE)
        assert result == 0

    
    @pytest.mark.parametrize("resolve_fixture, output", [
        ("damage_ad_flat", 71.429),
        ("damage_ap_maxhp", 75.758),
        ("damage_true_missinghp", 30.0),
        ("damage_true_currenthp", 72.0)
    ], indirect=["resolve_fixture"])
    def test_calculate_damage(self, dummy, resolve_fixture, output):
        dummy.hp = 900
        result = dummy.calculate_damage(resolve_fixture)
        assert result == output


    def test_take_damage(self, dummy, action_effect):
        dummy.take_damge(action_effect)
        assert dummy.damage_taken == 147.187
        assert dummy.hp == 852.813


class TestCharacter():

    def test_get_base_stat(self, aatrox_with_items):
        result = aatrox_with_items.get_base_stat(Stat.AD)
        assert result == 75.45

    def test_get_bonus_stat(self, aatrox_with_items):
        result = aatrox_with_items.get_bonus_stat(Stat.AD)
        assert result == 45
        result = aatrox_with_items.get_bonus_stat(Stat.ARMOR)
        assert result == 65

    def test_get_stat(self, aatrox_with_items):
        result = aatrox_with_items.get_stat(Stat.AD)
        assert result == 120.45
        result = aatrox_with_items.get_stat(Stat.SECONDS)
        assert result == 0

    def test_get_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items.get_attackspeed()
        assert result == 0.916

    def test_get_penetration(self, aatrox_with_items):
        result = aatrox_with_items.get_penetration(DamageSubType.PHYSIC)
        assert result == (0, 0)
        result = aatrox_with_items.get_penetration(DamageSubType.MAGIC)
        assert result == (0, 0)
        result = aatrox_with_items.get_penetration(DamageSubType.TRUE)
        assert result == (0, 0)

    def test_get_resistance(self, aatrox_with_items):
        result = aatrox_with_items.get_resistance(DamageSubType.PHYSIC)
        assert result == 117.832
        result = aatrox_with_items.get_resistance(DamageSubType.MAGIC)
        assert result == 38.334
        result = aatrox_with_items.get_resistance(DamageSubType.TRUE)
        assert result == 0


    def test_basic_attack(self, aatrox_with_items):
        result = aatrox_with_items.basic_attack()
        assert len(result.damages) == 1
        assert result.time == 0.215
        assert result.damages[0].value == 120.45
        assert result.damages[0].flat_pen == 0
        assert result.damages[0].percent_pen == 0
        assert result.damages[0].dmg_type == DamageType.BASIC
        assert result.damages[0].dmg_sub_type == DamageSubType.PHYSIC
        assert result.damages[0].dmg_calc == DamageCalculation.FLAT
        assert result.stati == []


    def test_take_damage(self, aatrox_with_items, action_effect):
        aatrox_with_items.take_damge(action_effect)
        assert aatrox_with_items.damage_taken == 175.372
        assert aatrox_with_items.hp == 1126.888


    def test_do_ability(self, aatrox_with_items):
        result = aatrox_with_items.do_ability(ActionType.Q)
        assert result.time == 0.6
        assert len(result.damages) == 1
        assert result.damages[0].value == 130.338
        assert result.damages[0].flat_pen == 0
        assert result.damages[0].percent_pen == 0
        assert result.damages[0].dmg_type == DamageType.AOE
        assert result.damages[0].dmg_sub_type == DamageSubType.PHYSIC
        assert result.damages[0].dmg_calc == DamageCalculation.FLAT


    def test_do_action(self, aatrox_with_items):
        result = aatrox_with_items.do_action(ActionType.AA)
        assert len(result.damages) == 1
        assert result.time == 0.215
        assert result.damages[0].value == 120.45
