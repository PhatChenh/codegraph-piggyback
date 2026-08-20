# Kickoff — Bucket 6 impl (paste into the Bkt6 session)

_Date:_ 2026-08-20  
_Owner intent:_ isolated **falkor-writ** tree, `/av-orchestrate`, parallel with Bucket 5, do not collide.

Plan: `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/docs/AI_artifacts/6_plans/2026-08-19-bkt6-writ-probe.md`  
Skill: `~/.claude/skills/av-orchestrate/SKILL.md`  
Away card: `~/.claude/skills/av-orchestrate/reference/away-mode.md` I1–I9  
Paper RUN_STATE: `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.state.md`

---

## House, not hallway

**Code repo (av-orchestrate cwd / worktrees):** `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`  
**Artifact / Step 10 repo:** `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback`

Do **not** run `/av-orchestrate` from piggyback. That would spawn a piggyback worktree and fight Bucket 5 (`codegraph/src/mcp/**`). Plan `## Files` are abs paths under falkor-writ; a piggyback WT would still write **falkor-writ `main`**. Isolate with a **falkor-writ** worktree.

Open the Cursor chat **in falkor-writ** (or its new worktree). Read piggyback `STATE.md` by abs path.

---

## Parallel with Bucket 5 — do not collide

Bucket 5 **already in flight**: piggyback `.worktrees/bkt5-codegraph-mcp`, daemon `:19851`, MCP fork. Leave it alone.

**Never:**

- Edit `codegraph/src/mcp/**`, piggyback `.worktrees/bkt5-*`, `*bkt5*` artifacts
- Pin or stop `VILLAGE_PORT=19851` / `:19831` / `:19391` / `:19641`. Never `:8877`
- `git add -A` on **piggyback `main`** (Bkt6 paper sits uncommitted next to other dirt) or on **falkor-writ `main`** (session-json junk + other WTs)
- Touch existing falkor-writ trees `improv-pipeline2-supervisor*` / `improv-track-i*`
- `npm i -g @colbymchenry/codegraph` / `codegraph upgrade`
- Overwrite `~/.cursor/hooks/writ-blast-gate.sh` or any `hooks.json` / `install.sh --all/--only`
- **rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1`** — Bkt5 pickup; you **need** today’s live `codegraph init` for WAL tests
- AST one-opener walk (C1 ABSORB = wrap real `sqlite3.connect`)
- Post-init `codegraph index`; delete `.codegraph/codegraph.db`

**Step 10 last:** piggyback `docs/TECH_DEBT.md` dated note only. Status stays OPEN. Surgical path add. Do not rewrite piggyback `STATE.md`/`CLAUDE.md` on `main` (Bkt5 §10 may touch the phase-branch copies).

---

## Docs commit (piggyback, surgical) then falkor-writ branch

Paper already on piggyback disk, **uncommitted**. Before or after wave 1:

```
cd /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback
git add \
  docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md \
  docs/AI_artifacts/4_specs/2026-08-19-bkt6-writ-probe.md \
  docs/AI_artifacts/5_factual-code-verification/2026-08-19-bkt6-writ-probe.md \
  docs/AI_artifacts/6_plans/2026-08-19-bkt6-writ-probe.md \
  docs/AI_artifacts/7_reviews/2026-08-19-bkt6-writ-probe*.md \
  docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.md \
  docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.state.md \
  docs/AI_artifacts/_handoff/2026-08-19-bkt6-writ-probe-grill.md \
  docs/AI_artifacts/_handoff/2026-08-20-bkt6-writ-probe-impl-kickoff.md
# optional one-liners: CHANGELOG.md only if the hunk is Bkt6-only
git commit -m "docs(pipeline): Bucket 6 writ-probe design→plan"
```

**Do not add:** `STATE.md`, `CLAUDE.md`, `docs/model-scoreboard.csv`, `docs/TECH_DEBT.md`, `plan-verifier/**`, `.village/`, `*bkt5*`.

Then **falkor-writ** (dirty `main` — do not commit that dirt):

```
cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ
git worktree add .worktrees/bkt6-writ-probe -b bkt6-writ-probe main
cd .worktrees/bkt6-writ-probe
```

I2: commits on `bkt6-writ-probe`. No push. No merge to falkor-writ `main` until human.

---

## Seats (owner 2026-08-20)

| Seat | Profile | Rule |
|---|---|---|
| Daemon | reuse `:19841` `orch-bkt6-writ-probe` | I5. Pin `VILLAGE_HOST=127.0.0.1` `VILLAGE_PORT=19841`. |
| IMPL | `clx-deepseek-v4-flash` | **Fresh SID every step / fix.** Never reuse flash. I6. |
| Tier-A review | harness grok 4.6 (Cursor Task / `cursor-grok-46`) | **ONLY I9 exception.** Impl, fix, whole-diff, gather-that-writes-code = `av` only. |
| Whole-diff §9.1 | `syn-3-kimi-k3` | **One agent, no panel.** I7. |
| Judge | **new** persistent `syn-3-kimi-k3` | Do not reuse paper-pipeline `ac4ecea7` / parked `acedea6f` / `5d4207c3`. |

Front-load knowable asks **before** away. Then Impl Away I1–I9: confirm-once `defaults` + this **I9 delta** (harness grok tier-A only). Do **not** re-ask auto-cross / commit-no-push / SID freshness / solo-vs-panel / harness-ban.

UI_SCOPE=no (no §9.0). Live rsync SKIP. Cursor hook copy SKIP (OQ-5.2).

Waves (plan): A step1 → B step2 → C 3 then 4 → 5/6/7 after 2 → D step8 → E step9 → F step10 piggyback TD-01.

Locks: four-name enum; wrap `sqlite3.connect`; first URI exact `file:{db}?mode=ro`; retry `immutable=1` only on `unable to open database file`; `timeout=0`; 5a/5b no mutation; fresh recorded list per `_connect` drive.

---

## Paste-ready owner line

Read `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/docs/AI_artifacts/_handoff/2026-08-20-bkt6-writ-probe-impl-kickoff.md` and piggyback `STATE.md`.

You implement **Bucket 6 only** (writ `probe` honesty). Cwd = **falkor-writ**, not piggyback. Surgical-commit Bkt6 paper on piggyback (never `git add -A`). Then `git worktree add .worktrees/bkt6-writ-probe -b bkt6-writ-probe main` in falkor-writ. `/av-orchestrate` that tree.

IMPL=`clx-deepseek-v4-flash`, fresh SID every step. Tier-A = harness grok 4.6 **only** (I9 exception). Whole-diff = one `syn-3-kimi-k3`, no panel. Judge = new persistent `syn-3-kimi-k3`. Reuse daemon `:19841`. Front-load, then Impl Away I1–I9 `defaults` + that I9 delta.

Do not touch Bucket 5, `codegraph/src/mcp/**`, `:19851`, live `~/.codegraph` rsync, falkor-writ `improv-*` trees, or `~/.cursor/hooks/writ-blast-gate.sh`. Plan abs path: `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/docs/AI_artifacts/6_plans/2026-08-19-bkt6-writ-probe.md`.
