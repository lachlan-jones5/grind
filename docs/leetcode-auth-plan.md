# LeetCode Authentication & Synchronization Plan

This document outlines the implementation plan for adding LeetCode account authentication and progress synchronization to Grind.

## Overview

### Goals
1. **Authenticate with LeetCode** - Allow users to connect their LeetCode account ✅
2. **Sync solved problems** - Fetch user's submission history from LeetCode ✅
3. **Track progress bidirectionally** - Local progress reflects LeetCode state ✅
4. **Submit solutions** - Run code against LeetCode's judge directly from Grind ✅

### Non-Goals
- Contest participation
- Discussion/comments integration
- leetcode.cn (Chinese version) support
- Premium-only problem access (filtered out)

---

## Phase 1: Authentication System ✅ COMPLETE

### Implementation Summary

**Files Created:**
- `src/grind/auth/__init__.py` - Module exports
- `src/grind/auth/session.py` - Session management with keyring storage
- `src/grind/auth/leetcode.py` - LeetCode authentication and GraphQL API

**Features Implemented:**
- Session cookie authentication (LEETCODE_SESSION + csrftoken)
- Secure storage via system keyring (macOS Keychain, GNOME Keyring, etc.)
- Fallback to JSON file with restrictive permissions (0o600)
- Session validation with 5-minute cache TTL
- GraphQL API integration with retry logic

### CLI Commands

```bash
# Authenticate with session cookies
grind auth login --session <LEETCODE_SESSION> --csrf <csrftoken>

# Check authentication status
grind auth status

# Logout / clear session
grind auth logout
```

### Tests
- 51 tests in `tests/test_auth.py`
- Covers Session, SessionManager, LeetCodeAuth, error handling

---

## Phase 2: Read-Only Synchronization ✅ COMPLETE

### Implementation Summary

**Files Created:**
- `src/grind/sync/__init__.py` - Module exports
- `src/grind/sync/models.py` - Data models (LeetCodeSubmission, ProblemStatus, SyncMeta)
- `src/grind/sync/service.py` - Sync service with database and API logic

**Database Tables Created:**
```sql
leetcode_submissions  -- Synced submissions from LeetCode
problem_status        -- Problem solved status (local + LeetCode, premium flag)
sync_meta            -- Sync metadata (last sync time, etc.)
submission_queue     -- Offline queue for later submission
```

**Features Implemented:**
- Full and incremental sync from LeetCode
- Paginated submission history fetch
- Problem list sync with premium filtering
- Premium problems marked and excluded by default
- Offline submission queue

### CLI Commands

```bash
# Incremental sync
grind sync

# Full sync (ignore last sync time)
grind sync --full

# Show progress during sync
grind sync --verbose

# Show sync status
grind sync --status
```

### Tests
- 43 tests in `tests/test_sync.py`
- Covers models, database operations, sync logic, queue management

---

## Phase 3: Solution Submission ✅ COMPLETE

### Implementation Summary

**Files Created:**
- `src/grind/sync/submission.py` - Submission service with GraphQL mutations

**Features Implemented:**
- Solution submission via GraphQL mutation
- Polling for submission results (1s interval, 30s timeout)
- Language mapping (18 languages supported)
- Result display with status, runtime, memory, percentiles
- Failed test case display with input/expected/actual
- Compile error and runtime error display
- Offline queue integration (auto-queue on failure)

### Language Mapping

| Grind      | LeetCode Slug |
|------------|---------------|
| cpp, c++   | cpp           |
| rust       | rust          |
| ocaml      | ocaml         |
| python     | python3       |
| java       | java          |
| go, golang | golang        |
| javascript, js | javascript |
| typescript, ts | typescript |
| c          | c             |
| csharp, c# | csharp        |
| ruby       | ruby          |
| swift      | swift         |
| kotlin     | kotlin        |
| scala      | scala         |
| php        | php           |

### TUI Integration

**Keybindings:**
- `Ctrl+Enter` - Submit to LeetCode
- `F3` - Local submit (AI review)

