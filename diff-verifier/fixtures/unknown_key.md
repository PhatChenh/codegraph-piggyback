# Fixture plan — unknown-key defect (capability C-05)

Proves `--per-step` refuses (exit 2) when a step declares paths under an
unknown manifest key — the §0.4 defect class (17/17 known-bad historical
steps: `av-ux-opt-shell-allow-circuit.md`, `2026-07-24-av-token-burn-mini.md`,
`2026-07-25-av-pause-cost-fixwave.md`).

Run from the worktree root:

    python3 diff-verifier/diff_verify.py \
        diff-verifier/fixtures/unknown_key.md --per-step

Expected: exit 2; stderr begins with the `PLAN-MALFORMED:` marker; one line
per offending step naming the step id + the unknown key (`'files'`).
Stdout is empty (no JSON payload on refusal).

### Step 1 — declare paths via the wrong key

<!-- plan-verify
files: src/auth.py, tests/test_auth.py
tier: B
-->

### Step 2 — correct step in the same plan (sanity)

<!-- plan-verify
touch: src/db.py::get_conn
new:   src/db.py::get_pool
tier: A
-->
