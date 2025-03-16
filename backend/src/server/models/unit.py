from pydantic import BaseModel


class Unit(BaseModel):
    hp: float
    armor: int
    mr: float
