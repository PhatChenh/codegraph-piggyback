# Plan: P3 — Diagram Model Extractor (`diagram-model.json`)
_Last updated: 2026-07-04_
_Status: [ ] pending_

## Analysis

P3 builds the deterministic heart of the ssot-diagram pipeline: a new script
`ssot-diagram/graph_model.py` that turns the codegraph SQLite database plus the
curated decision index plus a curated `ssot-diagram.config.json` into one
byte-deterministic `diagram-model.json` — the only file the future renderer
(P5) and the plan-visualizer will read. The build adds two CLI verbs
(`extract` and `bootstrap-config`), one config-schema owner, one manifest
entry, and one golden-model test fixture. It does NOT add an LLM, a hook
(P6 owns hook wiring), or a renderer (P5). The verdict is pure computation
over the DB every time.

What this build connects to and why:

- **Connects UP to P1** (`ssot-diagram/decision_index.py`) as a read-only
  sibling import. P1 already ships the DB open (`mode=ro&immutable=1`), the
  schema guard, the content-signature recipe (`file_content_hash`,
  `symbol_spans`, `slice_hash`, `_sha256`), the anchor staleness helpers
  (`current_sig`, `anchor_status`, `_evaluate`), and `parse_ref` + `load_index`.
  P3 imports these as `di.<name>` via the exact seam `decision_hook.py:22-23`
  established — `sys.path.insert(0, str(Path(__file__).resolve().parent))`
  then `import decision_index as di`. Verified fact (codegraph_callers):
  `decision_index` has exactly one sibling importer today (`decision_hook.py`);
  `graph_model.py` becomes the second sibling, making it P1's third caller
  alongside P1 itself and the hook. Per ADR 0001, the `_shared/` clean-cutover
  that would lift these 11 symbols into `_shared/db.py` + `_shared/sig.py` is
  deferred to Phase B as a separate, single-shot task — it is NOT this plan.
- **Connects DOWN to P4/P5/plan-visualizer** via the FROZEN Block 4 contract
  (`../docs/roadmap/skeleton-contracts.md`): three-level hierarchy
  (component → micro → nano), per-node `edges[]` with counts and a stable
  3-row `sample_callers[{file,line}]`, decision nodes with a
  `FRESH|STALE|ORPHANED|superseded` badge, content `signature` on every node.
  These consumers are not built yet; the Block 4 contract is the seam.
- **Connects SIDEWAYS to `manifest.json`** by adding one
  `diagram-model` entry (script, repo scope, `hooks: []` — CLI-first). The
  PostToolUse re-extract hook is P6, NOT this plan.

Why this approach (not another): the design's Option A (sibling import of P1)
is FROZEN (per ADR 0001, accepted 2026-07-04). The 6 grill contracts are
FROZEN. The 5 red-team fixes (assumptions A13–A17) are FROZEN, verified
against the live `mkt_engine` DB, and load-bearing. `graph_model.py` lives
in the same directory as `decision_index.py` so the sibling import resolves
without `sys.path` mutation beyond the established one-liner. P3's own code
concentrates where the design says the risk is — component grouping, edge
roll-up with the two-shape imports split, decision-node merge with the
worst-case badge, and byte-deterministic serialization (stricter than P1's
`save_index`: `sort_keys=True`, atomic temp+`os.replace`, fixed indent + trailing
newline). Everything else is reuse.

Five carry-forward items from factual-code-verification are baked into the
steps below (do NOT re-verify — verify already confirmed them against live
code/DB):

1. **A1 NUANCE — id-synthesis code comment.** `nodes.id` mixes two forms:
   226/232 function nodes have `function:<32-hex>` content-hash ids; 6
   React-hook nodes have `hook:<path>:<name>:<line>` path-derived ids. The
   spec's prescription ("synthesize your own id; never pass `nodes.id`
   through") is correct for BOTH forms. Step 7 (id synthesis) carries a code
   comment forbidding dispatch-on-source-id, so a future contributor does not
   "simplify" by reading `nodes.id`.
2. **E1 exit-code decision (PLANNER OWNS — type-b execution detail).** P1's
   `die()` exits **2** (`decision_index.py:372-374`); spec contract C2 /
   component 4 say "exit 1". Resolution chosen: **mirror P1 → exit 2**.
   Justification (1 line): P3 reuses `di.die()` verbatim for its fail-loud
   paths (no-config, schema drift, `--force` gate), so its exit code is
   inherited automatically; introducing a divergent exit 1 would mean P3
   writes its own `die()` for the same kind of failure — that is the
   inconsistency, not the consistency. Documented at every fail-loud step.
3. **Component 8 pin — `edges.line`.** `edges.line` is 100% populated for
   calls/imports/references/instantiates/implements; 0% for `contains` (which
   P3 does not read as an edge). Step 8 pins: "always read `line`; null only
   for `contains` (unused)." No skip/null/0 fallback branches needed.
4. **Component 12 atomicity — inherit P1's pattern.** P1's `save_index`
   (`decision_index.py:175-179`) already does atomic temp+`os.replace`.
   Step 12 inherits this verbatim; atomicity is NOT an open question.
5. **R4 extended schema guard — REQUIRED.** P1's `verify_schema` checks only
   5 nodes cols + 2 files cols. The extra cols P3 reads (`kind`, `id`,
   `docstring`, `is_exported`, `signature`, all `edges.*`) are unguarded by
   P1. Step 4's `_verify_model_schema` extends P1's check — call
   `di.verify_schema(con, path)` first, then assert P3's extras.

## Files

- `ssot-diagram/graph_model.py` — **create.** The extractor + `bootstrap-config`
  CLI. New module; sibling-imports `decision_index as di`. ~400 lines
  (design's estimate; the planner does not pin a line count). Hosts Steps 1-13.
- `ssot-diagram/test_graph_model.py` — **create.** pytest golden + determinism
  + 5 red-team regressions + fail-loud + bootstrap-config tests (Step 14).
- `ssot-diagram/testdata/mkt_engine.model.json` — **create (committed).**
  Golden model artifact, re-recorded only via `--update-golden` (Step 14).
  Lives under `testdata/` so it ships with the tool.
- `ssot-diagram/ssot-diagram.config.json` — **create (curated)**. The glob →
  component-name map. `bootstrap-config` writes the seed; a human curates
  before `extract` runs against `mkt_engine`. Not auto-generated by `extract`.
  (P3 owns the schema; first concrete instance is the mkt_engine pilot config.)
- `manifest.json` — **modify.** Add one entry under key `diagram-model`:
  `{"script": "ssot-diagram/graph_model.py", "scope": "repo", "desc":
  "ssot-diagram P3 — extract diagram-model.json from codegraph DB + decision
  index", "hooks": []}`. Additive only — do NOT edit the existing 3 entries
  (`impact-analyzer`, `codegraph-gate`, `decision-index`).
- `ssot-diagram/decision_index.py` — **READ-ONLY dependency, NEVER edit.**
  P3 imports it as a sibling; ADR 0001 forbids any edit to P1 in this phase.
  Listed here so the implementer knows the file is load-bearing (11 symbols
  P3 reaches across) but explicitly off-limits (see Delegation Authority).
- `ssot-diagram/decision_hook.py` — **READ-ONLY reference, NEVER edit.** The
  sibling-import precedent (`decision_hook.py:22-23`). Step 1 mirrors its
  import block verbatim. Listed so the implementer knows the pattern's source
  but does not modify it.

## Delegation Authority

The implementer may touch ONLY the files in ## Files that are marked
"create" or "modify" — i.e. `graph_model.py`, `test_graph_model.py`,
`testdata/mkt_engine.model.json`, `ssot-diagram.config.json`, and the
additive `manifest.json` entry. Nothing outside this set is in scope.

- **Allowed set** = the union of every step's "Files to modify" (= the
  ## Files list above). Nothing outside it.
- A file in ## Files but assigned to ANOTHER step = a dependency (run steps
  per ## Implementation Order), not a deviation.
- A file NOT in ## Files = STOP, do not silently edit. Record in an
  `### Out-of-scope touches` block of the end-of-implementation report: the
  file, why the step needed it, the change, and whether it signals a
  plan/spec gap. Present all such entries at the end.
- **Hard off-limits (escalate before touching):**
  - `ssot-diagram/decision_index.py` — P1's engine; a read dependency for
    P3 (the 11 siblings per ADR 0001). codegraph_callers confirms P1 has
    exactly one sibling importer today (`decision_hook.py`); P3 becomes the
    second. Any edit to P1's recipe (signature, `anchor_status`,
    `_evaluate`, `parse_ref`) breaks P1's own tests, the hook, AND P3 —
    escalate, do not edit. The Phase B `_shared/` cutover is the sanctioned
    moment to touch the recipe.
  - `ssot-diagram/decision_hook.py` — the existing hook; its import block is
    the precedent Step 1 mirrors verbatim. Do not modify.
  - `manifest.json` — additive only. Do not edit or remove the existing
    `impact-analyzer`, `codegraph-gate`, or `decision-index` entries.
  - The codegraph DB at `~/all-projects/mkt_engine/.codegraph/codegraph.db`
    — read-only, `mode=ro&immutable=1`, NEVER write (CLAUDE.md Critical
    Rule). The live `~/all-projects/mkt_engine/docs/decision-index.json`
    is a read-only input too; P3 reads it, never writes it.
  - Frozen contracts and source-of-truth docs —
    `../docs/roadmap/skeleton-contracts.md` (Block 1, 4, 5), `adrs/0001-…md`,
    `CLAUDE.md`, the design + spec + verification artifacts under
    `docs/AI_artifacts/`. Doc-sync is the pipeline-end job, not the
    implementer's.
  - `_shared/` directory — `_shared/design.md` exists; no `_shared/*.py` does.
    Do NOT create `_shared/db.py` / `_shared/sig.py` here (Option C, rejected;
    ADR 0001 scopes that to Phase B).

## Rules Applied

No matching rules. — the constraint preload returned empty (this repo has no
authored Writ rules in `docs/rules/`); only CLAUDE.md's project rules apply
(read-only DB, manifest registration, signature pinning, no-LLM verdicts,
sibling-import reuse per ADR 0001). Cited inline in each step where they bind.

## Capabilities

- [ ] **C-CLI-1** — `python3 ssot-diagram/graph_model.py extract --help` lists
  `--db`, `--index`, `--config`, `--out`, `--nano-cap` with correct defaults;
  `bootstrap-config --help` lists `--db`, `--out`, `--force`. (Step 2.)
- [ ] **C-IMPORT-1** — `python3 -c "import sys; sys.path.insert(0,
  'ssot-diagram'); import graph_model"` succeeds; the sibling-import seam
  works without error. (Step 1.)
