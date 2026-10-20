import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from iran_downloads_mcp import http
from iran_downloads_mcp.server import mcp

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fresh_http_client(monkeypatch):
    """The shared httpx client is bound to one event loop; each test gets a new loop."""
    monkeypatch.setattr(http, "RETRY_DELAY", 0)
    monkeypatch.setattr(http, "JITTER", (0, 0))
    http.set_transport(None)
    yield
    http.set_transport(None)


@pytest.fixture
def feeds():
    """Route table for a fake upstream: feeds["host/path"] = body bytes, or a callable(request) -> httpx.Response.

    Unknown routes return 404. Every request is appended to feeds.calls.
    """

    class Routes(dict):
        calls: list[httpx.Request]

    routes = Routes()
    routes.calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        routes.calls.append(request)
        target = routes.get(request.url.host + request.url.path)
        if target is None:
            return httpx.Response(404, text="no fake route")
        if callable(target):
            return target(request)
        return httpx.Response(200, content=target, headers={"content-type": "application/rss+xml"})

    http.set_transport(httpx.MockTransport(handler))
    return routes


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        call_tool = c.call_tool

        async def parsed(*args, **kwargs):
            result = await call_tool(*args, **kwargs)
            if not result.is_error:
                result.structured_content = json.loads(result.content[0].text)
            return result

        c.call_tool = parsed
        yield c
