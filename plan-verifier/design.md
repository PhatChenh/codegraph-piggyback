# plan-verifier — Design

**Status:** not built. **Effort:** M. **Build order:** #3 (after CI + test-count-guard and
ssot P2/P3; it is the first tool that triggers the `_shared/` extraction — see
`_shared/design.md`). The star tool of the "enforce careful planning" group.

---

## What it is

Before a plan is approved, this tool mechanically fact-checks it. Plans written by AI are
full of factual claims about the codebase — "modify this function in that file", "this
thing has no other users", "add a new piece here". Every one of those claims is either
true or false right now, and the codegraph database already knows the answer. plan-verifier
reads a plan document, pulls out every claim that names a piece of code, looks each one up
in the database, and prints a verdict table: this exists, this doesn't, this name matches
two different things, this thing you want to delete is used by twelve other places the plan
never mentions. No AI is involved in any verdict — it is a list of lookups, the same every
time — so the result is evidence you can trust, not another opinion.

## Why it exists

**Your single biggest exposure is approving a plan built on a hallucinated fact.** A plan
that says "edit `validate_token` in `src/auth.py`" when no such function exists sails
straight through a prose review — the sentence reads fine. Then an implementing agent burns
turns discovering the ghost, or worse, invents the function somewhere plausible and the
plan silently mutates. A SQL lookup catches the ghost in milliseconds.

Blueprint principles served:

- **Determinism before inference** (primary): the factual subset of a plan — does this file
  exist? is this name unique? who calls it? — is checkable by script, so a script checks
  it. The LLM keeps only the judgment calls.
- **Trust artifacts, not claims:** the verdict table is an artifact; "the plan looks
  correct" is a claim. This replaces one claim with one artifact at the exact gate where
  you sign off.
- **Route your attention to one-way doors:** plan approval is your gate. This tool makes
  the mechanical part of that gate free, so your attention goes to the judgment part.

**Why it saves tokens rather than costing them:** every `MISSING` caught here is an
implementation turn that will never be spent editing a file that doesn't exist; every
`BLOCKED` is a broken-caller debugging session that never happens; and `/build-pipeline`
no longer spends a whole LLM phase re-deriving facts a query answers for free.

---

## Inputs

1. **A plan document** — a markdown file (path given on the CLI, or the file just written
   when running as a hook).
2. **The codegraph index** — `.codegraph/codegraph.db`, discovered by walking up from the
   plan file's directory (same walk-up as every other tool here). No DB found → silent
   no-op (fail-open).

### Claim extraction — two tiers

**Tier 1: declared manifest (exact, preferred).** Plans adopt a tiny convention — an HTML
comment block the planner agent writes into the plan. Exact syntax:

```markdown
<!-- plan-verify
touch: src/auth.py::validate_token, src/db.py::get_conn
new:   src/auth.py::refresh_token
remove: src/auth.py::legacy_check
-->
```

- Block opens with `<!-- plan-verify` on its own line, closes with `-->`.
- Three line kinds: `touch:`, `new:`, `remove:` — each a comma-separated list.
- Entry form is `path::symbol` (a symbol inside a file), or a bare `path` (a whole file),
  or a bare `symbol` (resolved repo-wide; more likely to come back `AMBIGUOUS`).
- Multiple manifest blocks in one document are allowed; lists concatenate.
- HTML comments render invisibly, so the convention costs the plan nothing visually and
  costs the planner agent a few lines. The same manifest is the input contract for
  plan-visualizer, so writing it pays twice.

**Tier 2: heuristic sweep (fallback).** When no manifest block exists (or in addition to
it, reported separately at lower confidence): backticked identifiers and path-like tokens
in the prose, resolved against the DB the same way `decision_index bootstrap` resolves
anchor tokens — with honest `AMBIGUOUS`/`UNRESOLVED` outcomes, never a guess. Swept claims
are all treated as `touch`-class (the prose doesn't say intent), so they can produce
`MISSING`/`AMBIGUOUS`/`UNACKNOWLEDGED-BLAST` but never `COLLISION` or `BLOCKED`.

---

## Core computation

Every verdict is a pure DB lookup — no LLM anywhere in the pipeline. Resolution uses the
shared resolver (`_shared/resolve.py`); the underlying idiom is:

```sql
-- resolve a claimed token to real code (exists? ambiguous?)
SELECT id, kind, qualified_name, file_path, start_line, end_line
FROM nodes WHERE name = ? OR qualified_name = ?;
```

scoped to `file_path` when the claim carries a `path::` prefix. Caller counts use the
blast-radius idiom:

```sql
SELECT n2.name, n2.file_path, e.line
FROM edges e JOIN nodes n1 ON e.target = n1.id
             JOIN nodes n2 ON e.source = n2.id
WHERE n1.name = ? AND e.kind IN ('calls','references','imports');
```

### Verdict table (the contract)

| Claim | Check against DB | Verdict when wrong |
|---|---|---|
| `touch: X` | X exists and resolves to exactly one node/file | `MISSING` (zero matches) / `AMBIGUOUS` (more than one match) |
| `new: Y` | Y does **not** exist | `COLLISION` (a node/file with that name/path already exists) |
| `remove: Z` | Z exists, then count incoming `calls`/`references`/`imports` edges | `MISSING` if absent; `BLOCKED` when Z has N callers the plan text never mentions |
| any touched X | caller count vs plan text — does the plan's prose mention the callers (by file or symbol name)? | `UNACKNOWLEDGED-BLAST` when X has significant callers (reuse impact-analyzer's thresholds: HIGH ≥ 6, CRITICAL > 15) and none of them appear anywhere in the plan |

Claims that pass are reported `OK` with their evidence, so the table is a complete
audit — not just a list of problems.

