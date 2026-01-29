"""Main entry point for Grind CLI."""

import argparse
import asyncio
import sys


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="grind",
        description="AI-powered LeetCode practice TUI with vim bindings",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth subcommand
    auth_parser = subparsers.add_parser("auth", help="Manage LeetCode authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", help="Auth commands")

    # grind auth login
    login_parser = auth_subparsers.add_parser("login", help="Login to LeetCode")
    login_parser.add_argument(
        "--session",
        required=True,
        help="LEETCODE_SESSION cookie value",
    )
    login_parser.add_argument(
        "--csrf",
        required=True,
        help="csrftoken cookie value",
    )

    # grind auth logout
    auth_subparsers.add_parser("logout", help="Logout from LeetCode")

    # grind auth status
    auth_subparsers.add_parser("status", help="Check authentication status")

    # Sync subcommand
    sync_parser = subparsers.add_parser("sync", help="Sync LeetCode progress")
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync (ignore last sync time)",
    )
    sync_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress",
    )
    sync_parser.add_argument(
        "--status",
        action="store_true",
        help="Show sync status without syncing",
    )
    sync_parser.add_argument(
        "--queue",
        action="store_true",
        help="Submit pending queued solutions",
    )

    # Main app options (when no subcommand)
    parser.add_argument(
        "--provider",
        choices=["copilot", "openrouter"],
        help="AI provider (default: copilot)",
    )
    parser.add_argument(
        "--language",
        choices=["cpp", "rust", "ocaml"],
        help="Default programming language",
    )
    parser.add_argument(
        "--relay-url",
        help="Cynefin relay URL for Copilot (default: http://localhost:8080)",
    )

    args = parser.parse_args()

    if args.version:
        from grind import __version__
        print(f"grind {__version__}")
        return 0

    # Handle auth commands
    if args.command == "auth":
        return handle_auth_command(args)

    # Handle sync commands
    if args.command == "sync":
        return handle_sync_command(args)

    # Apply CLI overrides to environment
    import os
    if args.provider:
        os.environ["GRIND_PROVIDER"] = args.provider
    if args.language:
        os.environ["GRIND_DEFAULT_LANGUAGE"] = args.language
    if args.relay_url:
        os.environ["GRIND_COPILOT_RELAY_URL"] = args.relay_url

    # Run the TUI
    from grind.tui.app import run
    run()
    return 0


def handle_auth_command(args: argparse.Namespace) -> int:
    """Handle auth subcommands."""
    if args.auth_command == "login":
        return asyncio.run(auth_login(args.session, args.csrf))
    elif args.auth_command == "logout":
        return asyncio.run(auth_logout())
    elif args.auth_command == "status":
        return asyncio.run(auth_status())
    else:
        print("Usage: grind auth <login|logout|status>")
        print("  login   - Login with LeetCode session cookies")
        print("  logout  - Clear stored session")
        print("  status  - Check authentication status")
        return 1


async def auth_login(session: str, csrf: str) -> int:
    """Login to LeetCode with session cookies."""
    from grind.auth import LeetCodeAuth, AuthenticationError, SessionExpiredError

    print("Authenticating with LeetCode...")

    auth = LeetCodeAuth()
    try:
        session_obj = await auth.login_with_session(session, csrf)
        print(f"Successfully logged in as: {session_obj.username}")
        print("Session saved securely.")
        return 0
    except SessionExpiredError:
        print("Error: Session has expired. Please get fresh cookies from your browser.")
        return 1
    except AuthenticationError as e:
        print(f"Error: {e}")
        return 1
    finally:
        await auth.close()


async def auth_logout() -> int:
    """Logout from LeetCode."""
    from grind.auth import LeetCodeAuth

    auth = LeetCodeAuth()
    if await auth.logout():
        print("Logged out successfully. Session cleared.")
    else:
        print("No active session found.")
    await auth.close()
    return 0


async def auth_status() -> int:
    """Check authentication status."""
    from grind.auth import LeetCodeAuth

    auth = LeetCodeAuth()
    try:
        session = auth.get_session()
        if not session:
            print("Status: Not logged in")
            print("\nTo login, run:")
            print("  grind auth login --session <LEETCODE_SESSION> --csrf <csrftoken>")
            print("\nGet these cookies from your browser after logging into leetcode.com")
            return 0

        print("Checking session validity...")
        if await auth.is_authenticated():
            user = await auth.get_current_user()
            username = user.get("username", session.username) if user else session.username
            is_premium = user.get("isPremium", False) if user else False

            print(f"Status: Logged in")
            print(f"Username: {username}")
            print(f"Premium: {'Yes' if is_premium else 'No'}")

            # Get user stats
            stats = await auth.get_user_stats(username)
            if stats and stats.get("matchedUser"):
                submit_stats = stats["matchedUser"].get("submitStats", {})
                ac_stats = submit_stats.get("acSubmissionNum", [])
                for stat in ac_stats:
                    diff = stat.get("difficulty", "")
                    count = stat.get("count", 0)
                    if diff == "All":
                        print(f"Problems Solved: {count}")
                    elif diff in ("Easy", "Medium", "Hard"):
                        print(f"  {diff}: {count}")
        else:
            print("Status: Session expired")
            print("\nPlease login again with fresh cookies:")
            print("  grind auth login --session <LEETCODE_SESSION> --csrf <csrftoken>")
            return 1
    finally:
        await auth.close()

    return 0


