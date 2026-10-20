import json

import httpx
import pytest
from conftest import fixture

from iran_downloads_mcp import downloads as d
from iran_downloads_mcp.registry import TOOLS

pytestmark = pytest.mark.anyio

CHROME_P30 = "https://p30download.ir/fa/entry/101588/google-chrome"
CHROME_SOFT98 = "https://soft98.ir/internet/web-browser/244-google-chrome-desktop.html"
CHROME_DL = "https://downloadly.ir/software/internet/google-chrome/"


# ---- helpers


def test_jalali_dates():
    assert d._jalali("24 مهر 1405") == "2026-10-16"
    assert d._jalali("00:47 - 1405/7/24 | 2026.10.16") == "2026-10-16"
    assert d._jalali("۱ فروردین ۱۴۰۵") == "2026-03-21"
    assert d._jalali("1403/12/30") == "2025-03-20"
    assert d._jalali("no date") is None


def test_iso_dates():
    assert d._iso("Sun, 18 Oct 2026 19:15:35 +0330") == "2026-10-18T15:45:35Z"
    assert d._iso("2026-10-20T13:21:21+00:00") == "2026-10-20T13:21:21Z"
    assert d._iso("2026-10-19T12:10:59") == "2026-10-19T12:10:59Z"
    assert d._iso("2026-10-19") == "2026-10-19"
    assert d._iso("garbage") is None


def test_version_from_title():
    assert d._version("Google Chrome 155.0.8059.85 Win/Mac") == "155.0.8059.85"
    assert d._version("Firefox v9.1 x64") == "9.1"
    assert d._version("Windows 11 25H2") is None


def test_safe_drops_password_and_crack_sentences():
    text = "یک برنامه خوب است. گذرواژه فایل: abc. Crack included. نصب ساده است"
    assert d._safe(text) == "یک برنامه خوب است. نصب ساده است"


def test_html_tree_keeps_lines_and_survives_unclosed_tags():
    n = d.parse_html(b"<div><p>a<br>b<li>c<li>d</div><b>x")
    assert n.lines() == ["a", "b", "c", "d", "x"]
    deep = d.parse_html(("<div>" * 3000 + "end").encode())
    assert deep.text() == "end"


# ---- parsers on real trimmed pages


def test_soft98_search_page():
    items = d.parse_soft98_list(fixture("soft98_search.html"))
    assert len(items) == 3
    assert items[0]["url"] == CHROME_SOFT98
    assert items[0]["title"].startswith("Google Chrome 155.0.8059.85")
    assert items[0]["category"] == "اینترنت / مرورگر وب"
    assert items[0]["date"] == "2026-10-16"
    assert items[0]["summary"]


def test_soft98_item_page():
    r = d.parse_soft98_item(fixture("soft98_item.html"), CHROME_SOFT98)
    assert r["version"] == "155.0.8059.85"
    assert r["date"] == "2026-10-16"
    assert "Windows 7/8/10/11" in r["requirements"]
    assert "size" not in r and r["description"]


def test_p30_feed():
    items = d.parse_p30_feed(fixture("p30_rss.xml"))
    assert len(items) == 3
    assert items[0]["url"] == "https://p30download.ir/fa/entry/77366/figrcollage"
    assert items[0]["title"].startswith("FigrCollage Professional Edition v3.3.9")
    assert items[0]["category"] == "نرم افزار / ویرایشگر عکس"
    assert items[0]["date"] == "2018-01-23T00:00:00Z" or items[0]["date"].endswith("Z")
    assert "<" not in (items[0]["summary"] or "")


def test_p30_search_page():
    items = d.parse_p30_list(fixture("p30_search.html"))
    assert len(items) == 3
    assert items[0]["url"] == CHROME_P30
    assert items[0]["size"] == "162 مگابایت"
    assert items[0]["date"] == "2026-10-19"
    assert items[0]["category"] == "نرم افزار / اینترنت / مرورگر اینترنت"


def test_p30_item_page():
    r = d.parse_p30_item(fixture("p30_item.html"), CHROME_P30)
    assert r["version"] == "v155.0.8059.85 x86/x64"
    assert r["size"] == "162 مگابایت"
    assert r["date"] == "2026-10-16"
    assert r["maker"] == "گوگل / Google"
    assert "Free disk space" in r["requirements"]
    assert r["category"] == "نرم افزار / اینترنت / مرورگر اینترنت"


