"""Turns filter chips and the text query into one condition tree.

Text query syntax (PRD, "Query text syntax"):

    timeout deadlock          both words (AND is the default)
    timeout OR deadlock       either word
    -healthcheck, NOT x       exclude
    "connection reset"        exact phrase
    level:ERROR               field equals value ("*" in the value is a wildcard)
    ( ... )                   grouping

Errors say what is wrong and where (1-based position); they never repeat the query text.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn

from spanport_server.core.constants import (
    FIELD_NAME_PATTERN,
    MAX_QUERY_NESTING,
    QUERY_EXCLUDE_PREFIX,
    QUERY_FIELD_SEPARATOR,
    QUERY_KEYWORD_AND,
    QUERY_KEYWORD_NOT,
    QUERY_KEYWORD_OR,
    QUERY_PHRASE_QUOTE,
    QUERY_WORD_BREAKS,
)
from spanport_server.core.errors import InvalidRequestError
from spanport_server.core.log_query_model import (
    AllOf,
    AnyOf,
    Condition,
    FieldMatch,
    NotCondition,
    Operator,
    TextMatch,
)
from spanport_server.schemas.log_search import FilterChip, FilterCombine


class TokenKind(StrEnum):
    """Kinds of token in the text query."""

    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    WORD = "word"
    PHRASE = "phrase"
    FIELD_VALUE = "field:value"
    AND = QUERY_KEYWORD_AND
    OR = QUERY_KEYWORD_OR
    NOT = QUERY_KEYWORD_NOT


@dataclass(frozen=True)
class Token:
    """One token. `position` is 1-based; `field` is set for field:value tokens."""

    kind: TokenKind
    text: str
    position: int
    field: str | None = None


TERM_STARTS = frozenset(
    {TokenKind.LEFT_PAREN, TokenKind.WORD, TokenKind.PHRASE, TokenKind.FIELD_VALUE, TokenKind.NOT}
)
KEYWORDS = {
    QUERY_KEYWORD_AND: TokenKind.AND,
    QUERY_KEYWORD_OR: TokenKind.OR,
    QUERY_KEYWORD_NOT: TokenKind.NOT,
}


def fail(message: str) -> NoReturn:
    """Raise the error a user sees for a query they can fix."""
    raise InvalidRequestError(f"Query: {message}")


def build_condition(
    chips: Sequence[FilterChip], combine: FilterCombine, query: str
) -> Condition | None:
    """Combine the filter chips and the text query into one condition (both must match).

    Args:
        chips: Filter chips, joined with `combine`.
        combine: "and" or "or" between chips.
        query: The text query; may be empty.

    Returns:
        The condition, or None when there is nothing to filter on.

    Raises:
        InvalidRequestError: The text query is not valid.
    """
    parts = [part for part in (chips_to_condition(chips, combine), parse_query(query)) if part]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else AllOf(tuple(parts))


def chips_to_condition(chips: Sequence[FilterChip], combine: FilterCombine) -> Condition | None:
    """Turn filter chips into one condition.

    With "and" (the default), chips on the same field and operator are alternatives:
    Level = WARN and Level = ERROR means "level is one of WARN, ERROR", since a line has one
    level. Exclusions (!=, !:) on the same field must all hold. Different fields must all match.
    With "or", any chip may match.
    """
    matches: list[Condition] = [FieldMatch(chip.field, chip.operator, chip.value) for chip in chips]
    if not matches:
        return None
    if combine == "or":
        return matches[0] if len(matches) == 1 else AnyOf(tuple(matches))
    groups: dict[tuple[str, Operator], list[Condition]] = {}
    for chip, match in zip(chips, matches, strict=True):
        groups.setdefault((chip.field, chip.operator), []).append(match)
    parts = [group_condition(operator, members) for (_, operator), members in groups.items()]
    return parts[0] if len(parts) == 1 else AllOf(tuple(parts))


def group_condition(operator: Operator, members: list[Condition]) -> Condition:
    """One field's chips with one operator: any value may match, but every exclusion holds."""
    if len(members) == 1:
        return members[0]
    if operator in (Operator.NOT_EQUALS, Operator.NOT_CONTAINS):
        return AllOf(tuple(members))
    return AnyOf(tuple(members))


def parse_query(query: str) -> Condition | None:
    """Parse the text query.

    Returns:
        The condition, or None for an empty query.

    Raises:
        InvalidRequestError: Unbalanced brackets or quotes, AND/OR/NOT without a term, a field
            without a value, or brackets nested too deeply.
    """
    tokens = tokenize(query)
    if not tokens:
        return None
    return QueryParser(tokens).parse()


def tokenize(query: str) -> list[Token]:
    """Split the query into tokens."""
    tokens: list[Token] = []
    index = 0
    while index < len(query):
        char = query[index]
        if char.isspace():
            index += 1
        elif char in (TokenKind.LEFT_PAREN, TokenKind.RIGHT_PAREN):
            tokens.append(Token(TokenKind(char), char, index + 1))
            index += 1
        elif char == QUERY_PHRASE_QUOTE:
            phrase, index_after = read_phrase(query, index)
            tokens.append(Token(TokenKind.PHRASE, phrase, index + 1))
            index = index_after
        elif (
            char == QUERY_EXCLUDE_PREFIX
            and index + 1 < len(query)
            and starts_term(query[index + 1])
        ):
            tokens.append(Token(TokenKind.NOT, char, index + 1))
            index += 1
        else:
            token, index = read_word_token(query, index)
            tokens.append(token)
    return tokens


