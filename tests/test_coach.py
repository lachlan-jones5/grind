"""Comprehensive tests for the AI Coach."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from grind.ai.coach import Coach
from grind.config import Settings, AgentConfig


# =============================================================================
# Coach Initialization Tests
# =============================================================================

class TestCoachInit:
    """Tests for Coach initialization."""

    def test_coach_init_copilot(self):
        """Test coach initializes with copilot provider."""
        settings = Settings(provider="copilot", copilot_relay_url="http://localhost:8080")

        with patch("grind.ai.coach.AsyncOpenAI") as mock_openai:
            coach = Coach(settings)

            mock_openai.assert_called_once_with(
                base_url="http://localhost:8080/v1",
                api_key="copilot",
            )
            assert coach._conversation == []

    def test_coach_init_openrouter(self):
        """Test coach initializes with openrouter provider."""
        settings = Settings(
            provider="openrouter",
            openrouter_api_key="sk-test-key",
            openrouter_base_url="https://openrouter.ai/api/v1",
        )

        with patch("grind.ai.coach.AsyncOpenAI") as mock_openai:
            coach = Coach(settings)

            mock_openai.assert_called_once_with(
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test-key",
            )

    def test_coach_init_openrouter_no_key(self):
        """Test coach initializes with openrouter but no key."""
        settings = Settings(
            provider="openrouter",
            openrouter_api_key=None,
        )

        with patch("grind.ai.coach.AsyncOpenAI") as mock_openai:
            Coach(settings)

            # Should use empty string for api_key
            call_args = mock_openai.call_args
            assert call_args.kwargs["api_key"] == ""

    def test_coach_init_custom_relay_url(self):
        """Test coach with custom relay URL."""
        settings = Settings(
            provider="copilot",
            copilot_relay_url="http://custom-host:9000",
        )

        with patch("grind.ai.coach.AsyncOpenAI") as mock_openai:
            Coach(settings)

            call_args = mock_openai.call_args
            assert call_args.kwargs["base_url"] == "http://custom-host:9000/v1"

    def test_coach_stores_settings(self):
        """Test coach stores settings reference."""
        settings = Settings(provider="copilot")

        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            assert coach.settings == settings


# =============================================================================
# Conversation Management Tests
# =============================================================================

class TestCoachConversation:
    """Tests for conversation management."""

    @pytest.fixture
    def coach(self):
        """Create a coach with mocked client."""
        settings = Settings(provider="copilot")
        with patch("grind.ai.coach.AsyncOpenAI"):
            return Coach(settings)

    def test_reset_conversation(self, coach):
        """Test conversation reset."""
        coach._conversation = [{"role": "user", "content": "test"}]
        coach.reset_conversation()
        assert coach._conversation == []

    def test_reset_conversation_already_empty(self, coach):
        """Test resetting already empty conversation."""
        coach._conversation = []
        coach.reset_conversation()
        assert coach._conversation == []

    def test_reset_conversation_multiple_messages(self, coach):
        """Test resetting conversation with multiple messages."""
        coach._conversation = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
        ]
        coach.reset_conversation()
        assert coach._conversation == []

    def test_set_problem_context(self, coach):
        """Test setting problem context."""
        coach.set_problem_context("Two Sum", "Given an array of integers...")

        assert len(coach._conversation) == 2
        assert coach._conversation[0]["role"] == "user"
        assert "Two Sum" in coach._conversation[0]["content"]
        assert "Given an array" in coach._conversation[0]["content"]
        assert coach._conversation[1]["role"] == "assistant"

    def test_set_problem_context_replaces_existing(self, coach):
        """Test setting problem context replaces existing conversation."""
        coach._conversation = [{"role": "user", "content": "old message"}]
        coach.set_problem_context("New Problem", "New description")

        assert len(coach._conversation) == 2
        assert "New Problem" in coach._conversation[0]["content"]

    def test_set_problem_context_format(self, coach):
        """Test problem context message format."""
        coach.set_problem_context("Test Title", "Test Description")

        user_msg = coach._conversation[0]
        assert "# Test Title" in user_msg["content"]
        assert "Test Description" in user_msg["content"]
        assert "I'm working on this problem" in user_msg["content"]

    def test_set_problem_context_with_html(self, coach):
        """Test setting problem context with HTML description."""
        html_desc = "<p>This is a <code>problem</code></p>"
        coach.set_problem_context("HTML Problem", html_desc)

        assert html_desc in coach._conversation[0]["content"]

    def test_set_problem_context_with_unicode(self, coach):
        """Test setting problem context with unicode."""
        coach.set_problem_context("日本語タイトル", "Description with émojis 🎉")

        assert "日本語タイトル" in coach._conversation[0]["content"]
        assert "🎉" in coach._conversation[0]["content"]

    def test_set_problem_context_assistant_response(self, coach):
        """Test assistant's initial response in context."""
        coach.set_problem_context("Test", "Desc")

        assistant_msg = coach._conversation[1]
        assert assistant_msg["role"] == "assistant"
        assert "I see the problem" in assistant_msg["content"]


