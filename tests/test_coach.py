"""Tests for the AI Coach."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from grind.ai.coach import Coach
from grind.config import Settings, AgentConfig


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
        # Mock streaming response
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
        assert len(coach._conversation) == 2  # user + assistant
        assert coach._conversation[0]["content"] == "Hi there"
        assert coach._conversation[1]["content"] == "Hello World"

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
        assert "Time and space complexity" in call_args
        assert "Edge cases" in call_args

    @pytest.mark.asyncio
    async def test_review_code_cpp(self, coach):
        """Test code review with C++."""
        code = "int solve() { return 0; }"
        await coach.review_code(code, "cpp")

        call_args = coach.chat.call_args[0][0]
        assert "cpp" in call_args
        assert "```cpp" in call_args


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
