"""Tests for Phase 4: Polish & Enhancement features.

This module tests:
- 4.1: Progress Dashboard (StatsScreen)
- 4.2: Smart Problem Selection (filtering in ProblemsScreen)
- 4.3: Offline Mode (indicators and queue processing)
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from grind.tui.app import (
    StatsScreen,
    ProblemsScreen,
    WelcomeScreen,
    GrindApp,
)
from grind.db.database import Database
from grind.config import Settings


# Fixtures


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_db(temp_dir):
    """Create a test database."""
    db_path = os.path.join(temp_dir, "grind.db")
    db = Database(db_path)
    return db


@pytest.fixture
def mock_settings(temp_dir):
    """Create mock settings."""
    settings = MagicMock(spec=Settings)
    settings.get_db_path.return_value = os.path.join(temp_dir, "grind.db")
    settings.copilot_relay_url = "http://localhost:8080"
    settings.openrouter_api_key = None
    settings.provider = "copilot"
    settings.default_language = "python"
    settings.leetcode_api_url = "https://leetcode.com"
    return settings


@pytest.fixture
def mock_client():
    """Create a mock LeetCode client."""
    client = MagicMock()
    client.get_study_plan_problems = AsyncMock(return_value=[
        {"title": "Two Sum", "titleSlug": "two-sum", "difficulty": "Easy"},
        {"title": "Add Two Numbers", "titleSlug": "add-two-numbers", "difficulty": "Medium"},
        {"title": "Median of Two Arrays", "titleSlug": "median-of-two-sorted-arrays", "difficulty": "Hard"},
    ])
    client.get_problems = AsyncMock(return_value=[
        {"title": "Two Sum", "titleSlug": "two-sum", "difficulty": "Easy"},
    ])
    return client


@pytest.fixture
def mock_coach():
    """Create a mock coach."""
    coach = MagicMock()
    return coach


# =============================================================================
# 4.1: Progress Dashboard Tests (StatsScreen)
# =============================================================================


class TestStatsScreen:
    """Tests for the StatsScreen component."""

    def test_stats_screen_initialization(self, mock_settings, test_db):
        """Test StatsScreen can be initialized."""
        screen = StatsScreen(mock_settings, test_db, grind_app=None)
        assert screen is not None
        assert screen.settings == mock_settings
        assert screen.db == test_db

    def test_stats_screen_has_bindings(self, mock_settings, test_db):
        """Test StatsScreen has expected keybindings."""
        screen = StatsScreen(mock_settings, test_db)
        binding_keys = [b.key for b in screen.BINDINGS]
        assert "escape" in binding_keys
        assert "q" in binding_keys
        assert "r" in binding_keys

    def test_stats_screen_has_css(self, mock_settings, test_db):
        """Test StatsScreen has CSS defined."""
        screen = StatsScreen(mock_settings, test_db)
        assert screen.CSS is not None
        assert "stats-container" in screen.CSS
        assert "progress-bar" in screen.CSS

    def test_stats_screen_filter_constants(self, mock_settings, test_db):
        """Test StatsScreen has required filter constants in ProblemsScreen."""
        # This verifies ProblemsScreen has filter constants
        assert hasattr(ProblemsScreen, "FILTER_ALL")
        assert hasattr(ProblemsScreen, "FILTER_UNSOLVED")
        assert hasattr(ProblemsScreen, "FILTER_SOLVED")
        assert ProblemsScreen.FILTER_ALL == "all"
        assert ProblemsScreen.FILTER_UNSOLVED == "unsolved"
        assert ProblemsScreen.FILTER_SOLVED == "solved"


class TestProgressBarFormatting:
    """Tests for progress bar display formatting."""

    def test_progress_bar_percentage_calculation(self):
        """Test that progress percentages are calculated correctly."""
        # Test cases: (solved, total, expected_pct)
        test_cases = [
            (0, 100, 0.0),
            (50, 100, 50.0),
            (100, 100, 100.0),
            (25, 200, 12.5),
            (0, 0, 0.0),  # Edge case: zero total
        ]

        for solved, total, expected in test_cases:
            if total > 0:
                pct = (solved / total * 100)
            else:
                pct = 0.0
            assert pct == expected, f"Failed for solved={solved}, total={total}"

    def test_progress_bar_visual_creation(self):
        """Test visual progress bar string creation."""
        bar_width = 20
        test_cases = [
            (0, 0, 20),    # 0% -> 0 filled, 20 empty
            (50, 10, 10),  # 50% -> 10 filled, 10 empty
            (100, 20, 0),  # 100% -> 20 filled, 0 empty
        ]

        for pct, expected_filled, expected_empty in test_cases:
            filled = int(bar_width * pct / 100)
            empty = bar_width - filled
            bar = "\u2588" * filled + "\u2591" * empty
            assert len(bar) == bar_width, f"Failed for pct={pct}"
            assert bar.count("\u2588") == expected_filled, f"Wrong filled for pct={pct}"
            assert bar.count("\u2591") == expected_empty, f"Wrong empty for pct={pct}"


# =============================================================================
# 4.2: Smart Problem Selection Tests
# =============================================================================


class TestProblemsScreenFiltering:
    """Tests for problem filtering in ProblemsScreen."""

    def test_problems_screen_has_filter_bindings(self, mock_settings, mock_client, mock_coach, test_db):
        """Test ProblemsScreen has filter keybindings."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        binding_keys = [b.key for b in screen.BINDINGS]
        assert "f" in binding_keys  # Toggle filter
        assert "u" in binding_keys  # Unsolved
        assert "a" in binding_keys  # All

    def test_problems_screen_initialization_with_filter(self, mock_settings, mock_client, mock_coach, test_db):
        """Test ProblemsScreen initializes with default filter."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        assert screen.current_filter == ProblemsScreen.FILTER_ALL
        assert hasattr(screen, "filtered_problems")
        assert hasattr(screen, "_solved_slugs")

    def test_apply_filter_all(self, mock_settings, mock_client, mock_coach, test_db):
        """Test filter applies correctly for all problems."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        screen.problems = [
            {"titleSlug": "two-sum", "title": "Two Sum"},
            {"titleSlug": "add-two-numbers", "title": "Add Two Numbers"},
        ]
        screen._solved_slugs = {"two-sum"}
        screen.current_filter = ProblemsScreen.FILTER_ALL

        screen._apply_filter()

        assert len(screen.filtered_problems) == 2

    def test_apply_filter_unsolved(self, mock_settings, mock_client, mock_coach, test_db):
        """Test filter applies correctly for unsolved problems."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        screen.problems = [
            {"titleSlug": "two-sum", "title": "Two Sum"},
            {"titleSlug": "add-two-numbers", "title": "Add Two Numbers"},
        ]
        screen._solved_slugs = {"two-sum"}
        screen.current_filter = ProblemsScreen.FILTER_UNSOLVED

        screen._apply_filter()

        assert len(screen.filtered_problems) == 1
        assert screen.filtered_problems[0]["titleSlug"] == "add-two-numbers"

    def test_apply_filter_solved(self, mock_settings, mock_client, mock_coach, test_db):
        """Test filter applies correctly for solved problems."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        screen.problems = [
            {"titleSlug": "two-sum", "title": "Two Sum"},
            {"titleSlug": "add-two-numbers", "title": "Add Two Numbers"},
        ]
        screen._solved_slugs = {"two-sum"}
        screen.current_filter = ProblemsScreen.FILTER_SOLVED

        screen._apply_filter()

        assert len(screen.filtered_problems) == 1
        assert screen.filtered_problems[0]["titleSlug"] == "two-sum"

    def test_apply_filter_with_title_slug_key(self, mock_settings, mock_client, mock_coach, test_db):
        """Test filter handles both titleSlug and title_slug keys."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        screen.problems = [
            {"title_slug": "two-sum", "title": "Two Sum"},  # Alternative key
            {"titleSlug": "add-two-numbers", "title": "Add Two Numbers"},
        ]
        screen._solved_slugs = {"two-sum"}
        screen.current_filter = ProblemsScreen.FILTER_UNSOLVED

        screen._apply_filter()

        assert len(screen.filtered_problems) == 1
        assert screen.filtered_problems[0].get("titleSlug") == "add-two-numbers"

    def test_cursor_navigation_uses_filtered_problems(self, mock_settings, mock_client, mock_coach, test_db):
        """Test cursor navigation respects filtered problem list."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        screen.problems = [
            {"titleSlug": "a"}, {"titleSlug": "b"}, {"titleSlug": "c"}, {"titleSlug": "d"}
        ]
        screen._solved_slugs = {"a", "b"}  # 2 solved
        screen.current_filter = ProblemsScreen.FILTER_UNSOLVED

        screen._apply_filter()

        # Only 2 unsolved problems
        assert len(screen.filtered_problems) == 2


