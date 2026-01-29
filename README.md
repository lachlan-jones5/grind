# Grind

AI-powered LeetCode practice TUI with vim bindings. Train smarter, not harder.

## Features

- **Beautiful TUI** - Terminal-based interface with vim-like keybindings
- **AI Coach** - Personalized coaching with Socratic hints, code review, and pattern recognition
- **Spaced Repetition** - Automatically resurface problems based on your weak patterns
- **Progress Tracking** - SQLite-backed history of attempts, streaks, and insights
- **LeetCode Integration** - Sync solved problems and submit solutions directly
- **Multiple Languages** - C++, Rust, and OCaml support

## Installation

```bash
# Clone the repository
git clone https://github.com/lachlan-jones5/grind.git
cd grind

# Install with pip (recommended: use a virtual environment)
pip install -e .
```

## Usage

```bash
# Start the TUI
grind

# With options
grind --provider openrouter --language rust
grind --relay-url http://myrelay:8080
```

## LeetCode Authentication

Grind can connect to your LeetCode account to sync your solved problems and submit solutions directly.

### Getting Your Session Cookies

1. Log in to [leetcode.com](https://leetcode.com) in your browser
2. Open Developer Tools (F12) > Application > Cookies > leetcode.com
3. Copy the values for:
   - `LEETCODE_SESSION` - Your session token
   - `csrftoken` - Your CSRF token

### Authenticating

```bash
# Log in with your session cookies
grind auth login --session <LEETCODE_SESSION> --csrf <csrftoken>

# Check authentication status
grind auth status

# Log out
grind auth logout
```

### Syncing Progress

```bash
# Sync your submission history
grind sync

# Full sync (ignore incremental)
grind sync --full

# Show sync status
grind sync --status

# Process pending submissions (from offline queue)
grind sync --queue
```

### Submitting Solutions

When practicing in the TUI:
- **Ctrl+Enter** - Submit your solution to LeetCode
- **F3** - Get AI review of your solution (local only)

If you're offline, submissions are automatically queued and will be sent when you reconnect.

### Troubleshooting

**Session expired:**
```bash
# Re-authenticate with fresh cookies
grind auth logout
grind auth login --session <NEW_SESSION> --csrf <NEW_CSRF>
```

**Rate limiting:**
Grind implements exponential backoff. Wait a few minutes and retry.

**Premium problems:**
Premium-only problems are filtered out automatically. They're marked in the database but won't appear in problem lists.

## Keybindings

### Main Menu
| Key | Action |
|-----|--------|
| `d` | Daily challenge |
| `p` | Problem list |
| `s` | Statistics dashboard |
| `q` | Quit |

### Problem List
| Key | Action |
|-----|--------|
| `1-5` | Switch study plan (Top 150, Blind 75, etc.) |
| `j/k` | Navigate up/down |
| `Enter` | Select problem |
| `f` | Toggle filter (All/Unsolved/Solved) |
| `u` | Show unsolved only |
| `a` | Show all |
| `q` | Back |

### Practice Screen
| Key | Action |
|-----|--------|
| `h` | Get a hint (escalating: gentle -> medium -> strong) |
| `r` | Run code locally |
| `Ctrl+Enter` | Submit to LeetCode |
| `F3` | Get AI review |
| `c` | Chat with coach |
| `n` | Next problem |
| `Tab` | Switch panels |
| `q` | Quit |

### Statistics Screen
| Key | Action |
|-----|--------|
| `r` | Refresh stats |
| `q` | Back |

## Configuration

Grind uses environment variables for configuration. Create a `.env` file or export them:

```bash
# AI Provider: "copilot" (default) or "openrouter"
GRIND_PROVIDER=copilot

# For Copilot via Cynefin relay
GRIND_COPILOT_RELAY_URL=http://localhost:8080

# For OpenRouter
GRIND_OPENROUTER_API_KEY=sk-or-...

# Default language: cpp, rust, ocaml
GRIND_DEFAULT_LANGUAGE=cpp

# LeetCode username (for tracking)
GRIND_LEETCODE_USERNAME=your_username
```

## Customizing the AI Coach

The AI coach's behavior can be customized by modifying the system prompt. Create a file at `~/.config/grind/agent.txt`:

```text
You are a strict interview coach. Simulate real FAANG interview pressure.
Never give direct answers. Always ask clarifying questions first.
Time the user and provide feedback on their pacing.
```

Or set it via environment variable:

```bash
export GRIND_AGENT_SYSTEM_PROMPT="Your custom prompt here..."
```

### Coaching Modes

The default coach uses the Socratic method, but you can customize it for different training styles:

- **Socratic Mode** - Asks guiding questions, never gives direct answers
- **Teaching Mode** - Explains patterns and concepts in detail
- **Interview Mode** - Simulates interview pressure with time constraints
- **Debug Mode** - Helps trace through failing test cases step-by-step

## Architecture

```
grind/
├── src/grind/
│   ├── main.py         # CLI entry point
│   ├── config.py       # Settings management
│   ├── api/
│   │   └── leetcode.py # LeetCode API client
│   ├── ai/
│   │   └── coach.py    # AI coach (Copilot/OpenRouter)
│   ├── db/
│   │   └── database.py # SQLite persistence
│   └── tui/
│       └── app.py      # Textual TUI application
└── tests/
```

## Integration with Cynefin

Grind integrates with [Cynefin](https://github.com/lachlan-jones5/cynefin) for self-hosted AI access:

```bash
# Start the Cynefin relay
cy serve

# In another terminal, start grind
grind --relay-url http://localhost:8080
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/grind

# Linting
ruff check src/grind
```

## License

MIT
