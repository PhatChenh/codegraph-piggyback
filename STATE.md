# STATE.md — codegraph-piggyback

> **Pick-up point for the next AI session.** Read this first, then the files it
> names. Last updated 2026-07-04.

## What is happening right now

**Phase A — ssot P3 diagram-model extractor.** Code implementation is the next
action. The `/build-pipeline` (medium tier) run is COMPLETE through its five steps
(design → red-team → spec → factual-code-verification → plan). The plan is approved
and on disk. **No code has been written yet** for P3.

## One-paragraph orientation

P3 builds one deterministic script `ssot-diagram/graph_model.py` that reads the
codegraph DB (read-only) + the curated decision index + a config, and emits one
`diagram-model.json` (3-level: macro components → micro files/classes → nano
functions, with rolled-up edges, decision nodes from verified anchors, and a content
signature on every node). Same inputs ⇒ byte-identical JSON. No LLM in any verdict.
Ships via `manifest.json`, CLI-first. P2 (the curated index it depends on) LANDED
2026-07-04.

## Pipeline state (all DONE — these are inputs to the implement step)

| Step | Artifact | Status |
|---|---|---|
| design | `docs/AI_artifacts/1_design/p3-diagram-model-extractor.md` | ✅ written, revised post-red-team |
| red-team | (5 fixes folded into design as A13–A17) | ✅ 5 fixes applied |
| spec | `docs/AI_artifacts/2_specs/p3-diagram-model-extractor.md` | ✅ written (14 components, 25 assumptions A1–A25) |
| factual-code-verification | `docs/AI_artifacts/3_factual-code-verification/p3-diagram-model-extractor.md` | ✅ 23 valid / 0 invalidated / 2 unverifiable-non-blocking; A13–A17 each verified |
| ADR | `docs/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` | ✅ written |
| plan | `docs/AI_artifacts/4_plans/p3-diagram-model-extractor.md` | ✅ written (1484 lines, 14 Steps) |

## NEXT: implement P3 (`ssot-diagram/graph_model.py`)

**Read these first (in order):**
1. `docs/AI_artifacts/4_plans/p3-diagram-model-extractor.md` — the plan, 14 Steps.
   This is the primary work document. Follow it.
2. `docs/AI_artifacts/3_factual-code-verification/p3-diagram-model-extractor.md` —
   the verified facts. Trust this over the spec on any discrepancy (it was checked
   against live code/DB; the spec was not).
3. `docs/AI_artifacts/2_specs/p3-diagram-model-extractor.md` — the spec (component
   decomposition, 25 assumptions).
4. `docs/AI_artifacts/1_design/p3-diagram-model-extractor.md` — the design (options,
   chosen approach, risks).
5. `docs/roadmap/skeleton-contracts.md` — the 5 FROZEN cross-phase contracts. Do NOT
   re-litigate.
6. `CLAUDE.md` (repo root) — project rules. Especially: never write to
   `.codegraph/codegraph.db` (connect `mode=ro`); every tool registers in
   `manifest.json`; CLIs run standalone; signatures pin all persisted LLM output.

