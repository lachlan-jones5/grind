"""Tests for VimEditor widget."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from grind.tui.vim_editor import VimEditor, VimMode


class TestVimMode:
    """Tests for vim mode enum."""

    def test_vim_modes(self):
        """Test all vim modes exist."""
        assert VimMode.NORMAL.value == "NORMAL"
        assert VimMode.INSERT.value == "INSERT"
        assert VimMode.VISUAL.value == "VISUAL"
        assert VimMode.COMMAND.value == "COMMAND"

    def test_vim_mode_count(self):
        """Test correct number of modes."""
        assert len(VimMode) == 4


class TestVimEditorClass:
    """Tests for VimEditor class attributes."""

    def test_vim_editor_has_bindings(self):
        """Test VimEditor has BINDINGS attribute."""
        assert hasattr(VimEditor, "BINDINGS")

    def test_vim_editor_is_textarea_subclass(self):
        """Test VimEditor extends TextArea."""
        from textual.widgets import TextArea
        assert issubclass(VimEditor, TextArea)


# Note: VimEditor instantiation tests require a running Textual app context,
# so we skip direct instantiation tests here. The widget is tested through
# the TUI integration tests.
