import json
import pytest

from bs4 import BeautifulSoup
from bson.objectid import ObjectId
from datetime import datetime

from src.server.loader.helper import RuneClass
from src.server.loader.patchloader import Patchloader
from src.server.models.json_validation import (
    ChampionJson,
    ChampionsJson,
    ItemsJson,
    ItemJson,
    RuneTreeJson,
    SummonerspellsJson,
    SummonerspellJson
)
from src.server.models.champion import Champion
from src.server.models.dataenums import (
    ActionEffect,
    ActionType,
    DamageProperties,
    DamageSubType,
    DamageType,
    DamageCalculation,
    EffectDamage,
    EffectStatus,
    HealProperties,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    QueueStatus,
    StatusType,
    Target
)
from src.server.models.item import Item
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.models.patch import NewPatch, Patch
from src.server.models.request import Rank
from src.server.models.unit import Unit
from src.server.simulation.unit import Character
from src.server.simulation.simulator import Simulation




@pytest.fixture
def compare_objects():
    def _compare(obj1, obj2, float_precision=3):
        if type(obj1) != type(obj2):
            return False
        if isinstance(obj1, float) and isinstance(obj2, float):
            return round(obj1, float_precision) == round(obj2, float_precision)
        if isinstance(obj1, (list, tuple)):
            return len(obj1) == len(obj2) and all(_compare(a, b, float_precision) for a, b in zip(obj1, obj2))
        if isinstance(obj1, dict):
            return obj1.keys() == obj2.keys() and all(_compare(obj1[k], obj2[k], float_precision) for k in obj1)
        if hasattr(obj1, "__dict__") and hasattr(obj2, "__dict__"):
            return _compare(vars(obj1), vars(obj2), float_precision)
        return obj1 == obj2
    return _compare





@pytest.fixture
def resolve_fixture(request):
    return request.getfixturevalue(request.param)  # Resolves fixture dynamically



@pytest.fixture()
def clean_Patchloader():
    yield
    Patchloader.mute = False
    Patchloader.todo = []

@pytest.fixture()
def version1321_json():
    with open("src/tests/files/versions1321.json") as versions:
        return json.load(versions)


@pytest.fixture()
def version1322_json():
    with open("src/tests/files/versions1322.json") as versions:
        return json.load(versions)


@pytest.fixture()
def champion_json():
    with open("src/tests/files/champion.json", encoding='UTF-8') as champion:
        return json.load(champion)


@pytest.fixture()
def aatrox_soup():
    with open("src/tests/files/aatrox.html", encoding='UTF-8') as champion:
        return BeautifulSoup(champion, "lxml")


@pytest.fixture()
def ashe_soup():
    with open("src/tests/files/ashe.html", encoding='UTF-8') as champion:
        return BeautifulSoup(champion, "lxml")


@pytest.fixture()
def yuumi_soup():
    with open("src/tests/files/yuumi.html", encoding='UTF-8') as champion:
        return BeautifulSoup(champion, "lxml")


@pytest.fixture()
def aatrox_html():
    with open("src/tests/files/aatrox.html", encoding="utf-8") as patch:
        by = patch.read()
        return by.encode("utf-8")



@pytest.fixture()
def aatrox_json():
    with open("src/tests/files/aatrox_data.json", encoding='UTF-8') as champion:
        return json.load(champion)


@pytest.fixture()
def aatroxJson():
    with open("src/tests/files/aatrox_data.json", encoding='UTF-8') as champion:
        champ = ChampionsJson(**json.load(champion))
        return ChampionJson(**champ.data["Aatrox"])



@pytest.fixture()
def item_json():
    with open("src/tests/files/item.json", encoding='UTF-8') as item:
        return json.load(item)


@pytest.fixture()
def triforce_json():
    with open("src/tests/files/item.json", encoding='UTF-8') as item_file:
        items = ItemsJson(**json.load(item_file))
        item = ItemJson(**items.data["3078"])
        return item


@pytest.fixture()
def youmuusJson():
    with open("src/tests/files/item.json", encoding='UTF-8') as item_file:
        items = ItemsJson(**json.load(item_file))
        item = ItemJson(**items.data["3142"])
        return item


@pytest.fixture()
def youmuus_html():
    with open("src/tests/files/youmuus.html", encoding='UTF-8') as patch:
        by = patch.read()
        return by.encode("utf-8")
    




@pytest.fixture()
def runesReforged_json():
    with open("src/tests/files/runesReforged.json", encoding='UTF-8') as rune:
        return json.load(rune)


