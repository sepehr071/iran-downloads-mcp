"""Download-site tools: list sources, search, latest and item detail. Metadata only: no file links, no downloads."""

from __future__ import annotations

import asyncio
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Annotated, Any
from urllib.parse import quote, quote_plus, urlsplit

from pydantic import Field

from . import http
from .registry import clip, tool

# id -> name, host and latest-listing categories {slug: (path/id/section on the site, Persian title)}.
# soft98 has no categories: its listing pages hide the item links behind script keys, so only search works there.
SOURCES: dict[str, dict[str, Any]] = {
    "soft98": {"name": "Soft98 (سافت۹۸)", "host": "soft98.ir", "latest": False, "cats": {}},
    "p30download": {
        "name": "P30Download (پی‌سی دانلود)",
        "host": "p30download.ir",
        "latest": True,
        "cats": {
            "software": ("software", "نرم‌افزار"),
            "game": ("game", "بازی"),
            "tutorial": ("tutorial", "آموزش"),
            "graphic": ("graphic", "گرافیک"),
            "console": ("console", "کنسول"),
        },
    },
    "downloadly": {
        "name": "Downloadly (دانلودلی)",
        "host": "downloadly.ir",
        "latest": True,
        "cats": {
            "software": ("download/software", "نرم‌افزار"),
            "mobile": ("download/mobile", "موبایل"),
            "multimedia": ("download/multmedia", "چندرسانه‌ای"),
            "video-tutorials": ("download/elearning/video-tutorials", "آموزش تصویری"),
        },
    },
    "vgdl": {
        "name": "VGDL (ویجی دی ال)",
        "host": "vgdl.ir",
        "latest": True,
        "cats": {
            "game": ("8", "بازی"),
            "software": ("17499", "نرم‌افزار کامپیوتر"),
            "mobile": ("34075", "موبایل"),
        },
    },
}

Sources = Annotated[
    list[str],
    Field(
        description="Source ids to include (soft98, p30download, downloadly, vgdl; see dl_list_sources). Empty = all.",
        examples=[["p30download", "downloadly"]],
    ),
]

PER_SOURCE_MAX = 5  # 4 sources x 5 brief items stay under ~15 KB
SUMMARY_LEN = 120
DESC_LEN = 600

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_VERSION = re.compile(r"(?<![\w.])[vV]?(\d+(?:\.\d+){1,5})(?![\w])")
# Passwords, cracks and activation notes are never passed on: sentences containing these words are dropped.
_SIZE = re.compile(r"مگابایت|گیگابایت|کیلوبایت|[KMG]B\b", re.I)
_RISKY = re.compile(r"password|passwd|گذرواژه|پسورد|رمز|crack|کرک|keygen|patch|پچ|activat|فعال\s?ساز", re.I)
_JALALI_MONTHS = {
    m: i for i, m in enumerate("فروردین اردیبهشت خرداد تیر مرداد شهریور مهر آبان آذر دی بهمن اسفند".split(), 1)
}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# ---------------------------------------------------------------- tiny HTML tree (stdlib html.parser)

