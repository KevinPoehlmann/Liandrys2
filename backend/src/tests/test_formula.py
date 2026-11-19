from dataclasses import dataclass, field

import pytest

from src.server.models.dataenums import ActionType, Stat
from src.server.simulation.formula import FormulaContext, FormulaError, evaluate_formula


@dataclass
class FakeSource:
    level: int = 6
    current_hp: float = 500
    stats: dict[Stat, float] = field(default_factory=dict)
    base_stats: dict[Stat, float] = field(default_factory=dict)
    ranks: dict[ActionType, int] = field(default_factory=dict)
    buff_stacks: dict[str, int] = field(default_factory=dict)

    def get_stat(self, stat: Stat) -> float:
        return self.stats.get(stat, 0)

    def get_base_stat(self, stat: Stat) -> float:
        return self.base_stats.get(stat, 0)

    def get_rank(self, slot: ActionType) -> int:
        return self.ranks.get(slot, 0)

    def get_buff_stacks(self, buff: str) -> int:
        return self.buff_stacks.get(buff, 0)


@pytest.fixture
def vayne():
    return FakeSource(
        stats={Stat.AD: 100, Stat.HP: 1000},
        base_stats={Stat.AD: 70, Stat.HP: 1000},
        ranks={ActionType.Q: 3, ActionType.W: 1},
        buff_stacks={"tumble": 1},
    )

@pytest.fixture
def darius():
    return FakeSource(stats={Stat.HP: 1200, Stat.ARMOR: 50}, current_hp=900, buff_stacks={"silver_bolts": 2})


class TestVariables():

    def test_own_stats_and_bonus(self, vayne):
        context = FormulaContext(source=vayne)

        assert evaluate_formula("ad", context) == 100
        assert evaluate_formula("base_ad", context) == 70
        assert evaluate_formula("bonus_ad", context) == 30


    def test_hp_variables(self, darius):
        context = FormulaContext(source=darius)

        assert evaluate_formula("current_hp", context) == 900
        assert evaluate_formula("missing_hp", context) == 300
        assert evaluate_formula("missing_hp_percent", context) == 0.25


    def test_target_variables_read_the_target(self, vayne, darius):
        context = FormulaContext(source=vayne, target=darius)

        assert evaluate_formula("0.06 * target_max_hp", context) == pytest.approx(72)
        assert evaluate_formula("target_stacks_silver_bolts", context) == 2


    def test_context_variables(self, vayne):
        context = FormulaContext(source=vayne, rank=2, stacks=3)

        assert evaluate_formula("level + rank + stacks", context) == 11
        assert evaluate_formula("rank_q * 10 + rank_w", context) == 31
        assert evaluate_formula("stacks_tumble", context) == 1


    def test_inactive_buff_has_zero_stacks(self, vayne):
        assert evaluate_formula("stacks_final_hour", FormulaContext(source=vayne)) == 0


    def test_scenario_inputs_are_variables(self, vayne):
        assert evaluate_formula("terrain", FormulaContext(source=vayne, scenario={"terrain": 1})) == 1


    def test_elapsed_is_a_variable(self, vayne):
        assert evaluate_formula("1 - elapsed / 1.5", FormulaContext(source=vayne, elapsed=0.75)) == 0.5


    def test_builtins_min_max(self, vayne, darius):
        context = FormulaContext(source=vayne, target=darius, rank=1, max_rank=5)
        formula = "max(by_rank(0.06, 0.07, 0.08, 0.09, 0.10) * target_max_hp, by_rank(50, 65, 80, 95, 110))"

        assert evaluate_formula(formula, context) == pytest.approx(72)


class TestLookups():

    def test_by_rank_picks_the_current_rank(self, vayne):
        context = FormulaContext(source=vayne, rank=3, max_rank=5)

        assert evaluate_formula("by_rank(0.75, 0.85, 0.95, 1.05, 1.15) * ad", context) == pytest.approx(95)


    def test_several_tables_in_one_formula(self, vayne):
        context = FormulaContext(source=vayne, rank=2, max_rank=3)

        assert evaluate_formula("by_rank(50, 80, 110) + by_rank(1.0, 1.1, 1.2) * ad", context) == pytest.approx(190)


    def test_by_level_picks_the_source_level(self, vayne):
        context = FormulaContext(source=vayne)

        assert evaluate_formula(f"by_level({', '.join(str(n) for n in range(1, 21))})", context) == 6


    @pytest.mark.parametrize("formula, message", [
        ("by_rank(50, 80, 110)", "needs 5 values"),
        ("by_level(1, 2, 3)", "needs 20 values"),
    ])
    def test_wrong_table_length_is_rejected(self, vayne, formula, message):
        with pytest.raises(FormulaError, match=message):
            evaluate_formula(formula, FormulaContext(source=vayne, rank=1, max_rank=5))


    def test_by_rank_outside_abilities_is_rejected(self, vayne):
        with pytest.raises(FormulaError, match="only available in abilities"):
            evaluate_formula("by_rank(1, 2, 3)", FormulaContext(source=vayne))


    def test_by_rank_at_rank_zero_is_rejected(self, vayne):
        with pytest.raises(FormulaError, match="not learned"):
            evaluate_formula("by_rank(1, 2, 3)", FormulaContext(source=vayne, rank=0, max_rank=3))


class TestErrors():

    @pytest.mark.parametrize("formula", ["bonus_attack_damage", "target_ad", "target_target_ad"])
    def test_unknown_variable_names_the_formula(self, vayne, formula):
        with pytest.raises(FormulaError, match=f"Unknown variable in formula '{formula}'"):
            evaluate_formula(formula, FormulaContext(source=vayne))


    @pytest.mark.parametrize("formula", ["0.5 *", "__import__('os')", "open('x')"])
    def test_invalid_or_unsafe_formula_is_rejected(self, vayne, formula):
        with pytest.raises(FormulaError):
            evaluate_formula(formula, FormulaContext(source=vayne))
