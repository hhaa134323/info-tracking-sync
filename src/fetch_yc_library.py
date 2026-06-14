from __future__ import annotations

import json
import re
from html import unescape

import requests

# YC Library "The Latest" carousel -> list of recent items.
#
# YC publishes no public JSON/RSS feed. The carousel page embeds its data as
# HTML-entity-escaped JSON (e.g. &quot;slug&quot;:&quot;...&quot;). After
# unescaping, each content item looks like:
#   {"id":1553,"slug":"P3-...","title":"...","content":"...",
#    ...,"description":"...","link":"https://youtube...", ...}
# and the public URL is /library/<slug>.
#
# The embedded blob holds the whole library (~180 items) in newest-first order,
# so "The Latest" == the first N items in document order.

CAROUSEL_URL = "https://www.ycombinator.com/library/carousel/The%20Latest"
BASE_URL = "https://www.ycombinator.com"
MAX_ITEMS = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

EXCLUDE_SLUGS = {"carousel", "search"}

# Page renders the key/value separator as '::', so allow one-or-more colons.
SLUG_TITLE_RE = re.compile(
    r'"slug"\s*:+\s*"([^"]+)"\s*,\s*"title"\s*:+\s*"((?:\\.|[^"\\])*)"'
)
CONTENT_RE = re.compile(r'\s*,\s*"content"\s*:+\s*"((?:\\.|[^"\\])*)"')
DESC_RE = re.compile(r'"description"\s*:+\s*"((?:\\.|[^"\\])*)"')
DATE_RE = re.compile(
    r'"(?:created_at|published_at|posted_at|launched_at|created|published|date)"'
    r'\s*:+\s*"([^"]*?(\d{4}-\d{2}-\d{2})[^"]*)"'
)


def _decode(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except Exception:  # noqa: BLE001
        return raw


def _slug_to_url(slug: str) -> str:
    slug = (slug or "").strip().strip("/")
    if slug.startswith("library/"):
        slug = slug[len("library/"):]
    slug = slug.split("?")[0].split("#")[0].split("/")[0]
    if not slug or slug in EXCLUDE_SLUGS:
        return ""
    return f"{BASE_URL}/library/{slug}"


def _parse_items(text: str) -> list[dict[str, str]]:
    matches = list(SLUG_TITLE_RE.finditer(text))
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for i, m in enumerate(matches):
        url = _slug_to_url(m.group(1))
        if not url or url in seen:
            continue
        title = _decode(m.group(2)).strip()
        if not title:
            continue

        # Bound this item to the start of the next one to avoid field bleed.
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        window = text[m.end(): next_start]

        summary = ""
        cm = CONTENT_RE.match(window)
        if cm:
            summary = _decode(cm.group(1)).strip()
        if not summary:
            dm = DESC_RE.search(window)
            if dm:
                summary = _decode(dm.group(1)).strip()

        published_date = ""
        pm = DATE_RE.search(window)
        if pm:
            published_date = pm.group(2)

        seen.add(url)
        items.append(
            {
                "title": title,
                "url": url,
                "summary": summary,
                "published_date": published_date,
            }
        )
        if len(items) >= MAX_ITEMS:
            break

    return items


def fetch_yc_library_articles() -> list[dict[str, str]]:
    resp = requests.get(CAROUSEL_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    text = unescape(resp.text)

    items = _parse_items(text)
    if not items:
        print("YC DEBUG: no items parsed; status=", resp.status_code, "len=", len(text))
    return items


if __name__ == "__main__":
    for article in fetch_yc_library_articles():
        print(article)
