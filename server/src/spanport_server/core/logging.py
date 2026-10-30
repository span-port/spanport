"""NDJSON logging: one JSON object per line on stdout."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from spanport_server.core.constants import SERVICE_NAME
from spanport_server.core.request_context import request_id_var

# Attributes every LogRecord has; anything else was passed via `extra=` and is logged as a field.
# color_message is uvicorn's copy of the message with terminal colour codes.
SKIPPED_RECORD_ATTRIBUTES = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "color_message",
}


class NdjsonFormatter(logging.Formatter):
    """Formats a log record as one line of JSON with the standard Spanport fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Render `record` as JSON: ts, level, message, service, logger, request_id, then extras.

        Args:
            record: The log record to format.

        Returns:
            One line of JSON, without a trailing newline.
        """
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
            "logger": record.name,
        }
        request_id = request_id_var.get()
        if request_id:
            entry["request_id"] = request_id
        for attribute_name, attribute_value in vars(record).items():
            if attribute_name not in SKIPPED_RECORD_ATTRIBUTES:
                entry[attribute_name] = attribute_value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def build_logging_config(level: str, stream: str = "ext://sys.stdout") -> dict[str, Any]:
    """Build a `logging.config.dictConfig` dict that sends every logger to one stream as NDJSON.

    Uvicorn applies this dict in each process it starts, including reload workers.

    Args:
        level: Root log level, e.g. "INFO".
        stream: Where to write; the CLI uses stderr so stdout carries only its output.

    Returns:
        The dictConfig dictionary.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"ndjson": {"()": NdjsonFormatter}},
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "ndjson",
                "stream": stream,
            }
        },
        "root": {"handlers": ["stdout"], "level": level},
    }
