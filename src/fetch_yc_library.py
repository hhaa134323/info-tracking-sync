from __future__ import annotations

import json
import re
from html import unescape

import requests

# YC Library "The Latest" carousel.
#
# YC exposes no public JSON/RSS feed for the library, so we fetch the carousel
# page and recover the structured item list that the site ships inside the
# page HTML. Strategy, in order:
#   1. Parse the __NEXT_DATA__ hydration payload (Next.js pages router) and walk
#      it for objects that look like a library content item.
#   2. Fall back to scraping <a href="/library/..."> anchors from the HTML.
# Each item links to a /library/<slug> content page.
#
# The fetcher is intentionally defensive: if the page layout changes it returns
# whatever it can (possibly nothing) instead of raising, matching how the other
# fetchers fail soft in sync.py.

CAROUSEL_URL = "https://www.ycombinator.com/library/carousel/The%20Latest"
BASE_URL = "https://www.ycombinator.com"
MAX_ITEMS = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; info-tracking-sync/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}

TITLE_KEYS = ("title", "name", "heading")
URL_KEYS = ("url", "href", "path")
SUMMARY_KEYS = ("description", "excerpt", "subtitle", "summary", "previewText")
DATE_KEYS = (
    "publishedAt",
    "published_at",
    "publishDate",
    "date",
    "createdAt",
    "created_at",
)


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _abs_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{BASE_URL}{href}"
    return f"{BASE_URL}/{href}"


def _parse_date(raw: str) -> str:
    if not raw:
        return ""
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(raw))
    return match.group(0) if match else ""


def _iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_dicts(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_dicts(value)


def _to_item(obj: dict) -> dict | None:
    if not isinstance(obj, dict):
        return None

    title = next(
        (obj[k] for k in TITLE_KEYS if isinstance(obj.get(k), str) and obj[k].strip()),
        None,
    )
    if not title:
        return None

    raw_url = next(
        (obj[k] for k in URL_KEYS if isinstance(obj.get(k), str) and obj[k].strip()),
        None,
    )
    slug = obj.get("slug")
    if raw_url:
        url = _abs_url(str(raw_url))
    elif isinstance(slug, str) and slug.strip():
        url = f"{BASE_URL}/library/{slug.strip()}"
    else:
        return None

    # Keep only individual library content pages, not the carousel links
    # themselves or unrelated navigation entries.
    if "/library/" not in url or "/library/carousel/" in url:
        return None

    summary = next(
        (
            _strip_html(obj[k])
            for k in SUMMARY_KEYS
            if isinstance(obj.get(k), str) and obj[k].strip()
        ),
        "",
    )
    published_date = ""
    for key in DATE_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            published_date = _parse_date(value)
            if published_date:
                break

    return {
        "title": title.strip(),
        "url": url,
        "summary": summary,
        "published_date": published_date,
    }


def _from_next_data(html: str) -> list[dict[str, str]]:
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    items: list[dict[str, str]] = []
    for obj in _iter_dicts(data):
        item = _to_item(obj)
        if item:
            items.append(item)
    return items


def _from_anchors(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a[^>]+href="(/library/[^"#?]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        href, inner = match.group(1), match.group(2)
        if "/library/carousel/" in href:
            continue
        title = _strip_html(inner)
        if not title:
            continue
        items.append(
            {
                "title": title,
                "url": _abs_url(href),
                "summary": "",
                "published_date": "",
            }
        )
    return items


def fetch_yc_library_articles() -> list[dict[str, str]]:
    response = requests.get(CAROUSEL_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text

    items = _from_next_data(html)
    if not items:
        items = _from_anchors(html)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        url = item["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)
        if len(deduped) >= MAX_ITEMS:
            break

    return deduped


if __name__ == "__main__":
    for article in fetch_yc_library_articles():
        print(article)
