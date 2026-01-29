"""Solution submission service for LeetCode."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from grind.auth import LeetCodeAuth, AuthenticationError, SessionExpiredError


# Language mapping from Grind to LeetCode
LANGUAGE_MAP = {
    "cpp": "cpp",
    "c++": "cpp",
    "rust": "rust",
    "ocaml": "ocaml",
    "python": "python3",
    "python3": "python3",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "go": "golang",
    "golang": "golang",
    "c": "c",
    "csharp": "csharp",
    "c#": "csharp",
    "ruby": "ruby",
    "swift": "swift",
    "kotlin": "kotlin",
    "scala": "scala",
    "php": "php",
}

# Reverse mapping for display
LEETCODE_LANGUAGE_DISPLAY = {
    "cpp": "C++",
    "c": "C",
    "java": "Java",
    "python3": "Python3",
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "golang": "Go",
    "rust": "Rust",
    "ocaml": "OCaml",
    "csharp": "C#",
    "ruby": "Ruby",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "php": "PHP",
}


class SubmissionStatus(Enum):
    """Status of a submission."""
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    WRONG_ANSWER = "Wrong Answer"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
    RUNTIME_ERROR = "Runtime Error"
    COMPILE_ERROR = "Compile Error"
    OUTPUT_LIMIT_EXCEEDED = "Output Limit Exceeded"
    INTERNAL_ERROR = "Internal Error"
    UNKNOWN = "Unknown"
    
    @classmethod
    def from_string(cls, status: str) -> "SubmissionStatus":
        """Convert status string to enum."""
        status_map = {
            "Pending": cls.PENDING,
            "Accepted": cls.ACCEPTED,
            "Wrong Answer": cls.WRONG_ANSWER,
            "Time Limit Exceeded": cls.TIME_LIMIT_EXCEEDED,
            "Memory Limit Exceeded": cls.MEMORY_LIMIT_EXCEEDED,
            "Runtime Error": cls.RUNTIME_ERROR,
            "Compile Error": cls.COMPILE_ERROR,
            "Output Limit Exceeded": cls.OUTPUT_LIMIT_EXCEEDED,
            "Internal Error": cls.INTERNAL_ERROR,
        }
        return status_map.get(status, cls.UNKNOWN)


@dataclass
class TestCase:
    """A test case result."""
    input: str
    expected_output: str
    actual_output: str | None = None
    passed: bool = False


@dataclass
class SubmissionResult:
    """Result of a code submission."""
    submission_id: str
    status: SubmissionStatus
    status_message: str
    runtime: str | None = None
    runtime_percentile: float | None = None
    memory: str | None = None
    memory_percentile: float | None = None
    total_testcases: int | None = None
    passed_testcases: int | None = None
    failed_testcase: TestCase | None = None
    compile_error: str | None = None
    runtime_error: str | None = None
    submitted_at: datetime | None = None
    
    @property
    def is_accepted(self) -> bool:
        """Check if submission was accepted."""
        return self.status == SubmissionStatus.ACCEPTED
    
    @property
    def passed_ratio(self) -> str | None:
        """Get passed/total ratio string."""
        if self.passed_testcases is not None and self.total_testcases is not None:
            return f"{self.passed_testcases}/{self.total_testcases}"
        return None


class SubmissionError(Exception):
    """Base exception for submission errors."""
    pass


class RateLimitedError(SubmissionError):
    """Raised when rate limited by LeetCode."""
    pass


class ProblemNotFoundError(SubmissionError):
    """Raised when problem is not found."""
    pass


class InvalidLanguageError(SubmissionError):
    """Raised when language is not supported."""
    pass


class SubmissionService:
    """Service for submitting solutions to LeetCode.
    
    Handles:
    - Solution submission via GraphQL
    - Polling for submission results
    - Language mapping
    - Error handling
    """
    
    # GraphQL queries and mutations
    SUBMIT_MUTATION = """
        mutation submitSolution($questionSlug: String!, $lang: String!, $typedCode: String!) {
            submitSolution: submitQuestion(
                questionSlug: $questionSlug
                lang: $lang
                typedCode: $typedCode
            ) {
                submissionId: submission_id
            }
        }
    """
    
    # Alternative submit mutation format (LeetCode sometimes uses different schemas)
    SUBMIT_MUTATION_ALT = """
        mutation submitSolution($titleSlug: String!, $lang: String!, $code: String!) {
            submitCode(titleSlug: $titleSlug, lang: $lang, code: $code) {
                submission_id
            }
        }
    """
    
    CHECK_SUBMISSION_QUERY = """
        query checkSubmission($submissionId: Int!) {
            submissionDetails(submissionId: $submissionId) {
                statusDisplay
                statusCode
                runtime
                runtimePercentile
                memory
                memoryPercentile
                totalTestcases: total_testcases
                passedTestcases: total_correct
                compileError: compile_error
                runtimeError: runtime_error
                lastTestcase: last_testcase
                expectedOutput: expected_output
                codeOutput: code_output
            }
        }
    """
    
    # Polling configuration
    POLL_INTERVAL = 1.0  # seconds
    POLL_TIMEOUT = 30.0  # seconds
    MAX_POLL_ATTEMPTS = 30
    
    def __init__(self, auth: LeetCodeAuth | None = None):
        """Initialize submission service.
        
        Args:
            auth: LeetCode auth instance. If None, creates a new one.
        """
        self.auth = auth or LeetCodeAuth()
    
    @staticmethod
    def get_leetcode_language(language: str) -> str:
        """Map a language name to LeetCode's language slug.
        
        Args:
            language: Language name (e.g., "cpp", "python", "rust")
            
        Returns:
            LeetCode language slug
            
        Raises:
            InvalidLanguageError: If language is not supported
        """
        lang_lower = language.lower().strip()
        if lang_lower in LANGUAGE_MAP:
            return LANGUAGE_MAP[lang_lower]
        raise InvalidLanguageError(f"Unsupported language: {language}")
    
    @staticmethod
    def get_language_display(leetcode_lang: str) -> str:
        """Get display name for a LeetCode language slug."""
        return LEETCODE_LANGUAGE_DISPLAY.get(leetcode_lang, leetcode_lang)
    
    async def submit(
        self,
        problem_slug: str,
        code: str,
        language: str,
    ) -> SubmissionResult:
        """Submit a solution to LeetCode.
        
        Args:
            problem_slug: Problem title slug (e.g., "two-sum")
            code: Solution code
            language: Programming language
            
        Returns:
            SubmissionResult with status and details
            
        Raises:
            AuthenticationError: If not authenticated
            SubmissionError: If submission fails
        """
        # Validate authentication
        if not await self.auth.is_authenticated():
            raise AuthenticationError("Not authenticated. Run 'grind auth login' first.")
        
        session = self.auth.get_session()
        if not session:
            raise AuthenticationError("No valid session found.")
        
        # Map language
        leetcode_lang = self.get_leetcode_language(language)
        
        # Submit solution
        submission_id = await self._submit_code(
            session=session,
            problem_slug=problem_slug,
            code=code,
            language=leetcode_lang,
        )
        
        # Poll for result
        result = await self._poll_submission_result(
            session=session,
            submission_id=submission_id,
        )
        
        return result
    
    async def _submit_code(
        self,
        session: Any,
        problem_slug: str,
        code: str,
        language: str,
    ) -> str:
        """Submit code to LeetCode and return submission ID.
        
        Returns:
            Submission ID as string
        """
        try:
            # Try primary mutation format
            result = await self.auth._graphql_request(
                session,
                self.SUBMIT_MUTATION,
                variables={
                    "questionSlug": problem_slug,
                    "lang": language,
                    "typedCode": code,
                },
            )
            
            # Extract submission ID
            submit_data = result.get("data", {}).get("submitSolution", {})
            submission_id = submit_data.get("submissionId") or submit_data.get("submission_id")
            
            if not submission_id:
                # Try alternative field names
                if "errors" in result:
                    errors = result["errors"]
                    if errors:
                        error_msg = errors[0].get("message", "Unknown error")
                        if "not found" in error_msg.lower():
                            raise ProblemNotFoundError(f"Problem not found: {problem_slug}")
                        raise SubmissionError(f"Submission failed: {error_msg}")
                raise SubmissionError("No submission ID returned")
            
            return str(submission_id)
            
        except SessionExpiredError:
            raise
        except AuthenticationError:
            raise
        except SubmissionError:
            raise
        except Exception as e:
            raise SubmissionError(f"Failed to submit: {e}")
    
    async def _poll_submission_result(
        self,
        session: Any,
        submission_id: str,
    ) -> SubmissionResult:
        """Poll for submission result until complete or timeout.
        
        Args:
            session: Auth session
            submission_id: Submission ID to check
            
        Returns:
            SubmissionResult
        """
        for attempt in range(self.MAX_POLL_ATTEMPTS):
            try:
                result = await self.auth._graphql_request(
                    session,
                    self.CHECK_SUBMISSION_QUERY,
                    variables={"submissionId": int(submission_id)},
                )
                
                details = result.get("data", {}).get("submissionDetails", {})
                
                if not details:
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue
                
                status_str = details.get("statusDisplay", "Pending")
                
                # Check if still pending
                if status_str == "Pending" or details.get("statusCode") is None:
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue
                
                # Build result
                status = SubmissionStatus.from_string(status_str)
                
                # Handle failed test case
                failed_testcase = None
                if status != SubmissionStatus.ACCEPTED and details.get("lastTestcase"):
                    failed_testcase = TestCase(
                        input=details.get("lastTestcase", ""),
                        expected_output=details.get("expectedOutput", ""),
                        actual_output=details.get("codeOutput"),
                        passed=False,
                    )
                
                return SubmissionResult(
                    submission_id=submission_id,
                    status=status,
                    status_message=status_str,
                    runtime=details.get("runtime"),
                    runtime_percentile=details.get("runtimePercentile"),
                    memory=details.get("memory"),
                    memory_percentile=details.get("memoryPercentile"),
                    total_testcases=details.get("totalTestcases"),
                    passed_testcases=details.get("passedTestcases"),
                    failed_testcase=failed_testcase,
                    compile_error=details.get("compileError"),
                    runtime_error=details.get("runtimeError"),
                    submitted_at=datetime.now(),
                )
                
            except SessionExpiredError:
                raise
            except Exception as e:
                # Log error but continue polling
                await asyncio.sleep(self.POLL_INTERVAL)
                continue
        
        # Timeout - return pending result
        return SubmissionResult(
            submission_id=submission_id,
            status=SubmissionStatus.PENDING,
            status_message="Timeout waiting for result",
            submitted_at=datetime.now(),
        )
    
    async def run_tests(
        self,
        problem_slug: str,
        code: str,
        language: str,
        test_input: str | None = None,
    ) -> dict[str, Any]:
        """Run code against test cases without submitting.
        
        Note: This uses the /interpret_solution endpoint which runs code
        against example test cases or custom input.
        
        Args:
            problem_slug: Problem title slug
            code: Solution code
            language: Programming language
            test_input: Custom test input (optional)
            
        Returns:
            Test run result
        """
        if not await self.auth.is_authenticated():
            raise AuthenticationError("Not authenticated.")
        
        session = self.auth.get_session()
        if not session:
            raise AuthenticationError("No valid session.")
        
        leetcode_lang = self.get_leetcode_language(language)
        
        # The interpret (run) endpoint uses a different format
        # This is a simplified version - full implementation would need
        # the problem's test cases
        run_query = """
            mutation runCode($titleSlug: String!, $lang: String!, $code: String!, $testInput: String) {
                runCode(titleSlug: $titleSlug, lang: $lang, code: $code, testInput: $testInput) {
                    interpret_id
                }
            }
        """
        
        try:
            result = await self.auth._graphql_request(
                session,
                run_query,
                variables={
                    "titleSlug": problem_slug,
                    "lang": leetcode_lang,
                    "code": code,
                    "testInput": test_input,
                },
            )
            return result.get("data", {})
        except Exception as e:
            raise SubmissionError(f"Failed to run tests: {e}")


def format_submission_result(result: SubmissionResult) -> str:
    """Format a submission result for display.
    
    Args:
        result: SubmissionResult to format
        
    Returns:
        Formatted string for TUI display
    """
    lines = []
    
    # Status header
    if result.is_accepted:
        lines.append(f"✓ {result.status_message}")
    else:
        lines.append(f"✗ {result.status_message}")
    
    lines.append("")
    
    # Runtime and memory for accepted
    if result.is_accepted:
        if result.runtime:
            percentile = f" (faster than {result.runtime_percentile:.1f}%)" if result.runtime_percentile else ""
            lines.append(f"Runtime: {result.runtime}{percentile}")
        if result.memory:
            percentile = f" (less than {result.memory_percentile:.1f}%)" if result.memory_percentile else ""
            lines.append(f"Memory: {result.memory}{percentile}")
    else:
        # Test case info for failures
        if result.passed_ratio:
            lines.append(f"Test cases: {result.passed_ratio} passed")
        
        # Compile error
        if result.compile_error:
            lines.append("")
            lines.append("Compile Error:")
            lines.append(result.compile_error[:500])  # Truncate long errors
        
        # Runtime error
        if result.runtime_error:
            lines.append("")
            lines.append("Runtime Error:")
            lines.append(result.runtime_error[:500])
        
        # Failed test case
        if result.failed_testcase:
            lines.append("")
            lines.append("Failed Test Case:")
            lines.append(f"  Input: {result.failed_testcase.input[:200]}")
            lines.append(f"  Expected: {result.failed_testcase.expected_output[:200]}")
            if result.failed_testcase.actual_output:
                lines.append(f"  Output: {result.failed_testcase.actual_output[:200]}")
    
    return "\n".join(lines)