**Reference implementation to build against (P1, shipped — reuse, don't reimplement):**
- `ssot-diagram/decision_index.py` — P1 engine. P3 reuses `die()` (note: exits 2),
  `save_index` atomicity pattern (temp + `os.replace`, lines 175–179), `verify_schema`
  (P3 extends it — see carry-forward #5 below), signature recipe.
- `_shared/` — `db.py` (mode=ro), `sig.py` (sha256 of source slice), `resolve.py`,
  `queries.py`, `budget.py`, `hookio.py`. **Deferring `_shared/` extraction to Phase B**
  per ADR-0001 — P3 sibling-imports `decision_index.py` across the leading underscore
  for now (the off-limits set in the plan's `## Delegation Authority` enforces the
  convention).

**Pilot repo (the seed for golden tests):**
- DB (read-only, `mode=ro&immutable=1`): `~/all-projects/mkt_engine/.codegraph/codegraph.db`
- Curated index (P2 LANDED): `~/all-projects/mkt_engine/docs/decision-index.json` —
  8 ADRs (ADR-0001..ADR-0008), 33 anchors, all `verified:true`, all FRESH.

## Carry-forward facts the verify step confirmed (integrate into implementation)

1. **A1 nuance — `nodes.id` has two forms.** 226/232 function nodes have
   `function:<32-hex>` content-hash ids; 6 React-hook nodes have
   `hook:<path>:<name>:<line>` path-derived ids. The spec's "synthesize your own id;
   never pass `nodes.id` through" is correct for BOTH forms. **Add a code comment
   forbidding dispatch-on-source-id.** (Only the rationale "one-line edit changes it"
   over-claims for the hook case.)
2. **E1 RESOLVED (planner decision) — exit code 2, not 1.** P3 mirrors P1's `die()`
   (exits 2 at `decision_index.py:372–374`). P3 reuses `die()` verbatim for fail-loud
   paths, so exit 2 is inherited automatically. A divergent exit 1 would require P3
   to write its own `die()` for the same failure — that is the inconsistency.
3. **Component 8 pin — `edges.line`** is 100% populated for
   calls/imports/references/instantiates/implements; 0% for `contains` (which P3 does
   not read as an edge). Plan: "always read `line`; null only for `contains` (unused)."
4. **Component 12 atomicity — inherit P1's pattern.** `save_index`
   (`decision_index.py:175–179`) already does atomic temp + `os.replace`. Do not leave
   atomicity open.
5. **R4 extended schema guard REQUIRED.** P1's `verify_schema` checks only 5 nodes
   cols + 2 files cols; the extra cols P3 reads (`kind`, `id`, `docstring`,
   `is_exported`, `signature`, all `edges.*`) are unguarded by P1. The spec's
   component-4 extended guard is justified — implement it.

## OPEN human-authority items (deferred — surface, do not decide silently)

These are carried into the plan's `## Open Questions`. They do NOT block
implementation.
- **OQ-FOLDER-001 (product-identity):** repo is on the legacy folder scheme
  (`0_scout/1_design/2_specs/3_factual-code-verification/4_plans/`). The DOC-ARTIFACT-001
  rule wants the new scheme (`0_draft/1_scout/2_ux/3_design/4_specs/5_factual-code-verification/6_plans/…`).
  Migration deferred to post-pipeline — do NOT migrate mid-implement.
- **OQ-A18 (scope):** Windows backslash-path generalization — unverifiable from one
  DB; non-blocking under contract C1 (pilot = mkt_engine, a Unix repo).
- **OQ-A24 (operating-burden):** whether CI has the pilot DB checked out. The
  `extract` CLI must skip-if-absent (warn, not fail) so this stays non-blocking.

## Tools (verified online 2026-07-04)

- CodeGraph: ✅ online. CLI at `codegraph` (nvm bin); repo has `.codegraph/`; file
  watcher + hooks active (`codegraph-gate.py`, `decision_hook.py`). Use codegraph
  MCP tools (`codegraph_explore`/`codegraph_node`/`codegraph_callers`) or the shell CLI
  as the primary explore tool. Never write to the DB.
- Writ daemon: ✅ up (port 9130). Set writ mode to `work` before implementing:
  `/Users/phatchenh/.cache/writ/.venv/bin/python /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/writ-session.py mode set work <session-id>`.
  The implement step needs writ work-mode for the work-gate.
- Subagent casting rule (CLAUDE.md §10): `general-purpose`/`claude`/omitted
  subagent_type are BLOCKED (hook bounce). Cast a leaf: writes → `writ:worker` or
  `writ:writ-implementer` (plan-driven); read-only → `writ:writ-explorer`/`Explore`;
  review → `writ:writ-plan-reviewer` then `writ:writ-code-quality-reviewer`.

## Verify command (the proof the implement step is done)

After implementing, run:
```sh
python3 ssot-diagram/graph_model.py extract        # on the mkt_engine seed
python3 -m pytest ssot-diagram/                      # golden + 5 red-team regressions
```
**Pass = every step passes AND observed signals:**
- Re-running `extract` produces byte-identical `diagram-model.json` (determinism).
- Every verified anchor appears exactly once (decision-node merge).
- Nano-cap collapse produces `+K more` synthetic nodes (not silent truncation).
- `sample_callers` top-3 is stable across runs (file:line ascending tiebreak).
- Pre-extract guard prints a stderr warning (exit 0, not a hard fail) on a
  stale-or-unverified index — warn-and-continue per contract 5 FROZEN.
- `decision_index status` still exits 0 against mkt_engine (P2 regression check).

## Refused alternatives (do not re-debate)

- Pilot = this repo (no decision index; misses decision-merge path).
- No-config auto-seed / silent (kills curation nudge / fails silently).
- Nano silent-truncate / no cap (hidden drops / hairball).
- Decision single-anchor attach (arbitrary doc-order; hides cross-cutting).
- Synthetic cross-cutting component (violates Block 4a frozen 3-level hierarchy).
- Fail-loud extract guard requiring all-FRESH+verified (couples P3 runnability to P2
  completion, contra roadmap "start in parallel").
- Extract `_shared/` NOW instead of Phase B (scope creep delaying P3 ship; coupling
  is convention-guarded in the interim per ADR-0001).

## Stale artifacts (do NOT trust for current state)

- `docs/AI_artifacts/_handoff/p3-pipeline-state.md` — last updated at the spec step;
  its "next step: factual-code-verification" line is SUPERSEDED (verify + plan both
  done). Kept as a record, not a pick-up point. **Use STATE.md (this file) instead.**
- `docs/AI_artifacts/_handoff/p3-resume-verification.md` — same; superseded.
- `docs/AI_artifacts/_handoff/_archive/ssot-graph-p4-iteration.md` — phase-mismapped
  (labeled P4 but is P5/P6 pre-exploration) + stale P2 data. See its archive README.
- Assistant-private memory file `parallel-phase-ab-split.md` — has stale "0/25
  verified" framing. The live index (33/33 verified+FRESH) is the truth; re-verify
  the live index each session, do not trust that memory file.
