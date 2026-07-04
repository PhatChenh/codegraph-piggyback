# P3 build-pipeline — state handoff

_Paused 2026-07-04 after spec step, before factual-code-verification._
_Pipeline: `/build-pipeline` (medium tier). Feature: ssot-diagram P3 extractor._

## Resume point

**Next step: factual-code-verification subagent.** Dispatch template in
`~/.claude/skills/build-pipeline/SKILL.md` ("factual-code-verification").
Inputs to inject:
- Spec: `docs/AI_artifacts/2_specs/p3-diagram-model-extractor.md` (1076 lines,
  14 components, 25 assumptions A1-A25)
- Design: `docs/AI_artifacts/1_design/p3-diagram-model-extractor.md` (1330 lines,
  revised post-red-team)
- ADR: `docs/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`
- Repo root: `/Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback`
- Pilot DB: `~/all-projects/mkt_engine/.codegraph/codegraph.db` (read-only,
  `mode=ro&immutable=1`); curated index: `~/all-projects/mkt_engine/docs/decision-index.json`
  (8 ADRs, 33 anchors, all verified, all FRESH as of 2026-07-04 — P2 LANDED)
- Verify all 25 assumptions at the depth each claim requires (behavior claims =
  behavior reading, not signature grep). Distrust the spec's own "pre-validated"
  labels. The 5 red-team fixes (A13-A17) are load-bearing — verify each. Output
  to `docs/AI_artifacts/3_factual-code-verification/p3-diagram-model-extractor.md`
  with Spec Verification table + Invalidated Assumptions section.
- Return counts: validated / invalidated / unverifiable + list any invalidated IDs.
- CodeGraph-first (repo is indexed): use codegraph MCP tools / shell.
After verify: review gate → if any invalidated assumption, loop-back (cap 2 auto
cycles, escalate on type-c/regression); if all validated, dispatch plan step.

## What P3 is

Deterministic script `ssot-diagram/graph_model.py` — reads codegraph DB (read-
only, `mode=ro&immutable=1`) + curated decision index + a config → emits one
`diagram-model.json`. 3-level: macro (components) → micro (files/classes) →
nano (functions), rolled-up edges with counts, decision nodes from verified
anchors (status badges), content signature on every node. Same inputs ⇒ byte-
identical JSON. No LLM in any verdict. Ships via `manifest.json`, CLI-first.

## 6 locked contracts (from grill, DO NOT re-litigate)