def handle_sync_command(args: argparse.Namespace) -> int:
    """Handle sync subcommand."""
    if args.status:
        return asyncio.run(sync_status())
    if args.queue:
        return asyncio.run(process_submission_queue())
    return asyncio.run(sync_run(full=args.full, verbose=args.verbose))


async def sync_status() -> int:
    """Show sync status."""
    from grind.config import load_settings
    from grind.sync import SyncService

    settings = load_settings()
    sync = SyncService(settings.get_db_path())

    stats = sync.get_sync_stats()

    print("Sync Status")
    print("=" * 40)
    print(f"Last sync: {stats['last_sync'].isoformat() if stats['last_sync'] else 'Never'}")
    print(f"Synced submissions: {stats['total_submissions']}")
    print(f"Accepted submissions: {stats['accepted_submissions']}")
    print(f"Solved on LeetCode: {stats['solved_leetcode']}")
    print(f"Solved locally: {stats['solved_locally']}")
    print(f"Premium problems (hidden): {stats['premium_problems']}")

    # Show pending submissions in queue
    pending = sync.get_pending_submissions()
    if pending:
        print(f"\nPending submissions in queue: {len(pending)}")
        for sub in pending[:5]:
            print(f"  - {sub['problem_slug']} ({sub['language']})")
        if len(pending) > 5:
            print(f"  ... and {len(pending) - 5} more")

    return 0


async def sync_run(full: bool = False, verbose: bool = False) -> int:
    """Run sync."""
    from grind.config import load_settings
    from grind.sync import SyncService, SyncStatus

    settings = load_settings()
    sync = SyncService(settings.get_db_path())

    def progress(msg: str) -> None:
        if verbose:
            print(f"  {msg}")

    print("Starting LeetCode sync...")
    if full:
        print("Mode: Full sync")
    else:
        print("Mode: Incremental sync")

    result = await sync.sync(full=full, progress_callback=progress)

    print()
    if result.status == SyncStatus.SUCCESS:
        print("Sync completed successfully!")
        print(f"  Submissions synced: {result.submissions_synced}")
        print(f"  Problems updated: {result.problems_updated}")
        if result.duration_seconds:
            print(f"  Duration: {result.duration_seconds:.1f}s")
        return 0
    elif result.status == SyncStatus.NOT_AUTHENTICATED:
        print("Error: Not authenticated")
        print("Run 'grind auth login' first")
        return 1
    elif result.status == SyncStatus.PARTIAL:
        print("Sync partially completed")
        print(f"  Submissions synced: {result.submissions_synced}")
        for error in result.errors:
            print(f"  Warning: {error}")
        return 0
    else:
        print("Sync failed!")
        for error in result.errors:
            print(f"  Error: {error}")
        return 1


async def process_submission_queue() -> int:
    """Process and submit queued solutions."""
    from grind.config import load_settings
    from grind.sync import SyncService, SubmissionService
    from grind.auth import LeetCodeAuth

    settings = load_settings()
    sync = SyncService(settings.get_db_path())
    auth = LeetCodeAuth()

    # Check authentication
    if not await auth.is_authenticated():
        print("Error: Not authenticated")
        print("Run 'grind auth login' first")
        await auth.close()
        return 1

    pending = sync.get_pending_submissions()
    if not pending:
        print("No pending submissions in queue.")
        await auth.close()
        return 0

    print(f"Processing {len(pending)} queued submissions...")
    print()

    submission_svc = SubmissionService(auth=auth)
    success_count = 0
    fail_count = 0

    for item in pending:
        problem_slug = item["problem_slug"]
        code = item["code"]
        language = item["language"]
        queue_id = item["id"]

        print(f"Submitting: {problem_slug} ({language})...")

        try:
            result = await submission_svc.submit(
                problem_slug=problem_slug,
                code=code,
                language=language,
            )

            if result.is_accepted:
                print(f"  ✓ Accepted! Runtime: {result.runtime}, Memory: {result.memory}")
                sync.mark_queue_submitted(queue_id, result.submission_id)
                sync.mark_problem_solved_locally(problem_slug)
                success_count += 1
            else:
                print(f"  ✗ {result.status_message}")
                if result.passed_ratio:
                    print(f"    Test cases: {result.passed_ratio}")
                # Don't remove from queue on failure - user might want to fix and retry
                fail_count += 1

        except Exception as e:
            print(f"  Error: {e}")
            fail_count += 1

    print()
    print(f"Completed: {success_count} accepted, {fail_count} failed")

    await auth.close()
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
