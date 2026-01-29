"""Comprehensive tests for TUI components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
from pathlib import Path
from datetime import datetime

from grind.tui.app import (
    GrindApp,
    WelcomeScreen,
    PracticeScreen,
    LANGUAGE_TEMPLATES,
)
from grind.tui.vim_editor import VimEditor, VimMode
from grind.config import Settings
from grind.api.leetcode import LeetCodeClient, Problem, DailyProblem, TopicTag
from grind.ai.coach import Coach
from grind.db.database import Database


# =============================================================================
# Language Templates Tests
# =============================================================================

class TestLanguageTemplates:
    """Tests for language templates."""

    def test_cpp_template(self):
        """Test C++ template exists and has Solution class."""
        template = LANGUAGE_TEMPLATES["cpp"]
        assert "class Solution" in template
        assert "#include" in template

    def test_cpp_template_includes(self):
        """Test C++ template has necessary includes."""
        template = LANGUAGE_TEMPLATES["cpp"]
        assert "#include <bits/stdc++.h>" in template
        assert "using namespace std" in template

    def test_rust_template(self):
        """Test Rust template exists and has impl."""
        template = LANGUAGE_TEMPLATES["rust"]
        assert "impl Solution" in template
        assert "pub fn" in template

    def test_rust_template_structure(self):
        """Test Rust template structure."""
        template = LANGUAGE_TEMPLATES["rust"]
        assert "impl Solution" in template
        assert "fn" in template

    def test_ocaml_template(self):
        """Test OCaml template exists."""
        template = LANGUAGE_TEMPLATES["ocaml"]
        assert "let solve" in template

    def test_ocaml_template_structure(self):
        """Test OCaml template structure."""
        template = LANGUAGE_TEMPLATES["ocaml"]
        assert "let" in template
        assert "()" in template

    def test_all_languages_have_templates(self):
        """Test all supported languages have templates."""
        for lang in ["cpp", "rust", "ocaml"]:
            assert lang in LANGUAGE_TEMPLATES
            assert len(LANGUAGE_TEMPLATES[lang]) > 0

    def test_templates_have_todo(self):
        """Test all templates have TODO marker."""
        for lang, template in LANGUAGE_TEMPLATES.items():
            assert "TODO" in template, f"{lang} template missing TODO"

    def test_template_count(self):
        """Test exactly 3 templates exist."""
        assert len(LANGUAGE_TEMPLATES) == 3


# =============================================================================
# VimEditor Tests
# =============================================================================

class TestVimEditor:
    """Tests for VimEditor widget."""

    def test_editor_initialization_cpp(self):
        """Test editor initializes with C++ template."""
        editor = VimEditor(language="cpp")
        assert editor.code_language == "cpp"
        assert "class Solution" in editor.text

    def test_editor_initialization_rust(self):
        """Test editor initializes with Rust template."""
        editor = VimEditor(language="rust")
        assert editor.code_language == "rust"
        assert "impl Solution" in editor.text

    def test_editor_initialization_ocaml(self):
        """Test editor initializes with OCaml template."""
        editor = VimEditor(language="ocaml")
        assert editor.code_language == "ocaml"
        assert "let solve" in editor.text

    def test_editor_unknown_language(self):
        """Test editor with unknown language uses empty template."""
        editor = VimEditor(language="unknown")
        assert editor.text == ""

    def test_editor_empty_language(self):
        """Test editor with empty language."""
        editor = VimEditor(language="")
        assert editor.text == ""

    def test_editor_stores_language(self):
        """Test editor stores language attribute."""
        for lang in ["cpp", "rust", "ocaml"]:
            editor = VimEditor(language=lang)
            assert editor.code_language == lang

    def test_editor_bindings_exist(self):
        """Test editor has bindings defined."""
        assert hasattr(VimEditor, "BINDINGS")

    def test_editor_vim_mode_default(self):
        """Test editor starts in normal mode."""
        editor = VimEditor()
        assert editor.vim_mode == VimMode.NORMAL


# =============================================================================
# PracticeScreen Tests
# =============================================================================

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
            questionTitle="Test Problem",
            titleSlug="test-problem",
            difficulty="Easy",
            question="Solve this",
            topicTags=[TopicTag(name="Array", slug="array")],
        )

        screen = PracticeScreen(settings, client, coach, db, problem=problem)

        assert screen.current_problem == problem

    def test_practice_screen_attempt_start_none(self, mock_components):
        """Test attempt_start is None initially."""
        settings, client, coach, db = mock_components
        screen = PracticeScreen(settings, client, coach, db)
        assert screen.attempt_start is None

    def test_practice_screen_hints_start_zero(self, mock_components):
        """Test hints_used starts at zero."""
        settings, client, coach, db = mock_components
        screen = PracticeScreen(settings, client, coach, db)
        assert screen.hints_used == 0


class TestPracticeScreenCSS:
    """Tests for PracticeScreen CSS."""

    def test_css_defined(self):
        """Test CSS is defined on PracticeScreen."""
        assert hasattr(PracticeScreen, "CSS")
        assert len(PracticeScreen.CSS) > 0

    def test_css_has_grid(self):
        """Test CSS includes grid layout."""
        assert "grid" in PracticeScreen.CSS

    def test_css_has_panes(self):
        """Test CSS defines panes."""
        css = PracticeScreen.CSS
        assert "problem-pane" in css
        assert "editor-pane" in css
        assert "coach-pane" in css


# =============================================================================
# WelcomeScreen Tests
# =============================================================================

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

    def test_welcome_screen_stores_db(self, mock_components):
        """Test WelcomeScreen stores database."""
        settings, client, coach, db = mock_components
        screen = WelcomeScreen(settings, client, coach, db)
        assert screen.db == db

    def test_welcome_screen_stores_coach(self, mock_components):
        """Test WelcomeScreen stores coach."""
        settings, client, coach, db = mock_components
        screen = WelcomeScreen(settings, client, coach, db)
        assert screen.coach == coach


class TestWelcomeScreenCSS:
    """Tests for WelcomeScreen CSS."""

    def test_css_defined(self):
        """Test CSS is defined on WelcomeScreen."""
        assert hasattr(WelcomeScreen, "CSS")
        assert len(WelcomeScreen.CSS) > 0

    def test_css_centers_content(self):
        """Test CSS centers content."""
        css = WelcomeScreen.CSS
        assert "center" in css or "middle" in css

    def test_css_has_welcome_box(self):
        """Test CSS defines welcome box."""
        assert "welcome-box" in WelcomeScreen.CSS


# =============================================================================
# GrindApp Tests
# =============================================================================

class TestGrindApp:
    """Tests for main GrindApp."""

    def test_app_title(self):
        """Test app has correct title."""
        assert GrindApp.TITLE == "Grind"

    def test_app_has_bindings(self):
        """Test app has bindings defined."""
        assert hasattr(GrindApp, "BINDINGS")

    def test_app_ctrl_c_binding(self):
        """Test app has ctrl+c to quit."""
        binding_keys = {b.key for b in GrindApp.BINDINGS}
        assert "ctrl+c" in binding_keys

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

    @patch("grind.tui.app.load_settings")
    @patch("grind.tui.app.LeetCodeClient")
    @patch("grind.tui.app.Coach")
    @patch("grind.tui.app.Database")
    def test_app_uses_settings_url(
        self, mock_db, mock_coach, mock_client, mock_settings
    ):
        """Test app passes settings URL to client."""
        mock_settings.return_value = MagicMock(
            leetcode_api_url="http://custom-api:3000",
            get_db_path=MagicMock(return_value=Path("/tmp/test.db")),
        )

        GrindApp()

        mock_client.assert_called_once_with("http://custom-api:3000")


# =============================================================================
# PracticeScreen Actions Tests
# =============================================================================

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
                questionTitle="Test Problem",
                titleSlug="test-problem",
                difficulty="Medium",
                question="Solve this problem",
                topicTags=[TopicTag(name="DP", slug="dynamic-programming")],
            )

            screen = PracticeScreen(settings, client, coach, db, problem=problem)
            screen.attempt_start = datetime.now()

            yield screen

    @pytest.mark.asyncio
    async def test_hint_increments_counter(self, screen_with_mocks):
        """Test getting hint increments hints_used."""
        screen = screen_with_mocks
        initial_hints = screen.hints_used

        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="Here's a hint")

        await screen.action_hint()

        assert screen.hints_used == initial_hints + 1

    @pytest.mark.asyncio
    async def test_hint_escalation_gentle(self, screen_with_mocks):
        """Test first hint is gentle."""
        screen = screen_with_mocks
        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="hint")

        await screen.action_hint()

        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "gentle"

    @pytest.mark.asyncio
    async def test_hint_escalation_medium(self, screen_with_mocks):
        """Test second hint is medium."""
        screen = screen_with_mocks
        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="hint")

        await screen.action_hint()
        await screen.action_hint()

        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "medium"

    @pytest.mark.asyncio
    async def test_hint_escalation_strong(self, screen_with_mocks):
        """Test third hint is strong."""
        screen = screen_with_mocks
        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="hint")

        await screen.action_hint()
        await screen.action_hint()
        await screen.action_hint()

        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "strong"

    @pytest.mark.asyncio
    async def test_hint_stays_strong(self, screen_with_mocks):
        """Test hints stay strong after third."""
        screen = screen_with_mocks
        screen.query_one = MagicMock()
        screen.coach.get_hint = AsyncMock(return_value="hint")

        for _ in range(5):
            await screen.action_hint()

        call_args = screen.coach.get_hint.call_args
        assert call_args[0][1] == "strong"

    @pytest.mark.asyncio
    async def test_hint_no_problem_does_nothing(self, screen_with_mocks):
        """Test hint with no problem does nothing."""
        screen = screen_with_mocks
        screen.current_problem = None
        initial_hints = screen.hints_used

        await screen.action_hint()

        assert screen.hints_used == initial_hints

    @pytest.mark.asyncio
    async def test_chat_clears_input(self, screen_with_mocks):
        """Test chat clears input after sending."""
        screen = screen_with_mocks
        mock_input = MagicMock()
        mock_input.text = "test message"

        def query_one_side_effect(selector, widget_type=None):
            if "input" in selector:
                return mock_input
            return MagicMock()

        screen.query_one = query_one_side_effect
        screen.coach.chat = AsyncMock(return_value="response")

        await screen.action_chat()

        assert mock_input.text == ""

    @pytest.mark.asyncio
    async def test_chat_empty_does_nothing(self, screen_with_mocks):
        """Test chat with empty message does nothing."""
        screen = screen_with_mocks
        mock_input = MagicMock()
        mock_input.text = "   "  # Whitespace only

        screen.query_one = MagicMock(return_value=mock_input)
        screen.coach.chat = AsyncMock()

        await screen.action_chat()

        screen.coach.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_no_problem_does_nothing(self, screen_with_mocks):
        """Test submit with no problem does nothing."""
        screen = screen_with_mocks
        screen.current_problem = None

        initial_stats = screen.db.get_stats()
        await screen.action_submit()
        final_stats = screen.db.get_stats()

        assert initial_stats["total_attempts"] == final_stats["total_attempts"]

    @pytest.mark.asyncio
    async def test_submit_no_start_does_nothing(self, screen_with_mocks):
        """Test submit without attempt_start does nothing."""
        screen = screen_with_mocks
        screen.attempt_start = None

        initial_stats = screen.db.get_stats()
        await screen.action_submit()
        final_stats = screen.db.get_stats()

        assert initial_stats["total_attempts"] == final_stats["total_attempts"]


# =============================================================================
# Bindings Tests
# =============================================================================

class TestBindings:
    """Tests for keybindings."""

    def test_practice_screen_bindings(self):
        """Test PracticeScreen has required bindings."""
        binding_keys = {b.key for b in PracticeScreen.BINDINGS}

        # Updated: now uses function keys and ctrl+n for pane switching
        assert "f1" in binding_keys  # hint
        assert "f3" in binding_keys  # submit
        assert "f4" in binding_keys  # chat
        assert "f5" in binding_keys  # next
        assert "ctrl+n" in binding_keys  # focus next

    def test_practice_screen_binding_count(self):
        """Test PracticeScreen has expected number of bindings."""
        # Updated: now has more bindings for language switching
        assert len(PracticeScreen.BINDINGS) >= 8

    def test_welcome_screen_bindings(self):
        """Test WelcomeScreen has required bindings."""
        binding_keys = {b.key for b in WelcomeScreen.BINDINGS}

        assert "d" in binding_keys  # daily
        assert "p" in binding_keys  # problems
        assert "s" in binding_keys  # stats
        assert "q" in binding_keys  # quit

    def test_welcome_screen_binding_count(self):
        """Test WelcomeScreen has expected number of bindings."""
        assert len(WelcomeScreen.BINDINGS) == 4

    def test_app_bindings(self):
        """Test GrindApp has required bindings."""
        binding_keys = {b.key for b in GrindApp.BINDINGS}
        assert "ctrl+c" in binding_keys


# =============================================================================
# Problem Model Integration Tests
# =============================================================================

class TestProblemIntegration:
    """Tests for Problem model integration with TUI."""

    def test_problem_with_all_fields(self):
        """Test creating Problem with all fields."""
        problem = Problem(
            questionTitle="Two Sum",
            titleSlug="two-sum",
            difficulty="Easy",
            question="<p>Given an array...</p>",
            topicTags=[
                TopicTag(name="Array", slug="array"),
                TopicTag(name="Hash Table", slug="hash-table"),
            ],
            hints=["Use a hash map"],
        )

        assert problem.title == "Two Sum"
        assert len(problem.topic_tags) == 2
        assert len(problem.hints) == 1

    def test_problem_minimal(self):
        """Test creating Problem with minimal fields."""
        problem = Problem(
            questionTitle="Test",
            titleSlug="test",
            difficulty="Medium",
            question="Q",
        )

        assert problem.title == "Test"
        assert problem.topic_tags == []
        assert problem.hints == []


# =============================================================================
# Screen State Tests
# =============================================================================

class TestScreenState:
    """Tests for screen state management."""

    @pytest.fixture
    def practice_screen(self):
        """Create a practice screen for testing."""
        settings = MagicMock(spec=Settings)
        settings.default_language = "cpp"
        settings.agent = MagicMock()

        client = MagicMock(spec=LeetCodeClient)
        coach = MagicMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            yield PracticeScreen(settings, client, coach, db)

    def test_initial_state(self, practice_screen):
        """Test initial screen state."""
        assert practice_screen.current_problem is None
        assert practice_screen.attempt_start is None
        assert practice_screen.hints_used == 0

    def test_hints_counter_increments(self, practice_screen):
        """Test hints counter increments correctly."""
        for i in range(5):
            practice_screen.hints_used += 1
            assert practice_screen.hints_used == i + 1


# =============================================================================
# ProblemsScreen Tests
# =============================================================================

class TestProblemsScreen:
    """Tests for ProblemsScreen component."""

    @pytest.fixture
    def problems_screen(self):
        """Create a problems screen for testing."""
        settings = MagicMock(spec=Settings)
        settings.default_language = "cpp"
        settings.agent = MagicMock()

        client = MagicMock(spec=LeetCodeClient)
        coach = MagicMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            from grind.tui.app import ProblemsScreen
            yield ProblemsScreen(settings, client, coach, db)

    def test_problems_screen_initialization(self, problems_screen):
        """Test ProblemsScreen initializes correctly."""
        from grind.tui.app import ProblemsScreen
        assert isinstance(problems_screen, ProblemsScreen)
        assert problems_screen.current_plan == "top150"

    def test_problems_screen_has_study_plans(self, problems_screen):
        """Test ProblemsScreen has all study plans defined."""
        plans = problems_screen.STUDY_PLANS
        assert "top150" in plans
        assert "blind75" in plans
        assert "grind75" in plans
        assert "neetcode150" in plans
        assert "all" in plans

    def test_study_plan_metadata(self, problems_screen):
        """Test study plans have required metadata."""
        for key, plan in problems_screen.STUDY_PLANS.items():
            assert "name" in plan
            assert "slug" in plan
            assert "description" in plan

    def test_problems_screen_bindings(self, problems_screen):
        """Test ProblemsScreen has navigation bindings."""
        bindings = problems_screen.BINDINGS
        binding_keys = [b.key for b in bindings]
        assert "escape" in binding_keys
        assert "q" in binding_keys
        assert "j" in binding_keys
        assert "k" in binding_keys
        assert "enter" in binding_keys
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "3" in binding_keys
        assert "4" in binding_keys
        assert "5" in binding_keys

    def test_initial_selected_index(self, problems_screen):
        """Test initial selected index is 0."""
        assert problems_screen.selected_index == 0

    def test_problems_list_initially_empty(self, problems_screen):
        """Test problems list is initially empty."""
        assert problems_screen.problems == []


class TestProblemsScreenStudyPlans:
    """Tests for study plan functionality."""

    def test_top150_plan_config(self):
        """Test Top 150 Interview Questions plan configuration."""
        from grind.tui.app import ProblemsScreen
        plans = ProblemsScreen.STUDY_PLANS
        assert plans["top150"]["name"] == "Top 150 Interview Questions"
        assert plans["top150"]["slug"] == "top-interview-150"

    def test_blind75_plan_config(self):
        """Test Blind 75 plan configuration."""
        from grind.tui.app import ProblemsScreen
        plans = ProblemsScreen.STUDY_PLANS
        assert plans["blind75"]["name"] == "Blind 75"
        assert plans["blind75"]["slug"] == "blind-75"

    def test_grind75_plan_config(self):
        """Test Grind 75 plan configuration."""
        from grind.tui.app import ProblemsScreen
        plans = ProblemsScreen.STUDY_PLANS
        assert plans["grind75"]["name"] == "Grind 75"
        assert plans["grind75"]["slug"] == "grind-75"

    def test_neetcode150_plan_config(self):
        """Test NeetCode 150 plan configuration."""
        from grind.tui.app import ProblemsScreen
        plans = ProblemsScreen.STUDY_PLANS
        assert plans["neetcode150"]["name"] == "NeetCode 150"
        assert plans["neetcode150"]["slug"] == "neetcode-150"

    def test_all_problems_plan_config(self):
        """Test All Problems plan configuration."""
        from grind.tui.app import ProblemsScreen
        plans = ProblemsScreen.STUDY_PLANS
        assert plans["all"]["name"] == "All Problems"
        assert plans["all"]["slug"] is None  # No slug for all problems


class TestProblemsScreenCSS:
    """Tests for ProblemsScreen CSS styling."""

    def test_css_defined(self):
        """Test ProblemsScreen has CSS defined."""
        from grind.tui.app import ProblemsScreen
        assert ProblemsScreen.CSS is not None
        assert len(ProblemsScreen.CSS) > 0

    def test_css_has_grid_layout(self):
        """Test CSS defines grid layout."""
        from grind.tui.app import ProblemsScreen
        assert "grid" in ProblemsScreen.CSS

    def test_css_has_panes(self):
        """Test CSS defines plans and problems panes."""
        from grind.tui.app import ProblemsScreen
        assert "plans-pane" in ProblemsScreen.CSS
        assert "problems-pane" in ProblemsScreen.CSS

    def test_css_has_difficulty_colors(self):
        """Test CSS defines difficulty color classes."""
        from grind.tui.app import ProblemsScreen
        assert "problem-easy" in ProblemsScreen.CSS
        assert "problem-medium" in ProblemsScreen.CSS
        assert "problem-hard" in ProblemsScreen.CSS

    def test_css_has_loading_indicator_class(self):
        """Test CSS defines loading-indicator class instead of ID."""
        from grind.tui.app import ProblemsScreen
        # Should use class-based styling, not ID-based
        assert "loading-indicator" in ProblemsScreen.CSS
        # Should NOT have #loading ID selector (would cause duplicate ID issues)
        assert "#loading" not in ProblemsScreen.CSS


class TestProblemsScreenLoadingIndicator:
    """Tests for loading indicator to prevent duplicate ID issues."""

    def test_loading_indicator_uses_class_not_id(self):
        """Test loading indicator uses class instead of ID to prevent duplicates."""
        from grind.tui.app import ProblemsScreen
        # The CSS should style via class, not ID
        assert ".loading-indicator" in ProblemsScreen.CSS

    def test_load_problems_method_exists(self):
        """Test _load_problems method exists."""
        from grind.tui.app import ProblemsScreen
        assert hasattr(ProblemsScreen, "_load_problems")

    def test_problems_screen_no_duplicate_id_in_css(self):
        """Test ProblemsScreen CSS doesn't use #loading ID selector."""
        from grind.tui.app import ProblemsScreen
        css = ProblemsScreen.CSS
        # Ensure we're not using ID-based selectors for loading
        lines = [line.strip() for line in css.split('\n')]
        loading_id_selectors = [l for l in lines if l.startswith("#loading")]
        assert len(loading_id_selectors) == 0, "Should not use #loading ID selector"


