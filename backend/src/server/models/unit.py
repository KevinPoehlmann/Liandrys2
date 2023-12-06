from pydantic import BaseModel


class Unit(BaseModel):
    hp: float
    armor: int
    mr: float




class Fighter(Unit):
    ad: float
    attackspeed: float