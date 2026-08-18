## 2026-08-18 — Cursor session said codegraph inactive while `.codegraph/` exists (codegraph-piggyback, run-id 2026-08-18-bkt3-plan-verify)
**Seat:** ORCH first-hand (Cursor Grok 4.6)
**Category:** confusing
**Symptom:** MCP meta said “workspace not indexed (no `.codegraph/` directory)” this session. The directory is present (`ls .codegraph` ok; `plan_verify` found the db).
**Why it bites:** R12 tells agents to use codegraph first; they skip it and grep. Workers were told to Read/Grep as fallback.
**Suggested fix:** Cursor MCP `user-codegraph` should detect an existing `.codegraph/` in the workspace root, or the session start hook should not claim “no index.”
**Run-report:** `docs/AI_artifacts/9_runs/2026-08-18-bkt3-plan-verify.md`

## 2026-08-17 — ACP report sentinel fenced + 32k briefs + dual `.village/` trees (bkt4-codegraph-cli, run-id 2026-08-17-bkt4-codegraph-cli)
**Status:** ACCEPTED process
**Seat:** ORCH first-hand (Cursor Grok 4.6) · impl `822f1d33` (clx-deepseek-v4-pro) · judge `df93a896` · daemon `orch-bkt4-cg-cli` :19817
**Category:** burden
**Symptom:** DeepSeek FIX 1 wrote a correct disk report but wrapped `=== END REPORT ===` in a markdown fence in the ACP reply → verify-wave check 4 category 22. Same run: cmd-pro 32k `contextGate` + 10min wall; Step 5 `Prompt is too long`; judge stamps first landed in repo-root `.village/runs/` not the worktree channel.
**Why it bites:** gate red after green tests; extra exemption; wasted impl tokens on oversized briefs.
**Burden:**
- `=== END REPORT ===` must be unfenced last line of the **reply** and of WT-root `IMPLEMENTATION_REPORT.md`
- `av preflight --brief` is basename-under-cwd; turn needs `--overwrite-brief`
- clx `contextGate` 32000 with ~20k bootstrap → tiny briefs
- two trees share run-id path names: INT WT `.village/` vs parent checkout `.village/`
- sibling SIDs on one git common-dir need `reportExempt` + `exemptionAudit`
- pin `VILLAGE_PORT=19817`; never 8877
**Suggested fix:** (av) reject fenced sentinel as “found in fence, not last line”. (skill) worker-task.md: report lives at WT root, never `codegraph/IMPLEMENTATION_REPORT.md`. (ORCH) copy judge briefs into the WT that will be read.
**Run-report:** `docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.md`

## 2026-08-16 — Bucket 1 ACP CodeGraph live cert PASS (codegraph-piggyback, run-id bkt1-acp-livecert)
**Status:** LIVE-VERIFIED (source uncommitted in agent_village)
**Seat:** ORCH first-hand · `cursor-composer` SID `3927783f-11c7-4dee-8c01-6d1cd9391b58` · private daemon `bkt1-acp-livecert` :19701 pid 61207
**Category:** none
**Symptom:** n/a — cert of 08-14 `${workspaceFolder}` class. Staged worktree `.cursor/mcp.json` `--path` = absolute session cwd (not placeholder, not `profile.worktree`). One MCP `codegraph_explore` auto-allowed, `av turn` exit 0, worker `MCP_OK` + 188-symbol explore body. No exit 6.
**Run-report:** `docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/verdict.md`

