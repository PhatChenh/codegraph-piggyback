# codegraph-piggyback — Tool Roadmap

> **Rule:** this document answers *what* to build and *in what order*. The *what/why*
> of each tool lives in its own `<tool>/design.md`. The *how* (function names, file
> plans) belongs in per-phase planning inside `/build-pipeline` — never here.
>
> Source of truth for rationale: `~/all-projects/vibe-coding-setup/BLUEPRINT.md` (§6 build order).
> This file is the piggyback-scoped slice of that order. This supersedes the README's
> legacy "Planned scripts per tool" section.

## Project Context

Derivative tools over the read-only codegraph DB, in three goals: **G1** push
structural context to agents (save tokens), **G2** verify plan/commit claims
deterministically (make claims checkable), **G3** non-coder visibility (the ssot
diagram and its satellites). Delivery rail: `manifest.json` + `piggyback` CLI.

## Feature Inventory

| # | Capability (tool) | Goal | Status | Spec |
|---|---|---|---|---|
| 1 | impact-analyzer | G1 | ✅ shipped (+3 extensions pending) | `impact-analyzer/design-extensions.md` |
| 2 | codegraph-gate | G2 | ✅ shipped | `codegraph-gate/` |
| 3 | decision-index (ssot P1) | G3 | ✅ shipped; P2 curation in progress | `ssot-diagram/roadmap.md` |
| 4 | _shared | infra | not built | `_shared/design.md` |
| 5 | plan-verifier ⭐ | G2 | not built | `plan-verifier/design.md` |
| 6 | plan-visualizer ⭐ | G3 | not built | `plan-visualizer/design.md` |
| 7 | changeset-context | G1 | not built | `changeset-context/design.md` |
| 8 | repo-map | G1 | not built | `repo-map/design.md` |
| 9 | drift-digest | G3 | not built | `drift-digest/design.md` |
| 10 | sot-enrichment (biography) | G3 | not built | `sot-enrichment/design.md` |
| 11 | impact-precommit | G2 | not built | `impact-precommit/design.md` |
| 12 | dead-code-finder | G1 | not built | `dead-code-finder/design.md` |
| 13 | doc-coverage | G1 | not built | `doc-coverage/design.md` |

## Build Order

Piggyback-scoped slice of BLUEPRINT §6 (cross-project items like CI and the paved-road
template live in their own projects: `~/all-projects/vibe-coding-setup/paved-road-template/`,
`~/all-projects/vibe-coding-setup/workflow-guardrails/`).

### Build-order handoff (written by /architecture-grill, 2026-07-03)

Frozen contracts: `docs/roadmap/skeleton-contracts.md` (Blocks 1–5).

**Dependency DAG** (edges = imports, from "Dependency:" lines, not numbering):

```
A ──→ C ──┬──→ D
B ────────┤
B ──┬──→ E ∥ G ∥ H ∥ F(drift half)
    │         C ──→ F(biography half)
I ∥ everything
```

- **Parallel forks:** **A ∥ B** (neither imports the other — start both now;
  highest-value fork). After B: **E ∥ G ∥ H ∥ F-drift** all parallel. **I**
  parallel with anything.
- **Critical path:** A → C → D (D also needs B, but B is off the longest
  chain). Root to build first: A (P3 extractor) and B side by side.

