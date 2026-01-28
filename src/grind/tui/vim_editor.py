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
    COMMAND = "COMMAND"


class VimEditor(TextArea):
    """TextArea with vim-style keybindings.
    
    Modes:
    - NORMAL: Navigate and edit with vim motions
    - INSERT: Type text normally
    - VISUAL: Select text
    
    Normal mode commands:
    - i, a, o, O: Enter insert mode
    - h, j, k, l: Move cursor
    - w, b, e: Word motions
    - 0, $: Line start/end
    - gg, G: Document start/end
    - x: Delete character
    - dd: Delete line
    - yy: Yank (copy) line
    - p: Paste
    - u: Undo
    - Ctrl+r: Redo
    
    Insert mode:
    - Escape: Return to normal mode
    - Type normally
    """
    
    BINDINGS = []
    
    def __init__(self, language: str = "cpp", **kwargs):
        super().__init__(**kwargs)
        self.code_language = language  # Renamed to avoid conflict with TextArea.language
        self.vim_mode = VimMode.NORMAL
        self.yanked_text = ""
        self.pending_keys = ""
        self.last_search = ""
        
        # Set initial text
        from grind.tui.app import LANGUAGE_TEMPLATES
        self.text = LANGUAGE_TEMPLATES.get(language, "")
        
    @property
    def mode_display(self) -> str:
        """Get display string for current mode."""
        return f"-- {self.vim_mode.value} --"
    
    def set_language(self, language: str) -> None:
        """Change the editor language."""
        from grind.tui.app import LANGUAGE_TEMPLATES
        self.code_language = language
        self.text = LANGUAGE_TEMPLATES.get(language, "")
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key events for vim mode."""
        key = event.key
        
        if self.vim_mode == VimMode.INSERT:
            await self._handle_insert_mode(event)
        elif self.vim_mode == VimMode.NORMAL:
            await self._handle_normal_mode(event)
        elif self.vim_mode == VimMode.VISUAL:
            await self._handle_visual_mode(event)
    
    async def _handle_insert_mode(self, event: events.Key) -> None:
        """Handle keys in insert mode."""
        if event.key == "escape":
            self.vim_mode = VimMode.NORMAL
            self.cursor_blink = False
            # Move cursor back one if possible
            row, col = self.cursor_location
            if col > 0:
                self.move_cursor((row, col - 1))
            event.prevent_default()
            event.stop()
            self.refresh()
        # Let other keys pass through to TextArea for normal editing
    
    async def _handle_normal_mode(self, event: events.Key) -> None:
        """Handle keys in normal mode."""
        key = event.key
        
        # Always prevent default in normal mode
        event.prevent_default()
        event.stop()
        
        # Check for pending keys (like gg, dd, yy)
        if self.pending_keys:
            await self._handle_pending_key(key)
            return
        
        # Mode switching
        if key == "i":
            self.vim_mode = VimMode.INSERT
            self.cursor_blink = True
            self.refresh()
            return
        elif key == "a":
            self.vim_mode = VimMode.INSERT
            self.cursor_blink = True
            row, col = self.cursor_location
            lines = self.text.splitlines()
            if row < len(lines) and col < len(lines[row]):
                self.move_cursor((row, col + 1))
            self.refresh()
            return
        elif key == "o":
            self.vim_mode = VimMode.INSERT
            self.cursor_blink = True
            self.action_cursor_line_end()
            self.insert("\n")
            self.refresh()
            return
        elif key == "O":
            self.vim_mode = VimMode.INSERT
            self.cursor_blink = True
            self.action_cursor_line_start()
            self.insert("\n")
            self.action_cursor_up()
            self.refresh()
            return
        elif key == "v":
            self.vim_mode = VimMode.VISUAL
            self.refresh()
            return
        
        # Motion commands
        if key == "h":
            self.action_cursor_left()
        elif key == "j":
            self.action_cursor_down()
        elif key == "k":
            self.action_cursor_up()
        elif key == "l":
            self.action_cursor_right()
        elif key == "w":
            self.action_cursor_word_right()
        elif key == "b":
            self.action_cursor_word_left()
        elif key == "e":
            self.action_cursor_word_right()
        elif key == "0":
            self.action_cursor_line_start()
        elif key == "dollar" or key == "$":
            self.action_cursor_line_end()
        elif key == "g":
            self.pending_keys = "g"
        elif key == "G":
            # Go to end of document
            lines = self.text.splitlines()
            if lines:
                self.move_cursor((len(lines) - 1, 0))
        
        # Edit commands
        elif key == "x":
            self._delete_char()
        elif key == "d":
            self.pending_keys = "d"
        elif key == "y":
            self.pending_keys = "y"
        elif key == "p":
            self._paste_after()
        elif key == "P":
            self._paste_before()
        elif key == "u":
            self.undo()
        elif key == "ctrl+r":
            self.redo()
        
        self.refresh()
    
    async def _handle_pending_key(self, key: str) -> None:
        """Handle second key of a two-key command."""
        pending = self.pending_keys
        self.pending_keys = ""
        
        if pending == "g":
            if key == "g":
                # gg - go to start of document
                self.move_cursor((0, 0))
        elif pending == "d":
            if key == "d":
                # dd - delete line
                self._delete_line()
            elif key == "w":
                # dw - delete word
                self._delete_word()
        elif pending == "y":
            if key == "y":
                # yy - yank line
                self._yank_line()
        
        self.refresh()
    
    async def _handle_visual_mode(self, event: events.Key) -> None:
        """Handle keys in visual mode."""
        key = event.key
        event.prevent_default()
        event.stop()
        
        if key == "escape":
            self.vim_mode = VimMode.NORMAL
        elif key == "h":
            self.action_cursor_left()
        elif key == "j":
            self.action_cursor_down()
        elif key == "k":
            self.action_cursor_up()
        elif key == "l":
            self.action_cursor_right()
        elif key == "y":
            self._yank_line()
            self.vim_mode = VimMode.NORMAL
        elif key == "d":
            self._delete_line()
            self.vim_mode = VimMode.NORMAL
        
        self.refresh()
    
    def _delete_char(self) -> None:
        """Delete character under cursor (x command)."""
        row, col = self.cursor_location
        lines = self.text.splitlines()
        if row < len(lines) and col < len(lines[row]):
            self.action_cursor_right()
            self.action_delete_left()
    
    def _delete_line(self) -> None:
        """Delete current line (dd command)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines(keepends=True)
        if 0 <= row < len(lines):
            self.yanked_text = lines[row]
            del lines[row]
            self.text = "".join(lines)
            # Adjust cursor if needed
            new_lines = self.text.splitlines()
            if row >= len(new_lines):
                row = max(0, len(new_lines) - 1)
            self.move_cursor((row, 0))
    
    def _delete_word(self) -> None:
        """Delete word (dw command)."""
        start_row, start_col = self.cursor_location
        self.action_cursor_word_right()
        end_row, end_col = self.cursor_location
        
        if start_row == end_row:
            # Delete within same line
            lines = self.text.splitlines()
            if start_row < len(lines):
                line = lines[start_row]
                lines[start_row] = line[:start_col] + line[end_col:]
                self.text = "\n".join(lines)
                self.move_cursor((start_row, start_col))
    
    def _yank_line(self) -> None:
        """Yank (copy) current line (yy command)."""
        row, _ = self.cursor_location
        lines = self.text.splitlines(keepends=True)
        if 0 <= row < len(lines):
            self.yanked_text = lines[row]
    
    def _paste_after(self) -> None:
        """Paste after cursor (p command)."""
        if self.yanked_text:
            if self.yanked_text.endswith("\n"):
                # Line paste - paste on new line below
                self.action_cursor_line_end()
                self.insert("\n" + self.yanked_text.rstrip("\n"))
            else:
                self.action_cursor_right()
                self.insert(self.yanked_text)
    
    def _paste_before(self) -> None:
        """Paste before cursor (P command)."""
        if self.yanked_text:
            if self.yanked_text.endswith("\n"):
                # Line paste - paste on new line above
                self.action_cursor_line_start()
                self.insert(self.yanked_text)
                self.action_cursor_up()
            else:
                self.insert(self.yanked_text)
