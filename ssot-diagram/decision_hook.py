#!/usr/bin/env python3
"""decision_hook — surface decision staleness when a decision doc is read.

A Claude Code PostToolUse:Read hook. When a file under the decision index is
read, it recomputes that document's anchor statuses (via decision_index) and, if
any anchor is not FRESH, injects an advisory note into the agent's context.

Contract — ADVISORY, never blocking:
  - Fails OPEN on ANY error (no db, no index, bad json, codegraph drift): a bug
    here must never disrupt a Read.
  - Emits nothing when every anchor is FRESH (no noise).
  - It SURFACES staleness; it does not resolve it. Resolution is human-gated:
    the agent must propose, never silently rewrite a stale decision.

State source is decision_index (same dir), reused read-only.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decision_index as di  # noqa: E402


def _emit(context: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))


def main() -> int:
    data = json.loads(sys.stdin.read())
    if data.get("tool_name") != "Read":
        return 0
    fp = (data.get("tool_input", {}) or {}).get("file_path")
    if not fp:
        return 0

    cwd = data.get("cwd") or "."
    db = di.find_db(Path(cwd))
    if not db:
        return 0
    root = di.repo_root_for(db)
    index_path = di.default_index_path(root)
    if not index_path.is_file():
        return 0

    doc = json.loads(index_path.read_text())
    decisions = doc.get("decisions")
    if not isinstance(decisions, dict):
        return 0

    target = Path(fp).resolve()
    hits = {did: dec for did, dec in decisions.items()
            if isinstance(dec, dict) and (root / dec.get("doc", "")).resolve() == target}
    if not hits:
        return 0

    con = di.open_db(db)
    rows, not_fresh = di._evaluate(con, root, hits)
    if not not_fresh:
        return 0

    lines = [f"  - {state}: {did} anchor `{ref}`"
             for did, ref, state in rows if state != di.FRESH]
    context = (
        "DECISION STALENESS (deterministic, from codegraph):\n"
        + "\n".join(lines)
        + "\n\nThe code these decision(s) anchor to has drifted (STALE), vanished "
        "(ORPHANED), or is under-specified (AMBIGUOUS). Treat the document as "
        "SUSPECT — do not act on it as current truth without checking. SURFACE this "
        "to the user and PROPOSE a resolution (amend / supersede / refresh snapshot); "
        "do NOT silently rewrite the decision. If still valid, the human runs "
        "`decision_index refresh <id>`."
    )
    _emit(context)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        sys.exit(0)  # fail-open: never disrupt a Read on a hook bug
