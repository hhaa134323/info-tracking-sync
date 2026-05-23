# feishu-waytoagi-sync

每日同步飞书 waytoagi「近 7 日更新日志」到 Notion 数据库的 GitHub Action。

## 环境变量

- `NOTION_TOKEN`: Notion integration token
- `NOTION_DB_ID`: Notion database ID

## 本地运行

```bash
pip install -r requirements.txt
python src/sync.py
```

## 行为

- 从公开飞书页面抓取「近 7 日更新日志」
- 解析标题、原文链接和摘要
- 只写入 Notion 中不存在的链接
- 保留 `workflow_dispatch`，方便手动触发
