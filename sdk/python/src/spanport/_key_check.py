"""Checks the data key once against the Spanport server and says clearly if it is wrong.

The collector accepts logs without checking keys, so without this an app with a wrong key would
lose its logs silently.
"""

import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus

from spanport._constants import (
    ALLOWED_URL_SCHEMES,
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    CURRENT_API_KEY_PATH,
    KEY_CHECK_TIMEOUT_SECONDS,
    VISIBLE_KEY_SUFFIX_LENGTH,
)
from spanport._sdk_logger import get_sdk_logger


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Never follow redirects: urllib would resend the Authorization header (the data key) to
    whatever host the redirect names. A redirect becomes an HTTPError with its 3xx code instead.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        """Refuse every redirect."""
        return None


def check_data_key(server_url: str, data_key: str) -> bool:
    """Ask the server whether the data key is valid and log the answer. Never raises.

    Args:
        server_url: Base URL of the Spanport server, e.g. "https://spanport.example.com".
        data_key: The raw data key (sp_ingest_...). Only its last characters are ever logged.

    Returns:
        True if the server accepted the key; False if it rejected it or could not be asked.
    """
    sdk_logger = get_sdk_logger()
    key_suffix = data_key[-VISIBLE_KEY_SUFFIX_LENGTH:]
    if urllib.parse.urlsplit(server_url).scheme not in ALLOWED_URL_SCHEMES:
        sdk_logger.warning("server_url must start with http:// or https://; key not checked")
        return False
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        server_url.rstrip("/") + CURRENT_API_KEY_PATH,
        headers={AUTHORIZATION_HEADER: BEARER_PREFIX + data_key},
    )
    opener = urllib.request.build_opener(RefuseRedirects())
    try:
        with opener.open(request, timeout=KEY_CHECK_TIMEOUT_SECONDS):
            sdk_logger.info("data key ...%s accepted", key_suffix)
            return True
    except urllib.error.HTTPError as error:
        # The error holds the open response; its body isn't needed, so release it now.
        error.close()
        if error.code == HTTPStatus.UNAUTHORIZED:
            sdk_logger.error(
                "data key ...%s was rejected by %s; logs will NOT be stored. "
                "Check the key, or create one with create-data-key.",
                key_suffix,
                server_url,
            )
        else:
            sdk_logger.warning("could not check data key ...%s: HTTP %d", key_suffix, error.code)
        return False
    except OSError as error:
        sdk_logger.warning(
            "could not reach %s to check data key ...%s: %s", server_url, key_suffix, error
        )
        return False
