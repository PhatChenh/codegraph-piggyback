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

Legend — **Goal**: G1 = push structural context to agents (save tokens); G2 =
verify plan/commit claims deterministically (catch ghosts); G3 = non-coder visibility
(diagram, biography, drift). **Auto-install**: "global `install`" = wired into
`~/.claude/settings.json` by `piggyback install`; "per-repo `init`" = wired into the
repo's `.claude/settings.json` by `piggyback init`; "CLI ships in repo" = script is
distributed and runnable, but has no editor hook to wire.

| #   | Capability (plain name)                | Goal  | What it does (non-coder view)                                                                                                                  | When it fires / trigger                                                                                                                                               | Status                                                                                                     | Spec                                   | Auto-install?                             |
| --- | -------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------- | ----------------------------------------- |
| 1   | impact-analyzer                        | G1    | Reads blast radius for you: when an AI reads a plan or spec, shows which functions are called a lot, so it knows the risk before editing.      | `PostToolUse: Read` — only `.md` files (plans/specs). Source-file reads silently skipped.                                                                             | ✅ shipped (+3 extensions pending)                                                                          | `impact-analyzer/design-extensions.md` | yes — global `install`                    |
| 2   | codegraph-gate                         | G2    | Forces the AI to ask codegraph first: discourages blind Grep/Glob/Read so it gets answers from the index instead of re-reading source.         | `PreToolUse: Grep\|Glob\|Read`; `PostToolUse: mcp__codegraph__*`; `PostToolUse: Edit\|Write`.                                                                         | ✅ shipped                                                                                                  | `codegraph-gate/`                      | yes — per-repo `init`                     |
| 3   | ssot-diagram P1 — decision-index       | G3    | Pinned decision log: each ADR is anchored to the code it affects; surfaces STALE decisions when the code drifts.                               | `PostToolUse: Read` — surfaces stale anchors. CLI: `bootstrap` / `status` / `check` / `refresh`.                                                                      | ✅ shipped; P2 curation DONE 2026-07-04 (mkt_engine 8 ADRs / 33 anchors, all FRESH)                         | `ssot-diagram/AI-artifacts/roadmap.md` | yes — per-repo `init`                     |
| 4   | ssot-diagram P3 — diagram-model        | G3    | Generates one JSON file describing the repo's components and their relations — the single input every visualization later reads.               | CLI only (`graph_model.py extract`). No editor hook.                                                                                                                  | ✅ shipped 2026-07-04 (32/32 pytest, byte-deterministic)                                                    | `ssot-diagram/AI-artifacts/roadmap.md` | yes — CLI ships in repo                   |
| 5   | ssot-diagram P4 — narrative-sidecar    | G3    | Plain-language notes pinned to each component. AI proposes the wording, you approve, the note is signature-pinned — drift visible.             | CLI only (`graph_model.py narrate …`). No editor hook.                                                                                                                | ✅ shipped 2026-07-06 (105/108 pytest, byte-deterministic, F6 empty-sig laundering closed)                  | `ssot-diagram/AI-artifacts/roadmap.md` | yes — CLI ships in repo                   |
| 6   | ssot-diagram P5 — interactive renderer | G3    | One self-contained HTML file: click macro → micro → nano, decision status painted on. Opens in any browser, no internet needed.                | none — opens manually in a browser.                                                                                                                                   | BUILT 2026-07-10 (branch `dsk/p5-html-renderer`, 11 steps; 129 pytest / 3 pre-existing; render E2E 339KB self-contained; merge pending — live painter E2E browser check owed) | `ssot-diagram/AI-artifacts/roadmap.md` | once built, CLI + file output             |
| 7   | ssot-diagram P6 — re-extract hook      | G3    | Keeps `diagram-model.json` honest by regenerating it when code changes.                                                                        | `PostToolUse: Write\|Edit` (planned).                                                                                                                                 | not built                                                                                                  | `ssot-diagram/AI-artifacts/roadmap.md` | once built — per-repo `init`              |
| 8   | _shared (internal library)             | infra | Tiny toolkit every tool shares: open codegraph DB read-only, find symbols, hash code, format hook output, fit to a token budget.               | n/a — library, imported by other tools. Extracted when a 2nd tool needs it.                                                                                           | ✅ BUILT 2026-07-05 (db/sig/resolve/queries/budget/hookio/manifest; `decision_index` cut over, tests green) | `_shared/design.md`                    | ships with any piggyback tool             |
| 9   | plan-verifier ⭐                        | G2    | Fact-checks a plan before approval: "does this file exist? is this name unique? will removing it break 12 callers?" — verdict table.           | `PostToolUse: Write\|Edit` on `*plan*.md` or `docs/plans/**` (advisory table injected). CLI: `plan_verify.py <plan.md> [--strict]` (strict blocks the pipeline step). | ✅ BUILT 2026-07-05 (24 tests; sweep noise measured)                                                        | `plan-verifier/design.md`              | yes — per-repo `init`                     |
| 10  | diff-verifier                          | G2    | At wave-end, mechanically checks the diff delivered what the plan declared (files in scope, new symbols present, removes gone).                | CLI only (`diff_verify.py <plan.md> --diff <base>..<head>`); orchestrated skill calls it. No editor hook.                                                             | ✅ BUILT 2026-07-05 (14 tests; restricted-qualifier DSL)                                                    | `diff-verifier/design.md`              | yes — CLI ships in repo                   |
| 11  | plan-visualizer ⭐                      | G3    | Turns a verified plan into a picture on the code map: touched glows amber, new is dashed, removed is strikethrough, ghost = missing claim.     | CLI (`plan_visualize.py <plan.md> -o preview.html`). Pipe-to-/build-pipeline step planned.                                                                            | not built                                                                                                  | `plan-visualizer/design.md`            | once built — CLI + optional pipeline step |
| 12  | changeset-context                      | G1    | Branch brief: short summary (≤150 lines) of what changed + who depends on it + which decisions are anchored to the changed pieces.             | CLI (`context_brief.py`). Optional `SessionStart` hook (only mid-flight branch).                                                                                      | not built                                                                                                  | `changeset-context/design.md`          | once built — CLI + opt-in hook            |
| 13  | repo-map                               | G1    | Token-budgeted ranked list of the most-depended-on symbols across the whole repo — so a cold-start session orients without grepping.           | CLI (`repo_map.py --budget 1500`). Optional opt-in `SessionStart` hook.                                                                                               | not built                                                                                                  | `repo-map/design.md`                   | once built — CLI + opt-in hook            |
| 14  | drift-digest                           | G3    | "What changed since I last looked": snapshot the repo's shape today, later diff to see new functions, removed ones, decisions that went stale. | CLI (`digest.py snapshot` / `digest.py since <date\|last>`). Optional weekly cron.                                                                                    | not built                                                                                                  | `drift-digest/design.md`               | once built — CLI + cron                   |
| 15  | sot-enrichment (symbol biography)      | G3    | "Tell me everything about this piece" — what it is, who depends on it, which decisions anchor to it, recent change dates.                      | CLI (`biography.py <symbol>`). Also the data source for the diagram's node-detail side panel.                                                                         | not built                                                                                                  | `sot-enrichment/design.md`             | once built — CLI + diagram                |
| 16  | impact-precommit                       | G2    | Last-look before commit: warns if staged lines touch widely-used symbols with no test file. `--strict` blocks that one specific rule.          | `git pre-commit` hook (stub installed into `.git/hooks/`). CLI (`impact_precommit.py [--strict]`) for CI / manual checks.                                             | not built                                                                                                  | `impact-precommit/design.md`           | once built — git hook + CLI               |
| 17  | dead-code-finder                       | G1    | Lists symbols nothing in the repo refers to (after excluding public APIs, entry points, decorated routes, tests). Report-only, never deletes.  | CLI / cron only. No editor hook.                                                                                                                                      | not built                                                                                                  | `dead-code-finder/design.md`           | once built — CLI / cron                   |
| 18  | doc-coverage                           | G1    | Reports functions/methods missing a docstring. CI mode (changed files) exits 1 and blocks; report mode (whole repo) is informational.          | CLI only. CI gate + cron / manual report.                                                                                                                             | not built                                                                                                  | `doc-coverage/design.md`               | once built — CI / cron                    |

