# RUN_STATE — Bucket 4 codegraph CLI
_Parent scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## kickoff — 2026-08-17 10:00
POSITION: Stage 1 done (scout skip). Stage 2 grill Step 1 — waiting owner confirm of inherited frame.
ARTIFACTS: this file; `.village/runs/2026-08-17-bkt4-codegraph-cli/protocol-card.md`
DECIDED: seats per protocol-card; landmine scout skipped; LIGHT grill in this Cursor thread
DEFERRED: grill Step 1 adopt/replace; wave-1 design questions
OPEN: none

## stage2-q0 — 2026-08-17 10:05
POSITION: Stage 2 grill — frame adopted (0-a). Wave 1 out.
ARTIFACTS: none new
DECIDED: inherit scope IN/OUT/locks; no re-split
DEFERRED: wave-1 design questions (unusable definition, init positional ${}, corrupt wipe, ADR)
OPEN: none

## stage2-wave1 — 2026-08-17 10:19
POSITION: Stage 2 grill — wave 1 locked except Q3 (re-ask after owner correction).
ARTIFACTS: none new
DECIDED: 1-a refuse ${} on init positional too; 2-a empty-or-unreadable indexes, healthy skips; 4-a write init-repairs ADR; C1 hard error names literal, no cwd, nonzero
DEFERRED: Q3 smashed-db (owner: wipe may just be re-index)
OPEN: Q3 only

## stage2-wave2 — 2026-08-17 10:22
POSITION: Stage 2 grill — solution map DRAFT; waiting owner “nothing missing.”
ARTIFACTS: docs/AI_artifacts/_handoff/2026-08-17-bkt4-codegraph-cli-grill.md
DECIDED: 3-c replace smashed codegraph.db only; locked/busy → error no wipe
DEFERRED: Step 6 confirm
OPEN: none

## stage2-close — 2026-08-17 11:07
POSITION: Stage 2 LOCKED. Stage 3 LIGHT verified. Next: design-lite dispatch.
ARTIFACTS: docs/AI_artifacts/_handoff/2026-08-17-bkt4-codegraph-cli-grill.md (LOCKED)
DECIDED: owner close; LIGHT holds (one CLI surface; Q3-c resolved; no UI; no new MCP/writ contract)
DEFERRED: none
OPEN: none

## stage3 — 2026-08-17 11:07
POSITION: Stage 3 pass. Next: thin-stamp judge then design (`claude-opus`, code-read light-plan).
ARTIFACTS: none new
DECIDED: LIGHT PLAN — design-lite → RT → spec → FCV → plan. No ux-pipeline.
DEFERRED: judge thin stamp
OPEN: none

## stage4-design-dispatch — 2026-08-17 11:08
POSITION: Stage 4 design-lite in flight. SID a7a1ef7e-6565-470f-947c-0a179adeeb5a (`claude-opus`).
ARTIFACTS: .village/runs/2026-08-17-bkt4-codegraph-cli/channel/DESIGN.md
DECIDED: judge thin stamp YES
DEFERRED: design artifact + review brief
OPEN: none

## stage4-design-returned — 2026-08-17 11:31
POSITION: Design on disk. Review brief out. Waiting owner approve + proceed to RT.
ARTIFACTS: docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md
DECIDED: none this boundary (owner still signs Option A + OQs)
DEFERRED: design approve; OQ-1/2/3; proceed to RT
OPEN: none

## away-arm — 2026-08-17 11:34
POSITION: Away armed. Design approved. Mini-RT then big RT.
ARTIFACTS: none new
DECIDED: owner "run to done"; Away D1–D8 defaults; Option A; OQ-1 directory.ts; OQ-2 name daemon; OQ-3 no prompt; exit 0 Crit, Major→spec OQs; SPEC-ABSORB allowed
DEFERRED: none
OPEN: none

## stage4-minirt-1 — 2026-08-17 11:51
POSITION: Mini-RT not green. Design patch in flight (same opus SID). Strong RT blocked.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-mini-rt.md
DECIDED: findings are craft inside Option A (away A2.1 auto-patch); not a direction Crit
DEFERRED: re-run tier 0 + mini-RT after patch
OPEN: none

## stage4-minirt-2 — 2026-08-17 12:00
POSITION: Mini-RT-2 not green (round-1 classes closed). Design patch 2 in flight.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-mini-rt-2.md
DECIDED: residuals are craft (hash vs mtime; unclassified fixture; errcode-1 not wholesale delete)
DEFERRED: mini-RT-3 after patch
OPEN: none

