"""Tests for the submission module."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grind.sync.submission import (
    SubmissionService,
    SubmissionResult,
    SubmissionStatus,
    SubmissionError,
    RateLimitedError,
    ProblemNotFoundError,
    InvalidLanguageError,
    TestCase,
    format_submission_result,
    LANGUAGE_MAP,
    LEETCODE_LANGUAGE_DISPLAY,
)
from grind.auth.session import Session


# =============================================================================
# SubmissionStatus Tests
# =============================================================================

class TestSubmissionStatus:
    """Tests for SubmissionStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        assert SubmissionStatus.PENDING
        assert SubmissionStatus.ACCEPTED
        assert SubmissionStatus.WRONG_ANSWER
        assert SubmissionStatus.TIME_LIMIT_EXCEEDED
        assert SubmissionStatus.MEMORY_LIMIT_EXCEEDED
        assert SubmissionStatus.RUNTIME_ERROR
        assert SubmissionStatus.COMPILE_ERROR
        assert SubmissionStatus.OUTPUT_LIMIT_EXCEEDED
        assert SubmissionStatus.INTERNAL_ERROR
        assert SubmissionStatus.UNKNOWN

    def test_from_string_accepted(self):
        """Test from_string for Accepted."""
        assert SubmissionStatus.from_string("Accepted") == SubmissionStatus.ACCEPTED

    def test_from_string_wrong_answer(self):
        """Test from_string for Wrong Answer."""
        assert SubmissionStatus.from_string("Wrong Answer") == SubmissionStatus.WRONG_ANSWER

    def test_from_string_tle(self):
        """Test from_string for Time Limit Exceeded."""
        assert SubmissionStatus.from_string("Time Limit Exceeded") == SubmissionStatus.TIME_LIMIT_EXCEEDED

    def test_from_string_mle(self):
        """Test from_string for Memory Limit Exceeded."""
        assert SubmissionStatus.from_string("Memory Limit Exceeded") == SubmissionStatus.MEMORY_LIMIT_EXCEEDED

    def test_from_string_runtime_error(self):
        """Test from_string for Runtime Error."""
        assert SubmissionStatus.from_string("Runtime Error") == SubmissionStatus.RUNTIME_ERROR

    def test_from_string_compile_error(self):
        """Test from_string for Compile Error."""
        assert SubmissionStatus.from_string("Compile Error") == SubmissionStatus.COMPILE_ERROR

    def test_from_string_unknown(self):
        """Test from_string returns UNKNOWN for unknown status."""
        assert SubmissionStatus.from_string("Some Other Status") == SubmissionStatus.UNKNOWN


# =============================================================================
# TestCase Tests
# =============================================================================

class TestTestCase:
    """Tests for TestCase dataclass."""

    def test_testcase_creation(self):
        """Test creating a test case."""
        tc = TestCase(
            input="[1,2,3]",
            expected_output="6",
            actual_output="5",
            passed=False,
        )
        assert tc.input == "[1,2,3]"
        assert tc.expected_output == "6"
        assert tc.actual_output == "5"
        assert tc.passed is False

    def test_testcase_defaults(self):
        """Test test case default values."""
        tc = TestCase(input="test", expected_output="result")
        assert tc.actual_output is None
        assert tc.passed is False


# =============================================================================
# SubmissionResult Tests
# =============================================================================

