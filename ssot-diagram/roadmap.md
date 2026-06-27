# SSOT Diagram — Roadmap

## Goal

A **single source of truth** a non-coder can read to see the real state of what is
being built with an AI: the code structure, the decisions behind it, and whether
those decisions are still valid — in one place, kept honest by a deterministic
foundation rather than by trusting an AI to update docs.

Core principle: **determinism flows up, inference flows down through a human gate.**
- Lower layers (code structure, anchored decisions, staleness) are machine-checkable
  and never depend on an LLM for their verdicts.
- An LLM may *explain* and *propose*, but never silently rewrites a lower layer.
- No step auto-rewrites a decision; staleness is a review trigger, a human resolves.

## The layered model

```
L4  Visual SSOT graph        ← non-coder reads this (decisions + status, plain language)
L3  LLM advisory layer       ← explains / proposes, human-gated (never writes truth)
L2  Staleness engine         ← deterministic: anchor drift → fresh/stale/orphaned
L1  Anchored decision records← decisions reference code by stable anchor
L0  Codegraph foundation     ← deterministic: symbols, edges, content signatures
```

## Phases

### P0 — Codegraph foundation · DONE (external)
Codegraph indexes the repo into `.codegraph/codegraph.db` (symbols, edges, files,
content hashes). This is the deterministic substrate everything else hangs off.
Owned by codegraph itself; we only read it.

### P1 — decision-index: anchored records + deterministic staleness · **DONE**
The L1+L2 layers. A decision (ADR) declares **anchors** (a file or a symbol) with a
**signature** snapshot taken from codegraph; the engine recomputes and compares —
`FRESH / STALE / ORPHANED / AMBIGUOUS`, no LLM in the verdict.

Delivered:
- [x] Engine CLI `ssot-diagram/decision_index.py` — `bootstrap`, `status`, `check`, `refresh`.
- [x] Signature source = `.codegraph/codegraph.db` read-only (file → `content_hash`;
      symbol → sha256 of source slice). Schema-guarded, fail-loud.
- [x] `bootstrap` seeds an index from `docs/adrs/*.md`; anchors land `verified:false`
      for human curation; ambiguous/unresolved tokens skipped + reported, never guessed.
- [x] Read-hook `ssot-diagram/decision_hook.py` — surfaces non-FRESH anchors when an
      ADR is read; advisory, fail-open; tells the agent to **propose, not rewrite**.
- [x] Packaged into `piggyback init` — interactive picker (default all), add-only
      idempotent hook wiring, auto-seed index if absent (never clobbers a curated one).
- [x] Tests: `test_decision_index.py` (28) + `test_piggyback.py` (17), all passing.
- [x] Verified against the real mkt_engine index (8 ADRs, 25 anchors; FRESH baseline;
      tamper → STALE; zero writes to source repos during dry-runs).

### P2 — Curate the real index (produce B) · IN PROGRESS (user-owned)
Run `piggyback init` in mkt_engine to seed `docs/decision-index.json`, then curate:
- [ ] Drop wrong anchors (prose mentions that aren't real dependencies).
- [ ] Disambiguate `name@path` anchors that bootstrap skipped (e.g. `push`).
- [ ] Re-anchor field/property mentions to their owning type or file.
- [ ] Set `supersedes` chains; mark superseded ADRs.
- [ ] `decision_index refresh <id>` each curated decision to mark `verified:true`.

### P3 — LLM advisory layer · TODO
The L3 layer. When an anchor goes STALE, an LLM reads the drift + the decision and
**proposes** a resolution (amend / supersede / refresh) with reasoning — strictly
advisory, human picks. Candidate surface: extend the hook output, or a
`decision_index explain <id>` command. Must never write to L1/L2 without confirmation.

### P4 — Visual SSOT graph · TODO (the end goal)
The L4 layer — what the non-coder actually opens. One graph, multiple node types:
- [ ] Render code structure (from codegraph) + decision nodes + edges (`anchors`,
      `supersedes`).
- [ ] Color-code decision status (fresh / stale / orphaned / superseded).
- [ ] Plain-language summaries (fed by L3) so a non-coder reads decisions, not code.
- [ ] Scoped views (per subsystem) — avoid the whole-repo hairball.
- [ ] Regenerate on codegraph update (reuse the piggyback hook plumbing).

### P5 — Decision coverage beyond ADRs · BACKLOG
Genuine decisions scattered in `docs/AI_artifacts/**` get promoted to ADRs (per
DOC-ARCH-001); working-memory drafts stay out of scope. Optionally extend bootstrap
to a wider doc glob once the ADR promotion is done.

## Status summary

| Phase | What | Status |
|---|---|---|
| P0 | Codegraph foundation | done (external) |
| P1 | decision-index (records + staleness + hook + packaging) | **done** |
| P2 | Curate real index (B) | in progress (user) |
| P3 | LLM advisory layer | todo |
| P4 | Visual SSOT graph | todo |
| P5 | Decision coverage beyond ADRs | backlog |
