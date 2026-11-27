import pytest

from src.server.loader.dash_hint import DASH_TAG, dash_hint, wiki_formula
from src.server.models.ability import DashHint
from src.server.models.champion import WikiTemplate


DASH = {"mSpellTags": ["PositiveEffect_MoveBlock", DASH_TAG]}
NO_DASH = {"mSpellTags": ["Trait_DamageAbility"]}


def template(*lines: str) -> WikiTemplate:
    return WikiTemplate(title="Template:Data_X/Y", revision_id=1, text="\n".join(["{{Ability data", *lines, "}}"]))


class TestDashHint():

    def test_vayne_tumble(self):
        wiki = template("|range        = {{tt|300|Dash distance}}",
                        "|speed        = {{tt|500 + {{as|100% movement speed}}|Dash speed}}")

        assert dash_hint(DASH, wiki) == DashHint(distance="300", speed="500 + movespeed")


    def test_urgot_disdain_has_no_plain_distance(self):
        # The range field is a min/max list; only the speed is usable.
        wiki = template("|target range = {{dv|{{tt|475|Maximum range}}|{{tt|450|Minimum range}}}}",
                        "|speed        = {{tt|1200 + {{as|100% movement speed}}|Dash speed}}")

        assert dash_hint(DASH, wiki) == DashHint(distance=None, speed="1200 + movespeed")


    def test_a_plain_range_counts_only_for_a_tagged_dash(self):
        wiki = template("|range        = 250")

        assert dash_hint(DASH, wiki) == DashHint(distance="250")
        assert dash_hint(NO_DASH, wiki) is None


    def test_pounce_is_marked_without_values(self):
        wiki = template("|target range = {{dv|{{tt|375|Standard range}}|{{tt|750|Enhanced range}}}}")

        assert dash_hint(DASH, wiki) == DashHint()


    def test_a_dash_speed_marks_an_untagged_ability(self):
        assert dash_hint(NO_DASH, template("|speed = {{tt|1450|Dash speed}}")) == DashHint(speed="1450")


    def test_a_missile_speed_is_no_dash(self):
        assert dash_hint(NO_DASH, template("|speed        = 2200")) is None
        assert dash_hint(NO_DASH, None) is None


    @pytest.mark.parametrize("text, formula", [
        ("500", "500"),
        ("500 + {{as|100% movement speed}}", "500 + movespeed"),
        ("{{as|150% bonus movement speed}} + 800", "1.5 * bonus_movespeed + 800"),
        ("1000 / 1200 / 1400", None),
        ("{{ap|300 to 500}}", None),
        ("varies", None),
    ])
    def test_wiki_formula(self, text, formula):
        assert wiki_formula(text) == formula
