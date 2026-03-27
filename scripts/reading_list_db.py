#!/usr/bin/env python3
import argparse
import json
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

DEFAULT_DB = Path(__file__).resolve().parent.parent / "reading-list.db"

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unread' CHECK(status IN ('unread', 'read')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    read_at TEXT
);
"""

INDEX_SCHEMA = """
DROP INDEX IF EXISTS idx_articles_status_created_at;
DROP INDEX IF EXISTS idx_articles_status_recommendation_created_at;
DROP INDEX IF EXISTS idx_articles_title;
DROP INDEX IF EXISTS idx_articles_created_at;
DROP INDEX IF EXISTS idx_articles_updated_at;
DROP INDEX IF EXISTS idx_articles_recommendation_created_at;

CREATE INDEX IF NOT EXISTS idx_articles_status_created_reco ON articles(status, created_at DESC, recommendation DESC);
CREATE INDEX IF NOT EXISTS idx_articles_created_reco ON articles(created_at DESC, recommendation DESC);
CREATE INDEX IF NOT EXISTS idx_articles_status_updated_reco ON articles(status, updated_at DESC, recommendation DESC);
CREATE INDEX IF NOT EXISTS idx_articles_title_nocase ON articles(title COLLATE NOCASE);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(BASE_SCHEMA)
    migrate_schema(conn)
    conn.executescript(INDEX_SCHEMA)
    return conn


def migrate_schema(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(articles)")}
    if "recommendation" not in columns:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN recommendation INTEGER NOT NULL DEFAULT 5 CHECK(recommendation >= 1 AND recommendation <= 10)"
        )
        conn.commit()


