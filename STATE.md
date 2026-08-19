# STATE — codegraph-piggyback            _Last updated: 2026-08-19_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Bucket 3 impl DONE on phase branch** `bkt3-plan-verify` (not main). Whole-diff APPROVE. Behavior-verify all PASS. Remaining ROI **6 → 5**.

## Next action

Human: merge `bkt3-plan-verify` → `main` when ready (I2). Then start Bucket 6. Plan still: `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`.

## Working tree

- Parent: `main` (`b90f1ec`, not pushed). Phase branch tip after docs commit (this run-report).
- Village: `orch-bkt3-plan-verify` **`:19831`**. Pin `VILLAGE_HOST=127.0.0.1` `VILLAGE_PORT=19831`. Never `:8877`. Do not stop `:19641`.
- IMPL=`clx-deepseek-v4-flash`. WHOLE_DIFF=`syn-3-kimi-k3` `85edb2d9` stopped. JUDGE=`1b9d0820-ae86-4ee0-a150-0cc4ed5ecba4` (`claude-opus`) left live.

## Hazards / do-not-touch

- **TD-01** OPEN until Bucket 6 (`docs/TECH_DEBT.md`). Bucket 4 already on main.
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`. Live copy: rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/`.
- Workers: no `src/mcp/**`, no installer `cursor.ts`, no `.codegraph/ready`.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.

## Locked decisions

- Path-only regular file on disk → not MISSING; `new:` → COLLISION; evidence `on disk, not in index`. `::` stays index-bound (including `foo.py::`). Directories `is_file()` only.
- REUSE: strip `(...)`, `…`, `...`; warn-only.
- ADR: `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`.
- `_on_disk` catches `OSError` **and** `RuntimeError`. Stat root = DB’s repo (`--db`), not the plan folder.
- Impl Away I1–I8 + I9 DELTA ACCEPTED 2026-08-19.

## Key docs

- Plan: `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`
- Impl report: `docs/AI_artifacts/9_runs/2026-08-19-bkt3-plan-verify.md`
- Pipeline report: `docs/AI_artifacts/9_runs/2026-08-18-bkt3-plan-verify.md`
- Verify: `docs/AI_artifacts/8_verification/2026-08-19-bkt3-plan-verify/verdict.md`
- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## Resume steps

1. Merge `bkt3-plan-verify` → `main` (human). Then prune `.village/worktrees/bkt3-plan-verify*`.
2. Next ROI bucket: **6**.
3. `python3 -m pytest plan-verifier/ -q` — expect 59 passed on the phase branch.
