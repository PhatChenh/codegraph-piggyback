# STATE — codegraph-piggyback            _Last updated: 2026-08-19_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Two runs.** Bucket 6: **owner pause** after r8 patch landed. Daemon `:19841`. Bucket 5: Stage 4 paper DONE; impl waiting owner go. Daemon `:19851`.

## Next action

Bkt6: **paused** (owner). Next when resumed: claims + judge + RT r9 (terminal). Pin `VILLAGE_PORT=19841`. Bkt5: pin `VILLAGE_PORT=19851`. Implement 8-step plan when you say go.

Bkt6 RUN_STATE: `docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.state.md`
Bkt5 RUN_STATE: `docs/AI_artifacts/9_runs/2026-08-19-bkt5-codegraph-mcp.state.md`

## Working tree

- `main` `d3e0e0a` (ahead of origin). No `bkt3-plan-verify*` worktrees/branches.
- Village live (do not stop): `orch-bkt5-codegraph-mcp` `:19851`; `orch-bkt6-writ-probe` `:19841`; `orch-bkt3-plan-verify` `:19831`; `lp10-impl` `:19391`. Never `:8877`. Do not stop `:19641`.
- LIVE hooks: Claude `PostToolUse Write|Edit` → `$HOME/.codegraph-piggyback/plan-verifier/plan_verify.py --hook`. Cursor has no twin.

## Hazards / do-not-touch

- **TD-01** OPEN until Bucket 6 (`docs/TECH_DEBT.md`). Bucket 4 already on main + live dist already has the CLI strings.
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`. Live copy: rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/`.
- Bkt6 workers: no `src/mcp/**`, no installer `cursor.ts`, no `.codegraph/ready`.
- Bkt5 owns `codegraph/src/mcp/**`. Still no installer `cursor.ts`, no `.codegraph/ready`, no writ probe.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.

## Locked decisions

- Path-only regular file on disk → not MISSING; `new:` → COLLISION; evidence `on disk, not in index`. `::` stays index-bound. Directories `is_file()` only.
- REUSE: strip `(...)`, `…`, `...`; warn-only.
- ADR: `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`.
- `_on_disk` catches `OSError` **and** `RuntimeError`. Stat root = DB’s repo (`--db`).

## Key docs

- Plan: `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`
- Impl report: `docs/AI_artifacts/9_runs/2026-08-19-bkt3-plan-verify.md`
- Verify: `docs/AI_artifacts/8_verification/2026-08-19-bkt3-plan-verify/verdict.md`
- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`
- Bkt6 RUN_STATE: `docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.state.md`
- Bkt5 RUN_STATE: `docs/AI_artifacts/9_runs/2026-08-19-bkt5-codegraph-mcp.state.md`

## Resume steps

1. Bkt6: pin `VILLAGE_PORT=19841`. Judge stamp then design dispatch.
2. Bkt5: pin `VILLAGE_PORT=19851`. Implement `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md`.
3. Push `main` when you want GitHub to see Bucket 3 (still local).
4. Restart Claude Code so the plan-verifier hook loads.
