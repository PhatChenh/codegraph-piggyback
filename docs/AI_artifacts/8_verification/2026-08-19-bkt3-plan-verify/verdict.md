# Behavior-verify — Bucket 3 plan_verify (2026-08-19)

Plan: `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`
INT: `.village/worktrees/bkt3-plan-verify` tip `687a247`
CLI: `plan-verifier/plan_verify.py` against a fixture `make_db` (not the live repo index).

Live counterpart: yes. Evidence files in this folder.

## Walkthrough script (non-engineer)

1. Combined probe (unindexed `hooks.json` touch/new/remove + directory `docs/` + indexed `plan-verifier/plan_verify.py`) with `--db` + `--strict`. Expect: `on disk, not in index` on touch/remove, `COLLISION` on new, `MISSING` on `docs/`, indexed row not using disk evidence, exit **1**.
2. Same tree, plan with only `touch: hooks.json`, `--strict`. Expect exit **0**.
3. Plan file in a different folder, `--db` points at the fixture. Expect JSON `OK` + `on disk, not in index`, exit 0. Same plan without `--db`: stderr `error: no .codegraph/codegraph.db found walking up from the plan`, exit 2.
4. `--spec` with `runFalQueue(...)` deep + plan text `runFalQueue`. Expect no REUSE-DROPPED for that name; `AcpTransport` still REUSE-DROPPED; `--strict` exit 0.
5. Two-node symlink loop `loop/a`↔`loop/b`, `touch: loop/a`, `--strict`. Expect `MISSING` / `no node or file matches 'loop/a'`; no traceback.
6. `python3 -m pytest plan-verifier/ -q`. Expect all green.

## Verdict table

| Capability | What was done | Observed | Pass/Fail | Evidence |
|---|---|---|---|---|
| C1 / C2 walkthrough 1+5 | Combined CLI + symlink-loop CLI | touch/remove `OK` + `on disk, not in index`; `new:` `COLLISION` + same; `docs/` `MISSING`; loop `MISSING` no traceback | PASS | `01-combined-strict.txt`, `05-symlink-loop.txt` |
| C3 | Indexed `touch: src/db.py` and `plan-verifier/plan_verify.py` | Evidence `src/db.py (0 callers)` / `plan-verifier/plan_verify.py (0 callers)` — **not** `on disk, not in index` | PASS | `01-combined-strict.txt`; extra `src/db.py` CLI in orch notes |
| C4 walkthrough 3 | Plan in other temp dir + `--db` | exit 0, JSON OK, evidence `on disk, not in index`; omit `--db` exit 2 exact stderr | PASS | `03-away-plan-db-flag.txt`, `03b-away-plan-no-db.txt` |
| C5 walkthrough 1+2 | passing-only vs combined `--strict` | exit 0 vs exit 1 (COLLISION+MISSING). Not a net-fewer-failures win | PASS | `02-passing-only-strict.txt`, `01-combined-strict.txt` |
| C6 walkthrough 4 | `--spec` decorated `runFalQueue(...)` | `runFalQueue` not dropped; `AcpTransport` REUSE-DROPPED with normalized ident; exit 0 | PASS | `04-spec-reuse.txt` |
| C7 | Read ADR + design.md | (a)–(d) words present; header `Check against the index (path-only on-disk fallback)` | PASS | files in tree; `results.json` |
| C8 walkthrough 6 | pytest `plan-verifier/` | `59 passed in 1.50s` | PASS | `06-pytest.txt` |

## Human checks (copy-paste)

From the integration worktree `.village/worktrees/bkt3-plan-verify`:

```sh
python3 -m pytest plan-verifier/ -q
```

Expect: `59 passed`.

```sh
python3 plan-verifier/plan_verify.py /tmp/no-such-plan.md
```

Expect: exit 2 and `error: no .codegraph/codegraph.db found walking up from the plan` (file must exist for other errors; use a real empty file in a folder with no `.codegraph` above it).

## Merge gate

All PASS. Not a main merge — Away I2: propose only. Whole-diff kimi still in flight at time of this file; if kimi returns CHANGES_REQUESTED, orch adjudicates before the proposal.

=== END ===
