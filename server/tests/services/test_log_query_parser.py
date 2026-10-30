import re

import pytest

from spanport_server.core.errors import InvalidRequestError
from spanport_server.core.log_query_model import (
    AllOf,
    AnyOf,
    FieldMatch,
    NotCondition,
    Operator,
    TextMatch,
)
from spanport_server.schemas.log_search import FilterChip
from spanport_server.services.log_query_parser import build_condition, parse_query


def word(text: str) -> TextMatch:
    return TextMatch(text, exact_phrase=False)


def equals(field: str, value: str) -> FieldMatch:
    return FieldMatch(field, Operator.EQUALS, value)


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_empty_query_has_no_condition(query: str) -> None:
    assert parse_query(query) is None


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("timeout", word("timeout")),
        ("timeout deadlock", AllOf((word("timeout"), word("deadlock")))),
        ("timeout AND deadlock", AllOf((word("timeout"), word("deadlock")))),
        ("timeout OR deadlock", AnyOf((word("timeout"), word("deadlock")))),
        ("-healthcheck", NotCondition(word("healthcheck"))),
        ("NOT healthcheck", NotCondition(word("healthcheck"))),
        ('"connection reset"', TextMatch("connection reset", exact_phrase=True)),
        ("level:ERROR", equals("level", "ERROR")),
        ('service:"hr portal"', equals("service", "hr portal")),
        ("ip:45.142.*", equals("ip", "45.142.*")),
        ("user.id:u-42", equals("user.id", "u-42")),
        ("dead*", word("dead*")),
        ("order-1042", word("order-1042")),
        ("and or not", AllOf((word("and"), word("or"), word("not")))),
    ],
)
def test_parses_each_piece_of_the_syntax(query: str, expected: object) -> None:
    assert parse_query(query) == expected


def test_and_binds_tighter_than_or() -> None:
    assert parse_query("a b OR c") == AnyOf((AllOf((word("a"), word("b"))), word("c")))


def test_brackets_group() -> None:
    assert parse_query("(a OR b) c") == AllOf((AnyOf((word("a"), word("b"))), word("c")))


def test_full_example_from_the_prd() -> None:
    query = 'level:ERROR (timeout OR deadlock) -healthcheck "connection reset"'

    assert parse_query(query) == AllOf(
        (
            equals("level", "ERROR"),
            AnyOf((word("timeout"), word("deadlock"))),
            NotCondition(word("healthcheck")),
            TextMatch("connection reset", exact_phrase=True),
        )
    )


def test_not_applies_to_a_group() -> None:
    assert parse_query("-(a OR b)") == NotCondition(AnyOf((word("a"), word("b"))))


@pytest.mark.parametrize(
    ("query", "expected_message"),
    [
        ("(timeout", "missing closing bracket for the one at position 1"),
        ("timeout)", "unexpected ')' at position 8"),
        ('"connection reset', "missing closing quote for the one at position 1"),
        ('""', "empty phrase at position 1"),
        ("timeout AND", "AND at position 9 needs a term on both sides"),
        ("OR timeout", "OR at position 1 needs a term on both sides"),
        ("a OR OR b", "OR at position 3 needs a term on both sides"),
        ("NOT", "NOT at position 1 needs a term after it"),
        ("level:", "the field at position 1 needs a value"),
        ("()", "unexpected ')' at position 2"),
    ],
)
def test_invalid_queries_get_a_plain_error_with_the_position(
    query: str, expected_message: str
) -> None:
    with pytest.raises(InvalidRequestError, match=re.escape(expected_message)):
        parse_query(query)


def test_errors_never_repeat_the_query_text() -> None:
    with pytest.raises(InvalidRequestError) as raised:
        parse_query('secret-customer-name "unclosed')

    assert "secret-customer-name" not in raised.value.detail


def test_deep_brackets_are_refused() -> None:
    with pytest.raises(InvalidRequestError, match="nested more than 20 deep"):
        parse_query("(" * 21 + "a" + ")" * 21)


def test_long_not_chains_are_refused_instead_of_exhausting_the_stack() -> None:
    with pytest.raises(InvalidRequestError, match="nested more than 20 deep"):
        parse_query("NOT " * 500 + "a")


def test_twenty_levels_of_brackets_are_allowed() -> None:
    assert parse_query("(" * 20 + "a" + ")" * 20) == word("a")


def chip(field: str, operator: Operator, value: str) -> FilterChip:
    return FilterChip(field=field, operator=operator, value=value)


def test_no_chips_and_no_query_means_no_condition() -> None:
    assert build_condition([], "and", "") is None


def test_chips_join_with_and_or_or() -> None:
    chips = [chip("level", Operator.EQUALS, "ERROR"), chip("message", Operator.CONTAINS, "pay")]

    assert build_condition(chips, "and", "") == AllOf(
        (equals("level", "ERROR"), FieldMatch("message", Operator.CONTAINS, "pay"))
    )
    assert build_condition(chips, "or", "") == AnyOf(
        (equals("level", "ERROR"), FieldMatch("message", Operator.CONTAINS, "pay"))
    )


def test_values_of_one_field_are_alternatives_and_fields_must_all_match() -> None:
    chips = [
        chip("level", Operator.EQUALS, "WARN"),
        chip("service", Operator.EQUALS, "api"),
        chip("level", Operator.EQUALS, "ERROR"),
        chip("ip", Operator.NOT_EQUALS, "10.0.0.1"),
        chip("ip", Operator.NOT_EQUALS, "10.0.0.2"),
    ]

    assert build_condition(chips, "and", "") == AllOf(
        (
            AnyOf((equals("level", "WARN"), equals("level", "ERROR"))),
            equals("service", "api"),
            AllOf(
                (
                    FieldMatch("ip", Operator.NOT_EQUALS, "10.0.0.1"),
                    FieldMatch("ip", Operator.NOT_EQUALS, "10.0.0.2"),
                )
            ),
        )
    )


def test_chips_and_query_must_both_match() -> None:
    chips = [chip("service", Operator.NOT_EQUALS, "worker")]

    assert build_condition(chips, "or", "timeout") == AllOf(
        (FieldMatch("service", Operator.NOT_EQUALS, "worker"), word("timeout"))
    )
