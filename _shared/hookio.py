"""_shared.hookio — Claude Code hook stdin/stdout plumbing, fail-open.

Pattern extracted from `impact-analyzer/impact-analyzer.py` and
`ssot-diagram/decision_hook.py`. Frozen invariants (Block 1e): a hook using
this is silent on no-signal and NEVER raises into the session.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable


def read_hook_input() -> dict[str, Any] | None:
    """Parse the hook JSON from stdin. None on any parse failure (fail open)."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def emit_context(text: str, event: str = "PostToolUse") -> None:
    """Inject bounded additionalContext back into the session."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }))


def run_fail_open(main: Callable[[], int | None]) -> None:
    """Entrypoint wrapper: any internal error exits 0 silently — a hook bug
    must never disrupt the session."""
    try:
        sys.exit(main() or 0)
    except SystemExit:
        raise
    except BaseException:
        sys.exit(0)
