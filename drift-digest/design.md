# Drift Digest — Design

**Status:** not built (stub directory exists) · **Effort:** S · **Build order:** #10
in the BLUEPRINT §6 sequence (paired with the symbol biography), after the
ssot-diagram phases; pairs naturally with ssot P6 regeneration plumbing.

---

## What it is

A "what changed since I last looked" report — the non-coder's changelog, computed
instead of remembered. You take a snapshot of the codebase's shape whenever you like
(or a weekly job takes one for you). Later, one command compares that snapshot to the
codebase as it is now and prints a short report grouped by component: which areas
changed and how much, which pieces are new or gone, which recorded decisions went
stale because the code they were anchored to moved, and whether new "invisible to the
index" dynamic code appeared that is worth asking about. It replaces the feeling of
"I have no idea what the AI did to this project last week" with a dated, factual
diff.

## Why it exists

- **Principle 1 — trust artifacts, not claims.** Session summaries and AI status
  prose are claims about what changed. A diff of two snapshots plus the live database
  is an artifact.
- **Principle 3 — determinism before inference.** "What changed" is entirely
  checkable by script: hashes differ, names appeared, names disappeared, statuses
  flipped. No LLM is asked to remember or summarize.
- **Principle 4 — route attention.** The digest points your limited review energy at
  the components that actually moved and the decisions that actually went stale,
  instead of making you re-read everything.

**Failure it prevents:** silent drift — code changing under a non-coder owner across
many AI sessions with no honest record, which is exactly how the old hand-maintained
docs died and how stale decisions get built on.

## Inputs

1. **The codegraph database** (`.codegraph/codegraph.db`, read-only) — current file
   content hashes, per-file symbol names, and the unresolved-references table.
2. **The tool's own snapshot files** — dated records this tool wrote earlier (see
   below). These live in the tool's own state directory, never in the DB.
3. **`docs/decision-index.json`** + the shipped staleness engine (ssot-diagram P1) —
   for decision status transitions.
4. **`diagram-model.json`** or its component-grouping config (ssot-diagram P3) — to
   group the report by component instead of by raw file path.

## Core computation (deterministic)

**Snapshot** (`digest.py snapshot`) stores a dated record containing:
- `{path: content_hash}` for every indexed file (hashes come straight from the DB's
  files table).
- Per-file symbol name lists (so appearing/disappearing functions are detectable by
  name, not just "file changed").
- The current decision statuses and the current count of unresolved references, so
  transitions and deltas are computable later.

**Diff** (`digest.py since <date|last>`) compares the chosen snapshot against the
current DB (and, for statuses, the current staleness verdicts):

1. **Files:** hash differs → changed; path only in current → new; path only in
   snapshot → removed.
2. **Symbols:** per-file name lists diffed → new functions/classes named explicitly,
   removed ones counted.
3. **Grouping:** every file mapped to its component via the diagram-model grouping;
   results reported per component, with untouched components stated as untouched.
4. **Decision transitions:** statuses then vs. statuses now — a decision that was
   FRESH and is now STALE is reported with the date its anchored code changed
   (from the files table's modification data).
5. **Unresolved references:** count now minus count then — new dynamic code the
   index can't see, flagged as worth asking about.

Same snapshot + same current DB ⇒ identical report.

## Output contract

Plain-language text, grouped by component, in this shape (reproduced from the
blueprint):

```
Since 2026-06-24 (last snapshot):
  Payments — 3 files changed, 2 new functions (validate_iban, retry_charge), 1 removed
  Auth — untouched
  Decisions: ADR-0012 went STALE (its anchored code changed Jun 28)
  New unresolved references: 2 (dynamic code the index can't see — worth asking about)
```

- One line per component; explicit "untouched" lines so silence is never ambiguous.
- A Decisions line only when at least one status transitioned; likewise the
  unresolved-references line only when the count grew.
- No snapshot to compare against → say so plainly and suggest taking one; never
  fabricate a baseline.

## Delivery

- **CLI:** `digest.py snapshot` and `digest.py since <date|last>` — run manually
  whenever you're about to review a project.
- **Cron (optional):** a weekly scheduled snapshot so `since last` always has a
  baseline about a week old, with zero habit required.
- **Pairing:** fits naturally beside ssot-diagram P6's regeneration plumbing — the
  same "keep the picture honest" cadence can take the snapshot.
- **Piggyback:** ships as a `manifest.json` entry so `piggyback install/init/update`
  distributes it; runs standalone as well.

## Ground rules inherited

- **Read-only DB.** Never writes to `.codegraph/codegraph.db`. Snapshots are the
  tool's own derived state, stored in its own files — codegraph can re-index freely
  and the snapshots survive.
- **Determinism up, inference gated.** The entire digest is hash/name/status
  arithmetic. No LLM anywhere; the "worth asking about" phrasing is a fixed string
  attached to a computed count, not a judgment.
- **Signatures are the currency.** "Changed" is defined by `files.content_hash`
  differing — the same signature currency every sibling tool uses — never by
  timestamps or line counts alone.
- **Budgeted, fail-open.** Output is bounded: components roll up to counts, new
  symbol names list a handful and collapse the rest to "+N more". Not a hook, so no
  session budget applies; the cron variant must fail silently-with-a-log rather than
  ever blocking anything.
- **Piggyback delivery rail.** Distributed via `manifest.json` like every sibling.

## Dependencies

- **`_shared/` modules:** `db.py` (find + read-only connect), `queries.py`
  (nodes-for-files / per-file symbol listing), `budget.py` (bounded emission).
  `resolve.py` and `hookio.py` are not needed — nothing is resolved from prose and
  there is no hook.
- **ssot-diagram P1** (shipped) — decision statuses for the transitions line.
- **ssot-diagram P3** — component grouping (the model or its config). Fallback when
  absent: group by top-level directory, clearly labeled as such.
- **ssot-diagram P6** (soft pairing, not a hard dependency) — shared regeneration
  cadence for the weekly snapshot.

## Non-goals

- **Not a git diff viewer.** It reports shape-of-the-codebase changes (files,
  symbols, decisions, unresolved refs), not line-by-line diffs — git already does
  that for engineers.
- **No LLM narrative** of what the changes mean. If a change looks interesting, the
  follow-up is the symbol biography or the diagram, not generated prose here.
- **No enforcement.** It never blocks a session or a commit; it is a report you
  read.
- **No cross-repo aggregation** in v1 — one repo per digest run.

## Open questions

- **[Human-judgment]** Snapshot retention — keep every snapshot forever (they're
  small, and history is nice) or keep the last N? Proposal: keep all until it hurts.
- **[Human-judgment]** Should the weekly cron also drop the digest text somewhere
  you'll actually see it (e.g., a dated file in the repo's docs), or only keep the
  snapshot and let you run `since last` on demand?
- **[Technical research]** Where snapshot files live so they survive but don't
  pollute: the tool's directory vs. a dot-directory in the target repo vs. next to
  `docs/decision-index.json`. Needs a look at how piggyback's other per-repo state
  (decision index) chose its home, and whether snapshots should be git-tracked.
- **[Technical research]** The exact source for "its anchored code changed Jun 28" —
  the DB's file modification column vs. git commit dates; verify which is reliable
  after re-indexing before wording the Decisions line around it.
