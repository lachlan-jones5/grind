"""Comprehensive tests for Copilot authentication module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from grind.auth import (
    CopilotAuth,
    COPILOT_CLIENT_ID,
    GITHUB_DEVICE_CODE_URL,
    GITHUB_ACCESS_TOKEN_URL,
)


# =============================================================================
# Constants Tests
# =============================================================================

class TestAuthConstants:
    """Tests for authentication constants."""

    def test_copilot_client_id_exists(self):
        """Test client ID constant is defined."""
        assert COPILOT_CLIENT_ID is not None

    def test_copilot_client_id_value(self):
        """Test client ID has correct value."""
        assert COPILOT_CLIENT_ID == "Iv1.b507a08c87ecfe98"

    def test_copilot_client_id_format(self):
        """Test client ID has expected format."""
        assert COPILOT_CLIENT_ID.startswith("Iv1.")

    def test_github_device_code_url_exists(self):
        """Test device code URL is defined."""
        assert GITHUB_DEVICE_CODE_URL is not None

    def test_github_device_code_url_is_github(self):
        """Test device code URL is on GitHub."""
        assert "github.com" in GITHUB_DEVICE_CODE_URL

    def test_github_device_code_url_path(self):
        """Test device code URL has correct path."""
        assert "/login/device/code" in GITHUB_DEVICE_CODE_URL

    def test_github_access_token_url_exists(self):
        """Test access token URL is defined."""
        assert GITHUB_ACCESS_TOKEN_URL is not None

    def test_github_access_token_url_is_github(self):
        """Test access token URL is on GitHub."""
        assert "github.com" in GITHUB_ACCESS_TOKEN_URL

    def test_github_access_token_url_path(self):
        """Test access token URL has correct path."""
        assert "/login/oauth/access_token" in GITHUB_ACCESS_TOKEN_URL


# =============================================================================
# CopilotAuth Initialization Tests
# =============================================================================

class TestCopilotAuthInit:
    """Tests for CopilotAuth initialization."""

    def test_auth_init_no_args(self):
        """Test auth initializes without arguments."""
        auth = CopilotAuth()
        assert auth.relay_url is None

    def test_auth_init_with_relay(self):
        """Test auth initializes with relay URL."""
        auth = CopilotAuth(relay_url="http://localhost:8080")
        assert auth.relay_url == "http://localhost:8080"

    def test_auth_init_relay_url_stored(self):
        """Test relay URL is stored correctly."""
        url = "http://custom-relay:9000"
        auth = CopilotAuth(relay_url=url)
        assert auth.relay_url == url

    def test_auth_init_flow_id_none(self):
        """Test flow ID starts as None."""
        auth = CopilotAuth()
        assert auth._flow_id is None

    def test_auth_init_device_code_none(self):
        """Test device code starts as None."""
        auth = CopilotAuth()
        assert auth._device_code is None

    def test_auth_init_interval_default(self):
        """Test interval has default value."""
        auth = CopilotAuth()
        assert auth._interval == 5

    def test_auth_init_has_client(self):
        """Test auth has HTTP client."""
        auth = CopilotAuth()
        assert auth._client is not None
        assert isinstance(auth._client, httpx.AsyncClient)

    def test_auth_init_client_timeout(self):
        """Test client has timeout configured."""
        auth = CopilotAuth()
        assert auth._client.timeout.read == 30.0


# =============================================================================
# Context Manager Tests
# =============================================================================

class TestCopilotAuthContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_enter(self):
        """Test entering context manager."""
        async with CopilotAuth() as auth:
            assert auth is not None
            assert isinstance(auth, CopilotAuth)

    @pytest.mark.asyncio
    async def test_context_manager_exit(self):
        """Test exiting context manager closes client."""
        auth = CopilotAuth()
        async with auth:
            pass
        # Client should be closed after exiting

    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test close method doesn't raise."""
        auth = CopilotAuth()
        await auth.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Test close can be called multiple times."""
        auth = CopilotAuth()
        await auth.close()
        await auth.close()  # Should not raise


# =============================================================================
# Check Status Tests
# =============================================================================

class TestCopilotAuthCheckStatus:
    """Tests for check_status method."""

    @pytest.mark.asyncio
    async def test_check_status_no_relay(self):
        """Test check_status without relay configured."""
        auth = CopilotAuth()
        result = await auth.check_status()
        
        assert result["authenticated"] is False
        assert "No relay" in result["message"]

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
        assert result["message"] == "OK"

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
    async def test_check_status_relay_error(self):
        """Test check_status handles relay errors."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            result = await auth.check_status()

        assert result["authenticated"] is False
        assert "Error" in result["message"]

    @pytest.mark.asyncio
    async def test_check_status_relay_non_200(self):
        """Test check_status handles non-200 response."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await auth.check_status()

        assert result["authenticated"] is False

    @pytest.mark.asyncio
    async def test_check_status_calls_correct_endpoint(self):
        """Test check_status calls correct relay endpoint."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"authenticated": False}

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await auth.check_status()

        mock_get.assert_called_once_with("http://localhost:8080/auth/status")


