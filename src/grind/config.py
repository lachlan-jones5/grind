"""Configuration management for Grind."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseModel):
    """AI coach agent configuration."""

    system_prompt: str = Field(
        default="""You are a personalized algorithmic problem-solving coach. Your role is to help the user improve their skills through deliberate practice.

Coaching principles:
- Use the Socratic method: ask guiding questions rather than giving direct answers
- Identify patterns and help the user recognize them
- Track progress and reinforce weak areas
- Celebrate insights and breakthroughs
- Be encouraging but honest about areas needing improvement

When reviewing code:
- Analyze time and space complexity
- Suggest optimizations when appropriate
- Point out edge cases the user might have missed
- Compare approaches to common patterns (two-pointer, sliding window, etc.)

Adapt your style based on the user's needs - be more direct when they're stuck, more questioning when they're close to a breakthrough."""
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    model: str = Field(default="gpt-4o")


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="GRIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API provider: copilot or openrouter
    provider: Literal["copilot", "openrouter"] = Field(default="copilot")

    # Copilot settings (via Cynefin relay)
    copilot_relay_url: str = Field(default="http://localhost:8080")

    # OpenRouter settings
    openrouter_api_key: str | None = Field(default=None)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")

    # LeetCode API
    leetcode_api_url: str = Field(default="https://alfa-leetcode-api.onrender.com")
    leetcode_username: str | None = Field(default=None)

    # Languages (C++, Rust, OCaml)
    default_language: Literal["cpp", "rust", "ocaml"] = Field(default="cpp")

    # Data directory
    data_dir: Path = Field(default=Path.home() / ".local" / "share" / "grind")

    # Agent configuration
    agent: AgentConfig = Field(default_factory=AgentConfig)

    def get_db_path(self) -> Path:
        """Get the SQLite database path."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "grind.db"


def load_settings() -> Settings:
    """Load settings from environment and config files."""
    return Settings()
