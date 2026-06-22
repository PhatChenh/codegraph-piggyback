#!/usr/bin/env python3
"""Smoke test for piggyback.py.

Runs the CLI against a throwaway $HOME, a throwaway repo cwd, and a throwaway
manifest (PIGGYBACK_MANIFEST), asserting on the resulting settings.json. No
network, no codegraph: install uses --no-codegraph, every command uses
--no-update (this repo is a git checkout and must not be pulled).

Run:  python3 test_piggyback.py     (exit 0 = all pass)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "piggyback.py"
IMPACT = "impact-analyzer/impact-analyzer.py"
GATE = "codegraph_adoption/codegraph-gate.py"
PASS = FAIL = 0


def run(args, home, cwd, manifest):
    env = dict(os.environ, HOME=str(home), PIGGYBACK_MANIFEST=str(manifest))
    return subprocess.run([sys.executable, str(CLI), *args],
                          env=env, cwd=str(cwd), capture_output=True, text=True)


def write_manifest(path, scripts):
    path.write_text(json.dumps({"scripts": scripts}, indent=2))


def load(p):
    return json.loads(p.read_text()) if p.exists() else None


def has_hook(settings, event, matcher, cmd_substr):
    for g in (settings or {}).get("hooks", {}).get(event, []):
        if g.get("matcher") == matcher:
            for h in g.get("hooks", []):
                if cmd_substr in h.get("command", ""):
                    return True
    return False


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS {name}")
    else:
        FAIL += 1; print(f"  FAIL {name}")


IMPACT_ENTRY = {"impact-analyzer": {"script": IMPACT, "scope": "global",
                                    "hooks": [{"event": "PostToolUse", "matcher": "Read"}]}}
GATE_ENTRY = {"codegraph-gate": {"script": GATE, "scope": "repo", "hooks": [
    {"event": "PreToolUse", "matcher": "Grep|Glob|Read"},
    {"event": "PostToolUse", "matcher": "mcp__codegraph__.*"}]}}


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        home, repo, man = td / "home", td / "repo", td / "manifest.json"
        home.mkdir(); (repo / ".codegraph").mkdir(parents=True)
        g = home / ".claude" / "settings.json"
        r = repo / ".claude" / "settings.json"
        I = ["install", "--no-codegraph", "--no-update"]
        U = ["update", "--no-update"]

        # 1. install reconciles global impact-analyzer in
        write_manifest(man, dict(IMPACT_ENTRY))
        run(I, home, repo, man)
        check("install adds global impact-analyzer", has_hook(load(g), "PostToolUse", "Read", IMPACT))

        # 2. idempotent re-run
        before = g.read_text()
        run(I, home, repo, man)
        check("re-install byte-identical (idempotent)", g.read_text() == before)

        # 3. sibling hook + unrelated key survive reconcile
        s = load(g)
        s["hooks"]["PostToolUse"].append({"matcher": "Read",
                                          "hooks": [{"type": "command", "command": "echo sibling"}]})
        s["permissions"] = {"allow": ["mcp__x__y"]}
        g.write_text(json.dumps(s, indent=2))
        run(I, home, repo, man)
        s = load(g)
        check("sibling hook preserved",
              any("echo sibling" in h.get("command", "")
                  for grp in s["hooks"]["PostToolUse"] for h in grp.get("hooks", [])))
        check("unrelated key preserved", s.get("permissions", {}).get("allow") == ["mcp__x__y"])

        # 4. RECONCILE REMOVAL: drop impact from manifest → reconcile strips OUR
        #    hook but keeps the user's sibling.
        write_manifest(man, {})
        run(U, home, repo, man)
        s = load(g)
        check("manifest removal drops owned hook", not has_hook(s, "PostToolUse", "Read", IMPACT))
        check("removal keeps user's sibling",
              any("echo sibling" in h.get("command", "")
                  for grp in s.get("hooks", {}).get("PostToolUse", []) for h in grp.get("hooks", [])))

        # 5. repo scope: gate in manifest → update (cwd indexed) wires both blocks
        write_manifest(man, dict(GATE_ENTRY))
        run(U, home, repo, man)
        check("repo gate PreToolUse", has_hook(load(r), "PreToolUse", "Grep|Glob|Read", GATE))
        check("repo gate PostToolUse", has_hook(load(r), "PostToolUse", "mcp__codegraph__.*", GATE))

        # 6. repo removal propagates
        write_manifest(man, {})
        run(U, home, repo, man)
        s = load(r)
        check("repo gate removed on manifest drop", not has_hook(s, "PreToolUse", "Grep|Glob|Read", GATE))

        # 7. `add` upserts manifest + applies locally
        run(["add", "foo", "--script", IMPACT, "--scope", "global",
             "--hook", "PostToolUse:Write"], home, repo, man)
        check("add writes manifest entry", "foo" in load(man)["scripts"])
        check("add applies hook locally", has_hook(load(g), "PostToolUse", "Write", IMPACT))

        # 8. `rm` deletes manifest entry + reconciles it out
        run(["rm", "foo"], home, repo, man)
        check("rm deletes manifest entry", "foo" not in load(man)["scripts"])
        check("rm removes hook locally", not has_hook(load(g), "PostToolUse", "Write", IMPACT))

        # 9. unparseable settings → abort, no clobber
        write_manifest(man, dict(IMPACT_ENTRY))
        g.write_text("{ not json ]")
        res = run(I, home, repo, man)
        check("unparseable settings aborts (exit 1)", res.returncode == 1)
        check("unparseable settings not clobbered", g.read_text() == "{ not json ]")

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
