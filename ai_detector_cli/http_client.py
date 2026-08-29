"""
High-performance stdlib HTTP layer for AI Detector engines.

Features:
- Per-host persistent connection pools (HTTP keep-alive) so repeated requests
  skip the TCP+TLS handshake (2-4x faster for multi-request workloads).
- Automatic retries with exponential backoff + jitter on transient failures
  (timeouts, connection resets, 5xx).
- Global timeout control (``configure_timeout`` / ``AIDETECT_TIMEOUT`` env var).
- Pure standard library: no third-party dependencies required.

Thread-safety: one pooled connection per host per thread (thread-local storage),
so live engines running concurrently in the ThreadPoolExecutor never contend.
"""

import http.client
import json
import os
import random
import ssl
import threading
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 10.0
_timeout_lock = threading.Lock()
_default_timeout = _DEFAULT_TIMEOUT

# Thread-local connection pools: {origin: HTTPSConnection/HTTPConnection}
_local = threading.local()

_SSL_CONTEXT = ssl.create_default_context()

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def configure_timeout(seconds: float) -> None:
    """Set the default request timeout used by all engines."""
    global _default_timeout
    with _timeout_lock:
        _default_timeout = max(1.0, float(seconds))


def get_default_timeout() -> float:
    with _timeout_lock:
        return _default_timeout


def _load_env_timeout() -> None:
    env_timeout = os.environ.get("AIDETECT_TIMEOUT")
    if env_timeout:
        try:
            configure_timeout(float(env_timeout))
        except ValueError:
            pass


_load_env_timeout()


# ---------------------------------------------------------------------------
# Connection pooling
# ---------------------------------------------------------------------------

def _get_pooled_connection(origin: str, timeout: float):
    """Return a live keep-alive connection for ``origin`` or None."""
    pool = getattr(_local, "pool", None)
    if pool is None:
        pool = {}
        _local.pool = pool
    conn = pool.get(origin)
    if conn is None:
        return None
    # Test socket liveness cheaply; drop dead connections.
    if conn.sock is None:
        try:
            conn.close()
        except Exception:
            pass
        del pool[origin]
        return None
    conn.timeout = timeout
    return conn


def _store_connection(origin: str, conn) -> None:
    pool = getattr(_local, "pool", None)
    if pool is None:
        pool = {}
        _local.pool = pool
    old = pool.get(origin)
    if old is not None and old is not conn:
        try:
            old.close()
        except Exception:
            pass
    pool[origin] = conn


def _drop_connection(origin: str) -> None:
    pool = getattr(_local, "pool", None)
    if pool and origin in pool:
        try:
            pool[origin].close()
        except Exception:
            pass
        del pool[origin]


def close_all_connections() -> None:
    """Close every pooled connection owned by the calling thread."""
    pool = getattr(_local, "pool", None)
    if pool:
        for conn in pool.values():
            try:
                conn.close()
            except Exception:
                pass
        pool.clear()


def _new_connection(parsed, timeout: float):
    if parsed.scheme == "https":
        return http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=timeout,
            context=_SSL_CONTEXT,
        )
    return http.client.HTTPConnection(
        parsed.hostname, parsed.port or 80, timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Public request API
# ---------------------------------------------------------------------------

class HTTPResponse:
    """Lightweight response wrapper returned by :func:`request_json`."""

    __slots__ = ("status", "data", "elapsed_ms")

    def __init__(self, status: int, data: bytes, elapsed_ms: float):
        self.status = status
        self.data = data
        self.elapsed_ms = elapsed_ms

    def json(self) -> Any:
        return json.loads(self.data.decode("utf-8"))


class HTTPError(Exception):
    """Raised when all retries are exhausted or the response is unusable."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


_TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _single_request(
    parsed: urllib.parse.ParseResult,
    origin: str,
    method: str,
    path: str,
    headers: Dict[str, str],
    body: Optional[bytes],
    timeout: float,
) -> HTTPResponse:
    conn = _get_pooled_connection(origin, timeout)
    created = False
    if conn is None:
        conn = _new_connection(parsed, timeout)
        created = True

    start = time.monotonic()
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        elapsed = (time.monotonic() - start) * 1000.0
        status = resp.status
        if resp.getheader("Connection", "").lower() == "close":
            _drop_connection(origin)
        else:
            _store_connection(origin, conn)
        return HTTPResponse(status, data, elapsed)
    except Exception:
        # Connection is in an unknown state - discard it.
        _drop_connection(origin)
        if not created:
            # One immediate retry on a fresh connection (pool staleness).
            conn = _new_connection(parsed, timeout)
            try:
                conn.request(method, path, body=body, headers=headers)
                resp = conn.getresponse()
                data = resp.read()
                elapsed = (time.monotonic() - start) * 1000.0
                _store_connection(origin, conn)
                return HTTPResponse(resp.status, data, elapsed)
            except Exception:
                _drop_connection(origin)
                raise
        raise


def request(
    url: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    retries: int = 2,
    backoff_base: float = 0.45,
) -> HTTPResponse:
    """
    Perform an HTTP request with keep-alive pooling and retries.

    Args:
        url: Absolute http/https URL.
        method: HTTP verb.
        payload: JSON-serializable dict (sets Content-Type and encodes body).
        headers: Extra headers.
        timeout: Per-request timeout in seconds (default: global config).
        retries: Number of retry attempts for transient failures.
        backoff_base: Base delay for exponential backoff (with jitter).

    Returns:
        HTTPResponse (never raises for HTTP error statuses; caller inspects
        ``.status``). Raises HTTPError only on unrecoverable network failures.
    """
    parsed = urllib.parse.urlsplit(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    if timeout is None:
        timeout = get_default_timeout()

    body: Optional[bytes] = None
    final_headers: Dict[str, str] = {"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"}
    if headers:
        final_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        final_headers.setdefault("Content-Type", "application/json")
        final_headers["Content-Length"] = str(len(body))

    attempt = 0
    last_error: Optional[Exception] = None
    while attempt <= retries:
        try:
            resp = _single_request(parsed, origin, method, path, final_headers, body, timeout)
            if resp.status in _TRANSIENT_STATUSES and attempt < retries:
                attempt += 1
                time.sleep(backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.15))
                continue
            return resp
        except Exception as exc:  # URLError, timeouts, ssl errors...
            last_error = exc
            if attempt < retries:
                attempt += 1
                time.sleep(backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.15))
                continue
            break
    raise HTTPError(f"Request to {url} failed after {attempt} attempt(s): {last_error}")


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    retries: int = 2,
) -> HTTPResponse:
    """Convenience wrapper: POST JSON, get HTTPResponse back."""
    return request(url, method="POST", payload=payload, headers=headers,
                   timeout=timeout, retries=retries)


def post_json_parsed(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    retries: int = 2,
) -> Tuple[int, Any, float]:
    """POST JSON and return ``(status, parsed_json_body, elapsed_ms)``."""
    resp = post_json(url, payload, headers=headers, timeout=timeout, retries=retries)
    try:
        return resp.status, resp.json(), resp.elapsed_ms
    except ValueError:
        return resp.status, None, resp.elapsed_ms
