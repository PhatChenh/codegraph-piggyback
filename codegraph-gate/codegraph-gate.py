#!/usr/bin/env python3
"""CodeGraph-first ordering gate (Option A) -- reference implementation.

Ported from falkor-writ (.claude/hooks/codegraph-gate.py), tested across all
8 branches. This is the LITERAL port for the "quick path" in BUNDLING_TODO.md.
The "native path" reimplements this logic as a `codegraph tool-gate` TS
subcommand (mirroring `prompt-hook`); see that doc.

Two hook events, one script (dispatch on hook_event_name):

  PostToolUse  (matcher: mcp__codegraph__.*  AND  Edit|Write)
      Records a freshness timestamp every time a codegraph tool runs.
      Also records per-file "shown" (codegraph_node file-mode) and "edited"
      (Edit/Write) state so the edit phase isn't taxed by the window.

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
  - Read of a file codegraph_node has shown within SHOW_TTL   (edit-phase: the
    file was already returned verbatim; re-priming the gate would be busywork)
  - Read of a file just Edit/Write'd within EDIT_TTL          (verifying your
    own change, not exploring)

  The per-file exemptions address G1/G2 in FEEDBACK.md: the 5-min window kept
  lapsing mid edit-loop, forcing a throwaway codegraph_node purely to re-open
  the gate. A file codegraph already returned, or one you just edited, is read
  for detail -- not discovery -- so the gate steps aside.
  NOTE (G2): the hook CANNOT mark a file as "read" for the Edit tool's own
  "must Read first" precondition -- that is harness file-state only the Read
  tool updates. So a codegraph_node read still must be followed by a real
  Read before Edit. This gate only stops forcing the *extra* codegraph call;
  the inherent codegraph->Read round-trip for Edit is a harness limitation.

Safety:
  - No-ops entirely if cwd has no .codegraph/ dir  -> portable / globalizable.
  - Fails OPEN on any error -> a bug here never blocks legitimate work.

State files (all under <cwd>/.codegraph/, which is gitignored):
  .last_graph_use   epoch ts -- last codegraph call (global WINDOW unlock)
  .gate_shown       JSON {file_key: epoch ts} -- files codegraph_node returned
  .gate_edited      JSON {file_key: epoch ts} -- files just Edit/Write'd
  file_key is the raw path as the tool received it (codegraph_node may pass a
  basename); a Read matches on exact OR basename equality.
"""

import json
import os
import sys
import time

WINDOW = int(os.environ.get("CODEGRAPH_GATE_WINDOW", "300"))      # global unlock
SHOW_TTL = int(os.environ.get("CODEGRAPH_GATE_SHOW_TTL", "1800"))  # per-file shown
EDIT_TTL = int(os.environ.get("CODEGRAPH_GATE_EDIT_TTL", "300"))   # per-file edited

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


def _read_json(path, default):
    try:
        return json.loads(open(path).read())
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    try:
        with open(path, "w") as f:
            json.dump(obj, f)
    except OSError:
        pass


def _touch(path):
    try:
        with open(path, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def _record_file_state(cg_dir, fname, key, ttl):
    """Append/refresh {key: now} into <cg_dir>/<fname>, pruning entries older
    than ttl. No-op on any error (fail-open)."""
    state = os.path.join(cg_dir, fname)
    data = _read_json(state, {}) or {}
    if not isinstance(data, dict):
        data = {}
    now = time.time()
    data = {k: v for k, v in data.items()
            if isinstance(v, (int, float)) and now - v < ttl}
    data[key] = now
    _write_json(state, data)


def _file_exempt(cg_dir, fname, file_path, ttl):
    """True if file_path matches a key in <cg_dir>/<fname> within ttl.
    Matches on exact path OR basename (codegraph_node may pass a basename)."""
    state = os.path.join(cg_dir, fname)
    data = _read_json(state, {}) or {}
    if not isinstance(data, dict):
        return False
    now = time.time()
    base = os.path.basename(file_path)
    for key, ts in data.items():
        if not isinstance(ts, (int, float)) or now - ts > ttl:
            continue
        if key == file_path or (base and os.path.basename(key) == base):
            return True
    return False


def _post_tool_use(data, cwd, cg_dir):
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}

    # Any codegraph call refreshes the global window.
    if tool.startswith("mcp__codegraph__"):
        _touch(os.path.join(cg_dir, ".last_graph_use"))
        # codegraph_node file-mode returns a file's verbatim source -> record
        # it as "shown" so a follow-up Read of that file is gate-free.
        if tool == "mcp__codegraph__codegraph_node":
            f = (ti.get("file") or "").strip()
            if f:
                _record_file_state(cg_dir, ".gate_shown", f, SHOW_TTL)
        return 0

    # Edit/Write -> record the edited file so a verifying Read is gate-free.
    if tool in ("Edit", "Write"):
        f = (ti.get("file_path") or "").strip()
        if f:
            _record_file_state(cg_dir, ".gate_edited", f, EDIT_TTL)
    return 0


def _pre_tool_use(data, cwd, cg_dir):
    tool = data.get("tool_name", "")
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

    # Per-file edit-phase exemptions (G1/G2): a file codegraph already showed
    # or one just edited is read for detail, not discovery.
    if tool == "Read":
        fp = ti.get("file_path", "") or ""
        if fp and (_file_exempt(cg_dir, ".gate_shown", fp, SHOW_TTL)
                   or _file_exempt(cg_dir, ".gate_edited", fp, EDIT_TTL)):
            return 0

    # Recent codegraph call? -> allow detail inspection.
    try:
        last = float(open(os.path.join(cg_dir, ".last_graph_use")).read().strip())
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
        f"{WINDOW // 60} min for detail inspection. (Non-.py Read is never gated; "
        f"Read of a file codegraph_node already returned, or one you just "
        f"edited, is always exempt.)"
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


def main():
    data = json.loads(sys.stdin.read())
    event = data.get("hook_event_name", "")
    cwd = data.get("cwd") or os.getcwd()
    cg_dir = os.path.join(cwd, ".codegraph")

    # Not a codegraph-indexed repo -> never interfere.
    if not os.path.isdir(cg_dir):
        return 0

    if event == "PostToolUse":
        return _post_tool_use(data, cwd, cg_dir)
    if event == "PreToolUse":
        return _pre_tool_use(data, cwd, cg_dir)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open: never block real work on a gate bug