"""Comprehensive tests for configuration management."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from grind.config import Settings, AgentConfig, load_settings


# =============================================================================
# AgentConfig Tests
# =============================================================================

class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_values(self):
        """Test AgentConfig default values."""
        config = AgentConfig()

        assert "coach" in config.system_prompt.lower()
        assert config.temperature == 0.7
        assert config.model == "claude-opus-4-5-20250514"

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

    def test_temperature_min_bound(self):
        """Test temperature minimum bound."""
        config = AgentConfig(temperature=0.0)
        assert config.temperature == 0.0

    def test_temperature_max_bound(self):
        """Test temperature maximum bound."""
        config = AgentConfig(temperature=2.0)
        assert config.temperature == 2.0

    def test_temperature_below_min(self):
        """Test temperature below minimum raises error."""
        with pytest.raises(Exception):
            AgentConfig(temperature=-0.1)

    def test_temperature_above_max(self):
        """Test temperature above maximum raises error."""
        with pytest.raises(Exception):
            AgentConfig(temperature=2.1)

    def test_temperature_precision(self):
        """Test temperature accepts decimal values."""
        config = AgentConfig(temperature=0.73)
        assert config.temperature == 0.73

    def test_empty_system_prompt(self):
        """Test empty system prompt is allowed."""
        config = AgentConfig(system_prompt="")
        assert config.system_prompt == ""

    def test_long_system_prompt(self):
        """Test long system prompt."""
        long_prompt = "x" * 10000
        config = AgentConfig(system_prompt=long_prompt)
        assert config.system_prompt == long_prompt

    def test_unicode_system_prompt(self):
        """Test unicode in system prompt."""
        prompt = "You are a helpful 助手 🤖"
        config = AgentConfig(system_prompt=prompt)
        assert "助手" in config.system_prompt
        assert "🤖" in config.system_prompt

    def test_various_models(self):
        """Test various model names."""
        models = [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "anthropic/claude-3.5-sonnet",
        ]
        for model in models:
            config = AgentConfig(model=model)
            assert config.model == model

    def test_default_system_prompt_content(self):
        """Test default system prompt has expected content."""
        config = AgentConfig()
        prompt = config.system_prompt.lower()

        assert "socratic" in prompt
        assert "coach" in prompt or "pattern" in prompt


# =============================================================================
# Settings Basic Tests
# =============================================================================

class TestSettingsDefaults:
    """Tests for Settings default values."""

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

    def test_default_data_dir(self):
        """Test default data directory."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.data_dir == Path.home() / ".local" / "share" / "grind"


# =============================================================================
# Settings Environment Variable Tests
# =============================================================================

