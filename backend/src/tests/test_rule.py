import pytest
from pydantic import ValidationError

from src.server.models.champion import Champion
from src.server.models.dataenums import RuleActionType, Stat, Target, Trigger
from src.server.models.rule import ApplyBuffAction, Buff, DamageAction, ResetAttackAction, Rule, Stage


class TestRuleModels():

    def test_vayne_fixture_loads_in_new_format(self, load_champion):
        vayne = load_champion("vayne")

        tumble = vayne.q.buffs[0]
        assert vayne.q.cooldown_starts_after == "tumble"
        assert isinstance(vayne.q.stages[0].rules[0].actions[0], ApplyBuffAction)
        assert isinstance(vayne.q.stages[0].rules[0].actions[1], ResetAttackAction)
        assert tumble.rules[0].trigger == Trigger.ON_HIT
        assert isinstance(tumble.rules[0].actions[0], DamageAction)
        assert vayne.w.buffs[0].rules[0].actions[0].props.target == Target.BEARER
        assert vayne.r.buffs[0].stats[1].stat == Stat.Q_COOLDOWN_REDUCTION


    def test_round_trip_keeps_action_types(self, load_champion):
        vayne = load_champion("vayne")

        assert Champion.parse_obj(vayne.dict(by_alias=True)) == vayne


    def test_typo_in_action_field_is_rejected(self):
        with pytest.raises(ValidationError, match="extra fields not permitted"):
            Rule.parse_obj({"actions": [{"type_": "Damage", "props": {"target": "target", "scalling": "ad"}}]})


    def test_unknown_action_type_is_rejected(self):
        with pytest.raises(ValidationError, match="No match for discriminator"):
            Rule.parse_obj({"actions": [{"type_": "Explode", "props": {}}]})


    def test_nested_construction_without_parse_obj(self):
        rule = Rule(actions=[{"type_": RuleActionType.RESET_ATTACK}])

        assert isinstance(rule.actions[0], ResetAttackAction)


    @pytest.mark.parametrize("name", ["silver bolts", "3rd_hit", "final-hour"])
    def test_buff_name_must_be_identifier(self, name):
        with pytest.raises(ValidationError, match="valid identifier"):
            Buff(name=name)


    def test_rule_outcome_must_be_declared_by_the_stage(self):
        with pytest.raises(ValidationError, match="bladee"):
            Stage.parse_obj({"outcomes": ["blade", "handle"], "rules": [{"outcome": "bladee"}]})


    def test_stage_accepts_declared_outcomes(self):
        stage = Stage.parse_obj({"outcomes": ["blade", "handle"], "rules": [{"outcome": "handle"}, {}]})
        assert [rule.outcome for rule in stage.rules] == ["handle", None]
