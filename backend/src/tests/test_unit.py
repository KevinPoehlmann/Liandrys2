import pytest

from src.server.models.dataenums import Stat, ActionType



class TestDummy():

    def test_calculate_damage(self, dummy, damage):
        result = dummy.calculate_damage( damage, 220)
        assert result == 50


    def test_take_damage(self, dummy, damage):
        result = dummy.take_damge([damage, damage])
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


    def test_calculate_attackspeed(self, aatrox_with_items):
        result = aatrox_with_items.get_attackspeed()
        assert result == 0.92


    def test_basic_attack(self, aatrox_with_items):
        result = aatrox_with_items.basic_attack()
        assert result.value == 120.45
        assert result.flat_pen == 0
        assert result.perc_pen == 0


    def test_take_damage(self, aatrox_with_items, damage):
        result = aatrox_with_items.take_damge([damage, damage])
        assert result == 134.30
        assert aatrox_with_items.hp == 1167.96

    @pytest.mark.skip
    def test_do_ability(self, aatrox_with_items):
        result = aatrox_with_items.do_ability(ActionType.Q)
        assert result == 130.34
