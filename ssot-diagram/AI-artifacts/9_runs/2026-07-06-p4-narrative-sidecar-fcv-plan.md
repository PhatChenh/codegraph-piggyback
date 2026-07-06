# Run report — 2026-07-06 · P4 narrative sidecar (FCV + plan)

## Summary

This run finished the "thinking" half of P4 (the narrative-sidecar feature of the
ssot-diagram tool). It resumed at fact-checking the spec against the real code, then
turned the checked spec into a step-by-step build plan. The fact-check came back clean —
nothing in the spec was wrong — so no rethink was needed. Along the way it caught a wrong
fingerprint number (a code "golden hash") that had been copied into three project docs,
and fixed it in all three. The plan was double-checked by a machine gate that confirms
every function it names actually exists: 19 out of 19 passed. No code was written this
run — building the feature is a separate step that waits for your go-ahead.
**Worth your double-check:** the plan's two flagged judgment calls (how config/manifest
edits are guarded, and the ingest skip-message wording) — both non-blocking.

## Dispatches

| # | Model | Role | Task (one line) | Outcome |
|---|---|---|---|---|
| 1 | writ:worker (subagent; configured model) | judge/verify | factual-code-verification of P4 spec vs live code | findings-confirmed |
| 2 | writ:worker (subagent; configured model) | judge/verify | plan-from-specs → 12-Step P4 plan | pass-first-try |

Note: exact subagent model id not exposed to the orchestrator (harness env config); both
were read+verify workers, not cheap gatherers. Behavior claims re-checked by the
orchestrator directly (golden sha, `die` alias) per pipeline rule 2.

## Decisions made for you

- **Tier stayed medium** — inherited from the prior session's grill (command-per-id
  approval + scope = components/micros/important nanos); no re-classification needed.
- **FCV verdict accepted: 13 validated / 0 invalidated / 2 unverifiable.** The 2
  unverifiable (A14, A15) describe not-yet-built functions (`narrate ingest`/`approve`);
  they get real tests when built (spec T4–T6). Zero invalidated ⇒ no design loop-back
  (pipeline rule 4 satisfied). Full record: `ai-artifacts/3_factual-code-verification/p4-narrative-sidecar.md`.
- **Golden-sha finding adjudicated by orchestrator, then fixed.** Independently confirmed
  real hash `56df3d86…` ≠ the `5a1e2156…` cited in spec/CLAUDE/STATE (P3 test byte-compares
  the file on disk, so nothing was broken). Correction applied to STATE.md, CLAUDE.md,
  spec. Left as-is by design: the `9_runs/2026-07-04-p3-…md` historical report (audit
  record) and the FCV doc (which documents the mismatch).
- **Plan accepted after independent re-verification.** Re-ran `plan_verify.py --strict`
  in the main thread (not trusting the subagent's claim): PASS, 19/19 manifest claims
  resolve; 67 `swept` prose-token rows are warn-only (Block 3b), excluded from strict.
- **Two plan judgment calls recorded, not escalated** (both non-blocking, reversible):
  config/manifest step guarded by a `human:manifest-and-config-edit` gate because JSON
  isn't codegraph-indexed; ingest skip-message = single count (spec's lean).

## Escalations

- **Sha-drift handling** → owner chose "Fix sha, then plan" (corrected 3 docs, then planned).
- **Pipeline close-out** → owner chose "Run sweep + run-report."

(FCV dispatch was interrupted once by the user then resumed on "sorry, continue" — no
decision content, accidental reject.)

## Discoveries (persisted here, not auto-authored as rules)

- **Convention-gap (tooling):** the `<!-- plan-verify -->` manifest convention has no
  clean verb for steps that edit only non-code data files (JSON/config) — `touch:` on
  such a file always yields MISSING under codegraph. Plan Step 11 worked around it with a
  `note:` + `human:` gate + byte-unchanged golden qualifier. A first-class "data-file
  edit" verb would remove the ambiguity. (Not authored as a PROJ-* rule without owner
  sign-off.)
- **Tech-debt (mostly resolved):** stale golden sha `5a1e2156…` — fixed in the 3 live
  docs this run; still present in the `9_runs/2026-07-04-p3-…md` historical report by
  design (audit records are not retro-edited).

## Cost

~174.5k tokens across 2 dispatches (source: subagent usage — FCV 73.4k, plan 101.1k).
Within the medium band (100k–400k). No re-read waste flagged; plan warm-started from the
spec's Read-set + FCV doc.
