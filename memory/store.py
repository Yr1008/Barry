"""
Barry Memory Store — SQLite-backed long-term memory.

Stores:
- User preferences (key-value)
- Communication tone per contact
- Past interactions / summaries
- Cached data from connectors
- Todo items
- Events / reminders
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryStore:
    """Persistent memory for Barry using SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                -- User preferences (persistent settings)
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- Tone profiles per contact
                CREATE TABLE IF NOT EXISTS tone_profiles (
                    contact_id TEXT PRIMARY KEY,
                    contact_name TEXT,
                    platform TEXT,
                    tone_description TEXT,
                    sample_messages TEXT,
                    last_updated TEXT
                );

                -- Conversation history summaries
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT
                );

                -- Todo items
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority INTEGER DEFAULT 3,
                    due_date TEXT,
                    status TEXT DEFAULT 'pending',
                    source TEXT,
                    tags TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- Cached external data (emails, events, messages)
                CREATE TABLE IF NOT EXISTS data_cache (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT
                );

                -- Long-term facts Barry has learned
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    source TEXT
                );

                -- Notifications sent (to avoid duplicates)
                CREATE TABLE IF NOT EXISTS notifications_sent (
                    id TEXT PRIMARY KEY,
                    message TEXT,
                    sent_at TEXT NOT NULL
                );
            """)

    # ─── Preferences ──────────────────────────────────────────────────────────

    def set_preference(self, key: str, value: Any) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), datetime.now().isoformat()),
            )

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
            if row:
                return json.loads(row["value"])
            return default

    def get_all_preferences(self) -> dict[str, Any]:
        with self._conn() as conn:
            rows = conn.execute("SELECT key, value FROM preferences").fetchall()
            return {r["key"]: json.loads(r["value"]) for r in rows}

    # ─── Tone Profiles ────────────────────────────────────────────────────────

    def save_tone_profile(
        self,
        contact_id: str,
        contact_name: str,
        platform: str,
        tone_description: str,
        sample_messages: list[str],
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tone_profiles
                   (contact_id, contact_name, platform, tone_description, sample_messages, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    contact_id,
                    contact_name,
                    platform,
                    tone_description,
                    json.dumps(sample_messages[-20:]),  # Keep last 20 samples
                    datetime.now().isoformat(),
                ),
            )

    def get_tone_profile(self, contact_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tone_profiles WHERE contact_id = ?", (contact_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["sample_messages"] = json.loads(d["sample_messages"] or "[]")
                return d
            return None

    def get_all_tone_profiles(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM tone_profiles").fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["sample_messages"] = json.loads(d["sample_messages"] or "[]")
                result.append(d)
            return result

    # ─── Conversation History ─────────────────────────────────────────────────

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_history (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
                (role, content, datetime.now().isoformat(), session_id),
            )

    def get_recent_messages(self, limit: int = 20, session_id: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM conversation_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def clear_old_messages(self, keep_last: int = 100) -> None:
        with self._conn() as conn:
            conn.execute(
                """DELETE FROM conversation_history WHERE id NOT IN (
                   SELECT id FROM conversation_history ORDER BY timestamp DESC LIMIT ?)""",
                (keep_last,),
            )

    # ─── Todos ────────────────────────────────────────────────────────────────

    def add_todo(
        self,
        title: str,
        description: str = "",
        priority: int = 3,
        due_date: str | None = None,
        source: str = "manual",
        tags: list[str] | None = None,
    ) -> int:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO todos (title, description, priority, due_date, status, source, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
                (title, description, priority, due_date, source, json.dumps(tags or []), now, now),
            )
            return cur.lastrowid

    def get_todos(self, status: str = "pending") -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM todos WHERE status = ? ORDER BY priority ASC, due_date ASC",
                (status,),
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["tags"] = json.loads(d["tags"] or "[]")
                result.append(d)
            return result

    def update_todo_status(self, todo_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE todos SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), todo_id),
            )

    def update_todo_priority(self, todo_id: int, priority: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE todos SET priority = ?, updated_at = ? WHERE id = ?",
                (priority, datetime.now().isoformat(), todo_id),
            )

    # ─── Data Cache ───────────────────────────────────────────────────────────

    def cache_data(
        self,
        item_id: str,
        source: str,
        data_type: str,
        content: dict | str,
        ttl_minutes: int = 30,
    ) -> None:
        from datetime import timedelta
        expires = (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO data_cache (id, source, data_type, content, fetched_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    source,
                    data_type,
                    json.dumps(content) if isinstance(content, dict) else content,
                    datetime.now().isoformat(),
                    expires,
                ),
            )

    def get_cached(self, item_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM data_cache WHERE id = ? AND (expires_at IS NULL OR expires_at > ?)",
                (item_id, datetime.now().isoformat()),
            ).fetchone()
            if row:
                d = dict(row)
                try:
                    d["content"] = json.loads(d["content"])
                except Exception:
                    pass
                return d
            return None

    def get_all_cached(self, source: str | None = None, data_type: str | None = None) -> list[dict]:
        with self._conn() as conn:
            query = "SELECT * FROM data_cache WHERE expires_at > ?"
            params: list = [datetime.now().isoformat()]
            if source:
                query += " AND source = ?"
                params.append(source)
            if data_type:
                query += " AND data_type = ?"
                params.append(data_type)
            rows = conn.execute(query, params).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    d["content"] = json.loads(d["content"])
                except Exception:
                    pass
                result.append(d)
            return result

    # ─── Facts ────────────────────────────────────────────────────────────────

    def add_fact(self, category: str, fact: str, confidence: float = 1.0, source: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO facts (category, fact, confidence, created_at, source) VALUES (?, ?, ?, ?, ?)",
                (category, fact, confidence, datetime.now().isoformat(), source),
            )

    def get_facts(self, category: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM facts WHERE category = ? ORDER BY confidence DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM facts ORDER BY category, confidence DESC").fetchall()
            return [dict(r) for r in rows]

    # ─── Notifications ────────────────────────────────────────────────────────

    def mark_notification_sent(self, notif_id: str, message: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notifications_sent (id, message, sent_at) VALUES (?, ?, ?)",
                (notif_id, message, datetime.now().isoformat()),
            )

    def was_notification_sent(self, notif_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications_sent WHERE id = ?", (notif_id,)
            ).fetchone()
            return row is not None