## 2026-08-16 — `av preflight --brief` uses basename only; first `av turn --brief` refuses after preflight staged it (feedback-scope-scout, run-id 2026-08-16-feedback-scope-scout)
**Status:** OPEN
**Seat:** ORCH first-hand (Cursor Grok 4.6) · SID `76933935-f63c-4520-b008-fc11fc9b04c7` · profile `clx-deepseek-v4-pro` · daemon `orch-feedback-scope-scout` :19341
**Category:** burden
**Symptom:** `av preflight --session … --brief .village/runs/…/channel/SCOUT.md` → exit 24 `brief_unresolved: SCOUT.md not found under effective cwd` (basename lookup, path ignored). Copy to `$PWD/SCOUT.md` → preflight ok. Immediately `av turn --brief SCOUT.md` → `bad_request` `brief refused: SCOUT.md already exists (pass overwrite:true to replace)` because preflight had staged it. Needed `--overwrite-brief`. Turn then ok=true ~319s, digest 15KB, `spentTokens` 118943 (`usageSeen: true`). Harness `Task` subagents aborted; operator required `av` + private daemon.
**Why it bites:** two dispatch failures before any worker token; easy to think the session is broken. Copying a brief to repo root also leaves a dirty `SCOUT.md`.
**Burden:**
- `av preflight --brief` matches **basename under cwd**, not the path you passed
- preflight that succeeds **stages** the brief, so the following `av turn --brief` needs `--overwrite-brief`
- pin `VILLAGE_PORT` to the daemon you started; never 8877 when other orch villages are live
- clx `contextGate` 32000 with `bootstrapTokens` 20000 leaves ~7k for brief+repo; keep briefs tiny
**Suggested fix:** (av) preflight `--brief` should resolve the given relative path, or print “need basename at cwd”. (av) first turn after a successful preflight should not require overwrite, or preflight should be read-only. (skill) av-use: “preflight then turn” recipe with `--overwrite-brief`.
**Run-report:** `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## 2026-08-15 — blast-gate Write deny `found: {none}` while `.codegraph/codegraph.db` exists (mkt_engine, post-return p18-lite-part1)
**Seat:** ORCH first-hand (Cursor Grok 4.6 Desktop)
**Category:** bug
**Symptom:** Writ blast-gate **denied** `StrReplace`/`Write` on a village worktree `.tsx` with `unrecognized schema version (found: {none}; reader supports: {1, 5})`. `{none}` is writ `codegraph_index.probe` when `SELECT version FROM schema_versions` raises (empty found set), **not** an unknown integer version. Cursor workspace was `mkt_engine` **main**; the file lived in `.village/worktrees/p18-lite-part1`. That worktree already had `.codegraph/codegraph.db` (~19MB) + idle-killed daemon.log. `writ` not on PATH. `writ codegraph-init -f` rejected `-f`. `codegraph init` printed **Already initialized**. `codegraph index` in the worktree made probe `usable`; writes then passed. Main checkout also had a live `codegraph serve --mcp` + 295MB db + WAL. Session hook warned DEPLOY DRIFT (hooks from a different village worktree). Distinct from 2026-07-22 silent-empty MCP, 2026-07-23 verify-wave init-no-reindex, 2026-08-14 `${workspaceFolder}`.
**Why it bites:** fail-closed blocks all product-code edits in a worktree until a human guesses `codegraph index`. The named fix (`writ codegraph-init`) no-ops.
**Suggested fix:** (codegraph) if the db file exists but `schema_versions` is missing/unreadable (WAL/ro, pre-schema db), fail loud with `index_unreadable` + “run `codegraph index` in this worktree”, never a fake schema `{none}`. (writ) map that state to the `missing`/`stale` deny copy, and make `writ codegraph-init` call `codegraph index` when already initialized. Do not treat sqlite errors as “unknown schema version.”
**Product:** mkt_engine P18 lite Part 1 post-return (Kiểm tra lại drop); no new 9_runs file.

## 2026-08-15 — --allow glob `[id]` is a fnmatch char class (mkt_engine run, run-id 2026-08-15-p18-lite-part1-impl)
**Seat:** ORCH first-hand
**Category:** confusing
**Symptom:** `.av-verify.json` allow `app/api/assets/[id]/route.ts` did not admit the changed Next dynamic-segment file. `fnmatch` treats `[id]` as one of `{i,d}`. Workaround: `app/api/assets/*/route.ts`.
**Why it bites:** verify-wave 21 OUT-OF-SCOPE-TOUCH on a file the plan named; extra judge/allow round.
**Suggested fix:** document that Next `[id]` paths must be written `[[]id]` or `*` in `--allow`; or escape brackets in allow matching.
**Product report:** `mkt_engine/docs/AI_artifacts/9_runs/2026-08-15-p18-lite-part1-impl.md`

## 2026-08-12 — grep-absent on directory path passes vacuously (mkt_engine run, run-id 2026-08-12-p17-w4b-ref-tags-ui)
**Seat:** worker-observed (via av turn / judge)
**Category:** bug
**Symptom:** `grep-absent "LoRA" components/refs/` resolves the directory; `f.is_file()` filters it out → 0 files scanned → qualifier always None/pass.
**Why it bites:** plan's only mechanical PROJ-MODELPICK-001 guard was a no-op until rewritten to `components/refs/*.ts*`.
**Suggested fix:** treat directory globs as error (or expand to children) instead of vacuous pass; document that qualifiers must name files/`*.ext`.


## 2026-08-09 — plan_verify Prisma schema touch still unindexed (mkt_engine run, run-id 2026-08-09-p17-w2-asset-page)
**Seat:** ORCH first-hand
**Category:** bug | enhancement
**Symptom:** `touch: prisma/schema.prisma` and `touch: prisma/schema.prisma::Asset` both MISSING under `--strict` — Prisma schema not in codegraph index. Same class as prior non-Python path bug. REUSE-DROPPED for `runFalQueue(...)` until plan Facts cited the live `_shared.ts` symbol (spec path `fal/queue.ts` stale).
**Why it bites:** ORCH hand-patches every Prisma plan step; planners copy W1 waiver prose and still FAIL until touch dropped.
**Suggested fix:** filesystem `stat` fallback for `touch:`/`new:` paths; teach REUSE matcher to accept Facts cites of relocated symbols.
**Product report:** `mkt_engine/docs/AI_artifacts/9_runs/2026-08-09-p17-w2-asset-page.md`

## 2026-08-07 — plan_verify swept MISSING on prose / cross-repo tokens (agent_village run, run-id 2026-08-07-a6-work-mode-tdd)
**Seat:** ORCH first-hand
**Category:** enhancement · confusing
**Symptom:**  PASS on manifests, but Tier-2 sweep floods MISSING for English words (, , ) and cross-repo paths not in this repo's codegraph index. Noise rate high enough ORCH must ignore swept lines.
**Why it bites:** trains ignore-the-sweep reflex; hard to spot real ghosts.
**Suggested fix:**  / suppress prose tokens; or scope sweep to / symbols only when .

## 2026-08-14 — ACP/village MCP `codegraph_explore` returns no body; `--path ${workspaceFolder}` literal; exit 6 (mkt_engine, run-id 2026-08-14-p17.5-collected-edit)
**Status:** OPEN
**Seat:** ORCH first-hand (Cursor Grok 4.6 Desktop) · village `p17.5-collected-edit-orch` `:19781` · grok-46 SIDs `0f7f379e` / `133760bf` / `f98be08a` (all `non_convergence` exit 6)
**Category:** bug
**Symptom:** CLI `codegraph explore "AssetDetail isOwner …"` from `mkt_engine` returns ~25k of real source. Same query via Cursor ACP MCP `codegraph_explore` on three fresh grok-46 sessions: 5× `session/request_permission` (auto-allowed), **zero completed MCP `rawOutput`**. Grok thought “The codegraph output was truncated,” retried, village loop-breaker: `repeat-threshold after 5 progress-free events (last command: mcp__codegraph__codegraph_explore)`. Live processes on this host include `codegraph serve --mcp --path ${workspaceFolder}` — **placeholder not expanded**. This Desktop session’s CodeGraph MCP stayed `serverStatus: loading` / “no callable tools.” Index daemon log: idle/inactivity backstop restarts (even with `clients=4`); no error lines. Village writer: `agent_village/daemon/cursor-bundle.ts` `buildVillageMcpConfig()` args `"--path","${workspaceFolder}"` (Desktop substitution; ACP does not expand). ADR-0015: MCP cannot ride `session/new mcpServers` — delivery is `.cursor/mcp.json`.
**Why it bites:** Strong RT cannot finish on grok-46 if R12/skills say CodeGraph first. Three SIDs + one daemon bounce burned; no report file. Workaround this run: forbid CodeGraph MCP/CLI; Read named files.
**Suggested fix:** (codegraph) reject or resolve a literal `${workspaceFolder}` instead of indexing a garbage path; fail loud on MCP if the daemon is loading/idle-killing under clients. (village) write an **absolute** `--path <worktree cwd>` into staged `.cursor/mcp.json` for ACP; keep `${workspaceFolder}` only for Desktop. (skill) Cursor ACP briefs: CodeGraph MCP cap 0–1 then Read; do not treat R12 as load-bearing on ACP.
**Run-report:** `mkt_engine/docs/AI_artifacts/9_runs/2026-08-14-p17.5-collected-edit.state.md`

# codegraph-gate — usage feedback

## 2026-08-06 — plan_verify `--strict` MISSING on existing non-Python `touch:` paths (falkor-writ run, run-id c11-c16-inference-gates)
**Seat:** ORCH first-hand + worker-observed (via av turn)
**Category:** bug
**Symptom:** `plan_verify.py --strict` exit 1 with 4 `touch:` MISSING rows for `hooks/hooks.json` and three `integrated_skills/build-pipeline/handoffs/*.md` files that **exist on disk** (`[ -f ]` true). Codegraph’s Python-only index cannot see them; verifier does not fall back to a filesystem stat for non-indexed paths. Swept prose tokens also flood MISSING.
**Why it bites:** Orchestrators must manually cross-check FAIL before re-dispatching planners; workers burn turns documenting a tooling blind spot; exit 1 cannot mean “ghost” vs “unindexed but real.”
**Suggested fix:** For `touch:`/`new:` file paths, `stat` the filesystem when the index has no node; reserve MISSING for true absence. Optionally silence or demote `swept` prose tokens under `--strict`.

## 2026-07-26 — plan-verify unrecognised `files:` key → empty files[] (td-avdispatch)
**Seat:** ORCH first-hand (pipeline then impl)
**Category:** tool-bug / process
**Symptom:** Plan steps used `files:` YAML lists. Parser (`_shared/manifest.py`) only accepts `touch|new|remove|tier|gates|qualifiers`, so `files[]` empty for 16 steps. Floor lint + out-of-scope-touch passed vacuously. Five red-team rounds never ran the parser.
**Why it bites:** Compliance gates look green while switched off.
**Suggested fix:** (a) reject unknown keys loud; (b) refuse empty `files[]` in verify-wave preflight; (c) build-pipeline hard-gate `diff_verify.py --per-step` before first red-team (owner Q6-a 2026-07-26).

## 2026-07-23 — verify-wave literal backslash-pipe + stale worktree index (Iris run, run-id p8-slice-bc)
**Seat:** ORCH first-hand
**Category:** confusing
**Symptom:** (1) Plan qualifiers grep-present with a\|b require literal backslash+pipe on disk; workers write real pipe or double-backslash in normal docstrings and fail category 21. (2) av verify-wave auto-heal codegraph init -i does not reindex; NOT-DELIVERED until manual codegraph index in the task worktree.
**Why it bites:** Extra fix rounds on every Slice B/C step; false NOT-DELIVERED after green tests.
**Suggested fix:** Document literal backslash-pipe marker recipe in verify skill; auto-heal should codegraph index (or sync) not only init; optional normalize a|b as OR in qualifier parser.


## 2026-07-23 — plan_verify REUSE-DROPPED needs exact unicode name (Iris run, run-id p8-slice-bc)
**Seat:** ORCH first-hand
**Category:** confusing
**Symptom:** Spec reuse row ``claim_one(stage=…)`` (unicode ellipsis) stayed REUSE-DROPPED after plan cited `claim_one` / `claim_one(stage='process')` / `ingestion/queue.py` heavily — matcher requires exact name substring or full weird path cell.
**Why it bites:** False warn after a correct reuse citation; forced a second AV turn + surgical token patch.
**Suggested fix:** Normalize reuse names (strip `(…)` / ascii-fold ellipsis) or also match leading identifier before `(`.

Friction/bugs found while operating under the CodeGraph-first PreToolUse gate.
Each entry: symptom, why it bites, suggested fix. Newest first.

---

## 2026-07-22 — Empty/uninitialized index returns silently empty (agent_village UX batch item 3)

**Source:** agent_village improve-batch
(`docs/AI_artifacts/0_draft/next-improve-batch-av-village-ux.md` item 3);
cross-project friction from mkt_engine tooluse runs driving village workers.
Filed here (not agent_village) — symptom is codegraph MCP/index, not village.

**Symptom:** `codegraph_explore` (and siblings) on a worktree with no
`.codegraph/db`, or an empty/uninitialized index, returns **silently empty**
instead of a clear warning. Worker loops forever retrying query variants
with zero signal that the index itself is the problem.

**Why it bites:** agent treats empty as “wrong query,” not “no index.” Burns
turns; masks the real fix (`codegraph init` / wait for index). Distinct from
agent_village’s cwd-trust `codegraphIndexTrusted` security precondition
(already shipped) — this is **emptiness detection**, not path-escape.

**Suggested fix:** when index missing or zero symbols, return an explicit
error/warning payload (e.g. `index_empty` / `index_missing`) with remediation
(`codegraph init` in this worktree), never a bare empty success.

**Status:** OPEN (feedback only; not yet implemented).

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