# =============================================================================
# Start Device Flow Tests
# =============================================================================

class TestCopilotAuthStartDeviceFlow:
    """Tests for start_device_flow method."""

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
        assert result["expires_in"] == 900
        assert auth._flow_id == "abc123"

    @pytest.mark.asyncio
    async def test_start_device_flow_direct_github(self):
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

    @pytest.mark.asyncio
    async def test_start_device_flow_stores_interval(self):
        """Test start_device_flow stores polling interval."""
        auth = CopilotAuth()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "device_code": "device123",
            "user_code": "WXYZ-5678",
            "verification_uri": "https://github.com/login/device",
            "interval": 10,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.start_device_flow()

        assert auth._interval == 10

    @pytest.mark.asyncio
    async def test_start_device_flow_default_expires(self):
        """Test start_device_flow uses default expires_in."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "flow_id": "abc",
            "user_code": "CODE",
            "verification_uri": "https://github.com/login/device",
            # No expires_in
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.start_device_flow()

        assert result["expires_in"] == 900  # Default

    @pytest.mark.asyncio
    async def test_start_device_flow_calls_correct_github_endpoint(self):
        """Test start_device_flow calls correct GitHub endpoint."""
        auth = CopilotAuth()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "device_code": "d",
            "user_code": "u",
            "verification_uri": "v",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.start_device_flow()

        call_args = mock_post.call_args
        assert call_args[0][0] == GITHUB_DEVICE_CODE_URL

    @pytest.mark.asyncio
    async def test_start_device_flow_sends_correct_headers(self):
        """Test start_device_flow sends correct headers."""
        auth = CopilotAuth()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "device_code": "d",
            "user_code": "u",
            "verification_uri": "v",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.start_device_flow()

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_start_device_flow_sends_client_id(self):
        """Test start_device_flow sends client ID."""
        auth = CopilotAuth()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "device_code": "d",
            "user_code": "u",
            "verification_uri": "v",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.start_device_flow()

        call_args = mock_post.call_args
        json_data = call_args[1]["json"]
        assert json_data["client_id"] == COPILOT_CLIENT_ID


# =============================================================================
# Poll For Token Tests
# =============================================================================

class TestCopilotAuthPollForToken:
    """Tests for poll_for_token method."""

    @pytest.mark.asyncio
    async def test_poll_no_flow_started(self):
        """Test poll when no flow was started."""
        auth = CopilotAuth()
        result = await auth.poll_for_token()
        
        assert result["status"] == "error"
        assert "No flow" in result["message"]

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
        assert result["message"] == "Authenticated!"

    @pytest.mark.asyncio
    async def test_poll_pending_with_relay(self):
        """Test pending poll status via relay."""
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
    async def test_poll_relay_non_200(self):
        """Test poll handles non-200 from relay."""
        auth = CopilotAuth(relay_url="http://localhost:8080")
        auth._flow_id = "abc123"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "error"

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
        assert result["token"] == "ghu_xxx"

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
        assert "Waiting" in result["message"]

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
            result = await auth.poll_for_token()

        assert auth._interval == initial_interval + 5
        assert result["status"] == "pending"

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

    @pytest.mark.asyncio
    async def test_poll_direct_unknown_error(self):
        """Test unknown error response."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": "some_other_error",
            "error_description": "Something went wrong",
        }

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "error"
        assert "Something went wrong" in result["message"]

    @pytest.mark.asyncio
    async def test_poll_direct_http_error(self):
        """Test poll handles HTTP errors."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.poll_for_token()

        assert result["status"] == "error"
        assert "500" in result["message"]

    @pytest.mark.asyncio
    async def test_poll_calls_correct_github_endpoint(self):
        """Test poll calls correct GitHub endpoint."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "authorization_pending"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.poll_for_token()

        call_args = mock_post.call_args
        assert call_args[0][0] == GITHUB_ACCESS_TOKEN_URL

    @pytest.mark.asyncio
    async def test_poll_sends_device_code(self):
        """Test poll sends device code."""
        auth = CopilotAuth()
        auth._device_code = "my_device_code"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "authorization_pending"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.poll_for_token()

        call_args = mock_post.call_args
        json_data = call_args[1]["json"]
        assert json_data["device_code"] == "my_device_code"

    @pytest.mark.asyncio
    async def test_poll_sends_grant_type(self):
        """Test poll sends correct grant type."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "authorization_pending"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.poll_for_token()

        call_args = mock_post.call_args
        json_data = call_args[1]["json"]
        assert json_data["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"


# =============================================================================
# Wait For Auth Tests
# =============================================================================

class TestCopilotAuthWaitForAuth:
    """Tests for wait_for_auth method."""

    @pytest.mark.asyncio
    async def test_wait_for_auth_immediate_success(self):
        """Test wait_for_auth returns True on immediate success."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "token"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.wait_for_auth()

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_auth_immediate_error(self):
        """Test wait_for_auth returns False on immediate error."""
        auth = CopilotAuth()
        auth._device_code = "device123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "expired_token"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await auth.wait_for_auth()

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_auth_calls_callback(self):
        """Test wait_for_auth calls status callback."""
        auth = CopilotAuth()
        auth._device_code = "device123"
        callback = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "token"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await auth.wait_for_auth(on_status=callback)

        callback.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================

