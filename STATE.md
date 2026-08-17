# STATE — codegraph-piggyback            _Last updated: 2026-08-17_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Bucket 4 impl DONE on phase branch** `bkt4-codegraph-cli` (INT tip `e8acbf7`). Unexpanded `${…}` paths refused; `init` repairs empty/unreadable, refuses busy; whole-diff FIX 1: fresh-init failures say `Failed to initialize` (live CLI rsynced). **Not on main** (I2). Buckets 1+2 still uncommitted on the parent `main` checkout — do not mix.

## Next action

Owner merge `bkt4-codegraph-cli` → main when ready (separate from Buckets 1+2). Then FEEDBACK-scope **3 → 6 → 5**. Do not start Wave A again.

## Working tree

- Phase INT: `.village/worktrees/bkt4-codegraph-cli` branch `bkt4-codegraph-cli`.
- Parent `main`: dirty leftover Buckets 1+2 (`diff-verifier/*`, `FEEDBACK.md`, live-cert) — not this branch.
- village: `orch-bkt4-cg-cli` `:19817` left up (reused). Pin `VILLAGE_HOST=127.0.0.1` `VILLAGE_PORT=19817`. Never `:8877`.

## Hazards / do-not-touch

- **TD-01** OPEN until Buckets 4+6 (`docs/TECH_DEBT.md`).
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`. Live copy: rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/`.
- Workers: no `src/mcp/**`, no installer `cursor.ts`, no `.codegraph/ready`.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.
- Village ACP `--path` = worktree cwd lives in **this checkout’s village `dist/`** until other daemons rebuild.

## Locked decisions

- Away I1–I8 + **I9 DELTA**: grok 4.6 harness Task = tier-A review only; all other seats `av`.
- Q2-a ACP `--path` absolute cwd; Desktop keeps `${workspaceFolder}` → scope §2.
- Q3-a `grep-absent` 0 files = fail → scope §2.
- Init: empty/unreadable repair; busy/unclassified refuse; smashed db unlink three sqlite files only.

## Key docs

- Run report (INCOMPLETE vs main): `docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.md`
- RUN_STATE: `docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.state.md`
- Plan: `docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md`
- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## Resume steps

1. Work from INT WT or `git checkout bkt4-codegraph-cli` — not dirty `main`.
2. Pin `:19817`. Do not re-run Stages 1–5.
3. Merge to main is a human gate. After merge: prune `.village/worktrees/bkt4-codegraph-cli*`.