| Phase | Depends on | Parallel with | Risk tier (+ basis) |
|---|---|---|---|
| A ssot P2+P3 | — (P2 user curation in flight) | B, I | **A** — schema-once: `diagram-model.json` is the public intermediate every viz tool reads |
| B plan-verifier + `_shared` | — | A, I | **A** — schema-once (manifest + verdicts consumed cross-project) + integration-density (`_shared` correctness = whole stack's) |
| C ssot P4–P6 | A | E, G, H, F-drift, I | **B** — integration-density (renderer L-effort); narrative trust rule is correctness-sensitive but already contract-gated (Block 5b) |
| D plan-visualizer | B, A, C | E, F, G, H, I | **C** — mechanical composition of frozen parts |
| E changeset-context | B | C, D, F, G, H, I | **C** — mechanical; budget discipline only |
| F drift-digest + biography | B (drift) · B+C (biography) | C(drift), D, E, G, H, I | **C** — composes shipped parts |
| G repo-map | B | C, D, E, F, H, I | **C** — single ranked query |
| H hygiene (precommit, dead-code, doc-coverage, extensions) | B | C, D, E, F, G, I | **C** — advisory reports |
| I rail upgrades | — | all | **C**, but see landmine below |

Give the strongest model to tier A (Phases A, B); tier C phases suit cheap
implementers with standard review.

**Discrete landmines** (decision-level, even inside low-risk phases):
- **Phase A:** macro component grouping is a human call (config
  seed-then-curate) — bad grouping degrades every downstream picture; curate
  before P5 ships, cheap to redo before then, expensive after narratives pin.
- **Phase B:** `_shared` extraction refactors SHIPPED `decision_index.py` —
  regression risk on a live tool; its existing tests must pass unchanged
  (contract Block 1, decision-log note).
- **Phase C:** renderer's "one self-contained HTML, zero external deps" is
  hard-to-reverse once P5 template + D reuse land — any CDN/framework
  temptation breaks the contract two tools share.
- **Phase I:** per-repo picker-record location is PENDING (Block 1c) — decide
  there, don't improvise mid-build.
- **Phase E:** budget unit (lines vs tokens) — settle at build from design.md
  Q4 recommendation (lines), affects only this tool.

### Phase A — ssot P2 curation + P3 model extractor
**Feature description/requirements:** finish the human curation pass on the decision
index, then build the deterministic extractor that turns the codegraph DB + decision
index into `diagram-model.json`, the public intermediate every visualization tool
renders through. Behavior per `ssot-diagram/roadmap.md` (P2, P3).
**Delivers:** capabilities 3 (P2/P3 slice).
**Dependency:** ssot P2 is user-owned curation (in progress).
**Outcome:** any tool can render real repo structure without re-deriving it.
**Scope:** IN: P2 exit criteria, P3 extractor. OUT: narratives, renderer (P4–P5).
**Done when:** `decision_index status` exits 0 all-FRESH on the pilot repo; P3
extractor emits a valid model for that repo per its roadmap's exit criteria.
**Open questions:** none — governed by `ssot-diagram/roadmap.md`.

### Phase B — plan-verifier (+ `_shared` extraction)
**Feature description/requirements:** mechanically verify every code-referencing
claim in a plan (verdicts: MISSING / AMBIGUOUS / COLLISION / BLOCKED /
UNACKNOWLEDGED-BLAST) as a /build-pipeline step and a plan-file hook.
**Delivers:** capabilities 4, 5.
**Dependency:** none hard; this phase triggers the `_shared/` extraction (second
consumer rule — resolver + signature code comes out of the decision-index engine now).
**Outcome:** a plan built on a hallucinated fact is caught in milliseconds, before
implementation turns are spent on it.
**Scope:** IN: both claim-extraction tiers, verdict table, CLI + hook delivery,
`_shared` extraction. OUT: any visualization (Phase D).
**Done when:** a plan naming a ghost file exits 1 in strict mode; verdict table shows
evidence (`file:line`, caller counts); hook fires on plan-file writes.
**Open questions:** see `plan-verifier/design.md`.

### Phase C — ssot P4–P6 (narratives, renderer, regeneration)
**Feature description/requirements:** the interactive SSOT diagram, per
`ssot-diagram/roadmap.md`.
**Delivers:** capability 3 (remaining slices).
**Outcome:** non-coder opens one HTML file and sees the real system, decisions
painted on.
**Done when:** per that roadmap's P4–P6 exit criteria.
**Open questions:** governed by `ssot-diagram/roadmap.md`.

### Phase D — plan-visualizer
**Feature description/requirements:** render any verified plan as a picture over the
current code map — changed, new, removed, and collateral-caller pieces visually
distinct; verifier verdicts as warning chips.
**Delivers:** capability 6.
**Dependency:** Phase B (manifest + verdicts), Phases A+C (model + renderer).
**Outcome:** the human plan gate becomes "look at a picture," not "trust prose."
**Scope:** IN: rendering a verified plan over the model. OUT: any new analysis not
already computed by B/A/C.
**Done when:** the CLI renders a real plan to a self-contained HTML preview; a
MISSING claim appears as a ghost node.
**Open questions:** see `plan-visualizer/design.md`.

### Phase E — changeset-context
**Feature description/requirements:** the branch brief — touched symbols, one-hop
neighborhood, anchored decisions with staleness, budgeted to ~150 lines.
**Delivers:** capability 7.
**Dependency:** reuses shared query helpers extracted in Phase B.
**Outcome:** cheap implementer models start every task with blast-radius awareness.
**Done when:** given a branch, the brief prints within budget and flags symbols not
in the graph as new.
**Open questions:** see `changeset-context/design.md`.

### Phase F — drift-digest + sot-enrichment (biography)
**Feature description/requirements:** dated snapshots diffed into a plain-language
"what changed since I last looked" digest; per-symbol biography composing docstring,
callers, anchored decisions, and summarized git history.
**Delivers:** capabilities 9, 10.
**Outcome:** owner tracks the portfolio without reading code.
**Done when:** digest prints grouped-by-component changes between two snapshots;
biography answers "tell me everything about this piece" for a real symbol.
**Open questions:** see respective design.md files.

### Phase G — repo-map
**Feature description/requirements:** token-budgeted, ranked orientation map of the
repo's API surface for cold-start sessions.
**Delivers:** capability 8.
**Done when:** map respects the token budget and collapses overflow to counts.
**Open questions:** see `repo-map/design.md`.

### Phase H — hygiene: impact-precommit, dead-code-finder, doc-coverage, impact-analyzer extensions
**Feature description/requirements:** commit-time blast gate, unreferenced-code
reports, docstring CI check, and the three shipped-tool extensions. Low urgency by
design.
**Delivers:** capabilities 1 (extensions), 11, 12, 13.
**Done when:** each tool's design.md "Done" behavior observable on a pilot repo.
**Open questions:** see respective design.md files.

### Phase I — delivery-rail upgrades
**Feature description/requirements:** three targeted upgrades to `piggyback.py`
(architecture unchanged, per skeleton-contracts.md Block 1d): durable per-repo
picker record so `update` offers new tools instead of silently wiring
(distinguishes "declined" from "never seen"); `status` shows
wired/available/new per repo; post-pull sanity check (manifest validity +
optional per-script `--selfcheck`), warn-only.
**Delivers:** rail quality; no new capability number.
**Dependency:** none; can run parallel with any phase.
**Done when:** a new manifest entry shows up as OFFERED (not wired) on `update`
in a pilot repo; `status` distinguishes the three states; a deliberately broken
manifest is reported plainly without blocking.
**Open questions:** per-repo record location/shape (PENDING in contracts 1c).

## Open questions (cross-phase)

- ~~Which repos get which repo-scope hooks by default~~ **Answered 2026-07-03:**
  picker-curated per repo, never silent — frozen in
  `docs/roadmap/skeleton-contracts.md` Block 1c.
- [Technical research] Per-tool questions live in each `<tool>/design.md`.
