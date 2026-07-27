# Fixture plan — symbol-only step (capability C-05c)

Proves `--per-step` warns (does NOT refuse) when a step declares only bare
symbols — the documented form per `iter_blocks` docstring (the consumer
re-queries via the codegraph DB). `touch: av` looks path-ish but is the §0.1
extensionless-path trap: `looks_pathish` correctly classifies it as a symbol.
D1's three-way rule: case 2 — warn, do not refuse.

Run from the worktree root:

    python3 diff-verifier/diff_verify.py \
        diff-verifier/fixtures/symbol_only.md --per-step

Expected: exit 0; stdout is the JSON record list (1 record with
`files: []`); stderr carries the warning line (no `PLAN-MALFORMED:`
marker — that prefix is reserved for the REFUSE path).

### Step 1 — bare symbol (documented form, warns not refuses)

<!-- plan-verify
touch: av
new: .tier-floors
tier: B
-->
