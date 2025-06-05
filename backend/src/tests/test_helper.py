import pytest

from src.server.models.dataenums import HpScaling, Stat, EffectType, DamageSubType
from src.server.loader.helper import (
    info_loader,
    riot_to_wiki_patch,
    wiki_to_riot_patch,
    parse_formula_from_table,
    parse_formula_from_string,
    parse_formula_from_list,
    parse_effect_formula,
    find_stat,
    find_label
)
from src.server.loader.patchexceptions import PatcherError, ScrapeError






def test_info_loader():
    urls = info_loader().urls
    assert urls.patches == "https://ddragon.leagueoflegends.com/api/versions.json"



@pytest.mark.parametrize(
    "riot_patch, expected_wiki_patch", [
        ("15.7.1", "V25.07"),
        ("15.10.2", "V25.10")
    ],
)
def test_riot_to_wiki_patch(riot_patch, expected_wiki_patch):
    result = riot_to_wiki_patch(riot_patch)
    assert result == expected_wiki_patch

@pytest.mark.parametrize(
    "invalid_patch", [
        ("15."), ("abc.2.1"), ("15.abc.1"), (""), (15)
    ]
)
def test_riot_to_wiki_patch_invalid_format(invalid_patch):
    with pytest.raises(PatcherError):
        riot_to_wiki_patch(invalid_patch)


@pytest.mark.parametrize(
    "wiki_patch, expected_riot_patch", [
        ("V25.07", "15.7.1"),
        ("v14.10", "14.10.1"),
        ("V25.S1.3", "15.3.1")
    ],
)
def test_wiki_to_riot_patch(wiki_patch, expected_riot_patch):
    result = wiki_to_riot_patch(wiki_patch)
    assert result == expected_riot_patch

@pytest.mark.parametrize(
    "invalid_patch", [
        ("25.07"),       # Missing 'V'
        ("V25"),         # Missing minor version
        ("V25.abc"),     # Invalid minor version
        ("V"),           # Totally broken
        (""),            # Empty
        (25),            # Not a string
    ]
)
def test_wiki_to_riot_patch_invalid_format(invalid_patch):
    with pytest.raises(PatcherError):
        wiki_to_riot_patch(invalid_patch)




@pytest.mark.parametrize(
    "bot_values, top_values, scale, expected",
    [
        # Basic linear scaling
        ("22;21.29;20.59;19.88;19.18;18.47;17.76;17.06;16.35;15.65;14.94;14.24;13.53;12.82;12.12;11.41;10.71;10",
         "",
         "level",
         "22.0 + ((level - 1) // 1.0) * -0.7058823529411765"),
        
        # Nonlinear scaling with a single value
        ("30;24;18;12",
         "1;6;11;16",
         "level",
         "30.0 + ((level - 1.0) // 5.0) * -6.0"),
    ]
)
def test_parse_formula_from_table(bot_values, top_values, scale, expected):
    result = parse_formula_from_table(bot_str=bot_values, top_str=top_values, scale=scale)
    assert result == expected


@pytest.mark.parametrize(
    "string, scale, expected",
    [
        ("60 / 65 / 70 / 75 / 80 Mana",
         "rank",
         "60.0 + (rank - 1) * 5.0"),
        
        ("11 / 10 / 9 / 8 / 7", 
         "rank",
         "11.0 + (rank - 1) * -1.0"),
        
        ("60 Mana + all charges", 
         "rank",
         "60 Mana + all charges"),
        
        ("Damage scales with love and moonlight", 
         "rank",
         "Damage scales with love and moonlight"),
    ]
)
def test_parse_formula_from_string(string, scale, expected):

    result = parse_formula_from_string(string, scale)
    assert result == expected



@pytest.mark.parametrize(
    "string, expected",
    [
        ([60, 70, 80, 90, 100], "60 + (rank - 1) * 10.0")
    ]
)
def test_parse_formula_from_list(string, expected):
    result = parse_formula_from_list(string)
    assert result == expected



@pytest.mark.parametrize(
    "stat, expected_stat, hp_scaling, percent",
    [
        ("AP", Stat.AP, HpScaling.FLAT, False),
        ("bonus AD", Stat.BONUS_AD, HpScaling.FLAT, False),
        ("per 100 AP", Stat.AP, HpScaling.FLAT, True),
        ("of target's maximum health", Stat.FLAT, HpScaling.MAX_HP, False),
        (" of target's current health", Stat.FLAT, HpScaling.CURRENT_HP, False),
        ("of target's missing health", Stat.FLAT, HpScaling.MISSING_HP, False),
        ("Love and moonlight", Stat.ERROR, HpScaling.FLAT, False)
    ]
)
def test_find_stat(stat, expected_stat, hp_scaling, percent):
    result_stat, result_hp, result_percent = find_stat(stat)
    assert result_stat == expected_stat
    assert result_hp == hp_scaling
    assert result_percent == percent


@pytest.mark.parametrize(
    "string, expected, expected_hp", [
        ("80 / 115 / 150 / 185 / 220 ", "80.0 + (rank - 1) * 35.0", HpScaling.FLAT),
        ("(+ 80% AP)", "(0.8) * ap", HpScaling.FLAT),
        ("10 / 15 / 20% (+ 2.5% per 100 AP) of target's maximum health", "0.1 + (rank - 1) * 0.05 + (0.00025) * ap", HpScaling.MAX_HP),
    ]
)
def test_parse_effect_formula(string, expected, expected_hp):
    result, hp_scaling = parse_effect_formula(string)
    assert result == expected
    assert hp_scaling == expected_hp


@pytest.mark.parametrize(
    "label, effect_type, dmg_sub_type",
    [
        ("Shield Strength:", EffectType.SHIELD, DamageSubType.TRUE),
        ("Total Magic Damage:", EffectType.DAMAGE, DamageSubType.MAGIC),
        ("Heal:", EffectType.HEAL, DamageSubType.TRUE)
    ]
)
def test_find_label(label, effect_type, dmg_sub_type):
    result_effect_type, result_dmg_sub_type = find_label(label)
    assert result_effect_type == effect_type
    assert result_dmg_sub_type == dmg_sub_type



@pytest.mark.parametrize(
    "label",
    [
        ("Health Cost Reduction:"),
        ("Bonus Armor:")
    ]
)
def test_find_label_invalid(label):
    with pytest.raises(ScrapeError):
        find_label(label)