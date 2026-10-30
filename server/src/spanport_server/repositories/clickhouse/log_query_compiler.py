"""Compiles a log search condition tree into a parameterized ClickHouse WHERE fragment.

Columns come only from LOG_COLUMN_FIELDS; any other field is an attribute key. Every value and
every attribute key is a bound parameter ({p0:String}, ...), never part of the SQL text.
"""

import re
from dataclasses import dataclass, field

from spanport_server.core.constants import (
    LIKE_SPECIAL_CHARACTERS_PATTERN,
    LOG_COLUMN_FIELDS,
    LOG_FIELD_ALIASES,
    LOG_LEVEL_COLUMN,
    LOG_MESSAGE_COLUMN,
    QUERY_WILDCARD,
    SEARCH_WORD_PATTERN,
)
from spanport_server.core.log_query_model import (
    AllOf,
    AnyOf,
    Condition,
    FieldMatch,
    NotCondition,
    Operator,
    TextMatch,
)

TOKEN_REGEX = re.compile(SEARCH_WORD_PATTERN)
LIKE_SPECIAL_REGEX = re.compile(LIKE_SPECIAL_CHARACTERS_PATTERN)


@dataclass(frozen=True)
class CompiledCondition:
    """A WHERE fragment and the parameters it uses."""

    sql: str
    parameters: dict[str, str]


def compile_condition(condition: Condition) -> CompiledCondition:
    """Compile a condition into SQL with named parameters.

    Args:
        condition: The parsed condition tree.

    Returns:
        The fragment, e.g. "(level = {p0:String} AND ...)", and the values of p0, p1, ...
    """
    compiler = ConditionCompiler()
    return CompiledCondition(compiler.compile(condition), compiler.parameters)


def like_pattern(value: str, surround: bool) -> str:
    """ILIKE pattern where "*" matches anything and %, _ and \\ match themselves."""
    pattern = LIKE_SPECIAL_REGEX.sub(r"\\\1", value).replace(QUERY_WILDCARD, "%")
    return f"%{pattern}%" if surround else pattern


@dataclass
class ConditionCompiler:
    """Walks the tree, collecting parameters as it goes."""

    parameters: dict[str, str] = field(default_factory=dict)

    def compile(self, condition: Condition) -> str:
        """SQL for one node of the tree."""
        match condition:
            case FieldMatch():
                return self._field_match(condition)
            case TextMatch():
                return self._text_match(condition)
            case NotCondition():
                return f"NOT ({self.compile(condition.condition)})"
            case AllOf():
                return self._join(condition.conditions, " AND ")
            case AnyOf():
                return self._join(condition.conditions, " OR ")

    def _join(self, conditions: tuple[Condition, ...], separator: str) -> str:
        return "(" + separator.join(self.compile(child) for child in conditions) + ")"

    def _field_match(self, condition: FieldMatch) -> str:
        target = self._target(condition.field)
        value = condition.value.upper() if target == LOG_LEVEL_COLUMN else condition.value
        positive = self._compare(target, condition.operator, value)
        negated = condition.operator in (Operator.NOT_EQUALS, Operator.NOT_CONTAINS)
        return f"NOT ({positive})" if negated else positive

    def _compare(self, target: str, operator: Operator, value: str) -> str:
        contains = operator in (Operator.CONTAINS, Operator.NOT_CONTAINS)
        if QUERY_WILDCARD in value:
            return f"ilike({target}, {self._bind(like_pattern(value, surround=contains))})"
        if contains:
            return f"positionCaseInsensitive({target}, {self._bind(value)}) > 0"
        return f"{target} = {self._bind(value)}"

    def _text_match(self, condition: TextMatch) -> str:
        text = condition.text
        if not condition.exact_phrase and QUERY_WILDCARD in text:
            return f"ilike({LOG_MESSAGE_COLUMN}, {self._bind(like_pattern(text, surround=True))})"
        if not condition.exact_phrase and TOKEN_REGEX.match(text):
            return f"hasTokenCaseInsensitive({LOG_MESSAGE_COLUMN}, {self._bind(text)})"
        return f"positionCaseInsensitive({LOG_MESSAGE_COLUMN}, {self._bind(text)}) > 0"

    def _target(self, field_name: str) -> str:
        """A column from the allowlist, or the attribute map looked up by a bound key."""
        resolved = LOG_FIELD_ALIASES.get(field_name, field_name)
        if resolved in LOG_COLUMN_FIELDS:
            return resolved
        return f"attributes[{self._bind(resolved)}]"

    def _bind(self, value: str) -> str:
        name = f"p{len(self.parameters)}"
        self.parameters[name] = value
        return f"{{{name}:String}}"
