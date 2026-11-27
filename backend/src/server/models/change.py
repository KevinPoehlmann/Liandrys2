from datetime import datetime

from pydantic import BaseModel

from src.server.models.enums import ChangeSource


class Change(BaseModel):
    source: ChangeSource
    text: str
    details: list[str] = []  # sub-lines of a patch note line (wiki "***"): extra info on `text`
    hotfix: datetime | None = None  # None: came with the patch, else the hotfix run that found it

    def same_line(self, other: "Change") -> bool:
        return self.dict(exclude={"hotfix"}) == other.dict(exclude={"hotfix"})


def patch_note(text: str, details: list[str] | None = None) -> Change:
    return Change(source=ChangeSource.PATCH_NOTES, text=text, details=details or [])


def unrecorded(found: list[Change], earlier: list[Change]) -> list[Change]:
    """The lines that neither the patch nor an earlier hotfix run recorded yet."""
    return [change for change in found if not any(change.same_line(known) for known in earlier)]


def with_hotfix_lines(earlier: list[Change], found: list[Change], hotfixed_at: datetime) -> list[Change]:
    """A hotfix run adds the lines its patch (or an earlier run) didn't bring yet, marked with the run's date."""
    return earlier + [change.copy(update={"hotfix": hotfixed_at}) for change in unrecorded(found, earlier)]
