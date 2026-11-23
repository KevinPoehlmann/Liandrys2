from src.server.models.enums import ActionType, Actor, ErrorCode
from src.server.models.result import Origin


class SimulationError(Exception):
    code: ErrorCode = ErrorCode.INTERNAL

    def __init__(
        self,
        message: str,
        action_index: int | None = None,
        action_type: ActionType | None = None,
        actor: Actor | None = None,
        phase: str | None = None,  # "cast" (starting an action) or "effect" (a queued rule, buff or pet)
        tick: int | None = None,
        origin: Origin | None = None,
        champion: str | None = None,
        rule: str | None = None  # where the rule sits in its container: "stage 1, rule 2"
    ):
        self.message = message
        self.action_index = action_index
        self.action_type = action_type
        self.actor = actor
        self.phase = phase
        self.tick = tick
        self.origin = origin
        self.champion = champion
        self.rule = rule
        super().__init__(self.__str__())

    def __str__(self):
        details = f"SimulationError"
        if self.phase:
            details += f" during '{self.phase}'"
        if self.action_index is not None:
            details += f" at action #{self.action_index}"
        if self.action_type:
            details += f" ({self.action_type.value})"
        if self.actor:
            details += f" by {self.actor}"
        if self.tick is not None:
            details += f" at tick {self.tick}"
        if self.origin:
            details += f" in {self.champion + ' ' if self.champion else ''}{describe(self.origin)}"
        if self.rule:
            details += f", {self.rule}"
        details += f": {self.message}"
        return details


class ComboError(SimulationError):
    """The request can't be simulated as asked: not enough mana, an item without an active, an unknown outcome."""
    code = ErrorCode.INVALID_COMBO


class DataError(SimulationError):
    """The entered data is broken: a formula, an unknown buff, rules that trigger each other forever."""
    code = ErrorCode.INVALID_DATA


class NotEnteredError(SimulationError):
    code = ErrorCode.NOT_ENTERED


class NotSupportedError(SimulationError):
    """A NotImplementedError: the simulation can't do this yet."""
    code = ErrorCode.NOT_SUPPORTED


def describe(origin: Origin) -> str:
    return f"{origin.kind.value} '{origin.name}'" + (f" ({origin.buff})" if origin.buff else "")


def located(error: Exception, **where) -> SimulationError:
    """Adds where an error happened. Each field comes from the innermost place that knows it; a phase completes the error."""
    if not isinstance(error, SimulationError):
        if isinstance(error, NotImplementedError):
            wrapped = NotSupportedError(str(error))
        else:
            wrapped = SimulationError(f"{type(error).__name__}: {error}")
        wrapped.__cause__ = error
        error = wrapped
    if error.phase is None:
        for key, value in where.items():
            if getattr(error, key) is None:
                setattr(error, key, value)
        error.args = (str(error),)
    return error
