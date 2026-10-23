<!-- mcp-name: io.github.sepehr071/iran-downloads-mcp -->

# iran-downloads-mcp: Iranian software and game download sites MCP server for AI agents

**Let your AI agent look up software and games (دانلود نرم&zwnj;افزار و بازی) on Soft98, P30Download, Downloadly and VGDL.**<br>
An unofficial, read-only MCP server that searches the public pages of [Soft98](https://soft98.ir), [P30Download](https://p30download.ir), [Downloadly](https://downloadly.ir) and [VGDL](https://vgdl.ir) and returns **metadata only**: name, version, size, category, date, a short description, system requirements and the link to the item page.

[![PyPI](https://img.shields.io/pypi/v/iran-downloads-mcp?color=2563eb)](https://pypi.org/project/iran-downloads-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/iran-downloads-mcp)](https://pypi.org/project/iran-downloads-mcp/)
[![CI](https://github.com/sepehr071/iran-downloads-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sepehr071/iran-downloads-mcp/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-io.github.sepehr071%2Firan--downloads--mcp-7c3aed)](https://registry.modelcontextprotocol.io/?q=iran-downloads-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/iran-downloads-mcp/blob/main/LICENSE)

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_iran--downloads--mcp-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=iran-downloads&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22iran-downloads-mcp%22%5D%7D)

> **Metadata search only.** This server never downloads or saves files, never returns file links, and does not resolve or bypass gated or tokenised download links. It returns no passwords and no crack or activation notes. Many listings on these sites are cracked, repacked or otherwise redistributed software. You are responsible for checking the licence of whatever you install and for following the law where you live.

[For AI agents](#for-ai-agents) · [Why](#why) · [What it can do](#what-it-can-do) · [Quick start](#quick-start) · [Tools](#tools) · [Sources](#sources) · [How it works](#how-it-works) · [Good to know](#good-to-know) · [FAQ](#faq) · [Configuration](#configuration) · [فارسی](#فارسی) · [Development](#development) · [Related servers](#related-servers)

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for metadata search on Soft98 (soft98.ir), P30Download (p30download.ir), Downloadly (downloadly.ir) and VGDL (vgdl.ir). Persian and English text.
- **Install:** `uvx iran-downloads-mcp` or `claude mcp add iran-downloads -- uvx iran-downloads-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `IRAN_DOWNLOADS_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. No login, no downloads, so no confirmation is needed before calling any tool.
- **Tools:** 4, all prefixed `dl_`: `dl_list_sources`, `dl_search`, `dl_latest`, `dl_item`. Typical sequence: `dl_list_sources` (source ids and category slugs) -> `dl_search` or `dl_latest` -> `dl_item` with a result `url`.
- **Use when:** the user wants to find an app or game by name, see what is new, or check version, size and system requirements before opening the item page.
- **Do not use when:** the user wants the file itself, a direct link, a password, or a crack. None of that is returned; send them to the item page `url` and remind them to check the licence.
- **Output:** compact JSON. Dates are ISO (UTC where a time is shown); Soft98's Jalali dates are converted. Summaries are cut to 120 characters, descriptions to 600. Null and empty fields are omitted. Replies stay under ~15 KB (`per_source` max 5). A failing source is listed under `errors` while the others still answer. Pages are cached for 3 minutes.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/iran-downloads-mcp/blob/main/server.json) and the
  [iran-mcp catalog](https://github.com/sepehr071/iran-mcp).

## Why

Iranian download sites are the first stop for many people looking for an app, a game or a Persian-language mirror, but each one has its own layout, search and category tree. Asking "what is the latest version of Google Chrome, and how big is it?" or "which games were uploaded today?" means opening several sites. With `iran-downloads-mcp` an agent runs one search across all four sources and gets short, comparable records instead of full web pages.

> **You:** Is there a new version of VLC, and what does it need to run?
>
> **Agent:** *calls* `dl_search(query="VLC")` -> `dl_item(url=...)`
>
> It lists the matching entries per site with their versions, then reads one item page for size and system requirements, and points you to the page for the actual download.

Every reply is trimmed to stay under about 15 KB, so it does not flood the agent's context.

## What it can do

- **Search by name** across Soft98, P30Download, Downloadly and VGDL in one call, with up to 5 results per source
- **See the newest uploads** merged by date, optionally limited to sources and a category (Soft98 has no latest listing)
- **Read item details**: name, version, size, category, date, description and system requirements, where the site publishes them
- **List sources** with their ids, whether they have a latest listing, and category slugs
- **Read-only by design**: no downloads, no file links, no passwords, no crack notes

Example prompts:

- "Search for Google Chrome on the Iranian download sites and compare versions."
- "What was uploaded to P30Download and Downloadly today?"
- "What are the system requirements of Adobe Photoshop on Downloadly?"
- "Newest PC games on VGDL."
- <span dir="rtl">آخرین نسخه نرم&zwnj;افزار ویندوز ۱۱ یا فتوشاپ در سافت۹۸ چیست؟</span>
- <span dir="rtl">جدیدترین بازی&zwnj;های اضافه&zwnj;شده به پی&zwnj;سی دانلود را نشان بده.</span>
- <span dir="rtl">حجم و سیستم مورد نیاز این برنامه در دانلودلی چقدر است؟</span>

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add iran-downloads -- uvx iran-downloads-mcp
```
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "iran-downloads": { "command": "uvx", "args": ["iran-downloads-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Cursor</b></summary>

Add the Claude Desktop block above to `~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project).
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

Click **Install in VS Code** above, or add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "iran-downloads": { "type": "stdio", "command": "uvx", "args": ["iran-downloads-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex mcp add iran-downloads -- uvx iran-downloads-mcp
```

Or in `~/.codex/config.toml`:

```toml
[mcp_servers.iran-downloads]
command = "uvx"
args = ["iran-downloads-mcp"]
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "iran-downloads": { "command": "uvx", "args": ["iran-downloads-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Windsurf</b></summary>

Add the Claude Desktop block to `~/.codeium/windsurf/mcp_config.json`.
</details>

<details>
<summary><b>Anything else</b></summary>

It is a standard stdio MCP server: run `uvx iran-downloads-mcp`, or `pip install iran-downloads-mcp` and run `iran-downloads-mcp`.
</details>

## Tools

| Tool | What it does |
|---|---|
| `dl_list_sources` | List the four download-site sources and their latest-listing categories; call this first for valid ids |
| `dl_search` | Search the download sites by name and return metadata (title, item page url, category, date, short summary); takes `query`, `sources`, `page`, `per_source` (1-5) |
| `dl_latest` | Return the newest uploads of the download sites, merged and sorted by date; takes `sources`, `category`, `per_source` (1-5). Soft98 has no latest listing |
| `dl_item` | Return the details of one download item from its page `url`: name, version, size, category, date, description and system requirements |

All 4 tools are annotated `readOnlyHint: true`.

## Sources

| id | Site | Search | Latest | Item details |
|---|---|---|---|---|
| `soft98` | Soft98 | site search (8 per page) | no: listing pages hide item links behind script keys | title, version, category, date, description, requirements; no size |
| `p30download` | P30Download | `/search/<query>` (10 per page) | RSS per section: software, game, tutorial, graphic, console | adds size, publisher, release date |
| `downloadly` | Downloadly | `/?s=` (25 per page) | home or category archive: software, mobile, multimedia, video-tutorials | adds size and requirements |
| `vgdl` | VGDL | WordPress REST `/wp-json/wp/v2/posts?search=` | REST posts, optional category: game, software, mobile | title, category, date, excerpt only (size and requirements sit next to crack and repack notes, so they are not read) |

Titles carry the version where the site puts it there (for example `Google Chrome 155.0.8059.85`); `dl_item` returns a best-effort `version`.

## How it works

```text
  AI agent  (Claude, Cursor, Copilot, ...)
      │
      │  MCP over stdio
      ▼
  iran-downloads-mcp  (runs on your machine)
      │
      │  HTTPS, GET only
      ├──────▶  soft98.ir
      ├──────▶  p30download.ir
      ├──────▶  downloadly.ir
      └──────▶  vgdl.ir
```

`iran-downloads-mcp` runs locally and reads the public pages, RSS feeds and WordPress REST posts of the four sites. There is no hosted server in between and no API key. Requests go out through a Chrome-impersonating client, at most 4 at a time with a little jitter; answers are cached for 3 minutes, failed GETs are retried, and only these four hosts over HTTPS are allowed. It does not read or decode the download lists or the keys that hide links on the sites.

## Good to know

- **Metadata only.** No file downloads, no file or mirror links, no passwords, no crack or activation notes. Sentences mentioning those are dropped from summaries, descriptions and requirements.
- **Soft98 supports search only**, and its item pages have no file size. `dl_latest` skips it.
- **VGDL** returns title, category, date and excerpt only. Its listings are repacks, so the licence caveat applies in full.
- **Dates:** Soft98's Jalali dates are converted to Gregorian ISO dates; times, where shown, are UTC.
- **Versions** are parsed from the title when the page has no version field, so treat them as best effort.
- **Reply caps:** at most 5 results per source per call (`per_source`), summaries 120 characters, descriptions 600, about 15 KB per reply.
- **Partial failures:** a source that fails (blocked, down, bot-check page) appears under `errors` and the others still answer.
- **Network:** in testing the four sites answered direct connections from Iran. Through a Turkish proxy exit Soft98, P30Download and Downloadly answered, while VGDL returned a bot-check page instead of JSON. Prefer a direct connection, or set `IRAN_DOWNLOADS_MCP_PROXY` with an Iranian exit. System proxy variables are ignored on purpose.
- **Latin names work best** for search.
- **What it does not do:** no downloading, no link resolving, no licence checks, no other download sites.

## FAQ

<details>
<summary><b>Is there an MCP server for Soft98, P30Download or Downloadly?</b></summary>

None of these sites documents a public API. `iran-downloads-mcp` is an unofficial MCP server with 4 read-only tools that reads their public pages, feeds and (for VGDL) WordPress REST posts and returns compact JSON for AI agents.
</details>

<details>
<summary><b>Can it download a file or give me a direct link?</b></summary>

No, on purpose. The sites gate links behind tokens, countdowns and ads, and many files are cracked or repacked copies. The server stays a search index; each result carries the item page `url`.
</details>

<details>
<summary><b>Does it work outside Iran?</b></summary>

It depends on the site and your exit. From a Turkish proxy exit Soft98, P30Download and Downloadly answered in testing, but VGDL returned a bot-check page (the tool reports it). If a site blocks you, try a direct connection or `IRAN_DOWNLOADS_MCP_PROXY` with an Iranian exit.
</details>

<details>
<summary><b>Why does dl_latest have no Soft98 results?</b></summary>

Soft98's listing pages hide item links behind script keys, which this server does not decode. Soft98 is available through `dl_search` and `dl_item`.
</details>

<details>
<summary><b>Why is the file size missing for some items?</b></summary>

Soft98 shows no size outside its download data, and VGDL pages mix sizes with crack and install notes, so those are not read. P30Download and Downloadly items include size when the page has it.
</details>

<details>
<summary><b>Are the listed programs legal and safe?</b></summary>

The server cannot tell. Many listings on these sites are cracked, repacked or redistributed. Check each programme's licence and follow the law where you live.
</details>

<details>
<summary><b>How do I use it with Claude, Cursor or Copilot?</b></summary>

Add the server with `claude mcp add iran-downloads -- uvx iran-downloads-mcp`, or use the matching config in [Quick start](#quick-start), then ask in plain language, in Persian or English.
</details>

<details>
<summary><b>How do I debug what the agent sees?</b></summary>

```bash
npx @modelcontextprotocol/inspector uvx iran-downloads-mcp
```
</details>

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `IRAN_DOWNLOADS_MCP_PROXY` | unset | Optional HTTP proxy URL. System proxy settings are ignored. A comma-separated list is used one at a time: the next proxy takes over when one is blocked or cannot connect |

<a id="فارسی"></a>

## فارسی: سرور MCP سایت&zwnj;های دانلود نرم&zwnj;افزار و بازی

<div dir="rtl">

**iran-downloads-mcp** یک سرور MCP غیررسمی و فقط&zwnj;خواندنی برای جست&zwnj;وجوی **فراداده** (نام، نسخه، حجم، دسته، تاریخ، توضیح کوتاه، سیستم مورد نیاز و پیوند صفحهٔ آیتم) در سافت۹۸ (Soft98)، پی&zwnj;سی دانلود (P30Download)، دانلودلی (Downloadly) و ویجی دی ال (VGDL) است. به دستیار هوش مصنوعی شما (Claude، Cursor، Copilot و ...) کمک می&zwnj;کند آخرین نسخه و مشخصات یک برنامه یا بازی را پیدا کند.

**چه کارهایی می&zwnj;کند**

- **جست&zwnj;وجوی نام** نرم&zwnj;افزار یا بازی در چهار سایت با یک درخواست (نام لاتین بهتر جواب می&zwnj;دهد).
- **جدیدترین آپلودها** در پی&zwnj;سی دانلود، دانلودلی و ویجی دی ال (سافت۹۸ فهرست جدیدترین&zwnj;ها ندارد).
- **جزئیات آیتم**: نسخه، حجم، دسته، تاریخ، توضیحات و سیستم مورد نیاز، تا جایی که سایت منتشر کرده باشد.

**نکته&zwnj;ها**

- فقط فراداده برمی&zwnj;گرداند: فایلی دانلود یا ذخیره نمی&zwnj;کند، پیوند فایل، گذرواژه یا کرک برنمی&zwnj;گرداند و پیوندهای قفل&zwnj;شده را دور نمی&zwnj;زند.
- بسیاری از آیتم&zwnj;های این سایت&zwnj;ها کرک&zwnj;شده یا ریپک هستند؛ بررسی مجوز نرم&zwnj;افزارها و رعایت قانون با خود شماست.
- تاریخ&zwnj;های شمسی سافت۹۸ به میلادی تبدیل می&zwnj;شوند.
- ویجی دی ال فقط عنوان، دسته، تاریخ و خلاصه می&zwnj;دهد.
- اگر سایتی پاسخ نداد، همان سایت در بخش `errors` می&zwnj;آید و بقیه جواب می&zwnj;دهند. در صورت نیاز متغیر `IRAN_DOWNLOADS_MCP_PROXY` را روی یک پراکسی HTTP با خروجی ایران بگذارید.
- کلید API لازم نیست و روی سیستم خود شما اجرا می&zwnj;شود.

**نصب** (اول [uv](https://docs.astral.sh/uv/getting-started/installation/) را نصب کنید). در Claude Code:

</div>

```bash
claude mcp add iran-downloads -- uvx iran-downloads-mcp
```

<div dir="rtl">

در Claude Desktop، Cursor و بقیه برنامه&zwnj;ها همان تنظیم بخش [Quick start](#quick-start) را بگذارید.

**نمونه پرسش&zwnj;ها**

- «آخرین نسخه گوگل کروم را در سایت&zwnj;های دانلود ایرانی پیدا کن.»
- «امروز چه بازی&zwnj;هایی در ویجی دی ال اضافه شده؟»
- «سیستم مورد نیاز فتوشاپ در دانلودلی چیست؟»

</div>

## Development

```bash
git clone https://github.com/sepehr071/iran-downloads-mcp && cd iran-downloads-mcp
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q          # offline unit tests
uv run python -m pytest -m live -q  # calls the real sites
uv build
```

All tools live in `src/iran_downloads_mcp/downloads.py`; each is a typed async function with a docstring that tells the agent when to use it. Issues and PRs are welcome.

Releases: bump the version in `pyproject.toml` and `server.json`, then push a `v*` tag. GitHub Actions publishes to PyPI.

## Related servers

- [iran-mcp](https://github.com/sepehr071/iran-mcp): catalog of all Iranian-service MCP servers
- [iran-apps-mcp](https://github.com/sepehr071/iran-apps-mcp) for Iranian app stores
- [iran-news-mcp](https://github.com/sepehr071/iran-news-mcp) for Iranian news
- [torob-mcp](https://github.com/sepehr071/torob-mcp) for price comparison on Torob
- [digikala-mcp](https://github.com/sepehr071/digikala-mcp) for products on Digikala

## Disclaimer

Unofficial and not affiliated with or endorsed by Soft98, P30Download, Downloadly or VGDL. It is read-only, returns metadata and item page links only, and uses public pages that can change without notice. Many listings on these sites are cracked or repacked software: check licences yourself.

## Author

<a href="https://www.linkedin.com/in/sepehr-radmard"><img src="https://raw.githubusercontent.com/sepehr071/iran-mcp/main/assets/author-banner.png" alt="Sepehr Radmard: open-source MCP servers for the Iranian web. LinkedIn: linkedin.com/in/sepehr-radmard" width="100%"></a>

Built and maintained by **Sepehr Radmard** (سپهر رادمرد). Connect on [LinkedIn](https://www.linkedin.com/in/sepehr-radmard) or follow [@sepehr071 on GitHub](https://github.com/sepehr071) for more MCP servers for Iranian websites, all listed in [iran-mcp](https://github.com/sepehr071/iran-mcp). If this saves you time, a star on the repo helps other people find it.

## License

[MIT](https://github.com/sepehr071/iran-downloads-mcp/blob/main/LICENSE)