**Result Display:**
- Shows in coach panel
- Accepted: ✓ with runtime/memory percentiles
- Failed: ✗ with test case info, compile/runtime errors

### CLI Commands

```bash
# Process pending queued submissions
grind sync --queue
```

### Tests
- 46 tests in `tests/test_submission.py`
- Covers SubmissionStatus, SubmissionResult, language mapping, service, formatting

---

## Phase 4: Polish & Enhancement ✅ COMPLETE

### 4.1 Progress Dashboard ✅

StatsScreen added with:
- Local practice stats (streak, problems solved, attempts)
- LeetCode sync stats (solved count, submissions, accepted)
- Visual progress bars by difficulty (Easy/Medium/Hard)
- Pending submission queue count
- Last sync timestamp

```
┌─ Your Progress ─────────────────────────┐
│ LeetCode: 247 / 3000 solved             │
│ Local Practice: 52 problems, 89 attempts│
│                                         │
│ Easy:   ████████░░░░░░░░░░░░ 120/800    │
│ Medium: ████░░░░░░░░░░░░░░░░  98/1500   │
│ Hard:   ██░░░░░░░░░░░░░░░░░░  29/700    │
│                                         │
│ Streak: 12 days                         │
└─────────────────────────────────────────┘
```

### 4.2 Smart Problem Selection ✅

ProblemsScreen enhanced with:
- `[f]` Toggle filter (All → Unsolved → Solved → All)
- `[u]` Show unsolved only
- `[a]` Show all problems
- Solved problems marked with ✓
- Filter status indicator
- Cursor navigation respects filtered list

### 4.3 Offline Mode Improvements ✅

GrindApp enhanced with:
- `is_online` status tracking
- `queue_count` tracking
- Offline indicator on WelcomeScreen
- Pending queue count display
- Automatic queue processing (every 60s when online)
- Silent background submission processing

### 4.4 Documentation ✅

README.md updated with:
- LeetCode authentication instructions
- Cookie extraction steps
- Sync commands and options
- Submission keybindings
- Troubleshooting guide
- Updated keybinding tables

### Tests
- 25 tests in `tests/test_phase4.py`
- Covers StatsScreen, filtering, offline mode, queue processing

---

## Implementation Status

| Phase | Status | Tests |
|-------|--------|-------|
| Phase 1: Authentication | ✅ Complete | 51 tests |
| Phase 2: Read Sync | ✅ Complete | 43 tests |
| Phase 3: Submission | ✅ Complete | 46 tests |
| Phase 4: Polish | ✅ Complete | 25 tests |

**Total Tests: 633 passing**

---

## Security Implementation

1. **Session Storage** ✅
   - System keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager)
   - Fallback: JSON file with 0o600 permissions
   - Never log session tokens

2. **Rate Limiting** ✅
   - Exponential backoff on 429 responses
   - Retry-After header respected
   - Max 5 retries

3. **Privacy** ✅
   - Only fetch user's own data
   - Local DB is user-controlled
   - No telemetry or external reporting

---

## Dependencies Added

```toml
[project]
dependencies = [
    # ... existing
    "keyring>=25.0.0",  # Secure credential storage
]
```

---

## API Reference

### LeetCode GraphQL Endpoint
```
URL: https://leetcode.com/graphql
Method: POST
Headers:
  - Cookie: LEETCODE_SESSION=<session>; csrftoken=<csrf>
  - X-CSRFToken: <csrf>
  - Content-Type: application/json
```

### Queries Implemented
- `globalData` - Validate session, get username
- `userProfile` - Get user profile and premium status
- `userStats` - Get submission statistics
- `submissionList` - Get submission history (paginated)
- `problemsetQuestionList` - Get problem list with premium flag

### Mutations Implemented
- `submitSolution` - Submit code to LeetCode
- `checkSubmission` - Poll for submission result

---

## Resolved Questions

1. **leetcode.cn support?** → No, not in scope
2. **Premium problems?** → Filtered out, marked with `is_premium` flag
3. **Offline submissions?** → Queued locally, processed with `grind sync --queue`
