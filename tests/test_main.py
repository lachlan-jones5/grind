"""Comprehensive tests for main CLI entry point."""

import pytest
import sys
from unittest.mock import patch, MagicMock

from grind.main import main


# =============================================================================
# CLI Argument Tests
# =============================================================================

class TestCLIVersion:
    """Tests for --version flag."""

    def test_version_flag(self):
        """Test --version prints version and exits."""
        with patch.object(sys, "argv", ["grind", "--version"]):
            with patch("builtins.print") as mock_print:
                result = main()

                assert result == 0
                mock_print.assert_called_once()
                call_args = mock_print.call_args[0][0]
                assert "grind" in call_args
                assert "0.1.0" in call_args


class TestCLIProvider:
    """Tests for --provider flag."""

    def test_provider_copilot(self):
        """Test --provider copilot sets env var."""
        with patch.object(sys, "argv", ["grind", "--provider", "copilot"]):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_PROVIDER") == "copilot"

    def test_provider_openrouter(self):
        """Test --provider openrouter sets env var."""
        with patch.object(sys, "argv", ["grind", "--provider", "openrouter"]):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_PROVIDER") == "openrouter"


class TestCLILanguage:
    """Tests for --language flag."""

    def test_language_cpp(self):
        """Test --language cpp sets env var."""
        with patch.object(sys, "argv", ["grind", "--language", "cpp"]):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_DEFAULT_LANGUAGE") == "cpp"

    def test_language_rust(self):
        """Test --language rust sets env var."""
        with patch.object(sys, "argv", ["grind", "--language", "rust"]):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_DEFAULT_LANGUAGE") == "rust"

    def test_language_ocaml(self):
        """Test --language ocaml sets env var."""
        with patch.object(sys, "argv", ["grind", "--language", "ocaml"]):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_DEFAULT_LANGUAGE") == "ocaml"


class TestCLIRelayURL:
    """Tests for --relay-url flag."""

    def test_relay_url_custom(self):
        """Test --relay-url sets env var."""
        with patch.object(sys, "argv", ["grind", "--relay-url", "http://custom:9000"]):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_COPILOT_RELAY_URL") == "http://custom:9000"


class TestCLICombined:
    """Tests for combined CLI flags."""

    def test_all_flags_together(self):
        """Test all flags can be used together."""
        args = [
            "grind",
            "--provider", "openrouter",
            "--language", "rust",
            "--relay-url", "http://test:8080",
        ]
        with patch.object(sys, "argv", args):
            with patch("grind.tui.app.run") as mock_run:
                with patch.dict("os.environ", {}, clear=True):
                    import os
                    main()
                    assert os.environ.get("GRIND_PROVIDER") == "openrouter"
                    assert os.environ.get("GRIND_DEFAULT_LANGUAGE") == "rust"
                    assert os.environ.get("GRIND_COPILOT_RELAY_URL") == "http://test:8080"


class TestCLINoArgs:
    """Tests for CLI with no arguments."""

    def test_no_args_runs_tui(self):
        """Test running with no args starts TUI."""
        with patch.object(sys, "argv", ["grind"]):
            with patch("grind.tui.app.run") as mock_run:
                result = main()

                mock_run.assert_called_once()
                assert result == 0


class TestCLIRunsApp:
    """Tests that CLI runs the application."""

    def test_main_calls_run(self):
        """Test main calls run function."""
        with patch.object(sys, "argv", ["grind"]):
            with patch("grind.tui.app.run") as mock_run:
                main()
                mock_run.assert_called_once()

    def test_main_returns_zero(self):
        """Test main returns 0 on success."""
        with patch.object(sys, "argv", ["grind"]):
            with patch("grind.tui.app.run"):
                result = main()
                assert result == 0
