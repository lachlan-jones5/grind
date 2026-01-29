"""Sync service for LeetCode progress synchronization."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from pydantic import BaseModel

from grind.auth import LeetCodeAuth, AuthenticationError, SessionExpiredError
from grind.sync.models import LeetCodeSubmission, ProblemStatus, SyncMeta


class SyncStatus(Enum):
    """Status of a sync operation."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some items failed
    FAILED = "failed"
    NOT_AUTHENTICATED = "not_authenticated"
    RATE_LIMITED = "rate_limited"


class SyncResult(BaseModel):
    """Result of a sync operation."""
    
    status: SyncStatus
    submissions_synced: int = 0
    problems_updated: int = 0
    errors: list[str] = []
    started_at: datetime
    completed_at: datetime | None = None
    
    @property
    def duration_seconds(self) -> float | None:
        """Get sync duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class SyncService:
    """Service for syncing LeetCode progress to local database.
    
    Handles:
    - Fetching submission history from LeetCode
    - Storing submissions in local database
    - Tracking problem solved status
    - Incremental sync (only fetch new submissions)
    - Filtering premium-only problems
    """
    
    # GraphQL queries
    SUBMISSIONS_QUERY = """
        query getSubmissions($offset: Int!, $limit: Int!) {
            submissionList(offset: $offset, limit: $limit) {
                lastKey
                hasNext
                submissions {
                    id
                    title
                    titleSlug
                    timestamp
                    statusDisplay
                    lang
                    runtime
                    memory
                }
            }
        }
    """
    
    SOLVED_PROBLEMS_QUERY = """
        query getSolvedProblems($username: String!) {
            matchedUser(username: $username) {
                submitStatsGlobal {
                    acSubmissionNum {
                        difficulty
                        count
                    }
                }
            }
            allQuestionsCount {
                difficulty
                count
            }
        }
    """
    
    PROBLEM_LIST_QUERY = """
        query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
            problemsetQuestionList: questionList(
                categorySlug: $categorySlug
                limit: $limit
                skip: $skip
                filters: $filters
            ) {
                total: totalNum
                questions: data {
                    titleSlug
                    title
                    difficulty
                    paidOnly: isPaidOnly
                    status
                }
            }
        }
    """
    
    def __init__(self, db_path: Path, auth: LeetCodeAuth | None = None):
        """Initialize sync service.
        
        Args:
            db_path: Path to SQLite database
            auth: LeetCode auth instance. If None, creates a new one.
        """
        self.db_path = db_path
        self.auth = auth or LeetCodeAuth()
        self._init_sync_tables()
    
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_sync_tables(self) -> None:
        """Initialize sync-related database tables."""
        with self._connect() as conn:
            conn.executescript("""
                -- Synced submissions from LeetCode
                CREATE TABLE IF NOT EXISTS leetcode_submissions (
                    id TEXT PRIMARY KEY,
                    problem_slug TEXT NOT NULL,
                    problem_title TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    language TEXT NOT NULL,
                    runtime TEXT,
                    memory TEXT,
                    synced_at DATETIME NOT NULL
                );
                
                -- Problem status (local + LeetCode)
                CREATE TABLE IF NOT EXISTS problem_status (
                    slug TEXT PRIMARY KEY,
                    title TEXT,
                    difficulty TEXT,
                    is_premium INTEGER DEFAULT 0,
                    solved_locally INTEGER DEFAULT 0,
                    solved_leetcode INTEGER DEFAULT 0,
                    last_submission_id TEXT,
                    last_synced DATETIME
                );
                
                -- Sync metadata
                CREATE TABLE IF NOT EXISTS sync_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                
                -- Queued submissions (for offline mode)
                CREATE TABLE IF NOT EXISTS submission_queue (
                    id INTEGER PRIMARY KEY,
                    problem_slug TEXT NOT NULL,
                    code TEXT NOT NULL,
                    language TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    status TEXT DEFAULT 'pending'
                );
                
                CREATE INDEX IF NOT EXISTS idx_submissions_problem 
                    ON leetcode_submissions(problem_slug);
                CREATE INDEX IF NOT EXISTS idx_submissions_timestamp 
                    ON leetcode_submissions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_problem_status_solved 
                    ON problem_status(solved_leetcode);
            """)
            conn.commit()
    
    def get_sync_meta(self, key: str) -> str | None:
        """Get a sync metadata value."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM sync_meta WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else None
    
    def set_sync_meta(self, key: str, value: str) -> None:
        """Set a sync metadata value."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_meta (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now().isoformat())
            )
            conn.commit()
    
    def get_last_sync_time(self) -> datetime | None:
        """Get the timestamp of the last successful sync."""
        value = self.get_sync_meta("last_sync_time")
        if value:
            return datetime.fromisoformat(value)
        return None
    
    async def sync(
        self,
        full: bool = False,
        progress_callback: Callable[[str], None] | None = None,
    ) -> SyncResult:
        """Sync submissions from LeetCode.
        
        Args:
            full: If True, do a full sync ignoring last sync time
            progress_callback: Optional callback for progress updates
            
        Returns:
            SyncResult with sync status and statistics
        """
        result = SyncResult(
            status=SyncStatus.SUCCESS,
            started_at=datetime.now(),
        )
        
        def log(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)
        
        try:
            # Check authentication
            if not await self.auth.is_authenticated():
                result.status = SyncStatus.NOT_AUTHENTICATED
                result.errors.append("Not authenticated. Run 'grind auth login' first.")
                result.completed_at = datetime.now()
                return result
            
            session = self.auth.get_session()
            if not session or not session.username:
                result.status = SyncStatus.NOT_AUTHENTICATED
                result.errors.append("No valid session found.")
                result.completed_at = datetime.now()
                return result
            
            username = session.username
            log(f"Syncing for user: {username}")
            
            # Get last sync timestamp for incremental sync
            last_sync = None if full else self.get_last_sync_time()
            if last_sync:
                log(f"Incremental sync since: {last_sync.isoformat()}")
            else:
                log("Full sync starting...")
            
            # Fetch submissions
            log("Fetching submissions...")
            submissions = await self._fetch_submissions(
                last_sync_timestamp=int(last_sync.timestamp()) if last_sync else None,
                progress_callback=log,
            )
            log(f"Found {len(submissions)} submissions")
            
            # Save submissions to database
            log("Saving submissions...")
            saved_count = self._save_submissions(submissions)
            result.submissions_synced = saved_count
            
            # Update problem status
            log("Updating problem status...")
            updated_count = self._update_problem_status_from_submissions()
            result.problems_updated = updated_count
            
            # Fetch and filter premium problems
            log("Fetching problem list...")
            await self._sync_problem_list(progress_callback=log)
            
            # Update last sync time
            self.set_sync_meta("last_sync_time", datetime.now().isoformat())
            
            result.status = SyncStatus.SUCCESS
            log("Sync completed successfully!")
            
        except SessionExpiredError:
            result.status = SyncStatus.NOT_AUTHENTICATED
            result.errors.append("Session expired. Please login again.")
        except AuthenticationError as e:
            result.status = SyncStatus.FAILED
            result.errors.append(f"Authentication error: {e}")
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(f"Sync failed: {e}")
        
        result.completed_at = datetime.now()
        return result
    
    async def _fetch_submissions(
        self,
        last_sync_timestamp: int | None = None,
        limit: int = 20,
        max_pages: int = 50,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch submissions from LeetCode.
        
        Args:
            last_sync_timestamp: Only fetch submissions after this timestamp
            limit: Number of submissions per page
            max_pages: Maximum number of pages to fetch
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of submission dictionaries
        """
        session = self.auth.get_session()
        if not session:
            return []
        
        all_submissions: list[dict[str, Any]] = []
        offset = 0
        
        for page in range(max_pages):
            result = await self.auth._graphql_request(
                session,
                self.SUBMISSIONS_QUERY,
                variables={"offset": offset, "limit": limit},
            )
            
            data = result.get("data", {}).get("submissionList", {})
            submissions = data.get("submissions", [])
            
            if not submissions:
                break
            
            # Filter by timestamp if doing incremental sync
            for sub in submissions:
                timestamp = int(sub.get("timestamp", 0))
                if last_sync_timestamp and timestamp <= last_sync_timestamp:
                    # We've reached submissions we already have
                    return all_submissions
                all_submissions.append(sub)
            
            if progress_callback:
                progress_callback(f"Fetched {len(all_submissions)} submissions...")
            
            # Check if there are more
            if not data.get("hasNext"):
                break
            
            offset += limit
        
        return all_submissions
    
    def _save_submissions(self, submissions: list[dict[str, Any]]) -> int:
        """Save submissions to database.
        
        Args:
            submissions: List of submission dictionaries from LeetCode
            
        Returns:
            Number of submissions saved
        """
        saved = 0
        now = datetime.now().isoformat()
        
        with self._connect() as conn:
            for sub in submissions:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO leetcode_submissions
                        (id, problem_slug, problem_title, timestamp, status, language, runtime, memory, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(sub.get("id")),
                            sub.get("titleSlug", ""),
                            sub.get("title", ""),
                            int(sub.get("timestamp", 0)),
                            sub.get("statusDisplay", ""),
                            sub.get("lang", ""),
                            sub.get("runtime"),
                            sub.get("memory"),
                            now,
                        )
                    )
                    saved += 1
                except Exception:
                    pass
            conn.commit()
        
        return saved
    
    def _update_problem_status_from_submissions(self) -> int:
        """Update problem_status table based on submissions.
        
        Returns:
            Number of problems updated
        """
        with self._connect() as conn:
            # Get all problems with accepted submissions
            rows = conn.execute("""
                SELECT DISTINCT problem_slug, problem_title,
                    MAX(id) as last_submission_id
                FROM leetcode_submissions
                WHERE status = 'Accepted'
                GROUP BY problem_slug
            """).fetchall()
            
            updated = 0
            now = datetime.now().isoformat()
            
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO problem_status (slug, title, solved_leetcode, last_submission_id, last_synced)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        title = COALESCE(excluded.title, title),
                        solved_leetcode = 1,
                        last_submission_id = excluded.last_submission_id,
                        last_synced = excluded.last_synced
                    """,
                    (row["problem_slug"], row["problem_title"], row["last_submission_id"], now)
                )
                updated += 1
            
            conn.commit()
        
        return updated
    
    async def _sync_problem_list(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> int:
        """Sync problem list to identify premium problems.
        
        Returns:
            Number of problems updated
        """
        session = self.auth.get_session()
        if not session:
            return 0
        
        updated = 0
        skip = 0
        limit = 100
        
        while True:
            try:
                result = await self.auth._graphql_request(
                    session,
                    self.PROBLEM_LIST_QUERY,
                    variables={
                        "categorySlug": "",
                        "limit": limit,
                        "skip": skip,
                        "filters": {},
                    },
                )
                
                data = result.get("data", {}).get("problemsetQuestionList", {})
                questions = data.get("questions", [])
                
                if not questions:
                    break
                
                with self._connect() as conn:
                    for q in questions:
                        conn.execute(
                            """
                            INSERT INTO problem_status (slug, title, difficulty, is_premium)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(slug) DO UPDATE SET
                                title = COALESCE(excluded.title, title),
                                difficulty = COALESCE(excluded.difficulty, difficulty),
                                is_premium = excluded.is_premium
                            """,
                            (
                                q.get("titleSlug"),
                                q.get("title"),
                                q.get("difficulty"),
                                1 if q.get("paidOnly") else 0,
                            )
                        )
                        updated += 1
                    conn.commit()
                
                if progress_callback:
                    progress_callback(f"Synced {updated} problems...")
                
                if len(questions) < limit:
                    break
                
                skip += limit
                
            except Exception:
                break
        
        return updated
    
    def get_problem_status(self, slug: str) -> ProblemStatus | None:
        """Get status for a specific problem."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM problem_status WHERE slug = ?",
                (slug,)
            ).fetchone()
            
            if not row:
                return None
            
            return ProblemStatus(
                slug=row["slug"],
                title=row["title"],
                difficulty=row["difficulty"],
                is_premium=bool(row["is_premium"]),
                solved_locally=bool(row["solved_locally"]),
                solved_leetcode=bool(row["solved_leetcode"]),
                last_submission_id=row["last_submission_id"],
                last_synced=datetime.fromisoformat(row["last_synced"]) if row["last_synced"] else None,
            )
    
    def get_solved_problems(self, include_premium: bool = False) -> list[ProblemStatus]:
        """Get all solved problems.
        
        Args:
            include_premium: Whether to include premium-only problems
            
        Returns:
            List of solved problem statuses
        """
        with self._connect() as conn:
            query = """
                SELECT * FROM problem_status
                WHERE (solved_leetcode = 1 OR solved_locally = 1)
            """
            if not include_premium:
                query += " AND is_premium = 0"
            query += " ORDER BY title"
            
            rows = conn.execute(query).fetchall()
            return [self._row_to_problem_status(row) for row in rows]
    
    def get_unsolved_problems(self, include_premium: bool = False) -> list[ProblemStatus]:
        """Get all unsolved problems.
        
        Args:
            include_premium: Whether to include premium-only problems
            
        Returns:
            List of unsolved problem statuses
        """
        with self._connect() as conn:
            query = """
                SELECT * FROM problem_status
                WHERE solved_leetcode = 0 AND solved_locally = 0
            """
            if not include_premium:
                query += " AND is_premium = 0"
            query += " ORDER BY title"
            
            rows = conn.execute(query).fetchall()
            return [self._row_to_problem_status(row) for row in rows]
    
    def get_submissions(self, problem_slug: str | None = None, limit: int = 50) -> list[LeetCodeSubmission]:
        """Get synced submissions.
        
        Args:
            problem_slug: Filter by problem slug
            limit: Maximum number of submissions to return
            
        Returns:
            List of submissions
        """
        with self._connect() as conn:
            if problem_slug:
                rows = conn.execute(
                    """
                    SELECT * FROM leetcode_submissions
                    WHERE problem_slug = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (problem_slug, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM leetcode_submissions
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,)
                ).fetchall()
            
            return [self._row_to_submission(row) for row in rows]
    
    def _row_to_problem_status(self, row: sqlite3.Row) -> ProblemStatus:
        """Convert database row to ProblemStatus."""
        return ProblemStatus(
            slug=row["slug"],
            title=row["title"],
            difficulty=row["difficulty"],
            is_premium=bool(row["is_premium"]),
            solved_locally=bool(row["solved_locally"]),
            solved_leetcode=bool(row["solved_leetcode"]),
            last_submission_id=row["last_submission_id"],
            last_synced=datetime.fromisoformat(row["last_synced"]) if row["last_synced"] else None,
        )
    
    def _row_to_submission(self, row: sqlite3.Row) -> LeetCodeSubmission:
        """Convert database row to LeetCodeSubmission."""
        return LeetCodeSubmission(
            id=row["id"],
            problem_slug=row["problem_slug"],
            problem_title=row["problem_title"],
            timestamp=row["timestamp"],
            status=row["status"],
            language=row["language"],
            runtime=row["runtime"],
            memory=row["memory"],
            synced_at=datetime.fromisoformat(row["synced_at"]),
        )
    
    def mark_problem_solved_locally(self, slug: str) -> None:
        """Mark a problem as solved locally."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO problem_status (slug, solved_locally, last_synced)
                VALUES (?, 1, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    solved_locally = 1,
                    last_synced = excluded.last_synced
                """,
                (slug, datetime.now().isoformat())
            )
            conn.commit()
    
    def get_sync_stats(self) -> dict[str, Any]:
        """Get sync statistics."""
        with self._connect() as conn:
            total_submissions = conn.execute(
                "SELECT COUNT(*) FROM leetcode_submissions"
            ).fetchone()[0]
            
            accepted_submissions = conn.execute(
                "SELECT COUNT(*) FROM leetcode_submissions WHERE status = 'Accepted'"
            ).fetchone()[0]
            
            solved_leetcode = conn.execute(
                "SELECT COUNT(*) FROM problem_status WHERE solved_leetcode = 1"
            ).fetchone()[0]
            
            solved_locally = conn.execute(
                "SELECT COUNT(*) FROM problem_status WHERE solved_locally = 1"
            ).fetchone()[0]
            
            premium_count = conn.execute(
                "SELECT COUNT(*) FROM problem_status WHERE is_premium = 1"
            ).fetchone()[0]
            
            last_sync = self.get_last_sync_time()
            
            return {
                "total_submissions": total_submissions,
                "accepted_submissions": accepted_submissions,
                "solved_leetcode": solved_leetcode,
                "solved_locally": solved_locally,
                "premium_problems": premium_count,
                "last_sync": last_sync,
            }
    
    # Submission queue for offline mode
    def queue_submission(self, problem_slug: str, code: str, language: str) -> int:
        """Queue a submission for later sync.
        
        Args:
            problem_slug: Problem to submit
            code: Solution code
            language: Programming language
            
        Returns:
            Queue entry ID
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO submission_queue (problem_slug, code, language, created_at, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (problem_slug, code, language, datetime.now().isoformat())
            )
            conn.commit()
            return cursor.lastrowid or 0
    
    def get_pending_submissions(self) -> list[dict[str, Any]]:
        """Get all pending queued submissions."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM submission_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]
    
    def mark_queue_submitted(self, queue_id: int, submission_id: str | None = None) -> None:
        """Mark a queued submission as submitted."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE submission_queue
                SET status = 'submitted'
                WHERE id = ?
                """,
                (queue_id,)
            )
            conn.commit()