def test_downloadly_search_page():
    items = d.parse_downloadly_list(fixture("dl_search.html"))
    assert len(items) == 2
    assert items[1]["url"] == CHROME_DL
    assert items[1]["date"].endswith("Z")
    assert items[1]["category"]


def test_downloadly_item_page_has_no_password_or_links():
    r = d.parse_downloadly_item(fixture("dl_item.html"), CHROME_DL)
    assert r["version"] == "149.0.7827.53"
    assert "مگابایت" in r["size"]
    assert "Windows" in r["requirements"]
    assert r["description"]
    blob = json.dumps(r, ensure_ascii=False)
    assert "گذرواژه" not in blob and "www.downloadly.ir" not in blob and "dl2." not in blob


def test_vgdl_posts():
    items = d.parse_vgdl_posts(fixture("vgdl_posts.json"))
    assert len(items) == 3
    assert items[0]["url"] == "https://vgdl.ir/pc-the-witcher-3-wild-hunt-remastered/" or items[0]["url"].startswith(
        "https://vgdl.ir/"
    )
    assert "&#" not in items[0]["title"] and "–" in items[0]["title"]
    assert items[0]["date"].endswith("Z")


# ---- tools through the MCP client


def _routes(feeds):
    feeds["soft98.ir/"] = fixture("soft98_search.html")
    feeds["p30download.ir/search/chrome"] = fixture("p30_search.html")
    feeds["downloadly.ir/"] = fixture("dl_search.html")
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = fixture("vgdl_posts.json")


async def test_tool_set_has_no_download_tool(client):
    names = {t.name for t in (await client.list_tools()).tools}
    assert names == {"dl_list_sources", "dl_search", "dl_latest", "dl_item"} == {fn.__name__ for fn, _ in TOOLS}
    for t in (await client.list_tools()).tools:
        assert t.annotations.read_only_hint is True


async def test_list_sources(client):
    r = (await client.call_tool("dl_list_sources", {})).structured_content
    by_id = {s["id"]: s for s in r["sources"]}
    assert list(by_id) == ["soft98", "p30download", "downloadly", "vgdl"]
    assert by_id["soft98"]["latest"] is False
    assert by_id["vgdl"]["categories"]["game"]


async def test_search_all_sources(client, feeds):
    _routes(feeds)
    r = (await client.call_tool("dl_search", {"query": "chrome"})).structured_content
    assert r["errors"] == {}
    assert {i["source"] for i in r["items"]} == {"soft98", "p30download", "downloadly", "vgdl"}
    assert all(sum(i["source"] == s for i in r["items"]) <= 3 for s in d.SOURCES)
    assert all(i["url"].startswith("https://") for i in r["items"])


async def test_search_one_source_and_page_params(client, feeds):
    _routes(feeds)
    feeds["soft98.ir/"] = lambda req: httpx.Response(200, content=fixture("soft98_search.html"))
    await client.call_tool("dl_search", {"query": "chrome", "sources": ["soft98"], "page": 2})
    q = feeds.calls[-1].url.params
    assert q["story"] == "chrome" and q["search_start"] == "2" and q["result_from"] == "9"
    await client.call_tool("dl_search", {"query": "chrome", "sources": ["vgdl"], "page": 3})
    q = feeds.calls[-1].url.params
    assert q["search"] == "chrome" and q["page"] == "3"


async def test_search_failing_source_is_reported(client, feeds):
    _routes(feeds)
    feeds["p30download.ir/search/chrome"] = lambda req: httpx.Response(403)
    r = (await client.call_tool("dl_search", {"query": "chrome"})).structured_content
    assert "403" in r["errors"]["p30download"]
    assert {i["source"] for i in r["items"]} == {"soft98", "downloadly", "vgdl"}


async def test_search_vgdl_page_past_the_end_is_empty(client, feeds):
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = lambda req: httpx.Response(
        400, json={"code": "rest_post_invalid_page_number"}
    )
    r = (await client.call_tool("dl_search", {"query": "chrome", "sources": ["vgdl"], "page": 9})).structured_content
    assert r["items"] == [] and r["errors"] == {}


async def test_search_rejects_unknown_source_and_short_query(client, feeds):
    assert (await client.call_tool("dl_search", {"query": "chrome", "sources": ["nope"]})).is_error
    assert (await client.call_tool("dl_search", {"query": "c"})).is_error


