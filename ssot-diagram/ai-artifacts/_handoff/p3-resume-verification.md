# P3 — resume at factual-code-verification (SUPERSEDED 2026-07-04)

> **SUPERSEDED.** The factual-code-verification + plan steps are now DONE (0
> invalidated). **The current pick-up point is `STATE.md` at the repo root** — read
> that instead. This file is kept as a historical record.

Fresh-session handoff for the P3 ssot-diagram extractor build-pipeline.
Detailed state lives in `p3-pipeline-state.md` (same dir) — read it for the 6
grill contracts, 5 red-team fixes, and the full resume-point dispatch prompt.

## Goal

Dispatch the **factual-code-verification** subagent (the correctness boundary
of the pipeline) to verify the spec's 25 assumptions (A1-A25) against the real
codegraph DB + `decision_index.py` source. Run it on **GLM-5.2, max effort**.
If all validated → dispatch plan step. If any invalidated → loop-back per
build-pipeline SKILL.md (cap 2 auto cycles, escalate on type-c/regression).

## Read First

- `CLAUDE.md` (repo root) — esp §3 scope, §7 no-unread-code, §9 no private memory
- `ai-artifacts/_handoff/p3-pipeline-state.md` — full pipeline state + resume-point dispatch prompt
- `ai-artifacts/2_specs/p3-diagram-model-extractor.md` — the spec to verify (1076 lines, 14 components, 25 assumptions A1-A25)
- `ai-artifacts/1_design/p3-diagram-model-extractor.md` — design (1330 lines, revised post-red-team)
- `adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` — ADR
- `../docs/roadmap/skeleton-contracts.md` — Block 1e + Block 4 frozen contracts

## State

- Pipeline: `/build-pipeline`, medium tier (design-lite → spec → verify → plan).
- Phase -2 (scout), Phase -1 (grill, 6 contracts locked), design (written + red-teamed, 5 fixes applied), ADR-0001 (written), spec (written) — all DONE.
- **Now:** factual-code-verification step, NOT yet dispatched.
- Codegraph: ✅ online — daemon sock listening, hooks wired (codegraph-gate.py + decision_hook.py), file watcher active.
- Writ: ❌ daemon down (port 9130 unreachable, `writ-mode-set` read-back = `<none>`, `writ-project-rules.sh list` throws). **Verify is read-only → no writ dependency** (writ work-gate only matters at plan→implement). Re-check writ before plan step.
- Pilot repo: `~/all-projects/mkt_engine` — `.codegraph/codegraph.db` (read-only `mode=ro&immutable=1`) + `docs/decision-index.json` (8 ADRs, 33 anchors, ALL verified, ALL FRESH — P2 LANDED 2026-07-04).

## Next Steps

1. **Dispatch factual-code-verification subagent on GLM-5.2 max effort.** Use the `factual-code-verification` dispatch template in `~/.claude/skills/build-pipeline/SKILL.md`. Inputs: spec + design + ADR + repo root + pilot DB/index paths (full prompt ready in `p3-pipeline-state.md` → "Resume point"). Set subagent `model: opus` is wrong — use GLM-5.2 max effort if the harness supports it, else strongest available; the user explicitly asked for GLM-5.2 max. CodeGraph-first for all code reads.
2. Verify all 25 assumptions at the depth each claim requires (behavior claims = behavior reading, NOT signature grep). Distrust spec's "pre-validated" labels. The 5 red-team fixes (A13-A17) are load-bearing — verify each.
3. Output to `ai-artifacts/3_factual-code-verification/p3-diagram-model-extractor.md` (Spec Verification table + Invalidated Assumptions section if any).
4. Return counts: validated / invalidated / unverifiable + list any invalidated IDs.
5. Review gate: if any invalidated → loop-back (cap 2; escalate on type-c/regression). If all validated → phase-transition gate to plan step.
6. **Before plan step:** re-check writ daemon (port 9130). Plan step itself is read-only (no writ dependency), but implement step after it WILL need writ work mode. Surface writ status to user at plan gate.

## Open Items

- Writ daemon down — re-check before plan step; if still down at implement time, blocks the work-gate.
- `2_specs/` vs `4_specs/` folder name: build-pipeline spec skill mentions a rename convention; spec wrote to `2_specs/` per task override. Non-blocking; do not migrate mid-pipeline.
- Private memory file `parallel-phase-ab-split.md` still has stale "0/25 verified" framing — superseded by handoff + design's verified live state. Don't trust the memory file's P2-state claim; re-verify the live index each session (§9: don't write to private memory going forward).

## Files Touched (this session)

- `ai-artifacts/0_scout/macro-component-grouping-prior-art.md` (new)
- `ai-artifacts/1_design/p3-diagram-model-extractor.md` (new, revised post-red-team)
- `ai-artifacts/2_specs/p3-diagram-model-extractor.md` (new)
- `adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` (new)
- `ai-artifacts/_handoff/p3-pipeline-state.md` (new, updated to resume-point)
- `ai-artifacts/_handoff/p3-resume-verification.md` (this file)
- `CONTEXT.md` (new, glossary — by design subagent)

## Suggested Skills

- `build-pipeline` — the orchestrator wrapping the remaining steps (verify → plan).
- `factual-code-verification` — the skill the verify subagent reads by path (do NOT re-derive; dispatch the subagent per SKILL.md template).
- `plan-from-specs` — after verify passes, dispatch per SKILL.md plan template (standard mode).
- `code-review` / `red-team-review` — optional, if you want a second adversarial pass on the spec before verify (not required — design already red-teamed).