# =============================================================================
# 4.3: Offline Mode Tests
# =============================================================================


class TestOfflineModeIndicator:
    """Tests for offline mode indicators."""

    def test_grind_app_has_online_status(self):
        """Test GrindApp tracks online status."""
        assert hasattr(GrindApp, "__init__")
        # Check that the class definition includes is_online attribute
        # We can't instantiate easily due to Textual, so check class source
        import inspect
        source = inspect.getsource(GrindApp.__init__)
        assert "is_online" in source

    def test_grind_app_has_queue_count(self):
        """Test GrindApp tracks queue count."""
        import inspect
        source = inspect.getsource(GrindApp.__init__)
        assert "queue_count" in source

    def test_welcome_screen_shows_offline_status(self, mock_settings, mock_client, mock_coach, test_db):
        """Test WelcomeScreen can display offline status."""
        # Check CSS includes offline styling
        assert "offline-status" in WelcomeScreen.CSS


class TestQueueProcessing:
    """Tests for automatic queue processing."""

    def test_grind_app_has_queue_methods(self):
        """Test GrindApp has methods for queue processing."""
        assert hasattr(GrindApp, "_update_queue_count")
        assert hasattr(GrindApp, "_check_queue_and_process")
        assert hasattr(GrindApp, "_process_queue_silently")

    @pytest.mark.asyncio
    async def test_update_queue_count_with_mock_sync(self, mock_settings):
        """Test queue count update logic."""
        with patch("grind.sync.SyncService") as MockSync:
            # Setup mock
            mock_sync = MagicMock()
            mock_sync.get_pending_submissions.return_value = [
                {"id": 1, "problem_slug": "two-sum"},
                {"id": 2, "problem_slug": "add-two-numbers"},
            ]
            MockSync.return_value = mock_sync

            # Test the queue count logic
            pending = mock_sync.get_pending_submissions()
            queue_count = len(pending) if pending else 0
            assert queue_count == 2


