from dataclasses import dataclass, field, replace

import pytest

from src.server.models.enums import ActionType, Stat
from src.server.simulation.formula import FormulaContext, FormulaError, evaluate_formula


@dataclass
class FakeSource:
    level: int = 6
    current_hp: float = 500
    is_champion: bool = True
    is_ranged: bool = False
    stats: dict[Stat, float] = field(default_factory=dict)
    base_stats: dict[Stat, float] = field(default_factory=dict)
    ranks: dict[ActionType, int] = field(default_factory=dict)
    buff_stacks: dict[str, int] = field(default_factory=dict)
    buff_elapsed: dict[str, float] = field(default_factory=dict)

    def get_stat(self, stat: Stat) -> float:
        return self.stats.get(stat, 0)

    def get_base_stat(self, stat: Stat) -> float:
        return self.base_stats.get(stat, 0)

    def get_rank(self, slot: ActionType) -> int:
        return self.ranks.get(slot, 0)

    def get_buff_stacks(self, buff: str) -> int:
        return self.buff_stacks.get(buff, 0)

    def get_buff_elapsed(self, buff: str) -> float:
        return self.buff_elapsed.get(buff, 0)

    def get_cooldown(self, slot: ActionType) -> float:
        return {ActionType.Q: 4.5}[slot]

    def get_cooldown_multiplier(self, slot: ActionType) -> float:
        return {ActionType.Q: 0.75}[slot]


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


    def test_mana_variables(self):
        context = FormulaContext(source=FakeSource(stats={Stat.MANA: 1200}, base_stats={Stat.MANA: 900}))

        assert evaluate_formula("max_mana", context) == 1200
        assert evaluate_formula("base_mana", context) == 900
        assert evaluate_formula("bonus_mana", context) == 300


    def test_crit_damage_variables(self):
        context = FormulaContext(source=FakeSource(stats={Stat.CRIT_DAMAGE: 2.3}, base_stats={Stat.CRIT_DAMAGE: 2.0}))

        assert evaluate_formula("crit_damage", context) == 2.3
        assert evaluate_formula("bonus_crit_damage", context) == pytest.approx(0.3)


    def test_hp_variables(self, darius):
        context = FormulaContext(source=darius)

        assert evaluate_formula("current_hp", context) == 900
        assert evaluate_formula("missing_hp", context) == 300
        assert evaluate_formula("missing_hp_percent", context) == 0.25
        assert evaluate_formula("current_hp_percent", context) == 0.75


    def test_bonus_movespeed_stops_at_zero(self):
        hasted = FakeSource(stats={Stat.MOVESPEED: 420}, base_stats={Stat.MOVESPEED: 345})
        slowed = FakeSource(stats={Stat.MOVESPEED: 200}, base_stats={Stat.MOVESPEED: 345})

        assert evaluate_formula("bonus_movespeed", FormulaContext(source=hasted)) == 75
        assert evaluate_formula("bonus_movespeed", FormulaContext(source=slowed)) == 0


    def test_life_steal_heal_shield_power_and_bonus_attack_range(self):
        source = FakeSource(stats={Stat.LIFE_STEAL_P: 0.1, Stat.HEAL_N_SHIELD_P: 0.08, Stat.ATTACK_RANGE: 650},
                            base_stats={Stat.ATTACK_RANGE: 350})
        context = FormulaContext(source=source)

        assert evaluate_formula("life_steal", context) == 0.1
        assert evaluate_formula("heal_shield_power", context) == 0.08
        assert evaluate_formula("bonus_attack_range", context) == 300


    def test_target_variables_read_the_target(self, vayne, darius):
        context = FormulaContext(source=vayne, target=darius)

        assert evaluate_formula("0.06 * target_max_hp", context) == pytest.approx(72)
        assert evaluate_formula("target_stacks_silver_bolts", context) == 2


    def test_context_variables(self, vayne):
        context = FormulaContext(source=vayne, rank=2, stacks=3)

        assert evaluate_formula("level + rank + stacks", context) == 11
        assert evaluate_formula("rank_q * 10 + rank_w", context) == 31
        assert evaluate_formula("stacks_tumble", context) == 1


    def test_elapsed_share_of_a_buff(self, vayne, darius):
        vayne.buff_elapsed = {"tumble": 0.25}
        context = FormulaContext(source=vayne, target=darius)

        assert evaluate_formula("2 * elapsed_tumble", context) == 0.5
        assert evaluate_formula("elapsed_final_hour + target_elapsed_tumble", context) == 0


    def test_inactive_buff_has_zero_stacks(self, vayne):
        assert evaluate_formula("stacks_final_hour", FormulaContext(source=vayne)) == 0


    def test_scenario_inputs_are_variables(self, vayne):
        assert evaluate_formula("terrain", FormulaContext(source=vayne, scenario={"terrain": 1})) == 1


    def test_cooldown_is_the_cooldown_of_the_formulas_slot(self, vayne):
        assert evaluate_formula("cooldown", FormulaContext(source=vayne, slot=ActionType.Q)) == 4.5


    def test_cooldown_needs_a_slot(self, vayne):
        with pytest.raises(FormulaError):
            evaluate_formula("cooldown", FormulaContext(source=vayne))


    def test_cooldown_multiplier_is_the_haste_factor_of_the_formulas_slot(self, vayne):
        # Miss Fortune's Love Tap refunds LoveTapBaseRefund × the haste factor of her W.
        context = FormulaContext(source=vayne, slot=ActionType.Q)

        assert evaluate_formula("2 * cooldown_multiplier", context) == 1.5
        with pytest.raises(FormulaError):
            evaluate_formula("cooldown_multiplier", FormulaContext(source=vayne))


    def test_elapsed_is_a_variable(self, vayne):
        assert evaluate_formula("1 - elapsed / 1.5", FormulaContext(source=vayne, elapsed=0.75)) == 0.5


    def test_builtins_min_max(self, vayne, darius):
        context = FormulaContext(source=vayne, target=darius, rank=1, max_rank=5)
        formula = "max(by_rank(0.06, 0.07, 0.08, 0.09, 0.10) * target_max_hp, by_rank(50, 65, 80, 95, 110))"

        assert evaluate_formula(formula, context) == pytest.approx(72)


    @pytest.mark.parametrize("buff, result", [("tumble", 100), ("final_hour", 0)])
    def test_conditional_on_a_buff(self, vayne, buff, result):
        # The loader's translation of Riot's GameCalculationConditional (Jax W while empowered).
        assert evaluate_formula(f"ad if stacks_{buff} > 0 else 0", FormulaContext(source=vayne)) == result


    @pytest.mark.parametrize("stacks, result", [(49, 0), (50, 1), (149, 2)])
    def test_builtin_floor(self, vayne, stacks, result):
        vayne.buff_stacks["evil"] = stacks
        context = FormulaContext(source=vayne)

        assert evaluate_formula("floor(stacks_evil / 50)", context) == result


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


