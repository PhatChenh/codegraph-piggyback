# ADR 0003 — Proposed (unreviewed) narratives render visibly marked, not hidden

## Status

Accepted (2026-07-06). Owner-ratified at the P5 requirements grill (locked
decision 3); recorded here at the P5 design step.

## Context

P4's narratives carry a stored status of `proposed` (ingested, human not yet
approved) or `approved`. Block 5b's trust rule says nothing renders *as
trusted prose* unless approved AND signature-fresh. That rule constrains how
`proposed` text may be shown — but it does not by itself decide WHETHER to
show it. Two defensible postures exist for a node whose only narrative is an
unreviewed draft:

1. Hide it: render the deterministic fallback sentence until a human approves,
   so the artifact never displays words no human signed off on.
2. Show it marked: render the draft, visually muted, with an explicit
   "unreviewed" badge.

The same fork reappears for `stale` entries (approved once, code drifted
since): hide the old prose, or show the OLD prose clearly flagged.

## Decision

Marked-visible, both cases. Per the pinned status→treatment matrix (design doc
Constraints L3):

- `proposed` → prose rendered, muted, with a "PROPOSED — unreviewed" badge.
- `stale` → the OLD prose rendered, muted, with a danger "needs review" badge.

Neither ever renders with the normal trusted treatment; `approved`+fresh is
the only status that does. Hiding is reserved for `orphaned` entries (their
node no longer exists in the model — there is nothing to attach them to).

## Alternatives Considered

### Option B — hide unreviewed/stale prose; fallback text until approved-fresh

Strictest reading of "trust": the artifact only ever shows machine-derived
facts or human-approved sentences. Rejected by the owner at the grill: for the
tool's actual audience (a non-coder owner reviewing their own pipeline), a
hidden draft is invisible work — nothing in the artifact says "there are 40
sentences waiting for your approval", so the approval loop starves. A muted,
badged draft is simultaneously an honest display AND the review queue made
visible in the place the owner already looks.

### Option C — hide stale only, show proposed marked

Treats drift as more dangerous than non-review. Rejected: showing the OLD
sentence with a danger badge carries more information than removing it (the
reader sees what the description USED to claim while knowing the code moved),
and P4's one-step refresh flow (worklist → ingest → approve) already makes the
stale text easy to replace. Symmetric treatment is also one rule instead of
two.

## Consequences

Positive:

- The artifact doubles as the approval queue: unreviewed and drifted prose is
  findable by scanning for badges, which feeds P4's `narrate approve` flow.
- No information is destroyed at render time; a screenshot of the diagram is
  an honest snapshot of both the code AND the documentation debt.
- One rendering rule per status — the golden test pins each row visually.

Negative:

- Unreviewed LLM text is visible in a shipped artifact; a careless reader
  could quote muted-badged prose as fact. Mitigated by treatment, not
  placement: muting (`--fg-disabled`) plus an uppercase badge directly under
  the title, pinned by the UX addendum §2 and asserted by the golden test.
- Every consumer of the artifact inherits this posture — if a future audience
  (e.g. external stakeholders) must never see drafts, that needs a new
  render mode and a revisit of this ADR.

## References

- Design doc: `../AI-artifacts/1_design/p5-html-renderer.md` (Constraints L3 —
  the matrix pinned verbatim)
- UX addendum: `../AI-artifacts/1_design/p5-html-renderer-ux-addendum.md` §2
  (exact colors/chips per status)
- Contract: `../../docs/roadmap/skeleton-contracts.md` Block 5b (trust rule:
  stale shown as visibly stale, never silently as current)
