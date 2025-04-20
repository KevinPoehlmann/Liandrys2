

class LoadError(Exception):
    def __init__(self, code: int, reason: str, url:str, type: str, name: str) -> None:
        self.code: int = code
        self.reason: str = reason
        self.url: str = url
        self.type: str = type
        self.name: str = name


class ScrapeError(Exception):
    def __init__(self, reason: str, type: str, name: str) -> None:
        self.reason: str = reason
        self.type: str = type
        self.name: str = name


class NameError(Exception):
    def __init__(self, type: str, name: str) -> None:
        self.type: str = type
        self.name: str = name


class PatcherError(Exception):
    def __init__(self, message: str, error: str) -> None:
        self.message: str = message
        self.error: str = error


class MuteException(Exception):
    def __init__(self, message: str) -> None:
        self.message: str = message


class EmptyTodoException(Exception):
    def __init__(self, message: str) -> None:
        self.message: str = message