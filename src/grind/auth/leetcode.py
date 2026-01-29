"""LeetCode authentication and API client.

Handles authentication with LeetCode via session cookies and provides
authenticated GraphQL API access.
"""

import asyncio
import re
from typing import Any

import httpx

from grind.auth.session import Session, SessionManager


# LeetCode API constants
LEETCODE_BASE_URL = "https://leetcode.com"
LEETCODE_GRAPHQL_URL = f"{LEETCODE_BASE_URL}/graphql"
LEETCODE_LOGIN_URL = f"{LEETCODE_BASE_URL}/accounts/login/"

# Request timeout
REQUEST_TIMEOUT = 30.0

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class SessionExpiredError(AuthenticationError):
    """Raised when the session has expired."""
    pass


class LeetCodeAuth:
    """LeetCode authentication and authenticated API access.
    
    Usage:
        # With existing session
        auth = LeetCodeAuth(session_manager)
        if await auth.is_authenticated():
            user = await auth.get_current_user()
        
        # Login with session cookie
        session = await auth.login_with_session(leetcode_session, csrf_token)
    """
    
    def __init__(self, session_manager: SessionManager | None = None):
        """Initialize LeetCode auth.
        
        Args:
            session_manager: Session manager for persistence. If None, creates a new one.
        """
        self.session_manager = session_manager or SessionManager()
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "LeetCodeAuth":
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self.close()
    
    def get_session(self) -> Session | None:
        """Get the current session if it exists."""
        return self.session_manager.load()
    
    async def login_with_session(
        self,
        leetcode_session: str,
        csrf_token: str,
    ) -> Session:
        """Login with a LeetCode session cookie.
        
        Args:
            leetcode_session: The LEETCODE_SESSION cookie value
            csrf_token: The csrftoken cookie value
            
        Returns:
            Validated Session object
            
        Raises:
            AuthenticationError: If the session is invalid
        """
        # Clean up the tokens (remove whitespace, quotes)
        leetcode_session = leetcode_session.strip().strip('"\'')
        csrf_token = csrf_token.strip().strip('"\'')
        
        # Validate format
        if not leetcode_session or len(leetcode_session) < 20:
            raise AuthenticationError("Invalid LEETCODE_SESSION format")
        if not csrf_token or len(csrf_token) < 20:
            raise AuthenticationError("Invalid csrf_token format")
        
        # Create session object
        session = Session(
            leetcode_session=leetcode_session,
            csrf_token=csrf_token,
        )
        
        # Validate by fetching user info
        username = await self._validate_session(session)
        session.mark_validated(username)
        
        # Save session
        self.session_manager.save(session)
        
        return session
    
    async def _validate_session(self, session: Session) -> str:
        """Validate a session by fetching the current user.
        
        Args:
            session: Session to validate
            
        Returns:
            Username of the authenticated user
            
        Raises:
            SessionExpiredError: If the session is expired
            AuthenticationError: If validation fails
        """
        try:
            user_data = await self._graphql_request(
                session,
                query="""
                    query globalData {
                        userStatus {
                            isSignedIn
                            username
                            realName
                            avatar
                        }
                    }
                """,
            )
            
            user_status = user_data.get("data", {}).get("userStatus", {})
            
            if not user_status.get("isSignedIn"):
                raise SessionExpiredError("Session is not signed in")
            
            username = user_status.get("username")
            if not username:
                raise AuthenticationError("Could not get username from session")
            
            return username
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise SessionExpiredError("Session has expired")
            raise AuthenticationError(f"HTTP error during validation: {e}")
        except httpx.RequestError as e:
            raise AuthenticationError(f"Network error during validation: {e}")
    
    async def is_authenticated(self) -> bool:
        """Check if we have a valid authenticated session.
        
        Returns:
            True if authenticated, False otherwise
        """
        session = self.get_session()
        if not session:
            return False
        
        # If validation is recent, trust the cache
        if not session.is_validation_stale():
            return True
        
        # Re-validate the session
        try:
            username = await self._validate_session(session)
            session.mark_validated(username)
            self.session_manager.save(session)
            return True
        except AuthenticationError:
            return False
    
    async def get_current_user(self) -> dict[str, Any] | None:
        """Get the current authenticated user's profile.
        
        Returns:
            User profile data or None if not authenticated
        """
        session = self.get_session()
        if not session:
            return None
        
        try:
            result = await self._graphql_request(
                session,
                query="""
                    query userProfile {
                        userStatus {
                            isSignedIn
                            username
                            realName
                            avatar
                            isPremium
                        }
                    }
                """,
            )
            
            user_status = result.get("data", {}).get("userStatus", {})
            if not user_status.get("isSignedIn"):
                return None
            
            return user_status
            
        except AuthenticationError:
            return None
    
    async def get_user_stats(self, username: str | None = None) -> dict[str, Any] | None:
        """Get user submission statistics.
        
        Args:
            username: Username to fetch stats for. If None, uses current user.
            
        Returns:
            User stats or None if failed
        """
        session = self.get_session()
        if not session:
            return None
        
        if not username:
            username = session.username
        if not username:
            return None
        
        try:
            result = await self._graphql_request(
                session,
                query="""
                    query userStats($username: String!) {
                        matchedUser(username: $username) {
                            username
                            submitStats {
                                acSubmissionNum {
                                    difficulty
                                    count
                                    submissions
                                }
                            }
                            profile {
                                ranking
                                reputation
                            }
                        }
                        allQuestionsCount {
                            difficulty
                            count
                        }
                    }
                """,
                variables={"username": username},
            )
            
            return result.get("data", {})
            
        except AuthenticationError:
            return None
    
    async def logout(self) -> bool:
        """Logout and clear the stored session.
        
        Returns:
            True if a session was cleared, False if no session existed
        """
        return self.session_manager.delete()
    
    async def _graphql_request(
        self,
        session: Session,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated GraphQL request to LeetCode.
        
        Args:
            session: Authenticated session
            query: GraphQL query string
            variables: Optional query variables
            
        Returns:
            Response JSON data
            
        Raises:
            AuthenticationError: If the request fails
        """
        client = await self._get_client()
        
        # Build request
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        
        headers = {
            "Content-Type": "application/json",
            "X-CSRFToken": session.csrf_token,
            "Referer": LEETCODE_BASE_URL,
            "Origin": LEETCODE_BASE_URL,
        }
        
        cookies = {
            "LEETCODE_SESSION": session.leetcode_session,
            "csrftoken": session.csrf_token,
        }
        
        # Make request with retry
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(
                    LEETCODE_GRAPHQL_URL,
                    json=payload,
                    headers=headers,
                    cookies=cookies,
                )
                
                if response.status_code == 401:
                    raise SessionExpiredError("Session has expired")
                
                if response.status_code == 429:
                    # Rate limited - wait and retry
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                raise AuthenticationError(f"Request timeout: {e}")
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                raise AuthenticationError(f"Request failed: {e}")
        
        raise AuthenticationError(f"Request failed after {MAX_RETRIES} retries: {last_error}")

    async def get_problem_detail(self, title_slug: str) -> dict[str, Any] | None:
        """Get full problem details including code snippets.
        
        Args:
            title_slug: Problem slug (e.g., "two-sum")
            
        Returns:
            Problem detail including codeSnippets or None if failed
        """
        session = self.get_session()
        if not session:
            return None
        
        try:
            result = await self._graphql_request(
                session,
                query="""
                    query questionData($titleSlug: String!) {
                        question(titleSlug: $titleSlug) {
                            questionId
                            questionFrontendId
                            title
                            titleSlug
                            content
                            difficulty
                            topicTags {
                                name
                                slug
                            }
                            codeSnippets {
                                lang
                                langSlug
                                code
                            }
                            hints
                            exampleTestcaseList
                            sampleTestCase
                            metaData
                        }
                    }
                """,
                variables={"titleSlug": title_slug},
            )
            
            return result.get("data", {}).get("question")
            
        except AuthenticationError:
            return None

    async def run_code(
        self,
        title_slug: str,
        code: str,
        lang: str,
        test_cases: str | None = None,
    ) -> dict[str, Any] | None:
        """Run code against test cases without submitting.
        
        Args:
            title_slug: Problem slug
            code: Source code
            lang: Language slug (e.g., "python3", "cpp")
            test_cases: Optional custom test cases (newline-separated)
            
        Returns:
            Run result or None if failed
        """
        session = self.get_session()
        if not session:
            raise AuthenticationError("Not authenticated")
        
        # First, get the question ID
        problem = await self.get_problem_detail(title_slug)
        if not problem:
            raise AuthenticationError(f"Could not fetch problem: {title_slug}")
        
        question_id = problem.get("questionId")
        if not question_id:
            raise AuthenticationError("Could not get question ID")
        
        # Use example test cases if none provided
        if not test_cases:
            test_cases = problem.get("sampleTestCase", "")
        
        client = await self._get_client()
        
        # Make the interpret (run) request
        headers = {
            "Content-Type": "application/json",
            "X-CSRFToken": session.csrf_token,
            "Referer": f"{LEETCODE_BASE_URL}/problems/{title_slug}/",
            "Origin": LEETCODE_BASE_URL,
        }
        
        cookies = {
            "LEETCODE_SESSION": session.leetcode_session,
            "csrftoken": session.csrf_token,
        }
        
        payload = {
            "lang": lang,
            "question_id": question_id,
            "typed_code": code,
            "data_input": test_cases,
        }
        
        try:
            response = await client.post(
                f"{LEETCODE_BASE_URL}/problems/{title_slug}/interpret_solution/",
                json=payload,
                headers=headers,
                cookies=cookies,
            )
            
            if response.status_code == 401:
                raise SessionExpiredError("Session has expired")
            
            response.raise_for_status()
            result = response.json()
            
            # Get the interpret_id and poll for results
            interpret_id = result.get("interpret_id")
            if not interpret_id:
                return result
            
            # Poll for the result
            return await self._poll_run_result(session, interpret_id)
            
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(f"Run failed: {e}")
        except httpx.RequestError as e:
            raise AuthenticationError(f"Network error: {e}")

    async def _poll_run_result(
        self,
        session: Session,
        interpret_id: str,
        max_attempts: int = 30,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """Poll for run result.
        
        Args:
            session: Authenticated session
            interpret_id: The interpret/run ID to poll
            max_attempts: Maximum polling attempts
            poll_interval: Seconds between polls
            
        Returns:
            Run result
        """
        client = await self._get_client()
        
        headers = {
            "X-CSRFToken": session.csrf_token,
            "Referer": LEETCODE_BASE_URL,
        }
        
        cookies = {
            "LEETCODE_SESSION": session.leetcode_session,
            "csrftoken": session.csrf_token,
        }
        
        for _ in range(max_attempts):
            try:
                response = await client.get(
                    f"{LEETCODE_BASE_URL}/submissions/detail/{interpret_id}/check/",
                    headers=headers,
                    cookies=cookies,
                )
                
                if response.status_code == 401:
                    raise SessionExpiredError("Session has expired")
                
                response.raise_for_status()
                result = response.json()
                
                state = result.get("state")
                if state == "SUCCESS":
                    return result
                elif state in ("PENDING", "STARTED"):
                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    # Unknown state, return what we have
                    return result
                    
            except httpx.RequestError as e:
                raise AuthenticationError(f"Polling failed: {e}")
        
        raise AuthenticationError(f"Polling timed out after {max_attempts} attempts")


def extract_csrf_from_session(session_cookie: str) -> str | None:
    """Try to extract CSRF token from the session cookie or generate one.
    
    Note: This is a helper for users who only have the LEETCODE_SESSION cookie.
    The CSRF token can often be fetched from the LeetCode page.
    
    Args:
        session_cookie: The LEETCODE_SESSION cookie value
        
    Returns:
        CSRF token if extractable, None otherwise
    """
    # CSRF tokens are typically 64-character hex strings
    # They're separate from the session cookie, so we can't extract directly
    # This is a placeholder - users need to provide both cookies
    return None


async def fetch_csrf_token() -> str | None:
    """Fetch a CSRF token from LeetCode.
    
    Makes an unauthenticated request to get a csrftoken cookie.
    
    Returns:
        CSRF token if successful, None otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(LEETCODE_BASE_URL)
            csrf = response.cookies.get("csrftoken")
            return csrf
    except Exception:
        return None
