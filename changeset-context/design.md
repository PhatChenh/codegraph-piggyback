# Changeset Context — Design

**Status:** not built (stub dir exists) · **Effort:** S–M · **Build order:** #9 of 13
(after plan-verifier #3 has forced the `_shared/queries.py` extraction, which this tool
reuses).

---

## What it is

When an AI is about to work on a branch, it usually has no idea what the changed files
are connected to — who depends on them, what they depend on, and which recorded
decisions are anchored to them. This tool produces a "branch brief": a short, structured
summary of everything a change touches plus its immediate neighborhood, computed from
the code index and git, and capped to a fixed size. The agent reads one brief instead of
spending many turns rediscovering the structure by opening files.

## Why it exists

Serves principle 3, **determinism before inference**: the neighborhood of a change is a
pure database lookup, so a script computes it — no LLM re-reads code to figure out
structure. It also serves principle 1, **trust artifacts, not claims**: the brief is a
queryable artifact, not the agent's own guess about what its change affects.

Failure prevented: the #1 cheap-model failure — editing with no blast-radius awareness
(changing a function without knowing 7 other places call it). Secondary win: it saves
the tokens the agent would otherwise burn re-surveying the repo.

## Inputs

1. **Touched files**, from one of:
   - `git diff --name-only <base>...` for a branch (the primary mode), or
   - an explicit list of paths passed on the command line.
2. **The codegraph database** at `.codegraph/codegraph.db` (read-only), found by walking
   up from cwd. Relevant tables:

   | Table | Load-bearing columns |
   |---|---|
   | `nodes` | `id, kind, name, qualified_name, file_path, start_line, end_line, docstring, signature, is_exported, decorators` |
   | `edges` | `source, target, kind (calls/imports/contains/extends/references/…)` |
   | `files` | `path, content_hash, language, modified_at` |

3. **`docs/decision-index.json`** (if present) — the shipped decision index that anchors
   ADRs to files/symbols and knows each anchor's staleness status.

## Core computation

All SQL + git. No LLM anywhere in the pipeline.

1. **Touched files → their nodes:** `SELECT … FROM nodes WHERE file_path IN (…)`.
2. **For each node, its neighborhood:**
   - incoming edges (callers) — who breaks if this changes:

     ```sql
     SELECT n2.name, n2.file_path, e.line
     FROM edges e JOIN nodes n1 ON e.target = n1.id
                  JOIN nodes n2 ON e.source = n2.id
     WHERE n1.name = ? AND e.kind IN ('calls','references','imports');
     ```

   - outgoing edges (callees) — what this change depends on.
   - Both grouped and **counted**, not dumped raw.
3. **Decisions:** join `docs/decision-index.json` — any decision anchored to a touched
   file or symbol is listed with its live staleness status (e.g. FRESH / STALE), plus a
   note that it will need a refresh if the anchored code changes.
4. **Compression rule:** emit **signatures + docstring first-lines only — never bodies**.
5. **Names in the diff that resolve to no node** are reported as "not in graph — new
   symbol" rather than silently dropped (useful signal: brand-new code has no history).

## Output contract

Markdown, **budgeted to ≤ ~150 lines**. Shape (verbatim from the blueprint):

```
## Change brief: branch fix/retry-logic (4 files, 11 symbols)
### src/queue/retry.py — 3 symbols touched
  retry_with_backoff  ← called by 7 (worker.py:88, scheduler.py:41, …)
  ⚠ ADR-0012 "retry policy" anchors here — status FRESH, will need refresh
### Depends on (outgoing): db.get_conn (12 callers — shared), config.load
### Not in graph: `new_backoff_curve` — new symbol
```

Expanded contract, per element:

- **Header:** branch (or "explicit paths"), file count, symbol count.
- **Per touched file:** a `###` section, symbols listed with their **incoming caller
  count** and a truncated caller list (`file:line`, ellipsized).
- **Decision warnings:** `⚠` line under the symbol/file the decision anchors to, with
  ADR id, title, current status.
