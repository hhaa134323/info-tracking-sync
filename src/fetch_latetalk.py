from __future__ import annotations

import re
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree as ET

import requests

# Fireside-hosted RSS feed for 晚点聊 LateTalk — the same feed the official site
# links under 「通过 RSS 订阅」. Each episode carries a short, human-written
# one-line subtitle (e.g. 「回到智能，进入家庭。」) in <itunes:subtitle> — a
# curated 总结型 field — so we prefer it over the long HTML show notes in
# <description>. Belt+suspenders fallbacks keep the row useful if a given
# episode leaves the subtitle blank.
RSS_URL = "https://podcast.latepost.com/rss"
MAX_ITEMS = 30

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"

# ElementTree matches namespaced tags via Clark notation: a leading brace, the
# namespace URI, a closing brace, then the local name. A bare
# ITUNES_NS + "subtitle" (no braces) is instead parsed as an ElementPath, and
# the embedded "://" makes findtext raise SyntaxError: prefix 'http' not found
# in prefix map — which previously aborted the entire LateTalk fetch.
# Build the qualified tag via string concatenation (NOT f-string brace
# placeholders) so the literal braces survive intact.
ITUNES_SUBTITLE = "{" + ITUNES_NS + "}subtitle"
ITUNES_SUMMARY = "{" + ITUNES_NS + "}summary"


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_pub_date(raw: str) -> str:
    """Convert an RFC 822 pubDate to YYYY-MM-DD."""
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return ""


def _pick_summary(item: ET.Element) -> str:
    """Prefer the curated one-line subtitle; fall back to show notes / summary."""
    candidates = [
        item.findtext(ITUNES_SUBTITLE),
        item.findtext("description"),
        item.findtext(ITUNES_SUMMARY),
    ]
    for value in candidates:
        text = _strip_html(value or "")
        if text:
            return text
    return ""


def fetch_latetalk_articles() -> list[dict[str, str]]:
    response = requests.get(
        RSS_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; info-tracking-sync/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
        timeout=30,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    channel = root.find("channel")
    if channel is None:
        return []

    articles: list[dict[str, str]] = []
    for item in channel.findall("item")[:MAX_ITEMS]:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue

        articles.append(
            {
                "title": title,
                "url": url,
                "summary": _pick_summary(item),
                "published_date": _parse_pub_date(item.findtext("pubDate") or ""),
            }
        )

    return articles
