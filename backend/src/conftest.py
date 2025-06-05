import copy
import json
import pytest

from bs4 import BeautifulSoup
from bson.objectid import ObjectId
from datetime import datetime

from src.server.loader.helper import RuneClass
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
    HpScaling,
    EffectComp,
    HealProperties,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    ProcessedStatusProperties,
    QueueComponent,
    EffectType,
    StatusType,
    Actor
)
from src.server.models.item import Item
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.models.patch import NewPatch, Patch
from src.server.models.request import Rank
from src.server.simulation.character import Character
from src.server.simulation.simulation import Simulation




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


@pytest.fixture
def load_html():
    def _loader(name: str) -> str:
        with open(f"src/tests/static/html/{name}.html", "r", encoding="utf-8") as f:
            return f.read()
    return _loader

@pytest.fixture
def load_soup(load_html):
    def _loader(name: str) -> BeautifulSoup:
        return BeautifulSoup(load_html(name), "lxml")
    return _loader


@pytest.fixture()
def patch_with_hotfix() -> NewPatch:
    patch = NewPatch(
        patch="15.7.1",
        hotfix=datetime(2024, 4, 6, 12, 0),
        champion_count=170,
        item_count=435,
        rune_count=63,
        summonerspell_count=18,
    )
    return patch


@pytest.fixture()
def patch_without_hotfix() -> NewPatch:
    patch = NewPatch(
        patch="15.7.1",
        hotfix=None,
        champion_count=170,
        item_count=435,
        rune_count=63,
        summonerspell_count=18,
    )
    return patch



@pytest.fixture
def processed_damage_props(request) -> ProcessedDamageProperties:
    params = getattr(request, "param", {})
    return ProcessedDamageProperties(
        value=params.get("val", 50),
        flat_pen=params.get("flat_pen", 0),
        percent_pen=params.get("perc_pen", 0),
        dmg_type=params.get("dmg_type", DamageType.BASIC),
        dmg_sub_type=params.get("dmg_sub_type", DamageSubType.PHYSIC),
        hp_scaling=params.get("hp_scaling", HpScaling.FLAT)
    )


@pytest.fixture
def queue_damage_list(request) -> list[QueueComponent]:
    params = getattr(request, "param", {})
    values=params.get("values", [])
    props=[ProcessedDamageProperties(
        value=value,
        flat_pen=0,
        percent_pen=0,
        dmg_type=DamageType.BASIC,
        dmg_sub_type=DamageSubType.TRUE
    ) for value in values]
    queue_comps=[QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=prop
    ) for prop in props]
    return queue_comps


@pytest.fixture
def queue_heal_list(request) -> list[QueueComponent]:
    params = getattr(request, "param", {})
    values=params.get("values", [])
    props=[ProcessedHealProperties(value=value) for value in values]
    queue_comps=[QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=prop
    ) for prop in props]
    return queue_comps


@pytest.fixture
def queue_shield_list(request) -> list[QueueComponent]:
    params = getattr(request, "param", {})
    values=params.get("values", [])
    props=[ProcessedShieldProperties(value=value, duration=duration) for duration, value in values]
    queue_comps=[QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=prop
    ) for prop in props]
    return queue_comps


@pytest.fixture
def queue_status_list(request) -> list[QueueComponent]:
    params = getattr(request, "param", {})
    values=params.get("values", [])
    props=[ProcessedStatusProperties(type_=type_, duration=duration) for type_, duration in values]
    queue_comps=[QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=prop
    ) for prop in props]
    return queue_comps



@pytest.fixture
def processed_status_props(request) -> ProcessedStatusProperties:
    params = getattr(request, "param", {})
    return ProcessedStatusProperties(
        type_=params.get("type", StatusType.STUN),
        duration=params.get("duration", 1),
        strength=params.get("strength", 0),
    )


@pytest.fixture
def action_effect_aa() -> ActionEffect:
    return ActionEffect(
        time=0.215,
        effect_comps=[
            EffectComp(
                source=ActionType.AA,
                target=Actor.RED,
                type_=EffectType.DAMAGE,
                props=DamageProperties(
                    scaling="ad",
                    dmg_type=DamageType.BASIC,
                    dmg_sub_type=DamageSubType.PHYSIC,
                    hp_scaling=HpScaling.FLAT
                )
            )
        ]
    )


@pytest.fixture
def action_effect_q() -> ActionEffect:
    return ActionEffect(
        time=1.6,
        effect_comps=[
            EffectComp(
                source=ActionType.Q,
                target=Actor.RED,
                type_=EffectType.DAMAGE,
                props=DamageProperties(
                    scaling="-5 + rank * 15 + (0.525 + rank * 0.075) * ad",
                    dmg_type=DamageType.AOE,
                    dmg_sub_type=DamageSubType.PHYSIC,
                    hp_scaling=HpScaling.FLAT
                )
            )
        ]
    )


@pytest.fixture()
def e_damage_aa() -> EffectComp:
    d = EffectComp(
        source=ActionType.AA,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=DamageProperties(
            scaling="ad",
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            hp_scaling=HpScaling.FLAT,
    ))
    return d


