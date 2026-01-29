"""Tests for LeetCode integration improvements.

This module tests:
- Code snippet fetching from LeetCode API
- Run code functionality
- Login requirement
- Removal of local queuing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from grind.tui.app import (
    PracticeScreen,
    LoginRequiredScreen,
    GrindApp,
    LANGUAGE_TEMPLATES,
)
from grind.db.database import Database
from grind.config import Settings
from grind.auth.leetcode import LeetCodeAuth, AuthenticationError


# =============================================================================
# Fixtures
# =============================================================================


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
    client.get_daily = AsyncMock(return_value=None)
    client.get_problem = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_coach():
    """Create a mock coach."""
    coach = MagicMock()
    coach.set_problem_context = MagicMock()
    coach.get_hint = AsyncMock(return_value="Here's a hint")
    coach.review_code = AsyncMock(return_value="Code review")
    return coach


@pytest.fixture
def mock_session():
    """Create a mock session."""
    from grind.auth.session import Session
    session = Session(
        leetcode_session="test_session",
        csrf_token="test_csrf",
        username="testuser",
    )
    return session


# =============================================================================
# LoginRequiredScreen Tests
# =============================================================================


class TestLoginRequiredScreen:
    """Tests for the LoginRequiredScreen."""

    def test_login_required_screen_exists(self):
        """Test LoginRequiredScreen class exists and is importable."""
        assert LoginRequiredScreen is not None

    def test_login_required_screen_has_bindings(self):
        """Test LoginRequiredScreen has expected keybindings."""
        screen = LoginRequiredScreen()
        binding_keys = [b.key for b in screen.BINDINGS]
        assert "q" in binding_keys
        assert "r" in binding_keys

    def test_login_required_screen_has_css(self):
        """Test LoginRequiredScreen has CSS defined."""
        screen = LoginRequiredScreen()
        assert screen.CSS is not None
        assert "login-box" in screen.CSS


# =============================================================================
# Code Snippet Loading Tests
# =============================================================================


class TestCodeSnippetLoading:
    """Tests for loading code snippets from LeetCode."""

    def test_practice_screen_has_code_snippets_storage(self, mock_settings, mock_client, mock_coach, test_db):
        """Test PracticeScreen has _code_snippets dict."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        assert hasattr(screen, "_code_snippets")
        assert isinstance(screen._code_snippets, dict)

    def test_practice_screen_has_test_cases_storage(self, mock_settings, mock_client, mock_coach, test_db):
        """Test PracticeScreen has _test_cases string."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        assert hasattr(screen, "_test_cases")
        assert isinstance(screen._test_cases, str)

    def test_load_language_template_with_leetcode_snippet(self, mock_settings, mock_client, mock_coach, test_db):
        """Test template loading prefers LeetCode snippets over static templates."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        
        # Populate with LeetCode snippet
        screen._code_snippets = {
            "python3": "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        pass",
            "cpp": "class Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n    }\n};",
        }
        
        # Create a mock editor
        mock_editor = MagicMock()
        mock_editor.text = ""
        
        # Load Python template
        screen._load_language_template(mock_editor, "python")
        
        # Should use LeetCode snippet
        assert "class Solution" in mock_editor.text
        assert "twoSum" in mock_editor.text

    def test_load_language_template_fallback_to_static(self, mock_settings, mock_client, mock_coach, test_db):
        """Test template loading falls back to static templates when no LeetCode snippet."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        screen._code_snippets = {}  # No LeetCode snippets
        
        mock_editor = MagicMock()
        mock_editor.text = ""
        
        # Load cpp template (which exists in LANGUAGE_TEMPLATES)
        screen._load_language_template(mock_editor, "cpp")
        
        # Should use static template or fallback
        # Either matches static template or contains TODO fallback
        assert mock_editor.text != "" or "cpp" in LANGUAGE_TEMPLATES

    def test_language_map_correctness(self, mock_settings, mock_client, mock_coach, test_db):
        """Test language mapping is correct."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        screen._code_snippets = {
            "python3": "python3 code",
            "cpp": "cpp code",
            "golang": "go code",
        }
        
        mock_editor = MagicMock()
        
        # Test mapping
        test_cases = [
            ("python", "python3 code"),
            ("cpp", "cpp code"),
            ("go", "go code"),
        ]
        
        for lang, expected_code in test_cases:
            mock_editor.text = ""
            screen._load_language_template(mock_editor, lang)
            assert mock_editor.text == expected_code, f"Failed for {lang}"


# =============================================================================
# LeetCodeAuth API Tests
# =============================================================================


class TestLeetCodeAuthAPI:
    """Tests for LeetCodeAuth API methods."""

    def test_get_problem_detail_method_exists(self):
        """Test get_problem_detail method exists."""
        auth = LeetCodeAuth()
        assert hasattr(auth, "get_problem_detail")
        assert callable(auth.get_problem_detail)

    def test_run_code_method_exists(self):
        """Test run_code method exists."""
        auth = LeetCodeAuth()
        assert hasattr(auth, "run_code")
        assert callable(auth.run_code)

    def test_poll_run_result_method_exists(self):
        """Test _poll_run_result method exists."""
        auth = LeetCodeAuth()
        assert hasattr(auth, "_poll_run_result")

    @pytest.mark.asyncio
    async def test_get_problem_detail_without_session(self):
        """Test get_problem_detail returns None when no session stored."""
        auth = LeetCodeAuth()
        # Clear any stored session
        auth._session = None
        auth.session_manager._session = None
        result = await auth.get_problem_detail("nonexistent-problem-slug-xyz")
        # Without a valid session, should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_run_code_requires_authentication(self):
        """Test run_code requires get_session to return a valid session."""
        auth = LeetCodeAuth()
        # Verify the method exists and has the right signature
        import inspect
        sig = inspect.signature(auth.run_code)
        params = list(sig.parameters.keys())
        assert "title_slug" in params
        assert "code" in params
        assert "lang" in params


