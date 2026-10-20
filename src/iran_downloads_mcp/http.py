"""Shared async HTTP client for the download sites.

Every tool goes through `fetch`: one Chrome-impersonating client, a small cache, capped concurrency
and HTTP failures turned into `ToolError` messages the model can act on.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any

import httpx
from curl_cffi.const import CurlOpt
from httpx_curl_cffi import AsyncCurlTransport
from mcp.server.mcpserver.exceptions import ToolError

HEADERS = {
    # User-Agent, sec-ch-ua and TLS come from the impersonated Chrome profile (see _get_client).
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}
ACCEPT = {
    "html": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "xml": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "json": "application/json, */*;q=0.5",
}

MAX_CONCURRENCY = 4
JITTER = (0.1, 0.4)  # seconds before each uncached call
MAX_RETRIES = 2
MAX_RETRY_WAIT = 10  # cap for Retry-After and backoff, seconds
CACHE_TTL = 180  # seconds; listings change every few minutes at most
CACHE_MAX = 128
RETRY_DELAY = 0.5  # seconds, doubled per retry
MAX_BODY = 5_000_000  # bytes; larger responses are refused
HOSTS = {"soft98.ir", "p30download.ir", "downloadly.ir", "vgdl.ir"}

_transport: httpx.AsyncBaseTransport | None = None
_client: httpx.AsyncClient | None = None
_limit: asyncio.Semaphore | None = None
_proxy_index = 0
_retired: set[asyncio.Task] = set()
_cache: dict[str, tuple[float, bytes]] = {}


class _XhrTransport(AsyncCurlTransport):
    """The Chrome profile sends navigation-only headers; a None value makes curl drop them (feeds are not navigations)."""

    def _create_request_params(self, req: httpx.Request) -> dict[str, Any]:
        p = super()._create_request_params(req)
        p["headers"] = [*p["headers"], (b"upgrade-insecure-requests", None), (b"sec-fetch-user", None)]
        return p


class ApiError(ToolError):
    """A failed upstream call. `status` is the HTTP status, or None for network errors."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Swap the transport (tests use httpx.MockTransport). Drops the current client."""
    global _transport, _client, _limit, _proxy_index
    _transport, _client, _limit, _proxy_index = transport, None, None, 0
    _cache.clear()


def forget(url: str) -> None:
    """Drop one cached page."""
    _cache.pop(url, None)


def _proxies() -> list[str]:
    """IRAN_DOWNLOADS_MCP_PROXY: one proxy URL, or a comma-separated list used one at a time."""
    return [p.strip() for p in os.environ.get("IRAN_DOWNLOADS_MCP_PROXY", "").split(",") if p.strip()]


def _next_proxy(client: httpx.AsyncClient) -> None:
    """Sticky pool: move to the next proxy after a block or connect error; the next call rebuilds the client.

    Only the client that failed may rotate. The old client is closed late because other requests may still use it.
    """
    global _client, _limit, _proxy_index
    if len(_proxies()) < 2 or client is not _client:
        return
    _client, _limit, _proxy_index = None, None, _proxy_index + 1
    t = asyncio.create_task(_close_later(client))
    _retired.add(t)
    t.add_done_callback(_retired.discard)


async def _close_later(client: httpx.AsyncClient) -> None:
    await asyncio.sleep(30)  # longer than the 20 s request timeout
    await client.aclose()


def _get_client() -> tuple[httpx.AsyncClient, asyncio.Semaphore]:
    global _client, _limit
    if _client is None:
        # System proxy settings are ignored unless the user opts in with IRAN_DOWNLOADS_MCP_PROXY. curl_cffi presents
        # Chrome's TLS/HTTP2 fingerprint and default headers. The proxy goes to the transport.
        proxies = _proxies()
        _client = httpx.AsyncClient(
            transport=_transport
            or _XhrTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={
                    CurlOpt.NOPROXY: "*"
                },  # httpx-curl-cffi drops its own NOPROXY unless this dict is non-empty
                proxy=proxies[_proxy_index % len(proxies)] if proxies else None,
                max_connections=2 * MAX_CONCURRENCY,
            ),
            headers=HEADERS,
            timeout=httpx.Timeout(20, connect=5),
            limits=httpx.Limits(max_connections=2 * MAX_CONCURRENCY),
            follow_redirects=False,
            trust_env=False,
        )
        _limit = asyncio.Semaphore(MAX_CONCURRENCY)
    assert _limit is not None
    return _client, _limit