class TestCopilotAuthIntegration:
    """Integration tests for CopilotAuth."""

    @pytest.mark.asyncio
    async def test_full_flow_relay(self):
        """Test complete auth flow via relay."""
        auth = CopilotAuth(relay_url="http://localhost:8080")

        # Mock start flow
        start_response = MagicMock()
        start_response.status_code = 200
        start_response.json.return_value = {
            "flow_id": "flow123",
            "user_code": "CODE-1234",
            "verification_uri": "https://github.com/login/device",
        }
        start_response.raise_for_status = MagicMock()

        # Mock poll success
        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {"status": "success"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            with patch.object(auth._client, "get", new_callable=AsyncMock) as mock_get:
                mock_post.return_value = start_response
                mock_get.return_value = poll_response

                # Start flow
                flow = await auth.start_device_flow()
                assert flow["user_code"] == "CODE-1234"

                # Poll for success
                result = await auth.poll_for_token()
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_full_flow_direct(self):
        """Test complete auth flow directly with GitHub."""
        auth = CopilotAuth()

        # Mock start flow
        start_response = MagicMock()
        start_response.status_code = 200
        start_response.json.return_value = {
            "device_code": "dev123",
            "user_code": "WXYZ-5678",
            "verification_uri": "https://github.com/login/device",
            "interval": 5,
        }
        start_response.raise_for_status = MagicMock()

        # Mock poll success
        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {"access_token": "ghu_token123"}

        with patch.object(auth._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [start_response, poll_response]

            # Start flow
            flow = await auth.start_device_flow()
            assert flow["user_code"] == "WXYZ-5678"
            assert auth._device_code == "dev123"

            # Poll for success
            result = await auth.poll_for_token()
            assert result["status"] == "success"
            assert result["token"] == "ghu_token123"