class TestSettingsEnvVars:
    """Tests for Settings environment variable loading."""

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

    def test_provider_copilot(self):
        """Test copilot provider setting."""
        with patch.dict(os.environ, {"GRIND_PROVIDER": "copilot"}, clear=True):
            settings = Settings()
            assert settings.provider == "copilot"

    def test_provider_openrouter(self):
        """Test openrouter provider setting."""
        with patch.dict(os.environ, {"GRIND_PROVIDER": "openrouter"}, clear=True):
            settings = Settings()
            assert settings.provider == "openrouter"

    def test_provider_invalid(self):
        """Test invalid provider raises error."""
        with patch.dict(os.environ, {"GRIND_PROVIDER": "invalid"}, clear=True):
            with pytest.raises(Exception):
                Settings()

    def test_language_cpp(self):
        """Test cpp language setting."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "cpp"}, clear=True):
            settings = Settings()
            assert settings.default_language == "cpp"

    def test_language_rust(self):
        """Test rust language setting."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "rust"}, clear=True):
            settings = Settings()
            assert settings.default_language == "rust"

    def test_language_ocaml(self):
        """Test ocaml language setting."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "ocaml"}, clear=True):
            settings = Settings()
            assert settings.default_language == "ocaml"

    def test_language_invalid(self):
        """Test invalid language raises error."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "python"}, clear=True):
            with pytest.raises(Exception):
                Settings()

    def test_language_case_sensitive(self):
        """Test language is case sensitive."""
        with patch.dict(os.environ, {"GRIND_DEFAULT_LANGUAGE": "CPP"}, clear=True):
            with pytest.raises(Exception):
                Settings()

    def test_extra_env_vars_ignored(self):
        """Test unknown env vars are ignored."""
        env = {
            "GRIND_UNKNOWN_SETTING": "value",
            "GRIND_ANOTHER_UNKNOWN": "value2",
            "GRIND_PROVIDER": "copilot",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.provider == "copilot"

    def test_non_grind_env_vars_ignored(self):
        """Test non-GRIND prefixed env vars are ignored."""
        env = {
            "PROVIDER": "openrouter",  # No GRIND_ prefix
            "DEFAULT_LANGUAGE": "rust",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.provider == "copilot"  # Default
            assert settings.default_language == "cpp"  # Default


# =============================================================================
# Settings URL Tests
# =============================================================================

class TestSettingsURLs:
    """Tests for URL settings."""

    def test_custom_relay_url(self):
        """Test custom relay URL."""
        with patch.dict(os.environ, {"GRIND_COPILOT_RELAY_URL": "http://192.168.1.100:8080"}, clear=True):
            settings = Settings()
            assert settings.copilot_relay_url == "http://192.168.1.100:8080"

    def test_relay_url_with_path(self):
        """Test relay URL with path."""
        with patch.dict(os.environ, {"GRIND_COPILOT_RELAY_URL": "http://localhost:8080/api"}, clear=True):
            settings = Settings()
            assert settings.copilot_relay_url == "http://localhost:8080/api"

    def test_custom_openrouter_url(self):
        """Test custom OpenRouter URL."""
        with patch.dict(os.environ, {"GRIND_OPENROUTER_BASE_URL": "https://custom.api.com/v1"}, clear=True):
            settings = Settings()
            assert settings.openrouter_base_url == "https://custom.api.com/v1"

    def test_custom_leetcode_api_url(self):
        """Test custom LeetCode API URL."""
        with patch.dict(os.environ, {"GRIND_LEETCODE_API_URL": "http://localhost:3000"}, clear=True):
            settings = Settings()
            assert settings.leetcode_api_url == "http://localhost:3000"


# =============================================================================
# Settings Database Path Tests
# =============================================================================

class TestSettingsDbPath:
    """Tests for get_db_path method."""

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

    def test_get_db_path_idempotent(self):
        """Test get_db_path is idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "grind_data"

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings(data_dir=data_dir)
                path1 = settings.get_db_path()
                path2 = settings.get_db_path()

                assert path1 == path2

    def test_get_db_path_existing_dir(self):
        """Test get_db_path with existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "grind_data"
            data_dir.mkdir()

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings(data_dir=data_dir)
                db_path = settings.get_db_path()

                assert db_path == data_dir / "grind.db"


# =============================================================================
# Settings API Key Tests
# =============================================================================

class TestSettingsApiKeys:
    """Tests for API key settings."""

    def test_openrouter_key_set(self):
        """Test OpenRouter API key is set."""
        with patch.dict(os.environ, {"GRIND_OPENROUTER_API_KEY": "sk-or-xxx"}, clear=True):
            settings = Settings()
            assert settings.openrouter_api_key == "sk-or-xxx"

    def test_openrouter_key_none(self):
        """Test OpenRouter API key defaults to None."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.openrouter_api_key is None

    def test_openrouter_key_empty_string(self):
        """Test OpenRouter API key can be empty string."""
        with patch.dict(os.environ, {"GRIND_OPENROUTER_API_KEY": ""}, clear=True):
            settings = Settings()
            assert settings.openrouter_api_key == ""


# =============================================================================
# Settings Username Tests
# =============================================================================

class TestSettingsUsername:
    """Tests for LeetCode username settings."""

    def test_username_set(self):
        """Test LeetCode username is set."""
        with patch.dict(os.environ, {"GRIND_LEETCODE_USERNAME": "myuser"}, clear=True):
            settings = Settings()
            assert settings.leetcode_username == "myuser"

    def test_username_none(self):
        """Test LeetCode username defaults to None."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.leetcode_username is None

    def test_username_with_special_chars(self):
        """Test username with special characters."""
        with patch.dict(os.environ, {"GRIND_LEETCODE_USERNAME": "user_123-test"}, clear=True):
            settings = Settings()
            assert settings.leetcode_username == "user_123-test"


# =============================================================================
# load_settings Function Tests
# =============================================================================

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

    def test_load_settings_multiple_calls(self):
        """Test load_settings can be called multiple times."""
        with patch.dict(os.environ, {}, clear=True):
            settings1 = load_settings()
            settings2 = load_settings()

            assert settings1.provider == settings2.provider


# =============================================================================
# Settings Integration Tests
# =============================================================================

class TestSettingsIntegration:
    """Integration tests for settings with other components."""

    def test_settings_for_copilot_provider(self):
        """Test settings work for copilot configuration."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(
                provider="copilot",
                copilot_relay_url="http://localhost:8080",
            )

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

            assert settings.agent.model == "claude-opus-4-5-20250514"
            assert settings.agent.temperature == 0.7
            assert len(settings.agent.system_prompt) > 0

    def test_all_settings_together(self):
        """Test all settings configured together."""
        env = {
            "GRIND_PROVIDER": "openrouter",
            "GRIND_OPENROUTER_API_KEY": "sk-test",
            "GRIND_DEFAULT_LANGUAGE": "rust",
            "GRIND_LEETCODE_USERNAME": "testuser",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

            assert settings.provider == "openrouter"
            assert settings.openrouter_api_key == "sk-test"
            assert settings.default_language == "rust"
            assert settings.leetcode_username == "testuser"
