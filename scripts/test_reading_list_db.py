#!/usr/bin/env python3
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "reading_list_db.py"


def run_cmd(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command output is not valid JSON: {proc.stdout}") from exc


def seed_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            recommendation INTEGER NOT NULL CHECK(recommendation >= 1 AND recommendation <= 10),
            status TEXT NOT NULL DEFAULT 'unread' CHECK(status IN ('unread', 'read')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            read_at TEXT
        );
        """
    )
    rows = [
        (
            "https://example.com/older-high",
            "Older but recommended",
            "older item",
            10,
            "unread",
            "2026-03-25T00:00:00+00:00",
            "2026-03-25T00:00:00+00:00",
            None,
        ),
        (
            "https://example.com/new-mid",
            "Newest mid recommendation",
            "new item",
            6,
            "unread",
            "2026-03-26T00:00:00+00:00",
            "2026-03-26T00:00:00+00:00",
            None,
        ),
        (
            "https://example.com/mid-low",
            "Middle low recommendation",
            "middle item",
            2,
            "unread",
            "2026-03-25T12:00:00+00:00",
            "2026-03-25T12:00:00+00:00",
            None,
        ),
    ]
    conn.executemany(
        "INSERT INTO articles(url, title, summary, recommendation, status, created_at, updated_at, read_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "reading-list-test.db"
        seed_db(db_path)

        weighted = run_cmd("--db", str(db_path), "list", "--status", "unread", "--sort", "weighted", "--limit", "10")
        assert_true(weighted["ok"] is True, "weighted list should succeed")
        assert_true(weighted["sort_info"]["sort"] == "weighted", "weighted sort_info missing")
        assert_true(len(weighted["articles"]) == 3, "weighted list should return 3 articles")
        assert_true("ranking" in weighted["articles"][0], "weighted articles should include ranking")
        assert_true(weighted["sort_info"]["half_life_days"] == 7, "weighted sort should expose the configured half-life")
        assert_true(weighted["articles"][0]["url"] == "https://example.com/older-high", "weighted sort should allow a top recommendation to outrank a slightly newer mid-scored article under the configured weights")
        assert_true(weighted["articles"][1]["url"] == "https://example.com/new-mid", "weighted sort should keep the newer mid-scored article ahead of the low-scored article")
        assert_true(weighted["articles"][2]["url"] == "https://example.com/mid-low", "weighted sort should place the low-scored article last in this fixture")

        default_sort = run_cmd("--db", str(db_path), "list", "--status", "unread", "--limit", "10")
        assert_true(default_sort["articles"][0]["url"] == weighted["articles"][0]["url"], "default list should match weighted ordering")
        assert_true("sort_info" in default_sort, "default list should expose weighted sort_info")

        newest = run_cmd("--db", str(db_path), "list", "--status", "unread", "--sort", "newest", "--limit", "10")
        assert_true(newest["ok"] is True, "newest list should succeed")
        assert_true("sort_info" not in newest, "newest list should not include weighted sort_info")
        assert_true("ranking" not in newest["articles"][0], "newest list should not include ranking")
        assert_true(newest["articles"][0]["url"] == "https://example.com/new-mid", "newest should sort by created_at desc")
        assert_true(newest["articles"][1]["url"] == "https://example.com/mid-low", "newest second item should be middle item")

        recommended = run_cmd("--db", str(db_path), "list", "--status", "unread", "--sort", "recommended", "--limit", "10")
        assert_true(recommended["articles"][0]["url"] == "https://example.com/older-high", "recommended should sort by recommendation desc")
        assert_true(recommended["articles"][1]["url"] == "https://example.com/new-mid", "recommended second item should be newer mid recommendation")

        query = run_cmd("--db", str(db_path), "list", "--status", "all", "--query", "middle", "--sort", "weighted", "--limit", "10")
        assert_true(query["count"] == 1, "query should filter down to one article")
        assert_true(query["articles"][0]["url"] == "https://example.com/mid-low", "query should return the matching article")

    print("OK: reading-list regression tests passed")


if __name__ == "__main__":
    main()
