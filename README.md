# info-tracking-sync

每日把多个信息源同步到同一个 Notion 数据库（资料推送看板）的 GitHub Action。

## 信息源

| 来源 | 说明 |
| --- | --- |
| `waytoagi` | 飞书 waytoagi「近 7 日更新日志」 |
| `Latent Space` | Latent Space 博客最新文章 |
| `晚点聊 LateTalk` | 晚点聊 LateTalk 播客 RSS |
| `YC Library` | Y Combinator Library「The Latest」最新内容 |

## 环境变量

- `NOTION_TOKEN`: Notion integration token
- `NOTION_DB_ID`: Notion database ID

## 本地运行

```bash
pip install -r requirements.txt
python src/sync.py
```

## 行为

- 分别抓取上述各信息源的最新内容
- 解析标题、原文链接、摘要、发布日期
- 按「原文链接」去重，只写入 Notion 中尚不存在的链接
- 新写入的行「我的决定」默认是「📋 待审」
- 保留 `workflow_dispatch`，方便手动触发

## 添加新信息源

1. 在 `src/` 下新增 `fetch_<source>.py`，导出返回 `{title, url, summary, published_date}` 列表的函数
2. 在 `src/sync.py` 里 import 并包一层 `fetch_<source>()`，给每条加上 `source` 字段
3. 把它接入 `main()` 的统计与汇总
