import pytest

from src.server.models.dataenums import Stat, ActionType, DamageSubType, DamageType, DamageCalculation



class TestDummy():

    def test_calculate_damage(self, dummy, damage):
        result = dummy.calculate_damage( damage, 220)
        assert result == 50


    def test_take_damage(self, dummy, action_effect):
        result = dummy.take_damge(action_effect)
        assert result == 142.86
        assert dummy.hp == 857.14


class TestCharacter():

    def test_get_base_stat(self, aatrox_with_items):
        result = aatrox_with_items.get_base_stat(Stat.AD)
        assert result == 75.45

    def test_get_bonus_stat(self, aatrox_with_items):
        result = aatrox_with_items.get_bonus_stat(Stat.AD)
        assert result == 45

    def test_get_stat(self, aatrox_with_items):
        result = aatrox_with_items.get_stat(Stat.AD)
        assert result == 120.45

    def test_get_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items.get_attackspeed()
        assert result == 0.92

    def test_get_penetration(self, aatrox_with_items):
        result = aatrox_with_items.get_penetration(DamageSubType.PHYSIC)
        assert result == (0, 0)
        result = aatrox_with_items.get_penetration(DamageSubType.MAGIC)
        assert result == (0, 0)
        result = aatrox_with_items.get_penetration(DamageSubType.TRUE)
        assert result == (0, 0)


    def test_basic_attack(self, aatrox_with_items):
        result = aatrox_with_items.basic_attack()
        assert len(result.damages) == 1
        assert result.time == 0.21
        assert result.damages[0].value == 120.45
        assert result.damages[0].flat_pen == 0
        assert result.damages[0].percent_pen == 0
        assert result.damages[0].dmg_type == DamageType.BASIC
        assert result.damages[0].dmg_sub_type == DamageSubType.PHYSIC
        assert result.damages[0].dmg_calc == DamageCalculation.FLAT
        assert result.stati == []


    def test_take_damage(self, aatrox_with_items, action_effect):
        result = aatrox_with_items.take_damge(action_effect)
        assert result == 134.30
        assert aatrox_with_items.hp == 1167.96


    #@pytest.mark.skip
    def test_do_ability(self, aatrox_with_items):
        result = aatrox_with_items.do_ability(ActionType.Q)
        assert result.time == 0.6
        assert len(result.damages) == 1
        assert result.damages[0].value == 130.34
        assert result.damages[0].flat_pen == 0
        assert result.damages[0].percent_pen == 0
        assert result.damages[0].dmg_type == DamageType.AOE
        assert result.damages[0].dmg_sub_type == DamageSubType.PHYSIC
        assert result.damages[0].dmg_calc == DamageCalculation.FLAT


    def test_do_action(self, aatrox_with_items):
        result = aatrox_with_items.do_action(ActionType.AA)
        assert len(result.damages) == 1
        assert result.time == 0.21
        assert result.damages[0].value == 120.45
