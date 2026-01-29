"""Data models for LeetCode sync."""

from datetime import datetime
from pydantic import BaseModel


class LeetCodeSubmission(BaseModel):
    """A submission synced from LeetCode."""
    
    id: str  # LeetCode submission ID
    problem_slug: str
    problem_title: str
    timestamp: int  # Unix timestamp
    status: str  # "Accepted", "Wrong Answer", etc.
    language: str
    runtime: str | None = None
    memory: str | None = None
    synced_at: datetime
    
    @property
    def submitted_at(self) -> datetime:
        """Get submission time as datetime."""
        return datetime.fromtimestamp(self.timestamp)
    
    @property
    def is_accepted(self) -> bool:
        """Check if submission was accepted."""
        return self.status == "Accepted"


class ProblemStatus(BaseModel):
    """Status of a problem (local + LeetCode)."""
    
    slug: str
    title: str | None = None
    difficulty: str | None = None
    is_premium: bool = False
    solved_locally: bool = False
    solved_leetcode: bool = False
    last_submission_id: str | None = None
    last_synced: datetime | None = None
    
    @property
    def is_solved(self) -> bool:
        """Check if problem is solved (either locally or on LeetCode)."""
        return self.solved_locally or self.solved_leetcode


class SyncMeta(BaseModel):
    """Sync metadata."""
    
    key: str
    value: str
    updated_at: datetime