## stage4-minirt-3 — 2026-08-17 12:12
POSITION: Mini-RT-3 not green; round-2 classes closed. Design patch 3 in flight (last craft pass).
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-mini-rt-3.md
DECIDED: F1 named-symbol not count; F2 unreadable snapshot sentinel; F5/F6 constructor-in-try + message-gated errcode 1
DEFERRED: mini-RT-4; if still open, judge stamp on Spec-MUST absorb vs another loop
OPEN: none

## stage4-minirt-4 — 2026-08-17 12:25
POSITION: Mini-RT-4 residuals patched by ORCH. Awaiting judge fat stamp then big RT.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-mini-rt-4.md
DECIDED: skip mini-RT-5 (cascade); ORCH patched main→greet + calls-kind + external known-answer digest; F4/F5 sentinel → Spec MUST
DEFERRED: judge fat stamp
OPEN: none

## stage4-rt-fatstamp — 2026-08-17 12:36
POSITION: Judge fat stamp YES. Predispatch green. Big design RT dispatch next.
ARTIFACTS: docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md (C14 rewrite: SQLite codes not `errcode=N`; probe busy_timeout=500 (today) vs production 5000); receipt `.village/audit/422ca8f3ec479b3ec0ac48beb5026da408a7c1d7607c91cfaba6b258f281cafe.receipt`
DECIDED: skip mini-RT-5; 0 direction-Crit; F4/F5 → Spec MUST; C11-NOCALLERS advisory OK (test assertion surface)
DEFERRED: none
OPEN: none

## stage4-rt-1 — 2026-08-17 13:00
POSITION: Big RT returned 0 Crit / 8 Major. ORCH patched M1–M8 into design. Awaiting judge fat stamp then spec.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-design-redteam.md (harvested from side worktree); design patched
DECIDED: no second RT (D7 + cascade); OQ-1/2/3 CLOSED in artifact; probe unexported + readonly; write-path never unlink on non-5; stale-WAL under-delete gate
DEFERRED: judge fat stamp
OPEN: none

## stage4-spec-dispatch — 2026-08-17 13:05
POSITION: Judge YES on RT exit. Spec dispatch next (fresh cursor-grok-46).
ARTIFACTS: receipt `.village/audit/86cb6474bd605f7831a18c94ab77a2bab36ded3442e9db077ec51b398e2bb0b4.receipt`
DECIDED: 0 Crit; M1–M8 in design text; proceed spec
DEFERRED: none
OPEN: none

## stage4-spec-nonconv — 2026-08-17 13:12
POSITION: Spec SID 7714a7e6 non_convergence (5× unapproved codegraph_explore). Second SID 8dca0484 Connection stalled, no spec on disk.
ARTIFACTS: `.village/runs/2026-08-17-bkt4-codegraph-cli/handoff/TOOL_ISSUE_spec-nonconv.md`
DECIDED: judge YES — fresh SID, Read-only, MCP stripped from worktree
DEFERRED: none
OPEN: spec artifact

## stage4-spec-dispatch-3 — 2026-08-17 13:39
POSITION: Third spec SID `5896d1a9-08b0-4dda-b713-c7860a6ecaff` turn in flight (MCP emptied in worktree).
ARTIFACTS: none yet
DECIDED: same SPEC.md (no MCP)
DEFERRED: none
OPEN: spec artifact

## stage4-spec-orch-discarded — 2026-08-17 13:49
POSITION: Owner discarded ORCH-authored spec. Redispatch `cursor-grok-46`.
ARTIFACTS: `docs/AI_artifacts/4_specs/2026-08-17-bkt4-codegraph-cli.md` deleted
DECIDED: spec seat stays grok-46; ORCH must not author Stage-4 artifacts
DEFERRED: none
OPEN: spec artifact

## stage4-spec-paused — 2026-08-17 14:02
POSITION: PAUSED. Fourth grok-46 spec SID `26689b53` also `RetriableError: Connection stalled`. No spec on disk. Waiting owner.
ARTIFACTS: empty `docs/AI_artifacts/4_specs/`
DECIDED: do not redispatch; do not ORCH-author spec
DEFERRED: spec seat / split-turn / this-chat write
OPEN: owner pick

## stage4-spec-dispatch-5 — 2026-08-17 14:25
POSITION: Owner: grok-46 again, Codegraph banned. SID `f5812519-7fad-46a7-ad35-48189d4b3648`. MCP emptied. Skill CodeGraph-first waived in SPEC.md.
ARTIFACTS: none yet
DECIDED: no MCP, no `codegraph` CLI
DEFERRED: none
OPEN: spec artifact

## stage4-spec-on-disk — 2026-08-17 14:35
POSITION: Spec on disk. Grok wrote it; claims DENY parked it in worktree denied-writes; `--strict` green; ORCH copied those bytes to `4_specs/` (not authored). Next: FCV when owner says (last instruction was this redispatch only).
ARTIFACTS: docs/AI_artifacts/4_specs/2026-08-17-bkt4-codegraph-cli.md
DECIDED: Codegraph banned for this seat; no MCP used
DEFERRED: FCV+plan
OPEN: none

