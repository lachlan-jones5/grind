"""Tests for the sync module."""

import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grind.sync.models import LeetCodeSubmission, ProblemStatus, SyncMeta
from grind.sync.service import SyncService, SyncResult, SyncStatus
from grind.auth.session import Session, SessionManager


# =============================================================================
# Model Tests
# =============================================================================

class TestLeetCodeSubmission:
    """Tests for LeetCodeSubmission model."""

    def test_submission_creation(self):
        """Test creating a submission."""
        sub = LeetCodeSubmission(
            id="123",
            problem_slug="two-sum",
            problem_title="Two Sum",
            timestamp=1704067200,
            status="Accepted",
            language="python3",
            synced_at=datetime.now(),
        )
        assert sub.id == "123"
        assert sub.problem_slug == "two-sum"
        assert sub.status == "Accepted"

    def test_submission_with_runtime_memory(self):
        """Test submission with runtime and memory."""
        sub = LeetCodeSubmission(
            id="123",
            problem_slug="two-sum",
            problem_title="Two Sum",
            timestamp=1704067200,
            status="Accepted",
            language="python3",
            runtime="50 ms",
            memory="16.5 MB",
            synced_at=datetime.now(),
        )
        assert sub.runtime == "50 ms"
        assert sub.memory == "16.5 MB"

    def test_submitted_at_property(self):
        """Test submitted_at converts timestamp to datetime."""
        ts = 1704067200
        sub = LeetCodeSubmission(
            id="123",
            problem_slug="two-sum",
            problem_title="Two Sum",
            timestamp=ts,
            status="Accepted",
            language="python3",
            synced_at=datetime.now(),
        )
        expected = datetime.fromtimestamp(ts)
        assert sub.submitted_at == expected

    def test_is_accepted_true(self):
        """Test is_accepted returns True for Accepted status."""
        sub = LeetCodeSubmission(
            id="123",
            problem_slug="two-sum",
            problem_title="Two Sum",
            timestamp=1704067200,
            status="Accepted",
            language="python3",
            synced_at=datetime.now(),
        )
        assert sub.is_accepted is True

    def test_is_accepted_false(self):
        """Test is_accepted returns False for other statuses."""
        for status in ["Wrong Answer", "Time Limit Exceeded", "Runtime Error"]:
            sub = LeetCodeSubmission(
                id="123",
                problem_slug="two-sum",
                problem_title="Two Sum",
                timestamp=1704067200,
                status=status,
                language="python3",
                synced_at=datetime.now(),
            )
            assert sub.is_accepted is False


class TestProblemStatus:
    """Tests for ProblemStatus model."""

    def test_problem_status_creation(self):
        """Test creating a problem status."""
        status = ProblemStatus(slug="two-sum")
        assert status.slug == "two-sum"
        assert status.is_premium is False
        assert status.solved_locally is False
        assert status.solved_leetcode is False

    def test_problem_status_with_all_fields(self):
        """Test problem status with all fields."""
        status = ProblemStatus(
            slug="two-sum",
            title="Two Sum",
            difficulty="Easy",
            is_premium=False,
            solved_locally=True,
            solved_leetcode=True,
        )
        assert status.title == "Two Sum"
        assert status.difficulty == "Easy"

    def test_is_solved_when_solved_locally(self):
        """Test is_solved returns True when solved locally."""
        status = ProblemStatus(slug="two-sum", solved_locally=True)
        assert status.is_solved is True

    def test_is_solved_when_solved_leetcode(self):
        """Test is_solved returns True when solved on LeetCode."""
        status = ProblemStatus(slug="two-sum", solved_leetcode=True)
        assert status.is_solved is True

    def test_is_solved_when_not_solved(self):
        """Test is_solved returns False when not solved."""
        status = ProblemStatus(slug="two-sum")
        assert status.is_solved is False


class TestSyncMeta:
    """Tests for SyncMeta model."""

    def test_sync_meta_creation(self):
        """Test creating sync meta."""
        meta = SyncMeta(key="last_sync", value="2024-01-01", updated_at=datetime.now())
        assert meta.key == "last_sync"
        assert meta.value == "2024-01-01"


# =============================================================================
# SyncResult Tests
# =============================================================================

class TestSyncResult:
    """Tests for SyncResult model."""

    def test_sync_result_creation(self):
        """Test creating a sync result."""
        result = SyncResult(
            status=SyncStatus.SUCCESS,
            started_at=datetime.now(),
        )
        assert result.status == SyncStatus.SUCCESS
        assert result.submissions_synced == 0

    def test_sync_result_with_stats(self):
        """Test sync result with statistics."""
        result = SyncResult(
            status=SyncStatus.SUCCESS,
            submissions_synced=100,
            problems_updated=50,
            started_at=datetime.now(),
        )
        assert result.submissions_synced == 100
        assert result.problems_updated == 50

    def test_duration_seconds_none_when_not_completed(self):
        """Test duration is None when not completed."""
        result = SyncResult(
            status=SyncStatus.SUCCESS,
            started_at=datetime.now(),
        )
        assert result.duration_seconds is None

    def test_duration_seconds_calculated(self):
        """Test duration is calculated when completed."""
        start = datetime.now()
        result = SyncResult(
            status=SyncStatus.SUCCESS,
            started_at=start,
            completed_at=datetime.now(),
        )
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0