1. **Pilot repo = mkt_engine.** Extractor built in THIS repo; tests + golden
   model target `~/all-projects/mkt_engine` (TS/JS, 150 files, 1115 nodes, 8
   top-level dirs, 8 ADRs/25 anchors — roadmap's named pilot). Decision-node
   merge exercised. Determinism/schema tests run NOW against mkt_engine seed
   index (0/25 verified); full "every verified anchor appears once" assertion
   re-runs after P2 (external session) lands.
2. **No-config `extract` = fail-loud.** Exits "run `bootstrap-config` first"
   when no `ssot-diagram.config.json`. Two clean contracts: `bootstrap-config`
   seeds+writes; `extract` reads+emits. Matches decision_index fail-loud style.
3. **Nano cap = cap N (default 8, config-tunable) per micro by caller count,
   collapse rest to one synthetic "+K more" node** — kind=collapsed,
   sig=sha256 over collapsed members' hashes. Honest about dropped symbols.
4. **Multi-anchor decision = attach to every component owning ≥1 verified
   anchor** — id `decision:<ADR-ID>@<component-id>`. Status badge consistent
   across attachments (one underlying decision). Respects frozen 3-level
   hierarchy (NO phantom cross-cutting component — Block 4a).
5. **Pre-extract guard = warn-and-continue.** If index has `verified:false` OR
   not-FRESH anchors → print stderr warning pointing at `decision_index refresh
   <id>`, exit 0. Model still truthful (unverified → no decision node). Keeps
   P3 parallel-runnable now. Staleness consumed via L1 badge logic (recompute
   live sig per anchor, compare — same as decision_index `current_sig`), NOT a
   separate `status` re-run.
6. **Edge encoding = per-node `edges[]` array** —
   `{source, target, kind, count, sample_callers[file:line ×3]}`, directional
   (source→target = source depends on target), kind∈{calls,imports,references}.
   Sample_callers top 3 with STABLE tiebreak (call-site file:line ascending) —
   determinism depends on it. Matches Block 4c. Plan-visualizer reads
   count+sample_callers without DB.

## Open HOW questions (design step owns — NOT to re-grill)

- `ssot-diagram.config.json` exact schema (glob→component-name map shape,
  multi-match disambiguation, unknown-path component placement). Block 4 PENDING.
- Full field list per model node (Block 4b lists FROZEN subset
  `id,kind,name,path,signature`; extras like `docstring`, `caller_count`,
  `qualified_name` PENDING).
- `bootstrap-config` output format. Does `extract` re-seed if config drifted
  vs files changed? (No — fail-loud contract says extract only reads. Re-seed
  is a separate `bootstrap-config --force` action, like decision_index.)
- `sample_callers` stable ordering — locked above (file:line ascending); design
  confirms + documents.
- nano-cap "caller count" — incoming `calls`+`references`+`imports` edges on
  the symbol; design confirms the exact edge-kind set.

## Tier-A landmine (acknowledged, scout on disk)

Macro component grouping = human call. `bootstrap-config` seeds from top-level
dirs; human curates `ssot-diagram.config.json` (glob→name) before any narrative
pinning (P4). Prior art: `docs/AI_artifacts/0_scout/macro-component-grouping-prior-art.md`
(Structurizr, dependency-cruiser, ArchUnit — all converge on dir-as-default +
curated override).

## mkt_engine DB reality (queried 2026-07-04, for design grounding)

- 150 files, 1115 nodes, 8 top-level dirs (tests/47, lib/46, components/28,
  app/16, scripts/3, prisma/1, docs/1, .claude/1).
- Node kinds: import(439), function(232), file(148), constant(136),
  interface(92), method(20), type_alias(20), variable(12), class(10),
  property(6).
- Edge kinds: calls(1124), contains(961), imports(793), references(428),
  instantiates(17), implements(5).
- `file` is BOTH a node kind AND a `files` table row. `contains` edges =
  file→symbol containment. Only 10 `class` nodes → "micro = class when dominant"
  collapse rarely triggers; micro = file for nearly everything in mkt_engine.
- nodes cols: id, kind, name, qualified_name, file_path, language, start_line,
  end_line, start_column, end_column, docstring, signature, visibility,
  is_exported, is_async, is_static, is_abstract, decorators, type_parameters,
  return_type, updated_at.
- files cols: path, content_hash, language, size, modified_at, indexed_at,
  node_count, errors.
- edges cols: id, source, target, kind, metadata, line, col, provenance.

## mkt_engine decision index state (P2 LANDED, verified 2026-07-04)

8 decisions (ADR-0001..0008), **33 anchors, ALL `verified:true`, 0 STALE**
(P2 curation by the parallel session landed). `decision_index status` exits 0
all-FRESH. Index at `~/all-projects/mkt_engine/docs/decision-index.json`.
This means P3's "every verified anchor appears once" exit criterion is testable
NOW — no longer waiting on P2. The pre-extract guard's `verified:false` branch
is unexercised against mkt_engine (no live unverified anchors left); the guard
is still built (contract 5 FROZEN) but the golden test for the unverified case
needs a SYNTHETIC fixture, not the live repo.

## Refused alternatives (record — don't re-debate)

- Pilot = this repo (Python) — no decision index; misses decision-merge path.
- No-config auto-seed / silent — kills curation nudge / fails silently.
- Nano silent-truncate / no cap — hidden drops / hairball.
- Decision single-anchor attach — arbitrary (doc-order), hides cross-cutting.
- Synthetic cross-cutting component — violates Block 4a frozen 3-level.
- Fail-loud extract guard requiring all-FRESH+verified — couples P3 runnability
  to P2 completion, contra roadmap "start in parallel."
- Adjacency-map / DB-mirror edge encoding — loses counts/evidence or re-derives
  DB shape forcing renderer to re-aggregate.

## Parallel work: P2 (external session)

Your other agent session curates `~/all-projects/mkt_engine/docs/decision-index.json`
(human-gated: drop wrong anchors, disambiguate, set supersedes, refresh →
verified:true). P2 makes the index honest; P3 makes the map. They meet at the
decision-node merge test. P3 ships full picture after P2 lands. See memory
`parallel-phase-ab-split.md`.
