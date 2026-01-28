"""Tests for Copilot authentication module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from grind.auth import CopilotAuth, COPILOT_CLIENT_ID


class TestCopilotAuthInit:
    """Tests for CopilotAuth initialization."""

    def test_auth_init_with_relay(self):
        """Test auth initializes with relay URL."""
        auth = CopilotAuth(relay_url="http://localhost:8080")
        assert auth.relay_url == "http://localhost:8080"

    def test_auth_init_without_relay(self):
        """Test auth initializes without relay URL."""
        auth = CopilotAuth()
        assert auth.relay_url is None

    def test_auth_init_state(self):
        """Test initial state is clean."""
        auth = CopilotAuth()
        assert auth._flow_id is None
        assert auth._device_code is None
        assert auth._interval == 5


class TestCopilotAuthContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test auth works as context manager."""
        async with CopilotAuth() as auth:
            assert auth is not None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test close method."""
        auth = CopilotAuth()
        await auth.close()  # Should not raise


class TestCopilotAuthCheckStatus:
    """Tests for check_status method."""

    @pytest.mark.asyncio
    async def test_check_status_with_relay_authenticated(self):
        """Test check_status when authenticated via relay."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"authenticated": True, "message": "OK"}

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await auth.check_status()

        assert result["authenticated"] is True

    @pytest.mark.asyncio
    async def test_check_status_with_relay_not_authenticated(self):
        """Test check_status when not authenticated via relay."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"authenticated": False}

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await auth.check_status()

        assert result["authenticated"] is False

    @pytest.mark.asyncio
    async def test_check_status_without_relay(self):
        """Test check_status without relay configured."""
        auth = CopilotAuth()
        result = await auth.check_status()
        assert result["authenticated"] is False
        assert "No relay" in result["message"]

    @pytest.mark.asyncio
    async def test_check_status_error(self):
        """Test check_status handles errors."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            result = await auth.check_status()

        assert result["authenticated"] is False
        assert "Error" in result["message"]


class TestCopilotAuthDeviceFlow:
    """Tests for device flow."""

    @pytest.mark.asyncio
    async def test_start_device_flow_with_relay(self):
        """Test starting device flow via relay."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "flow_id": "abc123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.start_device_flow()

        assert result["user_code"] == "ABCD-1234"
        assert result["verification_uri"] == "https://github.com/login/device"
        assert auth._flow_id == "abc123"

    @pytest.mark.asyncio
    async def test_start_device_flow_direct(self):
        """Test starting device flow directly with GitHub."""
        auth = CopilotAuth()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "device_code": "device123",
            "user_code": "WXYZ-5678",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.start_device_flow()

        assert result["user_code"] == "WXYZ-5678"
        assert auth._device_code == "device123"


class TestCopilotAuthPollForToken:
    """Tests for poll_for_token method."""

    @pytest.mark.asyncio
    async def test_poll_success_with_relay(self):
        """Test successful poll via relay."""
        auth = CopilotAuth(relay_url="http://localhost:8080")
        auth._flow_id = "abc123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "message": "Authenticated!"}

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_poll_pending(self):
        """Test pending poll status."""
        auth = CopilotAuth(relay_url="http://localhost:8080")
        auth._flow_id = "abc123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "pending"}

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_poll_no_flow_started(self):
        """Test poll when no flow was started."""
        auth = CopilotAuth()
        result = await auth.poll_for_token()
        assert result["status"] == "error"
        assert "No flow" in result["message"]

    @pytest.mark.asyncio
    async def test_poll_direct_success(self):
        """Test successful direct poll to GitHub."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "ghu_xxx"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "success"
        assert "token" in result

    @pytest.mark.asyncio
    async def test_poll_direct_pending(self):
        """Test pending direct poll to GitHub."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "authorization_pending"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_poll_direct_slow_down(self):
        """Test slow_down response increases interval."""
        auth = CopilotAuth()
        auth._device_code = "device123"
        initial_interval = auth._interval

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "slow_down"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.poll_for_token()

        assert auth._interval > initial_interval

    @pytest.mark.asyncio
    async def test_poll_direct_expired(self):
        """Test expired token response."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "expired_token"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "error"
        assert "expired" in result["message"].lower()


class TestCopilotClientId:
    """Tests for client ID constant."""

    def test_client_id_exists(self):
        """Test client ID constant is defined."""
        assert COPILOT_CLIENT_ID == "Iv1.b507a08c87ecfe98"
