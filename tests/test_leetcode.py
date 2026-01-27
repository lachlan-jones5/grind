"""Tests for the LeetCode API client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from grind.api.leetcode import (
    LeetCodeClient,
    Problem,
    DailyProblem,
    UserStats,
)


class TestProblemModels:
    """Tests for Pydantic models."""

    def test_problem_from_api_response(self):
        """Test Problem model parses API response correctly."""
        data = {
            "title": "Two Sum",
            "titleSlug": "two-sum",
            "difficulty": "Easy",
            "question": "<p>Given an array...</p>",
            "topicTags": ["array", "hash-table"],
            "hints": ["Try using a hash map"],
            "exampleTestcases": [{"input": "[2,7,11,15]", "output": "[0,1]"}],
        }
        problem = Problem.model_validate(data)

        assert problem.title == "Two Sum"
        assert problem.title_slug == "two-sum"
        assert problem.difficulty == "Easy"
        assert "array" in problem.topic_tags
        assert len(problem.hints) == 1

    def test_problem_with_missing_optional_fields(self):
        """Test Problem model handles missing optional fields."""
        data = {
            "title": "Test Problem",
            "titleSlug": "test-problem",
            "difficulty": "Medium",
            "question": "Description here",
        }
        problem = Problem.model_validate(data)

        assert problem.title == "Test Problem"
        assert problem.topic_tags == []
        assert problem.hints == []
        assert problem.examples == []

    def test_daily_problem_model(self):
        """Test DailyProblem model."""
        data = {
            "date": "2024-01-15",
            "questionTitle": "Daily Challenge",
            "titleSlug": "daily-challenge",
            "difficulty": "Hard",
            "question": "Solve this...",
        }
        daily = DailyProblem.model_validate(data)

        assert daily.date == "2024-01-15"
        assert daily.title == "Daily Challenge"
        assert daily.title_slug == "daily-challenge"

    def test_user_stats_model(self):
        """Test UserStats model."""
        data = {
            "totalSolved": 150,
            "easySolved": 50,
            "mediumSolved": 75,
            "hardSolved": 25,
            "ranking": 12345,
        }
        stats = UserStats.model_validate(data)

        assert stats.total_solved == 150
        assert stats.easy_solved == 50
        assert stats.medium_solved == 75
        assert stats.hard_solved == 25
        assert stats.ranking == 12345

    def test_user_stats_default_ranking(self):
        """Test UserStats with missing ranking defaults to 0."""
        data = {
            "totalSolved": 10,
            "easySolved": 5,
            "mediumSolved": 3,
            "hardSolved": 2,
        }
        stats = UserStats.model_validate(data)
        assert stats.ranking == 0


class TestLeetCodeClient:
    """Tests for LeetCodeClient."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return LeetCodeClient("https://test-api.example.com")

    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        def _mock_response(data: dict, status_code: int = 200):
            response = MagicMock(spec=httpx.Response)
            response.status_code = status_code
            response.json.return_value = data
            response.raise_for_status = MagicMock()
            if status_code >= 400:
                response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Error", request=MagicMock(), response=response
                )
            return response
        return _mock_response

    def test_client_init(self, client):
        """Test client initialization."""
        assert client.base_url == "https://test-api.example.com"

    def test_client_strips_trailing_slash(self):
        """Test client strips trailing slash from base URL."""
        client = LeetCodeClient("https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_get_daily(self, client, mock_response):
        """Test getting daily challenge."""
        response_data = {
            "date": "2024-01-15",
            "questionTitle": "Daily Problem",
            "titleSlug": "daily-problem",
            "difficulty": "Medium",
            "question": "Solve this problem",
        }

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            result = await client.get_daily()

        assert result.title == "Daily Problem"
        assert result.title_slug == "daily-problem"
        mock_get.assert_called_once_with("https://test-api.example.com/daily")

    @pytest.mark.asyncio
    async def test_get_problem(self, client, mock_response):
        """Test getting a specific problem."""
        response_data = {
            "title": "Two Sum",
            "titleSlug": "two-sum",
            "difficulty": "Easy",
            "question": "<p>Given an array...</p>",
            "topicTags": ["array"],
            "hints": [],
        }

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            result = await client.get_problem("two-sum")

        assert result.title == "Two Sum"
        mock_get.assert_called_once_with(
            "https://test-api.example.com/select",
            params={"titleSlug": "two-sum"}
        )

    @pytest.mark.asyncio
    async def test_get_problems_with_filters(self, client, mock_response):
        """Test getting problems with filters."""
        response_data = {
            "problemsetQuestionList": [
                {"title": "Problem 1", "titleSlug": "problem-1"},
                {"title": "Problem 2", "titleSlug": "problem-2"},
            ]
        }

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            result = await client.get_problems(
                limit=10, skip=5, difficulty="Medium", tags=["array", "dp"]
            )

        assert len(result) == 2
        mock_get.assert_called_once_with(
            "https://test-api.example.com/problems",
            params={"limit": 10, "skip": 5, "difficulty": "Medium", "tags": "array,dp"}
        )

    @pytest.mark.asyncio
    async def test_get_problems_without_filters(self, client, mock_response):
        """Test getting problems without optional filters."""
        response_data = {"problemsetQuestionList": []}

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            await client.get_problems(limit=20, skip=0)

        mock_get.assert_called_once_with(
            "https://test-api.example.com/problems",
            params={"limit": 20, "skip": 0}
        )

    @pytest.mark.asyncio
    async def test_get_user_stats(self, client, mock_response):
        """Test getting user statistics."""
        response_data = {
            "totalSolved": 100,
            "easySolved": 40,
            "mediumSolved": 45,
            "hardSolved": 15,
            "ranking": 5000,
        }

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            result = await client.get_user_stats("testuser")

        assert result.total_solved == 100
        mock_get.assert_called_once_with("https://test-api.example.com/testuser/solved")

    @pytest.mark.asyncio
    async def test_get_user_submissions(self, client, mock_response):
        """Test getting user submissions."""
        response_data = {
            "submission": [
                {"title": "Two Sum", "timestamp": "123456"},
                {"title": "Add Two Numbers", "timestamp": "123457"},
            ]
        }

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            result = await client.get_user_submissions("testuser", limit=10)

        assert len(result) == 2
        mock_get.assert_called_once_with(
            "https://test-api.example.com/testuser/acSubmission",
            params={"limit": 10}
        )

    @pytest.mark.asyncio
    async def test_get_official_solution(self, client, mock_response):
        """Test getting official solution."""
        response_data = {"content": "Solution explanation..."}

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            result = await client.get_official_solution("two-sum")

        assert result == response_data

    @pytest.mark.asyncio
    async def test_get_official_solution_not_found(self, client, mock_response):
        """Test getting official solution returns None for 404."""
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({}, status_code=404)
            mock_get.return_value.raise_for_status = MagicMock()  # Don't raise on 404
            result = await client.get_official_solution("no-solution")

        assert result is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test client works as async context manager."""
        async with LeetCodeClient("https://test.com") as client:
            assert client.base_url == "https://test.com"

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client close method."""
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()
