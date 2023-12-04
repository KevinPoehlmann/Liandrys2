
from abc import ABC, abstractmethod


class Unit(ABC):
    def __init__(self, stats):
        #TODO stats
        pass

    @abstractmethod
    def take_damge(self, damage) -> None:
        pass



class Dummy(Unit):
    pass



class Champion(Unit):
    
    def __init__(self, champion_id: str):
        pass