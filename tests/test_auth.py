"""Tests for the authentication module."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from grind.auth.session import (
    Session,
    SessionManager,
    SERVICE_NAME,
    SESSION_KEY,
    SESSION_CACHE_TTL,
    KEYRING_AVAILABLE,
)
from grind.auth.leetcode import (
    LeetCodeAuth,
    AuthenticationError,
    SessionExpiredError,
    fetch_csrf_token,
    LEETCODE_GRAPHQL_URL,
)


# =============================================================================
# Session Tests
# =============================================================================

class TestSession:
    """Tests for Session dataclass."""

    def test_session_creation(self):
        """Test creating a session with required fields."""
        session = Session(
            leetcode_session="test_session_123",
            csrf_token="test_csrf_456",
        )
        assert session.leetcode_session == "test_session_123"
        assert session.csrf_token == "test_csrf_456"
        assert session.username is None
        assert session.validated_at is None

    def test_session_with_username(self):
        """Test creating a session with username."""
        session = Session(
            leetcode_session="test_session",
            csrf_token="test_csrf",
            username="testuser",
        )
        assert session.username == "testuser"

    def test_session_created_at_default(self):
        """Test created_at defaults to current time."""
        before = time.time()
        session = Session(leetcode_session="s", csrf_token="c")
        after = time.time()
        assert before <= session.created_at <= after

    def test_is_validation_stale_when_never_validated(self):
        """Test validation is stale when never validated."""
        session = Session(leetcode_session="s", csrf_token="c")
        assert session.is_validation_stale() is True

    def test_is_validation_stale_when_recently_validated(self):
        """Test validation is not stale when recently validated."""
        session = Session(leetcode_session="s", csrf_token="c")
        session.mark_validated("user")
        assert session.is_validation_stale() is False

    def test_is_validation_stale_after_ttl(self):
        """Test validation is stale after TTL expires."""
        session = Session(leetcode_session="s", csrf_token="c")
        session.validated_at = time.time() - SESSION_CACHE_TTL - 1
        assert session.is_validation_stale() is True

    def test_mark_validated_updates_timestamp(self):
        """Test mark_validated updates the timestamp."""
        session = Session(leetcode_session="s", csrf_token="c")
        before = time.time()
        session.mark_validated("user")
        after = time.time()
        assert session.validated_at is not None
        assert before <= session.validated_at <= after

    def test_mark_validated_updates_username(self):
        """Test mark_validated updates the username."""
        session = Session(leetcode_session="s", csrf_token="c")
        session.mark_validated("newuser")
        assert session.username == "newuser"

    def test_to_dict(self):
        """Test session serialization to dict."""
        session = Session(
            leetcode_session="session123",
            csrf_token="csrf456",
            username="testuser",
        )
        session.mark_validated()
        
        data = session.to_dict()
        assert data["leetcode_session"] == "session123"
        assert data["csrf_token"] == "csrf456"
        assert data["username"] == "testuser"
        assert "created_at" in data
        assert "validated_at" in data

    def test_from_dict(self):
        """Test session deserialization from dict."""
        data = {
            "leetcode_session": "session123",
            "csrf_token": "csrf456",
            "username": "testuser",
            "created_at": 1234567890.0,
            "validated_at": 1234567900.0,
        }
        session = Session.from_dict(data)
        assert session.leetcode_session == "session123"
        assert session.csrf_token == "csrf456"
        assert session.username == "testuser"
        assert session.created_at == 1234567890.0
        assert session.validated_at == 1234567900.0

    def test_from_dict_minimal(self):
        """Test from_dict with minimal required fields."""
        data = {
            "leetcode_session": "s",
            "csrf_token": "c",
        }
        session = Session.from_dict(data)
        assert session.leetcode_session == "s"
        assert session.csrf_token == "c"

    def test_get_cookies(self):
        """Test get_cookies returns correct dict."""
        session = Session(leetcode_session="s123", csrf_token="c456")
        cookies = session.get_cookies()
        assert cookies == {
            "LEETCODE_SESSION": "s123",
            "csrftoken": "c456",
        }

    def test_get_headers(self):
        """Test get_headers returns correct dict."""
        session = Session(leetcode_session="s", csrf_token="c456")
        headers = session.get_headers()
        assert headers["X-CSRFToken"] == "c456"
        assert "Referer" in headers


# =============================================================================
# SessionManager Tests
# =============================================================================

class TestSessionManager:
    """Tests for SessionManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a session manager with file storage only."""
        return SessionManager(use_keyring=False, config_dir=temp_dir)

    def test_session_manager_creation(self, temp_dir):
        """Test creating a session manager."""
        manager = SessionManager(config_dir=temp_dir)
        assert manager.config_dir == temp_dir

    def test_session_manager_use_keyring_flag(self, temp_dir):
        """Test use_keyring flag is respected."""
        manager = SessionManager(use_keyring=False, config_dir=temp_dir)
        assert manager.use_keyring is False

    def test_save_and_load_file(self, manager):
        """Test saving and loading session from file."""
        session = Session(
            leetcode_session="test_session",
            csrf_token="test_csrf",
            username="testuser",
        )
        manager.save(session)
        
        # Clear cache to force file read
        manager.clear_cache()
        
        loaded = manager.load()
        assert loaded is not None
        assert loaded.leetcode_session == "test_session"
        assert loaded.csrf_token == "test_csrf"
        assert loaded.username == "testuser"

    def test_load_returns_none_when_no_session(self, manager):
        """Test load returns None when no session exists."""
        result = manager.load()
        assert result is None

    def test_delete_removes_session(self, manager):
        """Test delete removes the session."""
        session = Session(leetcode_session="s", csrf_token="c")
        manager.save(session)
        
        result = manager.delete()
        assert result is True
        assert manager.load() is None

    def test_delete_returns_false_when_no_session(self, manager):
        """Test delete returns False when no session exists."""
        result = manager.delete()
        assert result is False

    def test_exists_returns_true_when_session_exists(self, manager):
        """Test exists returns True when session exists."""
        session = Session(leetcode_session="s", csrf_token="c")
        manager.save(session)
        assert manager.exists() is True

    def test_exists_returns_false_when_no_session(self, manager):
        """Test exists returns False when no session."""
        assert manager.exists() is False

    def test_cached_session_is_returned(self, manager):
        """Test cached session is returned without file read."""
        session = Session(leetcode_session="s", csrf_token="c")
        manager.save(session)
        
        # Delete file but session should still be cached
        manager.session_file.unlink()
        
        loaded = manager.load()
        assert loaded is not None
        assert loaded.leetcode_session == "s"

    def test_clear_cache(self, manager):
        """Test clear_cache clears the in-memory cache."""
        session = Session(leetcode_session="s", csrf_token="c")
        manager.save(session)
        
        # Delete file
        manager.session_file.unlink()
        manager.clear_cache()
        
        # Now load should return None since file is gone
        loaded = manager.load()
        assert loaded is None

    def test_session_file_permissions(self, manager):
        """Test session file has restrictive permissions."""
        session = Session(leetcode_session="s", csrf_token="c")
        manager.save(session)
        
        import stat
        mode = manager.session_file.stat().st_mode
        # Check only owner has read/write
        assert mode & stat.S_IRWXG == 0  # No group permissions
        assert mode & stat.S_IRWXO == 0  # No other permissions

    def test_session_file_path(self, temp_dir):
        """Test session file path is correct."""
        manager = SessionManager(config_dir=temp_dir)
        assert manager.session_file == temp_dir / "session.json"

    def test_config_dir_created_on_save(self, temp_dir):
        """Test config directory is created on save."""
        subdir = temp_dir / "nested" / "config"
        manager = SessionManager(config_dir=subdir, use_keyring=False)
        
        session = Session(leetcode_session="s", csrf_token="c")
        manager.save(session)
        
        assert subdir.exists()


# =============================================================================
# SessionManager Keyring Tests (Mocked)
# =============================================================================

class TestSessionManagerKeyring:
    """Tests for SessionManager keyring functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.skipif(not KEYRING_AVAILABLE, reason="keyring not installed")
    def test_keyring_save_and_load(self, temp_dir):
        """Test saving and loading from keyring."""
        with patch("grind.auth.session.keyring") as mock_keyring:
            stored_data = {}
            
            def set_password(service, key, value):
                stored_data[(service, key)] = value
            
            def get_password(service, key):
                return stored_data.get((service, key))
            
            mock_keyring.set_password = set_password
            mock_keyring.get_password = get_password
            
            manager = SessionManager(use_keyring=True, config_dir=temp_dir)
            session = Session(leetcode_session="s", csrf_token="c")
            
            manager.save(session)
            manager.clear_cache()
            
            loaded = manager.load()
            assert loaded is not None
            assert loaded.leetcode_session == "s"


