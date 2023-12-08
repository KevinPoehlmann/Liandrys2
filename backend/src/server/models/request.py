from pydantic import BaseModel



class DummyRequest(BaseModel):
    champion_id: str
    lvl: int