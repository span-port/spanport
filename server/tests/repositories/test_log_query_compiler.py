import pytest

from spanport_server.core.log_query_model import (
    AllOf,
    AnyOf,
    Condition,
    FieldMatch,
    NotCondition,
    Operator,
    TextMatch,
)
from spanport_server.repositories.clickhouse.log_query_compiler import compile_condition


@pytest.mark.parametrize(
    ("condition", "sql", "parameters"),
    [
        (
            FieldMatch("level", Operator.EQUALS, "error"),
            "level = {p0:String}",
            {"p0": "ERROR"},
        ),
        (
            FieldMatch("service", Operator.NOT_EQUALS, "worker"),
            "NOT (service = {p0:String})",
            {"p0": "worker"},
        ),
        (
            FieldMatch("message", Operator.CONTAINS, "pay"),
            "positionCaseInsensitive(message, {p0:String}) > 0",
            {"p0": "pay"},
        ),
        (
            FieldMatch("message", Operator.NOT_CONTAINS, "pay"),
            "NOT (positionCaseInsensitive(message, {p0:String}) > 0)",
            {"p0": "pay"},
        ),
        (
            FieldMatch("ip", Operator.EQUALS, "45.142.*"),
            "ilike(attributes[{p0:String}], {p1:String})",
            {"p0": "client.ip", "p1": "45.142.%"},
        ),
        (
            FieldMatch("order.id", Operator.EQUALS, "1042"),
            "attributes[{p0:String}] = {p1:String}",
            {"p0": "order.id", "p1": "1042"},
        ),
        (
            FieldMatch("trace", Operator.EQUALS, "0af7"),
            "trace_id = {p0:String}",
            {"p0": "0af7"},
        ),
        (
            TextMatch("timeout", exact_phrase=False),
            "hasTokenCaseInsensitive(message, {p0:String})",
            {"p0": "timeout"},
        ),
        (
            TextMatch("order-1042", exact_phrase=False),
            "positionCaseInsensitive(message, {p0:String}) > 0",
            {"p0": "order-1042"},
        ),
        (
            TextMatch("connection reset", exact_phrase=True),
            "positionCaseInsensitive(message, {p0:String}) > 0",
            {"p0": "connection reset"},
        ),
        (
            TextMatch("dead*", exact_phrase=False),
            "ilike(message, {p0:String})",
            {"p0": "%dead%%"},
        ),
    ],
)
def test_compiles_each_kind_of_match(
    condition: Condition, sql: str, parameters: dict[str, str]
) -> None:
    compiled = compile_condition(condition)

    assert compiled.sql == sql
    assert compiled.parameters == parameters


def test_compiles_nested_and_or_not() -> None:
    condition = AllOf(
        (
            FieldMatch("level", Operator.EQUALS, "ERROR"),
            AnyOf((TextMatch("timeout", False), TextMatch("deadlock", False))),
            NotCondition(TextMatch("healthcheck", False)),
        )
    )

    compiled = compile_condition(condition)

    assert compiled.sql == (
        "(level = {p0:String} AND (hasTokenCaseInsensitive(message, {p1:String}) OR "
        "hasTokenCaseInsensitive(message, {p2:String})) AND "
        "NOT (hasTokenCaseInsensitive(message, {p3:String})))"
    )
    assert compiled.parameters == {
        "p0": "ERROR",
        "p1": "timeout",
        "p2": "deadlock",
        "p3": "healthcheck",
    }


def test_like_wildcards_in_values_match_literally() -> None:
    compiled = compile_condition(FieldMatch("path", Operator.EQUALS, "100%_done\\*"))

    assert compiled.parameters["p1"] == "100\\%\\_done\\\\%"


def test_values_and_field_names_never_reach_the_sql_text() -> None:
    hostile = "x') OR 1=1 --"
    condition = AllOf(
        (
            FieldMatch(hostile, Operator.EQUALS, hostile),
            TextMatch(hostile, exact_phrase=True),
        )
    )

    compiled = compile_condition(condition)

    assert "1=1" not in compiled.sql
    assert "'" not in compiled.sql
    assert hostile in compiled.parameters.values()
