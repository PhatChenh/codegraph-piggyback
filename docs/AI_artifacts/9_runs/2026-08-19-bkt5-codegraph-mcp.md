# Run report — Bucket 5 codegraph MCP missing vs empty

**INCOMPLETE** — paper pipeline (design → RT → spec → FCV → plan) is done. **Code is not shipped.** Branch is still `main` (no impl commits). Left: implement the 8-step plan, then live dist rsync.

_Date:_ 2026-08-19  
_Run-id:_ `2026-08-19-bkt5-codegraph-mcp`  
_Daemon:_ `orch-bkt5-codegraph-mcp` `:19851`

## Plain summary

The coding agent’s map currently treats “the folder exists” as “the map is ready.” Empty or junk maps still get the full playbook and full tool list, then fail later. This run wrote the recipe to tell **missing** vs **empty** vs **usable** at first handshake, on both doors (direct session and the live proxy). Design survived two red-teams (zero rethinks). Spec, fact-check, and an 8-step build plan are on disk. **Nothing in the CodeGraph binary changed yet.** Say “implement” to build it.

## Dispatch ledger

| # | Model | Role | Task | Outcome | Commit(s) |
|---|---|---|---|---|---|
| 1 | claude-opus | judge | Stage-4 seed + thin stamps | findings-confirmed | — |
| 2 | syn-3-kimi-k3 | design | Option A design | pass-first-try | — |
| 3 | clx-deepseek-v4-flash | red-team | mini-RT | findings-confirmed | — |
| 4 | syn-3-kimi-k3 | design | mini-RT patch (reseat after idle-unload) | needed-fixes | — |
| 5 | cursor-grok-4.6-high | red-team | big-RT r1 | findings-confirmed | — |
| 6 | syn-3-kimi-k3 | design | r1 patch | needed-fixes + escalated (429 mid-write; bytes landed) | — |
| 7 | cursor-grok-4.6-high | red-team | big-RT r2 | findings-confirmed | — |
| 8 | syn-3-kimi-k3 | judge | EXIT (D7); later spec/plan stamps | findings-confirmed | — |
| 9 | cursor-gpt-sol | judge | fallback thin stamp (opus capped) | findings-confirmed | — |
| 10 | cursor-grok-4.6-high | gather | spec | pass-first-try | — |
| 11 | cursor-grok-4.6-high | gather | FCV + plan | pass-first-try | — |

## Decision ledger

- Grill 0-a…5-a, C1-a, C2-a, R4-a locked; Away D1–D8 accepted. Record: `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md`.
- Option A (one mapper, import probe, both doors). r1 M1–M4 HOLD craft → patched. r2 M1–M3 HOLD craft → **EXIT to spec OQs** (D7 0 Crit; do not burn loop 2/2).
- MUST-1/2/3: deep-equals `getStaticTools()`; throw→existence fallback via helper including `getCodeGraph`; session busy copy.
- FCV: 20 ✅ / 0 ❌; C1-a no A-split. Plan: 8 steps, `plan_verify --strict` exit 0. REUSE-DROPPED `MCPSession.handleInitialize` = FP (Step 3 touches `handleInitialize`).
- Owner 16:53: judge+design both `syn-3-kimi-k3` (usage solved). Same-model warn accepted.
- D1 ends at plan — **no impl this run**.

## Escalation ledger

- Grill + away card: owner compact `0-a…5-a, C1-a, C2-a, defaults, R1-a, R2 harness grok, R3-a, R4-a, R5-a`.
- Kimi 429 / opus session-limit: owner later “usage issues solved; both seats syn-3-kimi-k3.”
- Impl start: **open** — waiting on owner “go.”

## Cost line

Heavy (11+ dispatches). ACP/cursor seats `usageUnavailable`. Visible: kimi design SID `2456a894` ~1.94M tokens / $17.49 before 429. Exact village rollup: unavailable (no Block E). Over-band likely from design↔RT loop + kimi idle-unload reseat.

## Unfinished

1. Implement `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md` (8 steps, waves A–E).
2. rsync `codegraph/dist/` → live `~/.codegraph/versions/v1.0.1/lib/dist/` after impl.
3. TD-01, OQ-2 (plan builds A), OQ-3 stay OPEN.

## Resume

Pin `VILLAGE_PORT=19851`. Plan path above. Judge `4a6f6577`, design `4bcf89b3` (both `syn-3-kimi-k3`). Do not drive opus `2f1f7b26` or dead kimi `2456a894`.
