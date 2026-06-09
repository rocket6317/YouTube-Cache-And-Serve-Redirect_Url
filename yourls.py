import json
import logging
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("yourls")


def create_short_url(handle):
    api_url = os.getenv("YOURLS_API_URL")
    username = os.getenv("YOURLS_USER")
    password = os.getenv("YOURLS_PASS")
    stream_base_url = os.getenv("PUBLIC_STREAM_BASE_URL")
    if not all((api_url, username, password, stream_base_url)):
        return None

    long_url = f"{stream_base_url.rstrip('/')}/stream?name={handle}"
    payload = urlencode(
        {
            "username": username,
            "password": password,
            "action": "shorturl",
            "format": "json",
            "url": long_url,
            "keyword": handle,
            "title": f"YouTube stream: {handle}",
        }
    ).encode()
    try:
        request = Request(api_url, data=payload, method="POST")
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        short_url = result.get("shorturl")
        if short_url:
            return short_url
        logger.warning("[YOURLS] Could not shorten %s: %s", handle, result.get("message"))
    except Exception as exc:
        logger.warning("[YOURLS] Could not shorten %s: %s", handle, exc)
    return None