class TestSubmissionResult:
    """Tests for SubmissionResult dataclass."""

    def test_result_creation(self):
        """Test creating a submission result."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.ACCEPTED,
            status_message="Accepted",
        )
        assert result.submission_id == "12345"
        assert result.status == SubmissionStatus.ACCEPTED

    def test_is_accepted_true(self):
        """Test is_accepted returns True for ACCEPTED."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.ACCEPTED,
            status_message="Accepted",
        )
        assert result.is_accepted is True

    def test_is_accepted_false(self):
        """Test is_accepted returns False for non-ACCEPTED."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.WRONG_ANSWER,
            status_message="Wrong Answer",
        )
        assert result.is_accepted is False

    def test_passed_ratio(self):
        """Test passed_ratio property."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.WRONG_ANSWER,
            status_message="Wrong Answer",
            total_testcases=100,
            passed_testcases=50,
        )
        assert result.passed_ratio == "50/100"

    def test_passed_ratio_none(self):
        """Test passed_ratio returns None when not available."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.ACCEPTED,
            status_message="Accepted",
        )
        assert result.passed_ratio is None

    def test_result_with_runtime_memory(self):
        """Test result with runtime and memory."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.ACCEPTED,
            status_message="Accepted",
            runtime="50 ms",
            runtime_percentile=95.5,
            memory="16.5 MB",
            memory_percentile=80.0,
        )
        assert result.runtime == "50 ms"
        assert result.runtime_percentile == 95.5
        assert result.memory == "16.5 MB"
        assert result.memory_percentile == 80.0

    def test_result_with_failed_testcase(self):
        """Test result with failed test case."""
        tc = TestCase(input="[1,2]", expected_output="3", actual_output="2")
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.WRONG_ANSWER,
            status_message="Wrong Answer",
            failed_testcase=tc,
        )
        assert result.failed_testcase is not None
        assert result.failed_testcase.input == "[1,2]"

    def test_result_with_compile_error(self):
        """Test result with compile error."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.COMPILE_ERROR,
            status_message="Compile Error",
            compile_error="Line 5: syntax error",
        )
        assert result.compile_error == "Line 5: syntax error"

    def test_result_with_runtime_error(self):
        """Test result with runtime error."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.RUNTIME_ERROR,
            status_message="Runtime Error",
            runtime_error="IndexError: list index out of range",
        )
        assert result.runtime_error == "IndexError: list index out of range"


# =============================================================================
# Error Classes Tests
# =============================================================================

class TestSubmissionErrors:
    """Tests for submission error classes."""

    def test_submission_error_is_exception(self):
        """Test SubmissionError is an Exception."""
        assert issubclass(SubmissionError, Exception)

    def test_rate_limited_error(self):
        """Test RateLimitedError is a SubmissionError."""
        assert issubclass(RateLimitedError, SubmissionError)

    def test_problem_not_found_error(self):
        """Test ProblemNotFoundError is a SubmissionError."""
        assert issubclass(ProblemNotFoundError, SubmissionError)

    def test_invalid_language_error(self):
        """Test InvalidLanguageError is a SubmissionError."""
        assert issubclass(InvalidLanguageError, SubmissionError)

    def test_errors_can_be_raised(self):
        """Test errors can be raised and caught."""
        with pytest.raises(SubmissionError):
            raise SubmissionError("Test error")
        
        with pytest.raises(RateLimitedError):
            raise RateLimitedError("Rate limited")
        
        with pytest.raises(InvalidLanguageError):
            raise InvalidLanguageError("Invalid language")


# =============================================================================
# Language Mapping Tests
# =============================================================================

class TestLanguageMapping:
    """Tests for language mapping."""

    def test_language_map_contains_common_languages(self):
        """Test LANGUAGE_MAP contains common languages."""
        assert "cpp" in LANGUAGE_MAP
        assert "python" in LANGUAGE_MAP
        assert "rust" in LANGUAGE_MAP
        assert "java" in LANGUAGE_MAP
        assert "javascript" in LANGUAGE_MAP

    def test_language_map_aliases(self):
        """Test language aliases work."""
        assert LANGUAGE_MAP["c++"] == "cpp"
        assert LANGUAGE_MAP["python3"] == "python3"
        assert LANGUAGE_MAP["js"] == "javascript"
        assert LANGUAGE_MAP["ts"] == "typescript"
        assert LANGUAGE_MAP["golang"] == "golang"
        assert LANGUAGE_MAP["go"] == "golang"

    def test_leetcode_language_display(self):
        """Test display names for languages."""
        assert LEETCODE_LANGUAGE_DISPLAY["cpp"] == "C++"
        assert LEETCODE_LANGUAGE_DISPLAY["python3"] == "Python3"
        assert LEETCODE_LANGUAGE_DISPLAY["rust"] == "Rust"

    def test_get_leetcode_language_valid(self):
        """Test get_leetcode_language with valid language."""
        assert SubmissionService.get_leetcode_language("cpp") == "cpp"
        assert SubmissionService.get_leetcode_language("python") == "python3"
        assert SubmissionService.get_leetcode_language("RUST") == "rust"

    def test_get_leetcode_language_case_insensitive(self):
        """Test get_leetcode_language is case insensitive."""
        assert SubmissionService.get_leetcode_language("CPP") == "cpp"
        assert SubmissionService.get_leetcode_language("Python") == "python3"

    def test_get_leetcode_language_strips_whitespace(self):
        """Test get_leetcode_language strips whitespace."""
        assert SubmissionService.get_leetcode_language("  cpp  ") == "cpp"

    def test_get_leetcode_language_invalid(self):
        """Test get_leetcode_language raises for invalid language."""
        with pytest.raises(InvalidLanguageError):
            SubmissionService.get_leetcode_language("brainfuck")

    def test_get_language_display(self):
        """Test get_language_display."""
        assert SubmissionService.get_language_display("cpp") == "C++"
        assert SubmissionService.get_language_display("python3") == "Python3"
        # Unknown language returns itself
        assert SubmissionService.get_language_display("unknown") == "unknown"


