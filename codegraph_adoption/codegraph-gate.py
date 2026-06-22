#!/usr/bin/env python3
"""CodeGraph-first ordering gate (Option A) -- reference implementation.

Ported from falkor-writ (.claude/hooks/codegraph-gate.py), tested across all
8 branches. This is the LITERAL port for the "quick path" in BUNDLING_TODO.md.
The "native path" reimplements this logic as a `codegraph tool-gate` TS
subcommand (mirroring `prompt-hook`); see that doc.

Two hook events, one script (dispatch on hook_event_name):

  PostToolUse  (matcher: mcp__codegraph__.*)
      Records a freshness timestamp every time a codegraph tool runs.

  PreToolUse   (matcher: Grep|Glob|Read)
      Denies a code-exploration call UNLESS a codegraph tool ran within
      WINDOW seconds. Steers Claude to run codegraph_explore first, then
      Grep/Glob/Read are unlocked for detail inspection.

Gated calls:
  - Grep / Glob               (always exploration) -- except clearly non-.py greps
  - Read on a *.py file       (Python source)
Never gated:
  - Read on non-.py (md/toml/json/txt/...)   -> per the CLAUDE.md decision tree
  - anything, if a codegraph tool ran within WINDOW seconds

Safety:
  - No-ops entirely if cwd has no .codegraph/ dir  -> portable / globalizable.
  - Fails OPEN on any error -> a bug here never blocks legitimate work.

State file: <cwd>/.codegraph/.last_graph_use  (.codegraph/ is gitignored)
"""

import json
import os
import sys
import time

WINDOW = 300  # seconds a codegraph call keeps Grep/Glob/Read unlocked

# Extensions/types that are NOT Python -> a Grep scoped to these is allowed cold.
_NON_PY_HINTS = ("md", "markdown", "toml", "json", "txt", "yaml", "yml",
                 "cfg", "ini", "rst", "sh", "html", "css")


def _grep_is_non_python(tool_input):
    """True only if the Grep is explicitly scoped away from Python."""
    t = (tool_input.get("type") or "").lower()
    g = (tool_input.get("glob") or "").lower()
    if t:
        return t != "py" and t in _NON_PY_HINTS
    if g:
        return ".py" not in g and any(h in g for h in _NON_PY_HINTS)
    return False


def main():
    data = json.loads(sys.stdin.read())
    event = data.get("hook_event_name", "")
    cwd = data.get("cwd") or os.getcwd()
    cg_dir = os.path.join(cwd, ".codegraph")

    # Not a codegraph-indexed repo -> never interfere.
    if not os.path.isdir(cg_dir):
        return 0

    state = os.path.join(cg_dir, ".last_graph_use")
    tool = data.get("tool_name", "")

    if event == "PostToolUse":
        if tool.startswith("mcp__codegraph__"):
            try:
                with open(state, "w") as f:
                    f.write(str(time.time()))
            except OSError:
                pass
        return 0

    if event != "PreToolUse":
        return 0

    ti = data.get("tool_input", {}) or {}

    gated = False
    if tool == "Grep":
        gated = not _grep_is_non_python(ti)
    elif tool == "Glob":
        gated = True
    elif tool == "Read":
        gated = (ti.get("file_path", "") or "").endswith(".py")

    if not gated:
        return 0

    # Recent codegraph call? -> allow detail inspection.
    try:
        last = float(open(state).read().strip())
    except (OSError, ValueError):
        last = 0.0
    if time.time() - last <= WINDOW:
        return 0

    reason = (
        f"CodeGraph-first gate: this repo is codegraph-indexed, and no "
        f"codegraph tool has run in the last {WINDOW // 60} min. "
        f"Run codegraph_explore (a question or symbol/file names) or "
        f"codegraph_node BEFORE {tool} on code -- one call returns verbatim "
        f"source + call graph and usually answers the question outright. "
        f"After a codegraph call, {tool} is unlocked for "
        f"{WINDOW // 60} min for detail inspection. (Non-.py Read is never gated.)"
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open: never block real work on a gate bug
