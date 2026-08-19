# STATE — codegraph-piggyback            _Last updated: 2026-08-19_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Bucket 3 on `main` `d3e0e0a` and LIVE** (`~/.codegraph-piggyback` same SHA). Remaining ROI **6 → 5**.

## Next action

Start Bucket 6. Not pushed — origin is behind this machine.

## Working tree

- `main` `d3e0e0a` (ahead of origin). No `bkt3-plan-verify*` worktrees/branches.
- Village: `orch-bkt3-plan-verify` **`:19831`** still up (reused). Pin `VILLAGE_HOST=127.0.0.1` `VILLAGE_PORT=19831`. Never `:8877`. Do not stop `:19641`.
- LIVE hooks: Claude `PostToolUse Write|Edit` → `$HOME/.codegraph-piggyback/plan-verifier/plan_verify.py --hook`. Cursor has no twin.

## Hazards / do-not-touch

- **TD-01** OPEN until Bucket 6 (`docs/TECH_DEBT.md`). Bucket 4 already on main + live dist already has the CLI strings.
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`. Live copy: rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/`.
- Workers: no `src/mcp/**`, no installer `cursor.ts`, no `.codegraph/ready`.
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

## Resume steps

1. Bucket 6 next.
2. Push `main` when you want GitHub / other clones to see 3 (and the 39 local commits).
3. Restart Claude Code so the new plan-verifier hook loads.
