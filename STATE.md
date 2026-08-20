# STATE — codegraph-piggyback            _Last updated: 2026-08-20_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Bucket 5 impl DONE on phase branch** `bkt5-codegraph-mcp` tip `9c8afce` (not main). Handshake tells missing vs empty vs usable on both MCP doors. Whole-diff APPROVE 0 findings. E2E vitest 7 files / 52 pass. Live Cursor binary **not** rsynced.

## Next action

Human: rsync `codegraph/dist/` when you want Cursor MCP to see it; then merge branch → main **after** Bucket 6 is clear. Remaining ROI: Bucket 6 writ probe.

## Working tree

- Phase WT `.worktrees/bkt5-codegraph-mcp` on `bkt5-codegraph-mcp`.
- Village: `orch-bkt5-codegraph-mcp` `:19851`. Never `:8877`. Do not stop `:19841` `:19831` `:19391`.
- `main` may be dirty with Bucket 6 — do not use that tree for this merge.

## Hazards / do-not-touch

- **TD-01** OPEN. No installer `cursor.ts`, no `.codegraph/ready`.
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`.
- Frozen this phase: `directory.ts` / `engine.ts` / `daemon.ts` / barrel / CLI `init`.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.

## Locked decisions

- HOW locks A–E + MCP tri-state: plan `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md`. ADR `codegraph/docs/adr/0002-mcp-index-tri-state.md`.
- Grill: `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md`.
- OQ-2 A (re-probe). OQ-3 OPEN. Live rsync SKIP this run.
- Path-only on-disk (Bucket 3): `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`.

## Key docs

- Impl report: `docs/AI_artifacts/9_runs/2026-08-20-bkt5-codegraph-mcp.md`
- Paper report: `docs/AI_artifacts/9_runs/2026-08-19-bkt5-codegraph-mcp.md`
- Plan: `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md`
- E2E: `docs/AI_artifacts/8_verification/2026-08-20-bkt5-codegraph-mcp/verdict.md`
- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## Resume steps

1. Work in `.worktrees/bkt5-codegraph-mcp`. Pin `VILLAGE_PORT=19851` only if driving leftover judge `5257dc39`.
2. Rsync live dist when ready. Merge to main only when Bucket 6 is off `main`.
3. Do not push unless asked.
