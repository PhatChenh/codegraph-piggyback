#!/usr/bin/env python3
"""End-to-end replay of the FEEDBACK.md Phase-6 edit-loop scenario.

Drives a realistic session payload stream through the hook script against a
real indexed-repo cwd (a temp dir with .codegraph/). Runs the SAME stream
through BOTH:
  - the OLD/deployed script (reproduces G1/G2 -- the bug)
  - the NEW/fixed script in this repo           (passes -- the fix)

A true regression e2e: identical payload stream, old fails where new passes.

Does NOT touch live settings.json. To exercise the actual wired hook, the
fixed script must be deployed + the Edit|Write matcher reconciled into
~/.claude/settings.json (run `piggyback update` from this repo, then restart
the agent session) -- that deploy is a config change the user must approve.

Run:  python3 codegraph-gate/test_codegraph_gate_e2e.py     (exit 0 = pass)
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NEW = ROOT / "codegraph-gate.py"
OLD = Path.home() / ".codegraph-piggyback" / "codegraph_adoption" / "codegraph-gate.py"
PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS {name}")
    else:
        FAIL += 1; print(f"  FAIL {name}")


def run(script, payload, cwd):
    return subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                          env=dict(os.environ), cwd=str(cwd),
                          capture_output=True, text=True)


def denied(res):
    try:
        return json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except (ValueError, KeyError, TypeError):
        return False


def replay(label, script, repo):
    """Phase-6 edit-loop scenario. Returns dict of step -> denied? bool."""
    py = repo / "mod.py"; py.write_text("x = 1\n")
    other = repo / "other.py"; other.write_text("y = 2\n")
    r = {}

    # 1. cold start: Read .py -> denied (must codegraph first)
    r["cold_read_denied"] = denied(run(script, {
        "hook_event_name": "PreToolUse", "cwd": str(repo),
        "tool_name": "Read", "tool_input": {"file_path": str(py)}}, repo))

    # 2. codegraph_explore -> opens window
    run(script, {"hook_event_name": "PostToolUse", "cwd": str(repo),
                 "tool_name": "mcp__codegraph__codegraph_explore",
                 "tool_input": {"query": "how does x work"}}, repo)

    # 3. codegraph_node(file=other) -> returns other's source (records .gate_shown on NEW)
    run(script, {"hook_event_name": "PostToolUse", "cwd": str(repo),
                 "tool_name": "mcp__codegraph__codegraph_node",
                 "tool_input": {"file": str(other)}}, repo)

    # 4. window lapses mid edit-loop (backdate global window)
    (repo / ".codegraph" / ".last_graph_use").write_text(str(time.time() - 99999))

    # 5. Read of the file codegraph_node just showed (G1/G2): NEW allows, OLD denies
    r["shown_read_allowed"] = not denied(run(script, {
        "hook_event_name": "PreToolUse", "cwd": str(repo),
        "tool_name": "Read", "tool_input": {"file_path": str(other)}}, repo))

    # 6. unrelated .py still gated on both
    r["unrelated_denied"] = denied(run(script, {
        "hook_event_name": "PreToolUse", "cwd": str(repo),
        "tool_name": "Read", "tool_input": {"file_path": str(py)}}, repo))

    # 7. Edit other -> records .gate_edited on NEW
    run(script, {"hook_event_name": "PostToolUse", "cwd": str(repo),
                 "tool_name": "Edit", "tool_input": {
                     "file_path": str(other), "old_string": "y = 2",
                     "new_string": "y = 3"}}, repo)

    # 8. verify-own-change: Read other right after edit (window still lapsed)
    #    NEW allows, OLD denies
    r["verify_edit_allowed"] = not denied(run(script, {
        "hook_event_name": "PreToolUse", "cwd": str(repo),
        "tool_name": "Read", "tool_input": {"file_path": str(other)}}, repo))

    return r


def main():
    if not OLD.exists():
        print(f"SKIP: old/deeployed script not found at {OLD}")
        print("      (cannot reproduce-against-old; run new-script unit/e2e only)")
        # fall back to new-only sanity
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"; (repo / ".codegraph").mkdir(parents=True)
            r = replay("NEW-only", NEW, repo)
            check("NEW-only: shown_read_allowed", r["shown_read_allowed"])
            check("NEW-only: verify_edit_allowed", r["verify_edit_allowed"])
        print(f"\n{PASS} passed, {FAIL} failed")
        sys.exit(1 if FAIL else 0)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        repo_old = td / "old_repo"; (repo_old / ".codegraph").mkdir(parents=True)
        repo_new = td / "new_repo"; (repo_new / ".codegraph").mkdir(parents=True)
        old = replay("OLD", OLD, repo_old)
        new = replay("NEW", NEW, repo_new)

        print("OLD (deployed, pre-fix):")
        for k, v in old.items():
            print(f"  {k}={v}")
        print("NEW (fixed):")
        for k, v in new.items():
            print(f"  {k}={v}")

        # bug reproduction on OLD: shown_read and verify_edit are DENIED (the G1/G2 pain)
        check("OLD reproduces G1/G2: shown_read DENIED past window",
              old["shown_read_allowed"] is False)
        check("OLD reproduces G1: verify-edit DENIED past window",
              old["verify_edit_allowed"] is False)
        # fix on NEW: both allowed, unrelated still gated
        check("NEW fixes G1/G2: shown_read ALLOWED past window",
              new["shown_read_allowed"] is True)
        check("NEW fixes G1: verify-edit ALLOWED past window",
              new["verify_edit_allowed"] is True)
        # gate still bites where it should on both
        check("OLD cold_read denied", old["cold_read_denied"] is True)
        check("NEW cold_read denied", new["cold_read_denied"] is True)
        check("NEW unrelated .py still denied past window",
              new["unrelated_denied"] is True)

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()