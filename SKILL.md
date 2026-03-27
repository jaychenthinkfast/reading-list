---
name: reading-list
description: >
  维护一个轻量级“待阅读文章库”。当用户给出一个或多个文章 URL，希望先读取网页、生成简短摘要并评估推荐度，再把 URL/标题/摘要/推荐度保存为未读条目时使用；当用户想按时间、推荐度、标题、摘要或 URL 关键词列出待阅读文章时使用；当用户说某篇文章已读、要标记已读/未读、查看待读统计时也使用。适合“稍后阅读”“文章收集箱”“阅读队列管理”等场景。
---

# Reading List

## Overview

用本 skill 维护一个零依赖的 SQLite 文章库。默认流程是：先读取文章正文，再生成 1–3 句短摘要和 1–10 分推荐度，最后把标题、摘要、推荐度、URL 一起写入数据库并标记为 `unread`。

默认数据库文件：

`../db/reading-list.db`（相对于 skill 根目录；脚本按自身位置解析到 skill 同级 `db/` 目录，便于分发与更新时保留数据）

## Core workflow

### 1. Add articles

对每个 URL 按下面顺序执行：

1. 读取网页正文。
   - 若已安装 `web-content-fetcher` skill，优先按它的策略提取正文。
   - 否则直接使用 `web_fetch` 提取可读内容。
2. 从正文中提取标题。
   - 优先使用页面标题。
   - 如果标题缺失，生成一个简洁、可读的替代标题。
3. 生成 1–3 句简短摘要。
   - 聚焦“这篇文章讲什么 / 为什么值得读”。
   - 避免逐段复述。
   - 默认用中文输出，除非用户明确要求保留原文语言。
4. 给出 1–10 分推荐度。
   - `1–3`：价值较低，信息重复，或不太值得优先读。
   - `4–6`：一般可读，有一些信息量，但优先级普通。
   - `7–8`：值得读，信息密度高，或与用户近期兴趣明显相关。
   - `9–10`：强烈推荐，内容质量高、时效性强，或对用户有直接帮助。
5. 写入数据库并标记为 `unread`。
   - 使用 `scripts/reading_list_db.py add <url> <title> <summary> --recommendation <score>`
   - 如果 URL 已存在，更新标题、摘要和推荐度。

### 2. List articles

按用户要求列出条目：

- 默认：`list --status unread --sort weighted`
- 按时间：`list --sort newest` 或 `list --sort oldest`
- 按推荐度：`list --sort recommended`
- 按标题/摘要/URL 关键词：`list --query <keyword>`
- 按状态：`list --status unread|read|all`

常用命令：

```bash
python3 scripts/reading_list_db.py list --status unread --sort weighted --limit 20
python3 scripts/reading_list_db.py list --status unread --sort recommended --limit 20
python3 scripts/reading_list_db.py list --status all --query AI --sort weighted --limit 20
```

向用户展示时，优先给出：
- `id`
- `title`
- `recommendation`
- `summary`
- `status`
- `created_at`
- `url`

如果结果较多，先展示前 5–10 条并说明可继续筛选。

### 3. Mark read/unread

当用户说“这篇读完了”“把第 3 条标成已读”“恢复未读”时：

```bash
python3 scripts/reading_list_db.py mark-read --id 3
python3 scripts/reading_list_db.py mark-unread --url 'https://example.com/post'
```

优先使用 `id`，因为同一域名长 URL 更容易出错。

### 4. Show stats

当用户想看待读数量、总数、最近保存文章时：

```bash
python3 scripts/reading_list_db.py stats
```

## Chat workflow

当用户在聊天里直接使用这个 skill 时，优先支持下面这些自然表达：

- “把这个链接加入待读：<url>”
- “把这 3 个链接存一下，稍后看”
- “列出最近未读文章”
- “按推荐度列一下待读文章”
- “找一下标题里有 Agent 的文章”
- “把第 4 条标成已读”
- “把刚才那篇恢复成未读”
- “看看我还有多少没读”

### Recommended reply format for add/import

导入 1 个 URL 时，回复：
- 是否成功入库
- 提取到的标题
- 推荐度（1–10）
- 1–3 句摘要
- 当前状态（未读）

导入多个 URL 时，先给总览，再列逐条结果：
- 成功 X 篇 / 失败 Y 篇
- 对每篇成功条目给出：`id`、标题、推荐度、摘要
- 对失败条目给出 URL 和失败原因

### Recommended reply format for list

- 当使用默认排序或显式 `--sort weighted` 时：先展示排序规则，再给每篇文章附上加权值明细。
- 当使用 `--sort newest|oldest|recommended|updated|title` 时：按普通列表展示，不必附加权值。

默认加权排序下，在聊天界面里按下面格式列出，每条保持 4–6 行：

```text
排序规则：weighted_score = recency_score × 0.7 + recommendation_score × 0.3
[id] 标题
推荐度：8/10 | 状态：未读 | 加入时间：2026-03-26 09:30
加权值：0.8123（时间分 0.8747，推荐分 0.7000）
摘要：......
链接：https://example.com
```

如果结果很多：
- 默认先返回前 10 条
- 主动告诉用户可继续按关键词、时间、推荐度、已读/未读筛选

## Output rules

- 列表输出保持紧凑，适合聊天界面阅读。
- 摘要不要超过 120 个中文字符，除非用户明确要详细版。
- 如果文章提取失败，明确告诉用户该 URL 暂未入库，并给出失败原因。
- 批量导入多个 URL 时，逐条汇报成功/失败，不要把失败条目静默吞掉。
- 当用户指定“按时间”时，默认理解为按 `created_at` 排序。
- 当用户未指定排序方式时，默认列出 `status = unread` 的条目，并按“最新时间 + 推荐度”加权排序。
- 加权排序在检索时动态计算，不写回数据库；默认规则：`weighted_score = recency_score * 0.7 + recommendation_score * 0.3`。
- `recency_score` 使用基于加入时间的指数衰减，默认半衰期为 7 天；`recommendation_score = recommendation / 10`。
- 仅在默认排序或显式 `weighted` 排序时，返回结果应同时展示计算规则和每篇文章的加权值明细。
- `newest`、`oldest`、`recommended`、`updated`、`title` 均保持普通排序输出，不附加 `ranking` 字段。
- 数据库索引主要服务于时间序、推荐度序和更新时间序等数据库原生排序；默认加权排序在应用层动态计算。
- 当用户说“按标题找”或“按摘要找”时，可统一走 `--query` 模糊匹配，然后在回复里说明是关键词匹配结果。

## Scripts

### `scripts/reading_list_db.py`

SQLite 管理脚本，零额外依赖，支持：
- `add`
- `list`
- `mark-read`
- `mark-unread`
- `stats`

示例：

```bash
python3 scripts/reading_list_db.py add 'https://example.com' '示例标题' '这是一段简短摘要。' --recommendation 8
python3 scripts/reading_list_db.py list --status unread --sort weighted
```

## References

- 需要数据库字段说明和排序规则时，读取 `references/schema.md`。
