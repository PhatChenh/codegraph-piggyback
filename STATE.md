# STATE — codegraph-piggyback            _Last updated: 2026-08-20_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Bucket 5 impl on `main` + LIVE.** Handshake tells missing vs empty vs usable on both MCP doors. Whole-diff APPROVE 0 findings. E2E vitest 7 files / 52 pass. Live bundle rsynced `2026-08-20` → `~/.codegraph/versions/v1.0.1/lib/dist/` (`index-state.js` present). Restart Cursor/Claude MCP to pick it up.

**Bucket 6 paper on `main`.** Writ impl lives in `falkor-writ/.worktrees/bkt6-writ-probe` (daemon `:19841`). Not started as product code here.

## Next action

Optional: restart Cursor/Claude so the MCP process reloads. Remaining ROI: Bucket 6 writ probe impl. Do not push unless asked.

## Working tree

- Piggyback `main` holds Bucket 5 code + Bucket 6 paper.
- Phase WT `.worktrees/bkt5-codegraph-mcp` still exists (not pruned this merge).
- Village: `orch-bkt5-codegraph-mcp` `:19851`. Never `:8877`. Do not stop `:19841` `:19831` `:19391`.

## Hazards / do-not-touch

- **TD-01** OPEN until Bucket 6 (`docs/TECH_DEBT.md`). No installer `cursor.ts`, no `.codegraph/ready`.
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`.
- Bkt6 workers: no `src/mcp/**`, no installer `cursor.ts`. Never stop `:19841`.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.

## Locked decisions

- HOW locks A–E + MCP tri-state: plan `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md`. ADR `codegraph/docs/adr/0002-mcp-index-tri-state.md`.
- OQ-2 A (re-probe). OQ-3 OPEN. Live rsync DONE 2026-08-20.
- Path-only on-disk (Bucket 3): `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`.

## Key docs

- Bkt5 impl: `docs/AI_artifacts/9_runs/2026-08-20-bkt5-codegraph-mcp.md`
- Bkt6 paper: `docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.md`
- Bkt6 kickoff: `docs/AI_artifacts/_handoff/2026-08-20-bkt6-writ-probe-impl-kickoff.md`
- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## Resume steps

1. Restart Cursor/Claude MCP so the new handshake loads. First-contact: missing / empty / busy initialize.
2. Bucket 6: open **falkor-writ** worktree. Pin `VILLAGE_PORT=19841`.
3. Do not push unless asked.
