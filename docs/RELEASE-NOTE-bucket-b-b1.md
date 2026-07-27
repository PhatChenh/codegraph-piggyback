# Release note — Bucket B / B1 (diff_verify unknown-key refusal)

**Date:** 2026-07-27  
**Branch:** `dsk/orch-burden-b` (codegraph-piggyback)  
**Commits:** `fb4496a` Step 1 · `28acef9` Step 2 · `78f5507` Step 3

## What changed

`diff_verify.py --per-step` now **refuses** plan-verify blocks that declare
zero files because of an **unknown key** (most commonly the historical
`files:` YAML form). Exit code **2**, stderr prefixed with stable marker
`PLAN-MALFORMED:` (consumed by agent_village Step 3b / `av verify-wave`).

Three-way rule when `files == []`:

| Case | Behaviour |
|---|---|
| unknown keys present | refuse — `PLAN-MALFORMED:` + exit 2 |
| no unknown keys, ≥1 claim (symbols only) | warn on stderr; exit 0 |
| no unknown keys, no claims (gate-only) | silent pass; exit 0 |

Wave-end `verify()` emits a **`MANIFEST-EMPTY` finding** (not a note) when
`declared_paths()` is empty and unknown-key `meta_problems` exist — outside
the `--allow` admission path so widening globs cannot clear it.

## Consumer impact (every repo using `AV_DIFF_VERIFY`)

`av verify-wave --preflight` runs `--per-step`. Plans still using `files:`
will stop at preflight with exit 1 (until agent_village Step 3b lands, the
headline may still say "failed to run" — Step 3b rewrites that to
**plan malformed**).

**No village-only carve-out.** Repair defective manifests to `touch:` / `new:`
(and `path::symbol` or `./av` for extensionless paths).

## Tests

- `python3 -m pytest _shared/test_manifest.py diff-verifier/ -q` green
- Fixtures: `diff-verifier/fixtures/{unknown_key,gate_only,symbol_only}.md`
- agent_village `test/verify-wave-cert.test.ts` re-run against this tip before W2

## Not yet

- agent_village Step 3b (message path: "plan malformed" vs "tooling broken")
- Steps 4–7 (Bucket B W2/W3)
