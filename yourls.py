import json
import logging
import os
from urllib.parse import quote, urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger("yourls")


def create_short_url(handle):
    api_url = os.getenv("YOURLS_API_URL")
    username = os.getenv("YOURLS_USER")
    password = os.getenv("YOURLS_PASS")
    stream_base_url = os.getenv("PUBLIC_STREAM_BASE_URL")
    if not all((api_url, username, password, stream_base_url)):
        return None

    long_url = f"{stream_base_url.rstrip('/')}/stream?name={quote(handle, safe='')}"
    keyword = handle.replace(" ", "-")
    payload = urlencode(
        {
            "username": username,
            "password": password,
            "action": "shorturl",
            "format": "json",
            "url": long_url,
            "keyword": keyword,
            "title": f"YouTube stream: {handle}",
        }
    ).encode()
    try:
        request = Request(api_url, data=payload, method="POST")
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            result = json.load(response)
        short_url = result.get("shorturl")
        if short_url:
            return short_url
        logger.warning("[YOURLS] Could not shorten %s: %s", handle, result.get("message"))
    except Exception as exc:
        logger.warning("[YOURLS] Could not shorten %s: %s", handle, exc)
    return None
