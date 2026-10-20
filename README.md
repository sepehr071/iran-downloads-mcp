<!-- mcp-name: io.github.sepehr071/iran-downloads-mcp -->

# iran-downloads-mcp: Iranian software and game download sites MCP server for AI agents

**Let your AI agent look up software and games (دانلود نرم‌افزار و بازی) on Soft98, P30Download, Downloadly and VGDL.**<br>
An unofficial, read-only MCP server that searches the sites' public pages and returns **metadata only**: name, version, size, category, date, a short description, system requirements and the link to the item page.

> **Metadata search only.** This server never downloads or saves files, never returns file links, and does not resolve or bypass gated or tokenised download links. It returns no passwords and no crack or activation notes. Many listings on these sites are cracked, repacked or otherwise redistributed software. You are responsible for checking the licence of whatever you install and for following the law where you live.

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [Tools](#tools) · [Sources](#sources) · [فارسی](#فارسی)

---

## For AI agents

- **What:** unofficial MCP server for metadata search on Soft98 (soft98.ir), P30Download (p30download.ir), Downloadly (downloadly.ir) and VGDL (vgdl.ir). Persian and English text.
- **Install:** `uvx iran-downloads-mcp` or `claude mcp add iran-downloads -- uvx iran-downloads-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none. Optional `IRAN_DOWNLOADS_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. No login, no downloads, so no confirmation is needed before calling any tool.
- **Tools:** 4: `dl_list_sources`, `dl_search`, `dl_latest`, `dl_item`. Start with `dl_list_sources` for source ids and category slugs.
- **Use when:** the user wants to find an app or game by name, see what is new, or check version, size and system requirements before opening the item page.
- **Do not use when:** the user wants the file itself, a direct link, a password, or a crack. None of that is returned; send them to the item page `url` and remind them to check the licence.
- **Output:** compact JSON. Dates are ISO (UTC where a time is shown); Soft98's Jalali dates are converted. Summaries are cut to 120 characters, descriptions to 600. Null and empty fields are omitted. Replies stay under ~15 KB (`per_source` max 5). A failing source is listed under `errors` while the others still answer. Pages are cached for 3 minutes.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/iran-downloads-mcp/blob/main/server.json) and the
  [awesome-iran-mcp catalog](https://github.com/sepehr071/awesome-iran-mcp).

## Quick start

```bash
claude mcp add iran-downloads -- uvx iran-downloads-mcp
```

Other clients: command `uvx`, args `["iran-downloads-mcp"]`.

## Tools

| Tool | What it does |
|---|---|
| `dl_list_sources` | The four sources, whether they have a latest listing, and category slugs. |
| `dl_search` | Search by name across sources (`query`, `sources`, `page`, `per_source` 1-5). |
| `dl_latest` | Newest uploads, merged by date (`sources`, `category`, `per_source` 1-5). |
| `dl_item` | Details of one item from its page `url`: name, version, size, category, date, description, requirements. |

## Sources

| id | Site | Search | Latest | Item details |
|---|---|---|---|---|
| `soft98` | Soft98 | site search (8 per page) | no: listing pages hide item links behind script keys | title, version, category, date, description, requirements; no size |
| `p30download` | P30Download | `/search/<query>` (10 per page) | RSS per section: software, game, tutorial, graphic, console | adds size, publisher, release date |
| `downloadly` | Downloadly | `/?s=` (25 per page) | home or category archive: software, mobile, multimedia, video-tutorials | adds size and requirements |
| `vgdl` | VGDL | WordPress REST `/wp-json/wp/v2/posts?search=` | REST posts, optional category: game, software, mobile | title, category, date, excerpt only (size and requirements sit next to crack and repack notes, so they are not read) |

Titles carry the version where the site puts it there (for example `Google Chrome 155.0.8059.85`); `dl_item` returns a best-effort `version`.

## FAQ

**Does it work outside Iran?** The sites answered direct connections from Iran in testing. From a Turkish proxy exit Soft98, P30Download and Downloadly answered, VGDL returned a bot-check page instead of JSON (the tool reports it). If a site blocks you, try a direct connection or `IRAN_DOWNLOADS_MCP_PROXY` with an Iranian exit.

**Why no download links?** Out of scope on purpose: the sites gate links behind tokens, countdowns and ads, and many files are pirated copies. The server stays a search index.

## فارسی

سرور MCP غیررسمی و فقط‌خواندنی برای جست‌وجوی **فراداده** (نام، نسخه، حجم، دسته، تاریخ، توضیح کوتاه، سیستم مورد نیاز و پیوند صفحهٔ آیتم) در سافت۹۸، پی‌سی دانلود، دانلودلی و ویجی دی ال. این سرور فایلی دانلود یا ذخیره نمی‌کند، پیوند فایل، گذرواژه یا کرک برنمی‌گرداند و پیوندهای قفل‌شده را دور نمی‌زند. بررسی مجوز نرم‌افزارها با خود شماست.

```bash
claude mcp add iran-downloads -- uvx iran-downloads-mcp
```

## License

MIT
