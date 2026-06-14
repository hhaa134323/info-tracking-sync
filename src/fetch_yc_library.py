from __future__ import annotations

import json
import re
from html import unescape

import requests

# YC Library "The Latest" carousel.
#
# The carousel page embeds its data as HTML-entity-escaped JSON (e.g.
# &quot;slug&quot;:&quot;...&quot;). After unescaping, each content item looks
# like {"id":..,"slug":"P3-...","title":"...","content":"...", ...} and the
# public URL is /library/<slug>.
#
# NOTE: this commit is a DRY RUN. It parses and prints what it finds, but
# returns [] so nothing is written to Notion until scoping + date are confirmed.

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

# key:value with one-or-more colons (the page renders the separator as '::').
SLUG_TITLE_RE = re.compile(
    r'"slug"\s*:+\s*"([^"]+)"\s*,\s*"title"\s*:+\s*"((?:\\.|[^"\\])*)"'
)
CONTENT_RE = re.compile(r'\s*,\s*"content"\s*:+\s*"((?:\\.|[^"\\])*)"')


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
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for idx, m in enumerate(SLUG_TITLE_RE.finditer(text)):
        url = _slug_to_url(m.group(1))
        if not url or url in seen:
            continue
        title = _decode(m.group(2)).strip()
        if not title:
            continue
        seen.add(url)

        window = text[m.end(): m.end() + 8000]
        summary = ""
        cm = CONTENT_RE.match(window)
        if cm:
            summary = _decode(cm.group(1)).strip()
            if idx == 0:
                # reveal fields after 'content' (looking for a date field name)
                tail = window[cm.end(): cm.end() + 700]
                print("YC DEBUG after-content[0]=", repr(tail))

        items.append(
            {"title": title, "url": url, "summary": summary, "published_date": ""}
        )
    return items


def fetch_yc_library_articles() -> list[dict[str, str]]:
    resp = requests.get(CAROUSEL_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    text = unescape(resp.text)

    items = _parse_items(text)

    # DRY-RUN diagnostics: print matched items in document order.
    print(f"YC DEBUG matched {len(items)} items (document order):")
    for n, it in enumerate(items[:40]):
        print(f"YC DEBUG {n:02d}. {it['title']}  -> {it['url']}")

    # Intentionally write nothing yet.
    return []


if __name__ == "__main__":
    for article in fetch_yc_library_articles():
        print(article)
