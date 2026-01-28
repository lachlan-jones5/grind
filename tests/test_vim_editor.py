"""Comprehensive tests for VimEditor widget."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from grind.tui.vim_editor import VimEditor, VimMode


# =============================================================================
# VimMode Enum Tests
# =============================================================================

class TestVimModeEnum:
    """Tests for VimMode enum."""

    def test_normal_mode_value(self):
        """Test NORMAL mode value."""
        assert VimMode.NORMAL.value == "NORMAL"

    def test_insert_mode_value(self):
        """Test INSERT mode value."""
        assert VimMode.INSERT.value == "INSERT"

    def test_visual_mode_value(self):
        """Test VISUAL mode value."""
        assert VimMode.VISUAL.value == "VISUAL"

    def test_command_mode_value(self):
        """Test COMMAND mode value."""
        assert VimMode.COMMAND.value == "COMMAND"

    def test_vim_mode_count(self):
        """Test correct number of modes."""
        assert len(VimMode) == 4

    def test_modes_are_unique(self):
        """Test all mode values are unique."""
        values = [mode.value for mode in VimMode]
        assert len(values) == len(set(values))

    def test_mode_comparison(self):
        """Test mode comparison works."""
        assert VimMode.NORMAL == VimMode.NORMAL
        assert VimMode.NORMAL != VimMode.INSERT

    def test_mode_identity(self):
        """Test mode identity."""
        mode = VimMode.NORMAL
        assert mode is VimMode.NORMAL


# =============================================================================
# VimEditor Class Tests
# =============================================================================

class TestVimEditorClass:
    """Tests for VimEditor class attributes."""

    def test_vim_editor_has_bindings(self):
        """Test VimEditor has BINDINGS attribute."""
        assert hasattr(VimEditor, "BINDINGS")

    def test_vim_editor_bindings_is_list(self):
        """Test BINDINGS is a list."""
        assert isinstance(VimEditor.BINDINGS, list)

    def test_vim_editor_is_textarea_subclass(self):
        """Test VimEditor extends TextArea."""
        from textual.widgets import TextArea
        assert issubclass(VimEditor, TextArea)

    def test_vim_editor_has_on_key_method(self):
        """Test VimEditor has on_key method."""
        assert hasattr(VimEditor, "on_key")
        assert callable(getattr(VimEditor, "on_key"))

    def test_vim_editor_has_mode_display_property(self):
        """Test VimEditor has mode_display property."""
        assert hasattr(VimEditor, "mode_display")

    def test_vim_editor_has_set_language_method(self):
        """Test VimEditor has set_language method."""
        assert hasattr(VimEditor, "set_language")
        assert callable(getattr(VimEditor, "set_language"))


# =============================================================================
# VimEditor Initialization Tests
# =============================================================================

class TestVimEditorInit:
    """Tests for VimEditor initialization."""

    def test_editor_init_default_language(self):
        """Test editor initializes with default C++ language."""
        editor = VimEditor()
        assert editor.code_language == "cpp"

    def test_editor_init_cpp(self):
        """Test editor initializes with C++ template."""
        editor = VimEditor(language="cpp")
        assert editor.code_language == "cpp"
        assert "class Solution" in editor.text
        assert "#include" in editor.text

    def test_editor_init_rust(self):
        """Test editor initializes with Rust template."""
        editor = VimEditor(language="rust")
        assert editor.code_language == "rust"
        assert "impl Solution" in editor.text
        assert "pub fn" in editor.text

    def test_editor_init_ocaml(self):
        """Test editor initializes with OCaml template."""
        editor = VimEditor(language="ocaml")
        assert editor.code_language == "ocaml"
        assert "let solve" in editor.text

    def test_editor_init_unknown_language(self):
        """Test editor with unknown language uses empty template."""
        editor = VimEditor(language="python")
        assert editor.code_language == "python"
        assert editor.text == ""

    def test_editor_init_empty_language(self):
        """Test editor with empty language."""
        editor = VimEditor(language="")
        assert editor.code_language == ""
        assert editor.text == ""

    def test_editor_starts_in_normal_mode(self):
        """Test editor starts in NORMAL mode."""
        editor = VimEditor()
        assert editor.vim_mode == VimMode.NORMAL

    def test_editor_yanked_text_empty(self):
        """Test yanked text starts empty."""
        editor = VimEditor()
        assert editor.yanked_text == ""

    def test_editor_pending_keys_empty(self):
        """Test pending keys starts empty."""
        editor = VimEditor()
        assert editor.pending_keys == ""

    def test_editor_last_search_empty(self):
        """Test last search starts empty."""
        editor = VimEditor()
        assert editor.last_search == ""


# =============================================================================
# Mode Display Tests
# =============================================================================

class TestVimEditorModeDisplay:
    """Tests for mode_display property."""

    def test_mode_display_normal(self):
        """Test mode display in NORMAL mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.NORMAL
        display = editor.mode_display
        assert "NORMAL" in display
        assert "--" in display

    def test_mode_display_insert(self):
        """Test mode display in INSERT mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.INSERT
        display = editor.mode_display
        assert "INSERT" in display
        assert "--" in display

    def test_mode_display_visual(self):
        """Test mode display in VISUAL mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.VISUAL
        display = editor.mode_display
        assert "VISUAL" in display
        assert "--" in display

    def test_mode_display_command(self):
        """Test mode display in COMMAND mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.COMMAND
        display = editor.mode_display
        assert "COMMAND" in display
        assert "--" in display

    def test_mode_display_format(self):
        """Test mode display has correct format."""
        editor = VimEditor()
        display = editor.mode_display
        assert display.startswith("--")
        assert display.endswith("--")


# =============================================================================
# Set Language Tests
# =============================================================================

class TestVimEditorSetLanguage:
    """Tests for set_language method."""

    def test_set_language_cpp(self):
        """Test switching to C++."""
        editor = VimEditor(language="rust")
        editor.set_language("cpp")
        assert editor.code_language == "cpp"
        assert "class Solution" in editor.text

    def test_set_language_rust(self):
        """Test switching to Rust."""
        editor = VimEditor(language="cpp")
        editor.set_language("rust")
        assert editor.code_language == "rust"
        assert "impl Solution" in editor.text

    def test_set_language_ocaml(self):
        """Test switching to OCaml."""
        editor = VimEditor(language="cpp")
        editor.set_language("ocaml")
        assert editor.code_language == "ocaml"
        assert "let solve" in editor.text

    def test_set_language_unknown(self):
        """Test switching to unknown language."""
        editor = VimEditor(language="cpp")
        editor.set_language("unknown")
        assert editor.code_language == "unknown"
        assert editor.text == ""

    def test_set_language_replaces_content(self):
        """Test set_language replaces existing content."""
        editor = VimEditor(language="cpp")
        original_text = editor.text
        editor.text = "custom code"
        editor.set_language("rust")
        assert editor.text != "custom code"
        assert editor.text != original_text


# =============================================================================
# Yanked Text Tests
# =============================================================================

class TestVimEditorYankedText:
    """Tests for yanked text functionality."""

    def test_yanked_text_can_be_set(self):
        """Test yanked text can be stored."""
        editor = VimEditor()
        editor.yanked_text = "test line\n"
        assert editor.yanked_text == "test line\n"

    def test_yanked_text_persists(self):
        """Test yanked text persists across operations."""
        editor = VimEditor()
        editor.yanked_text = "persistent"
        editor.vim_mode = VimMode.INSERT
        editor.vim_mode = VimMode.NORMAL
        assert editor.yanked_text == "persistent"

    def test_yanked_text_can_be_multiline(self):
        """Test yanked text can contain multiple lines."""
        editor = VimEditor()
        editor.yanked_text = "line1\nline2\nline3\n"
        assert "line1" in editor.yanked_text
        assert "line2" in editor.yanked_text
        assert "line3" in editor.yanked_text

    def test_yanked_text_empty_string(self):
        """Test yanked text can be empty."""
        editor = VimEditor()
        editor.yanked_text = "something"
        editor.yanked_text = ""
        assert editor.yanked_text == ""


# =============================================================================
# Pending Keys Tests
# =============================================================================

class TestVimEditorPendingKeys:
    """Tests for pending key handling."""

    def test_pending_keys_default_empty(self):
        """Test pending keys start empty."""
        editor = VimEditor()
        assert editor.pending_keys == ""

    def test_pending_keys_single_char(self):
        """Test pending keys with single character."""
        editor = VimEditor()
        editor.pending_keys = "d"
        assert editor.pending_keys == "d"

    def test_pending_keys_g(self):
        """Test pending key 'g' for gg command."""
        editor = VimEditor()
        editor.pending_keys = "g"
        assert editor.pending_keys == "g"

    def test_pending_keys_y(self):
        """Test pending key 'y' for yy command."""
        editor = VimEditor()
        editor.pending_keys = "y"
        assert editor.pending_keys == "y"

    def test_pending_keys_can_be_cleared(self):
        """Test pending keys can be cleared."""
        editor = VimEditor()
        editor.pending_keys = "d"
        editor.pending_keys = ""
        assert editor.pending_keys == ""


# =============================================================================
# Delete Methods Tests
# =============================================================================

class TestVimEditorDeleteMethods:
    """Tests for delete functionality."""

    def test_delete_char_method_exists(self):
        """Test _delete_char method exists."""
        assert hasattr(VimEditor, "_delete_char")

    def test_delete_line_method_exists(self):
        """Test _delete_line method exists."""
        assert hasattr(VimEditor, "_delete_line")

    def test_delete_word_method_exists(self):
        """Test _delete_word method exists."""
        assert hasattr(VimEditor, "_delete_word")


# =============================================================================
# Yank Methods Tests
# =============================================================================

class TestVimEditorYankMethods:
    """Tests for yank functionality."""

    def test_yank_line_method_exists(self):
        """Test _yank_line method exists."""
        assert hasattr(VimEditor, "_yank_line")


# =============================================================================
# Paste Methods Tests
# =============================================================================

class TestVimEditorPasteMethods:
    """Tests for paste functionality."""

    def test_paste_after_method_exists(self):
        """Test _paste_after method exists."""
        assert hasattr(VimEditor, "_paste_after")

    def test_paste_before_method_exists(self):
        """Test _paste_before method exists."""
        assert hasattr(VimEditor, "_paste_before")


# =============================================================================
# Key Handler Methods Tests
# =============================================================================

class TestVimEditorKeyHandlers:
    """Tests for key handler methods."""

    def test_handle_insert_mode_exists(self):
        """Test _handle_insert_mode method exists."""
        assert hasattr(VimEditor, "_handle_insert_mode")

    def test_handle_normal_mode_exists(self):
        """Test _handle_normal_mode method exists."""
        assert hasattr(VimEditor, "_handle_normal_mode")

    def test_handle_visual_mode_exists(self):
        """Test _handle_visual_mode method exists."""
        assert hasattr(VimEditor, "_handle_visual_mode")

    def test_handle_pending_key_exists(self):
        """Test _handle_pending_key method exists."""
        assert hasattr(VimEditor, "_handle_pending_key")

    def test_on_key_is_async(self):
        """Test on_key is an async method."""
        import asyncio
        assert asyncio.iscoroutinefunction(VimEditor.on_key)


# =============================================================================
# Mode Transition Tests
# =============================================================================

class TestVimEditorModeTransitions:
    """Tests for mode transitions."""

    def test_normal_to_insert(self):
        """Test transition from NORMAL to INSERT."""
        editor = VimEditor()
        assert editor.vim_mode == VimMode.NORMAL
        editor.vim_mode = VimMode.INSERT
        assert editor.vim_mode == VimMode.INSERT

    def test_insert_to_normal(self):
        """Test transition from INSERT to NORMAL."""
        editor = VimEditor()
        editor.vim_mode = VimMode.INSERT
        editor.vim_mode = VimMode.NORMAL
        assert editor.vim_mode == VimMode.NORMAL

    def test_normal_to_visual(self):
        """Test transition from NORMAL to VISUAL."""
        editor = VimEditor()
        editor.vim_mode = VimMode.VISUAL
        assert editor.vim_mode == VimMode.VISUAL

    def test_visual_to_normal(self):
        """Test transition from VISUAL to NORMAL."""
        editor = VimEditor()
        editor.vim_mode = VimMode.VISUAL
        editor.vim_mode = VimMode.NORMAL
        assert editor.vim_mode == VimMode.NORMAL


# =============================================================================
# Template Content Tests
# =============================================================================

class TestVimEditorTemplates:
    """Tests for language templates content."""

    def test_cpp_template_has_includes(self):
        """Test C++ template has proper includes."""
        editor = VimEditor(language="cpp")
        assert "#include <bits/stdc++.h>" in editor.text

    def test_cpp_template_has_namespace(self):
        """Test C++ template has namespace."""
        editor = VimEditor(language="cpp")
        assert "using namespace std" in editor.text

    def test_cpp_template_has_solution_class(self):
        """Test C++ template has Solution class."""
        editor = VimEditor(language="cpp")
        assert "class Solution" in editor.text

    def test_cpp_template_has_todo(self):
        """Test C++ template has TODO marker."""
        editor = VimEditor(language="cpp")
        assert "TODO" in editor.text

    def test_rust_template_has_impl(self):
        """Test Rust template has impl block."""
        editor = VimEditor(language="rust")
        assert "impl Solution" in editor.text

    def test_rust_template_has_pub_fn(self):
        """Test Rust template has public function."""
        editor = VimEditor(language="rust")
        assert "pub fn" in editor.text

    def test_ocaml_template_has_let(self):
        """Test OCaml template has let binding."""
        editor = VimEditor(language="ocaml")
        assert "let solve" in editor.text

    def test_ocaml_template_has_comment(self):
        """Test OCaml template has comment."""
        editor = VimEditor(language="ocaml")
        assert "(*" in editor.text