- **Outgoing roll-up:** one shared "Depends on" section listing callees, flagging widely
  shared ones by their own caller count (e.g. `db.get_conn (12 callers — shared)`).
- **Not in graph:** names from the change that don't resolve — labeled "new symbol".
- When the budget would be exceeded, highest-caller-count symbols keep their detail;
  the tail collapses to counts.

## Delivery

- **CLI first:** `context_brief.py`, a piggyback-distributed script run manually or as a
  `/build-pipeline` step. Registers in `manifest.json` (script + scope + desc) like
  every other tool.
- **Optional, later:** a `SessionStart` hook that runs `git diff` against the default
  branch and injects the brief **only when a branch is mid-flight** (clean checkout of
  the default branch → silent). Not part of v1; the hook entry is added to the manifest
  only when it ships.

## Ground rules inherited

- **Read-only DB:** opens `.codegraph/codegraph.db` with `mode=ro`; writes nothing
  anywhere (the brief goes to stdout / the hook payload).
- **Budgeted, fail-open:** CLI output ≤ ~150 lines; the future hook variant injects
  ≤ ~30 lines, stays silent when there is no active branch diff, and never blocks a
  session on its own errors (no DB found → silent exit 0).
- **Signatures as currency:** emits `nodes.signature` and docstring first-lines only;
  never function bodies. File identity is `files.content_hash`.
- **Piggyback rail:** ships as a `manifest.json` entry so `piggyback install/init/update`
  distributes it; also runs standalone for CI and manual use.

## Dependencies

- `_shared/db.py` — `find_db()` walk-up + read-only connect + schema guard.
- `_shared/queries.py` — blast-radius, nodes-for-files, edge roll-up (extracted when
  plan-verifier ships, build-order #3 — that is why this tool sits at #9).
- `_shared/budget.py` — budgeted-emit helper for the ~150-line cap.
- `_shared/hookio.py` — only if/when the optional `SessionStart` hook ships.
- **Other tools:** reads `docs/decision-index.json` produced by the shipped
  decision-index engine (`ssot-diagram/`); degrades gracefully (skips the decision
  section) when the file is absent.

## Non-goals

- No LLM summarization or "explanation" of the change — structure only.
- No verdicts about whether the change is *good* (that's plan-verifier's and reviewers'
  job); this tool only describes the neighborhood.
- No editing, staging, or committing — pure reader.
- No transitive (multi-hop) dependency walk — **one-hop** neighborhood only.
- Does not replace codegraph's interactive MCP lookup; it *pushes* context at the
  moment of need instead of waiting to be asked.

## Open questions

1. **[Technical research] File-level vs hunk-level "touched symbols".** The blueprint's
   computation uses `git diff --name-only` → *all* nodes in a touched file. But the
   sample output says "3 symbols touched" in a file — should v1 intersect diff hunks
   with `[start_line, end_line]` (as the impact pre-commit gate does) to report only
   symbols whose lines actually changed? File-level is simpler and matches the spec
   text; hunk-level matches the sample more closely.
2. **[Technical research] Detecting "new symbol" names.** `new_backoff_curve` appears
   under "Not in graph" — this requires extracting candidate names from the diff's
   added lines (or from a plan manifest) and failing to resolve them. Decide the
   extraction source and reuse `_shared/resolve.py`'s honest UNRESOLVED outcome.
3. **[Human-judgment] Default base ref.** `<base>` when none is given: auto-detect the
   default branch (`origin/HEAD`) or hardcode `main`? Auto-detect recommended, but it
   is a behavior choice worth confirming.
4. **[Human-judgment] Budget unit.** The blueprint says "sized to a token budget" but
   the contract says "≤ ~150 lines". Recommend: lines are the enforced cap (simple,
   deterministic), with `_shared/budget.py` token estimation used only by the future
   hook variant.
5. **[Technical research] decision-index.json join contract.** Confirm the exact anchor
   schema (file anchors vs symbol anchors, status vocabulary) against the shipped
   `ssot-diagram/decision_index.py` before coding the join — do not guess it.
