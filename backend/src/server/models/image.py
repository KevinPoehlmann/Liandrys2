from pydantic import BaseModel


#TODO change string to FilePath

class Image(BaseModel):
    full: str
    group: str
    sprite: str = None
    x: int = None
    y: int = None
    h: int = None
    w: int = None