@pytest.fixture()
def electrocute():
    with open("src/tests/files/runesReforged.json", encoding='UTF-8') as rune_file:
        runes = json.load(rune_file)
        rune_tree = RuneTreeJson(**runes[0])
        rune_row = rune_tree.slots[0]
        rune = rune_row.runes[0]
        rune_class = RuneClass(
            rune=rune,
            tree=rune_tree.name,
            tree_id=rune_tree.id_,
            row=0
        )
        return rune_class


@pytest.fixture()
def electrocute_html():
    with open("src/tests/files/electrocute.html", encoding='UTF-8') as patch:
        by = patch.read()
        return by.encode("utf-8")
    


@pytest.fixture()
def summoner_json():
    with open("src/tests/files/summoner.json", encoding='UTF-8') as summoner:
        return json.load(summoner)


@pytest.fixture()
def ignite_json():
    with open("src/tests/files/summoner.json", encoding='UTF-8') as summoner_file:
        summoners = json.load(summoner_file)
        summoners_json = SummonerspellsJson(**summoners)
        summoner = SummonerspellJson(**summoners_json.data["SummonerDot"])
        return summoner


@pytest.fixture()
def ignite_html():
    with open("src/tests/files/ignite.html", encoding='UTF-8') as patch:
        by = patch.read()
        return by.encode("utf-8")
    


@pytest.fixture()
def patch1321():
    with open("src/tests/files/Patch1321.html", encoding="utf-8") as patch:
        by = patch.read()
        return by.encode("utf-8")
    


@pytest.fixture()
def db_fake_patch():
    patch = NewPatch(
        patch="13.21.1",
        champion_count=165,
        item_count=435,
        rune_count=63,
        summonerspell_count=18,
        document_count=681
    )
    return patch


@pytest.fixture()
def db_fake_patch_hotfix():
    patch = NewPatch(
        patch="13.21.1",
        hotfix=datetime(datetime.now().year, 10, 26),
        champion_count=165,
        item_count=435,
        rune_count=63,
        summonerspell_count=18,
        document_count=681
    )
    return patch


@pytest.fixture()
def db_fake_patch_uptodate():
    patch = NewPatch(
        patch="13.21.1",
        hotfix=datetime(datetime.now().year, 10, 27),
        champion_count=165,
        item_count=435,
        rune_count=63,
        summonerspell_count=18,
        document_count=681
    )
    return patch


@pytest.fixture()
def db_fake_patch_with_id():
    patch = Patch(
        _id=ObjectId(),
        patch="13.21.1",
        hotfix=datetime(datetime.now().year, 10, 27),
        champion_count=165,
        item_count=435,
        rune_count=63,
        summonerspell_count=18,
        document_count=681
    )
    return patch



@pytest.fixture
def processed_damage_props(request):
    params = getattr(request, "param", {})
    return ProcessedDamageProperties(
        value=params.get("val", 50),
        flat_pen=params.get("flat_pen", 100),
        percent_pen=params.get("perc_pen", 50),
        dmg_type=params.get("dmg_type", DamageType.BASIC),
        dmg_sub_type=params.get("dmg_sub_type", DamageSubType.PHYSIC),
        dmg_calc=params.get("dmg_calc", DamageCalculation.FLAT)
    )


@pytest.fixture
def action_effect_aa():
    return ActionEffect(
        time=0.215,
        stati=[
            EffectDamage(
                source=ActionType.AA,
                target=Target.DEFENDER,
                type_=StatusType.DAMAGE,
                props=DamageProperties(
                    scaling="ad",
                    dmg_type=DamageType.BASIC,
                    dmg_sub_type=DamageSubType.PHYSIC,
                    dmg_calc=DamageCalculation.FLAT
                )
            )
        ]
    )


@pytest.fixture
def action_effect_q():
    return ActionEffect(
        time=1.6,
        stati=[
            EffectStatus(
                source=ActionType.Q,
                target=Target.DEFENDER,
                type_=StatusType.DAMAGE,
                props=DamageProperties(
                    scaling="-5 + rank * 15 + (0.525 + rank * 0.075) * ad",
                    dmg_type=DamageType.AOE,
                    dmg_sub_type=DamageSubType.PHYSIC,
                    dmg_calc=DamageCalculation.FLAT
                )
            )
        ]
    )


@pytest.fixture()
def e_damage_aa():
    d = EffectDamage(
        source=ActionType.AA,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        props=DamageProperties(
            scaling="ad",
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            dmg_calc=DamageCalculation.FLAT,
    ))
    return d


