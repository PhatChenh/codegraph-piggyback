# STATE — codegraph-piggyback            _Last updated: 2026-08-18_

> Cap ~80 lines. History → `CHANGELOG.md`.

## Current position

**Bucket 3 pipeline DONE** (design → RT → spec → FCV → plan). No product code. Plan ready to implement. Remaining ROI still **3 impl → 6 → 5**.

## Next action

Implement `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md` (disk-stat path-only + REUSE normalize in `plan-verifier/plan_verify.py`).

## Working tree

- Branch: `main`. Docs commit this run; **not pushed**.
- Village: `orch-bkt3-plan-verify` **`:19831`**. Pin `VILLAGE_HOST=127.0.0.1` `VILLAGE_PORT=19831`. Never `:8877`. Do not stop `:19641`.
- JUDGE_SESSION=`b6c33674-ec91-4a92-9bde-9c6ee55dbef6`. DESIGN_SID=`0ddead60-3754-484f-aaaa-25f301780649`.

## Hazards / do-not-touch

- **TD-01** OPEN until Buckets 4+6 (`docs/TECH_DEBT.md`).
- Fork: never `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`. Live copy: rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/`.
- Workers: no `src/mcp/**`, no installer `cursor.ts`, no `.codegraph/ready`.
- BUG-023 FIXED (`1e48ad2`) — do not re-open.
- Village ACP `--path` = worktree cwd lives in **this checkout’s village `dist/`** until other daemons rebuild.

## Locked decisions

- Path-only regular file on disk → not MISSING; `new:` → COLLISION; evidence `on disk, not in index`. `::` stays index-bound (including `foo.py::`). Directories `is_file()` only.
- REUSE: strip `(...)`, `…`, `...`; warn-only.
- ADR tool-local: `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` (with impl).
- `_on_disk` catches `OSError` **and** `RuntimeError`. Stat root = DB’s repo (`--db`), not the plan folder.
- Away D1–D8 ACCEPTED 2026-08-18. This run I9: grok 4.6 Task = RT/spec/FCV/plan; other seats `av`.

## Key docs

- Plan: `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`
- Report: `docs/AI_artifacts/9_runs/2026-08-18-bkt3-plan-verify.md`
- Grill: `docs/AI_artifacts/_handoff/2026-08-18-bkt3-plan-verify-grill.md`
- Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## Resume steps

1. Pin `:19831` if still using the isolated daemon.
2. Implement the plan above. `python3 -m pytest plan-verifier/ -q`.
3. Next ROI bucket after 3 ships: **6**.
