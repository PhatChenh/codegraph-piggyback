# Kickoff — Bucket 5 impl (paste into the Bkt5 session)

_Date:_ 2026-08-20  
_Owner intent:_ isolated tree, `/av-orchestrate`, parallel with Bucket 6, do not collide.

**Read this file first, then `STATE.md`.** Do not invent a second impl.

---

## STOP — already in flight (2026-08-20 11:08)

Do **not** start Bucket 5 from `main`. Do **not** `git add -A`. Do **not** create a second branch.

Already exists:

- Worktree: `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/.worktrees/bkt5-codegraph-mcp`
- Branch: `bkt5-codegraph-mcp` (from `ae765b8`)
- All **8 plan steps merged** (`9c8afce` wave E)
- Impl RUN_STATE: `.worktrees/bkt5-codegraph-mcp/.village/runs/2026-08-20-bkt5-codegraph-mcp/state.md`
- Last position: **§9.1 solo kimi whole-diff in flight** (SID `8dbb58f1`); live rsync SKIP; no push; no main merge
- Daemon: `orch-bkt5-codegraph-mcp` **`:19851`** — pin `VILLAGE_PORT=19851`. Do not stop `:19841` (Bucket 6), `:19831`, `:19391`, `:19641`. Never `:8877`.

**If you are a new agent:** `cd` that worktree. Read that RUN_STATE last entry. Continue phase-end (`/av-orchestrate` §9.1 → §10). Do not re-run waves A–E. Do not re-commit paper docs (already on `ae765b8`).

**If whole-diff already finished:** do §10 docs on the **phase branch**, then stop for human merge/rsync.

---

## If (and only if) that worktree is gone — greenfield

Then follow the owner prompt below. Still never `git add -A` on piggyback `main`.

### Seats (owner 2026-08-20)

| Seat | Profile | Rule |
|---|---|---|
| IMPL | `clx-deepseek-v4-flash` | **Fresh SID every step / fix.** Never reuse a flash session. I6. |
| Tier-A review | harness grok 4.6 (`cursor-grok-46` / Cursor Grok 4.6 Task) | **ONLY I9 exception.** Impl, fix, whole-diff, gather-that-writes-code = `av` only. |
| Whole-diff §9.1 | `syn-3-kimi-k3` | **One agent, no panel.** I7. |
| Judge | `syn-3-kimi-k3` persistent `JUDGE_SESSION` | Thin stamps; Tier-A craft. Do not reuse a parked SID. |
| Daemon | reuse `:19851` `orch-bkt5-codegraph-mcp` | I5. |

Plan: `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md`  
Skill: `~/.claude/skills/av-orchestrate/SKILL.md`  
Away card: `~/.claude/skills/av-orchestrate/reference/away-mode.md` **I1–I9**. Confirm-once (`defaults`), then **only** run-specific leftovers. Do not re-ask auto-cross / commit-no-push / SID freshness / solo-vs-panel / harness-ban as separate Qs.

I9 **delta already accepted** on the in-flight run: harness grok 4.6 for **tier-A review only**.

Front-load all knowable asks **before** away. Bound every pre-auth (not a bare yes).

UI_SCOPE=no (no §9.0).

### Isolated tree

1. `cd` piggyback.
2. If `.worktrees/bkt5-codegraph-mcp` exists → use it (see STOP).
3. Else: `git worktree add .worktrees/bkt5-codegraph-mcp -b bkt5-codegraph-mcp` from current `main` **after** a **surgical** commit of **Bucket 5 paper only** (paths below). Never `git add -A`.

**Allowed on a docs commit (if paper is still uncommitted — it is NOT; skip):**  
`docs/AI_artifacts/{3_design,4_specs,5_factual-code-verification,6_plans,7_reviews,9_runs}/*bkt5-codegraph-mcp*`  
`docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md`

**Forbidden in that commit:** anything `*bkt6*`, `STATE.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/model-scoreboard.csv`, `docs/TECH_DEBT.md`, `plan-verifier/**`, `.village/`.

### Parallel with Bucket 6 — do not collide

Bucket 6 impl (other agent) owns **falkor-writ** + later piggyback `docs/TECH_DEBT.md` Step 10. Bucket 5 owns `codegraph/src/mcp/**` + plan Files list only.

**Never:**

- Edit `docs/TECH_DEBT.md` (Bkt5 plan off-limits; Bkt6 Step 10 owns the TD-01 note)
- Edit falkor-writ
- Edit `*bkt6*` artifacts / `.village/runs/2026-08-19-bkt6-writ-probe/`
- Stop or pin `VILLAGE_PORT=19841`
- `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`
- Overwrite `~/.cursor/hooks/writ-blast-gate.sh` or any `hooks.json`
- **rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1`** until the human says so — Bkt6 WAL tests use that live `codegraph init`. Pickup item. Plan already SKIP live rsync.
- Full-file overwrite `STATE.md` / `CLAUDE.md` on piggyback **main**. Phase-branch STATE in the Bkt5 worktree is OK. Main `STATE.md` is shared; surgical one-liners only, or leave it to the Bkt6 orch.

`STATE.md` / `CLAUDE.md` are hard off-limits in the Bkt5 **plan** for the worker; ORCH §10 on the **phase branch** is the exception.

### Commit / merge

I2: commit on `bkt5-codegraph-mcp`, **no push**, **no merge to main** until human. Finished waves committed before the run ends.

---

## Paste-ready owner line (greenfield only — do not use if STOP fired)

Read `docs/AI_artifacts/_handoff/2026-08-20-bkt5-impl-kickoff.md` and `STATE.md`. You implement **Bucket 5 only**. If `.worktrees/bkt5-codegraph-mcp` exists, reattach — do not start over. Else: surgical Bkt5-docs commit (never `git add -A`), then that worktree, then `/av-orchestrate`. IMPL=`clx-deepseek-v4-flash` fresh SID every step. Tier-A review = harness grok 4.6 **only** (I9 exception). Whole-diff = one `syn-3-kimi-k3` agent, no panel. Judge = persistent `syn-3-kimi-k3`. Reuse daemon `:19851`. Front-load, then Impl Away I1–I9 (`defaults`) plus the I9 grok delta. Do not rsync live `~/.codegraph`. Do not touch Bucket 6, falkor-writ, `docs/TECH_DEBT.md`, or `:19841`.
