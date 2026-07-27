# Fixture plan — gate-only step (capability C-05b)

Proves `--per-step` passes silently when a step carries tier + human gate
and nothing else — the §0.7 PASS class (7 in the corpus, all correct).
A blanket zero-file refusal would have broken all 7; D1's three-way rule
keeps them passing.

Run from the worktree root:

    python3 diff-verifier/diff_verify.py \
        diff-verifier/fixtures/gate_only.md --per-step

Expected: exit 0; stdout is the JSON record list (1 record); stderr is silent
(no `PLAN-MALFORMED:`, no warning).

### Step 1 — human-signoff step (gate-only by design)

<!-- plan-verify
tier: C
gates: human:live-spend-authorization
-->