# =============================================================================
# Chat Functionality Tests
# =============================================================================

class TestCoachChat:
    """Tests for chat functionality."""

    @pytest.fixture
    def coach(self):
        """Create a coach with mocked client."""
        settings = Settings(
            provider="copilot",
            agent=AgentConfig(model="gpt-4o", temperature=0.7),
        )
        with patch("grind.ai.coach.AsyncOpenAI") as mock_openai:
            coach = Coach(settings)
            coach._client = MagicMock()
            return coach

    @pytest.mark.asyncio
    async def test_chat_returns_full_response(self, coach):
        """Test chat method returns complete response."""
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=" World"))]),
            ]
            for chunk in chunks:
                yield chunk

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        result = await coach.chat("Hi there")

        assert result == "Hello World"
        assert len(coach._conversation) == 2
        assert coach._conversation[0]["content"] == "Hi there"
        assert coach._conversation[1]["content"] == "Hello World"

    @pytest.mark.asyncio
    async def test_chat_appends_to_conversation(self, coach):
        """Test chat appends messages to conversation history."""
        coach._conversation = [{"role": "user", "content": "previous"}]

        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="response"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        await coach.chat("new message")

        assert len(coach._conversation) == 3
        assert coach._conversation[1]["content"] == "new message"
        assert coach._conversation[2]["content"] == "response"

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, coach):
        """Test chat with empty message."""
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="response"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        result = await coach.chat("")

        assert result == "response"
        assert coach._conversation[0]["content"] == ""

    @pytest.mark.asyncio
    async def test_chat_long_message(self, coach):
        """Test chat with very long message."""
        long_message = "x" * 10000

        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="ok"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        await coach.chat(long_message)

        assert coach._conversation[0]["content"] == long_message

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, coach):
        """Test stream method yields individual chunks."""
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk1"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk2"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk3"))]),
            ]
            for chunk in chunks:
                yield chunk

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        chunks = []
        async for chunk in coach.stream("test message"):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2", "chunk3"]

    @pytest.mark.asyncio
    async def test_stream_handles_empty_delta(self, coach):
        """Test stream handles chunks with no content."""
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="text"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
                MagicMock(choices=[]),
            ]
            for chunk in chunks:
                yield chunk

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        chunks = []
        async for chunk in coach.stream("test"):
            chunks.append(chunk)

        assert chunks == ["text"]

    @pytest.mark.asyncio
    async def test_stream_handles_empty_choices(self, coach):
        """Test stream handles chunks with empty choices."""
        async def mock_stream():
            chunks = [
                MagicMock(choices=[]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="text"))]),
                MagicMock(choices=[]),
            ]
            for chunk in chunks:
                yield chunk

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        chunks = []
        async for chunk in coach.stream("test"):
            chunks.append(chunk)

        assert chunks == ["text"]

    @pytest.mark.asyncio
    async def test_chat_includes_system_prompt(self, coach):
        """Test chat includes system prompt in messages."""
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="response"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        await coach.chat("user message")

        call_args = coach._client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        assert messages[0]["role"] == "system"
        assert "coach" in messages[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_chat_uses_correct_model(self, coach):
        """Test chat uses model from settings."""
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="ok"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        await coach.chat("test")

        call_args = coach._client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_chat_uses_correct_temperature(self, coach):
        """Test chat uses temperature from settings."""
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="ok"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        await coach.chat("test")

        call_args = coach._client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_chat_enables_streaming(self, coach):
        """Test chat enables streaming mode."""
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="ok"))])

        coach._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        await coach.chat("test")

        call_args = coach._client.chat.completions.create.call_args
        assert call_args.kwargs["stream"] is True


