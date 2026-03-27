# reading-list

一个轻量的待读文章 Skill，使用 SQLite 管理文章列表，支持添加、检索、排序、标记已读/未读和查看统计信息。

## 功能

- 添加文章到待读列表
- 列出未读、已读或全部文章
- 按时间、推荐度、关键词筛选
- 标记文章为已读或未读
- 查看文章库统计信息

## 目录结构

```text
reading-list/
├── SKILL.md
├── README.md
├── scripts/
│   ├── reading_list_db.py
│   └── test_reading_list_db.py
└── references/
    └── schema.md
```

默认数据库位于 Skill 同级目录：

```text
../db/reading-list.db
```

也就是相对于当前 Skill 根目录，数据库默认放在：

```text
skills/db/reading-list.db
```

这样可以把 Skill 代码和持久化数据分开，更新、替换或重新分发 Skill 时更安全。

## 常用命令

以下命令默认在 Skill 根目录执行。

### 列出未读文章（默认加权排序）

```bash
python3 scripts/reading_list_db.py list --status unread --sort weighted --limit 20
```

### 按推荐度列出未读文章

```bash
python3 scripts/reading_list_db.py list --status unread --sort recommended --limit 20
```

### 按关键词搜索文章

```bash
python3 scripts/reading_list_db.py list --status all --query AI --sort weighted --limit 20
```

### 添加文章

```bash
python3 scripts/reading_list_db.py add 'https://example.com' '示例标题' '这是一段简短摘要。' --recommendation 8
```

### 标记已读

```bash
python3 scripts/reading_list_db.py mark-read --id 3
```

### 标记未读

```bash
python3 scripts/reading_list_db.py mark-unread --id 3
```

### 查看统计信息

```bash
python3 scripts/reading_list_db.py stats
```

## 可选参数

脚本支持通过 `--db` 显式指定数据库路径，例如：

```bash
python3 scripts/reading_list_db.py --db ../db/reading-list.db stats
```

如果不传 `--db`，脚本会默认解析到同级 `db/` 目录。

## 排序说明

默认排序使用动态加权公式：

```text
weighted_score = recency_score * 0.7 + recommendation_score * 0.3
```

其中：

- `recency_score`：基于加入时间的指数衰减，半衰期为 7 天
- `recommendation_score = recommendation / 10`

更多字段和排序细节可参考：

- `references/schema.md`

## 说明

- Skill 目录主要存放代码和说明文件
- 持久化数据默认放在同级 `db/` 目录
- `reading-list.db` 不应提交到仓库