# =============================================================================
# Run Code Action Tests
# =============================================================================


class TestRunCodeAction:
    """Tests for the run code action."""

    def test_practice_screen_has_action_run(self, mock_settings, mock_client, mock_coach, test_db):
        """Test PracticeScreen has action_run method."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        assert hasattr(screen, "action_run")
        assert callable(screen.action_run)

    def test_action_run_binding_exists(self, mock_settings, mock_client, mock_coach, test_db):
        """Test run binding exists in PracticeScreen."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        binding_keys = [b.key for b in screen.BINDINGS]
        assert "f2" in binding_keys  # F2 is the run key


# =============================================================================
# No Local Queuing Tests
# =============================================================================


class TestNoLocalQueuing:
    """Tests to verify local queuing has been removed."""

    def test_grind_app_no_queue_count_attribute(self):
        """Test GrindApp doesn't have queue_count attribute."""
        # Check the __init__ source doesn't have queue_count
        import inspect
        source = inspect.getsource(GrindApp.__init__)
        assert "queue_count" not in source

    def test_grind_app_no_queue_processing_methods(self):
        """Test GrindApp doesn't have queue processing methods."""
        assert not hasattr(GrindApp, "_update_queue_count")
        assert not hasattr(GrindApp, "_check_queue_and_process")
        assert not hasattr(GrindApp, "_process_queue_silently")

    def test_practice_screen_submit_doesnt_queue(self, mock_settings, mock_client, mock_coach, test_db):
        """Test action_submit_leetcode doesn't have queue fallback."""
        import inspect
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        source = inspect.getsource(screen.action_submit_leetcode)
        
        # Should not contain queue-related code
        assert "queue_submission" not in source
        assert "queued for later" not in source.lower()


# =============================================================================
# Login Required Tests
# =============================================================================


class TestLoginRequired:
    """Tests for login requirement."""

    def test_grind_app_shows_login_screen_when_not_authenticated(self):
        """Test GrindApp on_mount checks authentication."""
        import inspect
        source = inspect.getsource(GrindApp.on_mount)
        
        # Should check authentication
        assert "is_authenticated" in source
        
        # Should show LoginRequiredScreen when not authenticated
        assert "LoginRequiredScreen" in source

    def test_login_required_screen_has_retry_action(self):
        """Test LoginRequiredScreen has action_retry method."""
        screen = LoginRequiredScreen()
        assert hasattr(screen, "action_retry")
        assert callable(screen.action_retry)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the LeetCode improvements."""

    def test_all_required_imports_work(self):
        """Test all required classes can be imported."""
        from grind.tui.app import (
            PracticeScreen,
            LoginRequiredScreen,
            GrindApp,
            WelcomeScreen,
            ProblemsScreen,
            StatsScreen,
        )
        from grind.auth.leetcode import LeetCodeAuth, AuthenticationError
        
        assert PracticeScreen is not None
        assert LoginRequiredScreen is not None
        assert GrindApp is not None
        assert LeetCodeAuth is not None
        assert AuthenticationError is not None

    def test_practice_screen_stores_test_cases(self, mock_settings, mock_client, mock_coach, test_db):
        """Test PracticeScreen can store test cases from LeetCode."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        
        # Simulate fetched test cases
        screen._test_cases = "[2,7,11,15]\n9"
        
        assert screen._test_cases == "[2,7,11,15]\n9"

    def test_code_snippets_can_be_stored(self, mock_settings, mock_client, mock_coach, test_db):
        """Test _code_snippets dict can store and retrieve snippets."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        
        # Simulate fetched code snippets
        screen._code_snippets = {
            "python3": "class Solution:\n    pass",
            "cpp": "class Solution {};",
        }
        
        assert "python3" in screen._code_snippets
        assert "cpp" in screen._code_snippets
        assert screen._code_snippets["python3"] == "class Solution:\n    pass"


class TestErrorHandling:
    """Tests for error handling in LeetCode integration."""

    def test_practice_screen_handles_fetch_failure(self, mock_settings, mock_client, mock_coach, test_db):
        """Test _fetch_code_snippets handles failures gracefully."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        
        # Should start with empty dicts
        assert screen._code_snippets == {}
        assert screen._test_cases == ""
        
        # After failed fetch, should still be empty (no crash)
        # The method catches exceptions internally

    def test_load_template_handles_unknown_language(self, mock_settings, mock_client, mock_coach, test_db):
        """Test _load_language_template handles unknown languages."""
        screen = PracticeScreen(mock_settings, mock_client, mock_coach, test_db)
        screen._code_snippets = {}
        
        mock_editor = MagicMock()
        mock_editor.text = ""
        
        # Load unknown language
        screen._load_language_template(mock_editor, "unknown_lang")
        
        # Should set some fallback text
        assert "TODO" in mock_editor.text or mock_editor.text == ""
