"""Checks log alert rules every few seconds for as long as the server runs."""

import asyncio
import logging
from datetime import UTC, datetime

from spanport_server.services.alert_check_service import AlertCheckService

logger = logging.getLogger(__name__)


async def run_alert_checks(service: AlertCheckService) -> None:
    """Check due rules, wait the service's check interval, repeat; stops when cancelled.

    A failed round (e.g. Postgres briefly down) is logged and the next round runs as usual,
    so one bad round never stops alerting for good.

    Args:
        service: The alert check service.
    """
    while True:
        try:
            checked = await service.check_due_rules(datetime.now(UTC))
            if checked:
                logger.info("alert check round done rules=%d", checked)
        except Exception:  # see docstring: the loop must outlive any one failed round
            logger.exception("alert check round failed; retrying next round")
        await asyncio.sleep(service.check_interval.total_seconds())