# =============================================================================
# WelcomeScreen Action Tests
# =============================================================================

class TestWelcomeScreenActions:
    """Tests for WelcomeScreen action methods."""

    def test_welcome_screen_has_problems_action(self):
        """Test WelcomeScreen has action_problems method."""
        assert hasattr(WelcomeScreen, "action_problems")

    def test_welcome_screen_has_daily_action(self):
        """Test WelcomeScreen has action_daily method."""
        assert hasattr(WelcomeScreen, "action_daily")

    def test_welcome_screen_bindings_include_problems(self):
        """Test WelcomeScreen bindings include 'p' for problems."""
        bindings = WelcomeScreen.BINDINGS
        binding_keys = [b.key for b in bindings]
        assert "p" in binding_keys


# =============================================================================
# HTML to Markdown Conversion Tests
# =============================================================================

class TestHtmlToMarkdownConversion:
    """Tests for HTML to Markdown conversion in PracticeScreen."""

    @pytest.fixture
    def practice_screen(self):
        """Create a practice screen for testing."""
        settings = MagicMock(spec=Settings)
        settings.default_language = "cpp"
        settings.agent = MagicMock()

        client = MagicMock(spec=LeetCodeClient)
        coach = MagicMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            yield PracticeScreen(settings, client, coach, db)

    def test_html_to_markdown_method_exists(self, practice_screen):
        """Test _html_to_markdown method exists."""
        assert hasattr(practice_screen, "_html_to_markdown")

    def test_convert_paragraph_tags(self, practice_screen):
        """Test paragraph tags are converted."""
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        result = practice_screen._html_to_markdown(html)
        assert "First paragraph." in result
        assert "Second paragraph." in result

    def test_convert_code_tags(self, practice_screen):
        """Test inline code tags are converted."""
        html = "Use <code>nums[i]</code> to access elements."
        result = practice_screen._html_to_markdown(html)
        assert "`nums[i]`" in result

    def test_convert_pre_blocks(self, practice_screen):
        """Test pre/code blocks are converted to fenced code blocks."""
        html = "<pre>def foo():\n    return 42</pre>"
        result = practice_screen._html_to_markdown(html)
        assert "```" in result
        assert "def foo():" in result

    def test_convert_bold_tags(self, practice_screen):
        """Test bold/strong tags are converted."""
        html = "<strong>Important</strong> and <b>also bold</b>"
        result = practice_screen._html_to_markdown(html)
        assert "**Important**" in result
        assert "**also bold**" in result

    def test_convert_italic_tags(self, practice_screen):
        """Test italic/em tags are converted."""
        html = "<em>emphasized</em> and <i>italic</i>"
        result = practice_screen._html_to_markdown(html)
        assert "*emphasized*" in result
        assert "*italic*" in result

    def test_convert_unordered_list(self, practice_screen):
        """Test unordered lists are converted."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = practice_screen._html_to_markdown(html)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_convert_ordered_list(self, practice_screen):
        """Test ordered lists are converted."""
        html = "<ol><li>First</li><li>Second</li><li>Third</li></ol>"
        result = practice_screen._html_to_markdown(html)
        assert "1. First" in result
        assert "2. Second" in result
        assert "3. Third" in result

    def test_convert_links(self, practice_screen):
        """Test links are converted."""
        html = '<a href="https://example.com">Click here</a>'
        result = practice_screen._html_to_markdown(html)
        assert "[Click here](https://example.com)" in result

    def test_convert_line_breaks(self, practice_screen):
        """Test line breaks are converted."""
        html = "Line 1<br>Line 2<br/>Line 3"
        result = practice_screen._html_to_markdown(html)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_convert_html_entities(self, practice_screen):
        """Test HTML entities are decoded."""
        html = "a &lt; b &amp;&amp; c &gt; d"
        result = practice_screen._html_to_markdown(html)
        assert "a < b && c > d" in result

    def test_convert_nbsp(self, practice_screen):
        """Test non-breaking spaces are converted."""
        html = "Hello&nbsp;World"
        result = practice_screen._html_to_markdown(html)
        assert "Hello World" in result

    def test_convert_superscript(self, practice_screen):
        """Test superscript is converted."""
        html = "2<sup>10</sup> = 1024"
        result = practice_screen._html_to_markdown(html)
        assert "^10" in result

    def test_convert_subscript(self, practice_screen):
        """Test subscript is converted."""
        html = "H<sub>2</sub>O"
        result = practice_screen._html_to_markdown(html)
        assert "_2" in result

    def test_convert_headers(self, practice_screen):
        """Test header tags are converted."""
        html = "<h2>Section Title</h2>"
        result = practice_screen._html_to_markdown(html)
        assert "## Section Title" in result

    def test_convert_horizontal_rule(self, practice_screen):
        """Test horizontal rules are converted."""
        html = "Before<hr>After"
        result = practice_screen._html_to_markdown(html)
        assert "---" in result

    def test_strip_unknown_tags(self, practice_screen):
        """Test unknown tags are stripped."""
        html = "<custom>content</custom>"
        result = practice_screen._html_to_markdown(html)
        assert "content" in result
        assert "<custom>" not in result

    def test_numeric_entities(self, practice_screen):
        """Test numeric HTML entities are decoded."""
        html = "&#65;&#66;&#67;"  # ABC
        result = practice_screen._html_to_markdown(html)
        assert "ABC" in result

    def test_hex_entities(self, practice_screen):
        """Test hex HTML entities are decoded."""
        html = "&#x41;&#x42;&#x43;"  # ABC
        result = practice_screen._html_to_markdown(html)
        assert "ABC" in result


class TestHtmlTableConversion:
    """Tests for HTML table to Markdown table conversion."""

    @pytest.fixture
    def practice_screen(self):
        """Create a practice screen for testing."""
        settings = MagicMock(spec=Settings)
        settings.default_language = "cpp"
        settings.agent = MagicMock()

        client = MagicMock(spec=LeetCodeClient)
        coach = MagicMock(spec=Coach)

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            yield PracticeScreen(settings, client, coach, db)

    def test_convert_html_tables_method_exists(self, practice_screen):
        """Test _convert_html_tables method exists."""
        assert hasattr(practice_screen, "_convert_html_tables")

    def test_simple_table(self, practice_screen):
        """Test simple table conversion."""
        html = """<table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>A</td><td>1</td></tr>
            <tr><td>B</td><td>2</td></tr>
        </table>"""
        result = practice_screen._html_to_markdown(html)
        assert "| Name | Value |" in result
        assert "| --- | --- |" in result
        assert "| A | 1 |" in result
        assert "| B | 2 |" in result

    def test_table_with_only_data_rows(self, practice_screen):
        """Test table with only td elements (no th)."""
        html = """<table>
            <tr><td>X</td><td>Y</td></tr>
            <tr><td>1</td><td>2</td></tr>
        </table>"""
        result = practice_screen._html_to_markdown(html)
        assert "| X | Y |" in result
        assert "| 1 | 2 |" in result


# =============================================================================
# LeetCode API Client Extended Tests
# =============================================================================

class TestLeetCodeClientStudyPlans:
    """Tests for LeetCodeClient study plan functionality."""

    def test_client_has_study_plan_method(self):
        """Test LeetCodeClient has get_study_plan_problems method."""
        assert hasattr(LeetCodeClient, "get_study_plan_problems")

    @pytest.mark.asyncio
    async def test_study_plan_returns_list(self):
        """Test get_study_plan_problems returns a list."""
        client = LeetCodeClient()
        # Mock the internal client's get method
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        client._client.get = AsyncMock(return_value=mock_response)

        result = await client.get_study_plan_problems("blind-75")
        assert isinstance(result, list)
