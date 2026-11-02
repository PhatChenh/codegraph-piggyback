#!/usr/bin/env python3
"""Regression tests for codegraph-gate.py.

Feeds simulated hook JSON on stdin and asserts on stdout / state files.
Covers the G1/G2 fixes in FEEDBACK.md (per-file shown + edited exemptions)
plus the original behavior matrix from BUNDLING_TODO.

Run:  python3 codegraph-gate/test_codegraph_gate.py     (exit 0 = all pass)
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "codegraph-gate.py"
PASS = FAIL = 0


def run_hook(payload, cwd):
    env = dict(os.environ)
    return subprocess.run([sys.executable, str(SCRIPT)],
                          input=json.dumps(payload), env=env,
                          cwd=str(cwd), capture_output=True, text=True)


def pre(tool, cwd, **tool_input):
    return run_hook({"hook_event_name": "PreToolUse", "cwd": str(cwd),
                     "tool_name": tool, "tool_input": tool_input}, cwd)


def post(tool, cwd, **tool_input):
    return run_hook({"hook_event_name": "PostToolUse", "cwd": str(cwd),
                     "tool_name": tool, "tool_input": tool_input}, cwd)


def denied(res):
    try:
        return json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except (ValueError, KeyError, TypeError):
        return False


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS {name}")
    else:
        FAIL += 1; print(f"  FAIL {name}")


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        repo = td / "repo"
        (repo / ".codegraph").mkdir(parents=True)
        (repo / ".git").mkdir()  # CG1-1: a .py is gated via its file's git root
        py = repo / "mod.py"
        py.write_text("x = 1\n")

        # 1. cold: Read *.py denied; non-.py Read allowed; md-grep allowed
        check("cold Read .py denied", denied(pre("Read", repo, file_path=str(py))))
        md = repo / "doc.md"
        check("cold Read .md allowed",
              not denied(pre("Read", repo, file_path=str(md))))
        check("cold md-grep allowed",
              pre("Grep", repo, type="md", pattern="x").stdout == "")

        # 2. PostToolUse codegraph_explore writes .last_graph_use -> warm allow
        post("mcp__codegraph__codegraph_explore", repo, query="how does x work")
        check("warm Read .py allowed after explore",
              pre("Read", repo, file_path=str(py)).stdout == "")
        check("warm Grep allowed after explore",
              pre("Grep", repo, pattern="x").stdout == "")

        # 3. G2/G1 core: codegraph_node file-mode records .gate_shown -> a Read
        #    of that file is allowed EVEN after the global window lapses.
        #    Simulate window lapse by backdating .last_graph_use.
        other = repo / "other.py"
        other.write_text("y = 2\n")
        post("mcp__codegraph__codegraph_node", repo, file=str(other))
        # backdate global window so only the per-file exemption can save it
        state = repo / ".codegraph" / ".last_graph_use"
        state.write_text(str(time.time() - 99999))
        check("G1/G2: Read of codegraph_node-shown file allowed past window",
              pre("Read", repo, file_path=str(other)).stdout == "")
        # a different .py file (not shown, not edited) is still denied past window
        check("unrelated .py still denied past window",
              denied(pre("Read", repo, file_path=str(py))))

        # 4. codegraph_node may pass a basename -> Read with absolute path still
        #    matches on basename.
        basename_py = repo / "bn.py"
        basename_py.write_text("z = 3\n")
        post("mcp__codegraph__codegraph_node", repo, file="bn.py")
        state.write_text(str(time.time() - 99999))
        check("basename shown -> absolute-path Read allowed",
              pre("Read", repo, file_path=str(basename_py)).stdout == "")

        # 5. G1 verify-own-change: Edit/Write records .gate_edited -> Read of
        #    that file allowed even past window.
        edited = repo / "edited.py"
        edited.write_text("a = 0\n")
        post("Edit", repo, file_path=str(edited),
             old_string="a = 0", new_string="a = 1")
        state.write_text(str(time.time() - 99999))
        check("G1: Read of just-edited file allowed past window",
              pre("Read", repo, file_path=str(edited)).stdout == "")
        # Write also records
        written = repo / "written.py"
        post("Write", repo, file_path=str(written), content="b = 2")
        state.write_text(str(time.time() - 99999))
        check("G1: Read of just-written file allowed past window",
              pre("Read", repo, file_path=str(written)).stdout == "")

        # 6. TTL expiry: a shown file older than SHOW_TTL is denied again.
        shown_state = repo / ".codegraph" / ".gate_shown"
        data = json.loads(shown_state.read_text())
        key = next(k for k in data if os.path.basename(k) == "bn.py")
        data[key] = time.time() - (3600 * 24)  # way past any TTL
        shown_state.write_text(json.dumps(data))
        check("shown file past SHOW_TTL denied again",
              denied(pre("Read", repo, file_path=str(basename_py))))

        # 7. PostToolUse on a non-codegraph, non-Edit/Write tool is a no-op
        #    (matcher wouldn't fire, but script must tolerate it).
        before = (repo / ".codegraph" / ".last_graph_use").read_text()
        post("Read", repo, file_path=str(md))
        check("non-matching PostToolUse is no-op",
              (repo / ".codegraph" / ".last_graph_use").read_text() == before)

        # 8. cwd without .codegraph/ -> never interfere (allow everything)
        with tempfile.TemporaryDirectory() as td2:
            nodir = Path(td2) / "plain"
            nodir.mkdir()
            cold = pre("Read", nodir, file_path=str(nodir / "x.py"))
            check("no .codegraph dir -> Read .py allowed", cold.stdout == "")

        # 9. garbage stdin -> exit 0, no output (fail-open)
        env = dict(os.environ)
        garb = subprocess.run([sys.executable, str(SCRIPT)], input="{ broken",
                              env=env, cwd=str(repo), capture_output=True, text=True)
        check("garbage stdin exits 0", garb.returncode == 0)
        check("garbage stdin no stdout", garb.stdout == "")

        # 10. CG1-1: a Read of a .py is gated only when the FILE's own git repo
        #     root has a .codegraph/ dir. An indexed hook cwd alone does not gate it.
        with tempfile.TemporaryDirectory() as td3:
            td3 = Path(td3)
            idx = td3 / "indexed"  # hook cwd: indexed repo, cold (no graph use)
            (idx / ".codegraph").mkdir(parents=True)
            (idx / ".git").mkdir()
            idx_py = idx / "idx.py"
            idx_py.write_text("p = 1\n")

            # (a) sibling git worktree: .git is a FILE, no .codegraph/ -> allowed
            wt = td3 / "worktree"
            (wt / "scripts").mkdir(parents=True)
            (wt / ".git").write_text("gitdir: /elsewhere/.git/worktrees/worktree\n")
            wt_py = wt / "scripts" / "probe.py"
            wt_py.write_text("q = 2\n")
            check("CG1-1(a) Read .py in un-indexed worktree (.git file) allowed",
                  pre("Read", idx, file_path=str(wt_py)).stdout == "")

            # (b) a different plain repo with no index -> allowed
            plain = td3 / "plain"
            (plain / ".git").mkdir(parents=True)
            plain_py = plain / "mod.py"
            plain_py.write_text("r = 3\n")
            check("CG1-1(b) Read .py in other un-indexed repo allowed",
                  pre("Read", idx, file_path=str(plain_py)).stdout == "")

            # (c) a file inside no git repo at all -> allowed
            loose = td3 / "loose"
            loose.mkdir()
            loose_py = loose / "mod.py"
            loose_py.write_text("s = 4\n")
            check("CG1-1(c) Read .py in no git repo allowed",
                  pre("Read", idx, file_path=str(loose_py)).stdout == "")

            # (d) guard: .py inside the indexed cwd repo, cold -> still denied
            check("CG1-1(d) guard: .py in indexed cwd repo, cold, still denied",
                  denied(pre("Read", idx, file_path=str(idx_py))))

            # (e) guard: .py in ANOTHER repo that HAS a .codegraph/ -> still denied
            other = td3 / "other_indexed"
            (other / ".codegraph").mkdir(parents=True)
            (other / ".git").mkdir()
            other_py = other / "mod.py"
            other_py.write_text("t = 5\n")
            check("CG1-1(e) guard: .py in another indexed repo, cold, still denied",
                  denied(pre("Read", idx, file_path=str(other_py))))

            # (f) relative file_path resolves against the hook cwd (idx):
            #     ../worktree/scripts/probe.py is the un-indexed worktree file -> allowed;
            #     idx.py (indexed, cold) -> denied
            check("CG1-1(f) relative path to un-indexed worktree file allowed",
                  pre("Read", idx, file_path="../worktree/scripts/probe.py").stdout == "")
            check("CG1-1(f) relative path to indexed cwd file still denied",
                  denied(pre("Read", idx, file_path="idx.py")))

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()