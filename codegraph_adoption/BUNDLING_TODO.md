# Bundling the CodeGraph-first gate into `codegraph init`

**Goal:** when a user runs `codegraph init` on a repo, codegraph should wire a
**PreToolUse ordering gate** so the agent must call a codegraph tool before
reaching for Grep/Glob/Read-on-`.py`. Today the gate is a hand-installed Python
script + manual `settings.json` edit (done once in falkor-writ). This doc is the
plan to make it automatic.

> Why this exists: CLAUDE.md text ("CodeGraph First — MANDATORY") does **not**
> change agent behavior — it drifts and gets ignored. A `PreToolUse` deny+steer
> hook is the only real lever. Hooks can't *force* a codegraph call; they block
> the alternative and feed back a steer, and the agent retries with codegraph.

---

## How the gate works (the behavior to preserve)

| Event | Matcher | Action |
|---|---|---|
| `PostToolUse` | `mcp__codegraph__.*` | write epoch ts → `<cwd>/.codegraph/.last_graph_use` |
| `PreToolUse` | `Grep\|Glob\|Read` | **deny** unless a codegraph tool ran within `WINDOW` (300s) |

- **Gated:** Grep (unless `type`/`glob` scoped to non-py), Glob (always), Read on `*.py`.
- **Never gated:** non-`.py` Read; anything inside the warm window after a codegraph call.
- **Deny mechanism:** JSON `{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":...}}`. **Not** bare exit-2 (claude-code issue #24327: exit-2 can make Claude halt instead of adapting).
- **Portability guard:** no-op if cwd has no `.codegraph/`; fail OPEN on any error. Safe to ship even globally — only bites in indexed repos.

Reference impl: [`codegraph-gate.py`](./codegraph-gate.py) — verified across 8 branches (cold deny, non-py allow, md-grep allow, post writes state, warm unlock, no-`.codegraph` noop, garbage stdin fail-open).

---

## Two integration paths

### Path A — Quick / literal port (ship the Python script)
Lowest effort, matches what's running in falkor-writ today.
- Ship `codegraph-gate.py` inside the package (e.g. `dist/hooks/`).
- Installer merges two static hook blocks into `settings.json` pointing `python3` at the script's absolute path.
- **Cons:** adds a Python dependency to a Node tool; absolute-path fragility on upgrade/move; second language to maintain.

### Path B — Native subcommand (RECOMMENDED)
Reimplement the gate as a hidden `codegraph tool-gate` subcommand — **exact mirror of the existing `prompt-hook`** (`src/bin/codegraph.ts:1035`), which already reads `{...}` JSON on stdin and is wired into a Claude hook.
- Hook command becomes just `codegraph tool-gate` (same launcher the MCP server uses) — **no separate file, no path resolution, no Python**.
- State + WINDOW logic in TS alongside everything else.
- Installer wires it the same way it already wires `prompt-hook` + MCP + permissions.
- **This is the codegraph-native shape.** Recommend Path B; keep `codegraph-gate.py` as the spec/reference.

---

## TODO — Path B (native)

### 1. Add the `tool-gate` subcommand
- [ ] In `src/bin/codegraph.ts`, add `program.command('tool-gate', { hidden: true })` modeled on `prompt-hook` (line ~1035). Read JSON stdin, dispatch on `hook_event_name`.
- [ ] Kill-switch env var (mirror `CODEGRAPH_NO_PROMPT_HOOK`): e.g. `CODEGRAPH_NO_TOOL_GATE=1` → return immediately.
- [ ] `process.stdin.isTTY` → return (invoked by hand).
- [ ] Port the gate logic from `codegraph-gate.py`:
  - `PostToolUse` + `tool_name` starts `mcp__codegraph__` → write ts to `<root>/.codegraph/.last_graph_use`.
  - `PreToolUse`: compute `gated` (Grep unless non-py scoped; Glob always; Read iff `file_path` ends `.py`). If gated and `now - last > WINDOW` → print deny JSON. Else print nothing.
- [ ] Use the same indexed-root discovery as `prompt-hook` (`isInitialized` walk up ≤6 levels). No `.codegraph/` → return (allow).
- [ ] **Fail open by contract:** wrap in try/catch, always exit 0, never throw into the tool pipeline.
- [ ] Make `WINDOW` configurable (env `CODEGRAPH_TOOL_GATE_WINDOW`, default 300).

### 2. Wire it during install
- [ ] In `src/installer/config-writer.ts` (settings.json path resolved at lines 54–55: global `~/.claude/settings.json`, local `./.claude/settings.json`), add a `writeHooks(loc)` that merges the two blocks below into `settings.json.hooks`. **Merge, don't overwrite** — append to existing `PreToolUse`/`PostToolUse` arrays; dedupe on the command string so re-install is idempotent.
- [ ] Call it from the install flow in `src/installer/index.ts` alongside `writePermissions` / MCP write. Offer it like the git-sync-hook prompt (opt-in, default-yes), so users on shared configs can decline.
- [ ] Uninstall (`src/bin/uninstall.ts` / installer removal): strip the two hook blocks back out, mirroring how MCP/permissions are removed.

### 3. settings.json blocks to merge (Path B form)
```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Grep|Glob|Read",
        "hooks": [
          { "type": "command", "command": "codegraph tool-gate", "timeout": 5 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__codegraph__.*",
        "hooks": [
          { "type": "command", "command": "codegraph tool-gate", "timeout": 5 }
        ]
      }
    ]
  }
}
```
> For a global install, point `command` at the absolute launcher path
> (`~/.codegraph/bin/codegraph tool-gate` or wherever the bundle puts it),
> since `codegraph` may not be on PATH inside the hook subshell.

### State creation
- No migration needed. State file `<root>/.codegraph/.last_graph_use` is created
  lazily by the first `PostToolUse` (codegraph tool) write. `.codegraph/` already
  exists post-`init` and is gitignored. Cold start = no file = gate denies until
  the first codegraph call (correct — that's the point).

---

## TODO — Path A (quick port), if chosen instead
- [ ] Ship `codegraph-gate.py` in the package; resolve its absolute path at install time.
- [ ] Installer merges the same two blocks but with `"command": "python3", "args": ["<abs>/codegraph-gate.py"]`.
- [ ] Document the Python 3 runtime requirement.
- [ ] Same merge/idempotency/uninstall concerns as Path B step 2.

---

## Verification (either path)
Feed simulated hook JSON on stdin and assert:
- [ ] cold (no recent codegraph): Grep / Glob / Read `*.py` → deny JSON on stdout.
- [ ] non-`.py` Read, `type:md` Grep → no output (allow).
- [ ] PostToolUse on `mcp__codegraph__codegraph_explore` → writes/refreshes state file.
- [ ] warm (state ts < WINDOW old): Grep / Read `*.py` → no output (allow).
- [ ] cwd without `.codegraph/` → no output (allow).
- [ ] garbage stdin → exit 0, no output (fail-open).
- [ ] **end-to-end:** real session in an indexed repo — first Grep blocked, `codegraph_explore` then Grep allowed.

## Notes / gotchas
- Hook config loads at **session start** — after install, the user must restart their agent session for the gate to take effect.
- WINDOW tradeoff: one codegraph call unlocks all three tools for the whole window. Lower = stricter (re-codegraph more often); higher = looser. 300s (5 min) is the tested default.
- Don't gate the codegraph tools themselves, and don't gate non-`.py` Read — that's load-bearing for normal config/markdown work (CLAUDE.md decision tree).
- Provenance: `prompt-hook` (`src/bin/codegraph.ts:1035`) is the precedent for a stdin-JSON Claude hook subcommand that's degradable-by-contract; copy its failure discipline verbatim.
