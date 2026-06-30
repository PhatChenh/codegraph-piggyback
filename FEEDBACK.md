# codegraph-gate — usage feedback

Friction/bugs found while operating under the CodeGraph-first PreToolUse gate.
Each entry: symptom, why it bites, suggested fix. Newest first.

---

## 2026-06-30 — Gate hook command path wrong → every Read crashes (mkt_engine session)

**Symptom:** every `Read` tool call failed with a PreToolUse hook *error* (not the normal
gate block):
```
PreToolUse:Read hook error: [python3 $HOME/01_all_projects/codegraph-piggyback/codegraph-gate/codegraph-gate.py]:
... can't open file '/Users/lap14806/01_all_projects/codegraph-piggyback/codegraph-gate/codegraph-gate.py': [Errno 2] No such file or directory
```
The configured hook command in the project `.claude/settings.json` pointed at
`$HOME/01_all_projects/codegraph-piggyback/...`, but the repo actually lives at
`$HOME/all-projects/codegraph-piggyback/...` (no `01_` prefix). Same wrong prefix on 3 lines:
the `codegraph-gate.py` PreToolUse hooks (×2) and the `ssot-diagram/decision_hook.py` hook.

**Why it bites:** a non-existent script path makes python exit non-zero, which the harness
surfaces as a hook *error* that **blocks the gated tool entirely** — so `Read` was dead for the
whole session. Worse than the intended gate (which blocks with guidance); this is a hard crash
with no codegraph workaround. Editing also breaks downstream: the Edit tool requires a prior
`Read`, so with `Read` crashing, all Edits are blocked too (had to fall back to Bash/python
for every file edit).

**Root cause (verified, not a code bug):** `hook_command()` builds the command from
`ROOT = Path(__file__).resolve().parent` and emits a `$HOME`-relative path — so the path written is
whatever directory piggyback.py lived in at install time. The checkout was at
`$HOME/01_all_projects/codegraph-piggyback/` when these PROJECT-scope hooks were registered, then the
dir was renamed `01_all_projects` → `all-projects`, orphaning the recorded paths. The two sibling hooks
that point at `$HOME/.codegraph-piggyback/codegraph_adoption/...` (the install.sh global-clone convention)
were unaffected — confirming this is a dual-install + post-install rename, not a path-construction bug in
install.sh or piggyback.py.

**Fix (applied host-side):** replaced `$HOME/01_all_projects/` → `$HOME/all-projects/` (3 occurrences)
in the project `.claude/settings.json`; JSON re-validated; both target scripts confirmed present
+ `py_compile`-clean. Takes effect next session (hooks load at session start).

**Fix IMPLEMENTED (2026-06-30):** root of why `update` didn't already self-heal — `reconcile()` only
removes hooks `is_owned()` recognizes, and `is_owned()` matches the *current* ROOT only, so a hook left
behind by a checkout rename (old root) is invisible to reconcile and survives. Added `is_dead_ours(cmd)`:
a hook that runs one of our scripts (manifest basename, or a path under `codegraph-piggyback` /
`codegraph_adoption`) **whose target file is missing on disk**. `reconcile()` now prunes those too:
`stale = (is_owned and not desired) or is_dead_ours`. Keyed on *file missing*, not *current root*, so:
(a) a rename/move auto-heals on the next `piggyback update`/`install`/`init` (reconcile prunes the dead
entry, the manifest re-adds the correct current-ROOT one), and (b) valid hooks — including a different
legit install root like `~/.codegraph-piggyback` whose files exist — are never touched. Verified against
5 path cases (stale-missing → pruned; both live roots + unrelated user hook → kept).

---

## 2026-06-29 — Iris Phase 6 orchestration (Claude reviewing deepseek-implemented code across git worktrees)

**Overall:** codegraph itself (the `explore`/`node` MCP tools) was the highest-value tool of the session — one `codegraph_explore` returned verbatim source + blast radius (callers/tests) and replaced large amounts of file reading; per-worktree indexing (`init` the integration worktree, `sync` after each merge) worked exactly as documented. The friction below is entirely about the **gate hook**, not the index.

### G1 — The 5-minute gate fights the read→edit loop

