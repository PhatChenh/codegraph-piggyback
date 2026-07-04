# P3 — Diagram Model Extractor (design)

_Function: `ssot-diagram/graph_model.py` turns the codegraph DB + the curated
decision index into one deterministic `diagram-model.json` — the only file the
renderer (P5) ever reads. Three levels: macro (components) → micro (files) →
nano (functions), rolled-up edges with counts, decision nodes from verified
anchors. Same inputs ⇒ byte-identical JSON. No LLM in any verdict._

> **Revision 2 (post-red-team, 2026-07-04).** Adversarial red-team landed 2
> FATAL + 2 SERIOUS + 1 NOTE against the §Chosen Approach field-shape schema.
> All five were re-verified against the live `mkt_engine` DB read-only (counts
> in each fix below) and incorporated. The chosen Option A (sibling import)
> SURVIVES — these are TYPE-B fixes: execution-detail, Block 4
> contract-compliant, no re-litigation of Option A/B/C or the 6 grill
> contracts. See §Red-team revision at the bottom for the full change log.

Built in this repo (codegraph-piggyback); pilot target is `mkt_engine` (a TS/JS
repo at `~/all-projects/mkt_engine`). Ships CLI-first; the read-hook form is
deferred to P6 (regeneration plumbing) and is **out of scope** for this design.

## Cast of characters

| Symbol | Role |
|---|---|
| `decision_index.py` | P1 engine — the source of every DB / signature / resolve recipe P3 reuses |
| `diagram-model.json` | The single output file P3 emits; P5 renderer + plan-visualizer consume it |
| `ssot-diagram.config.json` | Curated glob→component-name map (P3 owns the schema) |
| `bootstrap-config` | Seed command: scans top-level dirs, proposes the config draft |
| `extract` | Emit command: reads DB + index + config, writes the model |
| `_evaluate` | P1 helper that walks anchors and returns their live FRESH/STALE/ORPHANED state |
| Block 4 | The frozen public contract for `diagram-model.json` (skeleton-contracts.md) |

---

## Summary

