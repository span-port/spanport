"""Spanport SDK: send your app's existing Python logs to Spanport.

    import spanport
    spanport.init(data_key="sp_ingest_...", service="hr-portal-api")

The SDK never breaks the host app: init() never raises, logs are sent in the background, and if
anything is wrong it says so on stderr and the app carries on.
"""

import logging
import threading

from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider

from spanport._constants import (
    DATA_KEY_PREFIX,
    DEFAULT_COLLECTOR_URL,
    DEFAULT_SERVER_URL,
    KEY_CHECK_THREAD_NAME,
)
from spanport._key_check import check_data_key
from spanport._pipeline import build_logging_handler, build_otlp_exporter
from spanport._sdk_logger import get_sdk_logger

__all__ = ["init", "shutdown"]

# The active pipeline, kept so shutdown() can flush and detach it.
_active_handler: LoggingHandler | None = None
_active_provider: LoggerProvider | None = None


def init(
    data_key: str,
    service: str,
    collector_url: str = DEFAULT_COLLECTOR_URL,
    server_url: str = DEFAULT_SERVER_URL,
    check_key: bool = True,
) -> None:
    """Start sending this app's logs to Spanport. Never raises.

    Hooks the root logger, so every existing `logging` call is sent; the app's own log level
    still decides which records are written. Call once at start-up.

    Args:
        data_key: The project's data key (sp_ingest_...).
        service: Name of this app as shown in Spanport, e.g. "hr-portal-api".
        collector_url: Where logs are sent: the Spanport OTel Collector (OTLP/HTTP).
        server_url: The Spanport server, asked once whether the data key is valid.
        check_key: Set False to skip the start-up key check (e.g. no route to the server).
    """
    try:
        _start(data_key, service, collector_url, server_url, check_key)
    except Exception:
        # The host app must keep running whatever goes wrong here.
        get_sdk_logger().exception("setup failed; the app keeps running but logs are not sent")


def shutdown() -> None:
    """Send any logs still queued and stop. Safe to call more than once. Never raises."""
    global _active_handler, _active_provider
    try:
        if _active_handler is not None:
            logging.getLogger().removeHandler(_active_handler)
        if _active_provider is not None:
            _active_provider.shutdown()
    except Exception:
        get_sdk_logger().exception("shutdown failed; some queued logs may not have been sent")
    finally:
        _active_handler = None
        _active_provider = None


def _start(
    data_key: str, service: str, collector_url: str, server_url: str, check_key: bool
) -> None:
    """Validate the arguments, attach the logging pipeline and start the key check."""
    global _active_handler, _active_provider
    sdk_logger = get_sdk_logger()
    if _active_handler is not None:
        sdk_logger.warning("init() was already called; ignoring the second call")
        return
    if not data_key.startswith(DATA_KEY_PREFIX):
        sdk_logger.error("data_key must be a data key (%s...); logs are not sent", DATA_KEY_PREFIX)
        return
    if not service:
        sdk_logger.error("service must name this app, e.g. service='hr-portal-api'; logs not sent")
        return
    exporter = build_otlp_exporter(collector_url, data_key)
    _active_handler, _active_provider = build_logging_handler(service, exporter)
    logging.getLogger().addHandler(_active_handler)
    sdk_logger.info("sending logs for service %s to %s", service, collector_url)
    if check_key:
        # In the background, so a slow or unreachable server never delays the app's start-up.
        threading.Thread(
            target=check_data_key,
            args=(server_url, data_key),
            name=KEY_CHECK_THREAD_NAME,
            daemon=True,
        ).start()
