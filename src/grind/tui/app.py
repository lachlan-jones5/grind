"""Main TUI application."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Footer, Header, Static, TextArea, Markdown, Label, Rule
from textual.screen import Screen

from grind.config import Settings, load_settings
from grind.api.leetcode import LeetCodeClient, Problem
from grind.ai.coach import Coach
from grind.db.database import Database, Attempt
from grind.tui.vim_editor import VimEditor, VimMode

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

LANGUAGES = ["cpp", "rust", "ocaml"]


class PracticeScreen(Screen):
    """Main practice screen with problem, editor, and coach."""

    BINDINGS = [
        Binding("f1", "hint", "Hint", priority=True),
        Binding("f2", "run", "Run", priority=True),
        Binding("f3", "submit", "Submit", priority=True),
        Binding("ctrl+enter", "submit_leetcode", "Submit to LC", priority=True),
        Binding("f4", "chat", "Chat", priority=True),
        Binding("f5", "next", "Next", priority=True),
        Binding("f6", "switch_language", "Lang", priority=True),
        Binding("ctrl+1", "lang_cpp", "C++", priority=True, show=False),
        Binding("ctrl+2", "lang_rust", "Rust", priority=True, show=False),
        Binding("ctrl+3", "lang_ocaml", "OCaml", priority=True, show=False),
        Binding("ctrl+q", "app_quit", "Quit", priority=True),
        Binding("ctrl+p", "focus_problem", "Problem", priority=True, show=False),
        Binding("ctrl+e", "focus_editor", "Editor", priority=True, show=False),
        Binding("ctrl+i", "focus_chat", "Chat", priority=True, show=False),
        Binding("ctrl+n", "focus_next", "Next Pane", priority=True),
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
        # Store code snippets from LeetCode keyed by langSlug
        self._code_snippets: dict[str, str] = {}
        # Store test cases from LeetCode
        self._test_cases: str = ""

    def compose(self) -> ComposeResult:
        stats = self.db.get_stats()
        streak = stats.get("streak", 0)
        solved = stats.get("unique_problems", 0)

        yield Static(
            f" GRIND | {streak} streak | {solved} solved | F1:Hint F3:Submit F4:Chat F5:Next F6:Lang Ctrl+N:Pane ",
            id="stats-header"
        )

        with ScrollableContainer(id="problem-pane"):
            yield Markdown(
                "# Welcome\n\nPress `F5` to load the daily challenge.\n\n"
                "**Vim Editor Keys:**\n"
                "- `i` - Insert mode\n"
                "- `Esc` - Normal mode\n"
                "- `h/j/k/l` - Move cursor\n"
                "- `dd` - Delete line\n"
                "- `yy` - Copy line\n"
                "- `p` - Paste\n\n"
                "**Pane Navigation:**\n"
                "- `Ctrl+N` - Next pane\n"
                "- `Ctrl+P` - Problem pane\n"
                "- `Ctrl+E` - Editor\n"
                "- `Ctrl+I` - Chat input",
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

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML content to Markdown for display.
        
        Handles common HTML elements from LeetCode problem descriptions:
        - Paragraphs, line breaks
        - Code blocks and inline code
        - Bold, italic, underline
        - Lists (ordered and unordered)
        - Tables
        - Superscript/subscript
        - Images
        - Links
        - HTML entities
        """
        import re
        
        text = html
        
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Handle code blocks first (preserve content)
        text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL)
        
        # Inline code
        text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)
        
        # Bold/strong
        text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.DOTALL)
        
        # Italic/emphasis
        text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL)
        
        # Underline (no markdown equivalent, use emphasis)
        text = re.sub(r"<u[^>]*>(.*?)</u>", r"_\1_", text, flags=re.DOTALL)
        
        # Strikethrough
        text = re.sub(r"<(s|strike|del)[^>]*>(.*?)</\1>", r"~~\2~~", text, flags=re.DOTALL)
        
        # Superscript (use ^ notation or just show inline)
        text = re.sub(r"<sup[^>]*>(.*?)</sup>", r"^\1", text, flags=re.DOTALL)
        
        # Subscript (use _ notation or just show inline)
        text = re.sub(r"<sub[^>]*>(.*?)</sub>", r"_\1", text, flags=re.DOTALL)
        
        # Headers
        text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.DOTALL)
        text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.DOTALL)
        text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.DOTALL)
        text = re.sub(r"<h4[^>]*>(.*?)</h4>", r"\n#### \1\n", text, flags=re.DOTALL)
        
        # Links
        text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.DOTALL)
        
        # Images - show alt text or URL
        text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*/?\s*>', r"[Image: \1]", text)
        text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*/?\s*>', r"[Image]", text)
        
        # Handle tables
        text = self._convert_html_tables(text)
        
        # Ordered lists - convert to numbered list (MUST be before unordered list processing)
        def replace_ol(match: re.Match) -> str:
            content = match.group(1)
            items = re.findall(r"<li[^>]*>(.*?)</li>", content, re.DOTALL)
            result = "\n"
            for i, item in enumerate(items, 1):
                result += f"{i}. {item.strip()}\n"
            return result + "\n"
        
        text = re.sub(r"<ol[^>]*>(.*?)</ol>", replace_ol, text, flags=re.DOTALL)
        
        # Unordered lists
        text = re.sub(r"<ul[^>]*>", "\n", text)
        text = re.sub(r"</ul>", "\n", text)
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL)
        
        # Paragraphs and line breaks
        text = re.sub(r"<p[^>]*>", "\n\n", text)
        text = re.sub(r"</p>", "", text)
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"<hr\s*/?>", "\n---\n", text)
        
        # Divs and spans (just remove tags, keep content)
        text = re.sub(r"<div[^>]*>", "\n", text)
        text = re.sub(r"</div>", "\n", text)
        text = re.sub(r"<span[^>]*>", "", text)
        text = re.sub(r"</span>", "", text)
        
        # Blockquotes
        text = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", r"\n> \1\n", text, flags=re.DOTALL)
        
        # Remove any remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        
        # HTML entities
        entities = {
            "&nbsp;": " ",
            "&lt;": "<",
            "&gt;": ">",
            "&amp;": "&",
            "&quot;": '"',
            "&apos;": "'",
            "&#39;": "'",
            "&ndash;": "–",
            "&mdash;": "—",
            "&lsquo;": "'",
            "&rsquo;": "'",
            "&ldquo;": """,
            "&rdquo;": """,
            "&bull;": "•",
            "&hellip;": "…",
            "&times;": "×",
            "&divide;": "÷",
            "&plusmn;": "±",
            "&le;": "≤",
            "&ge;": "≥",
            "&ne;": "≠",
            "&infin;": "∞",
            "&rarr;": "→",
            "&larr;": "←",
            "&uarr;": "↑",
            "&darr;": "↓",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        
        # Numeric entities
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
        
        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" +\n", "\n", text)
        text = re.sub(r"\n +", "\n", text)
        
        return text.strip()

    def _convert_html_tables(self, html: str) -> str:
        """Convert HTML tables to Markdown tables."""
        import re
        
        def table_to_markdown(match: re.Match) -> str:
            table_html = match.group(0)
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
            
            if not rows:
                return ""
            
            md_rows = []
            for i, row in enumerate(rows):
                # Extract cells (th or td)
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
                # Clean cell content
                cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                
                if not cells:
                    continue
                    
                md_rows.append("| " + " | ".join(cells) + " |")
                
                # Add separator after header row
                if i == 0:
                    separator = "| " + " | ".join(["---"] * len(cells)) + " |"
                    md_rows.append(separator)
            
            return "\n" + "\n".join(md_rows) + "\n"
        
        return re.sub(r"<table[^>]*>.*?</table>", table_to_markdown, html, flags=re.DOTALL)

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

        # Convert HTML to Markdown
        md += self._html_to_markdown(problem.question)

        if problem.hints:
            md += "\n\n---\n\n**Hints available:** " + str(len(problem.hints))

        content.update(md)

        # Set up coach context
        self.coach.set_problem_context(problem.title, problem.question)

        # Fetch code snippets from LeetCode API
        await self._fetch_code_snippets(problem.title_slug)

        # Reset editor with current language template
        editor = self.query_one("#editor", VimEditor)
        self._load_language_template(editor, self.current_language)

        # Update border title
        self.query_one("#problem-pane").border_title = f"Problem: {problem.title}"

    async def _fetch_code_snippets(self, title_slug: str) -> None:
        """Fetch code snippets from LeetCode for all languages."""
        self._code_snippets = {}
        self._test_cases = ""

        grind_app = self.app
        if not hasattr(grind_app, "leetcode_auth") or not grind_app.leetcode_auth:
            return

        try:
            problem_detail = await grind_app.leetcode_auth.get_problem_detail(title_slug)
            if problem_detail:
                # Extract code snippets
                snippets = problem_detail.get("codeSnippets", [])
                for snippet in snippets or []:
                    lang_slug = snippet.get("langSlug", "")
                    code = snippet.get("code", "")
                    if lang_slug and code:
                        self._code_snippets[lang_slug] = code

                # Extract test cases
                self._test_cases = problem_detail.get("sampleTestCase", "") or ""
        except Exception:
            # Fall back to static templates if fetch fails
            pass

    def _load_language_template(self, editor: VimEditor, language: str) -> None:
        """Load the appropriate code template for the language."""
        # Map our language names to LeetCode langSlugs
        lang_map = {
            "cpp": "cpp",
            "rust": "rust",
            "ocaml": "ocaml",
            "python": "python3",
            "java": "java",
            "javascript": "javascript",
            "typescript": "typescript",
            "go": "golang",
            "c": "c",
        }

        lc_lang = lang_map.get(language, language)

        if lc_lang in self._code_snippets:
            # Use LeetCode's template
            editor.text = self._code_snippets[lc_lang]
        elif language in self._code_snippets:
            editor.text = self._code_snippets[language]
        elif language in LANGUAGE_TEMPLATES:
            # Fall back to static template
            editor.text = LANGUAGE_TEMPLATES[language]
        else:
            # Generic fallback
            editor.text = f"// TODO: implement solution in {language}\n"

        # Reset cursor to beginning
        editor.cursor_location = (0, 0)

    def _switch_to_language(self, language: str) -> None:
        """Switch to a different programming language."""
        self.current_language = language
        editor = self.query_one("#editor", VimEditor)
        self._load_language_template(editor, language)
        self._update_editor_title()

    async def action_run(self) -> None:
        """Run code against test cases on LeetCode."""
        if not self.current_problem:
            return

        editor = self.query_one("#editor", VimEditor)
        code = editor.text
        coach_content = self.query_one("#coach-content", Markdown)

        # Check if we're authenticated
        grind_app = self.app
        if not hasattr(grind_app, "leetcode_auth") or not grind_app.leetcode_auth:
            coach_content.update(
                "**Not authenticated with LeetCode**\n\n"
                "Run `grind auth login` to connect your account."
            )
            return

        coach_content.update("*Running code...*")

        try:
            # Map language to LeetCode langSlug
            lang_map = {
                "cpp": "cpp",
                "rust": "rust",
                "ocaml": "ocaml",
                "python": "python3",
                "java": "java",
                "javascript": "javascript",
                "typescript": "typescript",
                "go": "golang",
                "c": "c",
            }
            lc_lang = lang_map.get(self.current_language, self.current_language)

            result = await grind_app.leetcode_auth.run_code(
                title_slug=self.current_problem.title_slug,
                code=code,
                lang=lc_lang,
                test_cases=self._test_cases if self._test_cases else None,
            )

            if not result:
                coach_content.update("**Run failed:** No result returned")
                return

            # Format the result
            status = result.get("status_msg", result.get("state", "Unknown"))
            run_success = result.get("run_success", False)
            
            if run_success and result.get("correct_answer"):
                # All test cases passed
                total_testcases = result.get("total_testcases", "?")
                runtime = result.get("status_runtime", "N/A")
                coach_content.update(
                    f"**Run Result: Accepted**\n\n"
                    f"All {total_testcases} test cases passed\n"
                    f"Runtime: {runtime}"
                )
            elif run_success:
                # Some test cases failed
                total_correct = result.get("total_correct", 0)
                total_testcases = result.get("total_testcases", 0)
                
                # Show failed test case details
                msg = f"**Run Result:** {total_correct}/{total_testcases} test cases passed\n\n"
                
                if result.get("code_answer"):
                    msg += f"**Your output:** `{result.get('code_answer')}`\n"
                if result.get("expected_code_answer"):
                    msg += f"**Expected:** `{result.get('expected_code_answer')}`\n"
                if result.get("std_output"):
                    msg += f"\n**Stdout:**\n```\n{result.get('std_output')}\n```"
                
                coach_content.update(msg)
            else:
                # Compile error or runtime error
                msg = f"**Run Result: {status}**\n\n"
                
                if result.get("compile_error"):
                    msg += f"```\n{result.get('full_compile_error', result.get('compile_error'))}\n```"
                elif result.get("runtime_error"):
                    msg += f"```\n{result.get('full_runtime_error', result.get('runtime_error'))}\n```"
                elif result.get("status_msg"):
                    msg += result.get("status_msg")
                
                coach_content.update(msg)

        except Exception as e:
            error_msg = str(e)
            if "Not authenticated" in error_msg or "Session expired" in error_msg:
                coach_content.update(
                    "**Session expired**\n\n"
                    "Run `grind auth login` to reconnect."
                )
            else:
                coach_content.update(f"**Run failed:**\n\n{error_msg}")

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

    async def action_submit_leetcode(self) -> None:
        """Submit solution to LeetCode."""
        if not self.current_problem or not self.attempt_start:
            return

        editor = self.query_one("#editor", VimEditor)
        code = editor.text
        coach_content = self.query_one("#coach-content", Markdown)

        # Check if we're authenticated
        grind_app = self.app
        if not hasattr(grind_app, 'leetcode_auth') or not grind_app.leetcode_auth:
            coach_content.update(
                "**Not authenticated with LeetCode**\n\n"
                "Run `grind auth login` to connect your account."
            )
            return

        coach_content.update("*Submitting to LeetCode...*")

        try:
            from grind.sync.submission import SubmissionService, format_submission_result

            submission_svc = SubmissionService(auth=grind_app.leetcode_auth)
            result = await submission_svc.submit(
                problem_slug=self.current_problem.title_slug,
                code=code,
                language=self.current_language,
            )

            # Format and display result
            result_text = format_submission_result(result)
            
            if result.is_accepted:
                # Save successful attempt
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

                # Mark as solved locally
                from grind.sync import SyncService
                sync_svc = SyncService(self.settings.get_db_path())
                sync_svc.mark_problem_solved_locally(self.current_problem.title_slug)

                coach_content.update(f"**LeetCode Result:**\n\n{result_text}")
            else:
                coach_content.update(f"**LeetCode Result:**\n\n{result_text}")

        except Exception as e:
            error_msg = str(e)
            if "Not authenticated" in error_msg:
                coach_content.update(
                    "**Not authenticated with LeetCode**\n\n"
                    "Run `grind auth login` to connect your account."
                )
            elif "Session expired" in error_msg:
                coach_content.update(
                    "**Session expired**\n\n"
                    "Run `grind auth login` to reconnect."
                )
            else:
                coach_content.update(f"**Submission failed:**\n\n{error_msg}")

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