class TestSyncStatus:
    """Tests for SyncStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        assert SyncStatus.SUCCESS
        assert SyncStatus.PARTIAL
        assert SyncStatus.FAILED
        assert SyncStatus.NOT_AUTHENTICATED
        assert SyncStatus.RATE_LIMITED

    def test_status_values(self):
        """Test status values."""
        assert SyncStatus.SUCCESS.value == "success"
        assert SyncStatus.FAILED.value == "failed"


# =============================================================================
# SyncService Database Tests
# =============================================================================

class TestSyncServiceDatabase:
    """Tests for SyncService database operations."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sync_service(self, temp_dir):
        """Create a sync service with test database."""
        db_path = temp_dir / "test.db"
        return SyncService(db_path)

    def test_init_creates_tables(self, sync_service):
        """Test initialization creates database tables."""
        with sync_service._connect() as conn:
            # Check tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            
            assert "leetcode_submissions" in table_names
            assert "problem_status" in table_names
            assert "sync_meta" in table_names
            assert "submission_queue" in table_names

    def test_get_set_sync_meta(self, sync_service):
        """Test get/set sync metadata."""
        sync_service.set_sync_meta("test_key", "test_value")
        result = sync_service.get_sync_meta("test_key")
        assert result == "test_value"

    def test_get_sync_meta_returns_none_for_missing(self, sync_service):
        """Test get_sync_meta returns None for missing key."""
        result = sync_service.get_sync_meta("nonexistent")
        assert result is None

    def test_get_last_sync_time_none_initially(self, sync_service):
        """Test last sync time is None initially."""
        result = sync_service.get_last_sync_time()
        assert result is None

    def test_get_last_sync_time_after_set(self, sync_service):
        """Test last sync time after setting."""
        now = datetime.now()
        sync_service.set_sync_meta("last_sync_time", now.isoformat())
        result = sync_service.get_last_sync_time()
        assert result is not None
        # Allow 1 second tolerance
        assert abs((result - now).total_seconds()) < 1


