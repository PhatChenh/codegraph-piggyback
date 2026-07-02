# Doc Coverage — Design

**Status:** not built (stub dir exists) · **Effort:** XS · **Build order:** #13 of 13
(hygiene, low urgency — explicitly "build last", bundled with dead-code-finder and the
impact pre-commit gate).

---

## What it is

Every function is supposed to carry a short description of what it does (a docstring).
When those are missing, both humans and AI agents have to read the function's body to
find out what it is for — the most expensive way to learn the cheapest fact. This tool
lists every function and method that has no docstring. It has two modes: check just the
files changed in the current piece of work (so a build pipeline can refuse to merge new
undocumented code), or sweep the whole repository (to see the overall debt). It is a
single database query with reporting around it.

## Why it exists

Serves principle 3, **determinism before inference**: "does this function have a
docstring?" is a null-check in the database — a script's job. Like its hygiene twin
dead-code-finder, its G1 payoff is indirect token saving: documented symbols let agents
(and repo-map, changeset-context, biography) work from one-line descriptions instead of
reading bodies.

Failure prevented: docstring debt accumulating invisibly — especially from cheap
implementation models that skip documentation unless something mechanical fails the
build.

## Inputs

- **The codegraph database** at `.codegraph/codegraph.db` (read-only), walk-up
  discovery. Table used:

  | Table | Load-bearing columns |
  |---|---|
  | `nodes` | `kind, name, qualified_name, file_path, start_line, docstring` |

- **Scope selector:**
  - **CI mode:** the files changed in the current diff (`git diff --name-only <base>`),
    coverage checked only there.
  - **Report mode:** the whole repo.

## Core computation

One query, two scopes. Deterministic; no LLM.

```sql
SELECT name, qualified_name, file_path, start_line
FROM nodes
WHERE kind IN ('function','method')
  AND docstring IS NULL
-- CI mode adds:  AND file_path IN (<changed files>)
ORDER BY file_path, start_line;
```

- **CI mode:** run the query scoped to changed files; any row is a failure.
- **Report mode:** run repo-wide; print everything, grouped by file, with a coverage
  summary (documented / total per `kind`).

## Output contract

The blueprint is terse — *"Exit 1 in CI mode"* — expanded:

- **CI mode:**
  - Findings printed one per line: `file_path:start_line  qualified_name — missing docstring`.
  - **Exit 1 if any changed-file function/method lacks a docstring; exit 0 otherwise.**
  - No findings → no output (quiet pass, clean CI logs).
- **Report mode:**
  - Grouped by file, same per-line format, plus a header with totals and a coverage
    percentage.
  - Always exit 0 — report mode informs, it never gates.

## Delivery

- **CLI only** — a piggyback-distributed script:
  - wired into CI as a step (CI mode is the point: it is one of the mechanical
    artifact-producers the workflow trusts instead of an agent's "I documented it"),
  - runnable manually in report mode.
- **No hook** — coverage is a gate/report concern, not moment-of-need context.
- **manifest.json entry:** script + scope + desc; no `hooks` array (CLI-only tool).

## Ground rules inherited

- **Read-only DB:** connects `mode=ro`; output is stdout + an exit code, nothing
  persisted.
- **Budgeted, fail-open — with one deliberate exception:** as a CLI it injects nothing;
  when no `.codegraph/` DB is found it exits 0 silently (fail-open) so uninitialized
  repos don't break. But **in CI mode a *findings* result is fail-closed by design** —
  exit 1 is its entire job. Only infrastructure problems fail open; findings never do.
- **Signatures as currency:** findings pin to `file:line` from the live index; nothing
  cached, nothing to drift.
- **Piggyback rail:** ships as a `manifest.json` entry; runs standalone in CI.

## Dependencies

- `_shared/db.py` — walk-up discovery + read-only connect + schema guard.
- Nothing else — it is deliberately the smallest tool in the family (XS). It does not
  even need `_shared/queries.py`; the query is a one-liner.
- **Other tools:** none. Pairs operationally with CI + test-count-guard (build-order
  #1) as another mechanical CI judge.

## Non-goals

- No judgment of docstring *quality* — presence only. (An LLM quality pass would be a
  separate, gated tool; out of scope here.)
- No auto-writing of docstrings — it reports, it never edits.
- No coverage of `kind` values beyond `('function','method')` — classes and modules are
  out of the blueprint's scope for v1.
- No percentage-threshold gating in CI mode — the blueprint's contract is binary (any
  missing → exit 1), applied only to *changed* files, which keeps the gate fair on
  legacy repos.

## Open questions

1. **[Human-judgment] Private-symbol exemption.** Should names starting with `_`
   (private helpers) be exempt in CI mode? The blueprint doesn't exempt them; strict is
   simpler, but it may make the gate annoying on tiny helpers. Recommend: no exemption
   in v1, add a flag only if friction shows up in the friction log.
2. **[Technical research] How the indexer stores "no docstring".** Verify it is
   literally `NULL` and never empty string `''` — if both occur, the predicate must be
   `(docstring IS NULL OR docstring = '')`. One query against a pilot repo settles it.
3. **[Human-judgment] CI-mode base ref.** Same question as changeset-context: default
   `<base>` for the diff (`origin/main`? auto-detected default branch?) — keep the two
   tools' answers consistent.
4. **[Technical research] Test-file exemption.** The blueprint excludes tests from
   dead-code-finder but says nothing here. Should test functions need docstrings?
   Check what the CI gate would flag on the pilot repos before deciding; if noisy,
   reuse the same test-glob list as repo-map/dead-code-finder for consistency.
