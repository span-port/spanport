import json
import logging
import sys
from collections.abc import Mapping

from spanport_server.core.logging import NdjsonFormatter
from spanport_server.core.request_context import request_id_var


def make_record(message: str, extra_fields: Mapping[str, object]) -> logging.LogRecord:
    record_fields = {"name": "spanport.test", "levelname": "INFO", "msg": message}
    return logging.makeLogRecord({**record_fields, **extra_fields})


def test_formats_standard_fields_as_one_json_line() -> None:
    line = NdjsonFormatter().format(make_record("log search rows=5", {}))

    entry = json.loads(line)
    assert "\n" not in line
    assert entry["message"] == "log search rows=5"
    assert entry["level"] == "INFO"
    assert entry["service"] == "spanport-server"
    assert entry["logger"] == "spanport.test"
    assert entry["ts"].endswith("+00:00")


def test_adds_extra_fields_and_skips_internal_record_attributes() -> None:
    extra_fields = {"project": "hr-portal", "color_message": "\x1b[1mingest\x1b[0m"}
    entry = json.loads(NdjsonFormatter().format(make_record("ingest", extra_fields)))

    assert entry["project"] == "hr-portal"
    assert "color_message" not in entry
    assert "lineno" not in entry
    assert "args" not in entry


def test_adds_the_current_request_id_only_inside_a_request() -> None:
    outside = json.loads(NdjsonFormatter().format(make_record("startup", {})))
    token = request_id_var.set("01a17751-d749-775a-8c05-4a617082d980")
    try:
        inside = json.loads(NdjsonFormatter().format(make_record("logs ingested", {})))
    finally:
        request_id_var.reset(token)

    assert "request_id" not in outside
    assert inside["request_id"] == "01a17751-d749-775a-8c05-4a617082d980"


def test_includes_exception_text() -> None:
    try:
        raise ValueError("bad batch")
    except ValueError:
        record = make_record("insert failed", {"exc_info": sys.exc_info()})

    entry = json.loads(NdjsonFormatter().format(record))

    assert "ValueError: bad batch" in entry["exception"]