def row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "summary": row["summary"],
        "recommendation": row["recommendation"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "read_at": row["read_at"],
    }


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def iso_to_ts(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def build_weighted_sort_payload(rows: List[sqlite3.Row]) -> Dict[str, Any]:
    articles = [row_to_dict(r) for r in rows]
    half_life_days = 7
    recency_weight = 0.7
    recommendation_weight = 0.3
    formula = "weighted_score = recency_score * 0.7 + recommendation_score * 0.3"

    if not articles:
        return {
            "articles": [],
            "sort_info": {
                "sort": "weighted",
                "default": True,
                "formula": formula,
                "weights": {"recency": recency_weight, "recommendation": recommendation_weight},
                "notes": [
                    "recency_score 使用基于加入时间的指数衰减，半衰期为 7 天",
                    "recommendation_score = recommendation / 10",
                    "weighted_score 在检索时动态计算，不写回数据库",
                ],
                "half_life_days": half_life_days,
            },
        }

    now_ts = datetime.now(timezone.utc).timestamp()
    weighted_articles = []
    for article in articles:
        created_at_ts = iso_to_ts(article["created_at"])
        age_days = max(0.0, (now_ts - created_at_ts) / 86400.0)
        recency_score = math.pow(0.5, age_days / half_life_days)
        recommendation_score = article["recommendation"] / 10.0
        weighted_score = recency_score * recency_weight + recommendation_score * recommendation_weight
        article["ranking"] = {
            "weighted_score": round(weighted_score, 6),
            "recency_score": round(recency_score, 6),
            "recommendation_score": round(recommendation_score, 6),
            "weights": {"recency": recency_weight, "recommendation": recommendation_weight},
            "formula": formula,
            "half_life_days": half_life_days,
            "age_days": round(age_days, 6),
            "created_at_ts": created_at_ts,
        }
        weighted_articles.append(article)

    weighted_articles.sort(
        key=lambda a: (
            a["ranking"]["weighted_score"],
            a["ranking"]["recency_score"],
            a["ranking"]["recommendation_score"],
            a["created_at"],
        ),
        reverse=True,
    )

    return {
        "articles": weighted_articles,
        "sort_info": {
            "sort": "weighted",
            "default": True,
            "formula": formula,
            "weights": {"recency": recency_weight, "recommendation": recommendation_weight},
            "notes": [
                "recency_score 使用基于加入时间的指数衰减，半衰期为 7 天",
                "recommendation_score = recommendation / 10",
                "weighted_score 在检索时动态计算，不写回数据库",
            ],
            "half_life_days": half_life_days,
            "evaluated_at": datetime.fromtimestamp(now_ts, timezone.utc).replace(microsecond=0).isoformat(),
        },
    }


def cmd_add(args):
    conn = connect(args.db)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO articles(url, title, summary, recommendation, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'unread', ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            summary=excluded.summary,
            recommendation=excluded.recommendation,
            updated_at=excluded.updated_at
        """,
        (args.url, args.title.strip(), args.summary.strip(), args.recommendation, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE url = ?", (args.url,)).fetchone()
    print_json({"ok": True, "article": row_to_dict(row)})


def cmd_list(args):
    conn = connect(args.db)
    where = []
    values = []

    if args.status != "all":
        where.append("status = ?")
        values.append(args.status)

    if args.query:
        like = f"%{args.query}%"
        where.append("(title LIKE ? OR summary LIKE ? OR url LIKE ?)")
        values.extend([like, like, like])

    sql = "SELECT * FROM articles"
    if where:
        sql += " WHERE " + " AND ".join(where)

    order_map = {
        "newest": "created_at DESC, recommendation DESC",
        "oldest": "created_at ASC, recommendation DESC",
        "updated": "updated_at DESC, recommendation DESC",
        "title": "title COLLATE NOCASE ASC",
        "recommended": "recommendation DESC, created_at DESC",
    }

    if args.sort == "weighted":
        rows = conn.execute(sql, values).fetchall()
        weighted = build_weighted_sort_payload(rows)
        limited_articles = weighted["articles"][: args.limit]
        print_json({
            "ok": True,
            "count": len(limited_articles),
            "total_matches": len(weighted["articles"]),
            "sort_info": weighted["sort_info"],
            "articles": limited_articles,
        })
        return

    sql += f" ORDER BY {order_map[args.sort]}"
    sql += " LIMIT ?"
    values.append(args.limit)

    rows = conn.execute(sql, values).fetchall()
    print_json({"ok": True, "count": len(rows), "articles": [row_to_dict(r) for r in rows]})


def cmd_mark(args, status: str):
    conn = connect(args.db)
    now = utc_now()
    read_at = now if status == "read" else None

    if args.id is not None:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (args.id,)).fetchone()
        if not row:
            raise SystemExit(f"Article id={args.id} not found")
        conn.execute(
            "UPDATE articles SET status = ?, updated_at = ?, read_at = ? WHERE id = ?",
            (status, now, read_at, args.id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM articles WHERE id = ?", (args.id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM articles WHERE url = ?", (args.url,)).fetchone()
        if not row:
            raise SystemExit(f"Article url={args.url} not found")
        conn.execute(
            "UPDATE articles SET status = ?, updated_at = ?, read_at = ? WHERE url = ?",
            (status, now, read_at, args.url),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM articles WHERE url = ?", (args.url,)).fetchone()

    print_json({"ok": True, "article": row_to_dict(updated)})


def cmd_stats(args):
    conn = connect(args.db)
    total = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
    unread = conn.execute("SELECT COUNT(*) AS c FROM articles WHERE status = 'unread'").fetchone()["c"]
    read = conn.execute("SELECT COUNT(*) AS c FROM articles WHERE status = 'read'").fetchone()["c"]
    latest = conn.execute("SELECT * FROM articles ORDER BY created_at DESC, id DESC LIMIT 1").fetchone()
    print_json({
        "ok": True,
        "stats": {
            "total": total,
            "unread": unread,
            "read": read,
            "latest": row_to_dict(latest) if latest else None,
        },
    })


def build_parser():
    parser = argparse.ArgumentParser(description="Manage a lightweight reading-list SQLite database")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add or update an article as unread")
    add.add_argument("url")
    add.add_argument("title")
    add.add_argument("summary")
    add.add_argument("--recommendation", type=int, choices=range(1, 11), default=5, help="Recommendation score from 1 to 10")
    add.set_defaults(func=cmd_add)

    ls = sub.add_parser("list", help="List articles")
    ls.add_argument("--status", choices=["unread", "read", "all"], default="unread")
    ls.add_argument("--query", help="Match title, summary, or url")
    ls.add_argument("--sort", choices=["weighted", "newest", "recommended", "oldest", "updated", "title"], default="weighted")
    ls.add_argument("--limit", type=int, default=20)
    ls.set_defaults(func=cmd_list)

    mark_read = sub.add_parser("mark-read", help="Mark an article as read")
    group_read = mark_read.add_mutually_exclusive_group(required=True)
    group_read.add_argument("--id", type=int)
    group_read.add_argument("--url")
    mark_read.set_defaults(func=lambda args: cmd_mark(args, "read"))

    mark_unread = sub.add_parser("mark-unread", help="Mark an article as unread")
    group_unread = mark_unread.add_mutually_exclusive_group(required=True)
    group_unread.add_argument("--id", type=int)
    group_unread.add_argument("--url")
    mark_unread.set_defaults(func=lambda args: cmd_mark(args, "unread"))

    stats = sub.add_parser("stats", help="Show reading list stats")
    stats.set_defaults(func=cmd_stats)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