@pytest.fixture()
def e_damage_w() -> EffectComp:
    d = EffectComp(
        source=ActionType.W,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        duration=2,
        interval=0.5,
        props=DamageProperties(
            scaling="20 + 0.3 * ap",
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            hp_scaling=HpScaling.FLAT,
        )
    )
    return d


@pytest.fixture()
def e_damage_e() -> EffectComp:
    d = EffectComp(
        source=ActionType.E,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        duration=2,
        interval=0.5,
        delay=0.2,
        props=DamageProperties(
            scaling="20 + 0.3 * ap",
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            hp_scaling=HpScaling.FLAT,
        )
    )
    return d


@pytest.fixture()
def e_damage_r() -> EffectComp:
    d = EffectComp(
        source=ActionType.R,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        duration=2,
        interval=0.5,
        delay=0,
        speed=2000,
        props=DamageProperties(
            scaling="20 + 0.3 * ap",
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            hp_scaling=HpScaling.FLAT,
        )
    )
    return d


@pytest.fixture
def q_processed_ad_flat() -> QueueComponent:
    p = QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=ProcessedDamageProperties(
            value=100,
            flat_pen=10,
            percent_pen=0.5,
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            hp_scaling=HpScaling.FLAT
        ))
    return p


@pytest.fixture
def q_processed_ap_maxhp():
    p = QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=ProcessedDamageProperties(
            value=0.1,
            flat_pen=18,
            percent_pen=0,
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.MAGIC,
            hp_scaling=HpScaling.MAX_HP
        ))
    return p


@pytest.fixture
def q_processed_heal_flat() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.E,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.HEAL,
        props=ProcessedHealProperties(
            value=440.15 ,
            hp_scaling=HpScaling.FLAT
    ))
    return d


@pytest.fixture
def q_processed_vamp() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=ProcessedDamageProperties(
            value=200,
            flat_pen=0,
            percent_pen=0.3,
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            hp_scaling=HpScaling.FLAT,
            vamp=0.2
        )
    )
    return d


@pytest.fixture
def q_processed_vamp_heal() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.BLUE,
        type_=EffectType.HEAL,
        props=ProcessedHealProperties(
            value=21.920,
            hp_scaling=HpScaling.FLAT
        )
    )
    return d


@pytest.fixture
def q_damage_aa() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=DamageProperties(
            scaling="ad",
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            hp_scaling=HpScaling.FLAT
    ))
    return d


@pytest.fixture
def q_vamp_aa() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.AA,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=DamageProperties(
            scaling="200",
            dmg_type=DamageType.BASIC,
            dmg_sub_type=DamageSubType.PHYSIC,
            hp_scaling=HpScaling.FLAT,
            vamp=0.2
    ))
    return d


@pytest.fixture
def q_damage_q() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.Q,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=DamageProperties(
            scaling="-5 + rank * 15 + (0.525 + rank * 0.075) * ad",
            dmg_type=DamageType.AOE,
            dmg_sub_type=DamageSubType.PHYSIC,
            hp_scaling=HpScaling.FLAT
    ))
    return d


@pytest.fixture
def q_damage_w() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.W,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.DAMAGE,
        props=DamageProperties(
            scaling="20 + 0.3 * ap" ,
            dmg_type=DamageType.DOT,
            dmg_sub_type=DamageSubType.MAGIC,
            hp_scaling=HpScaling.FLAT
    ))
    return d


@pytest.fixture
def q_damage_w_shadow() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.W,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.SHADOW,
        props=None
    )
    return d


@pytest.fixture
def q_heal_e() -> QueueComponent:
    d = QueueComponent(
        source=ActionType.E,
        actor=Actor.BLUE,
        target=Actor.RED,
        type_=EffectType.HEAL,
        props=HealProperties(
            scaling="400 + 0.3 * ad" ,
            hp_scaling=HpScaling.FLAT
    ))
    return d


@pytest.fixture()
def aatrox() -> Champion:
    with open("src/tests/static/json/aatrox.json", encoding='UTF-8') as f:
        data = json.load(f)
    return Champion.parse_obj(data)


@pytest.fixture()
def smite() -> Summonerspell:
    with open("src/tests/static/json/smite.json", encoding='UTF-8') as f:
        data = json.load(f)
    return Summonerspell.parse_obj(data)



@pytest.fixture()
def aatrox_with_items():
    with open("src/tests/static/json/aatrox.json", encoding='UTF-8') as champion:
        aatrox = Champion.parse_obj(json.load(champion))
    with open("src/tests/static/json/triforce.json", encoding='UTF-8') as tri_file:
        tri = Item.parse_obj(json.load(tri_file))
    with open("src/tests/static/json/frozen_heart.json", encoding='UTF-8') as fh_file:
        fheart = Item.parse_obj(json.load(fh_file))
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
def sim(aatrox_with_items) -> Simulation:
    aatrox2 = copy.deepcopy(aatrox_with_items)
    sim = Simulation(aatrox_with_items, aatrox2)
    return sim
