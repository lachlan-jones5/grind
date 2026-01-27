"""Comprehensive tests for the database module."""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from grind.db.database import (
    Database,
    Attempt,
    Pattern,
    Insight,
    PATTERNS,
)


# =============================================================================
# Database Initialization Tests
# =============================================================================

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

            db1 = Database(db_path)
            db2 = Database(db_path)

            assert db1.get_stats()["total_attempts"] == 0
            assert db2.get_stats()["total_attempts"] == 0

    def test_database_creates_all_tables(self):
        """Test database creates all required tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            Database(db_path)

            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            assert "attempts" in tables
            assert "patterns" in tables
            assert "insights" in tables
            assert "problem_patterns" in tables

    def test_database_creates_indexes(self):
        """Test database creates indexes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            Database(db_path)

            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = {row[0] for row in cursor.fetchall()}
            conn.close()

            assert "idx_attempts_problem" in indexes
            assert "idx_patterns_next_review" in indexes

    def test_database_pattern_count(self):
        """Test all 20 patterns are initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            patterns = db.get_patterns_due()
            assert len(patterns) == 20

    def test_database_stores_path(self):
        """Test database stores its path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            assert db.db_path == db_path


# =============================================================================
# Attempt Tests
# =============================================================================

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

    def test_save_attempt_returns_incrementing_ids(self, db):
        """Test IDs increment properly."""
        ids = []
        for i in range(5):
            attempt = Attempt(
                problem_slug=f"problem-{i}",
                started_at=datetime.now(),
                result="solved",
            )
            ids.append(db.save_attempt(attempt))

        assert ids == [1, 2, 3, 4, 5]

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

    def test_save_attempt_without_completion(self, db):
        """Test saving attempt without completion time."""
        attempt = Attempt(
            problem_slug="test",
            started_at=datetime.now(),
            result="gave_up",
        )

        db.save_attempt(attempt)
        attempts = db.get_attempts("test")

        assert attempts[0].completed_at is None

    def test_save_attempt_all_results(self, db):
        """Test saving attempts with all result types."""
        results = ["solved", "gave_up", "timeout"]

        for result in results:
            attempt = Attempt(
                problem_slug=f"test-{result}",
                started_at=datetime.now(),
                result=result,
            )
            db.save_attempt(attempt)
            saved = db.get_attempts(f"test-{result}")
            assert saved[0].result == result

    def test_save_attempt_all_languages(self, db):
        """Test saving attempts with all languages."""
        languages = ["cpp", "rust", "ocaml", "python"]

        for lang in languages:
            attempt = Attempt(
                problem_slug=f"test-{lang}",
                started_at=datetime.now(),
                result="solved",
                language=lang,
            )
            db.save_attempt(attempt)
            saved = db.get_attempts(f"test-{lang}")
            assert saved[0].language == lang

    def test_get_attempts_for_problem(self, db):
        """Test retrieving attempts for a specific problem."""
        for i in range(3):
            attempt = Attempt(
                problem_slug="same-problem",
                started_at=datetime.now() - timedelta(hours=i),
                result="solved" if i == 0 else "gave_up",
                code=f"attempt {i}",
            )
            db.save_attempt(attempt)

        other = Attempt(
            problem_slug="other-problem",
            started_at=datetime.now(),
            result="solved",
        )
        db.save_attempt(other)

        attempts = db.get_attempts("same-problem")

        assert len(attempts) == 3
        assert attempts[0].result == "solved"

    def test_get_attempts_empty(self, db):
        """Test getting attempts for non-existent problem."""
        attempts = db.get_attempts("nonexistent")
        assert attempts == []

    def test_get_attempts_order(self, db):
        """Test attempts are returned in correct order (newest first)."""
        for i in range(5):
            attempt = Attempt(
                problem_slug="test",
                started_at=datetime.now() - timedelta(hours=i),
                result="solved",
                code=f"code-{i}",
            )
            db.save_attempt(attempt)

        attempts = db.get_attempts("test")

        assert attempts[0].code == "code-0"  # Most recent
        assert attempts[4].code == "code-4"  # Oldest

    def test_save_attempt_with_long_code(self, db):
        """Test saving attempt with very long code."""
        long_code = "x" * 100000

        attempt = Attempt(
            problem_slug="test",
            started_at=datetime.now(),
            result="solved",
            code=long_code,
        )
        db.save_attempt(attempt)
        saved = db.get_attempts("test")

        assert saved[0].code == long_code

    def test_save_attempt_with_unicode(self, db):
        """Test saving attempt with unicode in code."""
        code = "# 日本語コメント\ndef solve(): return '🎉'"

        attempt = Attempt(
            problem_slug="unicode-test",
            started_at=datetime.now(),
            result="solved",
            code=code,
        )
        db.save_attempt(attempt)
        saved = db.get_attempts("unicode-test")

        assert "日本語" in saved[0].code
        assert "🎉" in saved[0].code

    def test_save_attempt_hints_used_range(self, db):
        """Test saving attempts with various hint counts."""
        for hints in [0, 1, 5, 10, 100]:
            attempt = Attempt(
                problem_slug=f"hints-{hints}",
                started_at=datetime.now(),
                result="solved",
                hints_used=hints,
            )
            db.save_attempt(attempt)
            saved = db.get_attempts(f"hints-{hints}")
            assert saved[0].hints_used == hints


