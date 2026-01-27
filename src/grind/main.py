"""Main entry point for Grind CLI."""

import argparse
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


if __name__ == "__main__":
    sys.exit(main())
