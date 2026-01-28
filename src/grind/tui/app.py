"""Main TUI application."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Footer, Header, Static, TextArea, Markdown, Label, Rule, Button
from textual.screen import Screen

from grind.config import Settings, load_settings
from grind.api.leetcode import LeetCodeClient, Problem
from grind.ai.coach import Coach
from grind.db.database import Database, Attempt
from grind.tui.vim_editor import VimEditor, VimMode
from grind.auth import CopilotAuth

from datetime import datetime
import asyncio


LANGUAGE_TEMPLATES = {
    "cpp": '''#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    // TODO: implement solution
};
''',
    "rust": '''impl Solution {
    pub fn solve() {
        // TODO: implement solution
    }
}
''',
    "ocaml": '''(* TODO: implement solution *)
let solve () =
  ()
''',
}

LANGUAGES = ["cpp", "rust", "ocaml"]


class AuthScreen(Screen):
    """GitHub Copilot authentication screen."""

    BINDINGS = [
        Binding("q", "quit", "Cancel"),
        Binding("escape", "quit", "Cancel", show=False),
    ]

    CSS = """
    AuthScreen {
        align: center middle;
    }

    #auth-box {
        width: 60;
        height: auto;
        border: double $primary;
        padding: 2;
        background: $surface;
    }

    #auth-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
    }

    #auth-status {
        text-align: center;
        padding: 1;
    }

    #auth-code {
        text-align: center;
        text-style: bold;
        color: $warning;
        padding: 1;
    }

    #auth-url {
        text-align: center;
        color: $text-muted;
        padding: 1;
    }

    #auth-instructions {
        text-align: center;
        padding: 1;
    }
    """

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.auth: CopilotAuth | None = None
        self._polling = False

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-box"):
            yield Static("GitHub Copilot Authentication", id="auth-title")
            yield Rule()
            yield Static("Checking authentication status...", id="auth-status")
            yield Static("", id="auth-code")
            yield Static("", id="auth-url")
            yield Static("", id="auth-instructions")
            yield Rule()
            yield Static("[q] Cancel", classes="menu-item")
        yield Footer()

    async def on_mount(self) -> None:
        """Start auth flow when screen mounts."""
        self.auth = CopilotAuth(self.settings.copilot_relay_url)
        
        # Check current status first
        status = await self.auth.check_status()
        if status.get("authenticated"):
            self.query_one("#auth-status").update("Already authenticated!")
            self.query_one("#auth-instructions").update("Press [q] to return")
            return
        
        # Start device flow
        try:
            flow = await self.auth.start_device_flow()
            self.query_one("#auth-status").update("Enter this code:")
            self.query_one("#auth-code").update(f"  {flow['user_code']}  ")
            self.query_one("#auth-url").update(f"at {flow['verification_uri']}")
            self.query_one("#auth-instructions").update("Waiting for authentication...")
            
            # Start polling in background
            self._polling = True
            asyncio.create_task(self._poll_auth())
        except Exception as e:
            self.query_one("#auth-status").update(f"Error: {e}")
            self.query_one("#auth-instructions").update("Press [q] to return")

    async def _poll_auth(self) -> None:
        """Poll for authentication completion."""
        while self._polling:
            try:
                result = await self.auth.poll_for_token()
                
                if result["status"] == "success":
                    self.query_one("#auth-status").update("Authentication successful!")
                    self.query_one("#auth-code").update("")
                    self.query_one("#auth-url").update("")
                    self.query_one("#auth-instructions").update("Press [q] to continue")
                    self._polling = False
                    return
                elif result["status"] == "error":
                    self.query_one("#auth-status").update(f"Error: {result['message']}")
                    self.query_one("#auth-instructions").update("Press [q] to retry")
                    self._polling = False
                    return
                
                await asyncio.sleep(5)
            except Exception as e:
                self.query_one("#auth-status").update(f"Error: {e}")
                self._polling = False
                return

    async def action_quit(self) -> None:
        """Close auth screen."""
        self._polling = False
        if self.auth:
            await self.auth.close()
        self.app.pop_screen()


class PracticeScreen(Screen):
    """Main practice screen with problem, editor, and coach."""

    BINDINGS = [
        Binding("f1", "hint", "Hint", priority=True),
        Binding("f2", "run", "Run", priority=True),
        Binding("f3", "submit", "Submit", priority=True),
        Binding("f4", "chat", "Chat", priority=True),
        Binding("f5", "next", "Next", priority=True),
        Binding("f6", "switch_language", "Lang", priority=True),
        Binding("ctrl+1", "lang_cpp", "C++", priority=True, show=False),
        Binding("ctrl+2", "lang_rust", "Rust", priority=True, show=False),
        Binding("ctrl+3", "lang_ocaml", "OCaml", priority=True, show=False),
        Binding("ctrl+q", "app_quit", "Quit", priority=True),
        Binding("ctrl+p", "focus_problem", "Problem", priority=True, show=False),
        Binding("ctrl+e", "focus_editor", "Editor", priority=True, show=False),
        Binding("ctrl+a", "focus_chat", "Chat Input", priority=True, show=False),
        Binding("tab", "focus_next", "Focus", priority=True),
        Binding("shift+tab", "focus_previous", "Back", priority=True, show=False),
    ]

    CSS = """
    PracticeScreen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 12;
    }

    #problem-pane {
        border: solid $primary;
        border-title-color: $primary;
        padding: 1 2;
    }

    #editor-pane {
        border: solid $secondary;
        border-title-color: $secondary;
        padding: 0;
    }

    #editor-pane VimEditor {
        width: 100%;
        height: 100%;
    }

    #vim-mode-bar {
        dock: bottom;
        height: 1;
        background: $surface-darken-1;
        color: $warning;
        padding: 0 1;
    }

    #coach-pane {
        column-span: 2;
        border: solid $warning;
        border-title-color: $warning;
        padding: 1 2;
    }

    #coach-content {
        height: auto;
        max-height: 6;
    }

    #coach-input {
        height: 3;
        margin-top: 1;
        border: solid $surface-lighten-2;
    }

    #stats-header {
        dock: top;
        height: 1;
        background: $primary-darken-3;
        color: $text;
        text-align: center;
        padding: 0 2;
    }

    .pane-title {
        text-style: bold;
        color: $text;
    }
    """

    def __init__(
        self,
        settings: Settings,
        client: LeetCodeClient,
        coach: Coach,
        db: Database,
        problem: Problem | None = None,
    ):
        super().__init__()
        self.settings = settings
        self.client = client
        self.coach = coach
        self.db = db
        self.current_problem = problem
        self.attempt_start: datetime | None = None
        self.hints_used = 0
        self.current_language = settings.default_language

    def compose(self) -> ComposeResult:
        stats = self.db.get_stats()
        streak = stats.get("streak", 0)
        solved = stats.get("unique_problems", 0)

        yield Static(
            f" GRIND | {streak} streak | {solved} solved | F1:Hint F2:Run F3:Submit F4:Chat F5:Next F6:Lang ",
            id="stats-header"
        )

        with ScrollableContainer(id="problem-pane"):
            yield Markdown(
                "# Welcome\n\nPress `F5` or `n` to load the daily challenge.\n\n"
                "**Vim Editor Keys:**\n"
                "- `i` - Insert mode\n"
                "- `Esc` - Normal mode\n"
                "- `h/j/k/l` - Move cursor\n"
                "- `dd` - Delete line\n"
                "- `yy` - Copy line\n"
                "- `p` - Paste",
                id="problem-content"
            )

        with Vertical(id="editor-pane"):
            yield VimEditor(language=self.current_language, id="editor")
            yield Static("-- NORMAL --", id="vim-mode-bar")

        with Vertical(id="coach-pane"):
            yield Markdown(
                "*Coach ready. Press `F1` for hints, `F4` to chat.*",
                id="coach-content"
            )
            yield TextArea(placeholder="Type message and press F4 to chat...", id="coach-input")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._update_editor_title()
        self.query_one("#problem-pane").border_title = "Problem"
        self.query_one("#coach-pane").border_title = "AI Coach"
        
        # Set up vim mode update timer
        self.set_interval(0.1, self._update_vim_mode)

        if self.current_problem:
            await self._show_problem(self.current_problem)

    def _update_vim_mode(self) -> None:
        """Update vim mode display."""
        try:
            editor = self.query_one("#editor", VimEditor)
            mode_bar = self.query_one("#vim-mode-bar", Static)
            mode_bar.update(editor.mode_display)
        except Exception:
            pass

    def _update_editor_title(self) -> None:
        """Update the editor pane title with current language."""
        lang_display = self.current_language.upper()
        self.query_one("#editor-pane").border_title = f"Editor [{lang_display}] - Vim Mode"

    async def _show_problem(self, problem: Problem) -> None:
        """Display a problem in the panel."""
        self.current_problem = problem
        self.attempt_start = datetime.now()
        self.hints_used = 0

        # Update problem panel
        content = self.query_one("#problem-content", Markdown)

        # Build markdown content
        tag_names = [t.name for t in problem.topic_tags] if problem.topic_tags else []
        tags = ", ".join(tag_names) if tag_names else "None"
        md = f"# {problem.title}\n\n"
        md += f"**Difficulty:** {problem.difficulty}  \n"
        md += f"**Tags:** {tags}\n\n"
        md += "---\n\n"

        # Clean up HTML content
        question = problem.question
        question = question.replace("<p>", "\n\n").replace("</p>", "")
        question = question.replace("<code>", "`").replace("</code>", "`")
        question = question.replace("<strong>", "**").replace("</strong>", "**")
        question = question.replace("<em>", "*").replace("</em>", "*")
        question = question.replace("<pre>", "\n```\n").replace("</pre>", "\n```\n")
        question = question.replace("<ul>", "").replace("</ul>", "")
        question = question.replace("<li>", "- ").replace("</li>", "\n")
        question = question.replace("&nbsp;", " ")
        question = question.replace("&lt;", "<").replace("&gt;", ">")
        question = question.replace("&amp;", "&")
        md += question

        if problem.hints:
            md += "\n\n---\n\n**Hints available:** " + str(len(problem.hints))

        content.update(md)

        # Set up coach context
        self.coach.set_problem_context(problem.title, problem.question)

        # Reset editor with current language
        editor = self.query_one("#editor", VimEditor)
        editor.set_language(self.current_language)

        # Update border title
        self.query_one("#problem-pane").border_title = f"Problem: {problem.title}"

    def _switch_to_language(self, language: str) -> None:
        """Switch to a different programming language."""
        self.current_language = language
        editor = self.query_one("#editor", VimEditor)
        editor.set_language(language)
        self._update_editor_title()

    async def action_switch_language(self) -> None:
        """Cycle through available languages."""
        current_idx = LANGUAGES.index(self.current_language)
        next_idx = (current_idx + 1) % len(LANGUAGES)
        self._switch_to_language(LANGUAGES[next_idx])

    async def action_lang_cpp(self) -> None:
        """Switch to C++."""
        self._switch_to_language("cpp")

    async def action_lang_rust(self) -> None:
        """Switch to Rust."""
        self._switch_to_language("rust")

    async def action_lang_ocaml(self) -> None:
        """Switch to OCaml."""
        self._switch_to_language("ocaml")

    async def action_focus_next(self) -> None:
        """Focus the next widget."""
        self.focus_next()

    async def action_focus_previous(self) -> None:
        """Focus the previous widget."""
        self.focus_previous()

    async def action_focus_problem(self) -> None:
        """Focus the problem pane."""
        self.query_one("#problem-pane").focus()

    async def action_focus_editor(self) -> None:
        """Focus the editor."""
        self.query_one("#editor").focus()

    async def action_focus_chat(self) -> None:
        """Focus the chat input."""
        self.query_one("#coach-input").focus()

    async def action_app_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    async def action_hint(self) -> None:
        """Request a hint from the coach."""
        if not self.current_problem:
            return

        self.hints_used += 1
        editor = self.query_one("#editor", VimEditor)

        levels = ["gentle", "medium", "strong"]
        level = levels[min(self.hints_used - 1, 2)]

        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Thinking...*")

        try:
            hint = await self.coach.get_hint(editor.text, level)  # type: ignore
            coach_content.update(f"**Hint ({level}):**\n\n{hint}")
        except Exception as e:
            coach_content.update(f"**Error getting hint:** {e}")

    async def action_chat(self) -> None:
        """Send a message to the coach."""
        input_area = self.query_one("#coach-input", TextArea)
        message = input_area.text.strip()
        if not message:
            return

        input_area.text = ""
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Thinking...*")

        try:
            response = await self.coach.chat(message)
            coach_content.update(response)
        except Exception as e:
            coach_content.update(f"**Error:** {e}")

    async def action_submit(self) -> None:
        """Submit solution and get review."""
        if not self.current_problem or not self.attempt_start:
            return

        editor = self.query_one("#editor", VimEditor)
        code = editor.text

        # Save attempt
        attempt = Attempt(
            problem_slug=self.current_problem.title_slug,
            started_at=self.attempt_start,
            completed_at=datetime.now(),
            result="solved",
            hints_used=self.hints_used,
            code=code,
            language=self.current_language,
        )
        self.db.save_attempt(attempt)

        # Get AI review
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Reviewing your solution...*")

        try:
            review = await self.coach.review_code(code, self.current_language)
            coach_content.update(f"**Code Review:**\n\n{review}")
        except Exception as e:
            coach_content.update(f"**Error reviewing:** {e}")

    async def action_next(self) -> None:
        """Get next problem."""
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Fetching daily challenge...*")

        try:
            problem = await self.client.get_daily()
            full_problem = await self.client.get_problem(problem.title_slug)
            await self._show_problem(full_problem)
            coach_content.update("*Problem loaded. Good luck!*")
        except Exception as e:
            coach_content.update(f"**Error:** {e}")


class WelcomeScreen(Screen):
    """Welcome screen with options."""

    BINDINGS = [
        Binding("d", "daily", "Daily Challenge"),
        Binding("p", "problems", "Problem List"),
        Binding("s", "stats", "Statistics"),
        Binding("a", "auth", "Authenticate"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    WelcomeScreen {
        align: center middle;
    }

    #welcome-box {
        width: 50;
        height: auto;
        border: double $primary;
        padding: 1 2;
        background: $surface;
    }

    #title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1 0;
    }

    #subtitle {
        text-align: center;
        color: $text-muted;
        padding-bottom: 1;
    }

    .stat-row {
        text-align: center;
        padding: 0 0 1 0;
    }

    .menu-section {
        padding-top: 1;
    }

    .menu-item {
        text-align: center;
        padding: 0;
    }

    .menu-key {
        color: $primary;
        text-style: bold;
    }
    """

    def __init__(self, settings: Settings, client: LeetCodeClient, coach: Coach, db: Database):
        super().__init__()
        self.settings = settings
        self.client = client
        self.coach = coach
        self.db = db

    def compose(self) -> ComposeResult:
        stats = self.db.get_stats()

        with Vertical(id="welcome-box"):
            yield Static("GRIND", id="title")
            yield Static("AI-Powered LeetCode Practice", id="subtitle")
            yield Rule()
            yield Static(f"{stats['streak']} day streak  |  {stats['unique_problems']} solved", classes="stat-row")
            yield Rule()
            yield Static("", classes="menu-section")
            yield Static("[d]  Daily Challenge", classes="menu-item")
            yield Static("[p]  Problem List", classes="menu-item")
            yield Static("[s]  Statistics", classes="menu-item")
            yield Static("[a]  Authenticate (Copilot)", classes="menu-item")
            yield Static("[q]  Quit", classes="menu-item")

        yield Footer()

    async def action_daily(self) -> None:
        """Start daily challenge."""
        screen = PracticeScreen(self.settings, self.client, self.coach, self.db)
        await self.app.push_screen(screen)
        # Trigger loading the daily problem
        await screen.action_next()

    async def action_auth(self) -> None:
        """Open authentication screen."""
        await self.app.push_screen(AuthScreen(self.settings))


class GrindApp(App):
    """Main Grind TUI application."""

    TITLE = "Grind"
    CSS_PATH = None

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.client = LeetCodeClient(self.settings.leetcode_api_url)
        self.coach = Coach(self.settings)
        self.db = Database(self.settings.get_db_path())

    async def on_mount(self) -> None:
        """Mount the welcome screen."""
        await self.push_screen(WelcomeScreen(self.settings, self.client, self.coach, self.db))

    async def on_unmount(self) -> None:
        """Clean up resources."""
        await self.client.close()


def run() -> None:
    """Run the Grind TUI."""
    app = GrindApp()
    app.run()
