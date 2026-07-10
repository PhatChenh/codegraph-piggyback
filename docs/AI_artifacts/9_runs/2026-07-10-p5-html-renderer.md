# Run report — ssot-diagram P5 interactive HTML renderer (2026-07-10)

Orchestration: `av-orchestrate` skill (Agent Village daemon, minimax worker seats).
Outcome: 11/11 plan steps shipped, merged to main `a51384e` + pushed to origin.
129 pytest pass / 3 pre-existing `TestGoldenLive` pilot-drift (0 NEW). Golden
model sha `56df3d86…` intact. Render E2E = 339KB self-contained, byte-deterministic, zero network.

## 1. Plain summary (for a non-technical reader)

Built the thing a non-coder opens to see what's being built: one clickable HTML
file showing the code's structure + the decisions behind it + whether those
decisions are still valid, all in plain language, kept honest by determinism not
by trusting an AI to update docs. Click a big box → smaller boxes → smallest
boxes; decision status painted on. Opens in any browser, no internet needed.

One AI model (minimax) wrote the genuinely-judgment parts; the orchestrator
(Claude/glm) wrote the verbatim-copy parts and reviewed the hard step itself.
Four worker-shipped test bugs were caught only because the orchestrator ran the
tests itself rather than trusting the worker's report (which had stalled before
it was written). Two tooling gaps in the Agent Village daemon were hit and
logged as bugs, with workarounds that kept the run moving.

**Double-check first:** open the rendered HTML and click around (the interactive
behavior is the one thing not auto-tested); and the 3 pre-existing test fails
are pilot-repo drift, not P5 regressions.

## 2. Dispatch ledger

