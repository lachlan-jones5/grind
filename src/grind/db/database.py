"""SQLite database for progress tracking and spaced repetition."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel


class Attempt(BaseModel):
    """A problem attempt record."""

    id: int | None = None
    problem_slug: str
    started_at: datetime
    completed_at: datetime | None = None
    result: str  # 'solved', 'gave_up', 'timeout'
    hints_used: int = 0
    code: str = ""
    language: str = "cpp"
    time_complexity: str | None = None
    space_complexity: str | None = None


class Pattern(BaseModel):
    """An algorithmic pattern for spaced repetition."""

    name: str  # 'two-pointer', 'sliding-window', etc
    last_practiced: datetime | None = None
    success_rate: float = 0.0
    total_attempts: int = 0
    next_review: datetime | None = None


class Insight(BaseModel):
    """A learning insight or 'aha moment'."""

    id: int | None = None
    problem_slug: str
    insight: str
    created_at: datetime


# Common algorithmic patterns
PATTERNS = [
    "two-pointer",
    "sliding-window",
    "binary-search",
    "dfs",
    "bfs",
    "dynamic-programming",
    "backtracking",
    "greedy",
    "hash-map",
    "stack",
    "queue",
    "heap",
    "trie",
    "union-find",
    "topological-sort",
    "monotonic-stack",
    "bit-manipulation",
    "math",
    "tree-traversal",
    "graph",
]


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY,
                    problem_slug TEXT NOT NULL,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    result TEXT NOT NULL,
                    hints_used INTEGER DEFAULT 0,
                    code TEXT,
                    language TEXT DEFAULT 'cpp',
                    time_complexity TEXT,
                    space_complexity TEXT
                );

                CREATE TABLE IF NOT EXISTS patterns (
                    name TEXT PRIMARY KEY,
                    last_practiced DATETIME,
                    success_rate REAL DEFAULT 0.0,
                    total_attempts INTEGER DEFAULT 0,
                    next_review DATETIME
                );

                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY,
                    problem_slug TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                );

                CREATE TABLE IF NOT EXISTS problem_patterns (
                    problem_slug TEXT NOT NULL,
                    pattern_name TEXT NOT NULL,
                    PRIMARY KEY (problem_slug, pattern_name)
                );

                CREATE INDEX IF NOT EXISTS idx_attempts_problem ON attempts(problem_slug);
                CREATE INDEX IF NOT EXISTS idx_patterns_next_review ON patterns(next_review);
            """)

            # Initialize patterns if not exist
            for pattern in PATTERNS:
                conn.execute(
                    "INSERT OR IGNORE INTO patterns (name) VALUES (?)",
                    (pattern,),
                )
            conn.commit()

    # Attempts CRUD
    def save_attempt(self, attempt: Attempt) -> int:
        """Save an attempt and return its ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO attempts 
                (problem_slug, started_at, completed_at, result, hints_used, code, language, time_complexity, space_complexity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.problem_slug,
                    attempt.started_at.isoformat(),
                    attempt.completed_at.isoformat() if attempt.completed_at else None,
                    attempt.result,
                    attempt.hints_used,
                    attempt.code,
                    attempt.language,
                    attempt.time_complexity,
                    attempt.space_complexity,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_attempts(self, problem_slug: str) -> list[Attempt]:
        """Get all attempts for a problem."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM attempts WHERE problem_slug = ? ORDER BY started_at DESC",
                (problem_slug,),
            ).fetchall()
            return [
                Attempt(
                    id=row["id"],
                    problem_slug=row["problem_slug"],
                    started_at=datetime.fromisoformat(row["started_at"]),
                    completed_at=datetime.fromisoformat(row["completed_at"])
                    if row["completed_at"]
                    else None,
                    result=row["result"],
                    hints_used=row["hints_used"],
                    code=row["code"] or "",
                    language=row["language"],
                    time_complexity=row["time_complexity"],
                    space_complexity=row["space_complexity"],
                )
                for row in rows
            ]

    # Pattern tracking
    def update_pattern(self, name: str, success: bool) -> None:
        """Update pattern after a practice attempt."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT total_attempts, success_rate FROM patterns WHERE name = ?",
                (name,),
            ).fetchone()

            if row:
                total = row["total_attempts"] + 1
                # Weighted average: recent attempts count more
                new_rate = (row["success_rate"] * 0.7 + (1.0 if success else 0.0) * 0.3)
                
                # Spaced repetition interval based on success
                if success:
                    # Increase interval on success
                    days = min(30, max(1, int(new_rate * 14)))
                else:
                    # Review again soon on failure
                    days = 1

                next_review = datetime.now() + timedelta(days=days)

                conn.execute(
                    """
                    UPDATE patterns 
                    SET last_practiced = ?, success_rate = ?, total_attempts = ?, next_review = ?
                    WHERE name = ?
                    """,
                    (datetime.now().isoformat(), new_rate, total, next_review.isoformat(), name),
                )
                conn.commit()

    def get_patterns_due(self) -> list[Pattern]:
        """Get patterns that are due for review."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM patterns 
                WHERE next_review IS NULL OR next_review <= ?
                ORDER BY success_rate ASC, next_review ASC
                """,
                (datetime.now().isoformat(),),
            ).fetchall()
            return [self._row_to_pattern(row) for row in rows]

    def get_weakest_patterns(self, limit: int = 5) -> list[Pattern]:
        """Get the patterns with lowest success rate."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM patterns 
                WHERE total_attempts > 0
                ORDER BY success_rate ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_pattern(row) for row in rows]

    def _row_to_pattern(self, row: sqlite3.Row) -> Pattern:
        return Pattern(
            name=row["name"],
            last_practiced=datetime.fromisoformat(row["last_practiced"])
            if row["last_practiced"]
            else None,
            success_rate=row["success_rate"],
            total_attempts=row["total_attempts"],
            next_review=datetime.fromisoformat(row["next_review"])
            if row["next_review"]
            else None,
        )

    # Insights
    def save_insight(self, insight: Insight) -> int:
        """Save a learning insight."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO insights (problem_slug, insight, created_at) VALUES (?, ?, ?)",
                (insight.problem_slug, insight.insight, insight.created_at.isoformat()),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_insights(self, problem_slug: str | None = None) -> list[Insight]:
        """Get insights, optionally filtered by problem."""
        with self._connect() as conn:
            if problem_slug:
                rows = conn.execute(
                    "SELECT * FROM insights WHERE problem_slug = ? ORDER BY created_at DESC",
                    (problem_slug,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM insights ORDER BY created_at DESC"
                ).fetchall()

            return [
                Insight(
                    id=row["id"],
                    problem_slug=row["problem_slug"],
                    insight=row["insight"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    # Stats
    def get_stats(self) -> dict:
        """Get overall practice statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            solved = conn.execute(
                "SELECT COUNT(*) FROM attempts WHERE result = 'solved'"
            ).fetchone()[0]
            unique_problems = conn.execute(
                "SELECT COUNT(DISTINCT problem_slug) FROM attempts WHERE result = 'solved'"
            ).fetchone()[0]

            # Streak calculation
            today = datetime.now().date()
            streak = 0
            current_date = today
            while True:
                has_attempt = conn.execute(
                    "SELECT 1 FROM attempts WHERE DATE(started_at) = ?",
                    (current_date.isoformat(),),
                ).fetchone()
                if has_attempt:
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break

            return {
                "total_attempts": total,
                "solved": solved,
                "unique_problems": unique_problems,
                "streak": streak,
            }
