"""Main TUI application."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static, TextArea, Markdown, Button, Label
from textual.screen import Screen

from grind.config import Settings, load_settings
from grind.api.leetcode import LeetCodeClient, Problem
from grind.ai.coach import Coach
from grind.db.database import Database, Attempt

from datetime import datetime


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


class ProblemPanel(Static):
    """Panel displaying the problem description."""

    def compose(self) -> ComposeResult:
        yield Markdown("# Welcome to Grind\n\nPress `d` for daily challenge or `p` to pick a problem.", id="problem-content")


class CodeEditor(TextArea):
    """Vim-enabled code editor."""

    BINDINGS = [
        Binding("escape", "normal_mode", "Normal mode", show=False),
    ]

    def __init__(self, language: str = "cpp", **kwargs):
        super().__init__(**kwargs)
        self.language = language
        self.text = LANGUAGE_TEMPLATES.get(language, "")


class CoachPanel(Static):
    """Panel for AI coach interactions."""

    def compose(self) -> ComposeResult:
        yield Markdown("*Coach is ready. Ask for hints or discuss your approach.*", id="coach-content")
        yield TextArea(id="coach-input", classes="coach-input")


class StatsBar(Static):
    """Statistics bar showing streak and progress."""

    def __init__(self, stats: dict, **kwargs):
        super().__init__(**kwargs)
        self.stats = stats

    def compose(self) -> ComposeResult:
        streak = self.stats.get("streak", 0)
        solved = self.stats.get("unique_problems", 0)
        yield Label(f"🔥 {streak} day streak | ✅ {solved} solved", id="stats-label")


class PracticeScreen(Screen):
    """Main practice screen with problem, editor, and coach."""

    BINDINGS = [
        Binding("h", "hint", "Hint"),
        Binding("r", "run", "Run"),
        Binding("s", "submit", "Submit"),
        Binding("c", "chat", "Chat"),
        Binding("n", "next", "Next"),
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("tab", "focus_next", "Next panel"),
    ]

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr auto;
    }

    #problem-panel {
        border: solid green;
        padding: 1;
        overflow-y: auto;
    }

    #editor-panel {
        border: solid blue;
        padding: 1;
    }

    #coach-panel {
        column-span: 2;
        border: solid yellow;
        padding: 1;
        height: 10;
    }

    .coach-input {
        height: 3;
        margin-top: 1;
    }

    #stats-bar {
        dock: top;
        height: 1;
        background: $surface;
        text-align: center;
    }

    TextArea {
        height: 100%;
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

    def compose(self) -> ComposeResult:
        stats = self.db.get_stats()
        yield StatsBar(stats, id="stats-bar")

        with Container(id="main-container"):
            with Vertical(id="problem-panel"):
                yield ProblemPanel()

            with Vertical(id="editor-panel"):
                yield CodeEditor(language=self.settings.default_language, id="editor")

            with Vertical(id="coach-panel"):
                yield CoachPanel()

        yield Footer()

    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        if self.current_problem:
            await self._show_problem(self.current_problem)

    async def _show_problem(self, problem: Problem) -> None:
        """Display a problem in the panel."""
        self.current_problem = problem
        self.attempt_start = datetime.now()
        self.hints_used = 0

        # Update problem panel
        content = self.query_one("#problem-content", Markdown)
        md = f"# {problem.title}\n\n**Difficulty:** {problem.difficulty}\n\n"
        md += f"**Tags:** {', '.join(problem.topic_tags)}\n\n---\n\n"
        # Convert HTML to markdown (simplified)
        md += problem.question.replace("<p>", "\n").replace("</p>", "\n")
        md += "\n".join(f"- {h}" for h in problem.hints[:2]) if problem.hints else ""
        content.update(md)

        # Set up coach context
        self.coach.set_problem_context(problem.title, problem.question)

        # Reset editor
        editor = self.query_one("#editor", CodeEditor)
        editor.text = LANGUAGE_TEMPLATES.get(self.settings.default_language, "")

    async def action_hint(self) -> None:
        """Request a hint from the coach."""
        if not self.current_problem:
            return

        self.hints_used += 1
        editor = self.query_one("#editor", CodeEditor)
        
        levels = ["gentle", "medium", "strong"]
        level = levels[min(self.hints_used - 1, 2)]
        
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Thinking...*")

        hint = await self.coach.get_hint(editor.text, level)  # type: ignore
        coach_content.update(f"**Hint ({level}):**\n\n{hint}")

    async def action_chat(self) -> None:
        """Send a message to the coach."""
        input_area = self.query_one("#coach-input", TextArea)
        message = input_area.text.strip()
        if not message:
            return

        input_area.text = ""
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Thinking...*")

        response = await self.coach.chat(message)
        coach_content.update(response)

    async def action_submit(self) -> None:
        """Submit solution and get review."""
        if not self.current_problem or not self.attempt_start:
            return

        editor = self.query_one("#editor", CodeEditor)
        code = editor.text

        # Save attempt
        attempt = Attempt(
            problem_slug=self.current_problem.title_slug,
            started_at=self.attempt_start,
            completed_at=datetime.now(),
            result="solved",
            hints_used=self.hints_used,
            code=code,
            language=self.settings.default_language,
        )
        self.db.save_attempt(attempt)

        # Get AI review
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Reviewing your solution...*")

        review = await self.coach.review_code(code, self.settings.default_language)
        coach_content.update(f"**Code Review:**\n\n{review}")

    async def action_next(self) -> None:
        """Get next problem."""
        coach_content = self.query_one("#coach-content", Markdown)
        coach_content.update("*Fetching next problem...*")

        problem = await self.client.get_daily()
        # Convert DailyProblem to Problem
        full_problem = await self.client.get_problem(problem.title_slug)
        await self._show_problem(full_problem)


class WelcomeScreen(Screen):
    """Welcome screen with options."""

    BINDINGS = [
        Binding("d", "daily", "Daily Challenge"),
        Binding("p", "problems", "Problem List"),
        Binding("s", "stats", "Statistics"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    #welcome-container {
        align: center middle;
    }

    #welcome-box {
        width: 60;
        height: auto;
        border: double green;
        padding: 2;
    }

    #title {
        text-align: center;
        text-style: bold;
    }

    .menu-item {
        margin: 1 0;
        text-align: center;
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

        with Container(id="welcome-container"):
            with Vertical(id="welcome-box"):
                yield Static("🏋️ GRIND", id="title")
                yield Static("", classes="menu-item")
                yield Static(f"🔥 {stats['streak']} day streak", classes="menu-item")
                yield Static(f"✅ {stats['unique_problems']} problems solved", classes="menu-item")
                yield Static("", classes="menu-item")
                yield Static("[d] Daily Challenge", classes="menu-item")
                yield Static("[p] Problem List", classes="menu-item")
                yield Static("[s] Statistics", classes="menu-item")
                yield Static("[q] Quit", classes="menu-item")

        yield Footer()

    async def action_daily(self) -> None:
        """Start daily challenge."""
        problem = await self.client.get_daily()
        full_problem = await self.client.get_problem(problem.title_slug)

        screen = PracticeScreen(
            self.settings, self.client, self.coach, self.db, full_problem
        )
        await self.app.push_screen(screen)


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
