from fastapi import APIRouter, HTTPException


from src.server.models.dataenums import (
    Buff, BuffActionType, Stat,
    EffectType, RangeType, ResourceType, ActiveType,
    Map, ItemClass, DamageType, DamageSubType, StatusType,
    HpScaling, ActionType, Comparison
)


router = APIRouter()


def enum_to_list(enum_cls):
    return [{"name": e.name, "value": e.value} for e in enum_cls]

@router.get("/")
async def get_enums():
    return {
        "ActionType": enum_to_list(ActionType),
        "Comparison": enum_to_list(Comparison),
        "Buff": enum_to_list(Buff),
        "BuffActionType": enum_to_list(BuffActionType),
        "Stat": enum_to_list(Stat),
        "EffectType": enum_to_list(EffectType),
        "RangeType": enum_to_list(RangeType),
        "ResourceType": enum_to_list(ResourceType),
        "ActiveType": enum_to_list(ActiveType),
        "Map": enum_to_list(Map),
        "ItemClass": enum_to_list(ItemClass),
        "DamageType": enum_to_list(DamageType),
        "DamageSubType": enum_to_list(DamageSubType),
        "StatusType": enum_to_list(StatusType),
        "HpScaling": enum_to_list(HpScaling),
    }