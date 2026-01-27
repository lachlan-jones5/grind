"""LeetCode API client using alfa-leetcode-api."""

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    """A LeetCode problem."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    title_slug: str = Field(alias="titleSlug")
    difficulty: str
    question: str  # HTML content
    topic_tags: list[str] = Field(default_factory=list, alias="topicTags")
    hints: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list, alias="exampleTestcases")


class DailyProblem(BaseModel):
    """Daily challenge problem."""

    date: str
    title: str
    title_slug: str = Field(alias="titleSlug")
    difficulty: str
    question: str


class UserStats(BaseModel):
    """User statistics from LeetCode."""

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

    async def get_daily(self) -> DailyProblem:
        """Get today's daily challenge."""
        resp = await self._client.get(f"{self.base_url}/daily")
        resp.raise_for_status()
        return DailyProblem.model_validate(resp.json())

    async def get_problem(self, title_slug: str) -> Problem:
        """Get a specific problem by its slug."""
        resp = await self._client.get(f"{self.base_url}/select", params={"titleSlug": title_slug})
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

        resp = await self._client.get(f"{self.base_url}/problems", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("problemsetQuestionList", [])

    async def get_user_stats(self, username: str) -> UserStats:
        """Get user statistics."""
        resp = await self._client.get(f"{self.base_url}/{username}/solved")
        resp.raise_for_status()
        return UserStats.model_validate(resp.json())

    async def get_user_submissions(self, username: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get user's recent submissions."""
        resp = await self._client.get(
            f"{self.base_url}/{username}/acSubmission", params={"limit": limit}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("submission", [])

    async def get_official_solution(self, title_slug: str) -> dict[str, Any] | None:
        """Get the official solution for a problem."""
        resp = await self._client.get(
            f"{self.base_url}/officialSolution", params={"titleSlug": title_slug}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
