from __future__ import annotations

import json
import re
from html import unescape

import requests

# YC Library "The Latest" carousel.
#
# YC ships no public JSON/RSS feed, so we fetch the carousel page and recover
# the item list from the server-rendered HTML. Items are content pages whose
# URL looks like /library/<slug> (slug e.g. "NH-the-new-way-to-build-a-startup").
#
# Extraction strategy, in order:
#   1. Pair "title" + "slug" out of the embedded JSON hydration payload
#      (works for both Next.js __NEXT_DATA__ and app-router RSC chunks, since
#      both end up as JSON text inside the HTML).
#   2. Fall back to scraping <a href="/library/..."> anchors.
# On zero results it prints a compact diagnostic of what the page actually
# contained, then returns []. Fails soft so one bad source never breaks the
# whole sync run.

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

# Path segments under /library/ that are routes, not content items.
EXCLUDE_SLUGS = {"carousel", "search"}


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _decode(raw: str) -> str:
    # Decode JSON string escapes (e.g. \u0026, \") without trusting the source.
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


def _add(items: list, seen: set, title: str, slug: str) -> None:
    title = _decode(title).strip()
    url = _slug_to_url(_decode(slug))
    if not title or not url or url in seen:
        return
    seen.add(url)
    items.append(
        {"title": title, "url": url, "summary": "", "published_date": ""}
    )


def _from_embedded_json(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    # title-then-slug and slug-then-title, kept within one JSON object by
    # forbidding braces between the two keys.
    for m in re.finditer(
        r'"title"\s*:\s*"([^"]+)"[^{}]{0,300}?"slug"\s*:\s*"([^"]+)"', html
    ):
        _add(items, seen, m.group(1), m.group(2))
    for m in re.finditer(
        r'"slug"\s*:\s*"([^"]+)"[^{}]{0,300}?"title"\s*:\s*"([^"]+)"', html
    ):
        _add(items, seen, m.group(2), m.group(1))
    return items


def _from_anchors(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in re.finditer(
        r'<a[^>]+href="(/library/[^"#?]+)"[^>]*>(.*?)</a>', html, re.DOTALL
    ):
        href, inner = m.group(1), m.group(2)
        title = _strip_html(inner)
        url = _slug_to_url(href)
        if title and url and url not in seen:
            seen.add(url)
            items.append(
                {"title": title, "url": url, "summary": "", "published_date": ""}
            )
    return items


def _print_diagnostics(resp: requests.Response, html: str) -> None:
    idx = html.find("/library/")
    sample = html[max(0, idx - 150): idx + 250] if idx != -1 else ""
    title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    print("YC DEBUG status=", resp.status_code, "final=", resp.url, "len=", len(html))
    print(
        "YC DEBUG __NEXT_DATA__=", "__NEXT_DATA__" in html,
        "__next_f=", "__next_f" in html,
    )
    print(
        'YC DEBUG href=/library count=', html.count('href="/library'),
        "/library/ count=", html.count("/library/"),
    )
    print("YC DEBUG <title>=", title_match.group(1).strip() if title_match else None)
    print("YC DEBUG sample=", repr(sample))


def fetch_yc_library_articles() -> list[dict[str, str]]:
    resp = requests.get(CAROUSEL_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    items = _from_embedded_json(html)
    if not items:
        items = _from_anchors(html)
    if not items:
        _print_diagnostics(resp, html)

    return items[:MAX_ITEMS]


if __name__ == "__main__":
    for article in fetch_yc_library_articles():
        print(article)