@dataclass
class FakeValues:
    values: dict[ActionType, dict[str, str]]
    ranks: dict[ActionType, int]
    max_ranks: dict[ActionType, int]

    def named_values(self, slot: ActionType) -> dict[str, str]:
        return self.values.get(slot, {})

    def get_rank(self, slot: ActionType) -> int:
        return self.ranks.get(slot, 0)

    def get_max_rank(self, slot: ActionType) -> int:
        return self.max_ranks.get(slot, 0)


@pytest.fixture
def vayne_values():
    return FakeValues(
        values={
            ActionType.Q: {"TotalADRatio": "by_rank(0.75, 0.85, 0.95, 1.05, 1.15)", "ADRatioBonus": "TotalADRatio * ad"},
            ActionType.R: {"TumbleCDReduction": "by_rank(30, 40, 50)"},
            ActionType.W: {"Loop": "Loop + 1", "PingA": "PingB", "PingB": "PingA"},
        },
        ranks={ActionType.Q: 3, ActionType.R: 2, ActionType.W: 1},
        max_ranks={ActionType.Q: 5, ActionType.R: 3, ActionType.W: 5},
    )


def values_context(source, values: FakeValues, slot: ActionType) -> FormulaContext:
    return FormulaContext(source=source, slot=slot, rank=values.get_rank(slot), max_rank=values.get_max_rank(slot), values=values)


class TestNamedValues():

    def test_name_resolves_at_the_slots_rank(self, vayne, vayne_values):
        assert evaluate_formula("TotalADRatio", values_context(vayne, vayne_values, ActionType.Q)) == 0.95


    def test_names_can_use_other_names_and_stats(self, vayne, vayne_values):
        assert evaluate_formula("ADRatioBonus", values_context(vayne, vayne_values, ActionType.Q)) == pytest.approx(95)


    def test_prefix_reads_another_slot_at_its_own_rank(self, vayne, vayne_values):
        assert evaluate_formula("r.TumbleCDReduction / 100", values_context(vayne, vayne_values, ActionType.Q)) == 0.4


    def test_unknown_name_is_an_unknown_variable(self, vayne, vayne_values):
        with pytest.raises(FormulaError, match="Unknown variable"):
            evaluate_formula("TumbleCDReduction", values_context(vayne, vayne_values, ActionType.Q))


    def test_unknown_prefixed_name_is_reported(self, vayne, vayne_values):
        with pytest.raises(FormulaError, match="Unknown named value 'r.BaseDamage'"):
            evaluate_formula("r.BaseDamage", values_context(vayne, vayne_values, ActionType.Q))


    @pytest.mark.parametrize("formula", ["Loop", "PingA"])
    def test_cycles_are_reported(self, vayne, vayne_values, formula):
        with pytest.raises(FormulaError, match="refers to itself"):
            evaluate_formula(formula, values_context(vayne, vayne_values, ActionType.W))


    def test_pets_read_named_values_from_their_owners_view(self, vayne, vayne_values):
        pet = FakeSource(stats={Stat.AD: 10})
        context = replace(values_context(vayne, vayne_values, ActionType.Q), source=pet, owner=vayne)

        assert evaluate_formula("ADRatioBonus + ad", context) == pytest.approx(95 + 10)


    def test_own_variables_come_before_named_values(self, vayne):
        values = FakeValues(values={ActionType.Q: {"ad": "1"}}, ranks={}, max_ranks={})

        assert evaluate_formula("ad", values_context(vayne, values, ActionType.Q)) == 100


class TestErrors():

    @pytest.mark.parametrize("formula", ["bonus_attack_damage", "target_ad", "target_target_ad"])
    def test_unknown_variable_names_the_formula(self, vayne, formula):
        with pytest.raises(FormulaError, match=f"Unknown variable in formula '{formula}'"):
            evaluate_formula(formula, FormulaContext(source=vayne))


    @pytest.mark.parametrize("formula", ["0.5 *", "__import__('os')", "open('x')"])
    def test_invalid_or_unsafe_formula_is_rejected(self, vayne, formula):
        with pytest.raises(FormulaError):
            evaluate_formula(formula, FormulaContext(source=vayne))
