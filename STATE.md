# STATE.md — codegraph-piggyback

> **Pick-up point for the next AI session.** Read this first, then the files it
> names. Last updated 2026-07-04.

## What is happening right now (repo-wide)

Last action: **ssot-diagram P3 merged to main** (`ba02a56`, 2026-07-04) — NOT pushed
to origin. All other tools specced in `<tool>/design.md`, build order in
`docs/roadmap/roadmap.md`.

## Per-tool state pointers

- **ssot-diagram** — phases P0–P6. P1 (decision-index) + P2 (curation) + P3
  (diagram-model extractor) all DONE; P4 (narrative sidecar) next. Pick-up point:
  `ssot-diagram/STATE.md`. Roadmap: `ssot-diagram/roadmap.md`. Rules:
  `ssot-diagram/CLAUDE.md`.
- _(other tools — impact-analyzer, codegraph-gate, _shared, plan-verifier,
  plan-visualizer, changeset-context, repo-map, impact-precommit, drift-digest,
  sot-enrichment, dead-code-finder, doc-coverage — have no per-tool STATE yet;
  see `docs/roadmap/roadmap.md` for status.)_

## OPEN human-authority items (repo-wide, deferred)

- **OQ-FOLDER-001 (product-identity):** repo is on the legacy artifact-folder scheme
  (`0_scout/1_design/2_specs/3_factual-code-verification/4_plans/`). The DOC-ARTIFACT-001
  rule wants the new scheme (`0_draft/1_scout/2_ux/3_design/4_specs/5_factual-code-verification/6_plans/…`).
  Migration deferred to post-pipeline — do NOT migrate mid-build.
- **OQ-A24 (operating-burden):** whether CI has the pilot DB checked out. The `extract`
  CLI must skip-if-absent (warn, not fail) so this stays non-blocking.

## Tools (verified online 2026-07-04)

- CodeGraph: ✅ online. CLI at `codegraph` (nvm bin); repo has `.codegraph/`; file
  watcher + hooks active (`codegraph-gate.py`, `decision_hook.py`). Use codegraph MCP
  tools (`codegraph_explore`/`codegraph_node`/`codegraph_callers`) or the shell CLI as
  the primary explore tool. Never write to the DB.
- Writ daemon: ✅ up (port 9130). Set writ mode before working:
  `/Users/phatchenh/.cache/writ/.venv/bin/python /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/writ-session.py mode set <work|review> <session-id>`.
- Subagent casting rule (CLAUDE.md §10): `general-purpose`/`claude`/omitted
  subagent_type are BLOCKED (hook bounce). Cast a leaf: writes → `writ:worker` or
  `writ:writ-implementer` (plan-driven); read-only → `writ:writ-explorer`/`Explore`;
  review → `writ:writ-plan-reviewer` then `writ:writ-code-quality-reviewer`.

## Refused alternatives (repo-wide, do not re-debate)

- Pilot = this repo (no decision index; misses the decision-merge path).
- Extract `_shared/` NOW instead of Phase B (scope creep delaying ships; coupling is
  convention-guarded in the interim per the per-tool ADR).
