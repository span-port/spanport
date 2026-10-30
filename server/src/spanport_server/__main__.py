"""Entry point: `python -m spanport_server` starts the API server."""

import uvicorn

from spanport_server.core.config import Settings, load_settings
from spanport_server.core.constants import APP_IMPORT_PATH
from spanport_server.core.logging import build_logging_config


def main() -> None:
    """Start uvicorn with the settings and NDJSON logging."""
    settings = load_settings(Settings)
    uvicorn.run(
        APP_IMPORT_PATH,
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
        log_config=build_logging_config(settings.log_level),
    )


if __name__ == "__main__":
    main()