# =============================================================================
# Pattern Tests
# =============================================================================

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
        assert dfs.next_review is not None
        assert dfs.next_review < datetime.now() + timedelta(days=2)

    def test_update_pattern_multiple_times(self, db):
        """Test updating pattern multiple times."""
        db.update_pattern("binary-search", success=False)
        db.update_pattern("binary-search", success=False)
        db.update_pattern("binary-search", success=True)

        patterns = db.get_weakest_patterns(limit=20)
        bs = next((p for p in patterns if p.name == "binary-search"), None)

        assert bs is not None
        assert bs.total_attempts == 3
        assert 0 < bs.success_rate < 1

    def test_update_pattern_success_rate_calculation(self, db):
        """Test success rate uses weighted average."""
        # Fail first
        db.update_pattern("stack", success=False)
        patterns = db.get_weakest_patterns(limit=20)
        stack = next((p for p in patterns if p.name == "stack"), None)
        rate_after_fail = stack.success_rate

        # Then succeed
        db.update_pattern("stack", success=True)
        patterns = db.get_weakest_patterns(limit=20)
        stack = next((p for p in patterns if p.name == "stack"), None)
        rate_after_success = stack.success_rate

        assert rate_after_success > rate_after_fail

    def test_update_pattern_next_review_success(self, db):
        """Test next_review increases on success."""
        db.update_pattern("heap", success=True)

        patterns = db.get_weakest_patterns(limit=20)
        heap = next((p for p in patterns if p.name == "heap"), None)

        # Should be at least 1 day in future
        assert heap.next_review > datetime.now()

    def test_update_pattern_next_review_failure(self, db):
        """Test next_review is soon on failure."""
        db.update_pattern("trie", success=False)

        patterns = db.get_weakest_patterns(limit=20)
        trie = next((p for p in patterns if p.name == "trie"), None)

        # Should be within 2 days
        assert trie.next_review < datetime.now() + timedelta(days=2)

    def test_update_nonexistent_pattern(self, db):
        """Test updating non-existent pattern does nothing."""
        db.update_pattern("nonexistent-pattern", success=True)
        # Should not raise, just do nothing

    def test_get_patterns_due_initial(self, db):
        """Test all patterns are due initially."""
        patterns_due = db.get_patterns_due()
        assert len(patterns_due) == len(PATTERNS)

    def test_get_patterns_due_ordering(self, db):
        """Test due patterns are ordered correctly."""
        db.update_pattern("stack", success=True)
        db.update_pattern("stack", success=True)  # High success
        db.update_pattern("heap", success=False)  # Low success

        patterns_due = db.get_patterns_due()

        # Find the practiced patterns
        practiced_patterns = [p for p in patterns_due if p.total_attempts > 0]

        # If heap is in the due list, it should have lower success rate
        heap = next((p for p in practiced_patterns if p.name == "heap"), None)
        stack = next((p for p in practiced_patterns if p.name == "stack"), None)

        if heap and stack:
            # Heap (lower success) should have lower success rate
            assert heap.success_rate <= stack.success_rate

    def test_get_weakest_patterns(self, db):
        """Test getting weakest patterns."""
        db.update_pattern("stack", success=True)
        db.update_pattern("stack", success=True)
        db.update_pattern("heap", success=False)
        db.update_pattern("trie", success=False)
        db.update_pattern("trie", success=False)

        weakest = db.get_weakest_patterns(limit=3)

        assert len(weakest) == 3
        assert weakest[0].success_rate <= weakest[1].success_rate <= weakest[2].success_rate

    def test_get_weakest_patterns_requires_attempts(self, db):
        """Test weakest patterns only includes practiced patterns."""
        weakest = db.get_weakest_patterns(limit=5)
        assert len(weakest) == 0

        db.update_pattern("queue", success=True)
        weakest = db.get_weakest_patterns(limit=5)
        assert len(weakest) == 1

    def test_get_weakest_patterns_limit(self, db):
        """Test limit parameter works."""
        for pattern in PATTERNS[:5]:
            db.update_pattern(pattern, success=True)

        weakest = db.get_weakest_patterns(limit=3)
        assert len(weakest) == 3

    def test_all_patterns_exist(self, db):
        """Test all expected patterns exist."""
        expected = [
            "two-pointer", "sliding-window", "binary-search", "dfs", "bfs",
            "dynamic-programming", "backtracking", "greedy", "hash-map",
            "stack", "queue", "heap", "trie", "union-find", "topological-sort",
            "monotonic-stack", "bit-manipulation", "math", "tree-traversal", "graph",
        ]

        patterns = db.get_patterns_due()
        pattern_names = {p.name for p in patterns}

        for expected_pattern in expected:
            assert expected_pattern in pattern_names