class TestSyncServiceSubmissions:
    """Tests for SyncService submission handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sync_service(self, temp_dir):
        """Create a sync service with test database."""
        db_path = temp_dir / "test.db"
        return SyncService(db_path)

    def test_save_submissions(self, sync_service):
        """Test saving submissions."""
        submissions = [
            {
                "id": "123",
                "titleSlug": "two-sum",
                "title": "Two Sum",
                "timestamp": 1704067200,
                "statusDisplay": "Accepted",
                "lang": "python3",
                "runtime": "50 ms",
                "memory": "16.5 MB",
            },
            {
                "id": "124",
                "titleSlug": "add-two-numbers",
                "title": "Add Two Numbers",
                "timestamp": 1704067300,
                "statusDisplay": "Wrong Answer",
                "lang": "cpp",
            },
        ]
        
        count = sync_service._save_submissions(submissions)
        assert count == 2

    def test_save_submissions_updates_existing(self, sync_service):
        """Test saving submissions updates existing."""
        submission = {
            "id": "123",
            "titleSlug": "two-sum",
            "title": "Two Sum",
            "timestamp": 1704067200,
            "statusDisplay": "Accepted",
            "lang": "python3",
        }
        
        sync_service._save_submissions([submission])
        
        # Update the same submission
        submission["runtime"] = "50 ms"
        sync_service._save_submissions([submission])
        
        # Should still be only 1
        subs = sync_service.get_submissions()
        assert len(subs) == 1
        assert subs[0].runtime == "50 ms"

    def test_get_submissions(self, sync_service):
        """Test getting submissions."""
        submissions = [
            {
                "id": "123",
                "titleSlug": "two-sum",
                "title": "Two Sum",
                "timestamp": 1704067200,
                "statusDisplay": "Accepted",
                "lang": "python3",
            },
        ]
        sync_service._save_submissions(submissions)
        
        result = sync_service.get_submissions()
        assert len(result) == 1
        assert result[0].problem_slug == "two-sum"

    def test_get_submissions_by_problem(self, sync_service):
        """Test getting submissions filtered by problem."""
        submissions = [
            {"id": "1", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 1, "statusDisplay": "Accepted", "lang": "python3"},
            {"id": "2", "titleSlug": "add-two-numbers", "title": "Add Two Numbers", "timestamp": 2, "statusDisplay": "Accepted", "lang": "python3"},
            {"id": "3", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 3, "statusDisplay": "Accepted", "lang": "cpp"},
        ]
        sync_service._save_submissions(submissions)
        
        result = sync_service.get_submissions(problem_slug="two-sum")
        assert len(result) == 2
        for sub in result:
            assert sub.problem_slug == "two-sum"


class TestSyncServiceProblemStatus:
    """Tests for SyncService problem status handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sync_service(self, temp_dir):
        """Create a sync service with test database."""
        db_path = temp_dir / "test.db"
        return SyncService(db_path)

    def test_update_problem_status_from_submissions(self, sync_service):
        """Test updating problem status from submissions."""
        submissions = [
            {"id": "1", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 1, "statusDisplay": "Accepted", "lang": "python3"},
            {"id": "2", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 2, "statusDisplay": "Accepted", "lang": "cpp"},
            {"id": "3", "titleSlug": "add-two-numbers", "title": "Add Two Numbers", "timestamp": 3, "statusDisplay": "Wrong Answer", "lang": "python3"},
        ]
        sync_service._save_submissions(submissions)
        
        count = sync_service._update_problem_status_from_submissions()
        assert count == 1  # Only two-sum has Accepted status

    def test_get_problem_status(self, sync_service):
        """Test getting problem status."""
        submissions = [
            {"id": "1", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 1, "statusDisplay": "Accepted", "lang": "python3"},
        ]
        sync_service._save_submissions(submissions)
        sync_service._update_problem_status_from_submissions()
        
        status = sync_service.get_problem_status("two-sum")
        assert status is not None
        assert status.solved_leetcode is True

    def test_get_problem_status_returns_none_for_missing(self, sync_service):
        """Test get_problem_status returns None for missing problem."""
        status = sync_service.get_problem_status("nonexistent")
        assert status is None

    def test_mark_problem_solved_locally(self, sync_service):
        """Test marking a problem as solved locally."""
        sync_service.mark_problem_solved_locally("two-sum")
        
        status = sync_service.get_problem_status("two-sum")
        assert status is not None
        assert status.solved_locally is True

    def test_get_solved_problems(self, sync_service):
        """Test getting solved problems."""
        submissions = [
            {"id": "1", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 1, "statusDisplay": "Accepted", "lang": "python3"},
        ]
        sync_service._save_submissions(submissions)
        sync_service._update_problem_status_from_submissions()
        sync_service.mark_problem_solved_locally("add-two-numbers")
        
        solved = sync_service.get_solved_problems()
        assert len(solved) == 2

    def test_get_solved_problems_excludes_premium(self, sync_service):
        """Test getting solved problems excludes premium by default."""
        # Add a premium solved problem
        with sync_service._connect() as conn:
            conn.execute(
                "INSERT INTO problem_status (slug, title, is_premium, solved_leetcode) VALUES (?, ?, ?, ?)",
                ("premium-problem", "Premium Problem", 1, 1)
            )
            conn.execute(
                "INSERT INTO problem_status (slug, title, is_premium, solved_leetcode) VALUES (?, ?, ?, ?)",
                ("free-problem", "Free Problem", 0, 1)
            )
            conn.commit()
        
        solved = sync_service.get_solved_problems(include_premium=False)
        assert len(solved) == 1
        assert solved[0].slug == "free-problem"

    def test_get_solved_problems_includes_premium(self, sync_service):
        """Test getting solved problems can include premium."""
        with sync_service._connect() as conn:
            conn.execute(
                "INSERT INTO problem_status (slug, title, is_premium, solved_leetcode) VALUES (?, ?, ?, ?)",
                ("premium-problem", "Premium Problem", 1, 1)
            )
            conn.commit()
        
        solved = sync_service.get_solved_problems(include_premium=True)
        assert len(solved) == 1

    def test_get_unsolved_problems(self, sync_service):
        """Test getting unsolved problems."""
        with sync_service._connect() as conn:
            conn.execute(
                "INSERT INTO problem_status (slug, title, solved_leetcode) VALUES (?, ?, ?)",
                ("solved", "Solved", 1)
            )
            conn.execute(
                "INSERT INTO problem_status (slug, title, solved_leetcode) VALUES (?, ?, ?)",
                ("unsolved", "Unsolved", 0)
            )
            conn.commit()
        
        unsolved = sync_service.get_unsolved_problems()
        assert len(unsolved) == 1
        assert unsolved[0].slug == "unsolved"


