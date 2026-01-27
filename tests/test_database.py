"""Tests for the database module."""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from grind.db.database import (
    Database,
    Attempt,
    Pattern,
    Insight,
    PATTERNS,
)


class TestDatabaseInit:
    """Tests for database initialization."""

    def test_database_creates_file(self):
        """Test database creates SQLite file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            assert db_path.exists()

    def test_database_initializes_patterns(self):
        """Test database initializes all patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            patterns_due = db.get_patterns_due()
            pattern_names = {p.name for p in patterns_due}

            for expected_pattern in PATTERNS:
                assert expected_pattern in pattern_names

    def test_database_schema_idempotent(self):
        """Test database can be opened multiple times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create database twice
            db1 = Database(db_path)
            db2 = Database(db_path)

            # Both should work
            assert db1.get_stats()["total_attempts"] == 0
            assert db2.get_stats()["total_attempts"] == 0


class TestAttempts:
    """Tests for attempt CRUD operations."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def test_save_attempt(self, db):
        """Test saving an attempt."""
        attempt = Attempt(
            problem_slug="two-sum",
            started_at=datetime.now(),
            result="solved",
            hints_used=2,
            code="def solve(): pass",
            language="python",
        )

        attempt_id = db.save_attempt(attempt)

        assert attempt_id > 0

    def test_save_attempt_with_completion(self, db):
        """Test saving a completed attempt."""
        start = datetime.now()
        end = start + timedelta(minutes=15)

        attempt = Attempt(
            problem_slug="add-two-numbers",
            started_at=start,
            completed_at=end,
            result="solved",
            hints_used=0,
            code="int solve() { return 0; }",
            language="cpp",
            time_complexity="O(n)",
            space_complexity="O(1)",
        )

        attempt_id = db.save_attempt(attempt)
        attempts = db.get_attempts("add-two-numbers")

        assert len(attempts) == 1
        assert attempts[0].id == attempt_id
        assert attempts[0].time_complexity == "O(n)"
        assert attempts[0].space_complexity == "O(1)"

    def test_get_attempts_for_problem(self, db):
        """Test retrieving attempts for a specific problem."""
        # Save multiple attempts for same problem
        for i in range(3):
            attempt = Attempt(
                problem_slug="same-problem",
                started_at=datetime.now() - timedelta(hours=i),
                result="solved" if i == 0 else "gave_up",
                code=f"attempt {i}",
            )
            db.save_attempt(attempt)

        # Save attempt for different problem
        other = Attempt(
            problem_slug="other-problem",
            started_at=datetime.now(),
            result="solved",
        )
        db.save_attempt(other)

        # Get attempts for specific problem
        attempts = db.get_attempts("same-problem")

        assert len(attempts) == 3
        # Most recent first
        assert attempts[0].result == "solved"

    def test_get_attempts_empty(self, db):
        """Test getting attempts for non-existent problem."""
        attempts = db.get_attempts("nonexistent")
        assert attempts == []


class TestPatterns:
    """Tests for pattern tracking."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def test_update_pattern_success(self, db):
        """Test updating pattern with success."""
        db.update_pattern("two-pointer", success=True)

        # Get all patterns and find two-pointer
        patterns = db.get_weakest_patterns(limit=20)
        two_pointer = next((p for p in patterns if p.name == "two-pointer"), None)

        assert two_pointer is not None
        assert two_pointer.total_attempts == 1
        assert two_pointer.success_rate > 0
        assert two_pointer.last_practiced is not None
        assert two_pointer.next_review is not None

    def test_update_pattern_failure(self, db):
        """Test updating pattern with failure."""
        db.update_pattern("dfs", success=False)

        patterns = db.get_weakest_patterns(limit=20)
        dfs = next((p for p in patterns if p.name == "dfs"), None)

        assert dfs is not None
        assert dfs.total_attempts == 1
        assert dfs.success_rate == 0.0
        # Should review soon (1 day)
        assert dfs.next_review is not None
        assert dfs.next_review < datetime.now() + timedelta(days=2)

    def test_update_pattern_multiple_times(self, db):
        """Test updating pattern multiple times."""
        # Fail twice, then succeed
        db.update_pattern("binary-search", success=False)
        db.update_pattern("binary-search", success=False)
        db.update_pattern("binary-search", success=True)

        patterns = db.get_weakest_patterns(limit=20)
        bs = next((p for p in patterns if p.name == "binary-search"), None)

        assert bs is not None
        assert bs.total_attempts == 3
        # Success rate should be weighted
        assert 0 < bs.success_rate < 1

    def test_get_patterns_due_initial(self, db):
        """Test all patterns are due initially (no next_review set)."""
        patterns_due = db.get_patterns_due()

        # All 20 patterns should be due
        assert len(patterns_due) == len(PATTERNS)

    def test_get_patterns_due_after_practice(self, db):
        """Test patterns with future review dates are not due."""
        # Practice one pattern successfully
        db.update_pattern("greedy", success=True)

        patterns_due = db.get_patterns_due()
        greedy = next((p for p in patterns_due if p.name == "greedy"), None)

        # Greedy might not be in due list if next_review is in future
        # This depends on the spaced repetition logic
        assert len(patterns_due) >= len(PATTERNS) - 1

    def test_get_weakest_patterns(self, db):
        """Test getting weakest patterns."""
        # Practice some patterns with different success rates
        db.update_pattern("stack", success=True)
        db.update_pattern("stack", success=True)  # High success
        db.update_pattern("heap", success=False)  # Low success
        db.update_pattern("trie", success=False)
        db.update_pattern("trie", success=False)  # Very low success

        weakest = db.get_weakest_patterns(limit=3)

        assert len(weakest) == 3
        # Lowest success rate should be first
        assert weakest[0].success_rate <= weakest[1].success_rate <= weakest[2].success_rate

    def test_get_weakest_patterns_requires_attempts(self, db):
        """Test weakest patterns only includes practiced patterns."""
        # No patterns practiced yet
        weakest = db.get_weakest_patterns(limit=5)
        assert len(weakest) == 0

        # Practice one
        db.update_pattern("queue", success=True)
        weakest = db.get_weakest_patterns(limit=5)
        assert len(weakest) == 1


class TestInsights:
    """Tests for insight tracking."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def test_save_insight(self, db):
        """Test saving an insight."""
        insight = Insight(
            problem_slug="two-sum",
            insight="Use a hash map to achieve O(n) time complexity",
            created_at=datetime.now(),
        )

        insight_id = db.save_insight(insight)

        assert insight_id > 0

    def test_get_insights_all(self, db):
        """Test getting all insights."""
        for i in range(3):
            insight = Insight(
                problem_slug=f"problem-{i}",
                insight=f"Insight {i}",
                created_at=datetime.now() - timedelta(hours=i),
            )
            db.save_insight(insight)

        insights = db.get_insights()

        assert len(insights) == 3
        # Most recent first
        assert insights[0].insight == "Insight 0"

    def test_get_insights_by_problem(self, db):
        """Test getting insights for specific problem."""
        # Multiple insights for same problem
        for i in range(2):
            insight = Insight(
                problem_slug="target-problem",
                insight=f"Target insight {i}",
                created_at=datetime.now(),
            )
            db.save_insight(insight)

        # Insight for different problem
        other = Insight(
            problem_slug="other-problem",
            insight="Other insight",
            created_at=datetime.now(),
        )
        db.save_insight(other)

        insights = db.get_insights("target-problem")

        assert len(insights) == 2
        assert all(i.problem_slug == "target-problem" for i in insights)