_VOID = {"br", "img", "hr", "input", "meta", "link", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
_BLOCK = {"br", "p", "div", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer", "h1", "h2", "h3"}
_BLOCK |= {"h4", "h5", "h6"}
_RAW = {"script", "style"}


class Node:
    """An element: kids are Nodes and text strings (block tags add a "\\n" string so `lines()` keeps line breaks)."""

    def __init__(self, tag: str = "", attrs: dict[str, str] | None = None):
        self.tag, self.attrs, self.kids = tag, attrs or {}, []

    def walk(self):
        stack = [self]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(k for k in reversed(n.kids) if isinstance(k, Node))

    def all(self, tag: str | None = None, cls: str | None = None, id: str | None = None) -> list[Node]:
        return [
            n
            for n in self.walk()
            if (tag is None or n.tag == tag)
            and (cls is None or cls in n.attrs.get("class", "").split())
            and (id is None or n.attrs.get("id") == id)
        ]

    def first(self, tag: str | None = None, cls: str | None = None, id: str | None = None) -> Node | None:
        return next(iter(self.all(tag, cls, id)), None)

    def lines(self) -> list[str]:
        out, stack = [], [self]
        while stack:
            n = stack.pop()
            if isinstance(n, str):
                out.append(n)
            else:
                stack.extend(reversed(n.kids))
        return [s for s in (_WS.sub(" ", x).strip() for x in "".join(out).split("\n")) if s]

    def text(self) -> str:
        return " ".join(self.lines())


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, {k: v or "" for k, v in attrs})
        if tag in _BLOCK:
            self.stack[-1].kids.append("\n")
        self.stack[-1].kids.append(n)
        if tag in _VOID and tag in _BLOCK:  # <br>
            self.stack[-1].kids.append("\n")
        if tag not in _VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                if tag in _BLOCK:
                    self.stack[i - 1].kids.append("\n")
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.stack[-1].tag not in _RAW:
            self.stack[-1].kids.append(data)


def parse_html(data: bytes) -> Node:
    b = _Builder()
    b.feed(data.decode("utf-8", errors="replace"))
    b.close()
    return b.root


# ---------------------------------------------------------------- small helpers


def _plain(s: str | None) -> str:
    """HTML fragment (possibly CDATA) to plain text."""
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s or ""))).strip()


def _safe(text: str | None) -> str:
    """Drop sentences that mention passwords, cracks, patches or activation."""
    parts = re.split(r"(?<=[.!?؟؛])\s+|\n", text or "")
    return " ".join(p for p in parts if not _RISKY.search(p)).strip()


def _meta(root: Node, key: str) -> str:
    for m in root.all("meta"):
        if key in (m.attrs.get("property"), m.attrs.get("name")):
            return m.attrs.get("content", "").strip()
    return ""


