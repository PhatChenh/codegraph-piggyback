# INCOMPLETE — Bucket 4 codegraph CLI impl

**Status:** impl landed on phase branch `bkt4-codegraph-cli` (INT tip `e8acbf7`). **Not merged to main** (Away I2). Parent `main` still has unrelated Buckets 1+2 dirty files — do not mix.

## Plain summary

The CLI now refuses a leftover `${…}` folder name instead of silently indexing the wrong place, and `codegraph init` will rebuild a junk or empty index while leaving a locked one alone. A last-minute bug: a brand-new project that failed to start was told we “couldn’t repair” it — that label is fixed and copied into the live install. The work is on a side branch waiting for you to merge to main later. Next product slice after that is still FEEDBACK-scope buckets 3 → 6 → 5.

## Dispatch ledger

| # | Model | Role | Task | Outcome | Commit(s) |
|---|---|---|---|---|---|
| 1 | cmd-pro | implement | Step 1 snapshotTree | pass after report testCmd FIX | `7b10e37` → merge `1b3e745` |
| 2 | cmd-pro | implement | Step 6 ADR/UPDATING/CHANGELOG | verify-wave 21 dismissed (md not in index) | `a3adf12` → `e7c6adb` |
| 3 | cmd-pro then cmd-pro FIX | implement | Step 2 probeIndexHealth | grok CHANGES_REQUESTED → judge CONFIRM test pins → APPROVE | `e42b8d8` → `133be83` |
| 4 | cmd-pro | implement | Step 3 assertExpandedPath | pass | `144c23f` → `3787d88` |
| 5 | cmd-pro (timeout/usage_limit) then clx-deepseek-v4-pro `3db47f9a` | implement | Step 4 init repair dispatch | grok APPROVE | `e303dd1` → `710836e` |
| 6 | clx-deepseek-v4-pro (prompt-too-long then continue + FIX 1) | implement | Step 5 E2E | grok CHANGES_REQUESTED → judge CONFIRM → APPROVE | `b93f288` `550fc9e` → `43745b3` |
| 7 | clx-deepseek-v4-pro `d22ac552` | implement | Step 7 build+rsync+live | cat21 TESTS-MISSING dismissed (empty-touch) | no source commit |
| 8 | syn-2-kimi-k3 `8e5f0865` | whole-diff | 265240e..43745b3 | CHANGES_REQUESTED Important 1 | — |
| 9 | claude-opus `df93a896` | judge | Important 1 | CONFIRM | — |
| 10 | clx-deepseek-v4-pro `822f1d33` | implement | whole-diff FIX 1 | verify-wave 0; grok APPROVE | `2b37c44` → `e8acbf7` |
| 11 | cursor grok 4.6 Task | tier-A review | Steps 2,4,5 + FIX 1 | APPROVE after judge-gated FIXes | harness, not av |

## Decision ledger

- I2: no push / no main merge. This report is the close of impl Away, not a main landing.
- Step 6 cat21 (markdown not indexed) and Step 7 cat21 (empty-touch) dismissed with judge/plan cover.
- Whole-diff Important 1 CONFIRMed: inner try wrapped fresh-init; user-facing “Cannot repair index (errcode undefined)”. Fix: `repairing` flag before probe; never use post-unlink `isInitialized`.
- Minors 1–3 folded; 4–5 dismissed by judge.
- IMPL seat: cmd-pro until usage_limit (resetAt 2026-08-17 23:22 +07); then clx-deepseek-v4-pro (owner 1b).
- Writ skipped (no writ.json row) — `TOOL_ISSUE_writ.md`.
- ORCH wrote no production code.

## Escalation ledger

- Spec-stage non_convergence / Connection stalled (pipeline, earlier same day) — owner reseated; not re-opened in impl.
- cmd-pro Step 4 usage_limit → reseat DeepSeek (not a 2-round code fix cap burn).
- Step 5 Prompt is too long → continue SID then FIX 1 (within cap).
- Check 4 fenced sentinel on FIX 1 ACP reply → reportExempt + disk report (not a production re-loop).

## Cost line

Daemon `:19817` session list (best-effort, 2026-08-17 22:55 +07): **~USD 24.69** summed `costUsd`, **not** the Away “$0 paid APIs” bound. Dominant: `syn-2-kimi-k3` whole-diff ~$13.84 (1.54M tok); earlier `syn-kimi-k3` ~$10.12 (1.12M tok, design/RT-era SID on same daemon). DeepSeek impl cluster ~$0.73. Opus judge `costUsd` 0 with 660 tok (unpriced or unmetered). cmd-pro mostly `usageUnavailable`. Harness grok Task tokens **UNKNOWN (not on this daemon)**. Village Block E reminder: use daemon usage when complete, not this scrape, for the next run.

## Retro (harvest)

Repeatable: (1) error-path plan lines must pin the exact user-visible string for **both** fresh and repair; (2) `=== END REPORT ===` must be unfenced last line of ACP reply **and** WT-root `IMPLEMENTATION_REPORT.md` (not `codegraph/`); (3) judge files belong in the **worktree** `.village/runs/…/channel/`, not repo-root `.village/` of a dirty main checkout; (4) clx `contextGate` 32k + 20k bootstrap → keep briefs tiny. One-off: cmd-pro usage_limit, Step 5 prompt-too-long after writing suites.

## Unfinished

- Phase branch not on main. Worktrees under `.village/worktrees/bkt4-codegraph-cli*` still live.
- Parent `main` dirty: Buckets 1+2 + this chat’s piggyback files — merge 4 separately.
- TD-01 OPEN until 4+6.
- Remaining ROI: 3 → 6 → 5.
- Judge SID `df93a896` left running (persistent). Daemon `orch-bkt4-cg-cli` left running (reused, not started solely for cleanup ownership).
