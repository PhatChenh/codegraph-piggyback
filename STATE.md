# STATE.md — codegraph-piggyback

> **Pick-up point for the next AI session.**

## Current position

**ssot-diagram P5 (interactive HTML renderer) MERGED to main `a51384e`
(2026-07-10)** + pushed `bf1570a`. 129 pytest / 3 pre-existing `TestGoldenLive`
pilot-drift (0 NEW); golden sha `56df3d86…` intact; render E2E 339KB
self-contained, byte-deterministic. Run report:
`docs/AI_artifacts/9_runs/2026-07-10-p5-html-renderer.md`.

**plan-verifier + diff-verifier MERGED to main** (`82287f9` ship + BUG-024
fix via `57c0961`).

## NEXT (in order)

0. **FEEDBACK bugs + TD-01 scope (2026-08-16)** — pickup:
   `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`.
   ROI pickup: 1 village ACP → 2 grep-absent → 4 codegraph CLI →
   3 plan_verify → 6 writ probe → 5 codegraph MCP.
   BUG-023 is FIXED (`1e48ad2`); do not re-open from this file's old bullet 3.
1. **Live painter E2E** — owner browser-check `/tmp/p5.html` (click
   macro→micro→nano, hover PROPOSED/UNNARRATABLE, pan/zoom, theme). Deferred,
   not headlessly assertable. `ssot-diagram/STATE.md` owns.
2. **ssot P6** — PostToolUse re-extract hook (`ssot-diagram/roadmap.md`).

## Per-tool pointers

- **ssot-diagram** — P5 done; P6 next; live painter E2E OPEN.
  `ssot-diagram/STATE.md` (canonical); `ssot-diagram/roadmap.md`.
- **plan-verifier / diff-verifier** — SHIPPED, on main. `plan-verifier/design.md`.
- All others (impact-analyzer, codegraph-gate, plan-visualizer,
  changeset-context, repo-map, impact-precommit, drift-digest, sot-enrichment,
  dead-code-finder, doc-coverage) — `docs/roadmap/roadmap.md`.

## OPEN human-authority items

- **OQ-FOLDER-001** — legacy `0_scout/1_design/…`; new scheme per
  DOC-ARTIFACT-001. Migration deferred post-pipeline.
- **OQ-A24** — CI pilot-DB presence; extract CLI must skip-if-absent.
  Non-blocking.

## Open tech debt

- **TD-01** — in scope as Bucket 4 (`codegraph init` repairs unusable) +
  Bucket 6 (writ wrapper runs `index`). Spec:
  `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`. Still OPEN
  until those buckets land (`docs/TECH_DEBT.md`).

## Tools online

- CodeGraph ✅ — `codegraph` CLI; MCP `codegraph_explore`/`codegraph_node`/`codegraph_callers` primary explore. Never write to DB.
- Writ daemon ✅ port 9130. Set mode via `writ-session.py` (path in repo `CLAUDE.md` §10).
- Subagent casting BLOCKED for `general-purpose`/`claude`/omitted. Use `writ:worker` / `writ:writ-implementer` (writes); `writ:writ-explorer` / `Explore` (read); `writ:writ-plan-reviewer` → `writ:writ-code-quality-reviewer` (review).

## Refused alternatives (do not re-debate)

- Pilot = this repo (no decision index; misses the decision-merge path).
- Defer `_shared/` to Phase B → SUPERSEDED (shipped `82287f9`).