**Symptom:** the gate blocks the `Read` tool with "CodeGraph-first gate: … no codegraph tool has run in the last 5 min. Run codegraph_explore/codegraph_node BEFORE Read." It fires even when:
- I just want a specific line range to set up an `Edit` (I already know the symbol; I don't need discovery), and
- a codegraph call moments earlier **already returned that exact file's source** — the gate still blocks the follow-up `Read` because the 5-min window lapsed or a different tool ran in between.

During an edit-heavy stretch (reviewing + patching ~8 files), the window kept lapsing mid-session, so almost every `Read` had to be preceded by a throwaway `codegraph_node` call purely to re-open the gate.

**Why it bites:** the gate's intent (don't grep/read when codegraph would answer better) is right for *discovery*, but it also taxes the *edit* phase, where a precise `Read` of a known range is the correct tool and codegraph is the detour.

**Suggested fix:**
- Exempt a `Read` of a file whose source a codegraph call returned within the window (track "files codegraph has shown" and let those through without re-priming).
- Exempt a `Read` of a file **immediately after an `Edit`/`Write` to that same file** (you're verifying your own change, not exploring).
- Consider widening the window or resetting it on any codegraph call rather than expiring on wall-clock.

### G2 — A codegraph "read" doesn't satisfy the Edit tool's separate "must Read first" requirement → forced double-reads

**Symptom:** to edit a file I must (a) run a codegraph call to pass the gate, then (b) still call the actual `Read` tool, because the Edit tool independently requires "the file has been read with the Read tool in this conversation" — a `codegraph_node` file-read does not count. So a single edit needs: codegraph call (to pass the gate) → `Read` (to satisfy Edit) → `Edit`. Two reads of the same bytes for one edit.

**Why it bites:** the two gates don't recognize each other. The codegraph gate pushes you toward codegraph; the Edit precondition pushes you back to `Read`; neither accepts the other's read.

**Suggested fix:** have `codegraph_node` file-mode (which returns the same line-numbered source as `Read`) mark the file as "read" for the Edit-tool precondition, or have the gate let a post-codegraph `Read` through cheaply so the double-read is at least gate-free. Either removes the redundant round-trip.

### Not a gate bug (cross-reference)
The deeper "codegraph index is blind inside orchestration worktrees" issue (index lives at the main repo root; `git worktree add` trees have none) is documented separately in `deepseek-bridge/BUGS.md` BUG-013 and was resolved host-side by indexing the integration worktree. Listed here only so the two reports cross-link.

---

## Resolution — 2026-06-29

G1 and the hook-fixable half of G2 are addressed in `codegraph-gate/codegraph-gate.py`
(+ `manifest.json` gains an `Edit|Write` PostToolUse matcher). Regression tests in
`codegraph-gate/test_codegraph_gate.py`.

**What changed:**
- PostToolUse now records per-file state: `.gate_shown` (from `codegraph_node`
  file-mode) and `.gate_edited` (from `Edit`/`Write`), under `<cwd>/.codegraph/`.
- PreToolUse `Read` is exempt for a file in `.gate_shown` within `SHOW_TTL`
  (default 1800s, env `CODEGRAPH_GATE_SHOW_TTL`) or in `.gate_edited` within
  `EDIT_TTL` (default 300s, env `CODEGRAPH_GATE_EDIT_TTL`). Matches on exact path
  OR basename (codegraph_node may pass a basename).
- The global `WINDOW` unlock (300s, env `CODEGRAPH_GATE_WINDOW`) and Grep/Glob
  behavior are unchanged.

**G1 (window lapses mid edit-loop):** fixed. A file codegraph_node already
returned, or one you just edited, can be `Read` without re-priming the gate —
the throwaway `codegraph_node` purely to reopen the gate is gone.

**G2 (codegraph read ≠ Edit's "must Read first"):** *partially* fixed, and the
unfixable part is a harness limitation, not a gate bug. The hook **cannot** mark
a file as "read" for the Edit tool's own precondition — that file-state is
harness-internal and only the real `Read` tool updates it. So the
codegraph→`Read` round-trip before `Edit` is inherent. What the hook now stops
doing is *forcing an extra codegraph call* just to satisfy the gate: after a
`codegraph_node`, the follow-up `Read` passes gate-free. The remaining
double-read is one Read (Edit precondition), not two-plus-a-codegraph-call.

**Not changed (intentional):** Grep/Glob stay gated by the global window only —
they are exploration, not edit-phase detail reads.
