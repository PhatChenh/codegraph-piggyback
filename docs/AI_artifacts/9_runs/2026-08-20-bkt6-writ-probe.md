# Run report — 2026-08-20 Bucket 6 writ-probe **impl**

**INCOMPLETE as a main-merge:** work is on `bkt6-writ-probe` (`5b937b4`), **not** falkor-writ `main`. No push. Human still owns main-merge, push, live rsync, Cursor hook copy.

Paper pipeline already shipped `docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.md`. This file is the **implementation** run.

## Plain summary

Writ now tells the truth when the code index file exists but cannot be read: it says “unreadable,” not “missing” or “wrong version.” Repair is rebuild via `writ codegraph-init` (which uses `codegraph init`), not a second `codegraph index`, and it never deletes the index file. The work is on a side branch waiting for you to merge. Eight older blast-gate tests still fail the same way they did before this work (they expect silence; the hook prints allow). Two WAL-retry tests need SQLite 3.51; the project venv’s 3.50.4 will show those two red even though the code is right.

## Dispatch ledger

| # | Model | Role | Task | Outcome | Commit(s) |
|---|---|---|---|---|---|
| 1 | clx-deepseek-v4-flash | implement | Step 1 `_connect` WAL | pass-first-try | `1ee9153` |
| 2 | cursor-grok-4.6-high | review | Step 1 tier-A | pass-first-try | — |
| 3 | clx-deepseek-v4-flash | implement | Step 2 `probe` enum | pass-first-try | `8bb3336` |
| 4 | cursor-grok-4.6-high | review | Step 2 tier-A | pass-first-try | — |
| 5 | clx-deepseek-v4-flash | implement | Step 3 one opener fold | pass-first-try | `5858aa3` |
| 6 | cursor-grok-4.6-high | review | Step 3 tier-A | pass-first-try | — |
| 7 | clx-deepseek-v4-flash | implement | Step 4 freshness | pass-first-try | `2f4fb58` |
| 8 | clx-deepseek-v4-flash | implement | Step 5 blast-gate (needed Step 4 merge + scoped testCmd) | needed-fixes | `57117fb` |
| 9 | clx-deepseek-v4-flash | implement | Step 6 PRE-UNREADABLE | pass-first-try | `94ae032` |
| 10 | cursor-grok-4.6-high | review | Step 6 tier-A | pass-first-try | — |
| 11 | clx-deepseek-v4-flash | implement | Step 7 wrapper exit 1 | pass-first-try | `9db075d` |
| 12 | cursor-grok-4.6-high | review | Step 7 tier-A | pass-first-try | — |
| 13 | clx-deepseek-v4-flash | implement | Step 8 ADR | pass-first-try | `2bb56d0` |
| 14 | clx-deepseek-v4-flash | implement | Step 9 WAL+lock pin | needed-fixes | `057fa79` |
| 15 | cursor-grok-4.6-high | review | Step 9 tier-A | findings-confirmed | — |
| 16 | clx-deepseek-v4-flash | implement | Step 9 FIX1 drop src.find | pass-first-try | `4852579` |
| 17 | cursor-grok-4.6-high | review | Step 9 FIX1 re-review | pass-first-try | — |
| 18 | syn-3-kimi-k3 | judge | thin stamps + finding 1 ACCEPT | findings-confirmed | — |
| 19 | orch (this session) | docs | Step 10 TD-01 note | pass-first-try | piggyback `9112ee7` |
| 20 | syn-3-kimi-k3 | review | §9.1 whole-diff | pass-first-try | — |

Merge commits on INT: `5c37998` `7872ec5` `7c487a5` `0f552b8` `c0d902e` `a044ef0` `e458ee6` `6e66f8a` `5b937b4`. Tip **`5b937b4`**.

## Decision ledger

- I1 auto-cross; no pause after waves.
- Step 5 testCmd scoped to the new unreadable equality test — 8 silent-pass vs `{"permission":"allow"}` failures pre-exist on falkor-writ `main`.
- Scratch plan `new:` → `touch:` for the markdown ADR (codegraph NOT-DELIVERED on `.md`). Canonical plan untouched.
- Judge ACCEPT Step 9 finding 1 (tautological `src.find < second`); FIX dropped the three position compares; membership pins kept.
- Whole-diff APPROVE; two MAJORs recorded as plan-premise (sqlite 3.50.4 vs 3.51.0 WAL-retry fire) and pre-existing blast-gate tests — not impl defects.
- Step 10 authored by orch as piggyback §10 docs (one dated line). Status OPEN.

## Escalation ledger

none this impl run (away I1–I9 already accepted 2026-08-20). Human still owns: falkor-writ main merge, push, live rsync, Cursor hook copy.

## Cost line

unavailable as a single number (`usageUnavailable` on flash). Roughly 10 flash impl turns + 1 FIX + 6 grok reviews + ~8 judge stamps + 1 whole-diff.

## Behavior-verify (offline)

INT + PYTHONPATH + `vendor/falkordb.so`: `243 passed` on codegraph_index + blast_radius + artifact_claims + writ_codegraph_init + connect_wal_lock. Blast-gate file: `8 failed, 12 passed` (same 8 at `193c957`). `rg sqlite3.connect bin/lib/` = two sites in `_connect`.

## Resume / leftover

- Merge: INT `.village/runs/2026-08-20-bkt6-writ-probe/channel/MERGE_PROPOSAL.md`
- Whole-diff: `channel/WHOLE_DIFF.md`
- Do not `git push`. Do not merge `bkt6-writ-probe` to `main` until you say.
