"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from grind.config import Settings
from grind.db.database import Database


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db(temp_dir):
    """Create a test database."""
    db_path = temp_dir / "test.db"
    return Database(db_path)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch.dict("os.environ", {}, clear=True):
        settings = Settings(
            provider="copilot",
            copilot_relay_url="http://localhost:8080",
            default_language="cpp",
        )
        return settings


@pytest.fixture
def mock_openai():
    """Mock the OpenAI client."""
    with patch("grind.ai.coach.AsyncOpenAI") as mock:
        yield mock
