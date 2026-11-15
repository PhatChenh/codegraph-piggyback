# diff-verifier — Design

**Status:** built 2026-07-05 (same change as plan-verifier). **Effort:** S.
**Build order:** #3b (BLUEPRINT §2.5, added 2026-07-04 for the M3-fleet workflow).
**Consumer:** the orchestrate skill's wave-end stage (agent_village roadmap P8);
runnable standalone anytime.

---

## What it is

plan-verifier (§2.2) checks plan-vs-DB *before* approval; CI checks tests.
Nothing checks **diff-vs-plan after implementation** deterministically. When a
cheap-model fleet implements, the wave-end "did it do what the plan said"
review is mostly a mechanical question — and per BLUEPRINT principle 3, a
script must answer it, not an LLM (least of all the model that wrote the diff,
principle 2).

`diff_verify.py <plan.md> --diff <base>..<head>` reads the SAME
`<!-- plan-verify -->` manifest (parser: `_shared/manifest.py` — extracted the
moment this tool became its second consumer) and verdicts the diff against it.

## Verdict table (the contract — BLUEPRINT §2.5)

| Check | Verdict when wrong |
|---|---|
| every changed file ∈ the declared file list (claim paths) ∪ `--allow` globs | `OUT-OF-SCOPE-TOUCH` |
| each `qualifiers:` entry runs clean | `QUALIFIER-FAIL` (named) |
| declared `new:` symbols now exist in the DB | `NOT-DELIVERED` |
| declared `remove:` symbols now gone from the DB | `NOT-REMOVED` |
| declared test files (paths matching test globs) appear in the diff | `TESTS-MISSING` |

Exit 0 advisory by default; `--strict` exits 1 on any verdict. Zero LLM.

**What it deliberately does NOT catch** (stays with the phase-end strong-model
review): wrong-but-green logic, plausible misinterpretation beyond the compiled
qualifiers, quality/security. This tool buys the right to SKIP per-wave model
review on tier-B/C steps — not to skip review entirely.

## Qualifier grammar (locked 2026-07-05, owner-approved)

Restricted verbs only — deterministic, no shell execution, no injection
surface from a cheap-model-authored plan:

- `grep-absent "<literal>" <glob>` — the literal string must not appear in any
  file matching the glob (checked in the working tree at head; pattern is a
  LITERAL substring, not a regex — determinism over power).
- `byte-unchanged <path>` — the path must not appear in the diff at all.
- `diff-only-within <dir> [<dir>…]` — every changed file lives under one of
  the listed dirs (tighter than the claim-path check when a step is confined).

Raw shell was rejected: flexible, but non-deterministic and hands arbitrary
execution to whoever wrote the plan. BLUEPRINT §2.2's raw-shell example
(`grep -L …`) compiles to `grep-absent`.

## Inputs

1. Plan markdown (manifest blocks; multiple blocks concatenate).
2. The diff: `--diff <base>..<head>` (runs `git diff --name-only` in the repo)
   or `--files f1 f2 …` (explicit list — CI artifacts, tests).
3. The codegraph DB (walk-up from the plan; `--db` to override) for
   NOT-DELIVERED / NOT-REMOVED. **The DB must be re-indexed after the
   implementation** (the file watcher lags writes by ~1s; in CI run
   `codegraph index` first). `--skip-db` skips the two DB checks and says so
   in the output — a skipped check is reported, never silently passed.

## Test-file convention

A declared path counts as a test file when it matches `test_*`, `*_test.*`,
`*.test.*`, or lives under `tests/`. No declared test files → the
TESTS-MISSING check is reported as `n/a (no test files declared)`.

## Scope file (2026-11-15)

`--scope-file <path>` reads a JSON array of repo-relative path strings and
makes that exact list **the only scope authority**:

- a changed file is in scope **iff** it is in the list (exact string match
  after stripping one leading `./`); each other changed file is an
  `OUT-OF-SCOPE-TOUCH` finding, as today;
- the plan block's declared paths (`touch:` / `new:` / `remove:`) and
  `--allow` globs play **no part** in the scope decision — a path the block
  declares but the list omits is still `OUT-OF-SCOPE-TOUCH`;
- `MANIFEST-EMPTY` is unchanged; qualifiers, claims and declared-test checks
  are unchanged code. With a block that declares nothing (only a `tier:` line)
  those checks produce no finding, which is the intended use; a declared test
  file that did not change still yields `TESTS-MISSING`;
- a note records the decision: `scope decided by --scope-file (<N> exact
  paths); block paths and --allow not used for scope`.

`--scope-file` with `--allow`, or with `--per-step`, is refused (exit 2) — two
authorities for one question is the failure this option exists to avoid. A
missing file, invalid JSON, a non-list, or an item that is not a non-empty
string is `error: …` on stderr and exit 2.

**Why:** a task can carry its one authoritative file list outside the plan
(an orchestration layer's contract/BRIEF for the step) while the plan block
holds only a `tier:` line. Pattern-based widening is the wrong answer there —
the task's contract file list is the contract, and it is exact. Without this
option the only way to express that would be `--allow` globs, which admit
more than the contract and cannot express `app/[id]/page.tsx` at all
(`fnmatch` reads `[id]` as a character class).

When `scope is None` — no `--scope-file` — behaviour is byte-for-byte what it
was before this date.

## Ground rules inherited

Read-only DB via `_shared/db.py` · CLI standalone (no hook mode — wave-end is
an orchestrated call site, not an editor event) · every verdict carries
evidence (the offending file list / qualifier / symbol) · registered in
`manifest.json` (CLI-only entry, no hook events).

## Non-goals

Judging code quality · running tests (CI's job) · parsing prose (manifest
only — prose constraints must be COMPILED to qualifiers by the planner).
