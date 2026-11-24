"""Reads the Lua data tables of wiki modules (Module:ChampionData/data): tables, strings, numbers, booleans, comments
and arithmetic (Kled's `84+1000/17`)."""
import re


TOKEN = re.compile(r"""
    \s+ | --[^\n]*                                      # whitespace and comments
    | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<number>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)
    | (?P<word>[A-Za-z_]\w*)
    | (?P<symbol>[{}\[\]=,;+\-*/()])
""", re.VERBOSE)
WORDS = {"true": True, "false": False, "nil": None}


def parse_lua_table(text: str) -> dict | list:
    """The table after `return`; a table with only the keys 1..n becomes a list."""
    parser = _Parser(_tokens(text))
    parser.expect("word", "return")
    return parser.value()


def _tokens(text: str) -> list[tuple[str, str]]:
    tokens, position = [], 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            raise ValueError(f"Unexpected Lua at {position}: {text[position:position + 30]!r}")
        if match.lastgroup:
            tokens.append((match.lastgroup, match.group(match.lastgroup)))
        position = match.end()
    return tokens


class _Parser:

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.index = 0

    def next(self) -> tuple[str, str]:
        if self.index >= len(self.tokens):
            raise ValueError("Unexpected end of Lua table")
        self.index += 1
        return self.tokens[self.index - 1]

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def expect(self, kind: str, text: str) -> None:
        token = self.next()
        if token != (kind, text):
            raise ValueError(f"Expected {text!r}, got {token[1]!r}")

    def value(self):
        kind, text = self.next()
        if kind == "string":
            return re.sub(r"\\(.)", r"\1", text[1:-1])
        if kind == "number" or text in ("-", "("):
            self.index -= 1
            return self.sum()
        if kind == "word" and text in WORDS:
            return WORDS[text]
        if (kind, text) == ("symbol", "{"):
            return self.table()
        raise ValueError(f"Unexpected Lua value {text!r}")

    def table(self) -> dict | list:
        entries, position = {}, 1
        while self.peek() != ("symbol", "}"):
            key = self.key()
            if key is None:
                key, position = position, position + 1
            entries[key] = self.value()
            if self.peek() in (("symbol", ","), ("symbol", ";")):
                self.next()
        self.next()
        if list(entries) == list(range(1, len(entries) + 1)):
            return list(entries.values())
        return entries

    def sum(self) -> float:
        result = self.product()
        while self.peek() in (("symbol", "+"), ("symbol", "-")):
            result = result + self.product() if self.next()[1] == "+" else result - self.product()
        return result

    def product(self) -> float:
        result = self.factor()
        while self.peek() in (("symbol", "*"), ("symbol", "/")):
            result = result * self.factor() if self.next()[1] == "*" else result / self.factor()
        return result

    def factor(self) -> float:
        kind, text = self.next()
        if text == "-":
            return -self.factor()
        if text == "(":
            result = self.sum()
            self.expect("symbol", ")")
            return result
        if kind == "number":
            number = float(text)
            return int(number) if number.is_integer() and "." not in text else number
        raise ValueError(f"Unexpected Lua value {text!r}")

    def key(self):
        """`["name"] =`, `[1] =` or `name =`; None for a positional entry."""
        token = self.peek()
        if token == ("symbol", "["):
            self.next()
            key = self.value()
            self.expect("symbol", "]")
            self.expect("symbol", "=")
            return key
        following = self.tokens[self.index + 1] if self.index + 1 < len(self.tokens) else None
        if token and token[0] == "word" and following == ("symbol", "="):
            self.index += 2
            return token[1]
        return None