### Notes on what's in the repo but not separately listed above

- **arch-visualizer/** — legacy stub, superseded by `ssot-diagram` + `plan-visualizer`. Not a
  separate capability.
- **impact-analyzer extensions** — three follow-ups tracked in
  `impact-analyzer/design-extensions.md`. Not yet separate rows; #1 still ships as one tool
  in `manifest.json`.
- **ssot-diagram P2 (decision-index curation)** — one-time human pass, not a tool. Embedded
  under row 3.
- **ssot-diagram P0 — codegraph foundation** — external dependency
  (`colbymchenry/codegraph`); piggyback reads only. `piggyback init` calls
  `codegraph init` and seeds the index in the repo.

### What piggyback install vs init does today (2026-07-08)

Verified against `manifest.json` + `piggyback.py`:

- **`piggyback install` (per-machine, once)** wires rows that carry `scope: "global"` into
  `~/.claude/settings.json`. Today that is only `impact-analyzer` (#1).
- **`piggyback init` (per-repo, idempotent)** wires rows with `scope: "repo"` into the
  repo's `.claude/settings.json`. Today that is `codegraph-gate` (#2), `decision-index`
  (#3), `plan-verifier` (#9), `diff-verifier` (#10). It also runs `codegraph init`, then
  seeds the repo's decision index (`decision_index bootstrap`).
- **`piggyback init` skips** every entry whose `hooks: []` even if `scope: "repo"`, because
  there's nothing to wire; the script is still distributed. Rows 4, 5, 8, 11–18 today have
  no editor hook to wire when they ship — they ship as CLIs (some with optional later
  hooks per their design).

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
- **Phase B:** ~~`_shared` extraction refactors SHIPPED `decision_index.py`~~ —
  RESOLVED: `_shared/` extraction SHIPPED in commit `82287f9` (alongside
  plan-verifier, by the second-consumer rule); `decision_index.py:44-57` now
  imports `_shared.db`/`resolve`/`sig`, tests pass unchanged. Was a regression-
  risk landmine pre-ship; the live plan-verifier/diff-verifier ADRs (0011+)
  carry forward any residual cutover notes.
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
**Delivers:** capabilities 3 (P2 curation slice), 4 (P3 slice).
**Dependency:** ssot P2 curation DONE (2026-07-04 — 8 ADRs / 33 anchors, all verified
+FRESH on `~/all-projects/mkt_engine`). P3 plan step complete; code implementation
is the remaining work.
**Outcome:** any tool can render real repo structure without re-deriving it.
**Scope:** IN: P2 exit criteria (MET), P3 extractor. OUT: narratives, renderer (P4–P5).
**Done when:** `decision_index status` exits 0 all-FRESH on the pilot repo (MET for P2);
P3 extractor emits a valid model for that repo per its roadmap's exit criteria (P2 half DONE,
P3 half at implement step — see `STATE.md`).
**Open questions:** none — governed by `ssot-diagram/roadmap.md`.

### Phase B — plan-verifier (+ `_shared` extraction) — SHIPPED (`82287f9`)
> **STATUS 2026-07-09 (doc-sweep): SHIPPED.** plan-verifier + diff-verifier +
> `_shared/` extraction all landed in commit `82287f9` (build-order #3). The
> plan-file hook + CLI are live; `_shared/` cutover happened by the
> second-consumer rule (the "Done when" criteria below are MET). This section
> kept as the record; Phase B is no longer forward work.
**Feature description/requirements:** mechanically verify every code-referencing
claim in a plan (verdicts: MISSING / AMBIGUOUS / COLLISION / BLOCKED /
UNACKNOWLEDGED-BLAST) as a /build-pipeline step and a plan-file hook.
**Delivers:** capabilities 8, 9.
**Dependency:** none hard; this phase *triggered* the `_shared/` extraction
(second-consumer rule — resolver + signature code came out of the
decision-index engine; DONE).
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
**Delivers:** capability 11.
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
**Delivers:** capability 12.
**Dependency:** reuses shared query helpers extracted in Phase B.
**Outcome:** cheap implementer models start every task with blast-radius awareness.
**Done when:** given a branch, the brief prints within budget and flags symbols not
in the graph as new.
**Open questions:** see `changeset-context/design.md`.

### Phase F — drift-digest + sot-enrichment (biography)
**Feature description/requirements:** dated snapshots diffed into a plain-language
"what changed since I last looked" digest; per-symbol biography composing docstring,
callers, anchored decisions, and summarized git history.
**Delivers:** capabilities 14, 15.
**Outcome:** owner tracks the portfolio without reading code.
**Done when:** digest prints grouped-by-component changes between two snapshots;
biography answers "tell me everything about this piece" for a real symbol.
**Open questions:** see respective design.md files.

### Phase G — repo-map
**Feature description/requirements:** token-budgeted, ranked orientation map of the
repo's API surface for cold-start sessions.
**Delivers:** capability 13.
**Done when:** map respects the token budget and collapses overflow to counts.
**Open questions:** see `repo-map/design.md`.

### Phase H — hygiene: impact-precommit, dead-code-finder, doc-coverage, impact-analyzer extensions
**Feature description/requirements:** commit-time blast gate, unreferenced-code
reports, docstring CI check, and the three shipped-tool extensions. Low urgency by
design.
**Delivers:** capability 1 (extensions), 16, 17, 18.
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
