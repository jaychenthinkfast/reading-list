# Reading List Schema

## SQLite file

Default database path:

`~/.openclaw/workspace/skills/reading-list/reading-list.db`

## Table: `articles`

- `id` — integer primary key
- `url` — unique article URL
- `title` — article title
- `summary` — short Chinese summary generated after reading the page
- `recommendation` — 推荐度，整数 1–10，数值越高越值得优先阅读
- `status` — `unread` or `read`
- `created_at` — first time the article was saved
- `updated_at` — last time title/summary/recommendation/status changed
- `read_at` — timestamp when marked as read; null when unread

## Query rules

Use SQL `LIKE` semantics through the helper script:
- title match
- summary match
- url match

## Sorting rules

The helper script supports these sort modes:

- `weighted` — 默认排序；按“最新时间 + 推荐度”加权排序
- `newest` — 纯按加入时间降序，再按推荐度降序
- `recommended` — 先按推荐度降序，再按加入时间降序
- `oldest` — 按加入时间升序
- `updated` — 按更新时间降序
- `title` — 按标题字母序

### Default sort behavior

默认使用动态加权排序：

`weighted_score = recency_score * 0.7 + recommendation_score * 0.3`

其中：

1. `recency_score`：基于加入时间做指数衰减，默认半衰期为 7 天，计算方式可理解为 `0.5 ^ (days_since_added / 7)`
2. `recommendation_score = recommendation / 10`
3. `weighted_score` 在检索时动态计算，不写回数据库

对待读文章列表，默认查询 `status = 'unread'`，确保排序和展示都只针对待读条目。
仅在默认排序或显式 `weighted` 排序时，返回中应包含排序规则说明，以及每篇文章的 `weighted_score / recency_score / recommendation_score`。

## Indexing notes

当前索引按实际读写模式收敛为：

- `(status, created_at DESC, recommendation DESC)`：支撑待读列表的时间序查询
- `(created_at DESC, recommendation DESC)`：支撑跨状态时间排序
- `(status, updated_at DESC, recommendation DESC)`：支撑按更新时间查看待读
- `title COLLATE NOCASE`：支撑标题排序
- `url` 的唯一约束：支撑按 URL 去重和更新

说明：默认 `weighted` 排序的加权值在应用层动态计算，因此不依赖单条 SQL `ORDER BY` 直接完成排序。