def starts_term(char: str) -> bool:
    """Whether a "-" followed by this character excludes a term (rather than being text)."""
    return not char.isspace() and char != TokenKind.RIGHT_PAREN


def read_phrase(query: str, quote_index: int) -> tuple[str, int]:
    """Read a quoted phrase starting at `quote_index`; return its text and the index after it."""
    closing = query.find(QUERY_PHRASE_QUOTE, quote_index + 1)
    if closing == -1:
        fail(f"missing closing quote for the one at position {quote_index + 1}.")
    phrase = query[quote_index + 1 : closing]
    if not phrase.strip():
        fail(f"empty phrase at position {quote_index + 1}.")
    return phrase, closing + 1


def read_word_token(query: str, start: int) -> tuple[Token, int]:
    """Read a bare word: a keyword, a field:value (value may be quoted) or plain text."""
    end = start
    while end < len(query) and not query[end].isspace() and query[end] not in QUERY_WORD_BREAKS:
        end += 1
    word = query[start:end]
    if word in KEYWORDS:
        return Token(KEYWORDS[word], word, start + 1), end
    name, separator, value = word.partition(QUERY_FIELD_SEPARATOR)
    if not separator or not re.fullmatch(FIELD_NAME_PATTERN, name):
        return Token(TokenKind.WORD, word, start + 1), end
    if value:
        return Token(TokenKind.FIELD_VALUE, value, start + 1, field=name), end
    if end < len(query) and query[end] == QUERY_PHRASE_QUOTE:
        phrase, end_after_phrase = read_phrase(query, end)
        return Token(TokenKind.FIELD_VALUE, phrase, start + 1, field=name), end_after_phrase
    fail(f"the field at position {start + 1} needs a value, e.g. level:ERROR.")


class QueryParser:
    """Recursive descent over the tokens: OR binds loosest, then AND, then NOT."""

    def __init__(self, tokens: list[Token]) -> None:
        """Create a parser over `tokens` (at least one)."""
        self._tokens = tokens
        self._index = 0
        self._depth = 0

    def parse(self) -> Condition:
        """Parse every token into one condition."""
        condition = self._or_expression()
        leftover = self._current()
        if leftover is not None:
            fail(f"unexpected '{leftover.text}' at position {leftover.position}.")
        return condition

    def _or_expression(self) -> Condition:
        terms = [self._and_expression()]
        while self._at(TokenKind.OR):
            self._take_keyword_with_term_after()
            terms.append(self._and_expression())
        return terms[0] if len(terms) == 1 else AnyOf(tuple(terms))

    def _and_expression(self) -> Condition:
        terms = [self._unary()]
        while True:
            if self._at(TokenKind.AND):
                self._take_keyword_with_term_after()
            elif not self._at_term_start():
                break
            terms.append(self._unary())
        return terms[0] if len(terms) == 1 else AllOf(tuple(terms))

    def _unary(self) -> Condition:
        if not self._at(TokenKind.NOT):
            return self._primary()
        not_token = self._take()
        if not self._at_term_start():
            fail(f"NOT at position {not_token.position} needs a term after it.")
        self._enter_nesting(not_token)
        condition = NotCondition(self._unary())
        self._depth -= 1
        return condition

    def _primary(self) -> Condition:
        token = self._current()
        if token is None:
            fail("the query ends where a term is expected.")
        if token.kind in (TokenKind.AND, TokenKind.OR):
            fail(f"{token.kind} at position {token.position} needs a term on both sides.")
        if token.kind == TokenKind.RIGHT_PAREN:
            fail(f"unexpected ')' at position {token.position}.")
        self._take()
        if token.kind == TokenKind.LEFT_PAREN:
            return self._group(token)
        if token.kind == TokenKind.FIELD_VALUE and token.field is not None:
            return FieldMatch(token.field, Operator.EQUALS, token.text)
        return TextMatch(token.text, exact_phrase=token.kind == TokenKind.PHRASE)

    def _group(self, opening: Token) -> Condition:
        self._enter_nesting(opening)
        inner = self._or_expression()
        if not self._at(TokenKind.RIGHT_PAREN):
            fail(f"missing closing bracket for the one at position {opening.position}.")
        self._take()
        self._depth -= 1
        return inner

    def _enter_nesting(self, token: Token) -> None:
        self._depth += 1
        if self._depth > MAX_QUERY_NESTING:
            fail(f"nested more than {MAX_QUERY_NESTING} deep at position {token.position}.")

    def _take_keyword_with_term_after(self) -> None:
        keyword = self._take()
        if not self._at_term_start():
            fail(f"{keyword.kind} at position {keyword.position} needs a term on both sides.")

    def _current(self) -> Token | None:
        return self._tokens[self._index] if self._index < len(self._tokens) else None

    def _at(self, kind: TokenKind) -> bool:
        current = self._current()
        return current is not None and current.kind == kind

    def _at_term_start(self) -> bool:
        current = self._current()
        return current is not None and current.kind in TERM_STARTS

    def _take(self) -> Token:
        token = self._tokens[self._index]
        self._index += 1
        return token
