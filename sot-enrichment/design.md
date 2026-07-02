# Sot-Enrichment (Symbol Biography) — Design

**Status:** not built (stub directory exists) · **Effort:** S — it is composition of
already-shipped parts · **Build order:** #10 in the BLUEPRINT §6 sequence (paired
with drift-digest), after the ssot-diagram phases it composes.

---

## What it is

A "tell me everything about this piece" command for a non-coder. You give it the name
of one piece of the codebase and it answers four questions in plain language, on one
page: **what is it** (what kind of thing, where it lives, what its own description
says, plus the approved plain-language narrative if one exists), **who depends on it**
(how many places call it, and which components those callers live in), **what
decisions were made about it** (every recorded decision anchored to it, and whether
each decision is still current or has gone stale), and **what is its history** (the
dates and one-line subjects of every past change to it, pulled from version control).
It is the biography of a single piece of code, assembled from records that already
exist — nothing is invented.

## Why it exists

- **Principle 3 — determinism before inference.** Every one of the four answers is a
  lookup over data that already exists (the code database, the decision index, the
  narrative sidecar, git history). No LLM re-reads code to summarize it.
- **Principle 1 — trust artifacts, not claims.** When you ask an AI "what is this
  function and is it safe to change?", you get prose. This tool gives you the caller
  counts, the decision statuses, and the change dates as computed facts.

**Failure it prevents:** the non-coder owner treating a piece of code as small and
safe when it actually has many dependents, an anchored decision, and a long history of
churn — or asking an expensive model to reconstruct all of that from scratch every
time the question comes up.

## Inputs

1. **A symbol name** (the thing you're asking about), given on the command line or by
   clicking a node in the interactive diagram.
2. **The codegraph database** (`.codegraph/codegraph.db`, read-only) — kind, file,
   line range, docstring, and edges.
3. **`docs/decision-index.json`** — the anchored decision records and their live
   staleness status (ssot-diagram P1, shipped).
4. **`narratives.json`** — the human-approved plain-language descriptions
   (ssot-diagram P4), when present.
5. **`diagram-model.json`** (ssot-diagram P3) — for mapping callers' files to
   component names via the model's grouping and rolled-up edges.
6. **Git history** — via `git log --follow -L<start>,<end>:<file>` scoped to the
   symbol's line range.

## Core computation (deterministic, four sections)

1. **What it is.** Look the name up in the code database — honest outcome discipline
   if it's ambiguous or missing (list candidates / say "not found", never guess).
   Report its kind (function, class, method…), a plain location ("in the Payments
   component, file X, lines A–B"), its docstring, and its narrative from
   `narratives.json` — approved narrative if fresh; the deterministic fallback text
   otherwise; a stale narrative is shown but visibly labeled stale, never presented
   as current.
2. **Who depends on it.** Count incoming calls/references/imports edges, then roll
   the callers up to component names using the diagram model's grouping ("called
   from 12 places across 3 components: Payments (7), Billing (4), Reports (1)").
3. **Decisions about it.** Filter the decision index to entries whose anchors point
   at this symbol (or its file), and print each with its live status
   (FRESH/STALE/ORPHANED/superseded) from the shipped staleness engine.
4. **History.** Run git's line-range history for the symbol's source slice and
   summarize deterministically: one line per commit — date + subject only. No LLM
   summarization; the "summary" is truncation, not paraphrase.

Same symbol + same repo state ⇒ identical output.

## Output contract

- Plain-language text report, the four sections above in that fixed order, each
  section headed by its question ("What it is", "Who depends on it", "Decisions about
  it", "History").
- Empty sections say so explicitly ("No recorded decisions mention this piece") —
  absence of a record is itself information.
- A machine-readable variant (JSON with the same four sections) so the diagram's
  side panel can consume it without parsing prose.

## Delivery

- **CLI:** `biography.py <symbol>` — run manually, in a session, or from other
  tools.
- **Diagram integration:** the same computation serves as the data source for a
  "node detail" side panel in the ssot-diagram interactive HTML — click a node, read
  its biography.
- **Piggyback:** ships as a `manifest.json` entry so `piggyback install/init/update`
  distributes it; runs standalone as well.

## Ground rules inherited

- **Read-only DB.** Opens `.codegraph/codegraph.db` read-only; writes nothing at all
  — this tool has no derived state file of its own.
- **Determinism up, inference gated.** All four sections are pure lookups. The only
  LLM-authored text it ever shows is the narrative — which arrives already gated
  (human-approved, signature-pinned) by ssot-diagram P4, and is labeled stale when
  its pin no longer matches.
- **Signatures are the currency.** Staleness of decisions and narratives is judged
  by the shipped signature machinery (P1/P4); this tool displays those verdicts and
  computes none of its own.
- **Budgeted, fail-open.** As a CLI its output is naturally bounded (caller lists
  roll up to component counts rather than enumerating every site; history truncates
  to recent entries with a "+N older changes" line). If a data source is absent
  (no narratives yet, no decision index), the section degrades to what exists and
  says what's missing — it never errors out over a missing sidecar.
- **Piggyback delivery rail.** Distributed via `manifest.json` like every sibling.

## Dependencies

- **`_shared/` modules:** `db.py` (find + read-only connect), `resolve.py` (name →
  node with honest AMBIGUOUS/UNRESOLVED), `queries.py` (blast radius / edge roll-up),
  `budget.py` (bounded emission). No hook, so `hookio.py` is not needed.
- **ssot-diagram P1** (shipped) — decision index + staleness verdicts.
- **ssot-diagram P3** — `diagram-model.json` for component grouping of callers.
- **ssot-diagram P4** — `narratives.json`. Optional at runtime: without it the tool
  falls back to docstring + counts.
- **ssot-diagram P5** — only for the side-panel integration, not for the CLI.
- **git** — must run inside a git repository for the History section; degrades to
  "no history available" outside one.

## Non-goals

- **No writing.** It never edits narratives, decisions, or the DB — it is a
  read-and-report tool.
- **No LLM explanation layer.** If a richer explanation is wanted, that is the
  narrative sidecar's job (proposed → human-approved → pinned), not this tool's.
- **No whole-file or whole-component biographies** in v1 — one symbol per query.
  Component-level storytelling belongs to the ssot diagram itself.
- **No code quality judgment** ("this looks risky/messy") — counts and statuses
  only.

## Open questions

- **[Human-judgment]** When the name is ambiguous (several symbols share it), print
  a candidate list and stop, or print a compact biography for each candidate?
  Stopping is stricter; multiple biographies may be friendlier for a non-coder.
- **[Human-judgment]** How much history is useful before it's noise — all commits,
  or the most recent N with a "+K older" line? Default proposal: recent 10.
- **[Technical research]** `git log -L` behavior when the symbol's line range moved
  across renames/refactors — verify `--follow` + `-L` interaction on the real repos
  (mkt_engine) before trusting the History section.
- **[Technical research]** Whether the P5 side panel consumes pre-computed JSON
  embedded at render time or shells out live — depends on P5's single-file/zero-deps
  constraint; resolve when wiring the diagram integration.
