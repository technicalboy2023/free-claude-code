"""Limits and defaults for outbound web server tool HTTP."""

_REQUEST_TIMEOUT_S = 30.0
_MAX_SEARCH_RESULTS = 10
_MAX_FETCH_CHARS = 24_000
# Hard cap on raw bytes read from HTTP responses before decode / HTML parse (memory bound).
_MAX_WEB_FETCH_RESPONSE_BYTES = 2 * 1024 * 1024
# Drain at most this many bytes from redirect responses before following Location.
_REDIRECT_RESPONSE_BODY_CAP_BYTES = 65_536
_MAX_WEB_FETCH_REDIRECTS = 10
_WEB_FETCH_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

_WEB_TOOL_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
