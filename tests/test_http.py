import httpx
import pytest

from iran_downloads_mcp import http

pytestmark = pytest.mark.anyio

URL = "https://vgdl.ir/wp-json/wp/v2/posts"


async def test_cache_hit(feeds):
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = b"[]"
    await http.fetch(URL, "json")
    await http.fetch(URL, "json")
    assert len(feeds.calls) == 1


async def test_retry_on_500_then_ok(feeds):
    n = {"c": 0}

    def flaky(req):
        n["c"] += 1
        return httpx.Response(500) if n["c"] == 1 else httpx.Response(200, content=b"[]")

    feeds["vgdl.ir/wp-json/wp/v2/posts"] = flaky
    assert await http.fetch(URL, "json") == b"[]"
    assert n["c"] == 2


async def test_403_not_retried_and_message(feeds):
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = lambda req: httpx.Response(403)
    with pytest.raises(http.ApiError, match="403"):
        await http.fetch(URL, "json")
    assert len(feeds.calls) == 1


async def test_html_is_not_json_and_not_cached(feeds):
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = lambda req: httpx.Response(200, content=b"<html>Wait</html>")
    with pytest.raises(http.ApiError, match="web page"):
        await http.fetch(URL, "json")
    with pytest.raises(http.ApiError, match="web page"):
        await http.fetch(URL, "json")
    assert len(feeds.calls) == 2


async def test_one_redirect_to_an_allowed_host_is_followed(feeds):
    feeds["soft98.ir/a"] = lambda req: httpx.Response(301, headers={"location": "https://soft98.ir/b"})
    feeds["soft98.ir/b"] = b"<html>ok</html>"
    assert await http.fetch("https://soft98.ir/a") == b"<html>ok</html>"


async def test_redirect_off_site_is_refused(feeds):
    feeds["soft98.ir/a"] = lambda req: httpx.Response(301, headers={"location": "https://example.com/b"})
    with pytest.raises(http.ApiError, match="unexpected host"):
        await http.fetch("https://soft98.ir/a")


async def test_host_allowlist():
    with pytest.raises(http.ApiError, match="unexpected host"):
        await http.fetch("https://example.com/x")
    with pytest.raises(http.ApiError, match="unexpected host"):
        await http.fetch("http://soft98.ir/x")


def test_proxy_env_is_a_comma_list(monkeypatch):
    monkeypatch.delenv("IRAN_DOWNLOADS_MCP_PROXY", raising=False)
    assert http._proxies() == []
    monkeypatch.setenv("IRAN_DOWNLOADS_MCP_PROXY", " http://a:1 , ,http://b:2")
    assert http._proxies() == ["http://a:1", "http://b:2"]


async def test_proxy_rotates_on_block(monkeypatch, feeds):
    seen = []
    monkeypatch.setenv("IRAN_DOWNLOADS_MCP_PROXY", "http://a:1,http://b:2")
    real = httpx.AsyncClient
    monkeypatch.setattr(http.httpx, "AsyncClient", lambda **kw: real(**kw))
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = lambda req: (seen.append(http._proxy_index), httpx.Response(403))[1]
    with pytest.raises(http.ApiError):
        await http.fetch(URL, "json")
    assert http._proxy_index == 1 and http._client is None  # next call builds the client on proxy b
    assert seen == [0]


def test_proxy_reaches_the_transport(monkeypatch):
    got = {}

    class Fake(httpx.AsyncBaseTransport):
        def __init__(self, **kw):
            got.update(kw)

    monkeypatch.setattr(http, "_XhrTransport", Fake)
    monkeypatch.setenv("IRAN_DOWNLOADS_MCP_PROXY", "http://a:1,http://b:2")
    http.set_transport(None)
    http._get_client()
    assert got["proxy"] == "http://a:1"
    http._proxy_index, http._client = 1, None
    http._get_client()
    assert got["proxy"] == "http://b:2"
