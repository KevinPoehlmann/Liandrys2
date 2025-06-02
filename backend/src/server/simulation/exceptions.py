from src.server.models.dataenums import ActionType, Actor


class SimulationError(Exception):
    def __init__(
        self,
        message: str,
        action_index: int | None = None,
        action_type: ActionType | None = None,
        actor: Actor | None = None,
        phase: str | None = None  # e.g. "cast" or "effect"
    ):
        self.message = message
        self.action_index = action_index
        self.action_type = action_type
        self.actor = actor
        self.phase = phase
        super().__init__(self.__str__())

    def __str__(self):
        details = f"SimulationError"
        if self.phase:
            details += f" during '{self.phase}'"
        if self.action_index is not None:
            details += f" at action #{self.action_index}"
        if self.action_type:
            details += f" ({self.action_type})"
        if self.actor:
            details += f" by {self.actor}"
        details += f": {self.message}"
        return details