Notes:

- `BLOCKED` vs `UNACKNOWLEDGED-BLAST`: `BLOCKED` is for removals (deleting something with
  live callers breaks them, period); `UNACKNOWLEDGED-BLAST` is advisory for touches (the
  change may be fine, but the plan shows no awareness of who depends on it).
- A `new:` name that also appears in `unresolved_refs` is worth a note ("something already
  references this name dynamically") but is not a `COLLISION` — the table above is the
  contract; extras are informational lines.

---

## Output contract

A table of claims + verdicts + evidence, printed to stdout (CLI) or injected as bounded
context (hook). Every row carries evidence: the resolved `file:line` of the definition,
and the caller count with the top caller locations. Shape:

```
── PLAN-VERIFY: docs/plans/phase-3-plan.md ── 7 claims (5 manifest, 2 swept)
  touch  src/auth.py::validate_token   OK        src/auth.py:41  (4 callers)
  touch  src/db.py::get_conn           OK        src/db.py:12    (12 callers)
  new    src/auth.py::refresh_token    OK        no existing match
  remove src/auth.py::legacy_check     BLOCKED   3 callers plan never mentions:
                                                 api/routes.py:88, cli.py:14, tests/test_auth.py:9
  touch  src/db.py::get_conn           UNACKNOWLEDGED-BLAST  12 callers, none named in plan
  swept  `parse_config`                MISSING   no node named parse_config
  swept  `Settings`                    AMBIGUOUS 2 matches: src/config.py:10, src/legacy/config.py:7
── verdict: FAIL (1 MISSING, 1 BLOCKED) ──
```

### Exit codes

- Default (advisory): always exit 0; the table is informational.
- `--strict`: exit 1 if any claim is `MISSING`, `COLLISION`, or `BLOCKED`.
  `AMBIGUOUS` and `UNACKNOWLEDGED-BLAST` warn but do not fail even in strict mode — they
  are judgment calls, and judgment calls belong to the human/LLM layer, not the gate.

---

## Delivery

Two modes, same core:

1. **CLI:** `plan_verify.py <plan.md> [--strict]` — run as a `/build-pipeline` step
   between spec and plan-approval. This is the deterministic core of the pipeline's
   factual-code-verification phase; the pipeline runs it with `--strict` and a non-zero
   exit sends the plan back before any human reads it.
2. **Hook:** `PostToolUse` on `Write|Edit`, matched on file paths `*plan*.md` or
   `docs/plans/**`. When an agent writes or edits a plan, the verdict table is injected
   immediately so the planning agent fixes ghosts in the same session, before a human
   gate is ever reached. Hook mode never blocks (advisory only) — the strict gate lives
   in the pipeline step.

Ships as a `manifest.json` entry (script + hook events + scope) so
`piggyback install/init/update` distributes it, like every other tool on this rail.

---

## Ground rules inherited

- **Read-only DB:** opens `.codegraph/codegraph.db` with `mode=ro&immutable=1` via
  `_shared/db.py`; writes nothing anywhere — its only output is text.
- **Budgeted, fail-open hooks:** hook mode is bounded (≤ ~30 lines — collapse to counts
  per verdict class when the table is longer, worst rows first), silent when every claim
  is `OK`, and never blocks the session on its own errors (no DB, unreadable plan,
  schema drift → exit quietly).
- **Signatures as currency:** resolution and identity checks go through the shared
  resolver so a "symbol" means the same thing here as in decision-index and the diagram
  model.
- **Piggyback delivery rail:** manifest entry; the CLI additionally runs standalone for
  CI and manual use.

---

## Dependencies

- `_shared/db.py` — DB discovery, read-only connect, schema guard.
- `_shared/resolve.py` — token → node resolution with `AMBIGUOUS`/`UNRESOLVED` outcomes
  (this tool is the second consumer that *triggers* the extraction from
  `ssot-diagram/decision_index.py`).
- `_shared/queries.py` — blast-radius / caller-count queries.
- `_shared/hookio.py` — hook stdin parsing + bounded fail-open output (hook mode).
- Downstream consumer: **plan-visualizer** reads the same `<!-- plan-verify -->` manifest
  and renders verdicts as warning chips — keep the manifest syntax stable; it is a
  public contract shared by two tools.

## Non-goals

- Judging whether the plan is a *good idea* — only whether its factual claims are true.
- Verifying non-code claims (schedules, requirements, prose reasoning).
- Editing or auto-fixing the plan. It reports; agents and humans fix.
- Blocking in hook mode. Blocking is opt-in via `--strict` in the pipeline step only.
- Cross-repo claims — one DB, one repo per run.

## Open questions

- **[Human-judgment]** `UNACKNOWLEDGED-BLAST` threshold: is "HIGH (≥6 callers) with zero
  callers named in the plan" the right trigger, or only CRITICAL (>15)? Too low and every
  plan yells; too high and the guard misses real exposure.
- **[Human-judgment]** Should `AMBIGUOUS` fail `--strict`? Argument for: an ambiguous
  claim means the implementer may edit the wrong symbol. Argument against (current
  choice): many repos legitimately reuse names and plans carry enough path context.
- **[Technical research]** Heuristic-sweep noise rate: on real plans in this workspace,
  what fraction of backticked tokens resolve? If `MISSING` from swept claims is mostly
  noise (pseudo-code, planned-but-undeclared names), swept claims may need to warn-only
  even in strict mode.
- **[Technical research]** How to detect "plan mentions the callers" for
  `UNACKNOWLEDGED-BLAST` — substring match of caller file/symbol names in plan text is
  the obvious deterministic choice; measure its false-negative rate before shipping
  anything fancier.
