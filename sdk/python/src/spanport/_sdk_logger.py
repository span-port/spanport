"""The SDK's own logger: always visible on stderr, never exported, never mixed into app logs."""

import logging

from spanport._constants import SDK_LOG_FORMAT, SDK_LOGGER_NAME


def get_sdk_logger() -> logging.Logger:
    """Return the "spanport" logger, writing to stderr and not passing records to the root logger.

    Not propagating keeps these messages out of the export pipeline and out of the app's own log
    files, and the stderr handler keeps them visible even if the app configured no logging.
    """
    sdk_logger = logging.getLogger(SDK_LOGGER_NAME)
    if not sdk_logger.handlers:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setFormatter(logging.Formatter(SDK_LOG_FORMAT))
        sdk_logger.addHandler(stderr_handler)
        sdk_logger.setLevel(logging.INFO)
        sdk_logger.propagate = False
    return sdk_logger