class TestSyncServiceQueue:
    """Tests for SyncService submission queue."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sync_service(self, temp_dir):
        """Create a sync service with test database."""
        db_path = temp_dir / "test.db"
        return SyncService(db_path)

    def test_queue_submission(self, sync_service):
        """Test queuing a submission."""
        queue_id = sync_service.queue_submission(
            problem_slug="two-sum",
            code="def solution(): pass",
            language="python3"
        )
        assert queue_id > 0

    def test_get_pending_submissions(self, sync_service):
        """Test getting pending submissions."""
        sync_service.queue_submission("two-sum", "code1", "python3")
        sync_service.queue_submission("add-two-numbers", "code2", "cpp")
        
        pending = sync_service.get_pending_submissions()
        assert len(pending) == 2

    def test_mark_queue_submitted(self, sync_service):
        """Test marking queued submission as submitted."""
        queue_id = sync_service.queue_submission("two-sum", "code", "python3")
        sync_service.mark_queue_submitted(queue_id)
        
        pending = sync_service.get_pending_submissions()
        assert len(pending) == 0


class TestSyncServiceStats:
    """Tests for SyncService statistics."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sync_service(self, temp_dir):
        """Create a sync service with test database."""
        db_path = temp_dir / "test.db"
        return SyncService(db_path)

    def test_get_sync_stats_empty(self, sync_service):
        """Test getting stats when empty."""
        stats = sync_service.get_sync_stats()
        assert stats["total_submissions"] == 0
        assert stats["accepted_submissions"] == 0
        assert stats["solved_leetcode"] == 0
        assert stats["solved_locally"] == 0
        assert stats["premium_problems"] == 0
        assert stats["last_sync"] is None

    def test_get_sync_stats_with_data(self, sync_service):
        """Test getting stats with data."""
        submissions = [
            {"id": "1", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 1, "statusDisplay": "Accepted", "lang": "python3"},
            {"id": "2", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 2, "statusDisplay": "Wrong Answer", "lang": "python3"},
        ]
        sync_service._save_submissions(submissions)
        sync_service._update_problem_status_from_submissions()
        
        stats = sync_service.get_sync_stats()
        assert stats["total_submissions"] == 2
        assert stats["accepted_submissions"] == 1
        assert stats["solved_leetcode"] == 1


# =============================================================================
# SyncService Sync Tests
# =============================================================================

class TestSyncServiceSync:
    """Tests for SyncService sync operation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sync_service(self, temp_dir):
        """Create a sync service with test database."""
        db_path = temp_dir / "test.db"
        # Create with mocked auth
        auth = MagicMock()
        return SyncService(db_path, auth=auth)

    @pytest.mark.asyncio
    async def test_sync_not_authenticated(self, sync_service):
        """Test sync returns NOT_AUTHENTICATED when not logged in."""
        sync_service.auth.is_authenticated = AsyncMock(return_value=False)
        
        result = await sync_service.sync()
        assert result.status == SyncStatus.NOT_AUTHENTICATED

    @pytest.mark.asyncio
    async def test_sync_no_session(self, sync_service):
        """Test sync returns NOT_AUTHENTICATED when no session."""
        sync_service.auth.is_authenticated = AsyncMock(return_value=True)
        sync_service.auth.get_session = MagicMock(return_value=None)
        
        result = await sync_service.sync()
        assert result.status == SyncStatus.NOT_AUTHENTICATED

    @pytest.mark.asyncio
    async def test_sync_success(self, sync_service):
        """Test successful sync."""
        # Mock auth
        session = Session(
            leetcode_session="test",
            csrf_token="csrf",
            username="testuser"
        )
        sync_service.auth.is_authenticated = AsyncMock(return_value=True)
        sync_service.auth.get_session = MagicMock(return_value=session)
        
        # Mock GraphQL request
        sync_service.auth._graphql_request = AsyncMock(side_effect=[
            # Submissions query
            {
                "data": {
                    "submissionList": {
                        "hasNext": False,
                        "submissions": [
                            {"id": "1", "titleSlug": "two-sum", "title": "Two Sum", "timestamp": 1704067200, "statusDisplay": "Accepted", "lang": "python3"},
                        ]
                    }
                }
            },
            # Problem list query
            {
                "data": {
                    "problemsetQuestionList": {
                        "questions": []
                    }
                }
            },
        ])
        
        result = await sync_service.sync()
        assert result.status == SyncStatus.SUCCESS
        assert result.submissions_synced == 1

    @pytest.mark.asyncio
    async def test_sync_with_progress_callback(self, sync_service):
        """Test sync calls progress callback."""
        session = Session(leetcode_session="test", csrf_token="csrf", username="testuser")
        sync_service.auth.is_authenticated = AsyncMock(return_value=True)
        sync_service.auth.get_session = MagicMock(return_value=session)
        sync_service.auth._graphql_request = AsyncMock(return_value={
            "data": {"submissionList": {"hasNext": False, "submissions": []}}
        })
        
        messages = []
        await sync_service.sync(progress_callback=messages.append)
        
        assert len(messages) > 0
        assert any("Syncing" in msg for msg in messages)
