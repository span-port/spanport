"""Where the data key may be sent: which server checks it, and warnings for plain http."""

import urllib.parse

from spanport._constants import DEFAULT_SERVER_URL, LOCAL_HOSTNAMES, PLAIN_HTTP_SCHEME
from spanport._sdk_logger import get_sdk_logger


def is_local_url(url: str) -> bool:
    """Whether the URL points at this machine (localhost, 127.0.0.1 or ::1)."""
    return (urllib.parse.urlsplit(url).hostname or "") in LOCAL_HOSTNAMES


def key_check_url(collector_url: str, server_url: str | None) -> str | None:
    """The server to check the data key with, or None to skip the check.

    Without a `server_url`, the default (localhost) is used only when the collector is local
    too; otherwise the key would be sent to whatever answers on this machine, which may be
    the app itself.

    Args:
        collector_url: Where logs and traces are sent.
        server_url: The URL passed to init(), or None.
    """
    if server_url is not None:
        return server_url
    if is_local_url(collector_url):
        return DEFAULT_SERVER_URL
    get_sdk_logger().warning(
        "data key not checked: set server_url to your Spanport address (the UI's URL, "
        "e.g. https://spanport.example.com; it forwards /api to the server)"
    )
    return None


def warn_plain_http(urls: list[str]) -> None:
    """Say once on stderr if the data key would go over plain http to another machine.

    Args:
        urls: Every URL the data key is sent to.
    """
    exposed = [
        url
        for url in urls
        if urllib.parse.urlsplit(url).scheme == PLAIN_HTTP_SCHEME and not is_local_url(url)
    ]
    if exposed:
        get_sdk_logger().warning(
            "the data key is sent over plain http to %s; anyone on the network can read it. "
            "Use https://",
            ", ".join(exposed),
        )
