"""Builds the OpenTelemetry pipeline: Python logging → batch → OTLP/HTTP → collector."""

import logging

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogRecordExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from spanport._constants import (
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    EXPORT_PATH_LOGGER_PREFIXES,
    OTLP_LOGS_PATH,
)


def is_app_log(record: logging.LogRecord) -> bool:
    """False for records from the SDK or its export path, which must never be exported."""
    return not record.name.startswith(EXPORT_PATH_LOGGER_PREFIXES)


def build_otlp_exporter(collector_url: str, data_key: str) -> OTLPLogExporter:
    """Exporter that sends batches to the collector with the data key as a bearer token.

    Args:
        collector_url: Base URL of the OTel Collector, e.g. "http://localhost:4318".
        data_key: The raw data key.

    Returns:
        The OTLP/HTTP (protobuf) log exporter.
    """
    return OTLPLogExporter(
        endpoint=collector_url.rstrip("/") + OTLP_LOGS_PATH,
        headers={AUTHORIZATION_HEADER: BEARER_PREFIX + data_key},
    )


def build_logging_handler(
    service: str, exporter: LogRecordExporter
) -> tuple[LoggingHandler, LoggerProvider]:
    """Build a logging handler that batches records in the background and hands them to `exporter`.

    Records written inside an OpenTelemetry span carry that span's trace_id and span_id.

    Args:
        service: Service name shown in Spanport, e.g. "hr-portal-api".
        exporter: Where batches go; OTLP in real use, in-memory in tests.

    Returns:
        The handler to attach to a logger, and the provider that must be shut down to flush.
    """
    logger_provider = LoggerProvider(resource=Resource.create({SERVICE_NAME: service}))
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    logging_handler = LoggingHandler(logger_provider=logger_provider)
    logging_handler.addFilter(is_app_log)
    return logging_handler, logger_provider
