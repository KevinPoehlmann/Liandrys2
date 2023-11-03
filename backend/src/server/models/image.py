from pydantic import BaseModel


#TODO change string to FilePath

class Image(BaseModel):
    image: str
    sprite: str = None
    sprite_x: int = None
    sprite_y: int = None
    sprite_w: int = None
    sprite_h: int = None