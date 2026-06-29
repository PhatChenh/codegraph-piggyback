# codegraph-gate — usage feedback

Friction/bugs found while operating under the CodeGraph-first PreToolUse gate.
Each entry: symptom, why it bites, suggested fix. Newest first.

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
