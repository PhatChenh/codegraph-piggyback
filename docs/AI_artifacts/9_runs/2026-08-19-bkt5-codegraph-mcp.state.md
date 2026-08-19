# RUN_STATE — Bucket 5 codegraph MCP missing vs empty
_Parent scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`

## kickoff — 2026-08-19 14:38
POSITION: Stage 1 skip recorded. Stage 2 design grill + away front-load waiting owner. No design dispatch until answers. No village daemon yet.
ARTIFACTS: this file; `.village/runs/2026-08-19-bkt5-codegraph-mcp/protocol-card.md`
DECIDED: next bucket = 5 (FULL, ITEM-1-cg); landmine scout skip (piggyback discrete landmines are ssot phases A–I; scope scout already covered ITEM-1-cg); ORCH conducts FULL grill in this Cursor thread (human here; judge stamps the lock); no new lib; seats owner-pinned this turn
DEFERRED: grill Q0–Q5 + C1–C2; Away defaults D1–D8; run-specific R1–R5
OPEN: owner answers; JUDGE_SESSION not created; daemon not started

## stage2-close — 2026-08-19 15:03
POSITION: Stage 2 LOCKED. Stage 3 FULL verified. Away D1–D8 accepted. Next: labeled daemon `:19851` + JUDGE_SESSION seed + design.
ARTIFACTS: docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md ; .village/runs/2026-08-19-bkt5-codegraph-mcp/protocol-card.md
DECIDED: 0-a adopt; 1-a junk→missing busy→empty-style; 2-a COUNT at handshake; 3-a import+map; 4-a session+proxy; 5-a user `codegraph init`; C1-a one pipeline; C2-a TD-01 OPEN; Away defaults; R1-a `:19851`; R2 band-2 harness grok 4.6; R3-a kimi judge fallback; R4-a vitest spawn = live; R5-a piggyback artifacts
DEFERRED: none for grill. R4 live narrowed as craft (no extra ORCH-operated cert)
OPEN: daemon + JUDGE_SESSION

## stage3 — 2026-08-19 15:03
POSITION: Stage 3 pass. FULL holds: MCP initialize + tools/list consumed by Cursor ACP and Claude MCP; empty-db looking indexed is silently-wrong; one surface (payloads) with two doors; no UI; HA locked (copy + live=tests). Steps: design → RT → spec → FCV → plan.
ARTIFACTS: none new
DECIDED: FULL PIPE — no ux-pipeline; no re-tier; Q4-a is not an A-split
DEFERRED: none
OPEN: daemon + judge seed + design dispatch

## away-arm+daemon — 2026-08-19 15:06
POSITION: Away armed. Daemon live. Next: JUDGE_SESSION seed+stamp then design.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/JUDGE_SEED.md
DECIDED: Away D1–D8 ACCEPTED; daemon orch-bkt5-codegraph-mcp pid=74904 port=19851; do not stop :19841 :19831 :19391 :19641
DEFERRED: none
OPEN: JUDGE_SESSION create

## stage4-design-dispatch — 2026-08-19 15:06
POSITION: Judge SID live. Seed+thin stamp in flight.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/JUDGE_SEED.md
DECIDED: JUDGE_SESSION=2f1f7b26-5c9c-4da8-998c-a9eaf1f35f98; cwd piggyback
DEFERRED: none
OPEN: judge YES then design SID

## stage4-design-sid — 2026-08-19 15:08
POSITION: Judge YES. Design SID live. Turn starting.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/DESIGN.md
DECIDED: DESIGN_SID=2a956eaa-2936-4d34-8121-fc33de430019 syn-3-kimi-k3; thin stamp YES design full-pipe
DEFERRED: none
OPEN: design artifact on disk

## stage4-design-landed — 2026-08-19 15:37
POSITION: Design on disk (276 lines). Next: judge thin stamp then mini-RT.
ARTIFACTS: docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md
DECIDED: Option A mcp index-state helper; claims --strict 0 DENY 2 C11 WARN (advisory; production caller `bin/codegraph.ts:1597` named in Assumptions #12); ddc alts:min2 waived (Options A–E as ### headings, checker wants [-*] bullets)
DEFERRED: OQ-1..4 craft/FCV
OPEN: judge stamp + mini-RT

## stage4-minirt-dispatch — 2026-08-19 15:40
POSITION: Judge YES. Mini-RT in flight.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/MINI_RT.md ; .village/audit/afa0140ce4ad36027af16598866836519ee8bc208c47cadd2aa1011d2fb7c91d.receipt
DECIDED: thin stamp YES; receipt afa0140c (C14 Option A vs B maintenance contrast FP); flash via av; wall 10 min → skip to big-RT if timeout
DEFERRED: none
OPEN: mini-RT report on disk

## stage4-minirt-sid — 2026-08-19 15:41
POSITION: Mini-RT SID live. Turn starting.
ARTIFACTS: none new
DECIDED: MINIRT_SID=bba5dadb-f4fb-4d5f-918a-d9996b08419c clx-deepseek-v4-flash
DEFERRED: none
OPEN: mini-RT report on disk

## stage4-minirt-landed — 2026-08-19 15:44
POSITION: Mini-RT 0 Crit / 3 MAJOR / 3 MINOR. Patching design then big-RT.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-mini-rt.md
DECIDED: M1/M2/M3 HOLD (craft). M1 proxy.ts:298/301 unverified by test. M2 mcp-initialize asserts handshake shape only. M3 watcher-seq test cannot see COUNT→openSync. m1 worktree.ts:89,103 MCP-served copy IN; site/CHANGELOG OUT. m2 folds into M2. m3 close OQ-1 as A.
DEFERRED: none
OPEN: design patch then big-RT

## stage4-minirt-patch-dispatch — 2026-08-19 15:45
POSITION: Judge YES. Mini-RT design patch in flight on existing kimi SID.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/DESIGN_PATCH.md
DECIDED: thin stamp YES; DESIGN_SID=2a956eaa remains (mini-RT ≠ big-RT count)
DEFERRED: none
OPEN: patched design on disk

## stage4-minirt-patch-reseat — 2026-08-19 15:48
POSITION: Old design SID idle-unload warmup timeout. Fresh SID in flight.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/handoff/TOOL_ISSUE_kimi-idle-respawn.md
DECIDED: DESIGN_SID=19ddfa89-66cd-4c4d-b734-6cafec0bd775 syn-3-kimi-k3 (was 2a956eaa); same DESIGN_PATCH.md; do not retry dead warmup
DEFERRED: none
OPEN: patched design on disk

## stage4-patch-landed — 2026-08-19 16:02
POSITION: Mini-RT patch on disk (296 lines). Next: judge stamp then big-RT r1.
ARTIFACTS: docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md
DECIDED: BT-1 stub proxy test; BT-2 MCP payload asserts; BT-3 no heavy open before sendResult; BT-4 worktree copy; OQ-1/OQ-4 CLOSED A; claims 0 DENY 2 C11 WARN (same advisory)
DEFERRED: none
OPEN: judge stamp + big-RT

## stage4-rt1-dispatch — 2026-08-19 16:04
POSITION: Judge YES. Big-RT r1 in flight (harness grok 4.6).
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/RT_BRIEF.md ; .village/audit/2d28c8eb2470fe452170b21d55f00e121ed5803462eab4ce301482794c3fe4a8.receipt
DECIDED: thin stamp YES; receipt 2d28c8eb (C14 Option A vs B maintenance contrast FP); first big-RT (mini-RT does not count)
DEFERRED: none
OPEN: r1 report on disk

## stage4-rt1-landed — 2026-08-19 16:15
POSITION: Big-RT r1: 0 CRITICAL / 4 MAJOR. Auto-redesign loop 1/2.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-design-redteam.md
DECIDED: M1–M4 HOLD (craft). M1 both doors nonempty from getStaticTools no engine wait. M2 probe-throw → existence fallback not missing. M3 pending getDaemonSocket stub. M4 return {state, busy}. m1 UNINDEXED must not claim dir absent; m3 EMPTY must not say tools unavailable. m2/m4/m5 → spec.
DEFERRED: none
OPEN: design patch then RT r2

## stage4-rt1-patch-dispatch — 2026-08-19 16:17
POSITION: Judge YES. Fresh kimi SID patching RT r1 M1–M4 (loop 1/2).
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/DESIGN_PATCH_RT1.md ; .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/JUDGE_STAMP_RT1.md
DECIDED: DESIGN_SID=2456a894-67ee-4531-a82e-4f48d0e4081f (fresh; 19ddfa89 past idle TTL, not D6 refresh — count stays 1/3). D7 already 0 Crit; if r2 craft-only, exit to spec not loop 2/2. Verify BT-1–BT-4 survive.
DEFERRED: none
OPEN: patched design on disk

## stage4-rt1-patch-landed — 2026-08-19 16:41
POSITION: Design patch on disk (317 lines). Kimi usage_limit (exit 5) after last Edit. Next: judge stamp then big-RT r2.
ARTIFACTS: docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md ; .village/runs/2026-08-19-bkt5-codegraph-mcp/handoff/TOOL_ISSUE_kimi-usage-limit.md
DECIDED: BT-1–BT-6 present; M1–M4 folded. Did not retry Synthetic. ORCH closed leftover Risks throw→missing vs G-10/BT-6. D7 still 0 Crit from r1.
DEFERRED: none
OPEN: judge stamp + RT r2

## stage4-rt2-judge-fallback — 2026-08-19 16:48
POSITION: Opus judge session-limit until 18:50. Thin stamp on cursor-gpt-sol (kimi/Synthetic also 429).
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/handoff/TOOL_ISSUE_judge-session-limit.md ; receipt 7472d079
DECIDED: JUDGE_FALLBACK=683392bb-dfbc-4cc2-adef-9e24738a91b9 cursor-gpt-sol; do not retry opus before 18:50; do not spawn Synthetic. Receipt for patched hash.
DEFERRED: none
OPEN: YES then RT r2

## stage4-rt2-dispatch — 2026-08-19 16:49
POSITION: Fallback judge YES. Big-RT r2 in flight (harness grok 4.6).
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/RT_BRIEF_R2.md ; .village/audit/7472d079e5a1850d5d69ef50a7a81248a74299010d2c83443c161ed8b145e81f.receipt
DECIDED: thin stamp YES via cursor-gpt-sol; C9 WARNs = m2/m4/m5 already routed to spec; C11 same advisory as r1; ddc alts:min2 waived (A–E as ### headings)
DEFERRED: none
OPEN: r2 report on disk

## seats-owner-16:53 — 2026-08-19 16:54
POSITION: Owner: judge+design both `syn-3-kimi-k3`; usage solved. RT r2 still in flight.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/protocol-card.md
DECIDED: JUDGE_SESSION=4a6f6577-3fa9-4c87-962c-d4aecc68de7f; DESIGN_SID=4bcf89b3-8238-4959-85a7-33b6073c4cdf. Same-model warn accepted. Retired opus `2f1f7b26` + gpt-sol `683392bb` (stopped). Do not revive `2456a894`.
DEFERRED: none
OPEN: r2 report; next stamp/patch on these SIDs

## stage4-rt2-landed — 2026-08-19 16:59
POSITION: Big-RT r2: 0 CRITICAL / 3 MAJOR. Fat stamp for D7 exit vs loop 2/2.
ARTIFACTS: docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-design-redteam-r2.md
DECIDED: M1–M3 HOLD (craft). M1 BT-5 names≠bytes + spy fights G-03. M2 Implications :131 throw→missing leftover + getCodeGraph extra COUNT. M3 session busy copy unpinned. Recommend EXIT (prior stamp: craft-only r2 → spec, not loop 2/2).
DEFERRED: none
OPEN: judge EXIT or LOOP

## stage4-rt-exit — 2026-08-19 17:00
POSITION: Judge EXIT. Spec next. Design SID unused.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/JUDGE_STAMP_RT2.md ; .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/SPEC.md
DECIDED: D7 0 Crit. Binding Spec OQs = r2 M1–M3 (byte-equal getStaticTools + no await on list; kill :131 + helper for getCodeGraph; session busy copy). OQ-2/OQ-3/TD-01 stay open. Next: spec harness grok 4.6.
DEFERRED: none
OPEN: spec on disk

## stage4-spec-dispatch — 2026-08-19 17:01
POSITION: Spec in flight (harness grok 4.6).
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/SPEC.md
DECIDED: EXIT locked; binding OQs 1–3 in spec brief
DEFERRED: none
OPEN: spec on disk

## stage4-spec-landed — 2026-08-19 17:14
POSITION: Spec on disk (320 lines). Next: judge stamp then FCV+plan.
ARTIFACTS: docs/AI_artifacts/4_specs/2026-08-19-bkt5-codegraph-mcp.md
DECIDED: MUST-1/2/3 carried; A1–A20; claims --strict 0 DENY. OQ-2/OQ-3/TD-01 OPEN.
DEFERRED: none
OPEN: judge stamp + FCV+plan

## stage4-fcv-plan-dispatch — 2026-08-19 17:16
POSITION: Judge YES. FCV+plan shared Task in flight.
ARTIFACTS: .village/runs/2026-08-19-bkt5-codegraph-mcp/channel/FCV_PLAN.md
DECIDED: thin stamp YES; plan only if FCV Invalidated Assumptions empty
DEFERRED: none
OPEN: FCV (+ plan if clean)

## stage4-plan-landed — 2026-08-19 17:36
POSITION: FCV clean. Plan on disk (8 steps). Stage 4 paper pipeline complete pending stamp.
ARTIFACTS: docs/AI_artifacts/5_factual-code-verification/2026-08-19-bkt5-codegraph-mcp.md ; docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md
DECIDED: ORCH plan_verify --strict exit 0 (17/17 manifest OK). Claims OK. REUSE-DROPPED handleInitialize = FP (Step 3 touches it). D1 ends at plan — no impl this stamp.
DEFERRED: none
OPEN: judge stamp then Stage 5 INCOMPLETE report

## stage5-report — 2026-08-19 17:38
POSITION: Stage 4 paper complete. Run-report INCOMPLETE. Impl waiting owner go.
ARTIFACTS: docs/AI_artifacts/9_runs/2026-08-19-bkt5-codegraph-mcp.md
DECIDED: Judge YES Stage 5 INCOMPLETE. D1 ends at plan.
DEFERRED: impl 8-step plan
OPEN: owner “implement”



