def _jalali_to_gregorian(jy: int, jm: int, jd: int) -> str:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    feb = 29 if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0 else 28
    lengths = [0, 31, feb, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and gd > lengths[gm]:
        gd -= lengths[gm]
        gm += 1
    return f"{gy:04d}-{gm:02d}-{gd:02d}"


def _jalali(s: str | None) -> str | None:
    """'24 مهر 1405' or '1405/7/24' to an ISO date; None if it is neither."""
    s = (s or "").translate(_DIGITS)
    if m := re.search(r"(\d{1,2})\s+(\S+)\s+(\d{4})", s):
        if month := _JALALI_MONTHS.get(m.group(2)):
            return _jalali_to_gregorian(int(m.group(3)), month, int(m.group(1)))
    if m := re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", s):
        return _jalali_to_gregorian(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _iso(s: str | None) -> str | None:
    """RFC 822 or ISO 8601 (naive = UTC) to a UTC ISO string; a bare date stays a date."""
    s = (s or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    d = d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _version(title: str) -> str | None:
    """Best-effort version number from a title such as 'Google Chrome 155.0.8059.85 Win/Mac'."""
    m = _VERSION.search(title)
    return m.group(1) if m else None


def _clean_title(t: str) -> str:
    return re.sub(r"^\s*\[[^\]]*\]\s*", "", t).removeprefix("دانلود ").strip()


def _card(source: str, title: str, url: str, **extra: Any) -> dict[str, Any]:
    d = {"source": source, "title": _clean_title(html.unescape(title)), "url": url, **extra}
    d["summary"] = clip(_safe(d.get("summary")), n=SUMMARY_LEN) or None
    return d


# ---------------------------------------------------------------- per-site parsers


def parse_soft98_list(data: bytes) -> list[dict[str, Any]]:
    out = []
    for art in parse_html(data).all("article", "cbdd"):
        a = art.first("a", "cbddtl")
        if not a or not a.attrs.get("href", "").startswith("https://soft98.ir/"):
            continue
        cat, dt, body = art.first("span", "cbddic"), art.first("span", "cbddid"), art.first("div", "cbddpb")
        out.append(
            _card(
                "soft98",
                a.text(),
                a.attrs["href"],
                category=cat.text() if cat else None,
                date=_jalali(dt.text()) if dt else None,
                summary=body.text() if body else None,
            )
        )
    return out


def parse_soft98_item(data: bytes, url: str) -> dict[str, Any]:
    root = parse_html(data)
    art = root.first("article", "cbdd")
    h1 = art.first("h1") if art else None
    if art is None or h1 is None:
        raise http.ApiError("soft98.ir page has no item on it (wrong url or changed layout).")
    cat, dt, body = art.first("span", "cbddic"), art.first("span", "cbddid"), art.first("div", "cbddpb")
    req = root.first(id="tbdbcobds")
    return _detail(
        "soft98",
        url,
        h1.text(),
        category=cat.text() if cat else None,
        date=_jalali(dt.text()) if dt else None,
        description=body.text() if body else None,
        requirements=req.lines() if req else None,
    )


def parse_p30_feed(data: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise http.ApiError(f"p30download.ir returned feed XML that could not be parsed ({e}).") from e
    out = []
    for it in root.iter("item"):
        f = {c.tag.lower(): c for c in it if c.tag.lower() not in ("category",)}
        raw = (f["title"].text or "") if "title" in f else ""
        link = (f["link"].text or "").strip() if "link" in f else ""
        if not raw or not link:
            continue
        label = re.match(r"\s*\[([^\]]*)\]", raw)
        leaf = next((c.text for c in it if c.tag == "category" and "/category/" in c.get("domain", "")), None)
        cat = " / ".join(x for x in (label.group(1) if label else None, leaf) if x)
        out.append(
            _card(
                "p30download",
                raw,
                link,
                category=cat or None,
                date=_iso(f["pubdate"].text) if "pubdate" in f else None,
                summary=_plain(f["description"].text) if "description" in f else None,
            )
        )
    return out


def parse_p30_list(data: bytes) -> list[dict[str, Any]]:
    out = []
    for art in parse_html(data).all("article"):
        a = next((x for h in art.all("h2") for x in h.all("a") if "/entry/" in x.attrs.get("href", "")), None)
        if a is None:
            continue
        crumbs, tm, size, body = art.first("li", "breadcrumbs"), art.first("time"), art.first("li", "size"), None
        body = art.first("div", "post-summary")
        out.append(
            _card(
                "p30download",
                a.attrs.get("title") or a.text(),
                a.attrs["href"],
                category=" / ".join(x.text() for x in crumbs.all("a")) if crumbs else None,
                date=_iso(tm.attrs.get("datetime")) if tm else None,
                size=size.text() if size else None,
                summary=body.text() if body else None,
            )
        )
    return out


def _labelled(p: Node) -> dict[str, str]:
    """`<strong>Label:</strong> value <br>` runs to {label: value}."""
    out: dict[str, str] = {}
    label, parts = None, []
    for k in [*p.kids, Node("br")]:
        if isinstance(k, Node) and k.tag == "strong":
            label, parts = k.text().rstrip(":： ").strip(), []
        elif isinstance(k, Node) and k.tag == "br":
            if label:
                out[label] = _WS.sub(" ", " ".join(parts)).strip()
            label, parts = None, []
        elif label:
            parts.append(k if isinstance(k, str) else k.text())
    return out


def parse_p30_item(data: bytes, url: str) -> dict[str, Any]:
    root = parse_html(data)
    title = _meta(root, "og:title")
    if not title:
        raise http.ApiError("p30download.ir page has no item on it (wrong url or changed layout).")
    info: dict[str, str] = {}
    for p in (root.first("div", "extra-info") or Node()).all("p"):
        info.update(_labelled(p))
    crumbs = root.first("li", "breadcrumbs")
    req = root.first("div", "system-requirements")
    date = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", info.get("تاریخ انتشار", ""))
    return _detail(
        "p30download",
        url,
        title,
        version=info.get("شماره نسخه"),
        maker=info.get("شرکت سازنده"),
        size=info.get("حجم فایل"),
        category=" / ".join(x.text() for x in crumbs.all("a")) if crumbs else None,
        date=f"{date.group(1)}-{int(date.group(2)):02d}-{int(date.group(3)):02d}"
        if date
        else _iso(_meta(root, "og:updated_time")),
        description=_meta(root, "og:description"),
        requirements=req.lines()[1:] if req else None,  # first line is the heading
    )


def parse_downloadly_list(data: bytes) -> list[dict[str, Any]]:
    out, seen = [], set()
    for art in parse_html(data).all("article", "w-grid-item"):
        h = art.first("h2", "post_title")
        a = h.first("a") if h else None
        if a is None or a.attrs.get("href", "") in seen:
            continue
        seen.add(a.attrs["href"])
        tm, tax, body = art.first("time"), art.first("div", "post_taxonomy"), art.first("div", "post_content")
        out.append(
            _card(
                "downloadly",
                a.text(),
                a.attrs["href"],
                category=" / ".join(x.text() for x in tax.all("a")) if tax else None,
                date=_iso(tm.attrs.get("datetime")) if tm else None,
                summary=body.text() if body else None,
            )
        )
    return out


def parse_downloadly_item(data: bytes, url: str) -> dict[str, Any]:
    root = parse_html(data)
    h1 = root.first("h1", "post_title")
    if h1 is None:
        raise http.ApiError("downloadly.ir page has no item on it (wrong url or changed layout).")
    sections: dict[str, list[str]] = {}
    for box in root.all():
        heads = [k for k in box.kids if isinstance(k, Node) and k.tag in ("h2", "h3", "h4", "h5")]
        if not heads:
            continue
        cur = None
        for k in box.kids:
            if isinstance(k, Node) and k.tag in ("h2", "h3", "h4", "h5"):
                cur = sections.setdefault(k.text(), [])
            elif cur is not None and isinstance(k, Node):
                cur += k.lines()
    tm, tax = root.first("time", "post_date"), root.first("div", "post_taxonomy")
    return _detail(
        "downloadly",
        url,
        h1.text(),
        size=" | ".join(x for x in sections.get("حجم فایل", []) if _SIZE.search(x)) or None,  # skips the rating line
        category=" / ".join(x.text() for x in tax.all("a")) if tax else None,
        date=_iso(tm.attrs.get("datetime")) if tm else _iso(_meta(root, "article:published_time")),
        description=" ".join(sections.get("توضیحات", [])[:3]) or _meta(root, "og:description"),
        requirements=sections.get("سیستم مورد نیاز"),
    )


def parse_vgdl_posts(data: bytes) -> list[dict[str, Any]]:
    try:
        posts = json.loads(data)
    except ValueError as e:
        raise http.ApiError("vgdl.ir returned JSON that could not be parsed.") from e
    return [
        _card(
            "vgdl",
            p["title"]["rendered"],
            p["link"],
            date=_iso(p.get("date_gmt")),
            summary=_plain(p.get("excerpt", {}).get("rendered")),
        )
        for p in posts
        if isinstance(p, dict) and p.get("link") and p.get("title")
    ]


def _detail(source: str, url: str, title: str, requirements: list[str] | None = None, **f: Any) -> dict[str, Any]:
    title = _clean_title(html.unescape(title))
    req = " | ".join(x for x in (requirements or []) if not _RISKY.search(x))
    f["version"] = f.get("version") or _version(title)
    f["description"] = clip(_safe(f.get("description")), n=DESC_LEN)
    f["requirements"] = clip(req, n=DESC_LEN)
    return {"source": source, "url": url, "title": title, **{k: v for k, v in f.items() if v}}


# ---------------------------------------------------------------- fetching per source

_FIELDS = "id,date_gmt,link,title,excerpt"


async def _search(source: str, query: str, page: int) -> list[dict[str, Any]]:
    q = quote(query, safe="")
    if source == "soft98":
        url = f"https://soft98.ir/?do=search&subaction=search&story={q}"
        if page > 1:
            url += f"&search_start={page}&result_from={(page - 1) * 8 + 1}"
        return parse_soft98_list(await http.fetch(url))
    if source == "p30download":
        url = f"https://p30download.ir/search/{q}" + (f"/page/{page}" if page > 1 else "")
        return parse_p30_list(await http.fetch(url))
    if source == "downloadly":
        url = f"https://downloadly.ir/{f'page/{page}/' if page > 1 else ''}?s={quote_plus(query)}"
        return parse_downloadly_list(await http.fetch(url))
    url = f"https://vgdl.ir/wp-json/wp/v2/posts?search={q}&per_page={PER_SOURCE_MAX}&page={page}&_fields={_FIELDS}"
    try:
        return parse_vgdl_posts(await http.fetch(url, "json"))
    except http.ApiError as e:
        if e.status == 400:  # WordPress answers 400 for a page past the last one
            return []
        raise


async def _latest(source: str, category: str) -> list[dict[str, Any]]:
    path = SOURCES[source]["cats"][category][0] if category else ""
    if source == "p30download":
        return parse_p30_feed(await http.fetch(f"https://p30download.ir/fa/{path or 'main'}/feed/rss.xml", "xml"))
    if source == "downloadly":
        return parse_downloadly_list(await http.fetch(f"https://downloadly.ir/{path + '/' if path else ''}"))
    cat = f"&categories={path}" if path else ""
    url = f"https://vgdl.ir/wp-json/wp/v2/posts?per_page={PER_SOURCE_MAX * 2}{cat}&_fields={_FIELDS}"
    return parse_vgdl_posts(await http.fetch(url, "json"))


async def _item(source: str, url: str) -> dict[str, Any]:
    if source == "vgdl":
        slug = urlsplit(url).path.strip("/")
        if not slug or "/" in slug:
            raise http.ApiError(
                "vgdl.ir item urls look like https://vgdl.ir/<slug>/ (take the url from a search result)."
            )
        api = "https://vgdl.ir/wp-json/wp/v2"
        posts = json.loads(
            await http.fetch(
                f"{api}/posts?slug={quote(slug, safe='')}&_fields=id,date_gmt,link,title,excerpt,categories", "json"
            )
        )
        if not posts:
            raise http.ApiError("Item not found on vgdl.ir; the post may have been removed or the url is wrong.", 404)
        p = posts[0]
        ids = ",".join(str(i) for i in p.get("categories", [])[:20])
        names = []
        if ids:
            cats = json.loads(await http.fetch(f"{api}/categories?include={ids}&per_page=20&_fields=name", "json"))
            names = [html.unescape(c["name"]) for c in cats]
        return _detail(
            "vgdl",
            p["link"],
            p["title"]["rendered"],
            category=" / ".join(names) or None,
            date=_iso(p.get("date_gmt")),
            description=_plain(p.get("excerpt", {}).get("rendered")),
        )
    data = await http.fetch(url)
    return {"soft98": parse_soft98_item, "p30download": parse_p30_item, "downloadly": parse_downloadly_item}[source](
        data, url
    )


def _ids(sources: list[str], need_latest: bool = False) -> list[str]:
    ids = list(dict.fromkeys(sources))
    for s in ids:
        if s not in SOURCES:
            raise http.ApiError(f"Unknown source '{s}'. Use one of: {', '.join(SOURCES)}.")
    return ids or [s for s, v in SOURCES.items() if v["latest"] or not need_latest]


async def _many(jobs: dict[str, Any], per_source: int) -> dict[str, Any]:
    results = await asyncio.gather(*jobs.values(), return_exceptions=True)
    items, errors = [], {}
    for s, r in zip(jobs, results, strict=True):
        if isinstance(r, Exception):
            errors[s] = str(r)[:200]
        else:
            items += r[:per_source]
    return {"items": items, "errors": errors}


# ---------------------------------------------------------------- tools


@tool("List download sources")
async def dl_list_sources() -> dict:
    """List the four download-site sources and their latest-listing categories; call this first for valid ids.

    Sources: soft98, p30download, downloadly, vgdl. This server returns metadata and the item page url only,
    never file links. Next: dl_search, dl_latest or dl_item.
    """
    return {
        "sources": [
            {
                "id": k,
                "name": v["name"],
                "site": f"https://{v['host']}/",
                "latest": v["latest"],
                "categories": {slug: title for slug, (_, title) in v["cats"].items()},
            }
            for k, v in SOURCES.items()
        ]
    }


@tool("Search download sites")
async def dl_search(
    query: Annotated[
        str,
        Field(
            min_length=2,
            max_length=80,
            description="Software or game name; Latin names work best on every site.",
            examples=["google chrome"],
        ),
    ],
    sources: Sources = [],  # noqa: B006
    page: Annotated[int, Field(ge=1, le=20, description="Result page (1-20) of each source.", examples=[1])] = 1,
    per_source: Annotated[
        int,
        Field(ge=1, le=PER_SOURCE_MAX, description=f"Items (1-{PER_SOURCE_MAX}) taken from each source.", examples=[3]),
    ] = 3,
) -> dict:
    """Search the download sites by name and return metadata (title, item page url, category, date, short summary).

    Results keep each site's own relevance order, grouped by source. Open the item page url yourself to download;
    this server never returns file links. A failing source is listed under `errors`.
    """
    jobs = {s: _search(s, query, page) for s in _ids(sources)}
    return {"query": query, "page": page, **await _many(jobs, per_source)}


@tool("Latest downloads")
async def dl_latest(
    sources: Sources = [],  # noqa: B006
    category: Annotated[
        str,
        Field(
            description="Category slug from dl_list_sources, e.g. 'software' or 'game'. Empty = everything.",
            examples=["game"],
        ),
    ] = "",
    per_source: Annotated[
        int,
        Field(ge=1, le=PER_SOURCE_MAX, description=f"Items (1-{PER_SOURCE_MAX}) taken from each source.", examples=[3]),
    ] = 3,
) -> dict:
    """Return the newest uploads of the download sites (soft98 has no latest listing), merged and sorted by date.

    Metadata and item page urls only. Sources that failed or lack the category are listed under `errors`.
    """
    ids = _ids(sources, need_latest=not sources)
    errors = {s: "no latest listing; use dl_search" for s in ids if not SOURCES[s]["latest"]}
    errors |= {
        s: f"no category '{category}'"
        for s in ids
        if SOURCES[s]["latest"] and category and category not in SOURCES[s]["cats"]
    }
    jobs = {s: _latest(s, category) for s in ids if s not in errors}
    out = await _many(jobs, per_source)
    out["items"].sort(key=lambda i: i.get("date") or "", reverse=True)
    return {"category": category or None, "items": out["items"], "errors": errors | out["errors"]}


@tool("Download item details")
async def dl_item(
    url: Annotated[
        str,
        Field(
            description="Item page url from dl_search or dl_latest (soft98.ir, p30download.ir, downloadly.ir or vgdl.ir).",
            examples=["https://p30download.ir/fa/entry/101588/google-chrome"],
        ),
    ],
) -> dict:
    """Return the details of one download item: name, version, size, category, date, description and system requirements.

    Fields a site does not publish are omitted (soft98 has no size; vgdl has neither size nor requirements). Never
    includes download links, passwords or crack notes: open the item page url yourself and check the licence.
    """
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    source = next((s for s, v in SOURCES.items() if v["host"] == host), None)
    if source is None:
        raise http.ApiError(
            f"Unsupported site '{host or url[:60]}'. Supported: {', '.join(v['host'] for v in SOURCES.values())}."
        )
    return await _item(source, url)
