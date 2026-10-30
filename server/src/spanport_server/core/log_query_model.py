"""The condition tree a log search is turned into.

The parser (a service) builds it from filter chips and the text query; the compiler (a
repository) turns it into parameterized ClickHouse SQL. Neither side sees the other's format.
"""

from dataclasses import dataclass
from enum import StrEnum


class Operator(StrEnum):
    """How a field is compared, as in the filter chips."""

    EQUALS = "="
    NOT_EQUALS = "!="
    CONTAINS = ":"
    NOT_CONTAINS = "!:"


@dataclass(frozen=True)
class FieldMatch:
    """A field compared with a value, e.g. Level = ERROR. "*" in the value matches anything."""

    field: str
    operator: Operator
    value: str


@dataclass(frozen=True)
class TextMatch:
    """Text in the message: a word, or an exact phrase when `exact_phrase` is set."""

    text: str
    exact_phrase: bool


@dataclass(frozen=True)
class NotCondition:
    """Matches when `condition` doesn't."""

    condition: Condition


@dataclass(frozen=True)
class AllOf:
    """Matches when every condition matches (AND)."""

    conditions: tuple[Condition, ...]


@dataclass(frozen=True)
class AnyOf:
    """Matches when at least one condition matches (OR)."""

    conditions: tuple[Condition, ...]


type Condition = FieldMatch | TextMatch | NotCondition | AllOf | AnyOf