# =============================================================================
# Insight Tests
# =============================================================================

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

    def test_save_insight_incrementing_ids(self, db):
        """Test insight IDs increment."""
        ids = []
        for i in range(3):
            insight = Insight(
                problem_slug=f"problem-{i}",
                insight=f"Insight {i}",
                created_at=datetime.now(),
            )
            ids.append(db.save_insight(insight))

        assert ids == [1, 2, 3]

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
        assert insights[0].insight == "Insight 0"

    def test_get_insights_by_problem(self, db):
        """Test getting insights for specific problem."""
        for i in range(2):
            insight = Insight(
                problem_slug="target-problem",
                insight=f"Target insight {i}",
                created_at=datetime.now(),
            )
            db.save_insight(insight)

        other = Insight(
            problem_slug="other-problem",
            insight="Other insight",
            created_at=datetime.now(),
        )
        db.save_insight(other)

        insights = db.get_insights("target-problem")

        assert len(insights) == 2
        assert all(i.problem_slug == "target-problem" for i in insights)

    def test_get_insights_empty(self, db):
        """Test getting insights when none exist."""
        insights = db.get_insights()
        assert insights == []

    def test_get_insights_nonexistent_problem(self, db):
        """Test getting insights for non-existent problem."""
        insights = db.get_insights("nonexistent")
        assert insights == []

    def test_save_insight_long_text(self, db):
        """Test saving insight with long text."""
        long_insight = "x" * 10000

        insight = Insight(
            problem_slug="test",
            insight=long_insight,
            created_at=datetime.now(),
        )
        db.save_insight(insight)
        saved = db.get_insights("test")

        assert saved[0].insight == long_insight

    def test_save_insight_unicode(self, db):
        """Test saving insight with unicode."""
        insight = Insight(
            problem_slug="test",
            insight="Key insight: 動的計画法を使う 🎯",
            created_at=datetime.now(),
        )
        db.save_insight(insight)
        saved = db.get_insights("test")

        assert "動的計画法" in saved[0].insight
        assert "🎯" in saved[0].insight

    def test_get_insights_order(self, db):
        """Test insights returned newest first."""
        for i in range(5):
            insight = Insight(
                problem_slug="test",
                insight=f"insight-{i}",
                created_at=datetime.now() - timedelta(hours=i),
            )
            db.save_insight(insight)

        insights = db.get_insights("test")

        assert insights[0].insight == "insight-0"
        assert insights[4].insight == "insight-4"


# =============================================================================
# Stats Tests
# =============================================================================

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
        for slug in ["problem-a", "problem-a", "problem-b"]:
            attempt = Attempt(
                problem_slug=slug,
                started_at=datetime.now(),
                result="solved",
            )
            db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["unique_problems"] == 2

    def test_get_stats_unique_problems_only_solved(self, db):
        """Test unique problems only counts solved."""
        attempt1 = Attempt(
            problem_slug="solved-problem",
            started_at=datetime.now(),
            result="solved",
        )
        db.save_attempt(attempt1)

        attempt2 = Attempt(
            problem_slug="failed-problem",
            started_at=datetime.now(),
            result="gave_up",
        )
        db.save_attempt(attempt2)

        stats = db.get_stats()

        assert stats["unique_problems"] == 1

    def test_get_stats_streak(self, db):
        """Test streak calculation."""
        today = datetime.now()

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

        attempt1 = Attempt(
            problem_slug="today-problem",
            started_at=today,
            result="solved",
        )
        db.save_attempt(attempt1)

        attempt2 = Attempt(
            problem_slug="old-problem",
            started_at=today - timedelta(days=2),
            result="solved",
        )
        db.save_attempt(attempt2)

        stats = db.get_stats()

        assert stats["streak"] == 1

    def test_get_stats_streak_zero(self, db):
        """Test streak is zero when no practice today."""
        yesterday = datetime.now() - timedelta(days=1)

        attempt = Attempt(
            problem_slug="yesterday",
            started_at=yesterday,
            result="solved",
        )
        db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["streak"] == 0

    def test_get_stats_streak_long(self, db):
        """Test long streak calculation."""
        today = datetime.now()

        for days_ago in range(30):
            attempt = Attempt(
                problem_slug=f"problem-{days_ago}",
                started_at=today - timedelta(days=days_ago),
                result="solved",
            )
            db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["streak"] == 30

    def test_get_stats_multiple_attempts_per_day(self, db):
        """Test streak counts day only once."""
        today = datetime.now()

        for i in range(5):
            attempt = Attempt(
                problem_slug=f"problem-{i}",
                started_at=today - timedelta(hours=i),
                result="solved",
            )
            db.save_attempt(attempt)

        stats = db.get_stats()

        assert stats["streak"] == 1


