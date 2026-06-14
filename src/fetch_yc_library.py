from __future__ import annotations

import json
import re
from html import unescape

import requests

# YC Library "The Latest" carousel.
#
# YC ships no public JSON/RSS feed, so we fetch the carousel page and recover
# the item list from the embedded data in the (very large) server response.
# Extraction strategy, in order:
#   1. Pair "title" + "slug" out of the embedded JSON.
#   2. Fall back to scraping <a href="/library/..."> anchors.
# On zero results it prints a detailed diagnostic of the page so the parser
# can be finished without guessing. Fails soft (returns []).

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


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


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


def _add(items: list, seen: set, title: str, slug: str) -> None:
    title = _decode(title).strip()
    url = _slug_to_url(_decode(slug))
    if not title or not url or url in seen:
        return
    seen.add(url)
    items.append({"title": title, "url": url, "summary": "", "published_date": ""})


def _from_embedded_json(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
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
            items.append({"title": title, "url": url, "summary": "", "published_date": ""})
    return items


def _print_diagnostics(resp: requests.Response, html: str) -> None:
    print("YC DEBUG status=", resp.status_code, "len=", len(html))
    tokens = [
        '"slug"', '"title"', '"name"', '"url"', '"cardTitle"', '"contentType"',
        '"linkTo"', '"href"', '"path"', '"permalink"', '"thumbnail"',
        'href="/library', 'ycombinator.com/library/', 'application/json',
        'window.__APOLLO_STATE__', 'window.__INITIAL', 'id="__gatsby',
        'window.pageData', 'window.___', '__remixContext', 'data-page',
    ]
    print("YC DEBUG counts:", {t: html.count(t) for t in tokens})
    for m in re.finditer(r"<script[^>]*type=\"application/json\"[^>]*>", html):
        print("YC DEBUG json-script:", m.group(0)[:200])
    for m in re.finditer(r'<script[^>]*\bid="[^"]+"[^>]*>', html):
        print("YC DEBUG script-id:", m.group(0)[:200])
    for probe in ("Demis Hassabis", "Playbook For Building", "Inside Garry Tan", "AI Native"):
        i = html.find(probe)
        if i != -1:
            print(f"YC DEBUG ctx[{probe}] at {i} =", repr(html[max(0, i - 400): i + 250]))
            break
    else:
        print("YC DEBUG: no known title text found in raw HTML (content likely JS-rendered)")


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