# =============================================================================
# SubmissionService Tests
# =============================================================================

class TestSubmissionService:
    """Tests for SubmissionService class."""

    @pytest.fixture
    def mock_auth(self):
        """Create a mock auth instance."""
        auth = MagicMock()
        auth.is_authenticated = AsyncMock(return_value=True)
        session = Session(leetcode_session="test", csrf_token="csrf", username="testuser")
        auth.get_session = MagicMock(return_value=session)
        return auth

    @pytest.fixture
    def service(self, mock_auth):
        """Create a submission service with mock auth."""
        return SubmissionService(auth=mock_auth)

    def test_service_creation(self):
        """Test creating a submission service."""
        service = SubmissionService()
        assert service is not None
        assert service.auth is not None

    def test_service_with_custom_auth(self, mock_auth):
        """Test creating service with custom auth."""
        service = SubmissionService(auth=mock_auth)
        assert service.auth == mock_auth

    @pytest.mark.asyncio
    async def test_submit_not_authenticated(self):
        """Test submit fails when not authenticated."""
        auth = MagicMock()
        auth.is_authenticated = AsyncMock(return_value=False)
        service = SubmissionService(auth=auth)

        from grind.auth import AuthenticationError
        with pytest.raises(AuthenticationError):
            await service.submit("two-sum", "code", "python")

    @pytest.mark.asyncio
    async def test_submit_invalid_language(self, service):
        """Test submit fails with invalid language."""
        with pytest.raises(InvalidLanguageError):
            await service.submit("two-sum", "code", "invalid-lang")

    @pytest.mark.asyncio
    async def test_submit_success(self, service, mock_auth):
        """Test successful submission."""
        mock_auth._graphql_request = AsyncMock(side_effect=[
            # Submit response
            {"data": {"submitSolution": {"submissionId": "12345"}}},
            # Poll response - accepted
            {
                "data": {
                    "submissionDetails": {
                        "statusDisplay": "Accepted",
                        "statusCode": 10,
                        "runtime": "50 ms",
                        "runtimePercentile": 95.0,
                        "memory": "16.5 MB",
                        "memoryPercentile": 80.0,
                    }
                }
            },
        ])

        result = await service.submit("two-sum", "def solution(): pass", "python")
        
        assert result.submission_id == "12345"
        assert result.status == SubmissionStatus.ACCEPTED
        assert result.runtime == "50 ms"

    @pytest.mark.asyncio
    async def test_submit_wrong_answer(self, service, mock_auth):
        """Test submission with wrong answer."""
        mock_auth._graphql_request = AsyncMock(side_effect=[
            {"data": {"submitSolution": {"submissionId": "12345"}}},
            {
                "data": {
                    "submissionDetails": {
                        "statusDisplay": "Wrong Answer",
                        "statusCode": 11,
                        "totalTestcases": 100,
                        "passedTestcases": 50,
                        "lastTestcase": "[1,2]",
                        "expectedOutput": "3",
                        "codeOutput": "2",
                    }
                }
            },
        ])

        result = await service.submit("two-sum", "code", "cpp")
        
        assert result.status == SubmissionStatus.WRONG_ANSWER
        assert result.passed_ratio == "50/100"
        assert result.failed_testcase is not None

    @pytest.mark.asyncio
    async def test_submit_compile_error(self, service, mock_auth):
        """Test submission with compile error."""
        mock_auth._graphql_request = AsyncMock(side_effect=[
            {"data": {"submitSolution": {"submissionId": "12345"}}},
            {
                "data": {
                    "submissionDetails": {
                        "statusDisplay": "Compile Error",
                        "statusCode": 20,
                        "compileError": "Line 5: missing semicolon",
                    }
                }
            },
        ])

        result = await service.submit("two-sum", "bad code", "cpp")
        
        assert result.status == SubmissionStatus.COMPILE_ERROR
        assert result.compile_error is not None

    @pytest.mark.asyncio
    async def test_polling_waits_for_result(self, service, mock_auth):
        """Test polling waits for pending result."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "submitSolution" in args[1] or "submitQuestion" in args[1]:
                return {"data": {"submitSolution": {"submissionId": "12345"}}}
            # Return pending twice, then accepted
            if call_count < 4:
                return {"data": {"submissionDetails": {"statusDisplay": "Pending"}}}
            return {
                "data": {
                    "submissionDetails": {
                        "statusDisplay": "Accepted",
                        "statusCode": 10,
                    }
                }
            }

        mock_auth._graphql_request = AsyncMock(side_effect=mock_request)

        with patch.object(service, "POLL_INTERVAL", 0.01):  # Speed up test
            result = await service.submit("two-sum", "code", "python")

        assert result.status == SubmissionStatus.ACCEPTED


# =============================================================================
# Format Result Tests
# =============================================================================

class TestFormatSubmissionResult:
    """Tests for format_submission_result function."""

    def test_format_accepted(self):
        """Test formatting accepted result."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.ACCEPTED,
            status_message="Accepted",
            runtime="50 ms",
            runtime_percentile=95.0,
            memory="16.5 MB",
            memory_percentile=80.0,
        )
        formatted = format_submission_result(result)
        
        assert "✓" in formatted
        assert "Accepted" in formatted
        assert "50 ms" in formatted
        assert "95.0%" in formatted
        assert "16.5 MB" in formatted

    def test_format_wrong_answer(self):
        """Test formatting wrong answer result."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.WRONG_ANSWER,
            status_message="Wrong Answer",
            total_testcases=100,
            passed_testcases=50,
        )
        formatted = format_submission_result(result)
        
        assert "✗" in formatted
        assert "Wrong Answer" in formatted
        assert "50/100" in formatted

    def test_format_compile_error(self):
        """Test formatting compile error result."""
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.COMPILE_ERROR,
            status_message="Compile Error",
            compile_error="Line 5: syntax error",
        )
        formatted = format_submission_result(result)
        
        assert "Compile Error" in formatted
        assert "syntax error" in formatted

    def test_format_with_failed_testcase(self):
        """Test formatting with failed test case."""
        tc = TestCase(
            input="[1,2,3]",
            expected_output="6",
            actual_output="5",
        )
        result = SubmissionResult(
            submission_id="12345",
            status=SubmissionStatus.WRONG_ANSWER,
            status_message="Wrong Answer",
            failed_testcase=tc,
        )
        formatted = format_submission_result(result)
        
        assert "Failed Test Case" in formatted
        assert "[1,2,3]" in formatted
        assert "Expected: 6" in formatted
        assert "Output: 5" in formatted


# =============================================================================
# Integration Tests
# =============================================================================

class TestSubmissionServiceIntegration:
    """Integration tests for SubmissionService."""

    @pytest.fixture
    def mock_auth(self):
        """Create a mock auth instance."""
        auth = MagicMock()
        auth.is_authenticated = AsyncMock(return_value=True)
        session = Session(leetcode_session="test", csrf_token="csrf", username="testuser")
        auth.get_session = MagicMock(return_value=session)
        return auth

    @pytest.mark.asyncio
    async def test_submit_problem_not_found(self, mock_auth):
        """Test submit handles problem not found."""
        mock_auth._graphql_request = AsyncMock(return_value={
            "errors": [{"message": "Problem not found"}]
        })

        service = SubmissionService(auth=mock_auth)
        
        with pytest.raises(ProblemNotFoundError):
            await service.submit("nonexistent-problem", "code", "python")

    @pytest.mark.asyncio
    async def test_timeout_returns_pending(self, mock_auth):
        """Test polling timeout returns pending result."""
        mock_auth._graphql_request = AsyncMock(side_effect=[
            {"data": {"submitSolution": {"submissionId": "12345"}}},
            # Always return pending
            {"data": {"submissionDetails": {"statusDisplay": "Pending"}}},
        ] * 50)  # More than MAX_POLL_ATTEMPTS

        service = SubmissionService(auth=mock_auth)
        service.POLL_INTERVAL = 0.001  # Speed up
        service.MAX_POLL_ATTEMPTS = 3  # Reduce attempts

        result = await service.submit("two-sum", "code", "python")
        
        assert result.status == SubmissionStatus.PENDING
        assert "Timeout" in result.status_message
