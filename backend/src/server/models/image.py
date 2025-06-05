from pydantic import BaseModel


#TODO change string to FilePath

class Image(BaseModel):
    full: str
    group: str
    sprite: str | None = None
    x: int | None = None
    y: int | None = None
    h: int | None = None
    w: int | None = None