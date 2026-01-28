"""Authentication module for GitHub Copilot."""

import asyncio
from typing import Any

import httpx


GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_CLIENT_ID = "Iv1.b507a08c87ecfe98"


class CopilotAuth:
    """Handle GitHub Copilot authentication via device code flow."""
    
    def __init__(self, relay_url: str | None = None):
        """Initialize auth handler.
        
        Args:
            relay_url: If provided, use Cynefin relay for auth.
                      Otherwise, authenticate directly with GitHub.
        """
        self.relay_url = relay_url
        self._client = httpx.AsyncClient(timeout=30.0)
        self._flow_id: str | None = None
        self._device_code: str | None = None
        self._interval: int = 5
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self) -> "CopilotAuth":
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self.close()
    
    async def check_status(self) -> dict[str, Any]:
        """Check current authentication status.
        
        Returns:
            Dict with 'authenticated' bool and optional 'message'.
        """
        if self.relay_url:
            try:
                resp = await self._client.get(f"{self.relay_url}/auth/status")
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "authenticated": data.get("authenticated", False),
                        "message": data.get("message", ""),
                    }
            except Exception as e:
                return {"authenticated": False, "message": f"Error: {e}"}
        
        return {"authenticated": False, "message": "No relay configured"}
    
    async def start_device_flow(self) -> dict[str, Any]:
        """Start the device code authentication flow.
        
        Returns:
            Dict with 'user_code', 'verification_uri', and 'expires_in'.
        """
        if self.relay_url:
            # Use relay's auth endpoint
            resp = await self._client.post(f"{self.relay_url}/auth/device")
            resp.raise_for_status()
            data = resp.json()
            self._flow_id = data.get("flow_id")
            return {
                "user_code": data["user_code"],
                "verification_uri": data["verification_uri"],
                "expires_in": data.get("expires_in", 900),
            }
        else:
            # Direct GitHub auth
            resp = await self._client.post(
                GITHUB_DEVICE_CODE_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "client_id": COPILOT_CLIENT_ID,
                    "scope": "read:user",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._device_code = data["device_code"]
            self._interval = data.get("interval", 5)
            return {
                "user_code": data["user_code"],
                "verification_uri": data["verification_uri"],
                "expires_in": data.get("expires_in", 900),
            }
    
    async def poll_for_token(self) -> dict[str, Any]:
        """Poll for authentication completion.
        
        Returns:
            Dict with 'status' ('pending', 'success', 'error') and optional 'message'.
        """
        if self.relay_url and self._flow_id:
            # Poll relay
            resp = await self._client.get(
                f"{self.relay_url}/auth/device/poll",
                params={"flow_id": self._flow_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": data.get("status", "pending"),
                    "message": data.get("message", ""),
                }
            return {"status": "error", "message": "Poll failed"}
        
        elif self._device_code:
            # Poll GitHub directly
            resp = await self._client.post(
                GITHUB_ACCESS_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "client_id": COPILOT_CLIENT_ID,
                    "device_code": self._device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if "access_token" in data:
                    # Store the token (you'd want to save this somewhere)
                    return {
                        "status": "success",
                        "message": "Authentication successful!",
                        "token": data["access_token"],
                    }
                elif data.get("error") == "authorization_pending":
                    return {"status": "pending", "message": "Waiting for user..."}
                elif data.get("error") == "slow_down":
                    self._interval += 5
                    return {"status": "pending", "message": "Slowing down..."}
                elif data.get("error") == "expired_token":
                    return {"status": "error", "message": "Code expired"}
                else:
                    return {"status": "error", "message": data.get("error_description", "Unknown error")}
            
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
        
        return {"status": "error", "message": "No flow started"}
    
    async def wait_for_auth(self, on_status: callable = None) -> bool:
        """Wait for authentication to complete, polling periodically.
        
        Args:
            on_status: Optional callback for status updates.
        
        Returns:
            True if authenticated, False otherwise.
        """
        max_attempts = 60  # 5 minutes at 5 second intervals
        
        for _ in range(max_attempts):
            result = await self.poll_for_token()
            
            if on_status:
                on_status(result)
            
            if result["status"] == "success":
                return True
            elif result["status"] == "error":
                return False
            
            await asyncio.sleep(self._interval)
        
        return False