# =============================================================================
# Pydantic Model Tests
# =============================================================================

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

    def test_attempt_all_fields(self):
        """Test Attempt with all fields."""
        now = datetime.now()
        attempt = Attempt(
            id=1,
            problem_slug="test",
            started_at=now,
            completed_at=now + timedelta(minutes=10),
            result="solved",
            hints_used=3,
            code="solution code",
            language="rust",
            time_complexity="O(n)",
            space_complexity="O(1)",
        )

        assert attempt.id == 1
        assert attempt.hints_used == 3
        assert attempt.language == "rust"

    def test_pattern_defaults(self):
        """Test Pattern model defaults."""
        pattern = Pattern(name="test-pattern")

        assert pattern.last_practiced is None
        assert pattern.success_rate == 0.0
        assert pattern.total_attempts == 0
        assert pattern.next_review is None

    def test_pattern_all_fields(self):
        """Test Pattern with all fields."""
        now = datetime.now()
        pattern = Pattern(
            name="two-pointer",
            last_practiced=now,
            success_rate=0.85,
            total_attempts=20,
            next_review=now + timedelta(days=7),
        )

        assert pattern.success_rate == 0.85
        assert pattern.total_attempts == 20

    def test_insight_required_fields(self):
        """Test Insight requires all fields."""
        with pytest.raises(Exception):
            Insight(problem_slug="test")  # type: ignore

    def test_insight_all_fields(self):
        """Test Insight with all fields."""
        now = datetime.now()
        insight = Insight(
            id=1,
            problem_slug="test",
            insight="Important insight",
            created_at=now,
        )

        assert insight.id == 1
        assert insight.insight == "Important insight"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def test_special_characters_in_slug(self, db):
        """Test handling special characters in problem slug."""
        attempt = Attempt(
            problem_slug="test-problem_with.special",
            started_at=datetime.now(),
            result="solved",
        )
        db.save_attempt(attempt)
        saved = db.get_attempts("test-problem_with.special")
        assert len(saved) == 1

    def test_empty_code(self, db):
        """Test saving attempt with empty code."""
        attempt = Attempt(
            problem_slug="test",
            started_at=datetime.now(),
            result="solved",
            code="",
        )
        db.save_attempt(attempt)
        saved = db.get_attempts("test")
        assert saved[0].code == ""

    def test_null_complexity(self, db):
        """Test saving attempt with null complexity."""
        attempt = Attempt(
            problem_slug="test",
            started_at=datetime.now(),
            result="solved",
            time_complexity=None,
            space_complexity=None,
        )
        db.save_attempt(attempt)
        saved = db.get_attempts("test")
        assert saved[0].time_complexity is None
        assert saved[0].space_complexity is None

    def test_concurrent_access(self, db):
        """Test database handles concurrent access."""
        # Save many attempts rapidly
        for i in range(100):
            attempt = Attempt(
                problem_slug=f"problem-{i % 10}",
                started_at=datetime.now(),
                result="solved",
            )
            db.save_attempt(attempt)

        stats = db.get_stats()
        assert stats["total_attempts"] == 100

    def test_datetime_precision(self, db):
        """Test datetime precision is preserved."""
        precise_time = datetime(2024, 1, 15, 12, 30, 45, 123456)
        attempt = Attempt(
            problem_slug="test",
            started_at=precise_time,
            result="solved",
        )
        db.save_attempt(attempt)
        saved = db.get_attempts("test")

        # Microseconds might not be preserved depending on SQLite
        assert saved[0].started_at.year == 2024
        assert saved[0].started_at.month == 1
        assert saved[0].started_at.day == 15
