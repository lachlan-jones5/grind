"""Tests for TUI components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
from pathlib import Path
from datetime import datetime

from grind.tui.app import (
    GrindApp,
    WelcomeScreen,
    PracticeScreen,
    ProblemPanel,
    CodeEditor,
    CoachPanel,
    StatsBar,
    LANGUAGE_TEMPLATES,
)
from grind.config import Settings
from grind.api.leetcode import LeetCodeClient, Problem, DailyProblem
from grind.ai.coach import Coach
from grind.db.database import Database


class TestLanguageTemplates:
    """Tests for language templates."""

    def test_cpp_template(self):
        """Test C++ template exists and has Solution class."""
        template = LANGUAGE_TEMPLATES["cpp"]
        assert "class Solution" in template
        assert "#include" in template

    def test_rust_template(self):
        """Test Rust template exists and has impl."""
        template = LANGUAGE_TEMPLATES["rust"]
        assert "impl Solution" in template
        assert "pub fn" in template

    def test_ocaml_template(self):
        """Test OCaml template exists."""
        template = LANGUAGE_TEMPLATES["ocaml"]
        assert "let solve" in template

    def test_all_languages_have_templates(self):
        """Test all supported languages have templates."""
        for lang in ["cpp", "rust", "ocaml"]:
            assert lang in LANGUAGE_TEMPLATES
            assert len(LANGUAGE_TEMPLATES[lang]) > 0


class TestCodeEditor:
    """Tests for CodeEditor widget."""

    def test_editor_initialization(self):
        """Test editor initializes with language template."""
        editor = CodeEditor(language="cpp")
        assert editor.language == "cpp"
        assert "class Solution" in editor.text

    def test_editor_rust_language(self):
        """Test editor with Rust template."""
        editor = CodeEditor(language="rust")
        assert editor.language == "rust"
        assert "impl Solution" in editor.text

    def test_editor_unknown_language(self):
        """Test editor with unknown language uses empty template."""
        editor = CodeEditor(language="unknown")
        assert editor.text == ""


class TestStatsBar:
    """Tests for StatsBar widget."""

    def test_stats_bar_initialization(self):
        """Test stats bar initializes with stats dict."""
        stats = {"streak": 5, "unique_problems": 42}
        bar = StatsBar(stats)
        assert bar.stats == stats

    def test_stats_bar_missing_keys(self):
        """Test stats bar handles missing keys."""
        bar = StatsBar({})
        assert bar.stats == {}


class TestPracticeScreen:
    """Tests for PracticeScreen."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for PracticeScreen."""
        settings = MagicMock(spec=Settings)
        settings.default_language = "cpp"
        settings.agent = MagicMock()
        settings.agent.system_prompt = "Test prompt"

        client = MagicMock(spec=LeetCodeClient)
        coach = MagicMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            yield settings, client, coach, db

    def test_practice_screen_initialization(self, mock_components):
        """Test PracticeScreen initializes correctly."""
        settings, client, coach, db = mock_components

        screen = PracticeScreen(settings, client, coach, db)

        assert screen.settings == settings
        assert screen.client == client
        assert screen.coach == coach
        assert screen.db == db
        assert screen.current_problem is None
        assert screen.hints_used == 0

    def test_practice_screen_with_problem(self, mock_components):
        """Test PracticeScreen initializes with a problem."""
        settings, client, coach, db = mock_components

        problem = Problem(
            title="Test Problem",
            title_slug="test-problem",
            difficulty="Easy",
            question="Solve this",
            topic_tags=["array"],
        )

        screen = PracticeScreen(settings, client, coach, db, problem=problem)

        assert screen.current_problem == problem


class TestWelcomeScreen:
    """Tests for WelcomeScreen."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for WelcomeScreen."""
        settings = MagicMock(spec=Settings)
        client = MagicMock(spec=LeetCodeClient)
        coach = MagicMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            yield settings, client, coach, db

    def test_welcome_screen_initialization(self, mock_components):
        """Test WelcomeScreen initializes correctly."""
        settings, client, coach, db = mock_components

        screen = WelcomeScreen(settings, client, coach, db)

        assert screen.settings == settings
        assert screen.client == client


