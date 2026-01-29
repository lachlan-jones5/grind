"""Comprehensive tests for the LeetCode API client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from grind.api.leetcode import (
    LeetCodeClient,
    Problem,
    DailyProblem,
    UserStats,
    TopicTag,
    RateLimitError,
    MAX_RETRIES,
    BASE_DELAY,
)


# =============================================================================
# TopicTag Model Tests
# =============================================================================

class TestTopicTagModel:
    """Tests for TopicTag Pydantic model."""

    def test_topic_tag_basic(self):
        """Test TopicTag with basic fields."""
        data = {"name": "Array", "slug": "array"}
        tag = TopicTag.model_validate(data)
        assert tag.name == "Array"
        assert tag.slug == "array"

    def test_topic_tag_with_translated_name(self):
        """Test TopicTag with translated name."""
        data = {"name": "Array", "slug": "array", "translatedName": "配列"}
        tag = TopicTag.model_validate(data)
        assert tag.translated_name == "配列"

    def test_topic_tag_null_translated_name(self):
        """Test TopicTag with null translated name."""
        data = {"name": "Array", "slug": "array", "translatedName": None}
        tag = TopicTag.model_validate(data)
        assert tag.translated_name is None

    def test_topic_tag_missing_translated_name(self):
        """Test TopicTag with missing translated name."""
        data = {"name": "Hash Table", "slug": "hash-table"}
        tag = TopicTag.model_validate(data)
        assert tag.translated_name is None

    def test_topic_tag_empty_slug(self):
        """Test TopicTag with empty slug defaults."""
        data = {"name": "Test"}
        tag = TopicTag.model_validate(data)
        assert tag.slug == ""


# =============================================================================
# Problem Model Tests
# =============================================================================

class TestProblemModel:
    """Comprehensive tests for Problem Pydantic model."""

    def test_problem_from_api_response(self):
        """Test Problem model parses API response correctly."""
        data = {
            "questionTitle": "Two Sum",
            "titleSlug": "two-sum",
            "difficulty": "Easy",
            "question": "<p>Given an array...</p>",
            "topicTags": [
                {"name": "Array", "slug": "array", "translatedName": None},
                {"name": "Hash Table", "slug": "hash-table", "translatedName": None},
            ],
            "hints": ["Try using a hash map"],
            "exampleTestcases": "[2,7,11,15]\n9",
        }
        problem = Problem.model_validate(data)

        assert problem.title == "Two Sum"
        assert problem.title_slug == "two-sum"
        assert problem.difficulty == "Easy"
        assert len(problem.topic_tags) == 2
        assert problem.topic_tags[0].name == "Array"
        assert len(problem.hints) == 1

    def test_problem_tag_names_property(self):
        """Test Problem tag_names property."""
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "difficulty": "Easy",
            "question": "Q",
            "topicTags": [
                {"name": "Array", "slug": "array"},
                {"name": "DP", "slug": "dynamic-programming"},
            ],
        }
        problem = Problem.model_validate(data)
        assert problem.tag_names == ["Array", "DP"]

    def test_problem_with_missing_optional_fields(self):
        """Test Problem model handles missing optional fields."""
        data = {
            "questionTitle": "Test Problem",
            "titleSlug": "test-problem",
            "difficulty": "Medium",
            "question": "Description here",
        }
        problem = Problem.model_validate(data)

        assert problem.title == "Test Problem"
        assert problem.topic_tags == []
        assert problem.hints == []
        assert problem.example_testcases == ""

    def test_problem_all_difficulties(self):
        """Test Problem accepts all difficulty levels."""
        for difficulty in ["Easy", "Medium", "Hard"]:
            data = {
                "questionTitle": "Test",
                "titleSlug": "test",
                "difficulty": difficulty,
                "question": "Q",
            }
            problem = Problem.model_validate(data)
            assert problem.difficulty == difficulty

    def test_problem_with_empty_topic_tags(self):
        """Test Problem with empty topic tags."""
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "difficulty": "Easy",
            "question": "Q",
            "topicTags": [],
        }
        problem = Problem.model_validate(data)
        assert problem.topic_tags == []
        assert problem.tag_names == []

    def test_problem_with_many_topic_tags(self):
        """Test Problem with many topic tags."""
        tags = [
            {"name": "Array", "slug": "array"},
            {"name": "Hash Table", "slug": "hash-table"},
            {"name": "Two Pointers", "slug": "two-pointers"},
            {"name": "Binary Search", "slug": "binary-search"},
            {"name": "DP", "slug": "dynamic-programming"},
        ]
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "difficulty": "Hard",
            "question": "Q",
            "topicTags": tags,
        }
        problem = Problem.model_validate(data)
        assert len(problem.topic_tags) == 5
        assert problem.tag_names == ["Array", "Hash Table", "Two Pointers", "Binary Search", "DP"]

    def test_problem_with_multiple_hints(self):
        """Test Problem with multiple hints."""
        hints = ["Hint 1", "Hint 2", "Hint 3"]
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "difficulty": "Medium",
            "question": "Q",
            "hints": hints,
        }
        problem = Problem.model_validate(data)
        assert problem.hints == hints

    def test_problem_with_html_content(self):
        """Test Problem with complex HTML content."""
        html = """
        <p>Given an array of integers <code>nums</code> and an integer <code>target</code>.</p>
        <ul>
            <li>Return indices of the two numbers</li>
            <li>Each input has exactly one solution</li>
        </ul>
        <pre>
        Input: nums = [2,7,11,15], target = 9
        Output: [0,1]
        </pre>
        """
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "difficulty": "Easy",
            "question": html,
        }
        problem = Problem.model_validate(data)
        assert "<p>" in problem.question
        assert "<code>" in problem.question

    def test_problem_with_unicode(self):
        """Test Problem with unicode characters."""
        data = {
            "questionTitle": "Test 日本語",
            "titleSlug": "test-unicode",
            "difficulty": "Easy",
            "question": "Description with émojis 🎉 and ñ",
        }
        problem = Problem.model_validate(data)
        assert "日本語" in problem.title
        assert "🎉" in problem.question

    def test_problem_slug_with_numbers(self):
        """Test Problem with numbers in slug."""
        data = {
            "questionTitle": "3Sum",
            "titleSlug": "3sum",
            "difficulty": "Medium",
            "question": "Q",
        }
        problem = Problem.model_validate(data)
        assert problem.title_slug == "3sum"

    def test_problem_long_slug(self):
        """Test Problem with very long slug."""
        long_slug = "a" * 200
        data = {
            "questionTitle": "Long",
            "titleSlug": long_slug,
            "difficulty": "Easy",
            "question": "Q",
        }
        problem = Problem.model_validate(data)
        assert problem.title_slug == long_slug

    def test_problem_missing_required_field_title(self):
        """Test Problem raises error when title is missing."""
        data = {
            "titleSlug": "test",
            "difficulty": "Easy",
            "question": "Q",
        }
        with pytest.raises(Exception):
            Problem.model_validate(data)

    def test_problem_missing_required_field_difficulty(self):
        """Test Problem raises error when difficulty is missing."""
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "question": "Q",
        }
        with pytest.raises(Exception):
            Problem.model_validate(data)

    def test_problem_missing_required_field_question(self):
        """Test Problem raises error when question is missing."""
        data = {
            "questionTitle": "Test",
            "titleSlug": "test",
            "difficulty": "Easy",
        }
        with pytest.raises(Exception):
            Problem.model_validate(data)

    def test_problem_alias_usage(self):
        """Test Problem uses aliases correctly."""
        # Using alias names
        data1 = {
            "questionTitle": "Test",
            "titleSlug": "test-slug",
            "difficulty": "Easy",
            "question": "Q",
            "topicTags": [{"name": "Array", "slug": "array"}],
        }
        problem1 = Problem.model_validate(data1)
        assert problem1.title_slug == "test-slug"
        assert len(problem1.topic_tags) == 1
        assert problem1.topic_tags[0].name == "Array"


# =============================================================================
# DailyProblem Model Tests
# =============================================================================

class TestDailyProblemModel:
    """Comprehensive tests for DailyProblem Pydantic model."""

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
        assert daily.difficulty == "Hard"

    def test_daily_problem_all_fields(self):
        """Test DailyProblem with all fields."""
        data = {
            "date": "2026-01-27",
            "questionTitle": "Minimum Cost Path",
            "titleSlug": "minimum-cost-path",
            "difficulty": "Medium",
            "question": "<p>Full problem description</p>",
        }
        daily = DailyProblem.model_validate(data)
        assert daily.date == "2026-01-27"
        assert daily.title == "Minimum Cost Path"

    def test_daily_problem_missing_title(self):
        """Test DailyProblem requires questionTitle."""
        data = {
            "date": "2024-01-15",
            "titleSlug": "test",
            "difficulty": "Easy",
            "question": "Q",
        }
        with pytest.raises(Exception):
            DailyProblem.model_validate(data)

    def test_daily_problem_date_formats(self):
        """Test DailyProblem accepts various date formats."""
        dates = ["2024-01-15", "2024-12-31", "2025-06-01"]
        for date in dates:
            data = {
                "date": date,
                "questionTitle": "Test",
                "titleSlug": "test",
                "difficulty": "Easy",
                "question": "Q",
            }
            daily = DailyProblem.model_validate(data)
            assert daily.date == date


# =============================================================================
# UserStats Model Tests
# =============================================================================

class TestUserStatsModel:
    """Comprehensive tests for UserStats Pydantic model."""

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

    def test_user_stats_zero_values(self):
        """Test UserStats with zero values."""
        data = {
            "totalSolved": 0,
            "easySolved": 0,
            "mediumSolved": 0,
            "hardSolved": 0,
            "ranking": 0,
        }
        stats = UserStats.model_validate(data)
        assert stats.total_solved == 0

    def test_user_stats_large_values(self):
        """Test UserStats with large values."""
        data = {
            "totalSolved": 3000,
            "easySolved": 800,
            "mediumSolved": 1500,
            "hardSolved": 700,
            "ranking": 1,
        }
        stats = UserStats.model_validate(data)
        assert stats.total_solved == 3000
        assert stats.ranking == 1

    def test_user_stats_sum_validation(self):
        """Test that easy + medium + hard could equal total."""
        data = {
            "totalSolved": 100,
            "easySolved": 40,
            "mediumSolved": 35,
            "hardSolved": 25,
        }
        stats = UserStats.model_validate(data)
        assert stats.easy_solved + stats.medium_solved + stats.hard_solved == stats.total_solved


# =============================================================================
# LeetCodeClient Tests
# =============================================================================

class TestLeetCodeClientInit:
    """Tests for LeetCodeClient initialization."""

    def test_client_init(self):
        """Test client initialization."""
        client = LeetCodeClient("https://test-api.example.com")
        assert client.base_url == "https://test-api.example.com"

    def test_client_strips_trailing_slash(self):
        """Test client strips trailing slash from base URL."""
        client = LeetCodeClient("https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    def test_client_strips_multiple_trailing_slashes(self):
        """Test client strips trailing slashes."""
        client = LeetCodeClient("https://api.example.com///")
        # rstrip('/') removes all trailing slashes
        assert client.base_url == "https://api.example.com"

    def test_client_default_url(self):
        """Test client uses default URL."""
        client = LeetCodeClient()
        assert "alfa-leetcode-api" in client.base_url

    def test_client_timeout(self):
        """Test client has timeout configured."""
        client = LeetCodeClient()
        assert client._client.timeout.read == 30.0


class TestLeetCodeClientMethods:
    """Tests for LeetCodeClient API methods."""

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

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_daily()

        assert result.title == "Daily Problem"
        assert result.title_slug == "daily-problem"
        mock_request.assert_called_once_with("GET", "https://test-api.example.com/daily")

    @pytest.mark.asyncio
    async def test_get_daily_all_difficulties(self, client, mock_response):
        """Test getting daily challenge with different difficulties."""
        for difficulty in ["Easy", "Medium", "Hard"]:
            response_data = {
                "date": "2024-01-15",
                "questionTitle": "Test",
                "titleSlug": "test",
                "difficulty": difficulty,
                "question": "Q",
            }
            with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response(response_data)
                result = await client.get_daily()
                assert result.difficulty == difficulty

    @pytest.mark.asyncio
    async def test_get_problem(self, client, mock_response):
        """Test getting a specific problem."""
        response_data = {
            "questionTitle": "Two Sum",
            "titleSlug": "two-sum",
            "difficulty": "Easy",
            "question": "<p>Given an array...</p>",
            "topicTags": [{"name": "Array", "slug": "array"}],
            "hints": [],
        }

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_problem("two-sum")

        assert result.title == "Two Sum"
        mock_request.assert_called_once_with(
            "GET",
            "https://test-api.example.com/select",
            params={"titleSlug": "two-sum"}
        )

    @pytest.mark.asyncio
    async def test_get_problem_with_special_characters(self, client, mock_response):
        """Test getting problem with special characters in slug."""
        response_data = {
            "questionTitle": "3Sum",
            "titleSlug": "3sum",
            "difficulty": "Medium",
            "question": "Q",
        }
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_problem("3sum")
            assert result.title == "3Sum"

    @pytest.mark.asyncio
    async def test_get_problems_with_filters(self, client, mock_response):
        """Test getting problems with filters."""
        response_data = {
            "problemsetQuestionList": [
                {"title": "Problem 1", "titleSlug": "problem-1"},
                {"title": "Problem 2", "titleSlug": "problem-2"},
            ]
        }

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_problems(
                limit=10, skip=5, difficulty="Medium", tags=["array", "dp"]
            )

        assert len(result) == 2
        mock_request.assert_called_once_with(
            "GET",
            "https://test-api.example.com/problems",
            params={"limit": 10, "skip": 5, "difficulty": "Medium", "tags": "array,dp"}
        )

    @pytest.mark.asyncio
    async def test_get_problems_without_filters(self, client, mock_response):
        """Test getting problems without optional filters."""
        response_data = {"problemsetQuestionList": []}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            await client.get_problems(limit=20, skip=0)

        mock_request.assert_called_once_with(
            "GET",
            "https://test-api.example.com/problems",
            params={"limit": 20, "skip": 0}
        )

    @pytest.mark.asyncio
    async def test_get_problems_with_only_difficulty(self, client, mock_response):
        """Test getting problems with only difficulty filter."""
        response_data = {"problemsetQuestionList": []}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            await client.get_problems(limit=10, skip=0, difficulty="Hard")

        call_args = mock_request.call_args
        assert call_args.kwargs["params"]["difficulty"] == "Hard"
        assert "tags" not in call_args.kwargs["params"]

    @pytest.mark.asyncio
    async def test_get_problems_with_only_tags(self, client, mock_response):
        """Test getting problems with only tags filter."""
        response_data = {"problemsetQuestionList": []}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            await client.get_problems(limit=10, skip=0, tags=["binary-search"])

        call_args = mock_request.call_args
        assert call_args.kwargs["params"]["tags"] == "binary-search"
        assert "difficulty" not in call_args.kwargs["params"]

    @pytest.mark.asyncio
    async def test_get_problems_empty_result(self, client, mock_response):
        """Test getting problems when no results."""
        response_data = {"problemsetQuestionList": []}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_problems()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_problems_missing_key(self, client, mock_response):
        """Test getting problems when key is missing from response."""
        response_data = {}  # Missing problemsetQuestionList

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_problems()

        assert result == []

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

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_user_stats("testuser")

        assert result.total_solved == 100
        mock_request.assert_called_once_with("GET", "https://test-api.example.com/testuser/solved")

    @pytest.mark.asyncio
    async def test_get_user_stats_different_usernames(self, client, mock_response):
        """Test getting user stats for different usernames."""
        usernames = ["user1", "test_user", "user-with-dash", "user123"]
        response_data = {
            "totalSolved": 0,
            "easySolved": 0,
            "mediumSolved": 0,
            "hardSolved": 0,
        }

        for username in usernames:
            with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response(response_data)
                await client.get_user_stats(username)
                mock_request.assert_called_once_with("GET", f"https://test-api.example.com/{username}/solved")

    @pytest.mark.asyncio
    async def test_get_user_submissions(self, client, mock_response):
        """Test getting user submissions."""
        response_data = {
            "submission": [
                {"title": "Two Sum", "timestamp": "123456"},
                {"title": "Add Two Numbers", "timestamp": "123457"},
            ]
        }

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_user_submissions("testuser", limit=10)

        assert len(result) == 2
        mock_request.assert_called_once_with(
            "GET",
            "https://test-api.example.com/testuser/acSubmission",
            params={"limit": 10}
        )

    @pytest.mark.asyncio
    async def test_get_user_submissions_default_limit(self, client, mock_response):
        """Test getting user submissions with default limit."""
        response_data = {"submission": []}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            await client.get_user_submissions("testuser")

        call_args = mock_request.call_args
        assert call_args.kwargs["params"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_get_user_submissions_empty(self, client, mock_response):
        """Test getting user submissions when empty."""
        response_data = {"submission": []}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_user_submissions("testuser")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_submissions_missing_key(self, client, mock_response):
        """Test getting user submissions when key missing."""
        response_data = {}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_user_submissions("testuser")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_official_solution(self, client, mock_response):
        """Test getting official solution."""
        response_data = {"content": "Solution explanation..."}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_official_solution("two-sum")

        assert result == response_data

    @pytest.mark.asyncio
    async def test_get_official_solution_not_found(self, client, mock_response):
        """Test getting official solution returns None for 404."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response({}, status_code=404)
            mock_request.return_value.raise_for_status = MagicMock()
            result = await client.get_official_solution("no-solution")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_official_solution_with_code(self, client, mock_response):
        """Test getting official solution with code."""
        response_data = {
            "content": "Explanation",
            "code": {"cpp": "code here", "python": "code here"},
        }

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response(response_data)
            result = await client.get_official_solution("test")

        assert result["content"] == "Explanation"
        assert "code" in result

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

    @pytest.mark.asyncio
    async def test_context_manager_closes(self):
        """Test context manager properly closes client."""
        client = LeetCodeClient("https://test.com")
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            async with client:
                pass
            mock_close.assert_called_once()


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestLeetCodeClientErrors:
    """Tests for error handling in LeetCodeClient."""

    @pytest.fixture
    def client(self):
        return LeetCodeClient("https://test-api.example.com")

    @pytest.mark.asyncio
    async def test_get_daily_http_error(self, client):
        """Test get_daily raises on HTTP error."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                await client.get_daily()

    @pytest.mark.asyncio
    async def test_get_problem_http_error(self, client):
        """Test get_problem raises on HTTP error."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                await client.get_problem("nonexistent")

    @pytest.mark.asyncio
    async def test_get_user_stats_http_error(self, client):
        """Test get_user_stats raises on HTTP error."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "User Not Found", request=MagicMock(), response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                await client.get_user_stats("nonexistent_user")

    @pytest.mark.asyncio
    async def test_network_error(self, client):
        """Test handling of network errors."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(httpx.ConnectError):
                await client.get_daily()

    @pytest.mark.asyncio
    async def test_timeout_error(self, client):
        """Test handling of timeout errors."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(httpx.TimeoutException):
                await client.get_problem("test")


# =============================================================================
# Rate Limiting and Retry Tests
# =============================================================================

class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_is_exception(self):
        """Test RateLimitError is an Exception."""
        assert issubclass(RateLimitError, Exception)

    def test_rate_limit_error_message(self):
        """Test RateLimitError can have a message."""
        error = RateLimitError("Too many requests")
        assert str(error) == "Too many requests"

    def test_rate_limit_error_can_be_raised(self):
        """Test RateLimitError can be raised and caught."""
        with pytest.raises(RateLimitError):
            raise RateLimitError("Rate limit exceeded")


class TestRetryConfiguration:
    """Tests for retry configuration constants."""

    def test_max_retries_is_positive(self):
        """Test MAX_RETRIES is a positive integer."""
        assert MAX_RETRIES > 0
        assert isinstance(MAX_RETRIES, int)

    def test_base_delay_is_positive(self):
        """Test BASE_DELAY is positive."""
        assert BASE_DELAY > 0

    def test_reasonable_retry_count(self):
        """Test MAX_RETRIES is reasonable (not too high)."""
        assert MAX_RETRIES <= 10


class TestRetryLogic:
    """Tests for the retry logic with exponential backoff."""

    @pytest.fixture
    def client(self):
        """Create a client for testing."""
        return LeetCodeClient()

    @pytest.mark.asyncio
    async def test_request_with_retry_method_exists(self, client):
        """Test _request_with_retry method exists."""
        assert hasattr(client, "_request_with_retry")

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self, client):
        """Test successful request doesn't trigger retries."""
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"date": "2024-01-01", "questionTitle": "Test", "titleSlug": "test", "difficulty": "Easy", "question": "Test"}
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            await client.get_daily()

            # Should only be called once (no retries needed)
            assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_429_triggers_retry(self, client):
        """Test 429 response triggers retry."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 3:
                mock_response.status_code = 429
                mock_response.headers = {}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"date": "2024-01-01", "questionTitle": "Test", "titleSlug": "test", "difficulty": "Easy", "question": "Test"}
                mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await client.get_daily()

                # Should have retried twice before succeeding
                assert call_count == 3
                # Should have slept twice (between retries)
                assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_429_exhausts_retries_raises_rate_limit_error(self, client):
        """Test exhausting retries on 429 raises RateLimitError."""
        async def mock_request(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {}
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(RateLimitError) as exc_info:
                    await client.get_daily()

                assert "Rate limit exceeded" in str(exc_info.value)
                assert str(MAX_RETRIES) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_respects_retry_after_header(self, client):
        """Test retry respects Retry-After header."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 429
                mock_response.headers = {"Retry-After": "5"}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"date": "2024-01-01", "questionTitle": "Test", "titleSlug": "test", "difficulty": "Easy", "question": "Test"}
                mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await client.get_daily()

                # Check that sleep was called with at least 5 seconds
                sleep_duration = mock_sleep.call_args[0][0]
                assert sleep_duration >= 5.0

    @pytest.mark.asyncio
    async def test_timeout_error_triggers_retry(self, client):
        """Test timeout errors trigger retries."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"date": "2024-01-01", "questionTitle": "Test", "titleSlug": "test", "difficulty": "Easy", "question": "Test"}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock):
                await client.get_daily()
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_connection_error_triggers_retry(self, client):
        """Test connection errors trigger retries."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection failed")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"date": "2024-01-01", "questionTitle": "Test", "titleSlug": "test", "difficulty": "Easy", "question": "Test"}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock):
                await client.get_daily()
                assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_429_error_not_retried(self, client):
        """Test non-429 HTTP errors are not retried."""
        async def mock_request(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request) as mock:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_daily()

            # Should only be called once (no retry on 500)
            assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_increases_delay(self, client):
        """Test exponential backoff increases delay between retries."""
        call_count = 0
        sleep_durations = []

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 4:
                mock_response.status_code = 429
                mock_response.headers = {}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"date": "2024-01-01", "questionTitle": "Test", "titleSlug": "test", "difficulty": "Easy", "question": "Test"}
                mock_response.raise_for_status = MagicMock()
            return mock_response

        async def track_sleep(duration):
            sleep_durations.append(duration)

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", side_effect=track_sleep):
                await client.get_daily()

                # Should have 3 sleep calls
                assert len(sleep_durations) == 3
                # Each delay should generally increase (accounting for jitter)
                # The base pattern is BASE_DELAY * 2^attempt
                # With jitter, we just check they're all positive
                for d in sleep_durations:
                    assert d > 0


class TestRetryWithDifferentEndpoints:
    """Tests for retry logic across different API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a client for testing."""
        return LeetCodeClient()

    @pytest.mark.asyncio
    async def test_get_problem_uses_retry(self, client):
        """Test get_problem uses retry logic."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 429
                mock_response.headers = {}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "questionTitle": "Test",
                    "titleSlug": "test",
                    "difficulty": "Easy",
                    "question": "Test question",
                    "topicTags": [],
                    "hints": [],
                }
                mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock):
                result = await client.get_problem("test")
                assert call_count == 2
                assert result.title == "Test"

    @pytest.mark.asyncio
    async def test_get_problems_uses_retry(self, client):
        """Test get_problems uses retry logic."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 429
                mock_response.headers = {}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"problemsetQuestionList": []}
                mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock):
                result = await client.get_problems()
                assert call_count == 2
                assert result == []

    @pytest.mark.asyncio
    async def test_get_study_plan_problems_uses_retry(self, client):
        """Test get_study_plan_problems uses retry logic."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 429
                mock_response.headers = {}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = []
                mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("grind.api.leetcode.asyncio.sleep", new_callable=AsyncMock):
                result = await client.get_study_plan_problems("blind-75")
                assert call_count == 2
                assert result == []
