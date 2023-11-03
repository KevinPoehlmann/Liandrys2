from pydantic import BaseModel, Field





class ChampionsJson(BaseModel):
    typ: str = Field(..., alias="type")
    frmt: str = Field(..., alias="format")
    version: str
    data: dict



class ItemJson(BaseModel):
    typ: str = Field(..., alias="type")
    version: str
    basic: dict
    data: dict
    groups: list[dict]
    tree: list[dict]



class RuneJson(BaseModel):
    pass



class SummonerspellJson(BaseModel):
    typ: str = Field(..., alias="type")
    version: str
    data: dict