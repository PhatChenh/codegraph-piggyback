# STATE — codegraph-piggyback            _Last updated: 2026-08-17_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

FEEDBACK-scope **Buckets 1+2 done in source** (uncommitted on this checkout). **Bucket 4 LIGHT pipeline DONE** (design→RT→spec→FCV→plan; docs commit `21221ce`). **Impl Away armed** — waves not started.

## Next action

**Bucket 4 Wave A** (Steps 1 ∥ 2 ∥ 6) on phase branch `bkt4-codegraph-cli`, isolated tree. Plan: `docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md`. RUN_STATE + away ledger: `docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.state.md`.

## Working tree

- piggyback `main` (ahead of origin). Dirty leftover **not** this run: `diff-verifier/*`, `FEEDBACK.md`, live-cert under `docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/`.
- Impl integration WT: `.village/worktrees/bkt4-codegraph-cli` (create after docs commit).
- village: reuse labeled daemon `orch-bkt4-cg-cli` `:19817` if live; else new same-label high port. Do not stop other orch daemons. Prior pins `:19341`/`:19581`/`:19621` were **not live** at 2026-08-17 kickoff.

## Hazards / do-not-touch

- **TD-01** still OPEN until Buckets 4+6 (`docs/TECH_DEBT.md`).
- **A5** skipped: no ACP skill file; do not invent one.
- Village ACP `--path` fix is in **this checkout’s `dist/`**. Other live daemons still old until rebuild+bounce. Desktop `${workspaceFolder}` stays.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`.
- Workers: no `src/mcp/**`, no installer `cursor.ts`, no `.codegraph/ready`.

## Locked decisions

- Q2-a ACP mcp `--path` = absolute worktree cwd; Desktop keeps `${workspaceFolder}` → scope §2.
- Q3-a `grep-absent` 0 files = fail, same as `grep-present` → scope §2.
- Full freeze table → scope §7.
- **Impl Away 2026-08-17:** I1–I8 accepted; **I9 DELTA** = grok 4.6 harness subagent for **tier-A review only**; all other seats `av`. Seats + bounds in RUN_STATE.

## Key docs

- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`
- Plan: `docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md`
- Bucket 1 live cert: `docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/verdict.md`
- Roadmap: `docs/roadmap/roadmap.md` · ssot P6: `ssot-diagram/STATE.md`

## Resume steps

1. Read RUN_STATE last entry. Do **not** re-run Stage 4.
2. Pin `VILLAGE_PORT` to this run’s labeled daemon.
3. Wave A from integration WT; IMPL `cmd-pro` (fallback `clx-deepseek-v4-pro`); tier-A review = this harness grok 4.6 Task; whole-diff `syn-2-kimi-k3`; judge `claude-opus`.