# =============================================================================
# Hint Functionality Tests
# =============================================================================

class TestCoachHints:
    """Tests for hint functionality."""

    @pytest.fixture
    def coach(self):
        """Create a coach with mocked chat."""
        settings = Settings(provider="copilot")
        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            coach.chat = AsyncMock(return_value="Here's a hint...")
            return coach

    @pytest.mark.asyncio
    async def test_get_hint_gentle(self, coach):
        """Test gentle hint request."""
        result = await coach.get_hint("def solve(): pass", "gentle")

        assert result == "Here's a hint..."
        call_args = coach.chat.call_args[0][0]
        assert "subtle hint" in call_args
        assert "def solve()" in call_args

    @pytest.mark.asyncio
    async def test_get_hint_medium(self, coach):
        """Test medium hint request."""
        await coach.get_hint("code here", "medium")

        call_args = coach.chat.call_args[0][0]
        assert "pattern or technique" in call_args

    @pytest.mark.asyncio
    async def test_get_hint_strong(self, coach):
        """Test strong hint request."""
        await coach.get_hint("code here", "strong")

        call_args = coach.chat.call_args[0][0]
        assert "stuck" in call_args.lower()
        assert "clear hint" in call_args

    @pytest.mark.asyncio
    async def test_get_hint_includes_code(self, coach):
        """Test hint request includes user code."""
        code = "int solve() { return 42; }"
        await coach.get_hint(code, "gentle")

        call_args = coach.chat.call_args[0][0]
        assert code in call_args
        assert "```" in call_args  # Code block

    @pytest.mark.asyncio
    async def test_get_hint_empty_code(self, coach):
        """Test hint request with empty code."""
        await coach.get_hint("", "gentle")

        call_args = coach.chat.call_args[0][0]
        assert "```" in call_args

    @pytest.mark.asyncio
    async def test_get_hint_multiline_code(self, coach):
        """Test hint request with multiline code."""
        code = """def solve(nums):
    result = []
    for i in range(len(nums)):
        for j in range(i+1, len(nums)):
            if nums[i] + nums[j] == target:
                result.append([i, j])
    return result"""
        await coach.get_hint(code, "medium")

        call_args = coach.chat.call_args[0][0]
        assert "solve(nums)" in call_args

    @pytest.mark.asyncio
    async def test_get_hint_all_levels(self, coach):
        """Test all hint levels have different prompts."""
        prompts = []
        for level in ["gentle", "medium", "strong"]:
            await coach.get_hint("code", level)
            prompts.append(coach.chat.call_args[0][0])

        # All prompts should be different
        assert len(set(prompts)) == 3


# =============================================================================
# Code Review Tests
# =============================================================================

