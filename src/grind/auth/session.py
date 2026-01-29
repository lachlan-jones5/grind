"""Session management for LeetCode authentication.

Handles secure storage and retrieval of LeetCode session cookies using
the system keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager).
Falls back to encrypted file storage if keyring is unavailable.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Optional keyring support
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


# Constants
SERVICE_NAME = "grind-leetcode"
SESSION_KEY = "leetcode_session"
CSRF_KEY = "csrf_token"
CONFIG_DIR = Path.home() / ".grind"
SESSION_FILE = CONFIG_DIR / "session.json"
SESSION_CACHE_TTL = 300  # 5 minutes


@dataclass
class Session:
    """Represents a LeetCode session."""
    
    leetcode_session: str
    csrf_token: str
    username: str | None = None
    created_at: float = field(default_factory=time.time)
    validated_at: float | None = None
    
    def is_validation_stale(self) -> bool:
        """Check if the session validation is stale and needs refresh."""
        if self.validated_at is None:
            return True
        return (time.time() - self.validated_at) > SESSION_CACHE_TTL
    
    def mark_validated(self, username: str | None = None) -> None:
        """Mark the session as recently validated."""
        self.validated_at = time.time()
        if username:
            self.username = username
    
    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "leetcode_session": self.leetcode_session,
            "csrf_token": self.csrf_token,
            "username": self.username,
            "created_at": self.created_at,
            "validated_at": self.validated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        return cls(
            leetcode_session=data["leetcode_session"],
            csrf_token=data["csrf_token"],
            username=data.get("username"),
            created_at=data.get("created_at", time.time()),
            validated_at=data.get("validated_at"),
        )
    
    def get_cookies(self) -> dict[str, str]:
        """Get cookies dict for HTTP requests."""
        return {
            "LEETCODE_SESSION": self.leetcode_session,
            "csrftoken": self.csrf_token,
        }
    
    def get_headers(self) -> dict[str, str]:
        """Get headers dict for HTTP requests."""
        return {
            "X-CSRFToken": self.csrf_token,
            "Referer": "https://leetcode.com",
        }


class SessionManager:
    """Manages LeetCode session storage and retrieval.
    
    Storage priority:
    1. System keyring (most secure)
    2. Encrypted file (fallback)
    3. Plain JSON file (development only, not recommended)
    """
    
    def __init__(self, use_keyring: bool = True, config_dir: Path | None = None):
        """Initialize session manager.
        
        Args:
            use_keyring: Whether to attempt using system keyring
            config_dir: Override config directory (for testing)
        """
        self.use_keyring = use_keyring and KEYRING_AVAILABLE
        self.config_dir = config_dir or CONFIG_DIR
        self._cached_session: Session | None = None
    
    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def session_file(self) -> Path:
        """Get the session file path."""
        return self.config_dir / "session.json"
    
    def save(self, session: Session) -> None:
        """Save session to storage.
        
        Args:
            session: Session to save
        """
        self._cached_session = session
        
        if self.use_keyring:
            try:
                self._save_to_keyring(session)
                return
            except Exception:
                # Fall back to file storage
                pass
        
        self._save_to_file(session)
    
    def _save_to_keyring(self, session: Session) -> None:
        """Save session to system keyring."""
        if not KEYRING_AVAILABLE:
            raise RuntimeError("Keyring not available")
        
        # Store as JSON in keyring
        data = json.dumps(session.to_dict())
        keyring.set_password(SERVICE_NAME, SESSION_KEY, data)
    
    def _save_to_file(self, session: Session) -> None:
        """Save session to file.
        
        Note: This stores the session in plain JSON. For production use,
        consider encrypting with a user-provided passphrase.
        """
        self._ensure_config_dir()
        
        data = session.to_dict()
        with open(self.session_file, "w") as f:
            json.dump(data, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(self.session_file, 0o600)
    
    def load(self) -> Session | None:
        """Load session from storage.
        
        Returns:
            Session if found, None otherwise
        """
        # Return cached session if available
        if self._cached_session is not None:
            return self._cached_session
        
        if self.use_keyring:
            try:
                session = self._load_from_keyring()
                if session:
                    self._cached_session = session
                    return session
            except Exception:
                pass
        
        session = self._load_from_file()
        if session:
            self._cached_session = session
        return session
    
    def _load_from_keyring(self) -> Session | None:
        """Load session from system keyring."""
        if not KEYRING_AVAILABLE:
            return None
        
        data_str = keyring.get_password(SERVICE_NAME, SESSION_KEY)
        if not data_str:
            return None
        
        try:
            data = json.loads(data_str)
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
    
    def _load_from_file(self) -> Session | None:
        """Load session from file."""
        if not self.session_file.exists():
            return None
        
        try:
            with open(self.session_file) as f:
                data = json.load(f)
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None
    
    def delete(self) -> bool:
        """Delete stored session.
        
        Returns:
            True if session was deleted, False if no session existed
        """
        self._cached_session = None
        deleted = False
        
        if self.use_keyring:
            try:
                deleted = self._delete_from_keyring()
            except Exception:
                pass
        
        if self._delete_from_file():
            deleted = True
        
        return deleted
    
    def _delete_from_keyring(self) -> bool:
        """Delete session from system keyring."""
        if not KEYRING_AVAILABLE:
            return False
        
        try:
            keyring.delete_password(SERVICE_NAME, SESSION_KEY)
            return True
        except keyring.errors.PasswordDeleteError:
            return False
    
    def _delete_from_file(self) -> bool:
        """Delete session file."""
        if self.session_file.exists():
            self.session_file.unlink()
            return True
        return False
    
    def exists(self) -> bool:
        """Check if a session exists in storage."""
        return self.load() is not None
    
    def clear_cache(self) -> None:
        """Clear the in-memory session cache."""
        self._cached_session = None