| # | Model | Role | Task | Outcome |
|---|---|---|---|---|
| 1 | minimax (M3[1m]) | implement | Step 3: render.py CLI plumbing (build_parser/_render_paths/cmd_render/main) | needed-fixes (subparser deviation — orchestrator reverted to subparser-required per §7) |
| 2 | minimax (M3[1m]) | implement | Step 4: render.py INPUT-LOAD (the L7 split) | needed-fixes (config=None bug in A14 branch — orchestrator fixed config-default) |
| — | (glm orchestrator) | implement | Steps 1,2,6,7 (verbatim: fonts, template, escape/font, splice/save) — not a dispatch | — |
| 3 | minimax (M3[1m]) | implement | Step 5: build_viewmodel (L2 trust join) + OTHER-FILE addendum note | pass-first-try (inline glm tier-A review approved; all L2 invariants held) |
| 4 | minimax (M3[1m]) | implement | Step 9: three test fixtures (4 JSON files) | needed-fixes (proposed-entry sig was all-zeros → derived stale not proposed — surfacing as a Step-10 failure) |
| 5 | minimax (M3[1m]) | implement | Step 8: JS painter body (focus views/breadcrumb/stubs/tooltips/legend/theme/pan-zoom) | needed-fixes (first dispatch was a no-op reported ok — session-id masking; re-dispatched) |
| 6 | minimax (M3[1m]) | implement | Step 10: test_render.py (3 goldens + structural + injection + exit + hygiene + scoped + regression) | needed-fixes (4 worker-shipped test bugs — em-dash/middle-dot escape mismatch, self-recursive regression test, missing subprocess timeout, Step-9 sig fallout) |
| 7 | glm (orchestrator) | review | Step 5 inline tier-A review (deepseek-pro av review seat broken per BUG-022) | findings-false-positive (worker code was contract-faithful; 0 defects — the deviation was Step 3's, adjudicated separately) |
| — | (glm orchestrator) | implement | Step 11 manifest — the human:manifest-edit gate (owner sign-off given) | — |

Revived from in-session context. Subagent token counts not surfaced per-session
(Agent Village Block E cost/usage guard is roadmap P3, not yet live — see step 5).

## 3. Decision ledger (autonomous, made without asking the user)

- **Hybrid pacing** — minimax for judgment steps (5/8/9/10), glm orchestrator for
  verbatim-copy steps (1/2/6/7). Rationale: dispatching minimax for a
  verbatim-transcription step then hand-fixing is overhead; reserve the worker
  model for where it earns it. Owner ratified at the pacing question (escalation
  ledger #3).
- **Subparser-required wins** — Step 3's plan self-contradicts (line 676 "bare →
  exit 0" vs line 682 "no-verb → exit 2", same invocation). §7 Implementer Notes
  mandate subparser `required=True` → exit 2. Reverted the worker's flat parser
  to §7's subparser form (matches P4 narrate convention). Escalated to owner
  (escalation #2) → chose (a). Commit `e710502`.
- **Fontsource font sourcing** — plan Step 1 assumed per-weight static `.woff2`
  files at google/fonts `ofl/dmsans`; that path serves only the VARIABLE font
  (DMSans[opsz,wght].ttf, 240KB). Sourced 3 pre-built per-weight woff2 from
  Fontsource (jsdelivr) — no new dependency (no fonttools subsetting), ~42.8KB
  total, wOF2 magic-byte verified. Escalated (escalation #6) → chose Fontsource.
  Commit `8dbb57c`.
- **Inline glm tier-A review** — the av-orchestrate skill mandates a cross-model
  `REVIEW_MODEL` (≠ IMPL) for tier-A steps. The only non-minimax av profile is
  deepseek-pro, but BUG-022 (this repo's own BUGS.md) says deepseek-pro stalls
  on any tool-bearing turn — a review turn reads a diff + writes a review = stall.
  Chose to do the tier-A review inline as the glm orchestrator (distinctness
  holds: minimax ≠ glm; only the av-driven part is lost). Escalated (escalation #4).
- **BUG-023 workaround** — the `av` CLI can't bind a worker to a worktree
  (daemon mints its own session id → staged-cwd pre-write unreachable → worker
  cwd always `profile.worktree`). Repointed minimax profile `worktree` to the
  codegraph repo; accepted sequential-only (no 4-parallel, shared cwd would
  clobber). Logged BUG-023 to `agent_village/BUGS.md`.
- **BUG-024 workaround** — `av verify-wave` category-21 (diff-vs-manifest) is
  whole-plan-scoped, not per-step → mid-multi-wave toll gate can't pass (demands
  symbols from not-yet-run steps). Gated each wave on cat-20 (tests) + cat-22
  (report) + manual per-step symbol check; full toll-gate pass deferred to
  phase-end. Logged BUG-024.
- **Step-9 proposed-sig fix** — the fixture's "proposed" entry had an all-zeros
  stored signature (mismatched the real node sig → derived `stale` not
  `proposed` → no PROPOSED chip in golden#2 → Step-10 chip assertion failed). Set
  stored sig to the node's REAL live sig `2a9436e7…`. Re-pinned
  GOLDEN_WITH_NARR_SHA (`3fc0b624` → `1f6dadf1`). Commit `4114e1a`.

## 4. Escalation ledger (AskUserQuestion / approvals)

1. **Worker path** — flagged minimax-via-av worktree-binding gap + that P3/P4
   shipped via writ:* subagents not av. Chose opt 2: minimax via av, sequential
   only, + log the bug. (Then owner: "log the bug to BUGs/FEEDBACK + go opt 2".)
2. **Step 3 parser shape** — plan self-contradiction (bare exit 0 vs no-verb
   exit 2). Chose (a): subparser required (exit 2 no-verb), matches §7 + P4.
3. **Pacing** — minimax for judgment steps vs all-steps-via-minimax vs drop av.
   Chose hybrid: minimax for judgment, glm for verbatim.
4. **Tier-A review seat** — deepseek-pro broken per BUG-022. Chose (c)/inline:
   glm does tier-A review (distinctness OK; only av-driven part lost).
5. **Gates that pause** — only "new dependency"; manifest gate still honored as
   plan-declared hard gate (deselected from pause-list because the plan冻结 it).
6. **Font source** — google/fonts lacks per-weight woff2. Chose Fontsource.
7. **Step 8 verification** — interactive painter not headlessly assertable. Chose:
   minimax writes, I verify static, owner verifies live at E2E (deferred).
8. **Manifest (Step 11)** — the human:manifest-edit gate. Chose: approve the
   `ssot-render` entry as specified.
9. **Merge** — chose: merge to main locally (option 1) then push (option 2).
10. **Push** — chose: push main to origin now (pushed `a51384e`).

## 5. Cost line

Per-session exact token/cost data is NOT exposed by Agent Village yet (Block E
cost/usage guard = roadmap P3, not live). Best-effort from visible dispatch
counts: 6 minimax dispatches (canary + Steps 3/4/5/8/9/10) over an ~11-step
phase, each a single implement turn (~10k–40k tokens of worker output each).
Estimate **~150–250k tokens across 6 minimax dispatches** (source: dispatch
count + per-turn output size; NOT metered). Band = heavy (7+ dispatches) →
400k–1M; this run was lighter (6 dispatches + orchestrator-authoring) so
~150–250k is plausible, under the heavy band floor.

**~Agent Village observability does not yet exist — when Block E ships, this
cost line should read it instead of best-effort estimates.~** (status unchanged
since the P3 run report.)

## 6. Scoreboard rows

Appended to `docs/model-scoreboard.csv` (this run's dispatches):
- minimax implement rows ×5 (Steps 3/5/8/9/10 — all `needed-fixes` except Step 5
  `pass-first-try`)
- glm orchestrator review ×1 (Step 5 tier-A inline — `findings-false-positive`)
(Step 4 grouped with Step 3's row-family; the Step-4 fix was the orchestrator's
own config-default correction, not a separate dispatch outcome.)

## 7. Verify

- Report: `docs/AI_artifacts/9_runs/2026-07-10-p5-html-renderer.md`
- Scoreboard: `docs/model-scoreboard.csv` (+6 rows through row 14)
- Decisions most worth the user's double-check:
  1. **Subparser-required (decision #2)** — inverted the plan's line 676 ("bare
     → exit 0"); `render.py` now requires the `render` verb (bare exits 2).
     Matches §7 + P4. If you actually wanted bare-to-just-run, this is the call
     to revisit.
  2. **Fontsource not google/fonts (decision #3)** — the plan named google/fonts;
     the vendored binaries came from Fontsource (different source). Provenance is
     in the commit body of `8dbb57c`; OFL license text is canonical from
     google/fonts. Acceptable, but not what the plan literally said.