- [ ] **C-CONFIG-FAIL** — `extract` with no `ssot-diagram.config.json`
  present exits 2 (E1 decision: mirroring P1's `die()`) with stderr
  containing "run `bootstrap-config` first" (contract C2). (Steps 3, 10.)
- [ ] **C-CONFIG-SHAPE** — `load_config` validates `version` (int, required),
  `components[]` (ordered), `default_component` (must exist in components),
  `nano_cap` (int, optional, default 8); duplicate component `id` exits 2;
  missing `default_component` exits 2. (Step 3.)
- [ ] **C-SCHEMA-GUARD** — `_verify_model_schema` calls `di.verify_schema`
  first, then asserts P3's extras
  (`nodes.{kind,id,docstring,is_exported,signature}`,
  `edges.{source,target,kind,line}`); passes against the live DB; exits 2
  on a synthetic DB missing `nodes.kind`. (Step 4, R4 carry-forward #5.)
- [ ] **C-GROUPING** — every indexed `mkt_engine` file lands in exactly one
  component (counts sum to total files); files matching no glob land in
  `cmp-misc`; first-match wins on multi-match + a sorted stderr warning
  fires. (Step 5.)
- [ ] **C-MICRO** — every `mkt_engine` file produces exactly one micro; a
  file with no classes → `dominant_class: null`; a file with one class →
  `dominant_class: <qname>`; the micro `id` is path-derived, never `nodes.id`.
  (Step 6.)
- [ ] **C-NANO-CAP** — a micro with 12 functions and `--nano-cap 8` produces
  8 visible nanos + 1 `collapsed` node (`collapsed_count=4`); the selected 8
  + collapsed 4 are exactly what the deterministic sort
  (`caller_count` DESC, `qualified_name` ASC, `path` ASC) picks — including
  the zero-caller tie case (A17). A micro with 5 functions and cap 8
  produces 5 nanos + 0 collapsed. (Step 7.)
- [ ] **C-ID-COMMENT** — the id-synthesis code path in `graph_model.py`
  carries a comment forbidding dispatch-on-`nodes.id` (A1 nuance carry-forward
  #1). (Step 7.)
- [ ] **C-EDGES-CALLS** — every nano micro node whose function has incoming
  calls carries a non-empty `edges[]`; `instantiates` edges appear as
  `kind: "calls"`; `implements` edges appear NOWHERE in the model. (Step 8,
  A16.)
- [ ] **C-EDGES-IMPORTS** — zero self-micro `imports` edges appear (the 440
  `file→import:` placeholder edges are dropped); every intra-repo symbol
  import rolls up as `file → target-symbol's-owning-micro` (target micro =
  target symbol's file's micro, NOT target-as-nano). (Step 8, A14.)
- [ ] **C-EDGES-REFERENCES** — a nano with 5 incoming `references` and 0
  incoming `calls`/`instantiates` has `caller_count = 0` AND the `references`
  still appear in `edges[]`. (Step 8, A15.)
- [ ] **C-EDGES-LINE-PIN** — `sample_callers[].line` is read from
  `edges.line` directly; null only for `contains` (which P3 does not read as
  an edge). No skip/null/0 fallback branches for the kinds P3 reads.
  (Step 8, carry-forward #3.)
- [ ] **C-SAMPLE-CALLERS-SHAPE** — every `sample_callers` entry is
  `{file, line}` with NO `symbol` key; the 3 emitted are the
  lexicographically smallest `(file, line)` ascending, stable across two
  runs; file-sourced edges populate `file`/`line` from the source `file:`
  node's `file_path` + `edges.line`. (Step 8, A13.)
- [ ] **C-DECISION-MERGE** — the 8 `mkt_engine` ADRs produce 8 decision nodes,
  each attached to ≥1 component, each `status: FRESH` (per A9 — pilot index
  fully curated). A synthetic `verified:false` anchor produces NO decision
  node for that ADR; a synthetic ORPHANED anchor produces a decision node
  with the ORPHANED (worst-case) badge. (Step 9.)
- [ ] **C-PRE-EXTRACT-GUARD** — against the live `mkt_engine` index (all
  verified, all FRESH), the guard emits nothing and `extract` exits 0;
  against a synthetic `verified:false` fixture, the guard warns on stderr
  pointing at `decision_index refresh <id>` and `extract` still exits 0 and
  still writes the model. (Step 10, contract C5.)
- [ ] **C-ID-SYNTHESIS** — no model node's `id` equals any `nodes.id` value
  in the DB; component ids match the config's `id` field; micro/nano/decision
  ids follow the design's path-derived forms. (Step 11.)
- [ ] **C-DETERMINISM** — two consecutive `extract` runs on `mkt_engine`
  produce files with identical sha256; 10× runs produce identical sha256
  every time; the produced JSON has `sort_keys=True`; `generated_at` is
  `null`; the output is written atomically (temp + `os.replace`, mirroring
  P1's `save_index`). (Step 12, carry-forwards #2, #4.)
- [ ] **C-MANIFEST** — `piggyback status` lists `diagram-model`; the entry
  has `scope: "repo"`, `hooks: []`, and the script path points at
  `ssot-diagram/graph_model.py`. (Step 13.)
- [ ] **C-BOOTSTRAP-CONFIG** — on a fresh repo, `bootstrap-config` writes a
  config with one component per top-level dir + a `cmp-misc` default +
  `nano_cap: 8`; a second `bootstrap-config` without `--force` exits 2
  ("exists — refusing to overwrite a curated config. Pass `--force` to
  reseed." — full P1 string verbatim, per verify); `--force` reseeds. (Step
  13, A7, E1 exit 2.)
- [ ] **C-GOLDEN** — `extract` against the live `mkt_engine` DB + index +
  config produces JSON byte-identical to
  `ssot-diagram/testdata/mkt_engine.model.json` (sha256 comparison); the
  golden is re-recorded only via the hidden `--update-golden` flag. (Step 14.)
- [ ] **C-TESTS-HERMETIC** — the determinism + 5 red-team regression tests
  (A13-A17) + `bootstrap-config` `--force` + no-config fail-loud + config
  validation tests all run against in-memory synthetic fixtures
  (`sqlite3` tmp_path) and pass without the live pilot DB; the golden test
  is `pytest.mark.skipif` on the pilot DB path (A24). (Step 14.)

## Implementation Order

The dependency graph below is derived FACTUALLY from `codegraph_callers` +
`codegraph_explore` on the symbols each step touches (the carry-forward E1
note + spec component table), NOT from inference. Codegraph evidence:

- `decision_index` (the module) has exactly one sibling importer today:
  `ssot-diagram/decision_hook.py` (codegraph_callers). P3
  (`graph_model.py`) becomes the second sibling. The import seam — and
  therefore Step 1 — depends on NOTHING inside this repo's build (P1 already
  shipped and tested).
- `_evaluate` (P1's helper, `decision_index.py:290`) has exactly 3 callers
  today: `decision_hook.main`, `cmd_status`, `cmd_check` (codegraph_callers).
  Step 10's pre-extract guard becomes the fourth caller across the leading
  underscore — safe per ADR 0001.
- `anchor_status` (`decision_index.py:154`) has exactly one caller
  (`_evaluate`) (codegraph_callers). Step 9's decision-node merge calls
  `di.anchor_status` directly per spec — adding a second caller; safe.
- `save_index` (`decision_index.py:175`) has only `cmd_bootstrap` +
  `cmd_refresh` as callers (codegraph_callers). P3 does NOT call `save_index`
  — Step 12 writes its own `serialize_model` (stricter: `sort_keys=True`).
  This is NOT a coupling.
- `parse_ref` calls `die` (codegraph_explore flow: `current_sig → parse_ref
  → die`). Step 9 calls `di.parse_ref` per spec; the `die()` exit 2 path is
  inherited (E1 carry-forward #2).

**Dependency table:**

| Step | Produces | Depends on | Why (codegraph fact) |
|---|---|---|---|
| 1 | sibling-import seam + argparse skeleton + manifest entry | — | none (P1 shipped; `decision_index` is on disk) |
| 2 | full CLI flag surface (`args` namespace) | Step 1 | argparse lives in `graph_model.py`, which Step 1 creates |
| 3 | `load_config(path) -> dict` | Step 1 | standalone helper, no DB; reads the curated `ssot-diagram.config.json` only |
| 4 | `_verify_model_schema(con, path)` | Step 1 | calls `di.verify_schema` first (verified at `decision_index.py:85`); then asserts extras |
| 5 | `group_components` + `seed_config` | Steps 2,3 | reads parsed `--config` arg + the loaded config dict; needs `files.path` (DB step 4 connection) |
| 6 | `select_micros` | Step 5 | needs the grouping dict to know which files belong to which component; queries `nodes.kind='class'` |
| 7 | `select_nanos` + cap + collapse | Step 6 | needs micros to query nanos per micro; computes `caller_count` (reads `edges`) |
| 8 | `roll_up_edges` (per-node `edges[]`) | Steps 5,6,7 | reads raw `edges` table once; joins to `nodes` on `nodes.id` for source/target file_path; needs component/micro mapping from 5,6,7 |
| 9 | `merge_decisions` (decision nodes + `decisions[]` forward pointers) | Steps 5,6,10 | needs grouping + micros to find owning components; needs `di.anchor_status` (verified) per anchor for the badge; pre-extract guard (10) runs first per C5 but only warns |
| 10 | `pre_extract_guard` (warn-and-continue) | Steps 2,3,4 | needs parsed args + `di.load_index` (verified at `decision_index.py:163`) + `di._evaluate` (verified at `:290`) for not-fresh walk; runs after schema guard (4) so the hard fail precedes the soft warn |
| 11 | id synthesis + `children[]` + back-pointers + assembled node dict | Steps 5,6,7,8,9 | pure in-memory assembly; no DB access; everything it assembles comes from 5-9 |
| 12 | `serialize_model` (byte-deterministic writer) | Step 11 | takes the assembled dict; writes `diagram-model.json`; honors `--out` (Step 2) + `--update-golden` |
| 13 | manifest entry + `bootstrap-config` writer | Steps 1,2,5 | the writer is `seed_config` from Step 5; the manifest entry is additive JSON |
| 14 | tests + golden fixture | Steps 1-13 | exercises the assembled extractor end-to-end |

**Parallel waves** (each wave's steps must touch DISJOINT files — verified
against the ## Files list: no two steps in a wave write the same file):

- **Wave A (no deps, must run first):** Step 1 (creates `graph_model.py` +
  the manifest entry — manifest touched here once, then never again).
- **Wave B (after A, parallel-safe — disjoint code regions inside
  `graph_model.py`):** Steps 2, 3, 4, 13 (manifest entry already wired by 1;
  Step 13's bootstrap-config writer is independent of the extract path).
  NOTE — these are "logically parallel" stub implementations; the
  implementer writes them in any order, all into `graph_model.py`, but each
  is independently testable.
- **Wave C (after B):** Steps 5, 10 (grouping + pre-extract guard; both read
  the DB but write disjoint code; both depend on Steps 2-4).
- **Wave D (after C — sequential, each depends on the previous's output):**
  Step 6 → Step 7 → Step 8 → Step 9 → Step 11 → Step 12 → Step 14.
  This is the critical path: deterministic assembly + serialization +
  golden test. No parallelism here — each consumes the previous's dict.
  Within Step 8, the calls/imports/references roll-ups are independent of
  each other but share the `edges`-read logic, so they are sequential
  inside the step.

**Critical path (solo linear order):** Step 1 → 5 → 6 → 7 → 8 → 11 → 12 → 14.
Wave B's isolation work (Steps 2/3/4/13) is on the side; the critical path is
the extract pipeline's data flow.

**Solo linear order for a single implementer:** 1, 2, 3, 4, 5, 10, 6, 7, 8,
9, 11, 12, 13, 14. (Step 13 and Step 14 are bookkeeping/test work after the
extract pipeline is wired.)

## Steps

### Step 1 — Sibling-import bootstrap + module skeleton + manifest entry

**Goal:** Establish the import seam that lets `graph_model.py` reach P1's
recipe without copying it, plus the empty CLI surface so every later step
has a place to hang, plus the manifest entry so the script is shippable from
the first commit.

**Design:**
A new file `ssot-diagram/graph_model.py` is created. Its very first lines
mirror the `decision_hook.py:22-23` precedent verbatim — insert the script's
own directory to `sys.path`, then `import decision_index as di`. This is the
ADR 0001 import block. Below it, an `argparse` subcommand dispatcher with two
empty subcommands — `extract` and `bootstrap-config` — each printing "not
implemented" and exiting 2 (E1 carry-forward #2) for now. The manifest entry
(component 13 of the spec) is wired in this step so the install rail knows
about `diagram-model` from the first commit. No business logic yet.

**Actions:**
1. Create `ssot-diagram/graph_model.py`.
2. Add the sibling-import block as the first executable lines:
   `sys.path.insert(0, str(Path(__file__).resolve().parent))` then
   `import decision_index as di  # noqa: E402` — verbatim from
   `decision_hook.py:22-23`.
3. Add `import argparse`, `import json`, `import sqlite3`, `import hashlib`,
   `import os`, `from pathlib import Path`, `import sys`, `import fnmatch`
   (each stdlib import as needed by later steps; no third-party packages).
4. Add `def main():` with an `argparse.ArgumentParser` and two subparsers
   (`extract`, `bootstrap-config`); each subparser's `set_defaults(func=...)`
   points at a `cmd_extract` / `cmd_bootstrap_config` stub that prints "not
   implemented" to stderr and `sys.exit(2)` (E1).
5. Add `if __name__ == "__main__": main()` at the bottom.
6. Add the manifest entry to `manifest.json` under key `diagram-model`:
   `{"script": "ssot-diagram/graph_model.py", "scope": "repo", "desc":
   "ssot-diagram P3 — extract diagram-model.json from codegraph DB +
   decision index", "hooks": []}`. Additive only — do not touch the existing
   3 entries.
7. Commit boundary: "feat(ssot-diagram): P3 skeleton — sibling import + CLI
   stubs + manifest entry" (intentionally not "P3 done"; this is the
   shippable shell).

**Files to modify:**
- `ssot-diagram/graph_model.py` — create with the import block + dispatcher
  + stubs.
- `manifest.json` — add the `diagram-model` entry (additive; no edits to
  other entries).

**Test criteria:**
- [ ] `python3 -c "import sys; sys.path.insert(0, 'ssot-diagram'); import
  graph_model"` succeeds without error (the sibling-import seam works).
  (Capability C-IMPORT-1.)
- [ ] `python3 ssot-diagram/graph_model.py extract` prints "not
  implemented" to stderr and exits 2 (E1 carry-forward #2 — exit 2, NOT 1).
- [ ] `python3 ssot-diagram/graph_model.py bootstrap-config` does the same.
- [ ] `piggyback status` lists `diagram-model` in its output (capability
  C-MANIFEST partial — full manifest wired).

**Status**: [ ] pending

---

### Step 2 — CLI argument parser (the two subcommands' full surface)

**Goal:** Pin the exact flags each subcommand accepts, so every later step
reads from a parsed `args` object, not ad-hoc `sys.argv` parsing.
Implements spec component 2.

**Design:**
The `extract` subcommand gets five flags: `--db DB` (optional; default
walks up via `di.find_db`), `--index INDEX` (optional; default
`docs/decision-index.json` via `di.default_index_path`), `--config CONFIG`
(optional; default `ssot-diagram/ssot-diagram.config.json`), `--out OUT`
(optional; default `ssot-diagram/diagram-model.json`), `--nano-cap N`
(optional int; default from config's `nano_cap` field, fallback 8). Plus a
hidden `--update-golden` flag (store_true) used only by the test harness —
it re-writes the committed golden JSON instead of asserting against it. The
`bootstrap-config` subcommand gets three flags: `--db DB`, `--out CONFIG`
(default `ssot-diagram/ssot-diagram.config.json`), `--force` (store_true).

**Actions:**
1. In `graph_model.py`, replace Step 1's stub subparsers with full argparse
   subparsers per the surface above.
2. `extract`: add `--update-golden` as a hidden flag (suppress in `--help`
   via `help=argparse.SUPPRESS`) — its only consumer is Step 14's test
   harness.
3. `bootstrap-config`: add `--force` as `action="store_true"` (mirrors
   `decision_index.py:391`).
4. Replace the stub `cmd_extract` / `cmd_bootstrap_config` with no-op
   functions that still print "not implemented" + `sys.exit(2)` for now
   (Steps 5-13 fill them in).
5. Confirm `argparse` exits 2 on unknown flags (the default behavior) — no
   custom exit code needed (E1: exit 2, matches P1's convention since
   argparse uses exit 2 for usage errors).

**Files to modify:**
- `ssot-diagram/graph_model.py` — extend the argparse surface.

**Test criteria:**
- [ ] `graph_model.py extract --help` lists `--db`, `--index`, `--config`,
  `--out`, `--nano-cap` with the correct defaults; `--update-golden` is
  suppressed (not shown in `--help`).
- [ ] `graph_model.py bootstrap-config --help` lists `--db`, `--out`,
  `--force`.
- [ ] `graph_model.py extract --nano-cap 3` parses `3` as the integer 3
  (assert via a debug print or a unit test calling
  `parser.parse_args(['extract', '--nano-cap', '3'])`).
- [ ] An unknown flag exits 2 with a usage message (capability C-CLI-1).

**Status**: [ ] pending

---

### Step 3 — Config loader (`ssot-diagram.config.json` reader + fail-loud guard)

**Goal:** Read the curated config, validate its shape, and hand the rest of
the script a typed dict; fail loud when the config is absent (contract C2).
Implements spec component 3.

**Design:**
A `load_config(path: Path) -> dict` function. On missing file, it exits 2
(E1: mirroring P1's `die()` exit code, NOT spec's literal "exit 1") with
the message "ssot-diagram.config.json not found — run `bootstrap-config`
first" (or use `di.die(...)` to inherit exit 2 verbatim — preferred). On
bad JSON, exits 2 with the parse error. Validates: top-level `version` (int,
required, must be `1` — strict per spec's open decision), `components[]`
(required, ordered), `default_component` (string, required, MUST exist in
`components[]` — fail loud if missing per C2's "must not delete cmp-misc"
posture), `nano_cap` (int, optional, default 8). Each `components[]` entry
must have `id` (string, unique within file), `name` (string), `glob`
(string); `notes` is optional and ignored. On any validation failure,
`di.die(...)` (inherit exit 2 per E1).

**Actions:**
1. Add `def load_config(path: Path) -> dict:` in `graph_model.py`.
2. Missing-file branch: `if not path.is_file(): di.die(f"{path} not found
   — run `bootstrap-config` first")`. (`di.die` exits 2 — E1 carry-forward
   #2.)
3. Bad-JSON branch: wrap `json.loads(path.read_text())` in `try/except
   json.JSONDecodeError as e: di.die(f"{path} is not valid JSON: {e}")`.
4. Validate `isinstance(doc.get("version"), int) and doc["version"] == 1`
   else `di.die(f"{path}: version must be 1, got {doc.get('version')!r}")`.
5. Validate `isinstance(doc.get("components"), list) and len(...) > 0` else
   `di.die(...)`. Validate `isinstance(doc.get("default_component"), str)`
   and `doc["default_component"]` is among the `components[].id` values
   else `di.die(...)`.
6. Validate each `components[]` entry has `id` (str), `name` (str), `glob`
   (str); detect duplicate `id` via a seen-set, `di.die(...)` on collision.
7. Default `nano_cap = doc.get("nano_cap", 8)`.
8. Return the validated dict (callers read `doc["components"]`,
   `doc["default_component"]`, `doc["nano_cap"]`).

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `load_config`.

**Test criteria:**
- [ ] A valid config file loads and returns a dict matching the schema.
- [ ] A missing config exits 2 (E1: NOT 1) with stderr containing "run
  `bootstrap-config` first" (capability C-CONFIG-FAIL).
- [ ] A config missing `default_component` exits 2.
- [ ] A config with a duplicate `id` in `components[]` exits 2.
- [ ] A config with `version: 2` exits 2 (strict `1` only) (capability
  C-CONFIG-SHAPE).

**Status**: [ ] pending

---

### Step 4 — Extended schema guard (P3's extra DB columns)

**Goal:** Fail loud if the codegraph schema has drifted in a way that would
make P3 emit wrong fields — extending P1's `verify_schema` with the columns
P3 reads. Implements spec component 4. **Required** per R4 carry-forward #5
(P1's guard does NOT cover these — verify confirmed).

**Design:**
A local `_verify_model_schema(con, path) -> None` function. It calls
`di.verify_schema(con, path)` FIRST (reuses P1's check for
`nodes.{name, qualified_name, file_path, start_line, end_line}` and
`files.{path, content_hash}` — verified at `decision_index.py:90-92`), then
checks P3's extra columns:
`nodes.{kind, id, docstring, is_exported, signature}`,
`edges.{source, target, kind, line}` (and the table `edges` itself exists).
On any missing column, `di.die(f"{path} schema not recognized (codegraph
version drift?); refusing to guess.")` (same posture + message shape as
P1's `verify_schema` — exit 2 per E1).

**Actions:**
1. Add `def _verify_model_schema(con, path) -> None:`.
2. First line: `di.verify_schema(con, path)` — P1's hard fail runs first
   (verified at `decision_index.py:85-92`).
3. Then `node_cols = {r[1] for r in con.execute("PRAGMA table_info(nodes)")`
   and assert `{"kind", "id", "docstring", "is_exported", "signature"}
   <= node_cols` else `di.die(...)`.
4. `edge_cols = {r[1] for r in con.execute("PRAGMA table_info(edges)")}`
   and assert `{"source", "target", "kind", "line"} <= edge_cols` else
   `di.die(...)`.
5. Confirm `files.path` is in P1's check (it is — `need_files = {"path",
   "content_hash"}`).
6. Do NOT check `edges.metadata` (P3 reads `edges.line`, not `metadata` —
   spec component 4 open decision closed: no).
7. Wire `_verify_model_schema` into the DB-open path so callers see a
   ready-to-query connection: extend Step 6's open flow (after `di.open_db`)
   or call it in `cmd_extract` right after `di.open_db`.

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `_verify_model_schema`.

**Test criteria:**
- [ ] Against the live `mkt_engine` DB (read-only
  `mode=ro&immutable=1`), `_verify_model_schema` passes (all columns
  present per verify's A19/A21/A23 confirmation).
- [ ] Against a synthetic in-memory DB missing `nodes.kind`, exits 2 with
  "schema not recognized (codegraph version drift?); refusing to guess."
- [ ] `di.verify_schema` is called first (assert via mocking or by reading
  the source — the reuse is structural, not optional) (capability
  C-SCHEMA-GUARD).

**Status**: [ ] pending

---

### Step 5 — Component grouping (config-driven + top-level-dir seed)

**Goal:** Assign every indexed file to exactly one component, using the
config globs first-match-wins, with unmatched files falling into
`default_component`. Implements spec component 5.

**Design:**
A `group_components(con, config) -> dict[component_id, list[relpath]]`
function. It reads `files.path` (the authoritative file list — A22, verified
all node `file_path`s have a `files.path` row). For each path, walk
`config["components"]` in file order; the first entry whose `glob` matches
via `fnmatch.fnmatch(relpath, glob)` wins; if none match, the path goes to
`config["default_component"]`. When a path matches more than one glob,
emit a stderr warning listing the path + the conflicting component ids
(sorted by path for determinism — R3); still assign to the first. The
matched component's `path` field (for the component node, Step 11) is
derived from the common prefix of its matched paths (open decision per
spec: common-prefix, robust to arbitrary glob shapes).

Also implement `seed_config(con, out_path) -> None` here — the
`bootstrap-config` writer (consumed by Step 13). It scans the top-level
directories of indexed files (`relpath.split('/')[0]`), emits one
component per dir with `glob="<dir>/**"`, `id="cmp-<dir>"`,
`name="<Dir>"`. ALWAYS seeds a `cmp-misc` (id stable, name "Other",
`glob="__never_matches__"`) as `default_component` (OQ-DISAMBIG-1 resolved:
always seed). Writes via
`json.dumps(doc, indent=2, sort_keys=True) + "\n"` (determinism).

**Actions:**
1. Add `def group_components(con, config) -> dict[component_id, list[str]]:`.
2. `paths = [r[0] for r in con.execute("SELECT path FROM files ORDER BY
   path")]` — sorted for determinism.
3. For each path, iterate `config["components"]`; first
   `fnmatch.fnmatch(relpath, comp["glob"])` wins; collect into the dict
   under that component id. Unmatched → `config["default_component"]`.
4. Track multi-matches: if >1 glob matches a path, append
   `(path, sorted conflicting ids)` to a warnings list. After the loop,
   print each warning to stderr sorted by path.
5. Add `def seed_config(con, out_path, force=False) -> None:` for the
   `bootstrap-config` writer.
6. Inside `seed_config`: if `out_path.exists() and not force`:
   `di.die(f"{out_path} exists — refusing to overwrite a curated config.
   Pass --force to reseed.")` — full P1 string verbatim (verify flagged
   the spec omitted the suffix in A7; mirror P1's actual wording per
   carry-forward). Exit 2 via `di.die` (E1).
7. Build the seed config: top-level dirs from `set(p.split('/')[0] for p
   in paths if '/' in p)`, plus `cmp-misc`. Each entry: `{"id":
   "cmp-<dir>", "name": "<Dir>", "glob": "<dir>/**"}`. Plus
   `{"id": "cmp-misc", "name": "Other", "glob": "__never_matches__"}`.
   Top-level: `{"version": 1, "components": [...sorted by id...],
   "default_component": "cmp-misc", "nano_cap": 8}`.
8. Write atomically (temp + `os.replace`, mirroring P1's `save_index` —
   carry-forward #4 applies to writers in general).

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `group_components` + `seed_config`.

**Test criteria:**
- [ ] Every indexed `mkt_engine` file lands in exactly one component
  (assert `sum(len(files) for files in group.values()) == total file
  count`).
- [ ] Files matching no glob land in `cmp-misc`
  (`config["default_component"]`).
- [ ] A config with two globs matching one path: file lands in the first
  component AND a stderr warning fires, sorted by path (capability
  C-GROUPING).
- [ ] `seed_config` on a fresh `tmp_path` writes a config with one entry
  per top-level dir + `cmp-misc` + `nano_cap: 8`; the JSON has sorted keys.

**Status**: [ ] pending

---

### Step 6 — Micro selection (file vs dominant class)

**Goal:** Decide, for each file, whether the micro is the whole file or
the single dominant class inside it. Implements spec component 6.

**Design:**
A `select_micros(con, root, component_grouping) -> list[dict]` function.
For each file path in each component: query `nodes` for `kind='class' AND
file_path=<path>`. If exactly ONE class node exists, the micro is that class
(micro id `micro:<relpath>#<qualified_name>`, signature from `di.slice_hash`
over the class span via `di.symbol_spans`). Otherwise (zero or 2+ classes),
the micro is the file (micro id `micro:<relpath>`, signature from
`di.file_content_hash`). The dominant-class case carries `dominant_class:
<qualified_name>` on the micro node; the file-dominant case carries
`dominant_class: null`.

**Actions:**
1. Add `def select_micros(con, root, grouping) -> list[dict]:`.
2. For each `(component_id, paths)` in the grouping:
3.   For each `relpath` in `paths`:
4.     Query `class_rows = con.execute("SELECT qualified_name, start_line,
       end_line FROM nodes WHERE kind='class' AND file_path=? ORDER BY
       qualified_name", (relpath,)).fetchall()`.
5.     If `len(class_rows) == 1`: micro is class-dominant. `qname, start,
       end = class_rows[0]`. `sig = di.slice_hash(root, relpath, start,
       end)`. `dominant_class = qname`. `micro_id = f"micro:{relpath}#{qname}"`.
6.     Else: micro is file-dominant. `sig = di.file_content_hash(con,
       relpath)`. `dominant_class = None`. `micro_id = f"micro:{relpath}"`.
7.     Append `{"id": micro_id, "kind": "micro", "name":
       relpath.rsplit("/", 1)[-1], "path": relpath, "signature": sig,
       "component_id": component_id, "dominant_class": dominant_class,
       "caller_count": 0, "decisions": [], "children": [], "edges": []}`
       (caller_count + edges filled later by Step 8).
8. Return the list (sorted by `path` for determinism — Step 12 enforces,
   but sorting here too is cheap).

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `select_micros`.

**Test criteria:**
- [ ] Every `mkt_engine` file produces exactly one micro.
- [ ] A file with no classes produces a file-micro with `dominant_class:
  null` and id `micro:<relpath>`.
- [ ] A file with exactly one class produces a class-micro with
  `dominant_class: <qname>` and id `micro:<relpath>#<qname>`. (Per A20 +
  verify: mkt_engine has 10 class nodes across 10 files; no file has 2+
  classes, so the 2+-class branch is exercised only by a synthetic fixture.)
- [ ] The micro `id` is path-derived, never `nodes.id` (capability
  C-MICRO).

**Status**: [ ] pending

---

### Step 7 — Nano selection + cap + collapse (the rank + tiebreak)

**Goal:** For each micro, pick the top N (default 8) nano functions/methods
by caller count, and collapse the rest into one honest `+K more` node.
Implements spec component 7. Carries the A1-nuance code comment
(carry-forward #1).

**Design:**
A `select_nanos(con, root, micros, nano_cap) -> list[dict]` function. For
each micro, query `nodes` for `kind IN ('function', 'method') AND file_path
= <micro path>`. For each nano, compute:
- `caller_count` = count of incoming `calls` + `instantiates` edges to that
  node's `nodes.id` (NOT `references` — A15; NOT `imports`).
- `signature` = `di.slice_hash(root, relpath, start, end)` via
  `di.symbol_spans(con, qualified_name, relpath)`.
- `qualified_name`, `start_line`, `end_line` from `nodes`.
- `docstring` from `nodes.docstring` (may be null — A23).
- `is_exported` from `nodes.is_exported`.

Sort nanos by: primary `caller_count` DESC, secondary `qualified_name` ASC,
tertiary `path` ASC (A17). Take the first N as visible; the rest (sorted the
same way) collapse into one `kind=collapsed` node with id
`nano:+collapsed@micro:<micro_id>`, `name="+K more"`, `collapsed_count=K`,
`signature` = `_sha256` (or `hashlib.sha256`) over the sorted concatenation
of the K members' `signature` fields (determinism — sorted, not insertion
order).

**A1-nuance code comment** (carry-forward #1): the id-synthesis line carries
this comment block:
```
# NEVER pass nodes.id through as the model id. nodes.id mixes two forms
# (function:<32-hex> content-hash for 226/232 function nodes;
# hook:<path>:<name>:<line> path-derived for 6 React-hook nodes).
# Dispatching on the source id's prefix would couple P3 to codegraph's
# id-emission quirks. The model id is path-derived
# (nano:<qualified_name>@<relpath>) so it survives content edits — P4
# narrative pinning depends on it (Block 4b).
```

**Actions:**
1. Add `def select_nanos(con, root, micros, nano_cap) -> list[dict]:`.
2. Build the id-synthesis with the A1-nuance comment immediately above the
   line `nano_id = f"nano:{qname}@{relpath}"` (or wherever the nano id is
   synthesized).
3. For each `micro` in `micros`:
4.   `rows = con.execute("SELECT id, qualified_name, start_line, end_line,
       docstring, is_exported FROM nodes WHERE kind IN ('function',
       'method') AND file_path=? ORDER BY qualified_name",
       (micro["path"],)).fetchall()`.
5.   For each row: compute `caller_count` via
       `con.execute("SELECT COUNT(*) FROM edges WHERE target=? AND kind IN
       ('calls', 'instantiates')", (nodes_id,)).fetchone()[0]`.
6.   Build the nano dict: `{"id": nano_id, "kind": "nano", "name": <name
       from qualified_name short form>, "path": micro["path"], "signature":
       <slice_hash>, "micro_id": micro["id"], "caller_count":
       caller_count, "qualified_name": qname, "start_line": start,
       "end_line": end, "docstring": doc, "is_exported": <bool>,
       "edges": []}`.
7.   Sort nanos by `(-caller_count, qualified_name, path)` (Python tuple
       sort = caller_count DESC, qname ASC, path ASC — A17). Use `sorted()`
       with a key tuple — NOT `set()` (determinism).
8.   If `len(nanos_sorted) > nano_cap`: visible = first `nano_cap`;
       collapsed_members = rest. Compute collapsed sig = `_sha256` or
       `hashlib.sha256("".join(sorted(m["signature"] for m in
       collapsed_members)).encode()).hexdigest()`. Append a collapsed dict:
       `{"id": f"nano:+collapsed@micro:{micro['id']}", "kind": "collapsed",
       "name": f"+{len(collapsed_members)} more", "path": micro["path"],
       "signature": collapsed_sig, "micro_id": micro["id"],
       "collapsed_count": len(collapsed_members)}`.
9.   Else: visible = all nanos_sorted; no collapsed.
10. Set `micro["children"] = [n["id"] for n in visible]` (+ the collapsed id
    if any).
11. Return the assembled list (visible nanos + collapsed nodes).

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `select_nanos` (+ carry-forward #1
  comment).

**Test criteria:**
- [ ] A synthetic micro with 12 functions and `nano_cap=8` produces 8
  visible nanos + 1 collapsed node (`collapsed_count=4`).
- [ ] The selected 8 + collapsed 4 are exactly the deterministic sort
  (`caller_count` DESC, `qualified_name` ASC, `path` ASC) picks — including
  the zero-caller tie (synthetic fixture with 5 zero-caller nanos named
  alpha..epsilon; assert visible picks alpha, beta, ... deterministically).
- [ ] A micro with 5 functions and `nano_cap=8` produces 5 nanos + 0
  collapsed.
- [ ] The collapsed node's `signature` is sha256 over the 4 members' sorted
  signatures (recompute and assert equality) (capability C-NANO-CAP).
- [ ] The A1-nuance code comment is present in the source (grep
  "NEVER pass nodes.id through" finds it) (capability C-ID-COMMENT).

**Status**: [ ] pending

---

### Step 8 — Edge roll-up (calls + instantiates, imports two-shape, references)

**Goal:** Turn the codegraph `edges` table into per-node rolled-up edge
lists with counts and a stable 3-row `sample_callers[{file, line}]` (no
`symbol` field). Implements spec component 8. Carries the line-pin
(carry-forward #3).

**Design:**
A `roll_up_edges(con, micros, nanos, components) -> dict[node_id,
list[edge]]` function. It reads the raw `edges` table once into memory as
`("SELECT source, target, kind, line FROM edges WHERE kind IN ('calls',
'imports', 'references', 'instantiates', 'implements')")` (drops `contains`
— it's the tree-parent relationship). Then joins both ends to `nodes` on
`nodes.id` (A11) to recover each end's `kind`, `file_path`, and
`qualified_name`. Then dispatches by `edges.kind`:

- **`calls` + `instantiates`** (fold): both roll up as `kind: "calls"`.
  Source is `function`/`method`/`file:` node; target is
  `function`/`method`/`class`.
- **`implements`** (drop): emit nothing (A16).
- **`references`** (keep as edges, exclude from rank): emit as
  `kind: "references"`.
- **`imports`** (two sub-shapes — A14):
  - (a) target `kind == 'import'`: DROP as self-loop (all 440 are same-file;
    never cross-component).
  - (b) target is a real symbol: roll as `file → target-symbol's-owning-micro`.
- **`contains`**: NOT an edge — already expressed by `children[]` /
  back-pointers.

For each rolled-up edge, build `sample_callers`: collect all source
call-sites `(source.file_path, edge.line)` for that source/target pair; emit
the 3 lexicographically smallest by `(file, line)` ascending.

**Line pin (carry-forward #3):** `edges.line` is 100% populated for
calls/imports/references/instantiates/implements (verified), 0% for
`contains` (unused). So always read `line` directly; no skip/null/0 fallback.

**Actions:**
1. Add `def roll_up_edges(con, micros, nanos, components) -> dict[str,
   list[dict]]:`.
2. Build `nodes_lookup = {row[0]: (row[1], row[2], row[3]) for row in
   con.execute("SELECT id, kind, file_path, qualified_name FROM
   nodes")}` — keyed by `nodes.id`; value is `(kind, file_path,
   qualified_name)`.
3. Build `micro_by_path = {micro["path"]: micro["id"] for micro in
   micros}` and `component_by_micro = {micro["id"]: micro["component_id"]
   for micro in micros}`.
4. Read edges once: `edges = con.execute("SELECT source, target, kind,
   line FROM edges WHERE kind IN ('calls', 'imports', 'references',
   'instantiates', 'implements') ORDER BY source, target, kind").fetchall()`.
5. Group edges by `(source, target, model_kind)` where `model_kind` =
   `"calls"` if raw kind in {`calls`, `instantiates`} else `kind` (drops
   `implements` early — skip emitting any bucket for them).
6. For each source/target/model_kind group: resolve source_micro via
   `micro_by_path[nodes_lookup[source][1]]`, target_micro via the imports
   two-shape rule below.
7. **Imports two-shape (A14):** if `model_kind == "imports"`:
   - If `nodes_lookup[target][0] == "import"`: skip this edge entirely
     (sub-shape a — self-loop drop). Add a counter for visibility if needed;
     the test asserts zero self-micro `imports` edges.
   - Else: target_micro = `micro_by_path[nodes_lookup[target][1]]` (the
     target symbol's file's micro — sub-shape b).
8. For non-imports: target_micro = `micro_by_path[nodes_lookup[target][1]]`.
9. Build `sample_callers`: collect `(source_file_path, edge.line)` for each
   raw edge in the group (source_file_path from
   `nodes_lookup[source][1]`); sort by `(file, line)` ascending; take the
   first 3. **NO `symbol` field** in the entries — only `{"file": ..., "line":
   ...}`.
10. Edge dict: `{"source": source_micro_or_component, "target":
    target_micro_or_component, "kind": model_kind, "count": len(group),
    "sample_callers": [...]}`. (Source/target at nano-level = source_micro;
    at component-level = source_component — build both maps: a nano-level
    dict keyed by nano micro node ids, a component-level dict keyed by
    component ids. Within-component edges only at micro/nano level;
    component-level edges only cross-component — roadmap.md line 96.)
11. Sort each node's `edges[]` by `(source, target, kind)` ascending.
12. Mutate `micro["edges"]` and `nano["edges"]` from the rolled-up dict.

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `roll_up_edges`.

**Test criteria:**
- [ ] Every nano micro node in `mkt_engine` whose function has incoming
  `calls` carries a non-empty `edges[]`.
- [ ] `references` test (synthetic fixture): a nano with 5 incoming
  `references` and 0 incoming `calls`/`instantiates` has `caller_count = 0`
  AND the `references` still appear in `edges[]` (capability
  C-EDGES-REFERENCES).
- [ ] `instantiates`/`implements` test (synthetic fixture): 2
  `instantiates` + 1 `implements` into a class. Assert the 2
  `instantiates` appear as `kind: "calls"`; assert the 1 `implements` does
  NOT appear anywhere (capability C-EDGES-CALLS).
- [ ] `imports` two-shape test (synthetic fixture): 2 `file→import:`
  same-file + 3 `file→symbol` intra-repo. Assert ZERO self-micro `imports`
  edges; assert the 3 intra-repo imports roll up to `file→target-micro`
  (target micro = target symbol's file's micro, NOT target-as-nano)
  (capability C-EDGES-IMPORTS).
- [ ] `sample_callers` shape (synthetic fixture): 5 call-sites into one
  target where 3 have a `file:` source and 2 have a `function:` source.
  Assert the 3 emitted are the lexicographically smallest `(file, line)`,
  in that order, stable across two runs. Assert file-sourced edges
  populate `file`/`line` from the source `file:` node's `file_path` +
  `edges.line`. Assert NO `symbol` key in any entry (capability
  C-SAMPLE-CALLERS-SHAPE).
- [ ] `edges.line` is read directly; no null-fallback branch for the kinds
  P3 reads (capability C-EDGES-LINE-PIN, carry-forward #3).

**Status**: [ ] pending

---

### Step 9 — Decision-node merge (verified anchors + worst-case badge)

**Goal:** Attach `decision:<ADR-ID>@<component-id>` nodes to every component
owning ≥1 verified anchor, with a live FRESH/STALE/ORPHANED/superseded
badge that is consistent across all attachments. Implements spec component
9.

**Design:**
A `merge_decisions(con, root, index, component_grouping, micros) ->
list[dict]` function. For each decision in the index:
1. Filter to anchors with `verified: true`. If zero verified anchors, skip
   (no decision node — contract C5).
2. For each verified anchor, call `di.parse_ref(a["ref"])` to extract the
   path. A `file:<path>` anchor → the file's component. A
   `<qname>@<path>` anchor → the symbol's file's component.
3. For each anchor, call `di.anchor_status(con, root, a)` to get the live
   status (`FRESH`/`STALE`/`ORPHANED`/`AMBIGUOUS` — A5, verified at
   `decision_index.py:154-158`). The decision's badge is the WORST status
   across its verified anchors (`ORPHANED > STALE > AMBIGUOUS > FRESH`).
4. Attach `decision:<ADR-ID>@<component-id>` to every component owning ≥1
   verified anchor's micro. Same status across all attachments.
5. Read `supersedes` from the index; a decision whose `supersedes` chain
   points at it renders `status: "superseded"`.
6. The decision node's `signature` = `_sha256` (or `hashlib.sha256`) over
   the sorted concatenation of the decision's verified anchor `sig`
   values.
7. The decision node's `anchor_count` = number of verified anchors.

**Actions:**
1. Add `def merge_decisions(con, root, index, grouping, micros) ->
   list[dict]:`.
2. Build `micro_by_path = {micro["path"]: micro["id"] for micro in
   micros}` and `micro_to_component = {micro["id"]: micro["component_id"]
   for micro in micros}`.
3. For each `(adr_id, dec)` in `index["decisions"].items()` (sorted by
   `adr_id` for determinism):
4.   `verified = [a for a in dec.get("anchors", []) if a.get("verified")
     is True]`. If empty: skip (no decision node).
5.   For each `a` in `verified`: `parsed = di.parse_ref(a["ref"])`. If
     `parsed[0] == "file"`: `path = parsed[1]`. Else `path = parsed[2]`.
     Look up `micro_id = micro_by_path.get(path)`; if missing, skip this
     anchor (the path is not in the index — should not happen given A22,
     but defensive). Look up `component_id =
     micro_to_component[micro_id]`. Collect
     `(component_id, a)` tuples.
6.   Compute badge: `statuses = [di.anchor_status(con, root, a) for (_,
     a) in tuples]`. Map to a worst-case ranking: define
     `WORST = {"ORPHANED": 3, "STALE": 2, "AMBIGUOUS": 1, "FRESH": 0}`;
     `badge = max(statuses, key=lambda s: WORST[s])`.
7.   If `dec.get("supersedes")` is non-empty and points at a known ADR:
     `badge = "superseded"` (overrides worst-case per spec step 5).
8.   For each unique `component_id` among the tuples: append a decision
     node:
       `{"id": f"decision:{adr_id}@{component_id}", "kind": "decision",
       "name": adr_id, "path": <the ADR file path if recorded in the
       index, else None>, "signature": <sha256 over sorted anchor sigs>,
       "adr_id": adr_id, "component_id": component_id, "status": badge,
       "supersedes": dec.get("supersedes"), "anchor_count": len(verified)}`.
9.   Mutate the corresponding component node's `decisions[]` to append
     `decision:{adr_id}@{component_id}`.
10.  Mutate each relevant micro node's `decisions[]` to append the same id
     (anchor-target inside the micro).
11. Return the decision-node list (sorted by `id` for determinism in Step
    12).

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `merge_decisions`.

**Test criteria:**
- [ ] The 8 `mkt_engine` ADRs (all verified, all FRESH per A9) produce 8
  decision nodes, each attached to ≥1 component, each `status: FRESH`
  (capability C-DECISION-MERGE, golden test slice).
- [ ] A synthetic fixture with one anchor flipped to `verified: false`
  produces NO decision node for that ADR.
- [ ] A synthetic fixture with an anchor whose symbol is deleted
  (ORPHANED status) produces a decision node with the ORPHANED
  (worst-case) badge.

**Status**: [ ] pending

---

### Step 10 — Pre-extract guard (warn-and-continue on not-verified / not-FRESH)

**Goal:** Before emitting, warn on stderr if the index has any
`verified:false` anchor or any not-FRESH anchor; always exit 0 and always
still emit (contract C5). Implements spec component 10.

**Design:**
A `pre_extract_guard(con, root, index) -> list[str]` function. It calls
`di._evaluate(con, root, index["decisions"])` (verified at
`decision_index.py:290-299` — returns `(rows, n_not_fresh)` where each row
is `(did, ref, state)`; reaching the leading underscore is acceptable
because P3 imports P1 as a sibling, the same move `decision_hook.py:64`
makes — ADR 0001-endorsed). It also scans for any anchor with `verified:
false`. If either condition is true, it warns on stderr listing each
offending `<ADR-ID>` + `ref` + reason, pointing at `decision_index refresh
<id>`. The caller (`extract`) ignores the return for control flow — the
guard never aborts. The warning text is sorted by `(ADR-ID, ref)` for
determinism (R3 posture).

**Actions:**
1. Add `def pre_extract_guard(con, root, index) -> list[str]:`.
2. `rows, n_not_fresh = di._evaluate(con, root, index["decisions"])`.
3. Collect `not_fresh = [(did, ref, state) for (did, ref, state) in rows
   if state != "FRESH"]` (state from A5 vocabulary).
4. Collect `not_verified = [(adr_id, a["ref"]) for adr_id, dec in
   index["decisions"].items() for a in dec.get("anchors", []) if
   a.get("verified") is not True]`.
5. If either list is non-empty: build warning strings (one per offending
   row) like `f"{adr_id} {ref} → {reason} (run: decision_index refresh
   {adr_id})"`; sort by `(adr_id, ref)`; print each to stderr; return the
   list.
6. If both empty: return `[]` (no stderr output, no warning).
7. Wire into `cmd_extract` between the schema guard (Step 4 — hard fail
   first) and the assembly (Step 11) — i.e. `pre_extract_guard` runs AFTER
   `_verify_model_schema` so a hard-fail drift skips the soft warn; but
   BEFORE the merge so the merge sees the warning surface.

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `pre_extract_guard`; wire call into
  `cmd_extract`.

**Test criteria:**
- [ ] Against the live `mkt_engine` index (all verified, all FRESH per A9),
  the guard emits nothing and `extract` proceeds (exit 0).
- [ ] Against a synthetic fixture with one `verified: false` anchor, the
  guard emits a stderr warning pointing at `decision_index refresh <adr_id>`
  and `extract` still exits 0 and still writes the model (with no
  decision node for the unverified anchor — verified by the Step 9 merge
  test) (capability C-PRE-EXTRACT-GUARD).
- [ ] The guard returns control to `extract` (does not abort); `extract`
  proceeds to assembly + serialization.

**Status**: [ ] pending

---

### Step 11 — Component + model id synthesis + child pointers

**Goal:** Build the final component/micro/nano node objects with their
model-derived ids, forward `children[]` pointers, and back-pointers, so the
renderer can traverse either direction. Implements spec component 11.

**Design:**
An `assemble_nodes(components_grouping, micros, nanos, decisions,
config) -> dict` function. It synthesizes ids per the design's id forms
(never `nodes.id` — A1, A11, with the Step 7 comment applying here too):
- component: use the config's `id` directly (already `cmp-<slug>` by
  convention).
- micro (file-dominant): `micro:<relpath>`.
- micro (class-dominant): `micro:<relpath>#<qualified_name>`.
- nano: `nano:<qualified_name>@<relpath>`.
- collapsed: `nano:+collapsed@micro:<micro_id>`.
- decision: `decision:<ADR-ID>@<component-id>` (contract C4).

Populate `children[]` on each component (forward-pointers to its micros'
ids) and on each micro (forward-pointers to its nanos' ids + its collapsed
node id if any). Populate `component_id` on each micro (already done in
Step 6) and `micro_id` on each nano (already done in Step 7). Populate
`file_count` + `symbol_count` on each component, `collapsed_count` on
collapsed nodes, `anchor_count` on decision nodes. Populate `edges[]` from
Step 8, `decisions[]` from Step 9 (already mutated in Step 9).

**Actions:**
1. Add `def assemble_nodes(grouping, micros, nanos, decisions, config) ->
   dict:`.
2. Build the component node list: for each `(component_id, paths)` in
   grouping: `{"id": component_id, "kind": "component", "name":
   <from config components[id]["name"]>, "path": <common prefix of paths,
   per Step 5's open decision>, "signature": <sha256 over sorted member
   files' content_hashes>, "file_count": len(paths), "symbol_count": <sum
   of nanos per micro>, "decisions": [], "children": [<micro ids>],
   "edges": []}`.
3. Components' `signature` = `_sha256` over the sorted concatenation of the
   member micros' `signature` values (Block 1e: "component = sha256 over
   member hashes"). Sort the member sigs (determinism).
4. Micros' `children[]` already set in Step 7; verify here. Component
   nodes' `children[]` set here = sorted list of micro ids under that
   component.
5. `decisions[]` already mutated on components + micros in Step 9; verify
   here.
6. `edges[]` already set in Step 8; verify here.
7. Return the assembled envelope:
   `{"components": [...], "micros": [...], "nanos": [...], "decisions":
   [...]}` (flat lists per the design's example — capability C-ID-SYNTHESIS
   favors flat lists with pointers, not a nested tree).
8. Do NOT call any DB here — pure in-memory assembly.

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `assemble_nodes`.

**Test criteria:**
- [ ] Every component node's `children[]` lists its micros' ids (sorted
  ascending).
- [ ] Every micro node's `children[]` lists its nanos' ids (+ collapsed id
  if any).
- [ ] Every micro node's `component_id` points back to its component;
  every nano node's `micro_id` points back to its micro.
- [ ] No node's `id` equals any `nodes.id` value in the DB (assert via a
  test: read `SELECT id FROM nodes` from the DB, assert no model id is in
  that set) (capability C-ID-SYNTHESIS).

**Status**: [ ] pending

---

### Step 12 — JSON serialization (byte-deterministic writer)

**Goal:** Write the assembled model to `diagram-model.json` with
byte-identical output across runs given identical inputs — the exit
criterion from `roadmap.md` line 113. Strictest serialization in the repo:
stricter than P1's `save_index` (A6 — `sort_keys=True`).
Carries the atomicity inheritance (carry-forward #4: P1's `save_index` at
`decision_index.py:175-179` already does temp + `os.replace`).

**Design:**
A `serialize_model(model_doc, out_path) -> None` function. The model doc
is the assembled node dict (Step 11) wrapped in a top-level envelope:
`{version: 1, generated_at: null, root: <repo-relative root>, nano_cap: N,
components: [...], micros: [...], nanos: [...], decisions: [...]}`.
The writer:
- `json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`
  — `sort_keys=True` is the key difference from P1's `save_index` (which
  does NOT sort — A6). P3 must sort because it emits from dict iteration
  whereas P1's index is human-curated to a stable order.
- All lists sorted by a deterministic key BEFORE serialization:
  components by `id`; micros by `path`; nanos by `qualified_name` then
  `path`; edges by `(source, target, kind)`; `sample_callers` by
  `(file, line)`; collapsed members by `qualified_name` then `path`;
  decisions by `id`; each component's + micro's `decisions[]` by decision
  id; each `children[]` by id.
- `generated_at` always null (a real timestamp breaks byte-determinism;
  consumers that want "when built" read the file mtime).
- `root` is the repo-relative root from `di.repo_root_for(db)`.
- No `set()` iteration order leaks — every collection is sorted explicitly
  before emission.
- **Atomicity (carry-forward #4):** write to a temp file
  (`out_path.with_suffix(out_path.suffix + ".tmp")`) then `os.replace(tmp,
  out_path)`. Inherited from P1's `save_index` verbatim — the design's
  "atomicity is an open question" is closed: P1 already does it; inherit.

The `--update-golden` flag (Step 2) routes here: instead of asserting
against the committed golden, the writer writes its output directly to
`ssot-diagram/testdata/mkt_engine.model.json`.

**Actions:**
1. Add `def serialize_model(model_doc, out_path) -> None:`.
2. Wrap `model_doc` in the envelope: top-level = `{"version": 1,
   "generated_at": None, "root": <repo-root-relpath>, "nano_cap": <n>,
   "components": ..., "micros": ..., "nanos": ..., "decisions": ...}`.
3. Sort every list per the design's deterministic keys (above).
4. `tmp = out_path.with_suffix(out_path.suffix + ".tmp")`;
   `tmp.parent.mkdir(parents=True, exist_ok=True)`;
   `tmp.write_text(json.dumps(doc, indent=2, sort_keys=True,
   ensure_ascii=False) + "\n")`;
   `os.replace(tmp, out_path)`. (Inherit P1's `save_index` pattern —
   carry-forward #4.)
5. Wire into `cmd_extract` at the end:
   `if args.update_golden: serialize_model(doc, Path("ssot-diagram/testdata/mkt_engine.model.json"))`
   else `serialize_model(doc, args.out)`.

**Files to modify:**
- `ssot-diagram/graph_model.py` — add `serialize_model`; wire the
  `--update-golden` branch into `cmd_extract`.

**Test criteria:**
- [ ] Two consecutive `extract` runs on `mkt_engine` produce files with
  identical sha256 (capability C-DETERMINISM).
- [ ] 10× runs produce identical sha256 every time (assert no `set()`
  order leak).
- [ ] The produced JSON has `sort_keys=True` (verify by re-parsing and
  comparing `sorted(doc.keys())` to `doc.keys()`).
- [ ] `generated_at` is `null` in the output.
- [ ] Output is written atomically — assert a `.tmp` file does NOT exist
  after `serialize_model` returns (the `os.replace` succeeded).
- [ ] `--update-golden` writes to `ssot-diagram/testdata/mkt_engine.model.json`
  instead of `args.out`.

**Status**: [ ] pending

---

### Step 13 — Manifest entry + bootstrap-config writer wiring

**Goal:** Confirm the manifest entry is in place (added in Step 1) and wire
the `bootstrap-config` writer — `seed_config` from Step 5 — into the
`cmd_bootstrap_config` function. Implements spec component 13.

**Design:**
The manifest entry was added in Step 1; verify here that it's intact (do
NOT re-add or modify it). The `cmd_bootstrap_config` function (stub from
Step 1) is filled in: parse args; locate the DB via `di.find_db(Path(".")
resolve())` if `--db` not given; open it via `di.open_db`; call
`seed_config(con, out_path, force=args.force)` from Step 5; print a one-line
success message to stdout ("wrote <out_path>"); exit 0.

**Actions:**
1. Confirm `manifest.json` has the `diagram-model` entry from Step 1 (no
   edit needed here — defensive read + assert).
2. Fill in `def cmd_bootstrap_config(args):`:
3.   `db_path = Path(args.db) if args.db else di.find_db(Path.cwd())`.
4.   If `db_path is None`: `di.die("codegraph DB not found — run
     `codegraph init` first")` (exit 2 per E1).
5.   `con = di.open_db(db_path)` (which calls `di.verify_schema` — P1's
     guard; the extended `_verify_model_schema` from Step 4 is NOT needed
     here because `bootstrap-config` only reads `files.path`, not the extra
     columns `extract` reads. Optionally call `_verify_model_schema` for
     consistency — open decision, lean no for `bootstrap-config` to keep
     it lighter).
6.   `seed_config(con, Path(args.out), force=args.force)` (Step 5's
     function — its `--force` gate is internal to `seed_config` and exits
     2 via `di.die`).
7.   Print `f"wrote {args.out}"` to stdout; `sys.exit(0)`.

**Files to modify:**
- `ssot-diagram/graph_model.py` — fill in `cmd_bootstrap_config`. (The
  manifest entry is from Step 1; no edit here unless it's missing.)

**Test criteria:**
- [ ] `piggyback status` lists `diagram-model` with scope `repo` and
  `hooks: []` (capability C-MANIFEST, full).
- [ ] On a fresh `tmp_path` with a synthetic DB, `bootstrap-config` writes
  a config with one component per top-level dir + `cmp-misc` + `nano_cap:
  8`; the JSON has sorted keys.
- [ ] A second `bootstrap-config` WITHOUT `--force` exits 2 with the
  full P1 string "exists — refusing to overwrite a curated config.
  Pass --force to reseed." (capability C-BOOTSTRAP-CONFIG, A7, E1 exit 2).

**Status**: [ ] pending

---

### Step 14 — Tests (golden + determinism + 5 red-team regressions + fail-loud)

**Goal:** Verify the byte-determinism contract, the model's correctness
against the curated pilot, and the 5 red-team fixes (A13-A17) stay fixed.
Implements spec component 14.

**Design:**
Create `ssot-diagram/test_graph_model.py` and the golden model artifact at
`ssot-diagram/testdata/mkt_engine.model.json` (committed;
re-recorded only via `--update-golden`). Tests use pytest. The golden +
verified-decision tests run against the LIVE pilot DB
(`~/all-projects/mkt_engine/.codegraph/codegraph.db` read-only); they are
marked `@pytest.mark.skipif(not db_exists)` so CI without the pilot DB
still passes the rest (A24 — the skip-if-absent posture). The determinism
+ 5 red-team regression + fail-loud + config-validation tests use
in-memory synthetic fixtures (`sqlite3` `tmp_path` with a schema-matching
DB constructed per test — keeps them hermetic and avoids fixture-DB drift).

**Actions:**
1. Create `ssot-diagram/test_graph_model.py`.
2. Add a `conftest.py`-level helper (or a fixture in `test_graph_model.py`)
   that builds a synthetic in-memory DB matching the codegraph schema
   (`nodes`, `files`, `edges` with the columns the schema guard checks),
   for the hermetic tests.
3. **Golden model test** (live DB): run `extract` via `cmd_extract` against
   the live DB + index + a curated `ssot-diagram/ssot-diagram.config.json`
   (the human-curated pilot config); assert the produced JSON matches
   `ssot-diagram/testdata/mkt_engine.model.json` byte-for-byte (sha256
   comparison). Mark `skipif` on the DB path.
4. **Determinism test**: run `extract` twice (in-memory synthetic or live
   DB); assert identical sha256.
5. **Verified-anchored decision appears once test** (live DB): assert 8
   decision nodes appear, each attached to ≥1 component, each `FRESH`.
6. **Unverified anchor → no decision node** (synthetic): flip one anchor's
   `verified` to false; assert no `decision:<that-ADR>@*` node emitted.
7. **Nano cap + collapse** (synthetic): 12 functions in one micro, cap 8;
   assert 8 nanos + 1 collapsed (`collapsed_count=4`) with the
   deterministic sort picking the right 8 + 4; include the zero-caller
   tie case.
8. **Sample_callers shape (FATAL1/A13)** (synthetic): 5 call-sites into a
   target (3 with `file:` source, 2 with `function:` source); assert the 3
   emitted are the lexicographically smallest `(file, line)` ascending,
   stable across two runs; assert NO `symbol` key.
9. **imports two-shape (FATAL2/A14)** (synthetic): 2 `file→import:`
   same-file + 3 `file→symbol` intra-repo; assert ZERO self-micro
   `imports` edges; assert the 3 intra-repo imports roll up to
   `file→target-micro`.
10. **`caller_count` excludes `references` (A15)** (synthetic): a nano
    with 5 incoming `references` (target type-mentions) and 0 incoming
    `calls`/`instantiates`; assert `caller_count = 0` AND `references`
    appear in `edges[]`.
11. **`instantiates` folds, `implements` drops (A16)** (synthetic): 2
    `instantiates` + 1 `implements` into a class; assert the 2
    `instantiates` appear as `kind: "calls"`; assert the 1 `implements`
    does not appear anywhere.
12. **First-match wins + multi-match warning** (synthetic config): two
    globs match one path; assert the file lands in the first component
    AND a stderr warning fires (capfd).
13. **No-config fail-loud**: run `extract` with no
    `ssot-diagram.config.json`; assert exit 2 (E1) + stderr contains "run
    `bootstrap-config` first".
14. **bootstrap-config --force**: assert a second `bootstrap-config`
    without `--force` exits 2 ("refusing to overwrite"); with `--force`
    it reseeds.
15. Generate the initial golden artifact via
    `python3 ssot-diagram/graph_model.py extract --update-golden` against
    the live pilot DB + the curated config; commit it as
    `ssot-diagram/testdata/mkt_engine.model.json`.

**Files to modify:**
- `ssot-diagram/test_graph_model.py` — create with all the tests above.
- `ssot-diagram/testdata/mkt_engine.model.json` — create (committed
  golden; re-recorded only via `--update-golden`).
- (Possibly `ssot-diagram/conftest.py` — create if shared fixtures warrant
  it; otherwise keep fixtures inside `test_graph_model.py`.)

**Test criteria:**
- [ ] `python3 -m pytest ssot-diagram/test_graph_model.py` passes all
  listed tests (capability C-TESTS-HERMETIC).
- [ ] The determinism test asserts two consecutive runs produce identical
  sha256 (capability C-DETERMINISM).
- [ ] The golden test matches the committed artifact byte-for-byte (or is
  re-recorded via `--update-golden` after a deliberate change) (capability
  C-GOLDEN).
- [ ] Each of the 5 red-team regression tests FAILS if its corresponding
  fix is reverted (A13-A17).

**Status**: [ ] pending

---

## E2E Done Criteria

Unit tests passing is necessary but NOT sufficient. Before "done", the
implementer runs the extractor like a real end-user / QC tester on the LIVE
stack and OBSERVES the signals below. The live stack = the pilot mkt_engine
repo DB at `~/all-projects/mkt_engine/.codegraph/codegraph.db` (read-only,
`mode=ro&immutable=1`) + the curated index at
`~/all-projects/mkt_engine/docs/decision-index.json` (8 ADRs / 33 anchors /
all verified / all FRESH per A9). The extractor emits JSON, so the
walkthrough inspects `diagram-model.json` directly.

**Prerequisites:** Python 3, the pilot repo checked out, the codegraph DB
present (`codegraph/codegraph.db`), the curated decision index present, a
human-curated `ssot-diagram/ssot-diagram.config.json` (run
`bootstrap-config` once if absent). No network, no LLM, no hook.

**Walkthrough** (each line: action → observe → expected; mapped to
Capabilities IDs):

1. `python3 ssot-diagram/graph_model.py bootstrap-config` (in the
   `mkt_engine` checkout) → observe: a `ssot-diagram.config.json` file is
   written; stdout prints `wrote ssot-diagram.config.json`; exit 0 →
   expected: one component per top-level dir (8 dirs: app, components, lib,
   prisma, scripts, tests, docs, .claude) + a `cmp-misc` row +
   `nano_cap: 8`. (Capability C-BOOTSTRAP-CONFIG, C-MANIFEST.)
2. Re-run `python3 ssot-diagram/graph_model.py bootstrap-config` without
   `--force` → observe: stderr "exists — refusing to overwrite a curated
   config. Pass --force to reseed."; exit 2 → expected: the full P1 string
   verbatim, exit 2 (E1). Run `--force` and observe a reseed. (Capability
   C-BOOTSTRAP-CONFIG.)
3. (Human curates the seeded config: rename, merge, split components so
   `lib/ai` becomes `cmp-ai`, etc. This curation step is OUTSIDE the
   extractor — it consumes a curated config.)
4. `python3 ssot-diagram/graph_model.py extract` → observe: a
   `ssot-diagram/diagram-model.json` file is written; stderr is empty (no
   pre-extract guard warnings — the pilot index is all-verified, all-FRESH
   per A9); exit 0 → expected: byte-identical to a re-run. (Capabilities
   C-DETERMINISM, C-PRE-EXTRACT-GUARD.)
5. Re-run `python3 ssot-diagram/graph_model.py extract` → observe:
   `diagram-model.json` sha256 unchanged → expected: byte-identical
   (C-DETERMINISM). Repeat 10× to lock out `set()` iteration order leaks.
6. Inspect `diagram-model.json` → observe: 8 `decision` nodes, each
   `status: FRESH`, each attached to ≥1 component, each `decisions:[]` id
   of the form `decision:ADR-NNNN@cmp-<slug>`; no `decision:` node for any
   non-verified ADR (the pilot has none — all 8 are verified). → expected:
   every verified anchor appears once across the 8 decision nodes (33
   anchors distributed across 8 decisions). (Capability C-DECISION-MERGE,
   C-GOLDEN.)
7. `python3 -c "import json; d=json.load(open('ssot-diagram/diagram-model.json'));
   assert d['generated_at'] is None"` → observe: passes → expected:
   `generated_at` is null (byte-determinism). (Capability C-DETERMINISM.)
8. Inspect any nano node with `caller_count == 0` → observe: it is still in
   the model (not dropped); its `qualified_name` and `path` are present;
   its `id` is `nano:<qname>@<relpath>` (path-derived) → expected: zero-
   caller nanos survived the cap on the secondary sort tiebreak (A17); the
   id is NOT `nodes.id` (no `function:<32-hex>` shape). (Capability
   C-ID-SYNTHESIS, C-NANO-CAP.)
9. Inspect any component with > 8 nanos in one micro → observe: a
   `collapsed` node present in `nanos[]` with `kind: "collapsed"`,
   `name: "+K more"`, `collapsed_count: K`, `signature` recompute-matches
   `hashlib.sha256(...)` over its K sorted members' signatures → expected:
   the "+K more" node is honest about dropped symbols (C-NANO-CAP).
10. Inspect any `edges[]` entry → observe: each entry is
    `{source, target, kind, count, sample_callers: [{file, line}, {file,
    line}, {file, line}]}` — exactly 3 sample_callers (or fewer if the
    raw-edge group had <3), each with NO `symbol` key → expected: FATAL1
    fix (A13) is live. (Capability C-SAMPLE-CALLERS-SHAPE.)
11. Inspect `kind` values across `edges[]` → observe: only `"calls"`,
    `"imports"`, `"references"` (no `instantiates`, no `implements`, no
    `contains`) → expected: FATAL2 fold/drop (A14/A16) is live, imports
    two-shape (A14) drops placeholder self-loops. (Capabilities
    C-EDGES-CALLS, C-EDGES-IMPORTS, C-EDGES-REFERENCES.)
12. Inspect any `<qname>@<relpath>` anchor's owning micro → observe: the
    micro's `decisions:[]` includes the decision id; the component's
    `decisions:[]` includes the same id → expected: multi-anchor decision
    attaches to every component owning ≥1 verified anchor (C4); consistent
    status across attachments. (Capability C-DECISION-MERGE.)
13. `piggyback status` → observe: `diagram-model` listed with scope
    `repo`, `hooks: []` → expected: manifest entry wired (C-MANIFEST).
14. `python3 ssot-diagram/graph_model.py extract --update-golden` →
    observe: `ssot-diagram/testdata/mkt_engine.model.json` rewritten; its
    sha256 == the production `diagram-model.json` sha256 → expected: the
    golden is the byte-truth for the live pilot (C-GOLDEN).
15. `python3 -m pytest ssot-diagram/test_graph_model.py -v` → observe: all
    tests pass; the golden test is NOT skipped (DB present); the hermetic
    tests (determinism, 5 red-team regressions, fail-loud, config
    validation, bootstrap-config) all pass → expected: full test suite
    green. (Capability C-TESTS-HERMETIC.)
16. Revert one red-team fix locally (e.g. re-add `symbol` to
    `sample_callers` in `graph_model.py`) → observe: the FATAL1 regression
    test FAILS → expected: the test guards the fix. Repeat for A14, A15,
    A16, A17 (each guarded by its named test). Restore the fix.

**Done gate:** every line above observed + matching, evidence captured
(sha256 outputs, golden diff, pytest output, `piggyback status` output),
plus all step-level tests/lint passing. If a live observation diverges
from a passing unit test, the live observation wins — fix + re-run before
marking done.

## Open Questions

- **OQ-FOLDER-001** — `OPEN (human-authority: product-identity)`. The repo
  is on the legacy artifact-folder scheme (`0_scout/1_design/2_specs/
  3_factual-code-verification`); the DOC-ARTIFACT-001 Writ rule says
  migrate to the integer-only lifecycle scheme (`0_draft/1_scout/2_ux/
  3_design/4_specs/5_factual-code-verification/6_plans/...`). This plan
  itself is written to `4_plans/` per the dispatch — the legacy scheme
  for the `plans` slot. The orchestrator / owner decides whether/when to
  migrate; deferred to post-pipeline, do NOT migrate mid-pipeline.
- **OQ-A18** — `OPEN (human-authority: scope)`. A18 cross-OS path
  generalization: codegraph's path-emission for Windows (backslash) was
  unverifiable from the single mkt_engine DB (which has 0 backslash paths
  per verify). Non-blocking under C1 (pilot = mkt_engine). Resurface only
  if P3 is retargeted to a Windows-codegraph build.
- **OQ-A24** — `OPEN (human-authority: operating-burden)`. Whether the CI
  environment possesses the pilot DB (`~/all-projects/mkt_engine/
  .codegraph/codegraph.db`) is unverified. The skip-if-absent posture
  makes this non-blocking (CI without the DB still passes — golden test
  skipped, hermetic tests run). The owner decides whether CI needs the
  pilot DB checked out.
- **OQ-E1 (RESOLVED in this plan)** — `RESOLVED`. Whether P3 uses exit 2
  (P1's `die()` convention) or exit 1 (spec's literal wording). The plan
  moves P3 to exit 2 by reusing `di.die()` verbatim (no divergence).
  Listed here for traceability; do NOT re-decide.
- **OQ-COMPONENT-PATH** — open per spec component 5. How is the component
  node's `path` field derived when the glob is not `<dir>/**`? Spec leans
  common-prefix-of-matched-paths. The implementer resolves inside Step 5
  (a code-shape decision, not a contract decision).
- **OQ-EMPTY-MICRO** — open per spec component 8. For a `references` edge
  into an `interface` node that lives in a file with no nanos, how is the
  target resolved? Spec leans: the file's micro still exists (every file →
  one micro per A22). The implementer resolves inside Step 8.
- **OQ-UPDATE-GOLDEN-SHAPE** — open per spec component 2. `--update-golden`
  as a hidden flag on `extract` vs a separate subcommand. The plan picks
  hidden flag (matches P1's `--force`/`--strict` pattern); resolved here
  for P3.
- **OQ-SYNTHETIC-FIXTURE** — open per spec component 14. In-memory tmp DB
  per test vs a committed fixture DB. The plan picks in-memory
  (`sqlite3` tmp_path) — hermetic, no fixture drift. Resolved here for P3.

## Out of Scope

- **The read-hook form (PostToolUse re-extract on codegraph re-index)** —
  P6 owns hook wiring. P3 registers `hooks: []`; the manifest entry is
  CLI-only. [P6]
- **The interactive HTML renderer** — P5 reads `diagram-model.json` but P3
  does not render. [P5]
- **Narrative sidecar** (`narratives.json` / `graph_model.py narrate`) —
  P4 layers inference over P3's deterministic substrate. [P4]
- **The `_shared/` extraction (Block 1 clean cutover)** — explicitly
  deferred to Phase B per ADR 0001. P3 imports P1 as a sibling; P1 is a
  read-only dependency in this plan. [Phase B]
- **Auto-deriving component names from path prefixes** — refused in the
  grill; explicit glob → name is the safer subset for a non-SWE owner.
  [deferred]
- **Streaming edge roll-up for very large repos** — in-memory roll-up is
  fine for the pilot (2345 edges in the relevant kinds); revisit if a
  real repo proves `extract` takes > a few seconds. [OQ-PERF-1, deferred]
- **`$1` capture-group globs** — refused in the scout (fragile on
  multi-match). [deferred]
- **External-module `import:` node bucketing as a separate edge set** —
  P5 may want external-dep arrows later; P3 drops placeholder `import:`
  nodes as self-loops to keep the model clean. [P5]
- **Renderer-side tooltip wording** for the file-sourced `sample_callers`
  case — P3 carries the truth in `kind`; the tooltip is the renderer's.
  [P5]
- **`implements` as a fourth edge kind** — dropped (A16, contract 6
  freezes `{calls, imports, references}`). A deliberate Block 4c amendment
  is its path back, not a P3 concern. [OQ-Block4c-1, deferred]
- **Writing any ADR in this phase** — ADR 0001 already exists per A25.
  P3 deliverables list does NOT include writing a new ADR. [Done]
- **Editing `decision_index.py` or `decision_hook.py`** — read-only
  dependencies per ADR 0001. Any change to the shared recipe is the
  Phase B cutover's job. [Phase B]
- **STATE.md write** — per the dispatch, the ORCHESTRATOR owns STATE.md;
  this subagent does NOT run the Step 6 mid-session STATE.md write. [Orchestrator]
