"""
History Store — SQLite-backed transcript and refinement history.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import uuid


@dataclass
class HistoryEntry:
    """A single history entry."""
    id: str
    timestamp: str
    transcript: str
    refined: str
    skill: str
    model: str
    latency_ms: float
    copied: bool = False
    favorited: bool = False
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "tags": json.dumps(self.tags),
        }

    @classmethod
    def from_row(cls, row: tuple) -> "HistoryEntry":
        return cls(
            id=row[0],
            timestamp=row[1],
            transcript=row[2],
            refined=row[3],
            skill=row[4],
            model=row[5],
            latency_ms=row[6],
            copied=bool(row[7]),
            favorited=bool(row[8]),
            tags=json.loads(row[9]) if row[9] else [],
        )


class HistoryStore:
    """SQLite-backed history store."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS history (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        transcript TEXT NOT NULL,
        refined TEXT NOT NULL,
        skill TEXT NOT NULL,
        model TEXT NOT NULL,
        latency_ms REAL NOT NULL,
        copied INTEGER DEFAULT 0,
        favorited INTEGER DEFAULT 0,
        tags TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp);
    CREATE INDEX IF NOT EXISTS idx_skill ON history(skill);
    CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
        transcript, refined, content='history', content_rowid='rowid'
    );
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".dictprompt" / "history.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.executescript(self.SCHEMA)
        return self._conn

    def add(
        self,
        transcript: str,
        refined: str,
        skill: str,
        model: str,
        latency_ms: float,
    ) -> HistoryEntry:
        """Add a new history entry."""
        entry = HistoryEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            transcript=transcript,
            refined=refined,
            skill=skill,
            model=model,
            latency_ms=latency_ms,
        )

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO history (id, timestamp, transcript, refined, skill, model, latency_ms, copied, favorited, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entry.id, entry.timestamp, entry.transcript, entry.refined,
             entry.skill, entry.model, entry.latency_ms, 0, 0, "[]"),
        )

        # Also add to FTS index
        cursor.execute(
            "INSERT INTO history_fts (rowid, transcript, refined) VALUES (?, ?, ?)",
            (cursor.lastrowid, transcript, refined),
        )

        self.conn.commit()
        return entry

    def get(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get a single entry by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM history WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        return HistoryEntry.from_row(row) if row else None

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        skill: Optional[str] = None,
        favorited_only: bool = False,
    ) -> List[HistoryEntry]:
        """List history entries with optional filters."""
        query = "SELECT * FROM history WHERE 1=1"
        params = []

        if skill:
            query += " AND skill = ?"
            params.append(skill)

        if favorited_only:
            query += " AND favorited = 1"

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [HistoryEntry.from_row(row) for row in cursor.fetchall()]

    def search(self, query: str, limit: int = 20) -> List[HistoryEntry]:
        """Full-text search across transcripts and refinements."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT h.* FROM history h
            JOIN history_fts fts ON h.rowid = fts.rowid
            WHERE history_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        return [HistoryEntry.from_row(row) for row in cursor.fetchall()]

    def toggle_favorite(self, entry_id: str) -> bool:
        """Toggle favorite status. Returns new state."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE history SET favorited = NOT favorited WHERE id = ?",
            (entry_id,),
        )
        self.conn.commit()

        cursor.execute("SELECT favorited FROM history WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False

    def delete(self, entry_id: str) -> bool:
        """Delete an entry."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> int:
        """Clear all history. Returns count deleted."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM history")
        count = cursor.rowcount
        self.conn.commit()
        return count

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