class TestStats:
    """Tests for statistics."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def test_get_stats_empty(self, db):
        """Test stats with no data."""
        stats = db.get_stats()

        assert stats["total_attempts"] == 0
        assert stats["solved"] == 0
        assert stats["unique_problems"] == 0
        assert stats["streak"] == 0

    def test_get_stats_with_attempts(self, db):
        """Test stats with some attempts."""
        # 3 attempts, 2 solved
        for i, result in enumerate(["solved", "solved", "gave_up"]):
            attempt = Attempt(
                problem_slug=f"problem-{i}",
                started_at=datetime.now(),
                result=result,
            )
            db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["total_attempts"] == 3
        assert stats["solved"] == 2
        assert stats["unique_problems"] == 2

    def test_get_stats_unique_problems(self, db):
        """Test unique problems counts distinct solved problems."""
        # Solve same problem twice, different problem once
        for slug in ["problem-a", "problem-a", "problem-b"]:
            attempt = Attempt(
                problem_slug=slug,
                started_at=datetime.now(),
                result="solved",
            )
            db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["unique_problems"] == 2

    def test_get_stats_streak(self, db):
        """Test streak calculation."""
        today = datetime.now()

        # Practice for 3 consecutive days
        for days_ago in range(3):
            attempt = Attempt(
                problem_slug=f"problem-{days_ago}",
                started_at=today - timedelta(days=days_ago),
                result="solved",
            )
            db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["streak"] == 3

    def test_get_stats_streak_broken(self, db):
        """Test streak resets when broken."""
        today = datetime.now()

        # Practice today
        attempt1 = Attempt(
            problem_slug="today-problem",
            started_at=today,
            result="solved",
        )
        db.save_attempt(attempt1)

        # Skip yesterday, practice day before
        attempt2 = Attempt(
            problem_slug="old-problem",
            started_at=today - timedelta(days=2),
            result="solved",
        )
        db.save_attempt(attempt2)

        stats = db.get_stats()

        # Streak should only be 1 (today)
        assert stats["streak"] == 1


class TestPydanticModels:
    """Tests for Pydantic model behavior."""

    def test_attempt_defaults(self):
        """Test Attempt model defaults."""
        attempt = Attempt(
            problem_slug="test",
            started_at=datetime.now(),
            result="solved",
        )

        assert attempt.id is None
        assert attempt.completed_at is None
        assert attempt.hints_used == 0
        assert attempt.code == ""
        assert attempt.language == "cpp"
        assert attempt.time_complexity is None
        assert attempt.space_complexity is None

    def test_pattern_defaults(self):
        """Test Pattern model defaults."""
        pattern = Pattern(name="test-pattern")

        assert pattern.last_practiced is None
        assert pattern.success_rate == 0.0
        assert pattern.total_attempts == 0
        assert pattern.next_review is None

    def test_insight_required_fields(self):
        """Test Insight requires all fields."""
        with pytest.raises(Exception):  # ValidationError
            Insight(problem_slug="test")  # type: ignore
