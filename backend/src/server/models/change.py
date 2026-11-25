from pydantic import BaseModel

from src.server.models.enums import ChangeSource


class Change(BaseModel):
    source: ChangeSource
    text: str
    details: list[str] = []  # sub-lines of a patch note line (wiki "***"): extra info on `text`

    @classmethod
    def validate(cls, value):
        # Documents from before the source existed hold plain patch note lines; gone after the fresh load.
        if isinstance(value, str):
            value = {"source": ChangeSource.PATCH_NOTES, "text": value}
        return super().validate(value)


def patch_note(text: str, details: list[str] | None = None) -> Change:
    return Change(source=ChangeSource.PATCH_NOTES, text=text, details=details or [])
