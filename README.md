# Grind 🏋️

AI-powered LeetCode practice TUI with vim bindings. Train smarter, not harder.

## Features

- **Beautiful TUI** - Terminal-based interface with vim-like keybindings
- **AI Coach** - Personalized coaching with Socratic hints, code review, and pattern recognition
- **Spaced Repetition** - Automatically resurface problems based on your weak patterns
- **Progress Tracking** - SQLite-backed history of attempts, streaks, and insights
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

### Keybindings

| Key | Action |
|-----|--------|
| `d` | Daily challenge |
| `p` | Problem list |
| `h` | Get a hint (escalating: gentle → medium → strong) |
| `r` | Run code |
| `s` | Submit and get AI review |
| `c` | Chat with coach |
| `n` | Next problem |
| `Tab` | Switch panels |
| `q` | Quit |

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
