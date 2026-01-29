"""Vim-style editor widget for code editing."""

from enum import Enum
from textual.widgets import TextArea
from textual.binding import Binding
from textual import events


class VimMode(Enum):
    """Vim editing modes."""
    NORMAL = "NORMAL"
    INSERT = "INSERT"
    VISUAL = "VISUAL"
    VISUAL_LINE = "VISUAL LINE"
    COMMAND = "COMMAND"


class VimEditor(TextArea):
    """TextArea with vim-style keybindings.
    
    Modes:
    - NORMAL: Navigate and edit with vim motions
    - INSERT: Type text normally
    - VISUAL: Character-wise visual selection
    - VISUAL_LINE: Line-wise visual selection
    
    Normal mode commands:
    - i, I: Enter insert mode (at cursor / at line start)
    - a, A: Enter insert mode (after cursor / at line end)
    - o, O: Open new line below/above
    - h, j, k, l: Move cursor
    - w, b, e: Word motions
    - W, B, E: WORD motions (whitespace-delimited)
    - 0, ^, $: Line start / first non-blank / line end
    - gg, G: Document start/end
    - {, }: Paragraph up/down
    - f{char}, F{char}: Find character forward/backward
    - t{char}, T{char}: Till character forward/backward
    - ;, ,: Repeat last f/F/t/T motion
    - x, X: Delete character under/before cursor
    - r{char}: Replace character under cursor
    - s, S: Substitute character / line
    - dd: Delete line
    - D: Delete to end of line
    - cc: Change line
    - C: Change to end of line
    - yy, Y: Yank line
    - yw, yW: Yank word
    - p, P: Paste after/before
    - u: Undo
    - Ctrl+r: Redo
    - J: Join lines
    - ~: Toggle case
    - >>, <<: Indent/outdent
    - v: Enter visual mode
    - V: Enter visual line mode
    
    Visual mode:
    - Escape: Return to normal mode
    - d, x: Delete selection
    - y: Yank selection
    - c: Change selection
    - >, <: Indent/outdent selection
    - ~: Toggle case of selection
    - o: Move to other end of selection
    
    Insert mode:
    - Escape: Return to normal mode
    - Ctrl+w: Delete word before cursor
    - Ctrl+u: Delete to start of line
    """
    
    BINDINGS = []
    
    # CSS for cursor styling
    # Note: Textual TextArea cursor styling is limited, but we can control blink
    DEFAULT_CSS = """
    VimEditor {
        /* Default styling for vim editor */
    }
    
    VimEditor:focus {
        /* Cursor is visible when focused */
    }
    """
    
    def __init__(self, language: str = "cpp", **kwargs):
        super().__init__(**kwargs)
        self.code_language = language
        self.vim_mode = VimMode.NORMAL
        self.yanked_text = ""
        self.pending_keys = ""
        self.last_search = ""
        self.last_find_char = ""
        self.last_find_forward = True
        self.last_find_till = False
        self.visual_start: tuple[int, int] | None = None
        self.count_buffer = ""  # For count prefix (e.g., 3j)
        
        # Set cursor style for NORMAL mode (thin line, not blinking)
        self.cursor_blink = False
        self._update_cursor_style()
        
        # Set initial text
        from grind.tui.app import LANGUAGE_TEMPLATES
        self.text = LANGUAGE_TEMPLATES.get(language, "")
    
    def _update_cursor_style(self) -> None:
        """Update cursor style based on current vim mode.
        
        - NORMAL: Thin line (bar), no blink
        - INSERT: Block cursor, blinking
        - VISUAL/VISUAL_LINE: Block cursor, no blink
        """
        if self.vim_mode == VimMode.INSERT:
            self.cursor_blink = True
            # TextArea uses "block" type by default, but we want block for INSERT
            # In Textual, we can use CSS or the cursor_type if available
        else:
            self.cursor_blink = False
        
    @property
    def mode_display(self) -> str:
        """Get display string for current mode."""
        count_prefix = self.count_buffer if self.count_buffer else ""
        pending = self.pending_keys if self.pending_keys else ""
        mode_str = f"-- {self.vim_mode.value} --"
        if count_prefix or pending:
            mode_str += f"  {count_prefix}{pending}"
        return mode_str
    
    def set_language(self, language: str) -> None:
        """Change the editor language."""
        from grind.tui.app import LANGUAGE_TEMPLATES
        self.code_language = language
        self.text = LANGUAGE_TEMPLATES.get(language, "")
    
    def _get_count(self) -> int:
        """Get the count prefix (default 1)."""
        if self.count_buffer:
            count = int(self.count_buffer)
            self.count_buffer = ""
            return count
        return 1
    
    def _current_line(self) -> str:
        """Get the current line text."""
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            return lines[row]
        return ""
    
    def _get_selection_range(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Get the visual selection range as (start, end)."""
        if self.visual_start is None:
            return None
        current = self.cursor_location
        start = self.visual_start
        # Normalize so start <= end
        if (start[0], start[1]) <= (current[0], current[1]):
            return (start, current)
        return (current, start)
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key events for vim mode."""
        if self.vim_mode == VimMode.INSERT:
            await self._handle_insert_mode(event)
        elif self.vim_mode == VimMode.NORMAL:
            await self._handle_normal_mode(event)
        elif self.vim_mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
            await self._handle_visual_mode(event)
    
    async def _handle_insert_mode(self, event: events.Key) -> None:
        """Handle keys in insert mode."""
        if event.key == "escape":
            self.vim_mode = VimMode.NORMAL
            self._update_cursor_style()
            # Move cursor back one if possible
            row, col = self.cursor_location
            if col > 0:
                self.move_cursor((row, col - 1))
            event.prevent_default()
            event.stop()
            self.refresh()
        elif event.key == "ctrl+w":
            # Delete word before cursor
            event.prevent_default()
            event.stop()
            self._delete_word_before()
            self.refresh()
        elif event.key == "ctrl+u":
            # Delete to start of line
            event.prevent_default()
            event.stop()
            self._delete_to_line_start()
            self.refresh()
        # Let other keys pass through to TextArea for normal editing
    
    async def _handle_normal_mode(self, event: events.Key) -> None:
        """Handle keys in normal mode."""
        key = event.key
        char = event.character
        
        # Always prevent default in normal mode
        event.prevent_default()
        event.stop()
        
        # Handle count prefix (digits except when starting with 0)
        if char and char.isdigit() and (self.count_buffer or char != "0"):
            self.count_buffer += char
            self.refresh()
            return
        
        # Check for pending keys (like gg, dd, yy, f{char}, etc.)
        if self.pending_keys:
            await self._handle_pending_key(key, char)
            return
        
        count = self._get_count()
        
        # Mode switching
        if key == "i":
            self._enter_insert_mode()
            return
        elif key == "I":
            self._move_to_first_nonblank()
            self._enter_insert_mode()
            return
        elif key == "a":
            row, col = self.cursor_location
            lines = self.text.splitlines()
            if row < len(lines) and col < len(lines[row]):
                self.move_cursor((row, col + 1))
            self._enter_insert_mode()
            return
        elif key == "A":
            self.action_cursor_line_end()
            self._enter_insert_mode()
            return
        elif key == "o":
            self.action_cursor_line_end()
            self.insert("\n")
            self._enter_insert_mode()
            return
        elif key == "O":
            self.action_cursor_line_start()
            self.insert("\n")
            self.action_cursor_up()
            self._enter_insert_mode()
            return
        elif key == "s":
            # Substitute character
            self._delete_char()
            self._enter_insert_mode()
            return
        elif key == "S":
            # Substitute line
            self._delete_line_content()
            self._enter_insert_mode()
            return
        elif key == "v":
            self.vim_mode = VimMode.VISUAL
            self.visual_start = self.cursor_location
            self.refresh()
            return
        elif key == "V":
            self.vim_mode = VimMode.VISUAL_LINE
            self.visual_start = self.cursor_location
            self.refresh()
            return
        
        # Motion commands (with count)
        for _ in range(count):
            if key == "h":
                self.action_cursor_left()
            elif key == "j":
                self.action_cursor_down()
            elif key == "k":
                self.action_cursor_up()
            elif key == "l":
                self.action_cursor_right()
            elif key == "w":
                self._move_word_forward()
            elif key == "W":
                self._move_word_forward(word=True)
            elif key == "b":
                self._move_word_backward()
            elif key == "B":
                self._move_word_backward(word=True)
            elif key == "e":
                self._move_word_end()
            elif key == "E":
                self._move_word_end(word=True)
        
        # Line navigation
        if key == "0":
            self.action_cursor_line_start()
        elif key == "asciicircum" or key == "^":
            self._move_to_first_nonblank()
        elif key == "dollar" or key == "$":
            self.action_cursor_line_end()
        elif key == "g":
            self.pending_keys = "g"
        elif key == "G":
            lines = self.text.splitlines()
            if lines:
                self.move_cursor((len(lines) - 1, 0))
        elif key == "braceleft" or key == "{":
            for _ in range(count):
                self._move_paragraph_up()
        elif key == "braceright" or key == "}":
            for _ in range(count):
                self._move_paragraph_down()
        
        # Find character commands
        elif key == "f":
            self.pending_keys = "f"
        elif key == "F":
            self.pending_keys = "F"
        elif key == "t":
            self.pending_keys = "t"
        elif key == "T":
            self.pending_keys = "T"
        elif key == "semicolon" or key == ";":
            if self.last_find_char:
                self._find_char(
                    self.last_find_char,
                    forward=self.last_find_forward,
                    till=self.last_find_till,
                    count=count,
                )
        elif key == "comma" or key == ",":
            if self.last_find_char:
                self._find_char(
                    self.last_find_char,
                    forward=not self.last_find_forward,
                    till=self.last_find_till,
                    count=count,
                )
        
        # Edit commands
        elif key == "x":
            for _ in range(count):
                self._delete_char()
        elif key == "X":
            for _ in range(count):
                self._delete_char_before()
        elif key == "r":
            self.pending_keys = "r"
        elif key == "d":
            self.pending_keys = "d"
        elif key == "D":
            self._delete_to_line_end()
        elif key == "c":
            self.pending_keys = "c"
        elif key == "C":
            self._delete_to_line_end()
            self._enter_insert_mode()
        elif key == "y":
            self.pending_keys = "y"
        elif key == "Y":
            self._yank_line()
        elif key == "p":
            for _ in range(count):
                self._paste_after()
        elif key == "P":
            for _ in range(count):
                self._paste_before()
        elif key == "u":
            self.undo()
        elif key == "ctrl+r":
            self.redo()
        elif key == "J":
            self._join_lines()
        elif key == "tilde" or key == "~":
            self._toggle_case()
        elif key == "greater" or key == ">":
            self.pending_keys = ">"
        elif key == "less" or key == "<":
            self.pending_keys = "<"
        
        self.refresh()
    
    async def _handle_pending_key(self, key: str, char: str | None) -> None:
        """Handle second key of a two-key command."""
        pending = self.pending_keys
        self.pending_keys = ""
        count = self._get_count()
        
        if pending == "g":
            if key == "g":
                self.move_cursor((0, 0))
            elif key == "e":
                self._move_word_end_backward()
        elif pending == "d":
            if key == "d":
                for _ in range(count):
                    self._delete_line()
            elif key == "w":
                for _ in range(count):
                    self._delete_word()
            elif key == "e":
                for _ in range(count):
                    self._delete_to_word_end()
            elif key == "0":
                self._delete_to_line_start()
            elif key == "dollar" or key == "$":
                self._delete_to_line_end()
            elif key == "g":
                self.pending_keys = "dg"
        elif pending == "dg":
            if key == "g":
                # dgg - delete to start of document
                self._delete_to_document_start()
        elif pending == "c":
            if key == "c":
                self._delete_line_content()
                self._enter_insert_mode()
            elif key == "w":
                for _ in range(count):
                    self._delete_word()
                self._enter_insert_mode()
            elif key == "e":
                for _ in range(count):
                    self._delete_to_word_end()
                self._enter_insert_mode()
        elif pending == "y":
            if key == "y":
                self._yank_line()
            elif key == "w":
                self._yank_word()
        elif pending == "f" and char:
            self._find_char(char, forward=True, till=False, count=count)
        elif pending == "F" and char:
            self._find_char(char, forward=False, till=False, count=count)
        elif pending == "t" and char:
            self._find_char(char, forward=True, till=True, count=count)
        elif pending == "T" and char:
            self._find_char(char, forward=False, till=True, count=count)
        elif pending == "r" and char:
            self._replace_char(char)
        elif pending == ">":
            if key == "greater" or key == ">":
                for _ in range(count):
                    self._indent_line()
        elif pending == "<":
            if key == "less" or key == "<":
                for _ in range(count):
                    self._outdent_line()
        
        self.refresh()
    
    async def _handle_visual_mode(self, event: events.Key) -> None:
        """Handle keys in visual mode."""
        key = event.key
        event.prevent_default()
        event.stop()
        
        if key == "escape":
            self.vim_mode = VimMode.NORMAL
            self.visual_start = None
        elif key == "v":
            if self.vim_mode == VimMode.VISUAL:
                self.vim_mode = VimMode.NORMAL
                self.visual_start = None
            else:
                self.vim_mode = VimMode.VISUAL
        elif key == "V":
            if self.vim_mode == VimMode.VISUAL_LINE:
                self.vim_mode = VimMode.NORMAL
                self.visual_start = None
            else:
                self.vim_mode = VimMode.VISUAL_LINE
        # Motion commands
        elif key == "h":
            self.action_cursor_left()
        elif key == "j":
            self.action_cursor_down()
        elif key == "k":
            self.action_cursor_up()
        elif key == "l":
            self.action_cursor_right()
        elif key == "w":
            self._move_word_forward()
        elif key == "b":
            self._move_word_backward()
        elif key == "e":
            self._move_word_end()
        elif key == "0":
            self.action_cursor_line_start()
        elif key == "dollar" or key == "$":
            self.action_cursor_line_end()
        elif key == "g":
            self.pending_keys = "g"
        elif key == "G":
            lines = self.text.splitlines()
            if lines:
                self.move_cursor((len(lines) - 1, 0))
        elif key == "o":
            # Swap cursor to other end of selection
            if self.visual_start:
                current = self.cursor_location
                self.move_cursor(self.visual_start)
                self.visual_start = current
        # Edit commands
        elif key == "d" or key == "x":
            self._delete_visual_selection()
            self.vim_mode = VimMode.NORMAL
            self.visual_start = None
        elif key == "y":
            self._yank_visual_selection()
            self.vim_mode = VimMode.NORMAL
            self.visual_start = None
        elif key == "c":
            self._delete_visual_selection()
            self._enter_insert_mode()
            self.visual_start = None
        elif key == "greater" or key == ">":
            self._indent_visual_selection()
            self.vim_mode = VimMode.NORMAL
            self.visual_start = None
        elif key == "less" or key == "<":
            self._outdent_visual_selection()
            self.vim_mode = VimMode.NORMAL
            self.visual_start = None
        elif key == "tilde" or key == "~":
            self._toggle_case_visual_selection()
            self.vim_mode = VimMode.NORMAL
            self.visual_start = None
        
        self.refresh()
    
    def _enter_insert_mode(self) -> None:
        """Enter insert mode."""
        self.vim_mode = VimMode.INSERT
        self._update_cursor_style()
        self.refresh()
    
    def _move_to_first_nonblank(self) -> None:
        """Move cursor to first non-blank character of line."""
        line = self._current_line()
        row, _ = self.cursor_location
        for i, c in enumerate(line):
            if c not in " \t":
                self.move_cursor((row, i))
                return
        self.move_cursor((row, 0))
    
    def _move_word_forward(self, word: bool = False) -> None:
        """Move cursor to start of next word (w or W)."""
        self.action_cursor_word_right()
    
    def _move_word_backward(self, word: bool = False) -> None:
        """Move cursor to start of previous word (b or B)."""
        self.action_cursor_word_left()
    
    def _move_word_end(self, word: bool = False) -> None:
        """Move cursor to end of current/next word (e or E)."""
        self.action_cursor_word_right()
    
    def _move_word_end_backward(self) -> None:
        """Move cursor to end of previous word (ge)."""
        self.action_cursor_word_left()
    
    def _move_paragraph_up(self) -> None:
        """Move cursor to previous paragraph."""
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        # Skip current blank lines
        while row > 0 and (row >= len(lines) or not lines[row].strip()):
            row -= 1
        # Find previous blank line
        while row > 0 and lines[row].strip():
            row -= 1
        self.move_cursor((row, 0))
    
    def _move_paragraph_down(self) -> None:
        """Move cursor to next paragraph."""
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        # Skip current non-blank lines
        while row < len(lines) - 1 and lines[row].strip():
            row += 1
        # Find next non-blank line
        while row < len(lines) - 1 and not lines[row].strip():
            row += 1
        self.move_cursor((row, 0))
    
    def _find_char(
        self, char: str, forward: bool = True, till: bool = False, count: int = 1
    ) -> None:
        """Find character on current line (f/F/t/T commands)."""
        self.last_find_char = char
        self.last_find_forward = forward
        self.last_find_till = till
        
        row, col = self.cursor_location
        line = self._current_line()
        
        found_count = 0
        if forward:
            for i in range(col + 1, len(line)):
                if line[i] == char:
                    found_count += 1
                    if found_count == count:
                        target = i - 1 if till else i
                        self.move_cursor((row, target))
                        return
        else:
            for i in range(col - 1, -1, -1):
                if line[i] == char:
                    found_count += 1
                    if found_count == count:
                        target = i + 1 if till else i
                        self.move_cursor((row, target))
                        return
    
    def _replace_char(self, char: str) -> None:
        """Replace character under cursor (r command)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if row < len(lines) and col < len(lines[row]):
            line = lines[row]
            lines[row] = line[:col] + char + line[col + 1:]
            self.text = "\n".join(lines)
            self.move_cursor((row, col))
    
    def _delete_char(self) -> None:
        """Delete character under cursor (x command)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if row < len(lines) and col < len(lines[row]):
            self.action_cursor_right()
            self.action_delete_left()
    
    def _delete_char_before(self) -> None:
        """Delete character before cursor (X command)."""
        row, col = self.cursor_location
        if col > 0:
            self.action_delete_left()
    
    def _delete_line(self) -> None:
        """Delete current line (dd command)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines(keepends=True)
        if 0 <= row < len(lines):
            self.yanked_text = lines[row]
            del lines[row]
            self.text = "".join(lines)
            new_lines = self.text.splitlines()
            if row >= len(new_lines):
                row = max(0, len(new_lines) - 1)
            self.move_cursor((row, 0))
    
    def _delete_line_content(self) -> None:
        """Delete line content but keep the line (S, cc command)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            self.yanked_text = lines[row] + "\n"
            # Preserve indentation
            indent = ""
            for c in lines[row]:
                if c in " \t":
                    indent += c
                else:
                    break
            lines[row] = indent
            self.text = "\n".join(lines)
            self.move_cursor((row, len(indent)))
    
    def _delete_word(self) -> None:
        """Delete word (dw command)."""
        start_row, start_col = self.cursor_location
        self.action_cursor_word_right()
        end_row, end_col = self.cursor_location
        
        if start_row == end_row:
            lines = self.text.splitlines()
            if start_row < len(lines):
                line = lines[start_row]
                lines[start_row] = line[:start_col] + line[end_col:]
                self.text = "\n".join(lines)
                self.move_cursor((start_row, start_col))
    
    def _delete_to_word_end(self) -> None:
        """Delete to end of word (de command)."""
        self._delete_word()
    
    def _delete_to_line_start(self) -> None:
        """Delete to start of line (d0, Ctrl+u)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            line = lines[row]
            self.yanked_text = line[:col]
            lines[row] = line[col:]
            self.text = "\n".join(lines)
            self.move_cursor((row, 0))
    
    def _delete_to_line_end(self) -> None:
        """Delete to end of line (D, d$)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            line = lines[row]
            self.yanked_text = line[col:]
            lines[row] = line[:col]
            self.text = "\n".join(lines)
            self.move_cursor((row, max(0, col - 1)))
    
    def _delete_to_document_start(self) -> None:
        """Delete to start of document (dgg)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines(keepends=True)
        self.yanked_text = "".join(lines[:row + 1])
        self.text = "".join(lines[row + 1:])
        self.move_cursor((0, 0))
    
    def _delete_word_before(self) -> None:
        """Delete word before cursor (Ctrl+w in insert mode)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            line = lines[row]
            # Find start of previous word
            i = col - 1
            while i > 0 and line[i - 1] in " \t":
                i -= 1
            while i > 0 and line[i - 1] not in " \t":
                i -= 1
            lines[row] = line[:i] + line[col:]
            self.text = "\n".join(lines)
            self.move_cursor((row, i))
    
    def _yank_line(self) -> None:
        """Yank (copy) current line (yy, Y command)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines(keepends=True)
        if 0 <= row < len(lines):
            self.yanked_text = lines[row]
    
    def _yank_word(self) -> None:
        """Yank word (yw command)."""
        start_row, start_col = self.cursor_location
        self.action_cursor_word_right()
        end_row, end_col = self.cursor_location
        
        if start_row == end_row:
            lines = self.text.splitlines()
            if start_row < len(lines):
                line = lines[start_row]
                self.yanked_text = line[start_col:end_col]
        
        self.move_cursor((start_row, start_col))
    
    def _paste_after(self) -> None:
        """Paste after cursor (p command)."""
        if self.yanked_text:
            if self.yanked_text.endswith("\n"):
                self.action_cursor_line_end()
                self.insert("\n" + self.yanked_text.rstrip("\n"))
            else:
                self.action_cursor_right()
                self.insert(self.yanked_text)
    
    def _paste_before(self) -> None:
        """Paste before cursor (P command)."""
        if self.yanked_text:
            if self.yanked_text.endswith("\n"):
                self.action_cursor_line_start()
                self.insert(self.yanked_text)
                self.action_cursor_up()
            else:
                self.insert(self.yanked_text)
    
    def _join_lines(self) -> None:
        """Join current line with next line (J command)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        if row < len(lines) - 1:
            current = lines[row].rstrip()
            next_line = lines[row + 1].lstrip()
            lines[row] = current + " " + next_line
            del lines[row + 1]
            self.text = "\n".join(lines)
            self.move_cursor((row, len(current)))
    
    def _toggle_case(self) -> None:
        """Toggle case of character under cursor (~ command)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if row < len(lines) and col < len(lines[row]):
            line = lines[row]
            char = line[col]
            if char.isupper():
                char = char.lower()
            else:
                char = char.upper()
            lines[row] = line[:col] + char + line[col + 1:]
            self.text = "\n".join(lines)
            self.move_cursor((row, col + 1))
    
    def _indent_line(self) -> None:
        """Indent current line (>> command)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            lines[row] = "    " + lines[row]
            self.text = "\n".join(lines)
            self.move_cursor((row, col + 4))
    
    def _outdent_line(self) -> None:
        """Outdent current line (<< command)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if 0 <= row < len(lines):
            line = lines[row]
            # Remove up to 4 spaces or a tab
            if line.startswith("    "):
                lines[row] = line[4:]
                self.text = "\n".join(lines)
                self.move_cursor((row, max(0, col - 4)))
            elif line.startswith("\t"):
                lines[row] = line[1:]
                self.text = "\n".join(lines)
                self.move_cursor((row, max(0, col - 1)))
            elif line.startswith(" "):
                # Remove leading spaces
                stripped = line.lstrip(" ")
                removed = len(line) - len(stripped)
                lines[row] = stripped
                self.text = "\n".join(lines)
                self.move_cursor((row, max(0, col - removed)))
    
    def _delete_visual_selection(self) -> None:
        """Delete the visual selection."""
        selection = self._get_selection_range()
        if not selection:
            return
        
        start, end = selection
        lines = self.text.splitlines()
        
        if self.vim_mode == VimMode.VISUAL_LINE:
            # Delete entire lines
            self.yanked_text = "\n".join(lines[start[0]:end[0] + 1]) + "\n"
            del lines[start[0]:end[0] + 1]
            self.text = "\n".join(lines)
            new_row = min(start[0], len(lines) - 1)
            self.move_cursor((max(0, new_row), 0))
        else:
            # Character-wise deletion
            if start[0] == end[0]:
                # Single line
                line = lines[start[0]]
                self.yanked_text = line[start[1]:end[1] + 1]
                lines[start[0]] = line[:start[1]] + line[end[1] + 1:]
            else:
                # Multiple lines
                first = lines[start[0]][:start[1]]
                last = lines[end[0]][end[1] + 1:]
                self.yanked_text = lines[start[0]][start[1]:] + "\n"
                for i in range(start[0] + 1, end[0]):
                    self.yanked_text += lines[i] + "\n"
                self.yanked_text += lines[end[0]][:end[1] + 1]
                lines[start[0]] = first + last
                del lines[start[0] + 1:end[0] + 1]
            self.text = "\n".join(lines)
            self.move_cursor(start)
    
    def _yank_visual_selection(self) -> None:
        """Yank the visual selection."""
        selection = self._get_selection_range()
        if not selection:
            return
        
        start, end = selection
        lines = self.text.splitlines()
        
        if self.vim_mode == VimMode.VISUAL_LINE:
            self.yanked_text = "\n".join(lines[start[0]:end[0] + 1]) + "\n"
        else:
            if start[0] == end[0]:
                line = lines[start[0]]
                self.yanked_text = line[start[1]:end[1] + 1]
            else:
                self.yanked_text = lines[start[0]][start[1]:] + "\n"
                for i in range(start[0] + 1, end[0]):
                    self.yanked_text += lines[i] + "\n"
                self.yanked_text += lines[end[0]][:end[1] + 1]
        
        self.move_cursor(start)
    
    def _indent_visual_selection(self) -> None:
        """Indent the visual selection."""
        selection = self._get_selection_range()
        if not selection:
            return
        
        start, end = selection
        lines = self.text.splitlines()
        
        for i in range(start[0], end[0] + 1):
            if i < len(lines):
                lines[i] = "    " + lines[i]
        
        self.text = "\n".join(lines)
        self.move_cursor(start)
    
    def _outdent_visual_selection(self) -> None:
        """Outdent the visual selection."""
        selection = self._get_selection_range()
        if not selection:
            return
        
        start, end = selection
        lines = self.text.splitlines()
        
        for i in range(start[0], end[0] + 1):
            if i < len(lines):
                line = lines[i]
                if line.startswith("    "):
                    lines[i] = line[4:]
                elif line.startswith("\t"):
                    lines[i] = line[1:]
                elif line.startswith(" "):
                    lines[i] = line.lstrip(" ")
        
        self.text = "\n".join(lines)
        self.move_cursor(start)
    
    def _toggle_case_visual_selection(self) -> None:
        """Toggle case of the visual selection."""
        selection = self._get_selection_range()
        if not selection:
            return
        
        start, end = selection
        lines = self.text.splitlines()
        
        if self.vim_mode == VimMode.VISUAL_LINE:
            for i in range(start[0], end[0] + 1):
                if i < len(lines):
                    lines[i] = lines[i].swapcase()
        else:
            if start[0] == end[0]:
                line = lines[start[0]]
                toggled = line[start[1]:end[1] + 1].swapcase()
                lines[start[0]] = line[:start[1]] + toggled + line[end[1] + 1:]
            else:
                # First line
                line = lines[start[0]]
                lines[start[0]] = line[:start[1]] + line[start[1]:].swapcase()
                # Middle lines
                for i in range(start[0] + 1, end[0]):
                    lines[i] = lines[i].swapcase()
                # Last line
                line = lines[end[0]]
                lines[end[0]] = line[:end[1] + 1].swapcase() + line[end[1] + 1:]
        
        self.text = "\n".join(lines)
        self.move_cursor(start)