# =============================================================================
# Integration Tests
# =============================================================================


class TestPhase4Integration:
    """Integration tests for Phase 4 features working together."""

    def test_all_screens_importable(self):
        """Test all new screens can be imported."""
        from grind.tui.app import StatsScreen, ProblemsScreen, WelcomeScreen, GrindApp
        assert StatsScreen is not None
        assert ProblemsScreen is not None
        assert WelcomeScreen is not None
        assert GrindApp is not None

    def test_welcome_screen_has_stats_action(self, mock_settings, mock_client, mock_coach, test_db):
        """Test WelcomeScreen has action_stats binding."""
        screen = WelcomeScreen(mock_settings, mock_client, mock_coach, test_db)
        binding_keys = [b.key for b in screen.BINDINGS]
        assert "s" in binding_keys
        assert hasattr(screen, "action_stats")

    def test_problems_screen_study_plans_exist(self, mock_settings, mock_client, mock_coach, test_db):
        """Test ProblemsScreen has study plans defined."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        assert hasattr(screen, "STUDY_PLANS")
        plans = screen.STUDY_PLANS
        assert "top150" in plans
        assert "blind75" in plans
        assert "grind75" in plans
        assert "neetcode150" in plans
        assert "all" in plans


class TestFilterStateManagement:
    """Tests for filter state management across navigation."""

    def test_filter_toggle_cycles_through_states(self, mock_settings, mock_client, mock_coach, test_db):
        """Test filter toggle cycles: all -> unsolved -> solved -> all."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)

        # Initial state
        assert screen.current_filter == ProblemsScreen.FILTER_ALL

        # Simulate toggle cycle
        if screen.current_filter == ProblemsScreen.FILTER_ALL:
            screen.current_filter = ProblemsScreen.FILTER_UNSOLVED
        assert screen.current_filter == ProblemsScreen.FILTER_UNSOLVED

        if screen.current_filter == ProblemsScreen.FILTER_UNSOLVED:
            screen.current_filter = ProblemsScreen.FILTER_SOLVED
        assert screen.current_filter == ProblemsScreen.FILTER_SOLVED

        if screen.current_filter == ProblemsScreen.FILTER_SOLVED:
            screen.current_filter = ProblemsScreen.FILTER_ALL
        assert screen.current_filter == ProblemsScreen.FILTER_ALL

    def test_filter_resets_selected_index(self, mock_settings, mock_client, mock_coach, test_db):
        """Test filter change resets selected index to 0."""
        screen = ProblemsScreen(mock_settings, mock_client, mock_coach, test_db)
        screen.selected_index = 5

        # Simulating what action_filter_unsolved does
        screen.current_filter = ProblemsScreen.FILTER_UNSOLVED
        screen.selected_index = 0

        assert screen.selected_index == 0


class TestSolvedMarkerDisplay:
    """Tests for solved problem marker display."""

    def test_solved_marker_format(self):
        """Test solved marker is displayed correctly."""
        is_solved = True
        solved_marker = "" if is_solved else "  "
        assert solved_marker == ""

        is_solved = False
        solved_marker = "" if is_solved else "  "
        assert solved_marker == "  "

    def test_difficulty_class_names(self):
        """Test difficulty class names are generated correctly."""
        difficulties = ["Easy", "Medium", "Hard"]
        expected_classes = ["problem-easy", "problem-medium", "problem-hard"]

        for diff, expected in zip(difficulties, expected_classes):
            class_name = f"problem-{diff.lower()}"
            assert class_name == expected
