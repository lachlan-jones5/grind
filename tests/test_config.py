"""Tests for configuration management."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from grind.config import Settings, AgentConfig, load_settings


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_values(self):
        """Test AgentConfig default values."""
        config = AgentConfig()

        assert "coach" in config.system_prompt.lower()
        assert config.temperature == 0.7
        assert config.model == "gpt-4o"

    def test_custom_values(self):
        """Test AgentConfig with custom values."""
        config = AgentConfig(
            system_prompt="Custom prompt",
            temperature=0.5,
            model="gpt-3.5-turbo",
        )

        assert config.system_prompt == "Custom prompt"
        assert config.temperature == 0.5
        assert config.model == "gpt-3.5-turbo"

    def test_temperature_bounds(self):
        """Test temperature validation."""
        # Valid temperatures
        AgentConfig(temperature=0.0)
        AgentConfig(temperature=2.0)

        # Invalid temperatures should raise
        with pytest.raises(Exception):
            AgentConfig(temperature=-0.1)
        with pytest.raises(Exception):
            AgentConfig(temperature=2.1)


class TestSettings:
    """Tests for Settings."""

    def test_default_values(self):
        """Test Settings default values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.provider == "copilot"
            assert settings.copilot_relay_url == "http://localhost:8080"
            assert settings.openrouter_api_key is None
            assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
            assert settings.leetcode_api_url == "https://alfa-leetcode-api.onrender.com"
            assert settings.leetcode_username is None
            assert settings.default_language == "cpp"
            assert isinstance(settings.agent, AgentConfig)

    def test_env_prefix(self):
        """Test settings load from GRIND_ prefixed env vars."""
        env = {
            "GRIND_PROVIDER": "openrouter",
            "GRIND_COPILOT_RELAY_URL": "http://custom:9000",
            "GRIND_OPENROUTER_API_KEY": "sk-test-key",
            "GRIND_DEFAULT_LANGUAGE": "rust",
            "GRIND_LEETCODE_USERNAME": "testuser",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

            assert settings.provider == "openrouter"
            assert settings.copilot_relay_url == "http://custom:9000"
            assert settings.openrouter_api_key == "sk-test-key"
            assert settings.default_language == "rust"
            assert settings.leetcode_username == "testuser"

    def test_provider_validation(self):
        """Test provider must be copilot or openrouter."""
        with patch.dict(os.environ, {"GRIND_PROVIDER": "invalid"}, clear=True):
            with pytest.raises(Exception):
                Settings()

    def test_language_validation(self):
        """Test language must be cpp, rust, or ocaml."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "python"}, clear=True):
            with pytest.raises(Exception):
                Settings()

        # Valid languages
        for lang in ["cpp", "rust", "ocaml"]:
            with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": lang}, clear=True):
                settings = Settings()
                assert settings.default_language == lang

    def test_get_db_path(self):
        """Test get_db_path creates directory and returns path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "grind_data"

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings(data_dir=data_dir)
                db_path = settings.get_db_path()

                assert db_path == data_dir / "grind.db"
                assert data_dir.exists()

    def test_get_db_path_nested(self):
        """Test get_db_path creates nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "nested" / "deep" / "grind_data"

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings(data_dir=data_dir)
                db_path = settings.get_db_path()

                assert db_path.parent.exists()

    def test_extra_env_vars_ignored(self):
        """Test unknown env vars are ignored."""
        env = {
            "GRIND_UNKNOWN_SETTING": "value",
            "GRIND_PROVIDER": "copilot",
        }

        with patch.dict(os.environ, env, clear=True):
            # Should not raise
            settings = Settings()
            assert settings.provider == "copilot"


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_settings_returns_settings(self):
        """Test load_settings returns Settings instance."""
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

            assert isinstance(settings, Settings)

    def test_load_settings_uses_env(self):
        """Test load_settings uses environment variables."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "ocaml"}, clear=True):
            settings = load_settings()

            assert settings.default_language == "ocaml"


class TestSettingsIntegration:
    """Integration tests for settings with other components."""

    def test_settings_for_copilot_provider(self):
        """Test settings work for copilot configuration."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(
                provider="copilot",
                copilot_relay_url="http://localhost:8080",
            )

            # These should be usable for creating AI client
            assert settings.provider == "copilot"
            assert "localhost" in settings.copilot_relay_url

    def test_settings_for_openrouter_provider(self):
        """Test settings work for openrouter configuration."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(
                provider="openrouter",
                openrouter_api_key="sk-or-test",
                openrouter_base_url="https://openrouter.ai/api/v1",
            )

            assert settings.provider == "openrouter"
            assert settings.openrouter_api_key == "sk-or-test"

    def test_agent_config_nested(self):
        """Test nested agent config in settings."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.agent.model == "gpt-4o"
            assert settings.agent.temperature == 0.7
            assert len(settings.agent.system_prompt) > 0
