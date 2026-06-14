from __future__ import annotations

import os
import traceback

from notion_client import Client

from fetch import fetch_html, parse_articles
from fetch_latent_space import fetch_latent_space_articles
from fetch_latetalk import fetch_latetalk_articles
from fetch_yc_library import fetch_yc_library_articles

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DB_ID"]

notion = Client(auth=NOTION_TOKEN)


def get_existing_urls() -> set[str]:
    urls: set[str] = set()
    cursor = None

    while True:
        response = notion.databases.query(
            database_id=NOTION_DB_ID,
            start_cursor=cursor,
            page_size=100,
        )

        for row in response["results"]:
            link = row["properties"]["原文链接"].get("url")
            if link:
                urls.add(link)

        if not response["has_more"]:
            break

        cursor = response["next_cursor"]

    return urls


def create_page(article: dict[str, str]) -> None:
    summary = article.get("summary") or ""
    properties = {
        "标题": {"title": [{"text": {"content": article["title"]}}]},
        "原文链接": {"url": article["url"]},
        "AI摘要": {"rich_text": [{"text": {"content": summary[:2000]}}]},
        "来源": {"select": {"name": article["source"]}},
        "我的决定": {"status": {"name": "📋 待审"}},
    }
    pub_date = article.get("feishu_date") or article.get("published_date")
    if pub_date:
        properties["发布日期"] = {"date": {"start": pub_date}}

    notion.pages.create(
        parent={"database_id": NOTION_DB_ID},
        properties=properties,
    )


def fetch_feishu() -> list[dict[str, str]]:
    try:
        html = fetch_html()
        articles = parse_articles(html)
        for a in articles:
            a["source"] = "waytoagi"
        return articles
    except Exception:  # noqa: BLE001
        print("❌ 飞书 waytoagi 抓取失败")
        traceback.print_exc()
        return []


def fetch_latent_space() -> list[dict[str, str]]:
    try:
        articles = fetch_latent_space_articles()
        for a in articles:
            a["source"] = "Latent Space"
        return articles
    except Exception:  # noqa: BLE001
        print("❌ Latent Space 抓取失败")
        traceback.print_exc()
        return []


def fetch_latetalk() -> list[dict[str, str]]:
    try:
        articles = fetch_latetalk_articles()
        for a in articles:
            a["source"] = "晚点聊 LateTalk"
        return articles
    except Exception:  # noqa: BLE001
        print("❌ 晚点聊 LateTalk 抓取失败")
        traceback.print_exc()
        return []


def fetch_yc_library() -> list[dict[str, str]]:
    try:
        articles = fetch_yc_library_articles()
        for a in articles:
            a["source"] = "YC Library"
        return articles
    except Exception:  # noqa: BLE001
        print("❌ YC Library 抓取失败")
        traceback.print_exc()
        return []


def main() -> None:
    feishu_articles = fetch_feishu()
    ls_articles = fetch_latent_space()
    latetalk_articles = fetch_latetalk()
    yc_articles = fetch_yc_library()

    print(
        f"飞书 waytoagi: {len(feishu_articles)} 篇 / "
        f"Latent Space: {len(ls_articles)} 篇 / "
        f"晚点聊 LateTalk: {len(latetalk_articles)} 篇 / "
        f"YC Library: {len(yc_articles)} 篇"
    )

    all_articles = feishu_articles + ls_articles + latetalk_articles + yc_articles
    existing_urls = get_existing_urls()
    new_articles = [a for a in all_articles if a["url"] not in existing_urls]

    print(f"合计 {len(all_articles)} 篇 / 新增 {len(new_articles)} 篇")

    for article in new_articles:
        try:
            create_page(article)
            print(f"✅ [{article.get('source','?')}] {article['title']}")
        except Exception:  # noqa: BLE001
            print(f"❌ [{article.get('source','?')}] {article['title']}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