P3 is the deterministic heart of the ssot-diagram pipeline. It reads three
inputs — the codegraph SQLite DB (read-only, `mode=ro&immutable=1`), the curated
`docs/decision-index.json` (P1's output, now fully curated for `mkt_engine`),
and a curated `ssot-diagram.config.json` (glob → component name) — and emits one
`diagram-model.json` whose bytes are identical across runs given identical
inputs. The model is a three-level tree: macro (human-named components) → micro
(the file, or the single dominant class when a file is one class) → nano (the
functions/methods inside, capped per micro by caller count, the rest collapsed
into one honest "+K more" node). Every node carries a content `signature`
(file → `files.content_hash`; symbol → sha256 of the source slice; component →
sha256 over its members' hashes), reusing the P1 recipes verbatim. Rolled-up
edges carry counts and a stable 3-row `sample_callers[file:line]` (no calling
symbol — 76% of incoming edges to functions/methods have a `file:` source, no
symbol exists; see §Edge roll-up). Verified decisions
attach as `decision:<ADR-ID>@<component-id>` nodes with a live FRESH/STALE/
ORPHANED badge; unverified anchors produce no decision node. The pre-extract
guard warns (stderr) and exits 0 when the index is not fully verified/FRESH, so
P3 stays parallel-runnable. The script also ships a CLI subcommand
`bootstrap-config` that seeds the config from top-level directories, mirroring
P1's seed-then-curate pattern.

## Constraints

The six grill contracts are FROZEN and bind this design (see handoff
`p3-pipeline-state.md` §"6 locked contracts"):

1. **Pilot = `mkt_engine`** — extractor lives here; tests + golden model target
   `~/all-projects/mkt_engine`. Determinism + schema tests run against the live
   seed NOW (the handoff's "0/25 verified" baseline is stale — see Discoveries
   in the dispatching summary; the live index is 8 ADRs / 33 anchors, all
   `verified:true`, all FRESH as of 2026-07-04).
2. **No-config `extract` = fail-loud** — exits with a "run `bootstrap-config`
   first" message when `ssot-diagram.config.json` is absent. Two clean
   contracts: `bootstrap-config` seeds+writes; `extract` reads+emits.
   Matches P1's `load_index` fail-loud style.
3. **Nano cap = top N (default 8) per micro by caller count** — the rest
   collapse into one synthetic `kind=collapsed` node whose `signature` is sha256
   over the collapsed members' hashes. Honest about dropped symbols. The "caller
   count" rank key is pinned to incoming `calls` + `instantiates` edges to the
   symbol (NOT `references` — see SERIOUS1 below: 348 of 428 `references` target
   `interface`, only 3 target `function`; folding them in would rank functions by
   signature-type mentions, not incoming calls). The grill's "by caller count"
   wording is ambiguous; P3 pins it to calls+instantiates, contract-compliant
   (the grill fixes the cap, not the rank-key set). Ties broken by
   `qualified_name` ASC then `path` ASC (determinism hole closed per NOTE).
4. **Multi-anchor decision = attach to every component owning ≥1 verified
   anchor** — id `decision:<ADR-ID>@<component-id>`. One underlying decision,
   one consistent status badge across attachments. No phantom cross-cutting
   component (Block 4a frozen three-level hierarchy).
5. **Pre-extract guard = warn-and-continue** — if the index has `verified:false`
   OR any not-FRESH anchor, print a stderr warning pointing at
   `decision_index refresh <id>`, exit 0. Model is still truthful: unverified
   → no decision node. Staleness is consumed via the live L1 badge logic
   (recompute per-anchor `current_sig`, compare — same as P1's
   `anchor_status`), NOT a separate status re-run.
6. **Edge encoding = per-node `edges[]` array** —
   `{source, target, kind, count, sample_callers[{file,line} ×3]}` (no `symbol`
   field — FATAL1: 831 of 1124 `calls` edges have a `file:` source node with no
   calling symbol; 689 of 902 incoming calls+references to fn/method/class have a
   `file:` source, 76%; Block 4c only requires `sample_callers[file:line ×3]`,
   no symbol). Directional (source→target = source depends on target),
   `kind ∈ {calls, imports, references}` (contract-freeze 3 kinds;
   `instantiates` folds into `calls`, `implements` dropped — see SERIOUS2 /
   §Edge roll-up). Sample_callers top 3 with a STABLE tiebreak (call-site
   `file:line` ascending). Matches Block 4c.

Cross-cutting constraints from CLAUDE.md and `skeleton-contracts.md`:

- **Read-only DB** — connect `mode=ro&immutable=1`; `_shared/design.md` Block 1e
  invariants (never write `codegraph.db`). P3 reuses P1's `open_db` /
  `verify_schema` rather than re-implementing.
- **Every persisted LLM artifact pinned to a content signature** (Block 1e,
  5b) — P3's `signature` field is the pin P4 narratives will later attach to.
- **Every tool registers in `manifest.json`** — a script not in the manifest
  does not ship. P3 adds one entry under key `diagram-model` (script
  `ssot-diagram/graph_model.py`, scope `repo`, no hook events in P3 — hook
  wiring is P6).
- **Verdicts are pure computations over the DB** — no LLM decides anything in
  P3. P3 emits the deterministic substrate; P4 layers inference on top, P5
  renders it.
- **`_shared/` not yet extracted** — only `design.md` exists; the Block 1
  clean-cutover is a later "Phase B" task per Block 1 note. P3 reuses P1's
  recipe by importing `decision_index` as a sibling module (precedent:
  `decision_hook.py:22-23` does exactly this with `sys.path.insert`).
- **Component signature dossier** — `node.id` must be deterministic and
  derived from path/qualified name (Block 4b); codegraph's internal `nodes.id`
  is `<kind>:<content-hash>` and therefore NOT stable across edits, so P3
  MUST synthesize its own `id` and never pass `nodes.id` through (see
  Assumptions to verify).

## Guardrail Checklist

No `guardrail-check` command exists in this repo (the skill notes it is a
no-op outside a Writ repo); the check was attempted and confirmed absent. The
relevant invariants are inlined above under Constraints (read-only DB,
manifest registration, signature pinning, no-LLM verdicts) and are checked
per-option below in the Constraints-check rows.

## Alternatives Considered

### Option A — Reuse P1's recipe by importing `decision_index` as a sibling (Recommended)

**What this means:** P3 reaches into the already-shipped P1 engine for its DB
open, schema guard, file/symbol signature, and anchor-status helpers instead of
copying them. This avoids a second copy of the load-bearing recipe while the
`_shared/` extraction (Block 1, "Phase B") is still pending. The owner gets one
less source of drift to curate.

**Approach:** `graph_model.py` does
`sys.path.insert(0, str(Path(__file__).resolve().parent)); import decision_index as di`
— the exact pattern `decision_hook.py` already uses. P3 calls `di.find_db`,
`di.open_db`, `di.verify_schema`, `di.file_content_hash`, `di.slice_hash`,
`di.symbol_spans`, `di.current_sig`, `di.anchor_status`, `di.parse_ref`. New
helpers in `graph_model.py` are limited to: component grouping (reads
`ssot-diagram.config.json`), micro-level selection (file vs dominant class),
nano cap + collapse, edge roll-up with stable sample selection, decision-node
merge, model id synthesis, and JSON serialization (sorted keys, fixed
indentation, trailing newline) for byte-determinism.

**Files touched:**
- `ssot-diagram/graph_model.py` (new) — the extractor + `bootstrap-config`.
- `ssot-diagram/ssot-diagram.config.json` (generated, then curated) — the glob
  → component-name map; `bootstrap-config` writes the seed, a human curates.
- `ssot-diagram/test_graph_model.py` (new) — golden model + determinism tests.
- `manifest.json` (edit) — add one `diagram-model` entry (no hook events in P3).
- `docs/decision-index.json` is read-only input (already curated for
  `mkt_engine`); P3 never writes it.

**Cost:**
- Dev effort: medium — most risk is in component grouping + edge roll-up +
  stable ordering, not in DB plumbing.
- Runtime cost: one SQLite read pass + one JSON write. No LLM, no network.
- Maintenance: one new module (≈400 lines) + one config schema to document.
  Doubles as the substrate for P4/P5; not throwaway.

**Risk:**
- Coupling to P1 internals: P3 becomes a second caller of `di.current_sig` /
  `di.anchor_status`. Any signature change in P1 must update two callers. Mitigation:
  the contract (Block 1) explicitly schedules the `_shared/` extraction as a
  clean cutover that updates both at once; until then, P1's tests + P3's tests
  both guard the recipe.
- Sibling import relies on `sys.path` mutation: fragile if the file is moved.
  Mitigation: `decision_hook.py:22` established this exact pattern and it is
  the repo convention; P3 mirrors it verbatim.

**Module depth:**
- New module boundaries: one — `graph_model.py`. Deletion test: delete it and
  the three-level model, edge roll-up, decision merge, and bootstrap-config all
  vanish from the world — complexity concentrates in callers (P5 renderer has
  nothing to read), so it earns its keep (deep module: small interface =
  "extract → diagram-model.json", large implementation).
- New interfaces: one public CLI surface (`extract`, `bootstrap-config`).
  Real seam: 2+ adapters already planned (P5 renderer + plan-visualizer both
  read `diagram-model.json`; narratives worklist P4 keys on `id`+`signature`).
- Existing modules affected: `decision_index.py` stays as-is (read dependency,
  no edit). `manifest.json` grows one entry. No shallow module deepened.

**What it defers:** the `_shared/` extraction (Block 1 clean cutover) stays a
later task; P3 does not pre-empt it. The hook form (P6) is deferred — P3 ships
CLI-first, no hook events registered.

**Constraints check:**
- [x] C-read-only — satisfies. Reuses P1's `open_db` (`mode=ro&immutable=1`).
- [x] C-manifest — satisfies. Adds one `diagram-model` entry, no hook events.
- [x] C-no-llm — satisfies. Every field is a pure computation.
- [x] C-signature-pin — satisfies. Every node carries a content hash from P1's
  recipe.
- [x] C-frozen-6 — satisfies by construction (each contract addressed below).

### Option B — Copy the recipe inline into `graph_model.py`

**What this means:** P3 carries its own private copy of `find_db`, `open_db`,
`verify_schema`, `file_content_hash`, `symbol_spans`, `slice_hash`,
`current_sig`, `anchor_status`, `parse_ref`. Zero cross-file coupling; P1 can
change without touching P3.

**Approach:** same external behavior, but ~120 lines of `decision_index.py` are
duplicated. The Block 1 `_shared/` extraction then has THREE consumers to unify
(P1, the hook, P3) instead of two.

**Files touched:** same as Option A but `graph_model.py` is ~520 lines and
does not import `decision_index`.

**Cost:**
- Dev effort: slightly higher (more code to write + test).
- Runtime cost: identical.
- Maintenance: higher — two copies of the signature recipe to keep honest.
  Any bug fix must be applied twice; drift between them is silent until a
  signature mismatch surfaces.

**Risk:**
- Drift between P1's recipe and P3's copy: a future edit to `slice_hash` in P1
  (e.g. normalizing line endings) that is not mirrored in P3 will produce
  different signatures for the same symbol, breaking the Block 5b trust rule
  (narrative pinned to P3's signature would not match P1's staleness check).
  Mitigation: a shared test that asserts P3 and P1 produce the same signature
  for the same anchor — but that test is itself a coupling, which defeats the
  isolation Option B buys.

**Module depth:**
- Deletion test: the duplicated recipe reappears in P3 — removing P3 leaves the
  recipe in P1 (good, P1 keeps working) but the recipe is now triplicated
  overall. Shallow module within P3 (the recipe is a utility, not a deep
  interface).
- Seam: same public surface as A. The internal seam (signature recipe) is
  speculative — only P3 uses P3's copy.

**What it defers:** same as A, plus it defers the
"don't-reimplement-the-sig-recipe" rule twice over.

**Constraints check:**
- [x] C-read-only — satisfies.
- [x] C-manifest — satisfies.
- [x] C-no-llm — satisfies.
- [x] C-signature-pin — satisfies, but with drift risk.
- [x] C-frozen-6 — satisfies.

### Option C — Extract `_shared/` now, P1 + P3 both import it

**What this means:** do the Block 1 "Phase B" clean cutover inside P3: lift
`find_db`/`open_db`/`verify_schema`/the signature recipe into `_shared/db.py`
+ `_shared/sig.py`, rewire `decision_index.py` and `decision_hook.py` to import
from there, then P3 imports the same. One copy of the recipe machine-wide.

**Approach:** the contract (Block 1 note) explicitly says the cutover is
"clean, no back-compat aliases; P1's tests must pass unchanged." That is a
separate, larger refactor that touches shipped code (`decision_index.py` + its
tests + `decision_hook.py`) and is scoped to "Phase B" per
`skeleton-contracts.md`. Doing it inside P3 inflates P3's blast radius and
couples P3's delivery to P1's test suite passing unchanged — a coupling
neither P3 nor P1 asked for.

**Files touched:** `_shared/db.py` (new), `_shared/sig.py` (new),
`decision_index.py` (large edit — remove the inlined recipe, import `_shared`),
`decision_hook.py` (edit import path), `graph_model.py` (new, imports
`_shared`), plus P1's test suite must still pass.

**Cost:**
- Dev effort: high — a refactor of shipped code plus the new extractor.
- Runtime cost: identical.
- Maintenance: lowest long-term (one recipe), highest short-term (refactor
  risk on shipped P1).

**Risk:**
- P1 regression: a clean cutover with no back-compat aliases can break P1's 45
  tests in subtle ways (import path, `sys.path` derivation). Mitigation: run
  the full P1 suite after cutover — but that is exactly the
  scope-creep CLAUDE.md §3 forbids ("Touch only what the request requires").
- Violates §3 Scope Discipline: this design is P3, not the Block 1 extraction.

**Module depth:** the new `_shared/` modules are deep (small interface, large
implementation) and earn their keep by the deletion test — but that earn is
the Block 1 contract's job, scheduled for "Phase B", not P3's.

**Constraints check:**
- [x] C-read-only — satisfies.
- [x] C-manifest — satisfies.
- [x] C-no-llm — satisfies.
- [x] C-signature-pin — satisfies, one copy.
- [x] C-frozen-6 — satisfies.
- [⚠️] C-scope — violates CLAUDE.md §3 (touches shipped P1 +酱 beyond P3's
  request). The contract itself flags this as a separate phase.

### Rejected alternatives (one line each)

- **Auto-derive component name from path prefix** (e.g. `lib/ai/*` → "AI"):
  the scout (`macro-component-grouping-prior-art.md`) shows dependency-cruiser's
  own caveat that capture-group / dynamic grouping is "fragile when a path
  matches multiple groups." Explicit glob → name is the safer subset for a
  non-SWE owner.
- **Phantom cross-cutting component for multi-anchor decisions**: violates
  Block 4a (frozen three-level hierarchy). Refused in the grill.
- **Nano silent-truncate**: hides dropped symbols, violates the "honest about
  dropped symbols" intent of contract 3. Refused in the grill.
- **Fail-loud pre-extract guard requiring all-FRESH+verified**: couples P3's
  runnability to P2 completion. Refused in the grill (contract 5).

> Recommended: Option A. It reuses the already-shipped, already-tested P1
> recipe without paying for the Block 1 refactor that the contract itself
> schedules separately — the lowest blast radius that still keeps one copy of
> the signature recipe.

**ADR offer:** Option A is hard to reverse (a second caller of P1 internals),
surprising without context (a future reader will wonder why P3 imports P1
instead of `_shared`), and a real trade-off (Option B's isolation was viable).
All three gates fire. An ADR is offered but not written here — see Open
Questions (OQ-ADR-1).

---

## Chosen Approach

**Option A** — `ssot-diagram/graph_model.py`, importing `decision_index` as a
sibling module (the `decision_hook.py` precedent). One new file + one new
config + one `manifest.json` entry + tests. No hook in P3.

### CLI surface

```
graph_model.py extract [--db DB] [--index INDEX] [--config CONFIG]
                       [--out OUT] [--nano-cap N]
graph_model.py bootstrap-config [--db DB] [--out CONFIG] [--force]
```

- `bootstrap-config` seeds `ssot-diagram.config.json` from the top-level
  directories of indexed files; refuses to overwrite a curated config without
  `--force` (mirrors `decision_index.bootstrap`'s `--force` gate at line 237).
  Emits one component per top-level dir, glob `<dir>/**`. Human curates
  (rename, merge, split) before `extract`.
- `extract` is the fail-loud contract: no `ssot-diagram.config.json` → exit 1
  with "run `bootstrap-config` first" (mirrors `decision_index.load_index`
  at line 165). Reads DB + index + config; writes `diagram-model.json`.
- Re-seed policy: `extract` NEVER re-seeds the config; if the config is
  missing or its globs no longer cover files that changed, the human reruns
  `bootstrap-config --force` (same shape as `decision_index refresh` being a
  separate, human-gated command). Drift between config and files is surfaced
  as an `unknown` component (see schema), not silently auto-merged.

### `ssot-diagram.config.json` schema (P3 owns; PENDING in Block 4)

```json
{
  "version": 1,
  "components": [
    {
      "id": "cmp-ai",
      "name": "AI image generation",
      "glob": "lib/ai/**",
      "notes": "human-readable, ignored by logic"
    }
  ],
  "default_component": "cmp-misc",
  "nano_cap": 8
}
```

- **`version`** (int, required): schema version; bump on incompatible change.
  P3 starts at 1.
- **`components[]`** (required, ordered): each entry is `{id, name, glob,
  notes?}`.
  - `id` (string, required): stable component identifier, unique within this
    file. Convention `cmp-<slug>`. Used in node `id` synthesis and in the
    decision-node attachment id `decision:<ADR-ID>@<component-id>`. MUST be
    stable across curations (renames break narrative pinning in P4) — warn on
    change in a later phase; P3 just uses it.
  - `name` (string, required): human-facing label, mutable.
  - `glob` (string, required): `fnmatch`-style pattern matched against the
    repo-relative `file_path` of every indexed file. First match wins (order =
    file order). `**` is the usual recursive form (stdlib `pathlib.PurePath`
    + `fnmatch` with the path's forward slashes; mkt_engine uses forward
    slashes throughout — verified).
  - `notes` (string, optional): human-only, never read by logic (mirrors
    dependency-cruiser's `comment` field per the scout).
- **`default_component`** (string, required): id of the component that swallows
  files matched by no glob. P3 ALWAYS seeds one named `cmp-misc` (id stable,
  name "Other") with `glob` set to a sentinel that never matches, so every file
  lands somewhere. This is the **unknown-path placement** answer Block 4 PENDING
  asked for: invisible bucket, never omitted, so counts add up.
- **`nano_cap`** (int, optional, default 8): per-micro nano cap (contract 3).
  Override per-extract with `--nano-cap`.

**Multi-match disambiguation:** first matching component in file order wins.
P3 does NOT support `$1` capture groups (scout: fragile on multi-match). If
two globs could match the same path, the curator is expected to order them;
P3 emits a stderr warning at `extract` time when a file matches >1 glob (so a
curator notices), but still assigns to the first.

**unknown-path component placement:** the `default_component` catches every
file matched by no explicit glob. The seed writes a `cmp-misc` row; a curator
may rename it but must not delete it (P3 fails loud if
`default_component` is missing from `components[]`).

### `diagram-model.json` — full node field list (Block 4b frozen subset + extras)

Block 4b FROZEN subset: `id`, `kind`, `name`, `path`, `signature`. P3 adds the
extras below, each justified:

```json
{
  "version": 1,
  "generated_at": null,
  "root": "<repo-relative root>",
  "components": [
    {
      "id": "cmp-ai",
      "kind": "component",
      "name": "AI image generation",
      "path": "lib/ai",
      "signature": "<sha256 over member file+symbol hashes>",
      "file_count": 46,
      "symbol_count": 232,
      "decisions": ["decision:ADR-0002@cmp-ai", "..."],
      "children": ["micro:lib/ai/image/index.ts", "..."],
      "edges": [
        {"source": "cmp-ai", "target": "cmp-canvas", "kind": "calls",
         "count": 14,
         "sample_callers": [
           {"file": "lib/ai/image/index.ts", "line": 18},
           {"file": "lib/ai/image/providers/fal/index.ts", "line": 42}
         ]}
      ]
    }
  ],
  "micros": [
    {
      "id": "micro:lib/ai/image/index.ts",
      "kind": "micro",
      "name": "index.ts",
      "path": "lib/ai/image/index.ts",
      "signature": "<files.content_hash>",
      "component_id": "cmp-ai",
      "dominant_class": null,
      "caller_count": 7,
      "decisions": [],
      "children": ["nano:...requireEnv@lib/ai/llm/providers/openai-compat/index.ts", "..."],
      "edges": []
    }
  ],
  "nanos": [
    {
      "id": "nano:requireEnv@lib/ai/llm/providers/openai-compat/index.ts",
      "kind": "nano",
      "name": "requireEnv",
      "path": "lib/ai/llm/providers/openai-compat/index.ts",
      "signature": "<slice_hash>",
      "micro_id": "micro:lib/ai/llm/providers/openai-compat/index.ts",
      "caller_count": 3,
      "qualified_name": "requireEnv",
      "start_line": 13,
      "end_line": 19,
      "docstring": null,
      "is_exported": true,
      "edges": [
        {"source": "nano:...requireEnv@...", "target": "nano:...other@...",
         "kind": "calls", "count": 1,
         "sample_callers": [{"file": "...", "line": 18}]}
      ]
    },
    {
      "id": "nano:+collapsed@micro:lib/jobs/job.ts",
      "kind": "collapsed",
      "name": "+5 more",
      "path": "lib/jobs/job.ts",
      "signature": "<sha256 over collapsed members' hashes>",
      "micro_id": "micro:lib/jobs/job.ts",
      "collapsed_count": 5
    }
  ],
  "decisions": [
    {
      "id": "decision:ADR-0006@cmp-canvas",
      "kind": "decision",
      "name": "ADR-0006",
      "path": "docs/adrs/ADR-0006-canvas-store.md",
      "signature": "<sha256 over the decision's anchor signatures>",
      "adr_id": "ADR-0006",
      "component_id": "cmp-canvas",
      "status": "FRESH",
      "supersedes": null,
      "anchor_count": 10
    }
  ]
}
```

**Frozen subset (Block 4b) on every node** — `id`, `kind`, `name`, `path`,
`signature`:

- `id` — P3-synthesized, deterministic, derived from path/qualified name (NOT
  codegraph's `nodes.id`, which is content-hashed and changes per edit; see
  Assumptions to verify). Forms:
  - component: `cmp-<slug-from-config-id>`
  - micro (file-dominant): `micro:<relpath>`
  - micro (class-dominant): `micro:<relpath>#<qualified_name>`
  - nano: `nano:<qualified_name>@<relpath>`
  - collapsed: `nano:+collapsed@micro:<micro_id>`
  - decision: `decision:<ADR-ID>@<component-id>` (contract 4)
- `kind` — one of `component | micro | nano | collapsed | decision`.
- `name` — human label.
- `path` — repo-relative.
- `signature` — see §Signature dossier below.

**Extras (PENDING in Block 4b) — each justified:**

- `qualified_name` (nano only): needed because `name` is the bare short name
  (e.g. `requireEnv`) which is NOT unique across the repo (verified: two files
  have a `requireEnv`). P4 narratives and the resolver need the qualified form
  to disambiguate; carrying it on the node avoids a DB read-back. Justified by
  the Block 1a resolver discipline (honest AMBIGUOUS — without `qualified_name`
  + `path`, a bare-name lookup is ambiguous).
- `caller_count` (micro + nano): the rank key for the nano cap (contract 3)
  and the blast-radius hint plan-visualizer reads. **Pinned to incoming
  `calls` + `instantiates` edges to the symbol (NOT `references`)** — SERIOUS1:
  348 of 428 `references` target `interface`, only 3 target `function`; folding
  `references` in would rank functions by signature-type mentions. Computed once
  from raw edges; cheap to persist.
- `docstring` (nano only, may be null): the deterministic fallback P4 uses for
  narrative text (`roadmap.md` P4 line 124: "kind + name + docstring first
  sentence + counts"). Carrying it on the node avoids P4 re-opening the DB.
- `is_exported` (nano only): mkt_engine has 259 exported / 856 non-exported
  (verified); exported-ness is a useful filter for "is this a public surface"
  in P5 rendering. Cheap, single bit.
- `start_line` / `end_line` (nano only): the slice extent for `slice_hash`;
  persisted so P4/P5 can locate the source without re-deriving.
- `dominant_class` (micro only, null when file-dominant): when a file holds
  exactly one class and that class is the bulk of the file, micro = that
  class. Verified: mkt_engine has only 10 `class` nodes across 10 files, so
  this rarely triggers — matches the handoff's DB reality note.
- `component_id` (micro) / `micro_id` (nano): back-pointers so the renderer
  can traverse either direction without walking the tree.
- `children[]` (component + micro): forward-pointers to direct children's
  `id`s, so the renderer expands in one pass.
- `edges[]` (component + micro + nano): per-node rolled-up edge list
  (contract 6 / Block 4c). Each edge:
  `{source, target, kind, count, sample_callers[]}` where `sample_callers`
  is `[{file, line}]` top 3 with stable tiebreak (call-site `(file, line)`
  ascending; FATAL1: no `symbol` field — 76% of incoming edges to
  fn/method/class have a `file:` source node with no calling symbol). For
  symbol-sourced edges `file` = source node's `file_path`, `line` =
  `edges.line`; for file-sourced edges (source is a `file:` node) `file` =
  source node's `file_path`, `line` = `edges.line` (which is the import/use
  site, not a call site — see §Edge roll-up for the file-sourced case).
  `kind ∈ {calls, imports, references}` exactly (contract 6 freeze);
  `instantiates` folds into `calls`, `implements` is dropped (SERIOUS2 /
  §Edge roll-up).
- `decisions[]` (component + micro): the decision-node ids attached at this
  level (contract 4: every component owning ≥1 verified anchor gets an
  attachment; only verified anchors produce decision nodes).
- `file_count` / `symbol_count` / `collapsed_count` / `anchor_count`: cheap
  counts for legend / tooltip rendering in P5.
- `version`, `generated_at` (null always — see Determinism), `root`,
  `status` (decision only, `FRESH|STALE|ORPHANED|superseded`): model-level or
  decision-level meta. `generated_at` is null because a real timestamp breaks
  byte-determinism; consumers that want "when was this built" read the file
  mtime.

**Non-fields (deliberately omitted):**

- `nodes.signature` (the DB column) — that is the CODE signature (`(request:
  Request): Promise<NextResponse>`), NOT a content hash. Confusingly named;
  P3 does NOT propagate it. The model `signature` is the content hash from
  `file_content_hash` / `slice_hash` (Block 1e).
- `nodes.id` (the codegraph internal id `<kind>:<hex>`) — content-derived, not
  path-derived; violates Block 4b's "derived from path/qualified name"
  stability requirement (a one-line edit changes it, breaking narrative
  pinning). P3 synthesizes ids (above).
- `visibility`, `is_async`, `is_static`, `is_abstract`, `decorators`,
  `type_parameters`, `return_type`, `start_column`, `end_column`,
  `language`, `updated_at` — not needed by any P3–P5 consumer; carrying them
  is speculative flexibility (CLAUDE.md §3 forbids). P3 reads `language` for
  the docstring slice but does not persist it.

### Signature dossier (reusing P1)

- **file (micro, file-dominant):** `di.file_content_hash(con, relpath)` →
  `files.content_hash` (sha256 of file content; verified column exists).
- **symbol (nano):** `di.slice_hash(root, relpath, start, end)` → sha256 of
  the source slice `[start_line, end_line]` 1-based inclusive. P3 gets
  `(start, end)` from `di.symbol_spans(con, qualified_name, relpath)` —
  which queries by `(qualified_name, file_path)` because `qualified_name`
  alone is NOT unique (verified: `requireEnv` in two files).
- **class-dominant micro:** `di.slice_hash(root, relpath, start, end)` over
  the class node's span (same as a nano).
- **component (macro):** sha256 over the sorted list of member file
  `content_hash`es (Block 1e: "component = sha256 over member hashes"). Sorted
  so member ordering does not perturb the hash.
- **collapsed nano:** sha256 over the sorted list of collapsed members'
  `signature` fields (contract 3).
- **decision node:** sha256 over the sorted list of the decision's anchor
  `sig` values (so a decision node changes iff any anchor's content changes —
  exactly when the L1 staleness badge flips, by construction).

### Decision-node merge (contract 4)

For each decision in the index with `verified:true` on at least one anchor:

1. Resolve each verified anchor's owning micro via `di.parse_ref` + the
   component map (a `file:<path>` anchor → that file's micro; a
   `<qname>@<path>` anchor → the file's micro, with the symbol flagged as the
   anchor target inside that micro's `decisions[]` extra).
2. Compute the live badge per anchor via `di.anchor_status(con, root, anchor)`
   (returns `FRESH | STALE | ORPHANED | AMBIGUOUS`). The decision's badge is
   the WORST status across its verified anchors (ORPHANED > STALE > AMBIGUOUS
   > FRESH), so a single drifted anchor marks the whole decision as needs-
   review — conservative and honest.
3. Attach `decision:<ADR-ID>@<component-id>` to every component owning ≥1
   verified anchor's micro. Same underlying status across all attachments
   (one decision, one badge).
4. `supersedes` is read from the index and emitted as a property; a decision
   whose `supersedes` chain points at it renders `status: superseded` (the
   renderer treats that as disabled per P5).

Unverified anchors produce no decision node (contract 5: model stays truthful).
The pre-extract guard warns on stderr if any anchor is `verified:false` or
not FRESH, exits 0.

### Edge roll-up (contract 6 / Block 4c)

The codegraph `edges` table has 6 kinds in the live DB: `calls` (1124),
`contains` (961), `imports` (793), `references` (428), `instantiates` (17),
`implements` (5). P3 collapses them to the contract-6 frozen three via the
rules below. Each rule is keyed off the kind's distinct shape (verified against
the live DB). `contains` is the tree-parent relationship, already expressed by
`children[]` / back pointers, not an edge.

#### `calls` roll-up (symbol→symbol, fold `instantiates`)

- **Shape:** source is a `function`/`method`/`file:` node, target is a
  `function`/`method`/`class` node. 1124 edges.
- **`instantiates` fold:** the 17 `instantiates` edges
  (`file`/`function → class`, verified) are genuine `new X()` call-deps and are
  emitted with `kind: "calls"`. They roll up identically (source micro → target
  micro = the class's file).
- **`implements` drop:** the 5 `implements` edges are all `class → interface`
  (verified) — type relations, not call deps. Dropped entirely (they were never
  in the contract-6 frozen set; this is a drop, NOT a contract amend). If P5
  later wants type relations, that's a deliberate Block 4c amendment, not P3.
- **Nano-level:** edge between two nanos in different micros, `count` =
  number of raw `calls`+`instantiates` edges between that source/target pair.
- **Micro-level / component-level:** aggregate by source micro/component ×
  target micro/component. Within-component edges appear only at micro/nano
  level (`roadmap.md` line 96).
- **`sample_callers[{file,line}]` (top 3, stable tiebreak):** for each
  rolled-up edge, collect all source call-sites
  `(source.file_path, edge.line)`; emit the 3 lexicographically smallest
  (tiebreak = `(file, line)` ascending). NO `symbol` field (FATAL1: 831 of 1124
  `calls` edges have a `file:` source; a symbol field is unimplementable for
  76% of incoming edges to fn/method/class). For symbol-sourced edges the
  `file` is the source function's `file_path`; for file-sourced edges the
  `file` is the source `file:` node's `file_path` (the import/use site, not a
  call site — surfaced as the caller location; see R8).

#### `references` roll-up (type-relation, kept but excluded from rank)

- **Shape:** 348 of 428 target `interface`, 77 `type_alias`, only 3 target
  `function` (verified). These are type relations (a symbol's signature mentions
  an interface), NOT call dependencies.
- **Roll-up:** emit as `kind: "references"` in the model `edges[]` (Block 4c
  includes it), aggregated the same way as `calls` (source micro → target
  micro owning the referenced type). Sample_callers same shape.
- **EXCLUDED from `caller_count`:** references do not count toward the
  nano-cap rank (SERIOUS1 — folding them in would rank functions by
  signature-type mentions, not incoming calls). Block 4c still gets them as
  edges; contract 3's "by caller count" rank is pinned to `calls` +
  `instantiates` only.

#### `imports` roll-up (TWO sub-shapes — FATAL2)

The `imports` kind has two semantically distinct shapes that must NOT be
rolled together. Live DB: 440 edges target an `import:` node, 353 target a
real symbol (function 151, interface 113, constant 49, type_alias 24, class
12, file 4).

- **(a) `file → import:` node — external-module, self-micro.** 440 edges,
  ALL of which are same-file (`source.file_path == import:.file_path`,
  verified for all 440). These represent `import` statements the codegraph
  extracted as `import:` placeholder nodes (a symbol resolves to an external
  module path, not a repo symbol). They are SELF-micro (the file imports
  itself, semantically a no-op for the diagram) and NEVER cross-component.
  P3 DROPS them as self-loops. (Alternative: bucket as a separate "external
  import" edge set pointing at the import-node's module name — deferred to P5
  if the renderer wants external-dep arrows; P3 drops to keep the model clean
  of placeholder nodes.) Documented here so the drop is explicit, not silent.
- **(b) `file → symbol` — intra-repo real import.** 353 edges where the
  target is a repo symbol (function/interface/constant/type_alias/class/file).
  These roll up as `file → target-symbol's-owning-micro`, resolved via the
  TARGET symbol's `file_path` (NOT treating the target as a nano — a file
  importing an interface creates a micro→micro edge, source = importing file's
  micro, target = interface's file's micro). `count` = number of intra-repo
  import edges between that source-file/target-micro pair.
  `sample_callers[{file,line}]`: `file` = importing file's path, `line` =
  `edges.line` (the import statement line). NO symbol (the source is always a
  `file:` node for imports; FATAL1).
- **Micro-level / component-level:** sub-shape (b) aggregates by source
  micro/component × target micro/component. Sub-shape (a) does not appear at
  any level (dropped).
- **`caller_count`:** intra-repo imports (sub-shape b) are also EXCLUDED from
  the nano-cap rank — a function with many type-imports is not "high-traffic."
  The rank is `calls` + `instantiates` incoming only (SERIOUS1).

### Direction and source/target orientation

`source → target` means "source depends on target" (source calls/imports/
references target). Matches the edges table's `source`/`target` orientation
(verified: in the live DB, `function:POST@.../route.ts` → `function:... logout`
is the caller→callee direction). The joined `nodes.id` is the codegraph
internal id (`<kind>:<hex>`); P3 recovers `file_path` + `qualified_name` by
joining `edges.source` and `edges.target` to `nodes.id` (the join key is the
codegraph id, NOT the model id — the model id is path-derived and the
codegraph id is content-derived; see Assumptions to verify #11).

### Nano-cap selection (deterministic tiebreak — NOTE)

The nano-cap (contract 3) selects the top N (default 8) nanos per micro. The
rank key is `caller_count` (=`calls`+`instantiates` incoming), DESC. Live DB:
82 of 252 fn/method nanos (33%) have ZERO incoming calls+instantiates — ties
at zero (and elsewhere) are common and need a deterministic secondary sort or
the cap is non-deterministic across runs.

Selection sort:
1. primary: `caller_count` DESC
2. secondary: `qualified_name` ASC
3. tertiary: `path` ASC

The cap takes the first N; the rest (sorted the same way) collapse into the
`collapsed` node whose `collapsed_count` and member list follow that same
order (deterministic). This closes the NOTE determinism hole.

### Determinism (byte-identical JSON given identical inputs)

- All dict keys emitted in sorted order (`json.dumps(doc, indent=2,
  sort_keys=True, ensure_ascii=False) + "\n"` — STRICTER than P1's `save_index`
  at line 178, which does NOT sort keys; P3 must, because P3 emits from dict
  iteration whereas P1's index is human-curated to a stable order).
- All lists sorted by a deterministic key (component by `id`, micro by
  `path`, nano by `qualified_name` then `path`, edge by
  `(source, target, kind)`, `sample_callers` by `(file, line)`, collapsed
  members by `qualified_name` then `path`).
- `generated_at` always null.
- No `set()` iteration order leaks anywhere; P3 sorts explicitly everywhere.
- Test: two `extract` runs in a row on `mkt_engine` produce identical bytes
  (exit criterion, `roadmap.md` line 113).

### Pre-extract guard (contract 5)

Before emitting, `extract` loads the index via `di.load_index` (which fails
loud on bad JSON / missing `decisions` key), then for each decision checks:
(a) every anchor's `verified` flag; (b) `di.anchor_status` per anchor. If any
`verified:false` OR any status ≠ FRESH → stderr warning listing the offending
`<ADR-ID>` + `ref`, pointing at `decision_index refresh <id>`, then continues
to emit (exit 0). The model is still produced and is still truthful
(unverified → no decision node; not-FRESH → decision node with the worst-case
badge).

### `manifest.json` entry (CLI-first; no hook in P3)

```json
"diagram-model": {
  "script": "ssot-diagram/graph_model.py",
  "scope": "repo",
  "desc": "ssot-diagram P3 — extract diagram-model.json from codegraph DB + decision index",
  "hooks": []
}
```

`hooks: []` because P3 ships CLI-first; the PostToolUse hook that re-runs
`extract` on codegraph re-index is P6. Registering as `repo` scope matches the
other ssot-diagram entry (`decision-index`) and the per-repo `.claude/
settings.json` model.

### Tests (`ssot-diagram/test_graph_model.py`)

- **Golden model** — run `extract` against the live `mkt_engine` DB + index,
  assert the produced JSON matches `ssot-diagram/testdata/mkt_engine.model.json`
  (committed). Re-recording is a deliberate `--update-golden` action.
- **Determinism** — two consecutive runs produce byte-identical output
  (sha256 comparison).
- **Verified-anchored decision appears once** — for `mkt_engine` (now 8 ADRs /
  33 verified anchors all FRESH), assert 8 decision nodes appear, each
  attached to ≥1 component, each badge = FRESH.
- **Unverified anchor → no decision node** — synthetic fixture: flip one
  anchor's `verified` to false, assert no decision node `decision:<that-ADR>@*`
  is emitted.
- **Nano cap + collapse** — synthetic fixture with 12 functions in one micro,
  `--nano-cap 8`: assert 8 nano + 1 `collapsed` node whose `collapsed_count=4`
  and whose `signature` is sha256 over the 4 members' hashes. Assert the
  selected 8 + the 4 collapsed are the ones the deterministic sort
  (`caller_count` DESC, `qualified_name` ASC, `path` ASC) picks — including
  the zero-caller case (NOTE: 33% of nanos tie at zero; the secondary sort
  must break those ties deterministically).
- **Sample_callers shape (FATAL1)** — assert every `sample_callers` entry is
  `{file, line}` with NO `symbol` key. Synthetic fixture with 5 call-sites
  into one target where 3 have a `file:` source and 2 have a `function:`
  source: assert the 3 emitted are the lexicographically smallest
  `(file, line)`, in that order, across two runs. Assert file-sourced edges
  populate `file`/`line` from the source `file:` node's `file_path` + the
  `edges.line` (the import/use site), not a call site.
- **imports two-shape roll-up (FATAL2)** — synthetic fixture: 2 `file→import:`
  same-file edges + 3 `file→symbol` intra-repo edges. Assert ZERO self-micro
  `imports` edges appear in the model; assert the 3 intra-repo imports roll
  up to `file→target-micro` correctly (target micro = the target symbol's
  file's micro, NOT the target treated as a nano).
- **`caller_count` excludes `references` (SERIOUS1)** — synthetic fixture: a
  nano with 5 incoming `references` (target type mentions) and 0 incoming
  `calls`/`instantiates`: assert `caller_count = 0` AND the `references`
  still appear in the node's `edges[]` array (Block 4c keeps them as edges;
  they just don't count toward the rank).
- **`instantiates` folds, `implements` drops (SERIOUS2)** — synthetic fixture:
  2 `instantiates` edges + 1 `implements` edge into a class. Assert the 2
  `instantiates` appear as `kind: "calls"` in the model; assert the 1
  `implements` does NOT appear anywhere in the model.
- **First-match wins + multi-match warning** — synthetic config where two
  globs match one path: assert the file lands in the first component AND a
  stderr warning fires.
- **No-config fail-loud** — run `extract` with no `ssot-diagram.config.json`:
  assert exit 1, stderr contains "run `bootstrap-config` first".
- **bootstrap-config --force** — assert a second `bootstrap-config` without
  `--force` exits 1 ("exists — refusing to overwrite"); with `--force` it
  reseeds.

## Risks

- **R1 — Id stability vs P4 narrative pinning.** P3's synthesized `id`
  (`nano:<qualified_name>@<relpath>`) must be stable across edits (Block 4b),
  because P4 narratives pin to `(node_id, signature)` and a renamed path
  would orphan the narrative. Mitigation: the id is built from
  `qualified_name` + `relpath`, neither of which changes on a content edit;
  renames are a real risk but are exactly the events that SHOULD surface as
  orphans (the narrative goes stale, which is the design). Documented in the
  schema. The factual-code-verification step must confirm `qualified_name` +
  `file_path` are stable fields in the codegraph schema (they are columns on
  `nodes`; verified at the live DB).

- **R2 — Edge roll-up cost on large repos.** A micro→micro and component→
  component roll-up over all `calls`/`imports`/`references` edges is O(edges)
  per level. `mkt_engine` has 1124 + 793 + 428 = 2345 edges in those three
  kinds (verified) — trivial. A 10k-edge repo is still sub-second. Mitigation:
  P3 reads edges once into memory, groups by `(source_micro, target_micro)`
  and `(source_component, target_component)`. No DB pass per edge. If a
  future repo is large enough to hurt, the answer is a streaming roll-up,
  not a different shape — deferred (Open Questions OQ-PERF-1).

- **R3 — Multi-match ambiguity in the config globs.** A curator writes two
  globs that both match a path; P3 takes the first. Mitigation: `extract`
  emits a stderr warning listing the path + the conflicting components on
  every multi-match (does not fail — the contract 2 fail-loud is reserved for
  missing config, not ambiguous config). The warning is deterministic (sorted
  by path) so it does not perturb the JSON.

- **R4 — Codegraph schema drift.** P3 reads `nodes`, `files`, `edges` columns
  beyond P1's `verify_schema` minimum (P1 only checks `name, qualified_name,
  file_path, start_line, end_line` + `path, content_hash`). P3 also reads
  `kind, docstring, is_exported, id, source, target, line, metadata`.
  Mitigation: extend the schema guard in `graph_model.py` (a local
  `_verify_model_schema` that calls `di.verify_schema` first, then checks
  P3's extra columns) — fail loud on drift, same posture as P1. Anyone
  changing the codegraph schema must update both P1 and P3 — that is the
  contract Block 1e doc already implies.

- **R5 — Parallel P2/P3 race on the decision index.** The handoff says P2
  (curation) and P3 run in parallel. As of 2026-07-04 the live
  `mkt_engine/docs/decision-index.json` is fully curated (8 ADRs / 33 anchors
  / all verified / all FRESH — see Discoveries), so P3's tests target the
  curated baseline NOW, not the "after P2 lands" future the handoff
  described. Mitigation: the golden model is regenerated only by an explicit
  `--update-golden` action; tests assert against the committed JSON. If P2
  re-curates (drops an anchor, sets `supersedes`), P3's golden is re-recorded
  deliberately. No silent drift.

- **R6 — Anchor owning-micro lookup for `file:<path>` vs `<qname>@<path>`.**
  A `file:<path>` anchor owns the whole file → attaches the decision to that
  file's component. A `<qname>@<path>` anchor owns a symbol inside the file →
  attaches to the symbol's file's component (the symbol is highlighted in the
  micro's `decisions[]`). If a symbol's `qualified_name` is ambiguous across
  files (verified: `requireEnv` exists in 2 files) but the anchor's `ref`
  pins the path, `di.symbol_spans(con, qname, relpath)` returns the right
  span. Mitigation: P3 calls `parse_ref` and uses the path component from
  the ref directly — it does not re-resolve via the bare name (which would
  be ambiguous per Block 1a). Factual-code-verification must confirm
  `parse_ref`'s path handling (it does: `parse_ref('x@p')` →
  `('sym', 'x', 'p')`; verified at decision_index.py:125-133).

- **R7 — `imports` two-shape roll-up (FATAL2).** The `imports` kind contains
  two semantically distinct sub-shapes: 440 `file → import:` same-file
  (external-module placeholders, dropped as self-loops) and 353 `file → symbol`
  (intra-repo real imports, rolled as file→target-micro). Treating them as one
  would either pollute the diagram with self-loops or lose real deps.
  Mitigation: P3 dispatches on the target node's `kind` — `import:` → drop;
  anything else → roll up via target symbol's `file_path`. The dispatch is
  documented in §Edge roll-up and covered by a unit test asserting zero
  self-micro `imports` edges appear AND every intra-repo symbol import does
  appear. If the codegraph later changes the `import:`-node convention, the
  schema guard (R4) catches the column/kind drift, not this rule.

- **R8 — `sample_callers` file-sourced case (FATAL1).** 76% of incoming edges to
  fn/method/class have a `file:` source node (no calling symbol). P3 emits
  `sample_callers: [{file, line}]` — no `symbol` field — and for file-sourced
  edges the `file`/`line` is the import/use site, not a call site. A renderer
  tooltip showing "called from lib/ai/image/index.ts:18" when the edge is
  actually "imported by lib/ai/image/index.ts:18" is technically imprecise.
  Mitigation: P5 (renderer concern) can disambiguate by `kind` — a `calls`
  edge with a file source is a module-level invocation, an `imports` edge with
  a file source is an import statement. P3 carries the truth in `kind`; the
  tooltip wording is the renderer's. Documented here so P5 knows the
  file-sourced case carries no symbol deliberately, not by omission.

## Open Questions

Each is deferred (not blocking the spec write). Factual-code-verification and
the spec step resolve them.

**OQ-ADR-1 — Write an ADR for the "import P1 as sibling, defer `_shared/` to
Phase B" choice? — RESOLVED (post-red-team).**

Right now, P3 imports `decision_index` as a sibling module because
`_shared/` (Block 1) is not yet extracted — only `_shared/design.md` exists
on disk, and the contract schedules the clean cutover as a separate "Phase B"
task.

The question: should this design choice (which is hard to reverse, surprising
without context, and a real trade-off against Option B's isolation) be
recorded as an ADR in `docs/adrs/` (no such directory exists yet — the repo
convention is `docs/roadmap/` + `docs/AI_artifacts/`; an ADR dir would be new)?

**Resolution: YES — write the ADR to `docs/adrs/` as part of P3 deliverables.**
All three ADR gates fire (hard to reverse, surprising without context, real
trade-off), and this is the repo's first ADR — it sets the convention (a new
`docs/adrs/` directory). The ADR is a separate deliverable from the spec; the
coordinator will dispatch it. For the spec writer: P3's deliverables list
includes `docs/adrs/<n>-shared-extraction-deferred.md` (numbering per the
ADR format). The ADR enumerates the exact Phase B `_shared/` consolidation
targets the design already lists: `find_db, open_db, verify_schema,
file_content_hash, symbol_spans, slice_hash, parse_ref, current_sig,
anchor_status, load_index, _evaluate` (the symbols P3 imports from
`decision_index` as a sibling). When Phase B lands, `_shared/db.py` +
`_shared/sig.py` lift these and P1 + the hook + P3 each cut over to import
from `_shared/` (clean cutover per Block 1 note — no back-compat aliases).

**OQ-SCOPE-1 — Should `instantiates` and `implements` edges fold into
`calls`, or be a separate model edge kind? — RESOLVED (post-red-team).**

Right now, contract 6 fixes the model edge `kind ∈ {calls, imports,
references}`. The live `mkt_engine` DB has `instantiates` (17) and
`implements` (5) edges.

**Resolution: FOLD `instantiates` into `calls`; DROP `implements` entirely.**
Red-team evidence (verified against the live DB):
- `implements` = 5 edges, ALL `class → interface` (type relations, not call
  deps). Drop from the model edge set entirely. This is contract-compliant
  (contract 6 freezes {calls, imports, references} — `implements` was never
  in it; dropping is not an amend).
- `instantiates` = 17 edges, `file`/`function → class` (genuine `new X()`
  call-deps, true call-dependencies). Fold into `calls`; emit as
  `kind: "calls"`.

If P5 later wants type relations, that is a deliberate Block 4c amendment
(`implements` reintroduced as a fourth kind), not a P3 concern. Documented as
a roll-up rule in §Edge roll-up.

**OQ-PERF-1 — Streaming edge roll-up for very large repos.**

The current design reads all `calls`/`imports`/`references` edges into
memory and groups them. This is fine for `mkt_engine` (2345 edges) and any
realistic single-repo codebase, but a 100k-edge monorepo would feel it.

**If keep in-memory:** simple, fast enough for any repo P3 will plausibly
target in the near term; risk is latent.

**If stream:** adds complexity (a grouping iterator over the edges table),
delays the simple path; only worth it when a real repo proves it hurts.

Recommendation: keep in-memory now; revisit if/when P3 is pointed at a repo
large enough that `extract` takes > a few seconds. Defer.

**OQ-DISAMBIG-1 — Should `bootstrap-config` seed `cmp-misc` always, or only
when there are unmatched files?**

Right now the design seeds a `cmp-misc` (id stable, `default_component`)
always, named "Other", with a glob that never matches.

**If always:** the renderer always has a bucket to drop unknown paths into,
even if empty; a bit of noise when it is empty.

**If only-when-needed:** cleaner output when every file is matched; but then
`default_component` can be absent and P3 must fail-loud instead of bucket —
loses the unknown-path placement answer.

Recommendation: always seed `cmp-misc`. Defer the "hide empty components in
the renderer" question to P5 (renderer concern, not P3).

## Consumer contracts

What the downstream consumers (P5 renderer, plan-visualizer, P4 narratives)
read from `diagram-model.json` — the seam, not their internals.

- **ssot P5 renderer (`ssot-diagram/render.py`)** — reads the whole
  `diagram-model.json`. Block 4 = its contract. It expects: three levels
  (component → micro → nano) via `children[]` + back-pointers
  (`component_id`, `micro_id`); per-node `edges[]` with `count`
  (`label: "calls ×14"` per `roadmap.md` line 95); decision nodes attached
  at component/micro level with a `status` badge
  (`FRESH|STALE|ORPHANED|superseded`); cross-component edges at the macro
  level, within-component edges only when expanded (`roadmap.md` line 96).
  P5 also reads `generated_at` (null), `nano_cap`, the `collapsed` kind for
  the "+K more" treatment. P5 is not built yet (P5 phase not started) —
  this design nails the seam per Block 4.

- **plan-visualizer** — reads the `<!-- plan-verify -->` manifest (Block 2,
  separate file) + reads one-hop callers from the rolled-up `edges[]` in
  `diagram-model.json` (Block 4c). Specifically: given a `path::symbol`
  manifest entry, it resolves to a model node via the Block 1a resolver
  (honest AMBIGUOUS/UNRESOLVED — Block 4e), then reads that node's
  `edges[]` for `count` + `sample_callers[{file,line}]` (NO `symbol` field —
  FATAL1: 76% of incoming edges have a `file:` source; the plan-visualizer
  never expects a symbol here) WITHOUT opening the DB. P3 therefore ensures
  every nano node carries its rolled-up `edges[]`, and a stable 3-row
  `sample_callers` sorted by `(file, line)` ascending. The plan-visualizer's
  "blast" count = `caller_count` = incoming `calls` + `instantiates` only
  (SERIOUS1: `references` excluded — those are type-mentions, not call deps).

- **narratives worklist (P4 `graph_model.py narrate`)** — keys on
  `(node_id, signature)` (Block 4b + Block 5a). P3's `id` synthesis
  (`nano:<qualified_name>@<relpath>` etc.) is the stable key, and P3's
  `signature` (content hash from `di.slice_hash` / `di.file_content_hash`)
  is the pin P4 compares against. P4 compares a narrative's pinned
  signature to the model node's current `signature` to mark it `stale`
  (Block 5b trust rule — exactly the same compare P1's `anchor_status`
  does for decision anchors).

## Read-set

The files actually surveyed for this design:

- `CLAUDE.md` (repo) — coding patterns, critical rules, build progress.
- `ssot-diagram/roadmap.md` — P0–P8 + P2 (lines 52-76) + P3 (lines 78-117),
  full.
- `../docs/roadmap/skeleton-contracts.md` — Block 1 (esp. 1e sig/db invariants)
  + Block 4 (the frozen `diagram-model.json` surface) + Block 5a/5b, full.
- `ai-artifacts/_handoff/p3-pipeline-state.md` — 6 locked contracts + open
  HOW questions + `mkt_engine` DB reality + refused alternatives, full.
- `ai-artifacts/0_scout/macro-component-grouping-prior-art.md` —
  Structurizr / dependency-cruiser / ArchUnit prior art, full.
- `ssot-diagram/decision_index.py` — full source via codegraph: `find_db`
  (line 53), `repo_root_for` (62), `default_index_path` (67), `open_db` (73),
  `verify_schema` (85), `file_content_hash` (96), `symbol_spans` (101),
  `_sha256` (111), `slice_hash` (115), `parse_ref` (125), `current_sig`
  (136), `anchor_status` (154), `load_index` (163), `save_index` (175),
  `extract_candidates` (191), `resolve_token` (205), `decision_id_for`
  (225), `cmd_bootstrap` (230), `_resolve_db_root_index` (281), `_evaluate`
  (290), `cmd_status` (302), `cmd_check` (317), `cmd_refresh` (334), `die`
  (372), `ok` (364); module docstring + constants `FRESH/STALE/ORPHANED/
  AMBIGUOUS` (line 48), `DEFAULT_DOCS_GLOB` / `DEFAULT_INDEX_REL` (45-46).
- `ssot-diagram/decision_hook.py` — full source (89 lines) via codegraph:
  the hookio pattern (`_emit` line 26, `main` line 35, fail-open
  `try/except BaseException: sys.exit(0)` at line 87-88). Hook form is OUT
  of scope for P3 but the pattern is now in the read-set for P6.
- `impact-analyzer/impact-analyzer.py` — first 120 lines via codegraph: the
  PostToolUse:Read hook output shape (`hookSpecificOutput.
  additionalContext`), `find_codegraph_db` (39), `get_callers` (102) for
  the edges-join pattern P3 references for edge roll-up.
- `manifest.json` — full (32 lines): existing 3 entries (`impact-analyzer`,
  `codegraph-gate`, `decision-index`); shape verified for the new
  `diagram-model` entry.
- `piggyback.py` — `reconcile` (line 288), `ok` / `die` / `warn` / `info`
  helpers (lines 360-392), `self_update` (339), `main` (754) — surveyed only
  for how a tool registers + ships (the manifest shape and reconciler
  intent, not internals).
- `_shared/design.md` — exists; `_shared/*.py` does NOT exist (only
  `design.md` on disk). Confirms Option C is premature.
- **Pilot repo DB (read-only, live):** `~/all-projects/mkt_engine/.codegraph/
  codegraph.db` — schema (nodes/files/edges columns), node-kind and
  edge-kind distributions, top-level dir counts, sample rows, qualified_name
  uniqueness probe, id-format probe. Verified the handoff's DB-reality section
  number-for-number (150 files, 1115 nodes, the 8 top-level dirs, the node-
  kind and edge-kind counts) — except the decision-index state, which has
  moved on (see Discoveries in the dispatching summary).
- **Pilot repo index (read-only, live):** `~/all-projects/mkt_engine/docs/
  decision-index.json` — 8 ADRs, 33 anchors, all `verified:true`. Ran
  `decision_index status` against the live DB: 33/33 FRESH, 0 not-fresh.
- **Red-team verification query (read-only, 2026-07-04 post-red-team):** one
  script querying `~/all-projects/mkt_engine/.codegraph/codegraph.db`
  (`mode=ro&immutable=1`) confirming all 5 fixes' evidence: (FATAL1) 831/1124
  `calls` edges have `file:` source; 689/902 incoming calls+references to
  fn/method/class have `file:` source (76%). (FATAL2) imports target dist:
  `import:` 440 + real symbols 353; all 440 `file → import:` edges are
  same-file. (SERIOUS1) `references` target dist: 348 `interface`, 77
  `type_alias`, 3 `function`. (SERIOUS2) `implements` = 5 `class→interface`;
  `instantiates` = 17 `file/function→class`. (NOTE) 82 of 252 fn/method
  nanos (33%) have zero incoming calls+instantiates. All five confirmed
  before the edits below were applied.

## Assumptions to verify

Factual claims about the code that factual-code-verification must check. Each:
claim + file:line + why it matters.

1. **`nodes.id` is content-derived, not path-derived.** Claim: codegraph node
   ids are `<kind>:<hex>` where the hex is unrelated to the path (samples:
   `function:1160d09796260bc002cfa4023f655680`, `file:app/api/auth/logout/
   route.ts`). File: live DB query (rows returned above). Why it matters: if
   P3 passed `nodes.id` through as the model `id`, a one-line edit would
   change the id and orphan every P4 narrative pinned to it — violating
   Block 4b. P3 synthesizes its own id; this claim must be confirmed so the
   spec writer knows NOT to use `nodes.id`.

2. **`nodes.signature` is the CODE signature, NOT a content hash.** Claim: the
   `signature` column on `nodes` holds type-signature text like
   `(request: Request): Promise<NextResponse>`, NOT the sha256 content hash
   Block 4b requires. File: `decision_index.py:96-97` (`file_content_hash`
   reads from `files.content_hash`, NOT `nodes.signature`) + live DB sample
   rows. Why it matters: P3's model `signature` field MUST come from
   `di.file_content_hash` / `di.slice_hash`, never from `nodes.signature`
   — a confusion here would break the Block 5b trust rule silently.

3. **`qualified_name` is NOT unique across the repo.** Claim: the same
   `qualified_name` can appear in multiple files (verified: `requireEnv` in
   both `lib/ai/llm/providers/openai-compat/index.ts` and `lib/storage/s3.ts`).
   File: live DB query. Why it matters: P3's micro / nano id synthesis uses
   `<qualified_name>@<relpath>` precisely because `qualified_name` alone is
   ambiguous; `di.symbol_spans` queries by `(qualified_name, file_path)` for
   the same reason (`decision_index.py:101-105`).

4. **`parse_ref` returns `('sym', qname, relpath)` for `<qname>@<path>`
   refs.** Claim: `parse_ref('CapabilitySlot::listModels@lib/ai/image/
   index.ts')` returns `('sym', 'CapabilitySlot::listModels',
   'lib/ai/image/index.ts')`. File: `decision_index.py:125-133`. Why it
   matters: the decision-node merge relies on extracting the path from each
   anchor's ref to find the owning micro; if `parse_ref` did something else
   (e.g. re-resolve via the bare name), the merge would be wrong.

5. **`anchor_status` returns `FRESH | STALE | ORPHANED | AMBIGUOUS`.** Claim:
   the status vocabulary is exactly these four, via `current_sig`'s `(state,
   sig)` tuple. File: `decision_index.py:136-158` (`current_sig` returns OK /
   ORPHANED / AMBIGUOUS; `anchor_status` maps OK → FRESH or STALE). Why it
   matters: the decision-node badge must use this exact vocabulary per Block
   4d; P3's "worst-case across anchors" reduce must operate on these.

6. **`save_index` writes `json.dumps(doc, indent=2) + "\n"` (no sort_keys).**
   Claim: P1's writer does NOT sort keys. File: `decision_index.py:175-178`.
   Why it matters: P3's determinism needs `sort_keys=True` (a stricter
   choice than P1 made — P1's index is human-curated so order is stable by
   curation; P3's model is machine-emitted from a dict iteration so it MUST
   sort). The spec writer must NOT copy P1's writer verbatim; P3 uses
   `sort_keys=True`.

7. **`cmd_bootstrap`'s `--force` gate exists and refuses overwrite by
   default.** Claim: `bootstrap` exits 1 if the output exists and `--force`
   is not passed, with the message "exists — refusing to overwrite a curated
   index." File: `decision_index.py:236-237`. Why it matters: P3's
   `bootstrap-config` mirrors this exact contract (contract 2 re-seed =
   `bootstrap-config --force`); the spec must copy the gate, not invent a
   new one.

8. **`_evaluate` walks anchors and returns `(rows, n_not_fresh)` where each
   row is `(did, ref, state)`.** Claim: P1's `_evaluate` is the helper the
   pre-extract guard can reuse to find not-FRESH anchors. File:
   `decision_index.py:290-300`. Why it matters: P3's pre-extract guard
   (contract 5) should call `di._evaluate` (or replicate it) rather than
   re-walk; confirms the guard is one helper call, not a new walk. Note the
   leading underscore — P3 reaches across a "private" boundary; this is
   acceptable because P3 imports `decision_index` as a sibling (the same
   thing `decision_hook.py` does at line 64).

9. **`mkt_engine/docs/decision-index.json` is fully curated (8 ADRs / 33
   anchors / all `verified:true` / all FRESH) as of 2026-07-04.** Claim: the
   handoff file (line 110-115) describes a "pre-P2" state ("0/25 verified, 4
   STALE in ADR-0007"); the LIVE index has moved on. File: live
   `decision-index.json` + `decision_index status` output (above). Why it
   matters: P3's tests target the curated baseline NOW; the "every verified
   anchor appears once" assertion (Roadmap exit criterion) can be exercised
   immediately, not "after P2 lands." The handoff's parallel-P2 framing is
   stale; P3 ships against the curated index.

10. **`fnmatch` with forward-slash repo-relative paths is the right matcher
    for the config globs.** Claim: `mkt_engine` file paths use forward
    slashes throughout (verified: every `file_path` in samples), so
    `fnmatch.fnmatch(relpath, glob)` works without OS-separator dance. File:
    live DB query + `decision_index.py` (P1 uses raw `file_path` / `path`
    strings everywhere, no `os.sep`). Why it matters: the config schema's
    `glob` field is `fnmatch`-style; the spec writer must NOT use
    `pathlib.match` (Python 3.12+) without confirming the target Python
    version — `fnmatch` is stdlib and works on 3.x.

11. **`edges.source` / `edges.target` reference `nodes.id` (the content-hash
    id), not the path-derived id.** Claim: P3 must join `edges` to `nodes` on
    `nodes.id` to recover source/target file paths for the roll-up. File:
    live DB sample rows (`edges.source = 'function:1160d09796260bc002cfa4023f655680'`).
    Why it matters: P3's edge roll-up reads `edges`, joins both ends to
    `nodes` (to get `file_path` + `qualified_name`), then rolls up by
    component / micro. The join key is the codegraph id, NOT the model id —
    the spec must be explicit about this two-id reality (codegraph id for
    DB joins; model id for the emitted JSON).

12. **The repo has no `docs/adrs/` directory yet.** Claim: there is no
    `docs/adrs/` or `docs/architecture/` directory; ADR convention is
    undeclared. File: `ls docs/` (returned `AI_artifacts INSTALL-simple.md
    hook.md roadmap`). Why it matters: OQ-ADR-1's recommendation to write an
    ADR would CREATE the convention; the spec writer should flag this to the
    human rather than silently inventing a path.

13. **FATAL1 — most `calls` edges have a `file:` source node with no calling
    symbol.** Claim: 831 of 1124 `calls` edges have `source LIKE 'file:%'`; 689
    of 902 incoming calls+references to fn/method/class have a `file:` source
    (76%). File: live DB query (§Read-set "Red-team verification query"). Why
    it matters: a `symbol` field on `sample_callers` is unimplementable for
    these — P3 emits `sample_callers: [{file, line}]` (no symbol), and for
    file-sourced edges `file`/`line` is the import/use site, not a call site
    (see R8). Block 4c only requires `sample_callers[file:line ×3]` — no
    `symbol` — so this is contract-compliant, not an amend.

14. **FATAL2 — `imports` has two semantically distinct sub-shapes.** Claim:
    440 of 793 `imports` edges target an `import:` placeholder node (all 440
    are same-file — `source.file_path == import:.file_path`); 353 target a
    real symbol (function 151, interface 113, constant 49, type_alias 24,
    class 12, file 4). File: live DB query. Why it matters: the two sub-shapes
    must NOT roll together — (a) is a self-micro no-op (drop as self-loops,
    never cross-component), (b) is a real intra-repo import (roll as
    file→target-symbol's-owning-micro). Treating them as one would either
    pollute the diagram with self-loops or lose real deps.

15. **SERIOUS1 — `references` are type-mentions, not call deps.** Claim: 348
    of 428 `references` target `interface`, 77 `type_alias`, only 3 target
    `function` (99% are type-references). File: live DB query. Why it matters:
    `references` must stay in the rolled `edges[]` array (Block 4c includes
    it) but is EXCLUDED from `caller_count` (the nano-cap rank key, contract
    3) — folding them in would rank functions by signature-type mentions.
    Contract 3's "by caller count" wording is ambiguous; P3 pins it to
    `calls` + `instantiates` incoming only, contract-compliant (the grill
    fixes the cap, not the rank-key set).

16. **SERIOUS2 — `implements` are type relations, `instantiates` are call deps.**
    Claim: `implements` = 5 edges, ALL `class → interface` (type relations);
    `instantiates` = 17 edges, `file`/`function → class` (genuine `new X()`
    call-deps). File: live DB query. Why it matters: `instantiates` FOLDS into
    `calls` (emitted as `kind: "calls"`); `implements` is DROPPED entirely
    (contract 6 freezes {calls, imports, references} — `implements` was never
    in it, so dropping is contract-compliant, not an amend). If P5 later wants
    type relations, that is a deliberate Block 4c amendment, not P3.

17. **NOTE — nano-cap `caller_count` ties need a deterministic secondary sort.**
    Claim: 82 of 252 fn/method nanos (33%) have ZERO incoming
    `calls`+`instantiates` edges; ties at zero (and elsewhere) are common.
    File: live DB query. Why it matters: without a secondary sort, the cap
    selection is non-deterministic across runs (Python set/dict order). P3's
    sort is: primary `caller_count` DESC, secondary `qualified_name` ASC,
    tertiary `path` ASC. The spec must pin this exact sort or the "byte-
    identical JSON" exit criterion (Roadmap line 113) fails.

## Red-team revision (2026-07-04)

Adversarial red-team landed 2 FATAL + 2 SERIOUS + 1 NOTE against the §Chosen
Approach `diagram-model.json` field-shape schema. The chosen Option A (sibling
import of `decision_index`) SURVIVES — these are TYPE-B fixes
(execution-detail, Block 4 contract-compliant). No re-litigation of Option
A/B/C or the 6 grill contracts. All 5 fixes were re-verified against the live
`mkt_engine` DB read-only before the edits were applied (one query, evidence
in §Read-set "Red-team verification query" + §Assumptions to verify #13-17).

**Changes applied to this doc:**

1. **FATAL1 — dropped `symbol` from `sample_callers`.** The example payload's
   component-level `sample_callers` entry no longer carries `symbol`; the
   `edges[]` field justification + contract 6 statement + §Edge roll-up
   `calls` roll-up + §Consumer contracts (plan-visualizer) all updated to
   `sample_callers: [{file, line}]`. Live-DB evidence: 831/1124 `calls` edges
   have a `file:` source (76% of incoming to fn/method/class). Documented the
   file-sourced case (R8). New test: `Sample_callers shape (FATAL1)`.

2. **FATAL2 — split `imports` roll-up into two sub-shapes.** §Edge roll-up
   rewritten with a dedicated `imports` roll-up subsection: (a) 440
   `file → import:` same-file edges DROP as self-loops (external-module
   placeholders, never cross-component); (b) 353 `file → symbol` intra-repo
   edges roll as `file → target-symbol's-owning-micro`. The old "aggregate
   nano→nano where source and target live in different micros" rule was wrong
   for imports. New test: `imports two-shape roll-up (FATAL2)`. New risk R7.

3. **SERIOUS1 — pinned `caller_count` = incoming `calls` + `instantiates`
   only.** The `caller_count` field justification, contract 3 statement, and
   §Consumer contracts all updated. Live-DB evidence: 348 of 428 `references`
   target `interface`, only 3 target `function`. New test:
   `caller_count excludes references (SERIOUS1)`.

4. **SERIOUS2 — fold `instantiates` into `calls`, drop `implements` entirely.**
   §Edge roll-up `calls` subsection + contract 6 statement updated.
   Live-DB evidence: `implements` = 5 `class→interface` (type relations);
   `instantiates` = 17 `file/function→class` (call deps). OQ-SCOPE-1 marked
   RESOLVED. New test: `instantiates folds, implements drops (SERIOUS2)`.

5. **NOTE — nano-cap `caller_count` tiebreak.** New §Nano-cap selection
   subsection pins the deterministic sort: primary `caller_count` DESC,
   secondary `qualified_name` ASC, tertiary `path` ASC. Live-DB evidence: 82
   of 252 fn/method nanos (33%) have zero incoming calls+instantiates. New
   assumption #17. The Nano-cap test was extended to assert the secondary
   sort at the zero-caller tie.

**OQ resolutions:**

- **OQ-ADR-1 — RESOLVED: YES, write the ADR.** Will be dispatched separately
  (not written in this design step). The ADR enumerates the exact Phase B
  `_shared/` consolidation targets: `find_db, open_db, verify_schema,
  file_content_hash, symbol_spans, slice_hash, parse_ref, current_sig,
  anchor_status, load_index, _evaluate`. P3 deliverables list now includes
  `docs/adrs/<n>-shared-extraction-deferred.md`.
- **OQ-SCOPE-1 — RESOLVED:** fold `instantiates` into `calls`, drop
  `implements` (see fix 4 above).
- **OQ-PERF-1 — unchanged:** keep in-memory roll-up, defer streaming.
- **OQ-DISAMBIG-1 — unchanged:** always seed `cmp-misc`.

**Other updates:** §Summary's edge-encoding line + revision banner at top;
§Constraints contract 3 (nano-cap rank pinned) + contract 6 (sample_callers
shape, instantiates/implements posture); §Determinism (collapsed members
sort pinned); §Risks R7 + R8 added; §Read-set red-team query logged; 5 new
§Assumptions to verify rows (#13-17) for factual-code-verification.
