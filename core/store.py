from __future__ import annotations
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.schema import Memory, MemorySource, MemoryCategory

DB_PATH = Path.home() / ".memos" / "memories.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id         TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    source     TEXT NOT NULL,
    category   TEXT NOT NULL,
    tags       TEXT DEFAULT '[]',
    sensitive  INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.8,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_raw TEXT
);
"""

CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(id UNINDEXED, content, tags, tokenize='porter ascii');
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_category ON memories(category)",
    "CREATE INDEX IF NOT EXISTS idx_source ON memories(source)",
    "CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_sensitive ON memories(sensitive)",
]

# keep the FTS table in sync via triggers so we don't have to do it manually
FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(id, content, tags) VALUES (new.id, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS fts_delete AFTER DELETE ON memories BEGIN
    DELETE FROM memories_fts WHERE id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS fts_update AFTER UPDATE ON memories BEGIN
    DELETE FROM memories_fts WHERE id = old.id;
    INSERT INTO memories_fts(id, content, tags) VALUES (new.id, new.content, new.tags);
END;
"""


def _migrate_sensitive_column(conn: sqlite3.Connection) -> None:
    """Add the sensitive column to existing databases that lack it."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
    if "sensitive" not in cols:
        conn.execute("ALTER TABLE memories ADD COLUMN sensitive INTEGER DEFAULT 0")
        conn.commit()


def _row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        id=row["id"],
        content=row["content"],
        source=MemorySource(row["source"]),
        category=MemoryCategory(row["category"]),
        tags=json.loads(row["tags"]),
        sensitive=bool(row["sensitive"]),
        confidence=row["confidence"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        source_raw=row["source_raw"],
    )


# ── Memory Store ─────────────────────────────────────────────────────────────

class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(CREATE_TABLE)
            _migrate_sensitive_column(conn)
            conn.executescript(CREATE_FTS)
            for idx in INDEXES:
                conn.execute(idx)
            conn.executescript(FTS_TRIGGERS)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def get_by_id(self, memory_id: str) -> Optional[Memory]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return _row_to_memory(row) if row else None

    def get_by_category(self, category: str) -> list[Memory]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY created_at DESC", (category,)
            ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def get_by_source(self, source: str) -> list[Memory]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE source = ? ORDER BY created_at DESC", (source,)
            ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def get_stale(self, threshold_days: int = 180) -> list[Memory]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=threshold_days)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE created_at < ? ORDER BY created_at ASC",
                (cutoff,)
            ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        # try FTS5 first, fall back to keyword scan for special chars / edge cases
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    """SELECT m.* FROM memories m
                       JOIN memories_fts f ON m.id = f.id
                       WHERE memories_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit)
                ).fetchall()
            return [_row_to_memory(r) for r in rows]
        except sqlite3.OperationalError:
            return self._keyword_search(query, limit)

    def _keyword_search(self, query: str, limit: int = 5) -> list[Memory]:
        all_memories = self.get_all(limit=1000)
        q = query.lower()
        scored = []
        for m in all_memories:
            text = (m.content + " " + " ".join(m.tags)).lower()
            score = sum(1 for word in q.split() if word in text)
            if score > 0:
                scored.append((score, m.created_at.isoformat(), m))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [m for _, _, m in scored[:limit]]

    def find_near_duplicates(self, threshold: float = 0.75) -> list[tuple[Memory, Memory]]:
        # Jaccard similarity on word sets — good enough for catching near-dupe imports
        all_memories = self.get_all(limit=1000)
        duplicates = []
        for i, a in enumerate(all_memories):
            for b in all_memories[i + 1:]:
                words_a = set(a.content.lower().split())
                words_b = set(b.content.lower().split())
                if not words_a or not words_b:
                    continue
                jaccard = len(words_a & words_b) / len(words_a | words_b)
                if jaccard >= threshold:
                    duplicates.append((a, b))
        return duplicates

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def count_by_source(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT source, COUNT(*) as n FROM memories GROUP BY source"
            ).fetchall()
        return {r["source"]: r["n"] for r in rows}

    def count_by_category(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) as n FROM memories GROUP BY category"
            ).fetchall()
        return {r["category"]: r["n"] for r in rows}

    def add(self, memory: Memory, skip_duplicates: bool = True) -> bool:
        if skip_duplicates and self.content_exists(memory.content):
            return False
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO memories
                   (id, content, source, category, tags, sensitive, confidence,
                    created_at, updated_at, source_raw)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory.id,
                    memory.content,
                    memory.source if isinstance(memory.source, str) else memory.source.value,
                    memory.category if isinstance(memory.category, str) else memory.category.value,
                    json.dumps(memory.tags),
                    int(memory.sensitive),
                    memory.confidence,
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.source_raw,
                )
            )
            conn.commit()
        return True

    def add_many(self, memories: list[Memory], skip_duplicates: bool = True) -> int:
        return sum(1 for m in memories if self.add(m, skip_duplicates=skip_duplicates))

    def update(self, memory_id: str, content: str,
               category: Optional[str] = None,
               tags: Optional[list[str]] = None) -> bool:
        memory = self.get_by_id(memory_id)
        if not memory:
            return False
        with self._conn() as conn:
            conn.execute(
                """UPDATE memories
                   SET content = ?, category = ?, tags = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    content,
                    category or memory.category,
                    json.dumps(tags if tags is not None else memory.tags),
                    datetime.now(timezone.utc).isoformat(),
                    memory_id,
                )
            )
            conn.commit()
        return True

    def set_sensitive(self, memory_id: str, sensitive: bool) -> bool:
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE memories SET sensitive = ?, updated_at = ? WHERE id = ?",
                (int(sensitive), datetime.now(timezone.utc).isoformat(), memory_id)
            )
            conn.commit()
        return cursor.rowcount > 0

    def get_sensitive(self) -> list[Memory]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE sensitive = 1 ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
        return cursor.rowcount > 0

    def clear_source(self, source: str) -> int:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE source = ?", (source,))
            conn.commit()
        return cursor.rowcount

    def clear_all(self) -> int:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM memories")
            conn.commit()
        return cursor.rowcount

    def content_exists(self, content: str) -> bool:
        with self._conn() as conn:
            return bool(conn.execute(
                "SELECT 1 FROM memories WHERE content = ?", (content,)
            ).fetchone())

    def exists(self, memory_id: str) -> bool:
        with self._conn() as conn:
            return bool(conn.execute(
                "SELECT 1 FROM memories WHERE id = ?", (memory_id,)
            ).fetchone())

    def export_json(self, output_path: Path, source: Optional[str] = None) -> int:
        memories = self.get_by_source(source) if source else self.get_all(limit=10000)
        data = [
            {
                "id": m.id,
                "content": m.content,
                "source": m.source,
                "category": m.category,
                "tags": m.tags,
                "sensitive": m.sensitive,
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in memories
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return len(data)