@pytest.fixture()
def e_damage_w():
    d = EffectDamage(
        source=ActionType.W,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        duration=2,
        interval=0.5,
        props=DamageProperties(
            scaling="20 + 0.3 * ap",
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            dmg_calc=DamageCalculation.FLAT,
        )
    )
    return d


@pytest.fixture()
def e_damage_e():
    d = EffectDamage(
        source=ActionType.E,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        duration=2,
        interval=0.5,
        delay=0.2,
        props=DamageProperties(
            scaling="20 + 0.3 * ap",
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            dmg_calc=DamageCalculation.FLAT,
        )
    )
    return d


@pytest.fixture()
def e_damage_r():
    d = EffectDamage(
        source=ActionType.R,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        duration=2,
        interval=0.5,
        delay=0,
        speed=2000,
        props=DamageProperties(
            scaling="20 + 0.3 * ap",
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            dmg_calc=DamageCalculation.FLAT,
        )
    )
    return d


@pytest.fixture
def q_processed_ad_flat():
    p = QueueStatus(
        source=ActionType.AA,
        type_=StatusType.DAMAGE,
        target=Target.DEFENDER,
        props=ProcessedDamageProperties(
            value=100,
            flat_pen=10,
            percent_pen=50,
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            dmg_calc=DamageCalculation.FLAT
        ))
    return p


@pytest.fixture
def q_processed_ap_maxhp():
    p = QueueStatus(
        source=ActionType.AA,
        type_=StatusType.DAMAGE,
        target=Target.DEFENDER,
        props=ProcessedDamageProperties(
            value=0.1,
            flat_pen=18,
            percent_pen=0,
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.MAGIC,
            dmg_calc=DamageCalculation.MAX_HP
        ))
    return p


@pytest.fixture
def q_processed_heal_flat():
    d = QueueStatus(
        source=ActionType.E,
        target=Target.DEFENDER,
        type_=StatusType.HEAL,
        props=ProcessedHealProperties(
            value="440.15" ,
            dmg_calc=DamageCalculation.FLAT
    ))
    return d


@pytest.fixture
def q_damage_aa():
    d = QueueStatus(
        source=ActionType.AA,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        props=DamageProperties(
            scaling="ad",
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            dmg_calc=DamageCalculation.FLAT
    ))
    return d


@pytest.fixture
def q_damage_q():
    d = QueueStatus(
        source=ActionType.Q,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        props=DamageProperties(
            scaling="-5 + rank * 15 + (0.525 + rank * 0.075) * ad",
            dmg_type=DamageType.AOE,
            dmg_sub_type=DamageSubType.PHYSIC,
            dmg_calc=DamageCalculation.FLAT
    ))
    return d


@pytest.fixture
def q_damage_w():
    d = QueueStatus(
        source=ActionType.W,
        target=Target.DEFENDER,
        type_=StatusType.DAMAGE,
        props=DamageProperties(
            scaling="20 + 0.3 * ap" ,
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            dmg_calc=DamageCalculation.FLAT
    ))
    return d


@pytest.fixture
def q_damage_w_shadow():
    d = QueueStatus(
        source=ActionType.W,
        target=Target.DEFENDER,
        type_=StatusType.SHADOW,
        props=None
    )
    return d


@pytest.fixture
def q_heal_e():
    d = QueueStatus(
        source=ActionType.E,
        target=Target.DEFENDER,
        type_=StatusType.HEAL,
        props=HealProperties(
            scaling="400 + 0.3 * ad" ,
            dmg_calc=DamageCalculation.FLAT
    ))
    return d


@pytest.fixture()
def action_effect(q_processed_ad_flat, q_processed_ap_maxhp):
    a = ActionEffect(
        time=1.0,
        stati=[q_processed_ad_flat, q_processed_ap_maxhp]
    )
    return a


@pytest.fixture()
def aatrox_with_items():
    with open("src/tests/files/aatrox.json", encoding='UTF-8') as champion:
        aatrox = Champion(**json.load(champion))
    with open("src/tests/files/triforce.json", encoding='UTF-8') as item:
        tri = Item(**json.load(item))
    with open("src/tests/files/frozen_heart.json", encoding='UTF-8') as item:
        fheart = Item(**json.load(item))
    ap = Rank(
        q=3,
        w=1,
        e=1,
        r=0
    )
    character = Character(
        champion=aatrox,
        lvl=5,
        rank=ap,
        items=[tri, fheart]
    )
    yield character



@pytest.fixture
def sim(aatrox_with_items):
    sim = Simulation(aatrox_with_items, aatrox_with_items)
    return sim