## stage4-fcv-dispatch — 2026-08-17 14:48
POSITION: Owner: continue; grok-46 may use Codegraph; ORCH must approve pauses (exit 11 ≠ fail).
ARTIFACTS: docs/AI_artifacts/4_specs/2026-08-17-bkt4-codegraph-cli.md
DECIDED: Codegraph allowed this FCV seat; approve from live inbox
DEFERRED: plan after FCV
OPEN: FCV artifact

## stage4-fcv-returned — 2026-08-17 15:04
POSITION: FCV on disk. 16 validated, **A13+A19 invalidated**. Plan blocked until spec patch + FCV re-check. Same grok SID `481dc733` for spec patch (FCV+plan seat).
ARTIFACTS: docs/AI_artifacts/5_factual-code-verification/2026-08-17-bkt4-codegraph-cli.md (harvested; claims --strict OK)
DECIDED: Codegraph allowed; 5 Shell pauses approved from live inbox this turn
DEFERRED: plan until A13/A19 rewritten
OPEN: spec patch A13/A19

## stage4-plan-on-disk — 2026-08-17 15:32
POSITION: Spec patched (A13=266, A19=open/unresolved_refs). FCV re-check 17 validated / 0 invalidated. Plan on disk. SID `481dc733-f50d-473e-9142-5fcc155c697d`. Next: Stage 5 docs commit (no push) then implement — not started this turn.
ARTIFACTS: docs/AI_artifacts/4_specs/… (patched); docs/AI_artifacts/5_factual-code-verification/… (re-check); docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md
DECIDED: Codegraph allowed; every exit-11 this SID approved from live inbox
DEFERRED: docs commit; implement
OPEN: none

## stage5-docs-commit — 2026-08-17 15:53
POSITION: Stage 4 LIGHT docs complete. Docs commit this turn; no push. Implement not started.
ARTIFACTS: design, spec, FCV, plan, mini-RT 1–4, design RT, grill, RUN_STATE
DECIDED: no push
DEFERRED: implement
OPEN: none

## impl-away-frontload — 2026-08-17 18:14
POSITION: STATE.md was stale (said RT in flight). Pipeline already Stage-5. Impl Away armed. Docs sync this turn, then isolated WT + Wave A.
ARTIFACTS: this ledger; STATE.md; CLAUDE.md Build Progress; scope progress; CHANGELOG 2026-08-17
DECIDED:
  Impl Away defaults: ACCEPTED 2026-08-17 with **I9 DELTA**.
  I1 auto-cross waves. I2 commit on phase branch, **no push / no main merge**. I3 no ORCH spend cancel. I4 hard-stop list as card. I5 reuse labeled daemon `orch-bkt4-cg-cli` `:19817` if live else new same label (never `:8877`). I6 FRESH IMPL SID every step/fix. I7 solo whole-diff, no panel. I8 approve-pump on Cursor **av** seats if any. **I9 DELTA (owner kickoff):** harness Task subagent allowed **only** for grok 4.6 **tier-A review**. Impl, fix, whole-diff, judge, gather = `av` only.
  Seats (owner): IMPL `cmd-pro` class impl; fallback `clx-deepseek-v4-pro` same-tier spawn-fail only. Tier-A REVIEW = Cursor grok 4.6 harness subagent (not `av`). WHOLE_DIFF `syn-2-kimi-k3`. JUDGE `claude-opus` persistent. ORCH = this Cursor grok 4.6 (strong-in-ORCH waste warn recorded; owner chose).
  Seat distinctness attested by owner naming four different profiles/harness.
  UI_SCOPE=no (CLI, no UX). Live spend bound **$0** paid APIs. Step 7 livecert = local vitest + **one** rsync `codegraph/dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/` + local `codegraph` refuse/repair; never `npm i -g` / `codegraph upgrade`. Fix-round cap = skill default 2 then escalate. Behavior-verify = plan E2E + Step 7 local live; no remote provider. OQ-4 stays 500 (plan lock). TD-01 stays OPEN. Plan has no `gates: human:*`.
  Tier-A checklist (Steps 2, 4, 5): AUTH/MONEY/MIGRATION = no. Step 4 changes operator-visible `init` behavior (already tagged A). Step 2 new probe (not barrel/MCP). Step 5 tests-only tagged A for repair-proof. No silent down-tier.
DEFERRED: none knowable in advance. Runtime-only: verify-wave 20–23 diffs, livecert FAIL retry, spawn-fail after 3+fallback.
OPEN: none — leftovers recorded as recommended and locked this kickoff

