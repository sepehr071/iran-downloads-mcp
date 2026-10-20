"""Calls the real download sites (run with `-m live`). Needs a connection that reaches Iranian hosts."""

import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]

ALL = ["soft98", "p30download", "downloadly", "vgdl"]


async def test_list_sources(client):
    r = (await client.call_tool("dl_list_sources", {})).structured_content
    assert [s["id"] for s in r["sources"]] == ALL


@pytest.mark.parametrize("source", ALL)
async def test_search_each_source(client, source):
    res = await client.call_tool("dl_search", {"query": "chrome", "sources": [source], "per_source": 3})
    r = res.structured_content
    assert r["errors"] == {}, r["errors"]
    assert r["items"], source
    for i in r["items"]:
        assert i["source"] == source and i["url"].startswith("https://") and i["title"]
    assert len(res.content[0].text.encode()) < 15_000


async def test_search_second_page(client):
    r = (await client.call_tool("dl_search", {"query": "adobe", "sources": ["soft98"], "page": 2})).structured_content
    assert r["items"] and r["errors"] == {}


@pytest.mark.parametrize("source", ["p30download", "downloadly", "vgdl"])
async def test_latest_each_source(client, source):
    r = (await client.call_tool("dl_latest", {"sources": [source], "per_source": 3})).structured_content
    assert r["errors"] == {}, r["errors"]
    assert r["items"]


async def test_latest_category_and_default_all(client):
    r = (await client.call_tool("dl_latest", {"category": "software"})).structured_content
    assert {i["source"] for i in r["items"]} >= {"p30download", "downloadly", "vgdl"}
    assert (await client.call_tool("dl_latest", {})).structured_content["errors"] == {}


@pytest.mark.parametrize("source", ALL)
async def test_item_from_search(client, source):
    hit = (
        await client.call_tool("dl_search", {"query": "chrome", "sources": [source], "per_source": 1})
    ).structured_content
    url = hit["items"][0]["url"]
    r = (await client.call_tool("dl_item", {"url": url})).structured_content
    assert r["source"] == source and r["url"] and r["title"] and r.get("description")
    blob = str(r).lower()
    assert "password" not in blob and "گذرواژه" not in blob