class TestGrindApp:
    """Tests for main GrindApp."""

    def test_app_title(self):
        """Test app has correct title."""
        assert GrindApp.TITLE == "Grind"

    @patch("grind.tui.app.load_settings")
    @patch("grind.tui.app.LeetCodeClient")
    @patch("grind.tui.app.Coach")
    @patch("grind.tui.app.Database")
    def test_app_initialization(
        self, mock_db, mock_coach, mock_client, mock_settings
    ):
        """Test app initializes all components."""
        mock_settings.return_value = MagicMock(
            leetcode_api_url="https://test.com",
            get_db_path=MagicMock(return_value=Path("/tmp/test.db")),
        )

        app = GrindApp()

        mock_settings.assert_called_once()
        mock_client.assert_called_once()
        mock_coach.assert_called_once()
        mock_db.assert_called_once()


class TestProblemPanel:
    """Tests for ProblemPanel widget."""

    def test_problem_panel_initialization(self):
        """Test ProblemPanel creates markdown widget."""
        panel = ProblemPanel()
        # Panel should compose without error
        children = list(panel.compose())
        assert len(children) == 1


class TestCoachPanel:
    """Tests for CoachPanel widget."""

    def test_coach_panel_initialization(self):
        """Test CoachPanel creates markdown and input widgets."""
        panel = CoachPanel()
        children = list(panel.compose())
        assert len(children) == 2  # Markdown and TextArea


class TestPracticeScreenActions:
    """Tests for PracticeScreen action methods."""

    @pytest.fixture
    def screen_with_mocks(self):
        """Create a PracticeScreen with mocked dependencies."""
        settings = MagicMock(spec=Settings)
        settings.default_language = "cpp"
        settings.agent = MagicMock()

        client = AsyncMock(spec=LeetCodeClient)
        coach = AsyncMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")

            problem = Problem(
                title="Test Problem",
                title_slug="test-problem",
                difficulty="Medium",
                question="Solve this problem",
                topic_tags=["dp"],
            )

            screen = PracticeScreen(settings, client, coach, db, problem=problem)
            screen.attempt_start = datetime.now()

            yield screen

    @pytest.mark.asyncio
    async def test_hint_increments_counter(self, screen_with_mocks):
        """Test getting hint increments hints_used."""
        screen = screen_with_mocks
        initial_hints = screen.hints_used

        # Mock the query methods to avoid TUI initialization
        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="Here's a hint")

        await screen.action_hint()

        assert screen.hints_used == initial_hints + 1

    @pytest.mark.asyncio
    async def test_hint_escalation(self, screen_with_mocks):
        """Test hints escalate from gentle to strong."""
        screen = screen_with_mocks
        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="hint")

        # First hint should be gentle
        await screen.action_hint()
        screen.coach.get_hint.assert_called()
        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "gentle"

        # Second hint should be medium
        await screen.action_hint()
        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "medium"

        # Third hint should be strong
        await screen.action_hint()
        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "strong"

        # Fourth hint should still be strong (capped)
        await screen.action_hint()
        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "strong"


class TestBindings:
    """Tests for keybindings."""

    def test_practice_screen_bindings(self):
        """Test PracticeScreen has required bindings."""
        binding_keys = {b.key for b in PracticeScreen.BINDINGS}

        assert "h" in binding_keys  # hint
        assert "r" in binding_keys  # run
        assert "s" in binding_keys  # submit
        assert "c" in binding_keys  # chat
        assert "n" in binding_keys  # next
        assert "q" in binding_keys  # quit

    def test_welcome_screen_bindings(self):
        """Test WelcomeScreen has required bindings."""
        binding_keys = {b.key for b in WelcomeScreen.BINDINGS}

        assert "d" in binding_keys  # daily
        assert "p" in binding_keys  # problems
        assert "q" in binding_keys  # quit
