# Dead Code Finder — Design

**Status:** not built (stub dir exists) · **Effort:** S · **Build order:** #13 of 13
(hygiene, low urgency — explicitly "build last", bundled with doc-coverage and the
impact pre-commit gate).

---

## What it is

Over time every codebase accumulates functions and classes that nothing uses anymore —
leftovers from refactors, abandoned experiments, replaced implementations. They cost
nothing at runtime but they cost plenty at *reading* time: every AI agent that surveys
the repo wastes attention (and tokens) on code that is effectively garbage. This tool
lists the symbols that nothing in the repository refers to, after carefully excluding
the categories that only *look* unused (public library entry points, things wired up
dynamically by frameworks, test files). The output is a grouped report a human or agent
can act on — it never deletes anything itself.

## Why it exists

Serves principle 3, **determinism before inference**: "who calls this?" is a database
count, not something an LLM should infer by re-reading code. Its G1 payoff is indirect
token saving: less junk for agents to read means every future survey, repo-map, and
change brief is smaller and sharper.

Failure prevented: silent rot — dead code that survives because nobody can cheaply
prove it's dead, and that agents keep reading, extending, and even "fixing".

## Inputs

- **The codegraph database** at `.codegraph/codegraph.db` (read-only), walk-up
  discovery. Tables used:

  | Table | Load-bearing columns |
  |---|---|
  | `nodes` | `id, kind, name, file_path, start_line, is_exported, decorators` |
  | `edges` | `source, target, kind (calls/imports/references/…)` |
  | `unresolved_refs` | `reference_name` — references codegraph could not resolve statically (a *negative* signal: the name IS used, just dynamically) |

- **CLI flags** for the filter knobs (see open questions: library mode, entry-point
  globs).

## Core computation

One core query plus exclusion filters. Deterministic; no LLM.

1. **Candidates: nodes with zero incoming use edges** — no edge of kind
   `calls`, `imports`, or `references` targets them:

   ```sql
   SELECT n.id, n.kind, n.name, n.file_path, n.start_line
   FROM nodes n
   WHERE NOT EXISTS (
     SELECT 1 FROM edges e
     WHERE e.target = n.id AND e.kind IN ('calls','imports','references')
   );
   ```

2. **Exclusion filters** (each removes a class of false positives; all from the
   blueprint, none optional):
   - **`is_exported` symbols in library code** — a library's public API is "called"
     from outside the repo; zero in-repo callers proves nothing.
   - **Entry-point globs** — mains, CLIs, scripts invoked by the OS/runner, not by
     other code.
   - **Decorated symbols** (`decorators IS NOT NULL`) — routes, fixtures, handlers,
     tasks register *dynamically* through their decorator; the static graph can't see
     the caller.
   - **Test files** — tests are invoked by the test runner, not by edges.
   - **Anything whose name appears in `unresolved_refs.reference_name`** — codegraph
     saw a reference it couldn't resolve; assume it points here (dynamic use) and
     suppress rather than falsely accuse.
3. **Grouping:** survivors grouped by directory, each with `file:line`.

## Output contract

The blueprint specifies: *"Output grouped by directory with `file:line`."* Expanded:

- Plain-text/markdown report to stdout.
- One section per directory, symbols listed as `name (kind) — file:line`.
- A summary header: total unreferenced symbols, total after filters, and counts of how
  many candidates each filter suppressed (so a reader can judge whether a filter is
  hiding too much).
- Advisory only: exit code 0 regardless of findings (it runs from cron; a nonzero exit
  would just be noise). Deletion decisions stay with a human or a reviewed agent task.

## Delivery

- **CLI / cron** — per the blueprint. Run manually, or scheduled (e.g. weekly) with the
  report dropped where the owner reads digests.
- **No hook** — this is not moment-of-need context; it is periodic hygiene.
- **manifest.json entry:** script + scope + desc so `piggyback install/init/update`
  distributes the script; empty/no `hooks` array (CLI-only tool).

## Ground rules inherited

- **Read-only DB:** connects `mode=ro`; the report goes to stdout (or a cron-redirected
  file *outside* `.codegraph/`). It never deletes code and never writes the DB.
- **Budgeted, fail-open:** as a CLI it has no injection budget to honor, but it still
  fails open — no `.codegraph/` DB found → silent exit 0, so a cron line never breaks a
  repo that hasn't been indexed.
- **Signatures as currency:** findings are pinned to `file:line` from the live index;
  if a re-index moves code, the next run re-derives everything — no cached verdicts to
  go stale.
- **Piggyback rail:** ships as a `manifest.json` entry; runs standalone for cron/CI.

## Dependencies

- `_shared/db.py` — walk-up discovery + read-only connect + schema guard.
- `_shared/queries.py` — the zero-in-degree query is the mirror image of repo-map's
  in-degree ranking; both belong in the shared module.
- **Other tools:** none. Sequencing: `_shared/` exists by build-order #3; this ships
  last (#13) so all shared pieces are proven by then.

## Non-goals

- **Never deletes anything** — report-only. Acting on the report is a separate,
  human-approved task.
- No reachability analysis beyond one fact (zero incoming use edges) — no
  whole-program liveness, no cross-repo analysis.
- No LLM judgment about whether something "seems" used — if the filters can't clear a
  suppression deterministically, the symbol is suppressed, not guessed about.
- Not a linter replacement (unused *variables*, unreachable *statements* inside a
  function are out of scope — this works at symbol granularity).

## Open questions

1. **[Human-judgment] What marks a repo as "library code"?** The `is_exported` filter
   only applies to library code (an *application's* exported-but-uncalled symbol is a
   legitimate finding). A `--lib` flag? A per-repo config line? Recommend a flag with
   the safe default (filter ON, i.e. treat as library) so false accusations are the
   rarer error.
2. **[Human-judgment] Entry-point glob defaults.** Propose `**/__main__.py`, `main.*`,
   `cli.*`, `scripts/**`, `conftest.py`; confirm the list and whether it is
   configurable per repo.
3. **[Technical research] `unresolved_refs.reference_name` matching semantics.** Exact
   bare-name match will over-suppress for common names (`run`, `main`, `get`). Check
   the real table contents: is a qualified match possible, and how many candidates does
   bare-name matching suppress on the pilot repos?
4. **[Human-judgment] Class-member roll-up.** If a class is dead, all its methods are
   too (via `contains`). Report the class once, or every member? Recommend: collapse to
   the outermost dead symbol to keep the report short.
5. **[Technical research] `kind` scope of candidates.** Functions/methods/classes for
   sure — should module-level constants/variables be candidates too, and does the
   indexer even emit reference edges to them reliably? Measure before including.