async def fetch(url: str, kind: str = "html") -> bytes:
    """GET a page (kind "html", "xml" or "json") and return the raw bytes (cached CACHE_TTL seconds).

    A GET is retried up to MAX_RETRIES times on timeout, network error, 5xx or 429, with jittered exponential
    backoff or after Retry-After when sent. 403 is never retried. One redirect to an allowed host is followed.
    A body of the wrong kind (a bot-check page where XML or JSON was expected) is an error and is not cached.
    """
    host = _host(url)
    if (hit := _cache.get(url)) and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    headers = {"Accept": ACCEPT[kind]}
    r, content = await _get(url, host, headers)
    if 300 <= r.status_code < 400 and (loc := r.headers.get("location")):
        url = str(r.url.join(loc))
        host = _host(url)
        r, content = await _get(url, host, headers)
    if r.status_code >= 300:
        raise ApiError(f"{host} redirected the request more than once (HTTP {r.status_code}).", r.status_code)
    head = content.lstrip()[:1]
    if (kind == "xml" and (head != b"<" or b"<html" in content[:500].lower())) or (
        kind == "json" and head not in (b"[", b"{")
    ):
        raise ApiError(
            f"{host} returned a web page instead of {kind.upper()} (bot check or moved endpoint). "
            "If you use a proxy outside Iran, try a direct connection.",
            r.status_code,
        )
    if len(_cache) >= CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[url] = (time.monotonic(), content)
    return content


def _host(url: str) -> str:
    u = httpx.URL(url)
    if u.scheme != "https" or u.host not in HOSTS:
        raise ApiError(
            f"Refusing to call unexpected host {u.host or url[:60]}; only the four download sites over https."
        )
    return u.host


async def _get(url: str, host: str, headers: dict[str, str] | None = None) -> tuple[httpx.Response, bytes]:
    """GET with retries; raises ApiError on 4xx/5xx and returns the response (2xx or 3xx) with its body."""
    for attempt in range(MAX_RETRIES + 1):
        last = attempt == MAX_RETRIES
        wait = RETRY_DELAY * 2**attempt * random.uniform(1, 1.5)
        try:
            r, content = await _send(url, host, headers)
        except ApiError as e:
            if last or e.status is not None:
                raise
            await asyncio.sleep(min(wait, MAX_RETRY_WAIT))
            continue
        if (r.status_code == 429 or r.status_code >= 500) and not last:
            await asyncio.sleep(min(_retry_after(r) or wait, MAX_RETRY_WAIT))
            continue
        break
    if r.status_code >= 400:
        raise ApiError(_status_message(r, host), r.status_code)
    return r, content


async def _send(url: str, host: str, headers: dict[str, str] | None = None) -> tuple[httpx.Response, bytes]:
    client, limit = _get_client()
    try:
        async with limit:
            await asyncio.sleep(random.uniform(*JITTER))
            async with client.stream("GET", url, headers=headers) as r:
                content = await _read_capped(r, host)
    except httpx.TimeoutException as e:
        raise ApiError(f"{host} did not answer in time. Try again in a moment.") from e
    except httpx.RequestError as e:
        if isinstance(e, httpx.ConnectError | httpx.ProxyError):
            _next_proxy(client)
        raise ApiError(f"Could not reach {host} ({type(e).__name__}). Check the internet connection.") from e
    if r.status_code in (403, 429):
        _next_proxy(client)
    return r, content


async def _read_capped(r: httpx.Response, host: str) -> bytes:
    """Read the body, refusing anything over MAX_BODY so one huge answer cannot flood memory."""
    buf = bytearray()
    async for chunk in r.aiter_bytes():
        buf += chunk
        if len(buf) > MAX_BODY:
            raise ApiError(f"{host} sent a response over {MAX_BODY // 1_000_000} MB; refused.", r.status_code)
    return bytes(buf)


def _retry_after(r: httpx.Response) -> float | None:
    """Seconds from a numeric Retry-After on a 429/503, else None (HTTP-date form is ignored)."""
    v = r.headers.get("retry-after", "")
    return float(v) if r.status_code in (429, 503) and v.replace(".", "", 1).isdigit() else None


def _status_message(r: httpx.Response, host: str) -> str:
    code = r.status_code
    if code == 403:
        return f"{host} blocked the request (HTTP 403). Try again later, or set IRAN_DOWNLOADS_MCP_PROXY to a proxy that exits in Iran."
    if code == 404:
        return f"Page not found on {host} (HTTP 404); the item may have been removed or the url is wrong."
    if code == 429:
        return f"{host} is rate limiting requests (HTTP 429). Wait a minute before retrying."
    if code >= 500:
        return f"{host} had a server error (HTTP {code}). Try again later."
    return f"{host} rejected the request (HTTP {code})."