# =============================================================================
# LeetCodeAuth Tests
# =============================================================================

class TestLeetCodeAuth:
    """Tests for LeetCodeAuth class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def auth(self, temp_dir):
        """Create a LeetCodeAuth instance with file storage."""
        manager = SessionManager(use_keyring=False, config_dir=temp_dir)
        return LeetCodeAuth(session_manager=manager)

    def test_auth_creation(self, auth):
        """Test creating LeetCodeAuth instance."""
        assert auth is not None
        assert auth.session_manager is not None

    def test_get_session_returns_none_when_not_logged_in(self, auth):
        """Test get_session returns None when not logged in."""
        assert auth.get_session() is None

    @pytest.mark.asyncio
    async def test_login_with_session_invalid_session(self, auth):
        """Test login fails with invalid session format."""
        with pytest.raises(AuthenticationError) as exc_info:
            await auth.login_with_session("short", "csrf")
        assert "Invalid LEETCODE_SESSION" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_with_session_invalid_csrf(self, auth):
        """Test login fails with invalid csrf format."""
        with pytest.raises(AuthenticationError) as exc_info:
            await auth.login_with_session("a" * 30, "short")
        assert "Invalid csrf_token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_with_session_strips_whitespace(self, auth):
        """Test login strips whitespace from tokens."""
        with patch.object(auth, "_validate_session", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = "testuser"
            
            await auth.login_with_session("  " + "a" * 30 + "  ", "  " + "b" * 30 + "  ")
            
            # Check the session was created with stripped values
            session = auth.get_session()
            assert session.leetcode_session == "a" * 30
            assert session.csrf_token == "b" * 30

    @pytest.mark.asyncio
    async def test_login_with_session_success(self, auth):
        """Test successful login with session."""
        with patch.object(auth, "_validate_session", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = "testuser"
            
            session = await auth.login_with_session("a" * 30, "b" * 30)
            
            assert session.username == "testuser"
            assert session.leetcode_session == "a" * 30
            assert session.csrf_token == "b" * 30

    @pytest.mark.asyncio
    async def test_is_authenticated_false_when_no_session(self, auth):
        """Test is_authenticated returns False when no session."""
        result = await auth.is_authenticated()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_authenticated_uses_cache(self, auth):
        """Test is_authenticated uses cache for recent validation."""
        # Create a session with recent validation
        session = Session(
            leetcode_session="a" * 30,
            csrf_token="b" * 30,
            username="testuser",
        )
        session.mark_validated()
        auth.session_manager.save(session)
        
        # Should return True without making network request
        with patch.object(auth, "_validate_session", new_callable=AsyncMock) as mock_validate:
            result = await auth.is_authenticated()
            assert result is True
            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_authenticated_revalidates_when_stale(self, auth):
        """Test is_authenticated revalidates when cache is stale."""
        session = Session(
            leetcode_session="a" * 30,
            csrf_token="b" * 30,
            username="testuser",
        )
        session.validated_at = time.time() - SESSION_CACHE_TTL - 100
        auth.session_manager.save(session)
        
        with patch.object(auth, "_validate_session", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = "testuser"
            result = await auth.is_authenticated()
            assert result is True
            mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_clears_session(self, auth):
        """Test logout clears the session."""
        session = Session(leetcode_session="a" * 30, csrf_token="b" * 30)
        auth.session_manager.save(session)
        
        result = await auth.logout()
        assert result is True
        assert auth.get_session() is None

    @pytest.mark.asyncio
    async def test_logout_returns_false_when_no_session(self, auth):
        """Test logout returns False when no session exists."""
        result = await auth.logout()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_current_user_returns_none_when_not_logged_in(self, auth):
        """Test get_current_user returns None when not logged in."""
        result = await auth.get_current_user()
        assert result is None


class TestLeetCodeAuthGraphQL:
    """Tests for LeetCodeAuth GraphQL functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def auth(self, temp_dir):
        """Create a LeetCodeAuth instance with file storage."""
        manager = SessionManager(use_keyring=False, config_dir=temp_dir)
        return LeetCodeAuth(session_manager=manager)

    @pytest.mark.asyncio
    async def test_validate_session_success(self, auth):
        """Test successful session validation."""
        session = Session(leetcode_session="a" * 30, csrf_token="b" * 30)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "userStatus": {
                    "isSignedIn": True,
                    "username": "testuser",
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(auth, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            username = await auth._validate_session(session)
            assert username == "testuser"

    @pytest.mark.asyncio
    async def test_validate_session_not_signed_in(self, auth):
        """Test validation fails when not signed in."""
        session = Session(leetcode_session="a" * 30, csrf_token="b" * 30)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "userStatus": {
                    "isSignedIn": False,
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(auth, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            with pytest.raises(SessionExpiredError):
                await auth._validate_session(session)

    @pytest.mark.asyncio
    async def test_validate_session_401_raises_expired(self, auth):
        """Test 401 response raises SessionExpiredError."""
        session = Session(leetcode_session="a" * 30, csrf_token="b" * 30)
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        with patch.object(auth, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            with pytest.raises(SessionExpiredError):
                await auth._validate_session(session)

    @pytest.mark.asyncio
    async def test_graphql_request_retries_on_429(self, auth):
        """Test GraphQL request retries on 429."""
        session = Session(leetcode_session="a" * 30, csrf_token="b" * 30)
        
        call_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 3:
                mock_response.status_code = 429
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"data": {}}
                mock_response.raise_for_status = MagicMock()
            return mock_response
        
        with patch.object(auth, "_get_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client
            
            with patch("grind.auth.leetcode.asyncio.sleep", new_callable=AsyncMock):
                result = await auth._graphql_request(session, "query { test }")
                assert result == {"data": {}}
                assert call_count == 3


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_fetch_csrf_token_success(self):
        """Test fetching CSRF token."""
        mock_response = MagicMock()
        mock_response.cookies = {"csrftoken": "test_csrf_token"}
        
        with patch("grind.auth.leetcode.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            result = await fetch_csrf_token()
            assert result == "test_csrf_token"

    @pytest.mark.asyncio
    async def test_fetch_csrf_token_failure(self):
        """Test fetching CSRF token handles errors."""
        with patch("grind.auth.leetcode.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            result = await fetch_csrf_token()
            assert result is None


# =============================================================================
# AuthenticationError Tests
# =============================================================================

class TestAuthenticationErrors:
    """Tests for authentication error classes."""

    def test_authentication_error_is_exception(self):
        """Test AuthenticationError is an Exception."""
        assert issubclass(AuthenticationError, Exception)

    def test_session_expired_error_is_authentication_error(self):
        """Test SessionExpiredError is an AuthenticationError."""
        assert issubclass(SessionExpiredError, AuthenticationError)

    def test_authentication_error_message(self):
        """Test AuthenticationError message."""
        error = AuthenticationError("Test error")
        assert str(error) == "Test error"

    def test_session_expired_error_message(self):
        """Test SessionExpiredError message."""
        error = SessionExpiredError("Session expired")
        assert str(error) == "Session expired"

    def test_authentication_error_can_be_caught(self):
        """Test AuthenticationError can be caught."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Test")

    def test_session_expired_caught_as_auth_error(self):
        """Test SessionExpiredError can be caught as AuthenticationError."""
        with pytest.raises(AuthenticationError):
            raise SessionExpiredError("Expired")