class ProblemsScreen(Screen):
    """Screen for browsing problems and study plans."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select", "Select"),
        Binding("1", "plan_top150", "Top 150"),
        Binding("2", "plan_blind75", "Blind 75"),
        Binding("3", "plan_grind75", "Grind 75"),
        Binding("4", "plan_neetcode150", "NeetCode 150"),
        Binding("5", "plan_all", "All Problems"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("u", "filter_unsolved", "Unsolved"),
        Binding("a", "filter_all", "Show All"),
    ]

    CSS = """
    ProblemsScreen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 2fr;
    }

    #plans-pane {
        border: solid $primary;
        border-title-color: $primary;
        padding: 1 2;
    }

    #problems-pane {
        border: solid $secondary;
        border-title-color: $secondary;
        padding: 1 2;
    }

    .plan-item {
        padding: 0 1;
        height: 1;
    }

    .plan-item:hover {
        background: $primary-darken-2;
    }

    .plan-selected {
        background: $primary;
        color: $text;
    }

    .problem-item {
        padding: 0 1;
        height: 1;
    }

    .problem-item:hover {
        background: $surface-lighten-1;
    }

    .problem-easy {
        color: $success;
    }

    .problem-medium {
        color: $warning;
    }

    .problem-hard {
        color: $error;
    }

    .problem-solved {
        text-style: italic;
        color: $text-muted;
    }

    .filter-indicator {
        padding: 1 0;
        text-align: center;
        color: $warning;
    }

    .loading-indicator {
        text-align: center;
        padding: 2;
        color: $text-muted;
    }
    """

    # Filter modes
    FILTER_ALL = "all"
    FILTER_UNSOLVED = "unsolved"
    FILTER_SOLVED = "solved"

    # Study plan definitions
    STUDY_PLANS = {
        "top150": {
            "name": "Top 150 Interview Questions",
            "slug": "top-interview-150",
            "description": "Curated list of 150 must-do problems for interviews",
        },
        "blind75": {
            "name": "Blind 75",
            "slug": "blind-75",
            "description": "Classic 75 problems for interview prep",
        },
        "grind75": {
            "name": "Grind 75",
            "slug": "grind-75",
            "description": "Updated and improved version of Blind 75",
        },
        "neetcode150": {
            "name": "NeetCode 150",
            "slug": "neetcode-150",
            "description": "Comprehensive problem set by NeetCode",
        },
        "all": {
            "name": "All Problems",
            "slug": None,
            "description": "Browse all LeetCode problems",
        },
    }

    def __init__(
        self,
        settings: Settings,
        client: LeetCodeClient,
        coach: Coach,
        db: Database,
    ):
        super().__init__()
        self.settings = settings
        self.client = client
        self.coach = coach
        self.db = db
        self.current_plan = "top150"
        self.problems: list[dict] = []
        self.filtered_problems: list[dict] = []  # Problems after filtering
        self.selected_index = 0
        self.current_filter = self.FILTER_ALL
        self._solved_slugs: set[str] = set()

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="plans-pane"):
            yield Static("[1] Top 150 Interview Questions", classes="plan-item plan-selected", id="plan-top150")
            yield Static("[2] Blind 75", classes="plan-item", id="plan-blind75")
            yield Static("[3] Grind 75", classes="plan-item", id="plan-grind75")
            yield Static("[4] NeetCode 150", classes="plan-item", id="plan-neetcode150")
            yield Static("[5] All Problems", classes="plan-item", id="plan-all")
            yield Rule()
            yield Static("[f] Filter  [u] Unsolved  [a] All", classes="plan-item")

        with ScrollableContainer(id="problems-pane"):
            yield Static("Loading problems...", classes="loading-indicator")

        yield Footer()

    async def on_mount(self) -> None:
        """Load initial problems."""
        self.query_one("#plans-pane").border_title = "Study Plans"
        self.query_one("#problems-pane").border_title = "Problems"
        await self._load_solved_status()
        await self._load_problems()

    async def _load_solved_status(self) -> None:
        """Load set of solved problem slugs."""
        try:
            from grind.sync import SyncService
            sync_svc = SyncService(self.settings.get_db_path())
            solved = sync_svc.get_solved_problems()
            # ProblemStatus objects have 'slug' attribute
            self._solved_slugs = set(p.slug for p in solved)
        except Exception as e:
            self._solved_slugs = set()

    async def _load_problems(self) -> None:
        """Load problems for the current study plan."""
        problems_pane = self.query_one("#problems-pane", ScrollableContainer)

        # Clear existing content
        for child in list(problems_pane.children):
            await child.remove()

        # Create loading indicator with unique ID to avoid duplicates
        loading_widget = Static("Loading...", classes="loading-indicator")
        await problems_pane.mount(loading_widget)

        try:
            plan = self.STUDY_PLANS[self.current_plan]
            if plan["slug"]:
                # Load study plan problems
                self.problems = await self.client.get_study_plan_problems(plan["slug"])
            else:
                # Load all problems
                self.problems = await self.client.get_problems(limit=50)

            # Apply filter
            self._apply_filter()

            # Remove loading indicator
            await loading_widget.remove()

            # Show filter indicator if filtering
            if self.current_filter != self.FILTER_ALL:
                filter_text = f"Showing: {self.current_filter} ({len(self.filtered_problems)}/{len(self.problems)})"
                filter_widget = Static(filter_text, classes="filter-indicator")
                await problems_pane.mount(filter_widget)

            # Add problem items
            for i, problem in enumerate(self.filtered_problems):
                title = problem.get("title", problem.get("questionTitle", "Unknown"))
                slug = problem.get("titleSlug", problem.get("title_slug", ""))
                difficulty = problem.get("difficulty", "Medium")
                is_solved = slug in self._solved_slugs

                diff_class = f"problem-{difficulty.lower()}"
                solved_class = " problem-solved" if is_solved else ""
                solved_marker = "✓ " if is_solved else "  "

                item = Static(
                    f"{i+1:3}. {solved_marker}[{difficulty[0]}] {title}",
                    classes=f"problem-item {diff_class}{solved_class}",
                    id=f"problem-{i}",
                )
                item.data_slug = slug  # type: ignore
                item.data_index = i  # type: ignore
                await problems_pane.mount(item)

        except Exception as e:
            # Update loading widget to show error
            loading_widget.update(f"Error loading problems: {e}")

    def _apply_filter(self) -> None:
        """Apply current filter to problems list."""
        if self.current_filter == self.FILTER_ALL:
            self.filtered_problems = self.problems
        elif self.current_filter == self.FILTER_UNSOLVED:
            self.filtered_problems = [
                p for p in self.problems
                if p.get("titleSlug", p.get("title_slug", "")) not in self._solved_slugs
            ]
        elif self.current_filter == self.FILTER_SOLVED:
            self.filtered_problems = [
                p for p in self.problems
                if p.get("titleSlug", p.get("title_slug", "")) in self._solved_slugs
            ]
        else:
            self.filtered_problems = self.problems

    async def action_toggle_filter(self) -> None:
        """Toggle through filter modes."""
        if self.current_filter == self.FILTER_ALL:
            self.current_filter = self.FILTER_UNSOLVED
        elif self.current_filter == self.FILTER_UNSOLVED:
            self.current_filter = self.FILTER_SOLVED
        else:
            self.current_filter = self.FILTER_ALL
        self.selected_index = 0
        await self._load_problems()

    async def action_filter_unsolved(self) -> None:
        """Filter to show only unsolved problems."""
        self.current_filter = self.FILTER_UNSOLVED
        self.selected_index = 0
        await self._load_problems()

    async def action_filter_all(self) -> None:
        """Show all problems (no filter)."""
        self.current_filter = self.FILTER_ALL
        self.selected_index = 0
        await self._load_problems()

    def _update_plan_selection(self) -> None:
        """Update visual selection of study plans."""
        for plan_key in self.STUDY_PLANS:
            plan_id = f"plan-{plan_key}"
            try:
                plan_widget = self.query_one(f"#{plan_id}", Static)
                if plan_key == self.current_plan:
                    plan_widget.add_class("plan-selected")
                else:
                    plan_widget.remove_class("plan-selected")
            except Exception:
                pass

    async def _switch_plan(self, plan_key: str) -> None:
        """Switch to a different study plan."""
        self.current_plan = plan_key
        self.selected_index = 0
        self._update_plan_selection()
        await self._load_problems()

    async def action_plan_top150(self) -> None:
        await self._switch_plan("top150")

    async def action_plan_blind75(self) -> None:
        await self._switch_plan("blind75")

    async def action_plan_grind75(self) -> None:
        await self._switch_plan("grind75")

    async def action_plan_neetcode150(self) -> None:
        await self._switch_plan("neetcode150")

    async def action_plan_all(self) -> None:
        await self._switch_plan("all")

    async def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    async def action_cursor_down(self) -> None:
        """Move cursor down in problem list."""
        if self.selected_index < len(self.filtered_problems) - 1:
            self.selected_index += 1
            self._update_problem_selection()

    async def action_cursor_up(self) -> None:
        """Move cursor up in problem list."""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._update_problem_selection()

    def _update_problem_selection(self) -> None:
        """Update visual selection in problem list."""
        problems_pane = self.query_one("#problems-pane", ScrollableContainer)
        for i in range(len(self.filtered_problems)):
            try:
                item = problems_pane.query_one(f"#problem-{i}", Static)
                if i == self.selected_index:
                    item.styles.background = "dodgerblue"
                else:
                    item.styles.background = None
            except Exception:
                pass

    async def action_select(self) -> None:
        """Select the current problem and start practicing."""
        if not self.filtered_problems or self.selected_index >= len(self.filtered_problems):
            return

        problem_data = self.filtered_problems[self.selected_index]
        slug = problem_data.get("titleSlug", problem_data.get("title_slug", ""))

        if not slug:
            return

        try:
            # Fetch full problem details
            problem = await self.client.get_problem(slug)

            # Switch to practice screen
            screen = PracticeScreen(
                self.settings, self.client, self.coach, self.db, problem=problem
            )
            await self.app.push_screen(screen)
        except Exception as e:
            # Show error in problems pane
            pass


class LoginRequiredScreen(Screen):
    """Screen shown when user is not logged in."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "retry", "Retry"),
    ]

    CSS = """
    LoginRequiredScreen {
        align: center middle;
    }

    #login-box {
        width: 60;
        height: auto;
        border: heavy $error;
        padding: 2 4;
        background: $surface;
    }

    #login-title {
        text-align: center;
        text-style: bold;
        color: $error;
        padding: 1 0;
    }

    #login-message {
        text-align: center;
        padding: 1 0;
    }

    .login-code {
        text-align: center;
        color: $primary;
        text-style: bold;
        padding: 1 0;
    }

    .login-hint {
        text-align: center;
        color: $text-muted;
        padding: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Login Required", id="login-title")
            yield Rule()
            yield Static(
                "Grind requires a LeetCode account to function.",
                id="login-message"
            )
            yield Static("")
            yield Static("To log in, run:", classes="login-hint")
            yield Static("grind auth login --session <SESSION> --csrf <CSRF>", classes="login-code")
            yield Static("")
            yield Static("Get cookies from leetcode.com (F12 > Application > Cookies)", classes="login-hint")
            yield Rule()
            yield Static("[r] Retry  |  [q] Quit", classes="login-hint")

        yield Footer()

    async def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    async def action_retry(self) -> None:
        """Retry authentication check."""
        grind_app = self.app
        if hasattr(grind_app, "leetcode_auth") and grind_app.leetcode_auth:
            try:
                is_auth = await grind_app.leetcode_auth.is_authenticated()
                if is_auth:
                    session = grind_app.leetcode_auth.get_session()
                    if session:
                        grind_app.leetcode_username = session.username
                        grind_app.is_online = True
                    # Pop this screen and show welcome
                    self.app.pop_screen()
                    await self.app.push_screen(
                        WelcomeScreen(
                            grind_app.settings,
                            grind_app.client,
                            grind_app.coach,
                            grind_app.db,
                            grind_app
                        )
                    )
            except Exception:
                pass  # Stay on this screen


class StatsScreen(Screen):
    """Statistics and progress dashboard screen."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    CSS = """
    StatsScreen {
        align: center middle;
    }

    #stats-container {
        width: 70;
        height: auto;
        max-height: 90%;
        border: double $primary;
        padding: 1 2;
        background: $surface;
    }

    #stats-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1 0;
    }

    .stats-section {
        padding: 1 0;
    }

    .stats-section-title {
        text-style: bold;
        color: $secondary;
        padding-bottom: 1;
    }

    .stats-row {
        padding: 0 1;
    }

    .progress-bar-container {
        height: 1;
        padding: 0 1;
    }

    .progress-label {
        width: 10;
    }

    .progress-bar {
        width: 30;
    }

    .progress-value {
        width: 15;
        text-align: right;
    }

    .easy-color {
        color: $success;
    }

    .medium-color {
        color: $warning;
    }

    .hard-color {
        color: $error;
    }

    .queue-info {
        color: $warning;
        padding-top: 1;
    }

    .sync-status {
        color: $text-muted;
        text-align: center;
        padding-top: 1;
    }
    """

    def __init__(self, settings: "Settings", db: "Database", grind_app: "GrindApp | None" = None):
        super().__init__()
        self.settings = settings
        self.db = db
        self.grind_app = grind_app
        self._stats: dict = {}
        self._sync_stats: dict = {}
        self._difficulty_counts: dict = {}

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="stats-container"):
            yield Static("Your Progress", id="stats-title")
            yield Rule()

            # Local stats section
            with Vertical(classes="stats-section"):
                yield Static("Local Practice", classes="stats-section-title")
                yield Static("", id="local-stats")

            yield Rule()

            # LeetCode stats section
            with Vertical(classes="stats-section"):
                yield Static("LeetCode Progress", classes="stats-section-title")
                yield Static("", id="leetcode-stats")

            yield Rule()

            # Progress bars section
            with Vertical(classes="stats-section"):
                yield Static("By Difficulty", classes="stats-section-title")
                yield Static("", id="easy-progress", classes="progress-bar-container")
                yield Static("", id="medium-progress", classes="progress-bar-container")
                yield Static("", id="hard-progress", classes="progress-bar-container")

            yield Rule()

            # Sync info
            yield Static("", id="sync-status", classes="sync-status")

        yield Footer()

    async def on_mount(self) -> None:
        """Load and display statistics."""
        await self._refresh_stats()

    async def _refresh_stats(self) -> None:
        """Refresh all statistics displays."""
        # Get local stats
        self._stats = self.db.get_stats()

        # Try to get sync stats
        try:
            from grind.sync import SyncService
            sync_svc = SyncService(self.settings.get_db_path())
            self._sync_stats = sync_svc.get_sync_stats()
            self._difficulty_counts = self._get_difficulty_counts(sync_svc)
        except Exception:
            self._sync_stats = {}
            self._difficulty_counts = {}

        self._update_display()

    def _get_difficulty_counts(self, sync_svc: "SyncService") -> dict:
        """Get counts by difficulty from problem_status table."""
        try:
            with sync_svc._connect() as conn:
                # Total problems by difficulty
                totals = conn.execute("""
                    SELECT difficulty, COUNT(*) as total,
                           SUM(CASE WHEN solved_leetcode = 1 OR solved_locally = 1 THEN 1 ELSE 0 END) as solved
                    FROM problem_status
                    WHERE is_premium = 0 AND difficulty IS NOT NULL
                    GROUP BY difficulty
                """).fetchall()

                result = {"Easy": {"total": 0, "solved": 0},
                          "Medium": {"total": 0, "solved": 0},
                          "Hard": {"total": 0, "solved": 0}}

                for row in totals:
                    diff = row["difficulty"]
                    if diff in result:
                        result[diff]["total"] = row["total"]
                        result[diff]["solved"] = row["solved"]

                return result
        except Exception:
            return {}

    def _update_display(self) -> None:
        """Update all display widgets."""
        # Local stats
        local_stats = self.query_one("#local-stats", Static)
        streak = self._stats.get("streak", 0)
        solved = self._stats.get("unique_problems", 0)
        attempts = self._stats.get("total_attempts", 0)
        local_stats.update(
            f"  Streak: {streak} days\n"
            f"  Problems solved: {solved}\n"
            f"  Total attempts: {attempts}"
        )

        # LeetCode stats
        leetcode_stats = self.query_one("#leetcode-stats", Static)
        if self._sync_stats:
            lc_solved = self._sync_stats.get("solved_leetcode", 0)
            submissions = self._sync_stats.get("total_submissions", 0)
            accepted = self._sync_stats.get("accepted_submissions", 0)
            leetcode_stats.update(
                f"  Problems solved: {lc_solved}\n"
                f"  Total submissions: {submissions}\n"
                f"  Accepted: {accepted}"
            )
        else:
            leetcode_stats.update("  Not synced. Run 'grind sync' to fetch data.")

        # Progress bars by difficulty
        self._update_progress_bar("easy", "Easy", "$success")
        self._update_progress_bar("medium", "Medium", "$warning")
        self._update_progress_bar("hard", "Hard", "$error")

        # Sync status
        sync_status = self.query_one("#sync-status", Static)
        if self._sync_stats and self._sync_stats.get("last_sync"):
            last_sync = self._sync_stats["last_sync"]
            sync_status.update(f"Last synced: {last_sync.strftime('%Y-%m-%d %H:%M')}")
        else:
            sync_status.update("Never synced")

    def _update_progress_bar(self, widget_id: str, difficulty: str, color: str) -> None:
        """Update a progress bar widget."""
        widget = self.query_one(f"#{widget_id}-progress", Static)

        if difficulty not in self._difficulty_counts or not self._difficulty_counts[difficulty]["total"]:
            widget.update(f"  {difficulty}: No data")
            return

        data = self._difficulty_counts[difficulty]
        total = data["total"]
        solved = data["solved"]
        pct = (solved / total * 100) if total > 0 else 0

        # Create visual progress bar
        bar_width = 20
        filled = int(bar_width * pct / 100)
        empty = bar_width - filled
        bar = "█" * filled + "░" * empty

        widget.update(f"  {difficulty:6} {bar} {solved:4}/{total:4} ({pct:5.1f}%)")

    async def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    async def action_refresh(self) -> None:
        """Refresh statistics."""
        await self._refresh_stats()


class WelcomeScreen(Screen):
    """Welcome screen with options."""

    BINDINGS = [
        Binding("d", "daily", "Daily Challenge"),
        Binding("p", "problems", "Problem List"),
        Binding("s", "stats", "Statistics"),
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

    .offline-status {
        color: $warning;
        text-style: bold;
    }
    """

    def __init__(self, settings: Settings, client: LeetCodeClient, coach: Coach, db: Database, grind_app: "GrindApp | None" = None):
        super().__init__()
        self.settings = settings
        self.client = client
        self.coach = coach
        self.db = db
        self.grind_app = grind_app

    def compose(self) -> ComposeResult:
        stats = self.db.get_stats()

        # Get auth status
        auth_status = ""
        if self.grind_app and self.grind_app.leetcode_username:
            auth_status = f"Logged in as: {self.grind_app.leetcode_username}"
        else:
            auth_status = "Not logged in (grind auth login)"

        with Vertical(id="welcome-box"):
            yield Static("GRIND", id="title")
            yield Static("AI-Powered LeetCode Practice", id="subtitle")
            yield Rule()
            yield Static(auth_status, classes="stat-row", id="auth-status")
            yield Static(f"{stats['streak']} day streak  |  {stats['unique_problems']} solved", classes="stat-row")
            yield Rule()
            yield Static("", classes="menu-section")
            yield Static("[d]  Daily Challenge", classes="menu-item")
            yield Static("[p]  Problem List", classes="menu-item")
            yield Static("[s]  Statistics", classes="menu-item")
            yield Static("[q]  Quit", classes="menu-item")

        yield Footer()

    async def action_daily(self) -> None:
        """Start daily challenge."""
        screen = PracticeScreen(self.settings, self.client, self.coach, self.db)
        await self.app.push_screen(screen)
        # Trigger loading the daily problem
        await screen.action_next()

    async def action_problems(self) -> None:
        """Open problem list and study plans."""
        screen = ProblemsScreen(self.settings, self.client, self.coach, self.db)
        await self.app.push_screen(screen)

    async def action_stats(self) -> None:
        """Open statistics dashboard."""
        screen = StatsScreen(self.settings, self.db, self.grind_app)
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
        self.leetcode_auth: "LeetCodeAuth | None" = None
        self.leetcode_username: str | None = None
        self.is_online: bool = True

    async def on_mount(self) -> None:
        """Mount the welcome screen and check auth status."""
        # Initialize LeetCode auth
        from grind.auth import LeetCodeAuth
        self.leetcode_auth = LeetCodeAuth()

        # Check authentication status - REQUIRED
        is_authenticated = False
        try:
            is_authenticated = await self.leetcode_auth.is_authenticated()
            if is_authenticated:
                session = self.leetcode_auth.get_session()
                if session:
                    self.leetcode_username = session.username
                    self.is_online = True
        except Exception:
            self.is_online = False

        if not is_authenticated:
            # Show login required screen
            await self.push_screen(LoginRequiredScreen())
            return

        await self.push_screen(WelcomeScreen(self.settings, self.client, self.coach, self.db, self))

    async def on_unmount(self) -> None:
        """Clean up resources."""
        await self.client.close()
        if self.leetcode_auth:
            await self.leetcode_auth.close()


def run() -> None:
    """Run the Grind TUI."""
    app = GrindApp()
    app.run()
