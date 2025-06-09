from pydantic import BaseModel


class MigrationRequest(BaseModel):
    patch: bool = False
    champion: bool = False
    item: bool = False
    rune: bool = False
    summonerspell: bool = False



class MigrationResult(BaseModel):
    updated_patches: int = 0
    updated_champions: int = 0
    updated_items: int = 0
    updated_runes: int = 0
    updated_summonerspells: int = 0
    errors: list[str] = []