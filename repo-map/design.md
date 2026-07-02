# Repo Map — Design

**Status:** not built (new idea, dir just created) · **Effort:** S · **Build order:**
#11 of 13 ("nice-to-have orientation" — after changeset-context #9, before the hygiene
pair #13).

---

## What it is

When an AI session starts cold in an unfamiliar repository, its first minutes are spent
figuring out "what are the important pieces here?" This tool prints a compressed
orientation map of the repository: the most-depended-on functions and classes, one line
each, grouped by file, ranked so the things everything else relies on come first — and
cut off at a fixed size so it never floods the context window. It is the same idea as
the "repo map" the aider tool is known for, except it is computed from codegraph's
already-indexed dependency table instead of re-parsing the code, and the ranking is
fully deterministic (same repo state → same map, every time).

## Why it exists

Serves principle 3, **determinism before inference**: "which symbols matter most" is
answerable by counting edges in the database — a script's job, not an LLM's. It fills
G1's gap: codegraph's MCP tools handle *interactive* lookup, but nothing *pushes* the
right structural context at session start, so agents spend turns (and tokens)
discovering what the DB already knows.

Failure prevented: cold-start flailing — an agent greps and reads a dozen files to
orient itself, burning tokens to reconstruct a picture that one bounded, ranked map
gives for free.

## Inputs

- **The codegraph database** at `.codegraph/codegraph.db` (read-only), found by walking
  up from cwd. Tables used:

  | Table | Load-bearing columns |
  |---|---|
  | `nodes` | `id, kind, name, file_path, start_line, signature, is_exported` |
  | `edges` | `source, target, kind (calls/imports/references/…)` |

- **CLI flags:** `--budget <tokens>` (the canonical invocation is
  `repo_map.py --budget 1500`).

## Core computation

Deterministic, pure SQL + a budgeted emitter. No LLM.

1. **Candidate set:** `nodes WHERE kind IN ('class','function','method','interface')`
   only — no variables, no files, no modules.
2. **Test exclusion:** skip nodes whose `file_path` matches test globs.
3. **Rank by in-degree** — how many other symbols depend on this one:

   ```sql
   SELECT COUNT(*) FROM edges
   WHERE target = <node.id> AND kind IN ('calls','imports','references');
   ```

   (In practice one `GROUP BY target` query, not N queries.)
4. **Tie-break:** `is_exported DESC, name` — exported symbols outrank internal ones at
   equal in-degree; then alphabetical, so output is stable across runs.
5. **Budget enforcement:** emit highest-ranked symbols first, one line each
   (signature only), grouped by file; **stop at the budget**; collapse everything that
   didn't fit into per-directory tallies: `+ N more in src/foo/`.

## Output contract

The blueprint gives the contract in prose; expanded:

- **One line per symbol:** its signature (from `nodes.signature`) — never a body, never
  a docstring beyond what the signature carries.
- **Grouped by file:** a short file header, then that file's ranked symbols.
- **Ranked globally:** the most-depended-on symbols in the whole repo appear first;
  grouping by file never promotes a low-ranked symbol above the cut.
- **Budget line:** hard stop at `--budget` tokens (default invocation shows 1500);
  everything below the cut compresses to `+ N more in <directory>/` lines so the reader
  knows what was elided and where.
- Plain text / markdown to stdout (CLI) or injected context (hook).

## Delivery

- **CLI:** `repo_map.py --budget 1500` — piggyback-distributed script, runnable
  standalone (cold-start orientation, CI artifacts).
- **Optional hook:** `SessionStart`, for repos where you want every session
  pre-oriented. Opt-in per repo (manifest `scope: repo`), not global — most sessions in
  a familiar repo don't need it.
- **manifest.json entry:** script + scope + desc; the `hooks` array carries the
  `SessionStart` event only for the opt-in variant.

## Ground rules inherited

- **Read-only DB:** connects `mode=ro`; produces stdout only, writes no state.
- **Budgeted, fail-open:** the CLI's whole purpose is a hard token budget; the hook
  variant additionally caps at ≤ ~30 injected lines, is silent when there is no
  `.codegraph/` DB, and never blocks a session on its own errors.
- **Signatures as currency:** the map is made of `nodes.signature` lines exclusively —
  the cheapest faithful representation of a symbol.
- **Piggyback rail:** ships via `manifest.json` so `piggyback install/init/update`
  distributes it; the CLI also runs standalone.

## Dependencies

- `_shared/db.py` — walk-up discovery + read-only connect + schema guard.
- `_shared/queries.py` — the in-degree ranking query belongs here (shared with
  dead-code-finder, which is the same query with the opposite filter).
- `_shared/budget.py` — token estimation + budgeted-emit helper (this tool is its
  most natural consumer).
- `_shared/hookio.py` — for the optional `SessionStart` variant.
- **Other tools:** none at runtime. Sequencing only: `_shared/` must exist (extracted
  by plan-verifier, build-order #3).

## Non-goals

- Not a call-graph or architecture diagram — that is `ssot-diagram`'s job; this is a
  flat ranked list.
- No LLM summarization, no "importance" heuristics beyond edge counting.
- No re-parsing of source files — if codegraph didn't index it, it isn't in the map.
- Not a substitute for `changeset-context`: repo-map orients on the *whole repo* at
  session start; changeset-context briefs a *specific change*.
- No per-symbol detail (docstrings, callers list) — one signature line each, full stop.

## Open questions

1. **[Human-judgment] Default budget.** The blueprint's canonical invocation is
   `--budget 1500`; confirm 1500 tokens as the default when the flag is omitted, and
   whether the SessionStart hook should use a smaller default (it competes with the
   ≤ ~30-line hook budget, which is far below 1500 tokens — the hook likely needs its
   own, much smaller number).
2. **[Human-judgment] Test glob list.** The blueprint says "skip tests by glob" without
   naming globs. Propose `tests/**`, `test_*.py`, `*_test.*`, `*.spec.*`, `*.test.*` —
   confirm, and decide whether the list is configurable per repo.
3. **[Technical research] `kind` vocabulary across languages.** Verify against the
   actual indexer that `'interface'` (TypeScript) and `'method'` are the literal kind
   strings, and whether other kinds (e.g. `'struct'`, `'trait'`) should join the
   candidate set for non-Python/TS repos.
4. **[Technical research] Token estimation method.** `_shared/budget.py` needs a
   deterministic estimator (chars/4 heuristic vs a real tokenizer). A heuristic keeps
   the tool dependency-free; measure how far off it runs on real signatures before
   choosing.
5. **[Human-judgment] File-grouping vs global-rank display tension.** Strict global
   ranking interleaves files (file header repeats); strict file grouping can pull a
   file's weak symbols above another file's strong ones. Recommend: order files by
   their top symbol's rank, list each file's above-the-cut symbols under it — but this
   is a presentation choice worth a one-line sign-off.