async def test_latest_merges_and_skips_soft98(client, feeds):
    feeds["p30download.ir/fa/main/feed/rss.xml"] = fixture("p30_rss.xml")
    feeds["downloadly.ir/"] = fixture("dl_search.html")
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = fixture("vgdl_posts.json")
    r = (await client.call_tool("dl_latest", {})).structured_content
    assert r["errors"] == {}
    assert {i["source"] for i in r["items"]} == {"p30download", "downloadly", "vgdl"}
    dates = [i["date"] for i in r["items"]]
    assert dates == sorted(dates, reverse=True)


async def test_latest_category_and_errors(client, feeds):
    feeds["p30download.ir/fa/game/feed/rss.xml"] = fixture("p30_rss.xml")
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = fixture("vgdl_posts.json")
    r = (
        await client.call_tool("dl_latest", {"sources": ["p30download", "soft98", "vgdl"], "category": "game"})
    ).structured_content
    assert "no latest" in r["errors"]["soft98"]
    assert "vgdl" not in r["errors"]
    assert feeds.calls[-1].url.params.get("categories") == "8"
    r = (await client.call_tool("dl_latest", {"sources": ["p30download"], "category": "nope"})).structured_content
    assert "no category" in r["errors"]["p30download"]


async def test_item_dispatch_by_host(client, feeds):
    feeds["p30download.ir/fa/entry/101588/google-chrome"] = fixture("p30_item.html")
    r = (await client.call_tool("dl_item", {"url": CHROME_P30})).structured_content
    assert r["source"] == "p30download" and r["size"] == "162 مگابایت"
    feeds["soft98.ir/internet/web-browser/244-google-chrome-desktop.html"] = fixture("soft98_item.html")
    r = (await client.call_tool("dl_item", {"url": CHROME_SOFT98})).structured_content
    assert r["source"] == "soft98" and r["date"] == "2026-10-16"
    feeds["downloadly.ir/software/internet/google-chrome/"] = fixture("dl_item.html")
    r = (await client.call_tool("dl_item", {"url": CHROME_DL})).structured_content
    assert r["source"] == "downloadly" and r["requirements"]


async def test_item_vgdl_uses_rest_by_slug(client, feeds):
    post = {**json.loads(fixture("vgdl_posts.json"))[0], "categories": [1, 2]}
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = lambda req: httpx.Response(200, json=[post])
    feeds["vgdl.ir/wp-json/wp/v2/categories"] = lambda req: httpx.Response(
        200, json=[{"name": "&#1576;&#1575;&#1586;&#1740;"}, {"name": "FPS"}]
    )
    r = (await client.call_tool("dl_item", {"url": post["link"]})).structured_content
    assert r["source"] == "vgdl" and r["category"].endswith("FPS") and r["date"].endswith("Z")
    assert feeds.calls[0].url.params["slug"] == "pc-the-witcher-3-wild-hunt-remastered"
    assert "size" not in r and "requirements" not in r


async def test_item_errors(client, feeds):
    assert (await client.call_tool("dl_item", {"url": "https://example.com/x"})).is_error
    assert (await client.call_tool("dl_item", {"url": "https://vgdl.ir/"})).is_error
    feeds["vgdl.ir/wp-json/wp/v2/posts"] = b"[]"
    assert (await client.call_tool("dl_item", {"url": "https://vgdl.ir/nothing/"})).is_error
    feeds["soft98.ir/a.html"] = b"<html><body>no item</body></html>"
    assert (await client.call_tool("dl_item", {"url": "https://soft98.ir/a.html"})).is_error


async def test_max_reply_stays_under_15kb(client, feeds):
    _routes(feeds)
    res = await client.call_tool("dl_search", {"query": "chrome", "per_source": 5})
    assert len(res.content[0].text.encode()) < 15_000


def test_downloadly_size_skips_rating_line():
    page = (
        '<h1 class="post_title">App 1.2.3</h1><div><h3>حجم فایل</h3><p>12 مگابایت</p>'
        "<p>4.4/5 - (111328 امتیاز)</p></div>"
    ).encode()
    assert d.parse_downloadly_item(page, "https://downloadly.ir/x/")["size"] == "12 مگابایت"
