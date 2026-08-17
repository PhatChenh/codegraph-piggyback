# CHANGELOG — codegraph-piggyback

One line per landing. Detail lives in the linked artifact.

## 2026-08-17

- **Bucket 4 codegraph CLI pipeline DONE** — design/RT/spec/FCV/plan pinned (`21221ce`). Impl Away armed (I1–I8 + I9 harness-subagent exception for grok 4.6 tier-A review only). Plan: `docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md`. RUN_STATE: `docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.state.md`.

## 2026-08-16

- **FEEDBACK-scope Buckets 1+2** — (1) village ACP `.cursor/mcp.json` `--path` = absolute worktree cwd (not `${workspaceFolder}`, not `profile.worktree`); live cert PASS. (2) `diff-verifier` `grep-absent` with zero files scanned = `no file matches` (QUALIFIER_FAIL). Uncommitted. Next: Bucket 4 codegraph CLI. Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`. Cert: `docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/verdict.md`.
- **FEEDBACK-scope grill** — 6 buckets / 3 tiers locked (2 prior items already DONE). Scout SID `76933935-…` on `:19341`. Same scope file.

## 2026-07-10

- **ssot P5 HTML renderer MERGED** `a51384e` (pushed `bf1570a`) — 129 pytest / 3 pre-existing `TestGoldenLive` pilot-drift. → `docs/AI_artifacts/9_runs/2026-07-10-p5-html-renderer.md`

## 2026-07-09

- **plan-verifier + diff-verifier + `_shared/` MERGED** `82287f9`; BUG-024 per-wave `--step` `57c0961`. BUG-023 staged-cwd FIXED in village `1e48ad2` (not a piggyback re-open).
