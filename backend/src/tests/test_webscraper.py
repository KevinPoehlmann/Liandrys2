import pytest

from src.server.models.dataenums import AttackspeedStats, RangeType, ItemClass
from src.server.models.image import Image
from src.server.loader.webscraper import (
    get_hotfix_list,
    datetime,
    get_attackspeed_stats,
    get_side_box_stats,
    create_champion,
    create_item,
    create_rune,
    create_summonerspell
)




def test_get_hotfix_list():
    with open("src/tests/files/Patch1321.html", encoding="UTF-8") as patch1321:
        result = get_hotfix_list(patch1321)
        assert result == [datetime(2023, 10, 26), datetime(2023, 10, 27)]



@pytest.mark.parametrize("wiki, ats, output", [
    (pytest.lazy_fixture("aatrox_soup"), 0.651, AttackspeedStats(0.651,19.737)),
    (pytest.lazy_fixture("ashe_soup"), 0.658, AttackspeedStats(0.658,21.93,1,2500)),
    (pytest.lazy_fixture("yuumi_soup"), 0.625, AttackspeedStats(0.625,15.625)),
])
def test_get_attackspeed_stats(wiki, ats, output):
    stats = get_attackspeed_stats(wiki, ats)
    assert stats == output


@pytest.mark.parametrize("wiki, output", [
    (pytest.lazy_fixture("aatrox_soup"), ("13.20.1",RangeType.MELEE)),
    (pytest.lazy_fixture("ashe_soup"), ("13.12.1",RangeType.RANGED)),
])
def test_get_side_box_stats(wiki, output):
    tup = get_side_box_stats(wiki)
    assert tup == output


@pytest.mark.skip
def test_create_passive():
    pass


@pytest.mark.skip
def test_create_ability():
    pass


def test_create_champion(aatroxJson, aatrox_html):
    champion = create_champion(aatroxJson, aatrox_html, "13.22.1")
    assert champion.name == "Aatrox"
    assert champion.patch == "13.22.1"
    assert champion.passive.name == "Deathbringer Stance"
    assert champion.w.name == "Infernal Chains"


@pytest.mark.skip
def test_get_item_content():
    pass

def test_create_item(youmuusJson, youmuus_html):
    item = create_item("3142", youmuusJson, youmuus_html, "13.22.1")
    assert item.item_id == "3142"
    assert "3133" in item.from_ and "3134" in item.from_
    assert item.class_ == ItemClass.MYTHIC


@pytest.mark.skip
def test_get_rune_passive():
    pass

def test_create_rune(electrocute, electrocute_html):
    image = Image(full="electrocute.png", group="rune")
    rune = create_rune(electrocute, electrocute_html, "13.22.1", image)
    assert rune.name == "Electrocute"
    assert rune.ready_to_use == False
    assert rune.passive.name == "Electrocute"


@pytest.mark.skip
def test_get_summonerspell_content():
    pass

def test_create_summonerspell_ability(ignite_json, ignite_html):
    summoner = create_summonerspell(ignite_json, ignite_html, "13.22.1")
    assert summoner.name == "Ignite"
    assert summoner.ability.name == "Ignite"

@pytest.mark.skip
def test_create_summonerspell():
    pass
