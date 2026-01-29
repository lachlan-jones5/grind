"""LeetCode API client using alfa-leetcode-api."""

import asyncio
import random
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Retry configuration
MAX_RETRIES = 5
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 60.0  # seconds
JITTER = 0.5  # random jitter factor


class RateLimitError(Exception):
    """Raised when rate limit is exceeded after all retries."""
    pass


class TopicTag(BaseModel):
    """A topic tag from LeetCode."""

    name: str
    slug: str = ""
    translated_name: str | None = Field(default=None, alias="translatedName")

    model_config = ConfigDict(populate_by_name=True)


class Problem(BaseModel):
    """A LeetCode problem."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(alias="questionTitle")
    title_slug: str = Field(alias="titleSlug")
    difficulty: str
    question: str  # HTML content
    topic_tags: list[TopicTag] = Field(default_factory=list, alias="topicTags")
    hints: list[str] = Field(default_factory=list)
    example_testcases: str = Field(default="", alias="exampleTestcases")

    @property
    def tag_names(self) -> list[str]:
        """Get list of tag names."""
        return [tag.name for tag in self.topic_tags]


class DailyProblem(BaseModel):
    """Daily challenge problem."""

    model_config = ConfigDict(populate_by_name=True)

    date: str
    title: str = Field(alias="questionTitle")
    title_slug: str = Field(alias="titleSlug")
    difficulty: str
    question: str


class UserStats(BaseModel):
    """User statistics from LeetCode."""

    model_config = ConfigDict(populate_by_name=True)

    total_solved: int = Field(alias="totalSolved")
    easy_solved: int = Field(alias="easySolved")
    medium_solved: int = Field(alias="mediumSolved")
    hard_solved: int = Field(alias="hardSolved")
    ranking: int = 0


class LeetCodeClient:
    """Client for the alfa-leetcode-api."""

    def __init__(self, base_url: str = "https://alfa-leetcode-api.onrender.com"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "LeetCodeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with exponential backoff retry on 429 errors.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            httpx.Response on success
            
        Raises:
            RateLimitError: If rate limit exceeded after all retries
            httpx.HTTPStatusError: For other HTTP errors
        """
        last_error: Exception | None = None
        
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.request(method, url, **kwargs)
                
                if resp.status_code == 429:
                    # Rate limited - calculate backoff delay
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    # Add jitter to prevent thundering herd
                    delay = delay * (1 + random.uniform(-JITTER, JITTER))
                    
                    # Check for Retry-After header
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise RateLimitError(
                            f"Rate limit exceeded after {MAX_RETRIES} retries. "
                            f"Try again in {delay:.1f} seconds."
                        )
                
                return resp
                
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    await asyncio.sleep(delay)
                    continue
                raise
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RateLimitError("Request failed after all retries")

    async def get_daily(self) -> DailyProblem:
        """Get today's daily challenge."""
        resp = await self._request_with_retry("GET", f"{self.base_url}/daily")
        resp.raise_for_status()
        return DailyProblem.model_validate(resp.json())

    async def get_problem(self, title_slug: str) -> Problem:
        """Get a specific problem by its slug."""
        resp = await self._request_with_retry(
            "GET", f"{self.base_url}/select", params={"titleSlug": title_slug}
        )
        resp.raise_for_status()
        return Problem.model_validate(resp.json())

    async def get_problems(
        self,
        limit: int = 20,
        skip: int = 0,
        difficulty: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get a list of problems with optional filters."""
        params: dict[str, Any] = {"limit": limit, "skip": skip}
        if difficulty:
            params["difficulty"] = difficulty
        if tags:
            params["tags"] = ",".join(tags)

        resp = await self._request_with_retry("GET", f"{self.base_url}/problems", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("problemsetQuestionList", [])

    async def get_user_stats(self, username: str) -> UserStats:
        """Get user statistics."""
        resp = await self._request_with_retry("GET", f"{self.base_url}/{username}/solved")
        resp.raise_for_status()
        return UserStats.model_validate(resp.json())

    async def get_user_submissions(self, username: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get user's recent submissions."""
        resp = await self._request_with_retry(
            "GET", f"{self.base_url}/{username}/acSubmission", params={"limit": limit}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("submission", [])

    async def get_official_solution(self, title_slug: str) -> dict[str, Any] | None:
        """Get the official solution for a problem."""
        resp = await self._request_with_retry(
            "GET", f"{self.base_url}/officialSolution", params={"titleSlug": title_slug}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def get_study_plan_problems(self, plan_slug: str) -> list[dict[str, Any]]:
        """Get problems from a study plan.
        
        Supported plan slugs:
        - top-interview-150: Top 150 Interview Questions
        - blind-75: Classic Blind 75
        - grind-75: Updated Grind 75
        - neetcode-150: NeetCode 150
        """
        # Try the study plan endpoint first
        try:
            resp = await self._request_with_retry(
                "GET", f"{self.base_url}/studyPlan", params={"slug": plan_slug}
            )
            if resp.status_code == 200:
                data = resp.json()
                # The API may return problems in different formats
                if isinstance(data, list):
                    return data
                if "questions" in data:
                    return data["questions"]
                if "problems" in data:
                    return data["problems"]
        except Exception:
            pass

        # Fallback: try problems endpoint with tags
        tag_mapping = {
            "top-interview-150": None,  # Use general query
            "blind-75": None,
            "grind-75": None,
            "neetcode-150": None,
        }

        # If no specific tag, fetch general problems
        return await self.get_problems(limit=75)