class TestCoachReview:
    """Tests for code review functionality."""

    @pytest.fixture
    def coach(self):
        """Create a coach with mocked chat."""
        settings = Settings(provider="copilot")
        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            coach.chat = AsyncMock(return_value="Review feedback...")
            return coach

    @pytest.mark.asyncio
    async def test_review_code(self, coach):
        """Test code review request."""
        code = "def two_sum(nums, target):\n    return [0, 1]"
        result = await coach.review_code(code, "python")

        assert result == "Review feedback..."
        call_args = coach.chat.call_args[0][0]
        assert "python" in call_args
        assert "two_sum" in call_args

    @pytest.mark.asyncio
    async def test_review_code_checks_complexity(self, coach):
        """Test review asks about complexity."""
        await coach.review_code("code", "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "Time and space complexity" in call_args

    @pytest.mark.asyncio
    async def test_review_code_checks_edge_cases(self, coach):
        """Test review asks about edge cases."""
        await coach.review_code("code", "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "Edge cases" in call_args

    @pytest.mark.asyncio
    async def test_review_code_checks_style(self, coach):
        """Test review asks about code style."""
        await coach.review_code("code", "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "Code style" in call_args or "readability" in call_args

    @pytest.mark.asyncio
    async def test_review_code_checks_optimizations(self, coach):
        """Test review asks about optimizations."""
        await coach.review_code("code", "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "optimization" in call_args.lower()

    @pytest.mark.asyncio
    async def test_review_code_checks_patterns(self, coach):
        """Test review asks about patterns."""
        await coach.review_code("code", "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "Pattern" in call_args or "technique" in call_args

    @pytest.mark.asyncio
    async def test_review_code_cpp(self, coach):
        """Test code review with C++."""
        code = "int solve() { return 0; }"
        await coach.review_code(code, "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "cpp" in call_args
        assert "```cpp" in call_args

    @pytest.mark.asyncio
    async def test_review_code_rust(self, coach):
        """Test code review with Rust."""
        code = "fn solve() -> i32 { 0 }"
        await coach.review_code(code, "rust")

        call_args = coach.chat.call_args[0][0]
        assert "rust" in call_args
        assert "```rust" in call_args

    @pytest.mark.asyncio
    async def test_review_code_ocaml(self, coach):
        """Test code review with OCaml."""
        code = "let solve () = 0"
        await coach.review_code(code, "ocaml")

        call_args = coach.chat.call_args[0][0]
        assert "ocaml" in call_args


# =============================================================================
# Approach Explanation Tests
# =============================================================================

class TestCoachExplain:
    """Tests for approach explanation."""

    @pytest.fixture
    def coach(self):
        """Create a coach with mocked chat."""
        settings = Settings(provider="copilot")
        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            coach.chat = AsyncMock(return_value="Explanation...")
            return coach

    @pytest.mark.asyncio
    async def test_explain_approach(self, coach):
        """Test approach explanation request."""
        result = await coach.explain_approach("two-pointer")

        assert result == "Explanation..."
        call_args = coach.chat.call_args[0][0]
        assert "two-pointer" in call_args
        assert "Explain" in call_args

    @pytest.mark.asyncio
    async def test_explain_various_approaches(self, coach):
        """Test explaining various algorithmic approaches."""
        approaches = [
            "two-pointer",
            "sliding-window",
            "binary-search",
            "dynamic-programming",
            "backtracking",
            "bfs",
            "dfs",
        ]

        for approach in approaches:
            await coach.explain_approach(approach)
            call_args = coach.chat.call_args[0][0]
            assert approach in call_args

    @pytest.mark.asyncio
    async def test_explain_approach_mentions_problem(self, coach):
        """Test explanation mentions applying to current problem."""
        await coach.explain_approach("greedy")

        call_args = coach.chat.call_args[0][0]
        assert "this problem" in call_args.lower()


# =============================================================================
# Agent Config Tests
# =============================================================================

class TestAgentConfiguration:
    """Tests for agent configuration."""

    def test_custom_system_prompt(self):
        """Test coach uses custom system prompt."""
        custom_prompt = "You are a strict interviewer."
        settings = Settings(
            provider="copilot",
            agent=AgentConfig(system_prompt=custom_prompt),
        )

        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            assert coach.settings.agent.system_prompt == custom_prompt

    def test_custom_temperature(self):
        """Test coach uses custom temperature."""
        settings = Settings(
            provider="copilot",
            agent=AgentConfig(temperature=0.3),
        )

        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            assert coach.settings.agent.temperature == 0.3

    def test_custom_model(self):
        """Test coach uses custom model."""
        settings = Settings(
            provider="copilot",
            agent=AgentConfig(model="gpt-3.5-turbo"),
        )

        with patch("grind.ai.coach.AsyncOpenAI"):
            coach = Coach(settings)
            assert coach.settings.agent.model == "gpt-3.5-turbo"
