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
        assert len(VimMode) == 5

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


# =============================================================================
# Visual Line Mode Tests
# =============================================================================

class TestVimEditorVisualLineMode:
    """Tests for VISUAL LINE mode."""

    def test_visual_line_mode_value(self):
        """Test VISUAL LINE mode value."""
        assert VimMode.VISUAL_LINE.value == "VISUAL LINE"

    def test_mode_count_includes_visual_line(self):
        """Test correct number of modes with VISUAL LINE."""
        assert len(VimMode) == 5

    def test_visual_line_transition(self):
        """Test transition to VISUAL LINE mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.VISUAL_LINE
        assert editor.vim_mode == VimMode.VISUAL_LINE

    def test_visual_start_attribute(self):
        """Test visual_start attribute exists."""
        editor = VimEditor()
        assert hasattr(editor, "visual_start")
        assert editor.visual_start is None


# =============================================================================
# Count Prefix Tests
# =============================================================================

class TestVimEditorCountPrefix:
    """Tests for count prefix functionality (e.g., 3j, 5dd)."""

    def test_count_buffer_attribute_exists(self):
        """Test count_buffer attribute exists."""
        editor = VimEditor()
        assert hasattr(editor, "count_buffer")

    def test_count_buffer_starts_empty(self):
        """Test count buffer starts empty."""
        editor = VimEditor()
        assert editor.count_buffer == ""

    def test_count_buffer_can_store_digits(self):
        """Test count buffer can store digits."""
        editor = VimEditor()
        editor.count_buffer = "123"
        assert editor.count_buffer == "123"

    def test_get_count_method_exists(self):
        """Test _get_count method exists."""
        assert hasattr(VimEditor, "_get_count")

    def test_get_count_returns_default_one(self):
        """Test _get_count returns 1 when buffer is empty."""
        editor = VimEditor()
        count = editor._get_count()
        assert count == 1

    def test_get_count_clears_buffer(self):
        """Test _get_count clears the buffer."""
        editor = VimEditor()
        editor.count_buffer = "5"
        editor._get_count()
        assert editor.count_buffer == ""

    def test_get_count_returns_buffer_value(self):
        """Test _get_count returns correct value."""
        editor = VimEditor()
        editor.count_buffer = "42"
        count = editor._get_count()
        assert count == 42


# =============================================================================
# Find Character Tests
# =============================================================================

class TestVimEditorFindChar:
    """Tests for f/F/t/T character search."""

    def test_last_find_char_attribute(self):
        """Test last_find_char attribute exists."""
        editor = VimEditor()
        assert hasattr(editor, "last_find_char")
        assert editor.last_find_char == ""

    def test_last_find_forward_attribute(self):
        """Test last_find_forward attribute exists."""
        editor = VimEditor()
        assert hasattr(editor, "last_find_forward")
        assert editor.last_find_forward is True

    def test_last_find_till_attribute(self):
        """Test last_find_till attribute exists."""
        editor = VimEditor()
        assert hasattr(editor, "last_find_till")
        assert editor.last_find_till is False

    def test_find_char_method_exists(self):
        """Test _find_char method exists."""
        assert hasattr(VimEditor, "_find_char")

    def test_find_char_saves_last_search(self):
        """Test _find_char saves the last search character."""
        editor = VimEditor()
        editor.text = "hello world"
        editor.move_cursor((0, 0))
        editor._find_char("w", forward=True, till=False)
        assert editor.last_find_char == "w"
        assert editor.last_find_forward is True
        assert editor.last_find_till is False


# =============================================================================
# Motion Command Tests
# =============================================================================

class TestVimEditorMotions:
    """Tests for vim motion commands."""

    def test_move_word_forward_exists(self):
        """Test _move_word_forward method exists."""
        assert hasattr(VimEditor, "_move_word_forward")

    def test_move_word_backward_exists(self):
        """Test _move_word_backward method exists."""
        assert hasattr(VimEditor, "_move_word_backward")

    def test_move_word_end_exists(self):
        """Test _move_word_end method exists."""
        assert hasattr(VimEditor, "_move_word_end")

    def test_move_paragraph_up_exists(self):
        """Test _move_paragraph_up method exists."""
        assert hasattr(VimEditor, "_move_paragraph_up")

    def test_move_paragraph_down_exists(self):
        """Test _move_paragraph_down method exists."""
        assert hasattr(VimEditor, "_move_paragraph_down")

    def test_move_to_first_nonblank_exists(self):
        """Test _move_to_first_nonblank method exists."""
        assert hasattr(VimEditor, "_move_to_first_nonblank")

    def test_current_line_method_exists(self):
        """Test _current_line method exists."""
        assert hasattr(VimEditor, "_current_line")

    def test_current_line_returns_string(self):
        """Test _current_line returns the current line."""
        editor = VimEditor()
        editor.text = "line one\nline two\nline three"
        editor.move_cursor((1, 0))
        line = editor._current_line()
        assert line == "line two"


# =============================================================================
# Edit Command Tests
# =============================================================================

class TestVimEditorEditCommands:
    """Tests for vim edit commands."""

    def test_replace_char_exists(self):
        """Test _replace_char method exists."""
        assert hasattr(VimEditor, "_replace_char")

    def test_delete_char_before_exists(self):
        """Test _delete_char_before method exists."""
        assert hasattr(VimEditor, "_delete_char_before")

    def test_delete_to_line_start_exists(self):
        """Test _delete_to_line_start method exists."""
        assert hasattr(VimEditor, "_delete_to_line_start")

    def test_delete_to_line_end_exists(self):
        """Test _delete_to_line_end method exists."""
        assert hasattr(VimEditor, "_delete_to_line_end")

    def test_delete_line_content_exists(self):
        """Test _delete_line_content method exists."""
        assert hasattr(VimEditor, "_delete_line_content")

    def test_delete_to_document_start_exists(self):
        """Test _delete_to_document_start method exists."""
        assert hasattr(VimEditor, "_delete_to_document_start")

    def test_delete_word_before_exists(self):
        """Test _delete_word_before method exists."""
        assert hasattr(VimEditor, "_delete_word_before")

    def test_yank_word_exists(self):
        """Test _yank_word method exists."""
        assert hasattr(VimEditor, "_yank_word")

    def test_join_lines_exists(self):
        """Test _join_lines method exists."""
        assert hasattr(VimEditor, "_join_lines")

    def test_toggle_case_exists(self):
        """Test _toggle_case method exists."""
        assert hasattr(VimEditor, "_toggle_case")

    def test_indent_line_exists(self):
        """Test _indent_line method exists."""
        assert hasattr(VimEditor, "_indent_line")

    def test_outdent_line_exists(self):
        """Test _outdent_line method exists."""
        assert hasattr(VimEditor, "_outdent_line")


# =============================================================================
# Visual Selection Tests
# =============================================================================

class TestVimEditorVisualSelection:
    """Tests for visual selection functionality."""

    def test_get_selection_range_exists(self):
        """Test _get_selection_range method exists."""
        assert hasattr(VimEditor, "_get_selection_range")

    def test_get_selection_range_none_when_no_visual_start(self):
        """Test _get_selection_range returns None when not in visual mode."""
        editor = VimEditor()
        assert editor._get_selection_range() is None

    def test_delete_visual_selection_exists(self):
        """Test _delete_visual_selection method exists."""
        assert hasattr(VimEditor, "_delete_visual_selection")

    def test_yank_visual_selection_exists(self):
        """Test _yank_visual_selection method exists."""
        assert hasattr(VimEditor, "_yank_visual_selection")

    def test_indent_visual_selection_exists(self):
        """Test _indent_visual_selection method exists."""
        assert hasattr(VimEditor, "_indent_visual_selection")

    def test_outdent_visual_selection_exists(self):
        """Test _outdent_visual_selection method exists."""
        assert hasattr(VimEditor, "_outdent_visual_selection")

    def test_toggle_case_visual_selection_exists(self):
        """Test _toggle_case_visual_selection method exists."""
        assert hasattr(VimEditor, "_toggle_case_visual_selection")


# =============================================================================
# Enter Insert Mode Tests
# =============================================================================

class TestVimEditorEnterInsertMode:
    """Tests for entering insert mode."""

    def test_enter_insert_mode_exists(self):
        """Test _enter_insert_mode method exists."""
        assert hasattr(VimEditor, "_enter_insert_mode")

    def test_enter_insert_mode_changes_mode(self):
        """Test _enter_insert_mode changes to INSERT mode."""
        editor = VimEditor()
        editor._enter_insert_mode()
        assert editor.vim_mode == VimMode.INSERT


# =============================================================================
# Mode Display with Pending Keys Tests
# =============================================================================

class TestVimEditorModeDisplayExtended:
    """Extended tests for mode display with pending keys and count."""

    def test_mode_display_with_pending_key(self):
        """Test mode display shows pending key."""
        editor = VimEditor()
        editor.pending_keys = "d"
        display = editor.mode_display
        assert "d" in display

    def test_mode_display_with_count_buffer(self):
        """Test mode display shows count buffer."""
        editor = VimEditor()
        editor.count_buffer = "5"
        display = editor.mode_display
        assert "5" in display

    def test_mode_display_with_count_and_pending(self):
        """Test mode display shows both count and pending."""
        editor = VimEditor()
        editor.count_buffer = "3"
        editor.pending_keys = "d"
        display = editor.mode_display
        assert "3" in display
        assert "d" in display


# =============================================================================
# Delete To Word End Tests
# =============================================================================

class TestVimEditorDeleteToWordEnd:
    """Tests for delete to word end."""

    def test_delete_to_word_end_exists(self):
        """Test _delete_to_word_end method exists."""
        assert hasattr(VimEditor, "_delete_to_word_end")


# =============================================================================
# Move Word End Backward Tests
# =============================================================================

class TestVimEditorMoveWordEndBackward:
    """Tests for move word end backward (ge command)."""

    def test_move_word_end_backward_exists(self):
        """Test _move_word_end_backward method exists."""
        assert hasattr(VimEditor, "_move_word_end_backward")


# =============================================================================
# Cursor Style Tests
# =============================================================================

class TestVimEditorCursorStyle:
    """Tests for vim editor cursor styling."""

    def test_update_cursor_style_method_exists(self):
        """Test _update_cursor_style method exists."""
        assert hasattr(VimEditor, "_update_cursor_style")

    def test_normal_mode_cursor_no_blink(self):
        """Test cursor doesn't blink in NORMAL mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.NORMAL
        editor._update_cursor_style()
        assert editor.cursor_blink is False

    def test_insert_mode_cursor_blinks(self):
        """Test cursor blinks in INSERT mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.INSERT
        editor._update_cursor_style()
        assert editor.cursor_blink is True

    def test_visual_mode_cursor_no_blink(self):
        """Test cursor doesn't blink in VISUAL mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.VISUAL
        editor._update_cursor_style()
        assert editor.cursor_blink is False

    def test_visual_line_mode_cursor_no_blink(self):
        """Test cursor doesn't blink in VISUAL LINE mode."""
        editor = VimEditor()
        editor.vim_mode = VimMode.VISUAL_LINE
        editor._update_cursor_style()
        assert editor.cursor_blink is False

    def test_initial_cursor_style_is_normal(self):
        """Test initial cursor style is set for NORMAL mode."""
        editor = VimEditor()
        assert editor.cursor_blink is False

    def test_enter_insert_mode_updates_cursor(self):
        """Test entering insert mode updates cursor style."""
        editor = VimEditor()
        assert editor.cursor_blink is False
        editor._enter_insert_mode()
        assert editor.cursor_blink is True

    def test_default_css_defined(self):
        """Test DEFAULT_CSS is defined."""
        assert hasattr(VimEditor, "DEFAULT_CSS")
        assert VimEditor.DEFAULT_CSS is not None
