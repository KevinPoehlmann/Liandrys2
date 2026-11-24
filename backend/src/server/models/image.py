from pydantic import BaseModel


class Image(BaseModel):
    """An image under src/images/<group>/<full>. Newly loaded images carry a content hash in `full`."""
    full: str
    group: str
