from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape

import requests

FEED_URL = "https://www.latent.space/feed"
MAX_ITEMS = 20


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_pubdate(raw: str) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return None


def fetch_latent_space_articles() -> list[dict[str, str]]:
    response = requests.get(
        FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; info-tracking-sync/1.0)"},
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
        link = (item.findtext("link") or "").strip()
        desc_raw = item.findtext("description") or ""
        date_raw = item.findtext("pubDate") or ""

        if not title or not link:
            continue

        # Skip [AINews] daily roundups — low signal, waytoagi already
        # covers the same news in Chinese. Keep only long-form podcasts
        # and essay posts from latent.space.
        if title.startswith("[AINews]"):
            continue

        summary = _strip_html(desc_raw)
        published_date = _parse_pubdate(date_raw) or ""

        articles.append(
            {
                "title": title,
                "url": link,
                "summary": summary,
                "published_date": published_date,
            }
        )

    return articles
