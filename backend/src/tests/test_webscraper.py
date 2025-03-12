import pytest

from src.server.models.dataenums import (
    AttackspeedStats,
    RangeType,
    ItemClass,
    Stat,
    Table,
    TableTitle
)
from src.server.models.effect import Status, StatusType, Scaling
from src.server.models.image import Image
from src.server.loader.webscraper import (
    get_hotfix_list,
    datetime,
    get_attackspeed_stats,
    get_side_box_stats,
    create_champion,
    create_item,
    create_rune,
    create_summonerspell,
    usify_stats,
    usify_tables
)




def test_get_hotfix_list():
    with open("src/tests/files/Patch1321.html", encoding="UTF-8") as patch1321:
        result = get_hotfix_list(patch1321)
        assert result == [datetime(datetime.now().year, 10, 26), datetime(datetime.now().year, 10, 27)]



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

@pytest.mark.skip
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
    item = create_item("3142", youmuusJson, youmuus_html, "13.22.1", False)
    assert item.item_id == "3142"
    assert "3133" in item.from_ and "3134" in item.from_
    assert item.class_ == ItemClass.LEGENDARY


def test_create_item_masterwork(youmuusJson, youmuus_html):
    item = create_item("3142", youmuusJson, youmuus_html, "13.22.1", True)
    assert item.item_id == "3142"
    assert "3133" in item.from_ and "3134" in item.from_
    assert item.class_ == ItemClass.MASTERWORK
    assert item.stats[Stat.AD] == 88.57


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



@pytest.mark.parametrize("input, output", [
    (
        {'Magic Damage': '80 / 100 / 120 / 140 / 160 (+ 60% AP)', 'Heal': '20 / 25 / 30 / 35 / 40 (+ 35% AP)'},
        [Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[80, 100, 120, 140, 160]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1], bot=[60], title=TableTitle.FLAT), stat=Stat.AP)],
            type_=StatusType.DAMAGE,
            comment="Magic Damage"),
        Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[20, 25, 30, 35, 40]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1], bot=[35], title=TableTitle.FLAT), stat=Stat.AP)],
            type_=StatusType.HEAL,
            comment="Heal")]
    ),
    (
        {'Minimum Magic Damage': '30 / 45 / 60 / 75 / 90 (+ 1.5% maximum health) (+ 35% AP)', 'Maximum Magic Damage': '60 / 90 / 120 / 150 / 180 (+ 6% maximum health) (+ 80% AP)'},
        [Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[30, 45, 60, 75, 90]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1], bot=[1.5], title=TableTitle.FLAT), stat=Stat.MAX_HP),
                Scaling(value=Table(top=[1], bot=[35], title=TableTitle.FLAT), stat=Stat.AP)],
            type_=StatusType.DAMAGE,
            comment="Minimum Magic Damage"),
        Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[60, 90, 120, 150, 180]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1], bot=[6], title=TableTitle.FLAT), stat=Stat.MAX_HP),
                Scaling(value=Table(top=[1], bot=[80], title=TableTitle.FLAT), stat=Stat.AP)],
            type_=StatusType.DAMAGE,
            comment="Maximum Magic Damage")]
    ),
    (
        {'Total Physical Damage': '8 / 11 / 14 / 17 / 20 (+ 100 / 105 / 110 / 115 / 120% AD)', 'Physical Damage per Hit': '1.14 / 1.57 / 2 / 2.43 / 2.86 (+ 14.29 / 15 / 15.71 / 16.43 / 17.14% AD)'},
        [Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[8, 11, 14, 17, 20]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1,2,3,4,5], bot=[100, 105, 110, 115, 120]), stat=Stat.AD)],
            type_=StatusType.DAMAGE,
            comment="Total Physical Damage"),
        Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[1.14, 1.57, 2, 2.43, 2.86]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1,2,3,4,5], bot=[14.29, 15, 15.71, 16.43, 17.14]), stat=Stat.AD),],
            type_=StatusType.DAMAGE,
            comment="Physical Damage per Hit")]
    ),
    (
        {'Magic Damage': "35 / 50 / 65 / 80 / 95 (+ 4 / 5 / 6 / 7 / 8% (+ 4% per 100 AP) of target's maximum health)", 'Capped Non-Champion Damage': '235 / 250 / 265 / 280 / 295'},
        [Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[35, 50, 65, 80, 95]), stat=Stat.FLAT),
                Scaling(value=Table(top=[1,2,3,4,5], bot=[4, 5, 6, 7, 8]), stat=Stat.MAX_HP_TARGET),
                Scaling(value=Scaling(value=Table(top=[1], bot=[4], title=TableTitle.FLAT), stat=Stat.AP), stat=Stat.MAX_HP_TARGET)],
            type_=StatusType.DAMAGE,
            comment="Magic Damage"),
        Status(scalings=[Scaling(value=Table(top=[1,2,3,4,5], bot=[235, 250, 265, 280, 295]), stat=Stat.FLAT)],
            type_=StatusType.DAMAGE,
            comment="Capped Non-Champion Damage")]
    )
])
def test_usify_stats(input, output):
    result = usify_stats(input)
    assert result == output



@pytest.mark.parametrize("bot_input, top_input, title, output", [
    (
        '1;6;11;16', '10;20;30;40', '',
        Table(
            top=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0],
            bot=[10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0, 20.0, 30.0, 30.0, 30.0, 30.0, 30.0, 40.0, 40.0, 40.0],
            title=TableTitle.LEVEL
        )
    ),
    (
        '', '1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18', '',
        Table(
            top=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0],
            bot=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0],
            title=TableTitle.LEVEL
        )
    )])
def test_usify_tables(top_input, bot_input, title, output):
    result = usify_tables(top_input, bot_input)
    assert result == output
