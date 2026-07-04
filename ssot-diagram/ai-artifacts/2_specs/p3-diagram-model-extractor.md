# Phase 3 — Diagram Model Extractor (`diagram-model.json`)

> **Spec source:** decomposed from `ai-artifacts/1_design/p3-diagram-model-extractor.md`
> (Revision 2, post-red-team 2026-07-04) and ADR
> `adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`.
> The design's Option A (sibling import of P1) is FROZEN; the 6 grill contracts
> are FROZEN; the 5 red-team fixes (assumptions A13-A17) are FROZEN and
> load-bearing for research. This spec carries the design's `## Assumptions to
> verify` (#1-17) forward verbatim as assumption rows A1-A17 (a FLOOR, not a
> ceiling); new assumptions introduced by decomposition are A18+.

## Purpose

P3 builds the deterministic heart of the ssot-diagram pipeline: one script
(`ssot-diagram/graph_model.py`) that turns the codegraph SQLite database plus
the curated decision index into a single `diagram-model.json` file. After this
phase, the system can produce — in one command, with no LLM, with byte-identical
output across runs — a three-level map of a repo (macro components → micro
files/classes → nano functions) with rolled-up dependency edges, decision (ADR)
status badges, and content signatures pinned to every node. This file is the
only input the future renderer (P5) and the plan-visualizer will read; P3 makes
the diagram's substrate truthful and reproducible before any rendering or
narrative work begins.

## Already built (reuse, do not rebuild)

P3 reuses the already-shipped P1 engine (`ssot-diagram/decision_index.py`) as a
sibling module via the established `decision_hook.py` precedent. The
`_shared/` library does NOT exist yet (only `_shared/design.md`); the Block 1
clean-cutover extraction is a separate "Phase B" task per ADR 0001. Every item
below is a load-bearing P1 symbol P3 imports rather than reimplements.

| Function/Module | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| `find_db` | `ssot-diagram/decision_index.py:53` | Walk up from a start dir to locate `.codegraph/codegraph.db` | Both subcommands locate the DB | deep |
| `repo_root_for` | `decision_index.py:62` | Indexed repo root = parent of `.codegraph/` | Derive the repo-relative root for paths + `slice_hash` | deep |
| `default_index_path` | `decision_index.py:67` | Default path to `docs/decision-index.json` | Default `--index` argument | deep |
| `open_db` | `decision_index.py:73` | Read-only SQLite connect (`mode=ro&immutable=1`) + schema guard | Open the codegraph DB without writing | deep |
| `verify_schema` | `decision_index.py:85` | Fail-loud guard checking `nodes`/`files` have required columns | P3 extends this with extra columns it reads (see component 4) | deep |
| `file_content_hash` | `decision_index.py:96` | File content hash from `files.content_hash` | Micro (file-dominant) node `signature` | deep |
| `symbol_spans` | `decision_index.py:101` | `(start_line, end_line)` for a `(qualified_name, file_path)` lookup | Nano span lookup (qualified_name alone is ambiguous — A3) | deep |
| `_sha256` | `decision_index.py:111` | sha256 hex of UTF-8 text | Used by `slice_hash`; P3 may call for component/collapsed/decision hashes | deep |
| `slice_hash` | `decision_index.py:115` | sha256 of a symbol's source slice `[start,end]` 1-based inclusive | Nano + class-dominant micro `signature` | deep |
| `parse_ref` | `decision_index.py:125` | Split an anchor ref into `('file', path)` or `('sym', qname, path)` | Decision-node merge: extract owning path from each anchor ref | deep |
| `current_sig` | `decision_index.py:136` | Live `(state, sig)` for a ref: `OK`/`ORPHANED`/`AMBIGUOUS` | Decision-node badge computation | deep |
| `anchor_status` | `decision_index.py:154` | `FRESH`/`STALE`/`ORPHANED`/`AMBIGUOUS` per anchor | Decision-node badge (worst-case across anchors) | deep |
| `load_index` | `decision_index.py:163` | Fail-loud JSON loader for the decision index (`decisions` key required) | Pre-extract guard + decision merge load the index | deep |
| `save_index` | `decision_index.py:175` | P1's JSON writer (`indent=2`, NO `sort_keys`) | NOT copied verbatim — P3's writer is stricter (A6, component 12) | deep |
| `_evaluate` | `decision_index.py:290` | Walk all anchors; return `((did, ref, state) rows, n_not_fresh)` | Pre-extract guard finds not-FRESH anchors via this helper | deep |
| `cmd_bootstrap` | `decision_index.py:230` | P1's seed-then-curate `bootstrap` command; `--force` gate at line 236 | The contract P3's `bootstrap-config` mirrors (A7) | deep |
| `decision_hook.py` | `ssot-diagram/decision_hook.py:22-23` | Established sibling-import pattern: `sys.path.insert(0, str(Path(__file__).resolve().parent)); import decision_index as di` | P3 mirrors this exact import verbatim | deep |
| `manifest.json` | repo root | SSOT of shippable scripts (3 entries today: `impact-analyzer`, `codegraph-gate`, `decision-index`) | P3 adds one `diagram-model` entry (component 13) | — |

The pilot decision index at `~/all-projects/mkt_engine/docs/decision-index.json`
is fully curated (8 ADRs, 33 anchors, all `verified:true`, all FRESH as of
2026-07-04 — A9); it is a read-only input. P3 never writes it.

## Feature overview

The extractor reads three inputs and writes one output:

- **Inputs:** (1) the codegraph SQLite DB (read-only, `mode=ro&immutable=1`);
  (2) the curated `docs/decision-index.json` (P1's output);
  (3) a curated `ssot-diagram.config.json` (glob → component-name map).
- **Output:** one `diagram-model.json` whose bytes are identical across runs
  given identical inputs.

**Happy path (the `extract` command):** The script locates the DB, opens it
read-only, and runs an extended schema guard (P1's guard plus P3's extra
columns). It loads the config (fail-loud if absent: "run `bootstrap-config`
first") and the decision index (fail-loud on bad JSON via P1's `load_index`).
A pre-extract guard walks the index: if any anchor is `verified:false` or any
anchor status is not FRESH, it prints a stderr warning pointing at
`decision_index refresh <id>` and continues (exit 0) — P3 stays parallel-runnable
with ongoing curation. The script then groups every indexed file into a
component by walking the config's glob list (first match wins; unmatched files
fall into `cmp-misc`). For each micro (file, or the single dominant class when
a file is one class) it selects the nano functions/methods inside, capped at N
(default 8) by caller count (ties broken deterministically). It rolls up the
codegraph `edges` table into per-node edge lists with counts and a stable
3-row `sample_callers[file:line]` (no `symbol` field — A13). It merges verified
decision anchors into `decision:<ADR-ID>@<component-id>` nodes with a live
FRESH/STALE/ORPHANED/superseded badge. It synthesizes path-derived ids for
every node (never passing codegraph's content-derived `nodes.id` through — A1,
A11). It serializes the whole model with sorted keys, fixed indentation, and a
trailing newline (byte-deterministic).

**Happy path (the `bootstrap-config` command):** When no config exists, the
human runs `bootstrap-config`, which scans the top-level directories of indexed
files, writes one component per dir (glob `<dir>/**`), always seeds a `cmp-misc`
default, and refuses to overwrite a curated config without `--force` (mirrors
P1's `bootstrap`).

**Edge cases handled explicitly:** unmatched file paths (→ `cmp-misc`); a glob
matching multiple components (first wins + a stderr warning); a function name
that exists in multiple files (disambiguated by `qualified_name@path` id); a
file that holds exactly one dominant class (micro = the class); more nanos than
the cap (excess collapse into one `+K more` node); an anchor whose symbol has
been deleted (ORPHANED badge, decision node still emitted if at least one
anchor is verified); a decision that supersedes another (status `superseded`);
an unverified anchor (no decision node); the codegraph `imports` kind's two
distinct sub-shapes (placeholder `import:` nodes dropped as self-loops; real
intra-repo imports rolled up — A14); the codegraph `references` kind
(type-mentions, kept as edges but excluded from the nano-cap rank — A15);
`instantiates` (folded into `calls`) and `implements` (dropped — A16).

## Out of scope

- **The read-hook form (PostToolUse re-extract on codegraph re-index)** — P3
  ships CLI-first; hook wiring is P6. P3 registers `hooks: []` in the manifest.
  [P6]
- **The interactive HTML renderer** — P5 reads `diagram-model.json` but P3 does
  not render. [P5]
- **Narrative sidecar** (`narratives.json` / `graph_model.py narrate`) — P4
  layers inference over P3's deterministic substrate; P3 emits nothing
  narrative. [P4]
- **The `_shared/` extraction (Block 1 clean cutover)** — explicitly deferred to
  Phase B per ADR 0001. P3 imports P1 as a sibling in the meantime. [Phase B]
- **Auto-deriving component names from path prefixes** — refused in the grill;
  explicit glob → name is the safer subset for a non-SWE owner. [deferred]
- **Streaming edge roll-up for very large repos** — in-memory roll-up is fine
  for the pilot (2345 edges in the relevant kinds); revisit if a real repo
  proves slow. [OQ-PERF-1, deferred]
- **`$1` capture-group globs** — refused in the scout (fragile on multi-match).
  [deferred]
- **External-module `import:` node bucketing as a separate edge set** — P5 may
  want external-dep arrows later; P3 drops placeholder `import:` nodes as
  self-loops to keep the model clean. [P5]
- **Renderer-side tooltip wording** for the file-sourced `sample_callers` case
  (an `imports` edge with a `file:` source is an import statement, not a call
  site) — P3 carries the truth in `kind`; the tooltip is the renderer's. [P5]

## Constraints

Non-negotiable rules from CLAUDE.md, the FROZEN contracts, and the design.

- **Read-only DB, always** — connect `mode=ro&immutable=1`; never write
  `.codegraph/codegraph.db`. Derived state lives in tool-owned files
  (`diagram-model.json`). Source: CLAUDE.md Critical Rules; skeleton-contracts
  Block 1e.
- **Every persisted artifact pinned to a content signature** — every model node
  carries a `signature` from P1's recipe (file → `files.content_hash`;
  symbol → `slice_hash`; component → sha256 over member hashes). This is what P4
  narratives pin to. Source: CLAUDE.md Critical Rules; Block 5b.
- **Every tool registers in `manifest.json`** — a script not in the manifest
  does not ship. P3 adds one `diagram-model` entry. Source: CLAUDE.md Critical
  Rules.
- **CLIs run standalone** (CI + manual use), not only as hooks. Source:
  CLAUDE.md Critical Rules.
- **No LLM in any verdict** — every field is a pure computation over the DB.
  Source: CLAUDE.md Coding Patterns; Block 1e.
- **`_shared/` extraction happens when the second consumer appears, not
  speculatively** — but it has NOT happened yet (only `_shared/design.md` exists
  on disk); ADR 0001 confirms P3 imports P1 as a sibling and defers the clean
  cutover to Phase B. Source: CLAUDE.md Coding Patterns; ADR 0001.
- **C1 (pilot = `mkt_engine`)** — extractor lives in this repo; tests + golden
  model target `~/all-projects/mkt_engine`. The live index is fully curated as
  of 2026-07-04 (A9). Source: design §Constraints contract 1.
- **C2 (no-config `extract` = fail-loud)** — exits 1 with "run `bootstrap-config`
  first" when `ssot-diagram.config.json` is absent. Two clean contracts:
  `bootstrap-config` seeds+writes; `extract` reads+emits. `extract` NEVER
  re-seeds the config. Source: design §Constraints contract 2.
- **C3 (nano cap = top N by caller count; default 8)** — the rest collapse into
  one synthetic `kind=collapsed` node; honest about dropped symbols. Rank key
  pinned to incoming `calls` + `instantiates` only (NOT `references` — A15);
  ties broken by `qualified_name` ASC then `path` ASC (A17). Source: design
  §Constraints contract 3.
- **C4 (multi-anchor decision = attach to every component owning ≥1 verified
  anchor)** — id `decision:<ADR-ID>@<component-id>`; one underlying decision,
  one consistent status badge across attachments. No phantom cross-cutting
  component. Source: design §Constraints contract 4; Block 4a/4d.
- **C5 (pre-extract guard = warn-and-continue)** — if the index has
  `verified:false` OR any not-FRESH anchor, print a stderr warning pointing at
  `decision_index refresh <id>`, exit 0. Model still produced and still
  truthful (unverified → no decision node; not-FRESH → decision node with the
  worst-case badge). Source: design §Constraints contract 5.
- **C6 (edge encoding = per-node `edges[]`)** —
  `{source, target, kind, count, sample_callers[{file,line} ×3]}` (NO `symbol`
  field — A13). Directional (source→target = source depends on target).
  `kind ∈ {calls, imports, references}` exactly; `instantiates` folds into
  `calls`, `implements` is dropped (A16). `sample_callers` top 3 with a STABLE
  tiebreak (call-site `(file, line)` ascending). Source: design §Constraints
  contract 6; Block 4c.
- **Byte-determinism** — same DB + same index + same config ⇒ byte-identical
  JSON. `json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`.
  `generated_at` always null. No `set()` iteration order leaks; sort
  explicitly everywhere. Stricter than P1's `save_index` (A6). Source: design
  §Determinism; roadmap.md exit criterion.
- **Id synthesis never passes `nodes.id` through** — the codegraph internal id
  is content-derived (`<kind>:<hex>`, A1) and changes per edit; P3 synthesizes
  path-derived ids so P4 narrative pinning survives edits (A1, A11). Source:
  Block 4b.
- **Two-id reality** — `edges.source`/`edges.target` reference `nodes.id`
  (content-derived); P3 joins `edges` to `nodes` on `nodes.id` to recover
  `file_path` + `qualified_name` for the roll-up. The model `id` is
  path-derived and is NOT a DB join key (A11).
- **Block 4b FROZEN node fields** — every node carries `id`, `kind`, `name`,
  `path`, `signature`. Source: skeleton-contracts Block 4b.

## Assumptions

Carried forward verbatim from the design's `## Assumptions to verify` (#1-17)
as the FLOOR; new assumptions introduced by decomposition are A18+. Each is a
falsifiable claim — research (`/factual-code-verification`) verifies it.

| ID | Assumption | Source | What would prove it wrong |
|----|-----------|--------|--------------------------|
| A1 | `nodes.id` is content-derived, not path-derived. Claim: codegraph node ids are `<kind>:<hex>` where the hex is unrelated to the path (samples: `function:1160d09796260bc002cfa4023f655680`, `file:app/api/auth/logout/route.ts`). File: live DB query. Why it matters: if P3 passed `nodes.id` through as the model `id`, a one-line edit would change the id and orphan every P4 narrative pinned to it — violating Block 4b. P3 synthesizes its own id; this claim must be confirmed so the spec writer knows NOT to use `nodes.id`. | design impl #1 | A codegraph build where `nodes.id` is path-derived or stable across content edits would invalidate the "synthesize your own id" requirement. |
| A2 | `nodes.signature` is the CODE signature, NOT a content hash. Claim: the `signature` column on `nodes` holds type-signature text like `(request: Request): Promise<NextResponse>`, NOT the sha256 content hash Block 4b requires. File: `decision_index.py:96-97` (`file_content_hash` reads from `files.content_hash`, NOT `nodes.signature`) + live DB sample rows. Why it matters: P3's model `signature` field MUST come from `di.file_content_hash` / `di.slice_hash`, never from `nodes.signature` — a confusion here would break the Block 5b trust rule silently. | design impl #2 | A `nodes.signature` value that is a sha256 content hash (matching `files.content_hash` for a file node) would mean P3 could read it directly; the "use slice_hash" rule would be wrong. |
| A3 | `qualified_name` is NOT unique across the repo. Claim: the same `qualified_name` can appear in multiple files (verified: `requireEnv` in both `lib/ai/llm/providers/openai-compat/index.ts` and `lib/storage/s3.ts`). File: live DB query. Why it matters: P3's micro / nano id synthesis uses `<qualified_name>@<relpath>` precisely because `qualified_name` alone is ambiguous; `di.symbol_spans` queries by `(qualified_name, file_path)` for the same reason (`decision_index.py:101-105`). | design impl #3 | A DB where every `qualified_name` is repo-unique would let P3 use the bare name; the `@<relpath>` disambiguation would be unnecessary. |
| A4 | `parse_ref` returns `('sym', qname, relpath)` for `<qname>@<path>` refs. Claim: `parse_ref('CapabilitySlot::listModels@lib/ai/image/index.ts')` returns `('sym', 'CapabilitySlot::listModels', 'lib/ai/image/index.ts')`. File: `decision_index.py:125-133`. Why it matters: the decision-node merge relies on extracting the path from each anchor's ref to find the owning micro; if `parse_ref` did something else (e.g. re-resolve via the bare name), the merge would be wrong. | design impl #4 | `parse_ref` returning a different tuple shape or re-resolving via the bare name would break the merge's path component extraction. |
| A5 | `anchor_status` returns `FRESH \| STALE \| ORPHANED \| AMBIGUOUS`. Claim: the status vocabulary is exactly these four, via `current_sig`'s `(state, sig)` tuple. File: `decision_index.py:136-158` (`current_sig` returns OK / ORPHANED / AMBIGUOUS; `anchor_status` maps OK → FRESH or STALE). Why it matters: the decision-node badge must use this exact vocabulary per Block 4d; P3's "worst-case across anchors" reduce must operate on these. | design impl #5 | A different vocabulary (e.g. an added `SUPERSEDED` state from `anchor_status`) would change P3's reduce and its badge emission. |
| A6 | `save_index` writes `json.dumps(doc, indent=2) + "\n"` (no sort_keys). Claim: P1's writer does NOT sort keys. File: `decision_index.py:175-178`. Why it matters: P3's determinism needs `sort_keys=True` (a stricter choice than P1 made — P1's index is human-curated so order is stable by curation; P3's model is machine-emitted from a dict iteration so it MUST sort). The spec writer must NOT copy P1's writer verbatim; P3 uses `sort_keys=True`. | design impl #6 | P1 already sorting keys would make P3's stricter choice redundant; the "use sort_keys=True" rule would be wrong. |
| A7 | `cmd_bootstrap`'s `--force` gate exists and refuses overwrite by default. Claim: `bootstrap` exits 1 if the output exists and `--force` is not passed, with the message "exists — refusing to overwrite a curated index." File: `decision_index.py:236-237`. Why it matters: P3's `bootstrap-config` mirrors this exact contract (contract 2 re-seed = `bootstrap-config --force`); the spec must copy the gate, not invent a new one. | design impl #7 | The gate message or exit code differing would mean P3's mirror must use P1's exact shape, not a new one. |
| A8 | `_evaluate` walks anchors and returns `(rows, n_not_fresh)` where each row is `(did, ref, state)`. Claim: P1's `_evaluate` is the helper the pre-extract guard can reuse to find not-FRESH anchors. File: `decision_index.py:290-300`. Why it matters: P3's pre-extract guard (contract 5) should call `di._evaluate` (or replicate it) rather than re-walk; confirms the guard is one helper call, not a new walk. Note the leading underscore — P3 reaches across a "private" boundary; this is acceptable because P3 imports `decision_index` as a sibling (the same thing `decision_hook.py` does at line 64). | design impl #8 | A different return shape (e.g. no `n_not_fresh`, or rows without `state`) would force P3 to re-walk anchors itself. |
| A9 | `mkt_engine/docs/decision-index.json` is fully curated (8 ADRs / 33 anchors / all `verified:true` / all FRESH) as of 2026-07-04. Claim: the handoff file describes a "pre-P2" state ("0/25 verified, 4 STALE in ADR-0007"); the LIVE index has moved on. File: live `decision-index.json` + `decision_index status` output. Why it matters: P3's tests target the curated baseline NOW; the "every verified anchor appears once" assertion (Roadmap exit criterion) can be exercised immediately, not "after P2 lands." The handoff's parallel-P2 framing is stale; P3 ships against the curated index. | design impl #9 | The live index regressing to unverified/STALE anchors would force P3's golden test to record a different baseline. |
| A10 | `fnmatch` with forward-slash repo-relative paths is the right matcher for the config globs. Claim: `mkt_engine` file paths use forward slashes throughout (verified: every `file_path` in samples), so `fnmatch.fnmatch(relpath, glob)` works without OS-separator dance. File: live DB query + `decision_index.py` (P1 uses raw `file_path` / `path` strings everywhere, no `os.sep`). Why it matters: the config schema's `glob` field is `fnmatch`-style; the spec writer must NOT use `pathlib.match` (Python 3.12+) without confirming the target Python version — `fnmatch` is stdlib and works on 3.x. | design impl #10 | Repo paths using OS separators on Windows-codegraph builds would require a separator-normalization step before `fnmatch`. |
| A11 | `edges.source` / `edges.target` reference `nodes.id` (the content-hash id), not the path-derived id. Claim: P3 must join `edges` to `nodes` on `nodes.id` to recover source/target file paths for the roll-up. File: live DB sample rows (`edges.source = 'function:1160d09796260bc002cfa4023f655680'`). Why it matters: P3's edge roll-up reads `edges`, joins both ends to `nodes` (to get `file_path` + `qualified_name`), then rolls up by component / micro. The join key is the codegraph id, NOT the model id — the spec must be explicit about this two-id reality (codegraph id for DB joins; model id for the emitted JSON). | design impl #11 | `edges.source`/`target` referencing a path-derived column would let P3 skip the `nodes` join; the "two-id reality" rule would be wrong. |
| A12 | The repo has no `docs/adrs/` directory yet (at design time). Claim: there is no `docs/adrs/` or `docs/architecture/` directory; ADR convention is undeclared. File: `ls docs/`. Why it matters: OQ-ADR-1's recommendation to write an ADR would CREATE the convention; the spec writer should flag this to the human rather than silently inventing a path. | design impl #12 | An existing `docs/adrs/` convention (now present — ADR 0001 already written) means P3's deliverables list includes a numbered ADR under the existing convention, not a new one. |
| A13 | **FATAL1** — most `calls` edges have a `file:` source node with no calling symbol. Claim: 831 of 1124 `calls` edges have `source LIKE 'file:%'`; 689 of 902 incoming calls+references to fn/method/class have a `file:` source (76%). File: live DB query. Why it matters: a `symbol` field on `sample_callers` is unimplementable for these — P3 emits `sample_callers: [{file, line}]` (no symbol), and for file-sourced edges `file`/`line` is the import/use site, not a call site (see R8). Block 4c only requires `sample_callers[file:line ×3]` — no `symbol` — so this is contract-compliant, not an amend. | design impl #13 (red-team) | A codegraph build where `calls` edges always carry a symbol source would make a `symbol` field implementable; the "no symbol" rule would be overly restrictive. |
| A14 | **FATAL2** — `imports` has two semantically distinct sub-shapes. Claim: 440 of 793 `imports` edges target an `import:` placeholder node (all 440 are same-file — `source.file_path == import:.file_path`); 353 target a real symbol (function 151, interface 113, constant 49, type_alias 24, class 12, file 4). File: live DB query. Why it matters: the two sub-shapes must NOT roll together — (a) is a self-micro no-op (drop as self-loops, never cross-component), (b) is a real intra-repo import (roll as file→target-symbol's-owning-micro). Treating them as one would either pollute the diagram with self-loops or lose real deps. | design impl #14 (red-team) | A codegraph build that no longer emits `import:` placeholder nodes would collapse the two sub-shapes; the dispatch-on-target-kind rule would be dead code. |
| A15 | **SERIOUS1** — `references` are type-mentions, not call deps. Claim: 348 of 428 `references` target `interface`, 77 `type_alias`, only 3 target `function` (99% are type-references). File: live DB query. Why it matters: `references` must stay in the rolled `edges[]` array (Block 4c includes it) but is EXCLUDED from `caller_count` (the nano-cap rank key, contract 3) — folding them in would rank functions by signature-type mentions. Contract 3's "by caller count" wording is ambiguous; P3 pins it to `calls` + `instantiates` incoming only, contract-compliant (the grill fixes the cap, not the rank-key set). | design impl #15 (red-team) | `references` targeting functions (call deps) at high rates would make folding them into `caller_count` correct; the "exclude from rank" rule would under-count. |
| A16 | **SERIOUS2** — `implements` are type relations, `instantiates` are call deps. Claim: `implements` = 5 edges, ALL `class → interface` (type relations); `instantiates` = 17 edges, `file`/`function → class` (genuine `new X()` call-deps). File: live DB query. Why it matters: `instantiates` FOLDS into `calls` (emitted as `kind: "calls"`); `implements` is DROPPED entirely (contract 6 freezes {calls, imports, references} — `implements` was never in it, so dropping is contract-compliant, not an amend). If P5 later wants type relations, that is a deliberate Block 4c amendment, not P3. | design impl #16 (red-team) | `implements` edges being call-deps (not type relations) would make dropping them wrong; the "drop entirely" rule would lose real deps. |
| A17 | **NOTE** — nano-cap `caller_count` ties need a deterministic secondary sort. Claim: 82 of 252 fn/method nanos (33%) have ZERO incoming `calls`+`instantiates` edges; ties at zero (and elsewhere) are common. File: live DB query. Why it matters: without a secondary sort, the cap selection is non-deterministic across runs (Python set/dict order). P3's sort is: primary `caller_count` DESC, secondary `qualified_name` ASC, tertiary `path` ASC. The spec must pin this exact sort or the "byte-identical JSON" exit criterion (Roadmap line 113) fails. | design impl #17 (red-team) | A future codegraph build where caller counts are unique per nano would make the secondary sort unnecessary; pinning it would be dead but harmless. |
| A18 | `mkt_engine` file paths use forward slashes throughout (claimed in A10) extends to ALL codegraph builds P3 will target — i.e. codegraph does not emit OS-separator paths on macOS/Linux. New assumption from decomposition: P3 must not normalize separators because A10 only verified `mkt_engine`. | decomposition | A codegraph build emitting backslash paths (Windows) would break `fnmatch` with forward-slash globs without normalization. |
| A19 | The `nodes.kind` vocabulary includes `function`, `method`, `class`, `interface`, `type_alias`, `constant`, `file`, `import` (and the `file:` source nodes have `kind='file'` or that `nodes.id` starts with `file:`). P3's edge roll-up dispatches on the target node's `kind` to detect the `import:` placeholder sub-shape (A14). New assumption: the dispatch key is `nodes.kind`, not `nodes.id` prefix matching. | decomposition (edge roll-up, components 7-9) | A codegraph build using `nodes.id` prefix only (no `kind` column value `'import'`) would force P3 to dispatch on `nodes.id` prefix instead. |
| A20 | A "dominant class" exists when a file holds exactly ONE `class` node (kind='class') whose `file_path` equals the micro's path. The design notes mkt_engine has only 10 `class` nodes across 10 files, so this rarely triggers. New assumption: "dominant" = the only class in the file, regardless of how much of the file's line span it occupies. | decomposition (component 5, micro selection) | A file with 2+ classes would make "dominant" ill-defined; P3's rule would need a span-ratio threshold, which the design does not specify. |
| A21 | The `edges.line` column exists and holds the call-site / import-site / reference-site line number (1-based) for every edge. P3 reads it for `sample_callers[].line`. The design's edge roll-up section references `edge.line` without citing the column name; this assumption pins it to `edges.line`. | decomposition (edge roll-up, component 7) | A codegraph schema where the line is stored elsewhere (e.g. `edges.metadata` JSON) would require P3 to parse JSON for the line, not read a column. |
| A22 | The `files` table contains every indexed file (`path` = repo-relative) and `nodes.file_path` joins to `files.path`. P3 builds the micro set by reading `files.path`, not by enumerating `nodes`. New assumption: `files` is the authoritative file list. | decomposition (component 5) | A codegraph build where some indexed files appear only in `nodes.file_path` (no `files` row) would require P3 to union `files.path` with distinct `nodes.file_path`. |
| A23 | The `nodes.is_exported` / `nodes.docstring` columns exist (P1's `verify_schema` does NOT check them; P3's extended schema guard does). The design lists these in the "extra columns" the schema guard must check. New assumption: both columns are present and populated (may be null). | decomposition (component 4) | A codegraph build without these columns would make P3's `is_exported` / `docstring` extras unimplementable; P3 would have to drop them. |
| A24 | The pilot codegraph DB at `~/all-projects/mkt_engine/.codegraph/codegraph.db` is the golden-test fixture source. A committed `ssot-diagram/testdata/mkt_engine.model.json` is re-recorded only by an explicit `--update-golden` action. New assumption: tests run against this live DB (read-only) and the committed golden JSON; CI does not need a fixture DB copy. | decomposition (component 14, tests) | A CI environment without the live pilot DB would force P3 to commit a fixture DB or use a synthetic one; the golden test would need a different fixture. |
| A25 | ADR 0001 (already accepted and on disk) supersedes design OQ-ADR-1. P3's deliverables list does NOT include writing a new ADR — the ADR already exists. New assumption introduced because A12 says "no `docs/adrs/` yet" but ADR 0001 is now present. | decomposition (discoveries) | ADR 0001 being rejected or moved would restore OQ-ADR-1 to an open deliverable for P3. |

## Component dependency order

Documents what must exist before each component can work — not the order a
developer writes code. The downstream planner decides exact code.

---

### 1. Sibling-import bootstrap + module skeleton

**Goal.** Establish the import seam that lets `graph_model.py` reach P1's
recipe without copying it, plus the empty CLI surface so every later component
has a place to hang.

**Build.** Create `ssot-diagram/graph_model.py`. The first lines mirror the
`decision_hook.py` precedent exactly (the ADR's import block): insert the
script's own directory to `sys.path` and `import decision_index as di`. Add an
`argparse` subcommand dispatcher with two empty subcommands — `extract` and
`bootstrap-config` — each printing "not implemented" and exiting 1 for now. Add
the manifest entry wiring (component 13) here so the script is shippable from
the first commit. No business logic.

**Depends on.** None.

**Assumes.** A1-A11 (P1 symbols exist at the cited lines with the cited
shapes), A18 (forward-slash paths), A25 (ADR 0001 exists).

**Interface shape.** Public CLI surface: `graph_model.py extract [...]` and
`graph_model.py bootstrap-config [...]`. Hidden: every P1 helper reached via
`di.<name>`. One new module (`graph_model.py`); no new seam beyond the CLI.
Adapters that will consume `diagram-model.json`: P5 renderer + plan-visualizer
(2+, real) — but those consume the OUTPUT, not this import seam.

**Dependency category.** in-process (test the import + dispatch directly; no
external service).

**Decisions.**
- Q: Should the sibling-import block live at the very top (before any other
  import) or after stdlib imports? Options: top (matches `decision_hook.py`)
  / after-stdlib. Leaning top because it is the established convention and the
  ADR pins "verbatim."

**Done when.** Running `python3 ssot-diagram/graph_model.py extract` prints a
"not implemented" message and exits 1; running `python3 ssot-diagram/graph_model.py
bootstrap-config` does the same; `python3 -c "import sys; sys.path.insert(0,
'ssot-diagram'); import graph_model"` succeeds without error (the import seam
works); `piggyback status` lists `diagram-model` (component 13 wired).

---

### 2. CLI argument parser (the two subcommands' full surface)

**Goal.** Pin the exact flags each subcommand accepts, so every later
component reads from a parsed `args` object, not ad-hoc `sys.argv` parsing.

**Build.** Define the `extract` subcommand flags: `--db DB` (optional; default
walks up via `di.find_db`), `--index INDEX` (optional; default
`docs/decision-index.json` via `di.default_index_path`), `--config CONFIG`
(optional; default `ssot-diagram/ssot-diagram.config.json`), `--out OUT`
(optional; default `ssot-diagram/diagram-model.json`), `--nano-cap N` (optional
int; default from config's `nano_cap` field, fallback 8). Define the
`bootstrap-config` subcommand flags: `--db DB` (optional; default walks up),
`--out CONFIG` (optional; default `ssot-diagram/ssot-diagram.config.json`),
`--force` (store_true flag). The `extract` subcommand also accepts a hidden
`--update-golden` flag used only by the test harness (component 14) — it
re-writes the committed golden JSON instead of asserting against it.

**Depends on.** Component 1.

**Assumes.** A7 (mirror P1's `--force` gate shape), the `nano_cap` config
field default (contract 3, default 8).

**Interface shape.** Two `argparse` subparsers; the `args` namespace object is
the interface every later component reads.

**Dependency category.** in-process (parse argv, assert the namespace).

**Decisions.**
- Q: Should `--update-golden` be a separate subcommand (`update-golden`)
  instead of a hidden flag? Options: hidden flag on `extract` (matches P1's
  pattern of `--force` / `--strict` flags) / separate subcommand. Leaning
  hidden flag because it is developer-only, not a user-facing verb.

**Done when.** `graph_model.py extract --help` lists all five flags with the
correct defaults; `graph_model.py bootstrap-config --help` lists `--db`,
`--out`, `--force`; passing `--nano-cap 3` parses as the integer 3; an unknown
flag exits 2 with a usage message.

---

### 3. Config loader (`ssot-diagram.config.json` reader + fail-loud guard)

**Goal.** Read the curated config, validate its shape, and hand the rest of
the script a typed dict; fail loud (exit 1 with "run `bootstrap-config` first")
when the config is absent (contract C2).

**Build.** A `load_config(path)` function. It reads the JSON; on missing file,
exits 1 with the "run `bootstrap-config` first" message (mirrors P1's
`load_index` fail-loud at `decision_index.py:165`). On bad JSON, exits 1 with
the parse error. Validates: top-level `version` (int, required),
`components[]` (required, ordered), `default_component` (string, required),
`nano_cap` (int, optional, default 8). Each `components[]` entry must have
`id` (string, unique within file), `name` (string), `glob` (string); `notes`
is optional and ignored. The `default_component` id MUST exist in
`components[]` — fail loud if missing (contract C2's "must not delete cmp-misc"
posture).

**Depends on.** Component 1.

**Assumes.** A10 (forward-slash paths + `fnmatch`), the config schema (design
§ssot-diagram.config.json schema), A18 (no separator normalization needed).

**Interface shape.** `load_config(path: Path) -> dict`. Callers see a validated
dict; the raw JSON parse + validation is hidden.

**Decisions.**
- Q: What `version` values are accepted? Options: only `1` (strict) / any int
  with a warning. Leaning strict `1` because the schema is new and bumping
  should be deliberate.

**Done when.** A valid config file loads and returns the dict; a missing config
exits 1 with the "run `bootstrap-config` first" message (the C2 fail-loud
contract is exercised by a test, component 14); a config missing
`default_component` exits 1; a config with a duplicate `id` in `components[]`
exits 1.

---

### 4. Extended schema guard (P3's extra DB columns)

**Goal.** Fail loud if the codegraph schema has drifted in a way that would
make P3 emit wrong fields — extending P1's `verify_schema` with the columns
P3 reads beyond P1's minimum.

**Build.** A local `_verify_model_schema(con, path)` function. It calls
`di.verify_schema(con, path)` FIRST (reuses P1's check for
`nodes.{name, qualified_name, file_path, start_line, end_line}` and
`files.{path, content_hash}`), then checks P3's extra columns:
`nodes.{kind, docstring, is_exported, id}`, `edges.{source, target, line}`
(and `edges.kind` if present — see A21), `files.path`. On any missing column,
exit 1 with a "codegraph schema not recognized (version drift?); refusing to
guess" message (same posture as P1's `verify_schema` at `decision_index.py:85`).

**Depends on.** Component 1.

**Assumes.** A19 (`nodes.kind` exists and is the dispatch key for the imports
two-shape split), A21 (`edges.line` exists), A23 (`is_exported`, `docstring`
exist), the design's R4 ("anyone changing the codegraph schema must update both
P1 and P3").

**Interface shape.** `_verify_model_schema(con, path) -> None` (raises/exits on
drift). Hidden behind the open_db step; callers see a ready-to-query connection.

**Decisions.**
- Q: Does the guard check `edges.metadata` (referenced in some codegraph
  builds)? Options: yes if present / no. Leaning no — P3 reads `edges.line`,
  not `metadata`; A21 pins the line column.

**Done when.** Against the live `mkt_engine` DB the guard passes (all columns
present); against a synthetic DB missing `nodes.kind` it exits 1 with the drift
message; P1's own `verify_schema` is still called first (the reuse is
verified by reading the source, not by skipping P1's guard).

---

### 5. Component grouping (config-driven + top-level-dir seed)

**Goal.** Assign every indexed file to exactly one component, using the config
globs first-match-wins, with unmatched files falling into `default_component`
(usually `cmp-misc`).

**Build.** A `group_components(con, config) -> dict[component_id, list[relpath]]`
function. It reads `files.path` (the authoritative file list — A22). For each
path, walk `config["components"]` in file order; the first entry whose `glob`
matches via `fnmatch.fnmatch(relpath, glob)` wins; if none match, the path goes
to `config["default_component"]`. When a path matches more than one glob, emit
a stderr warning listing the path + the conflicting component ids (sorted by
path for determinism — R3); still assign to the first. The matched component's
`path` (for the component node) is derived from the glob (strip the trailing
`/**` to get the directory) or falls back to the common prefix of its matched
paths.

For `bootstrap-config`'s seed: scan the top-level directories of indexed files
(`relpath.split('/')[0]`), emit one component per dir with `glob = "<dir>/**"`,
`id = "cmp-<dir>"`, `name = "<Dir>"`. ALWAYS seed a `cmp-misc` (id stable,
name "Other", `glob = "__never_matches__") as `default_component`. Write the
config via `json.dumps(..., indent=2, sort_keys=True) + "\n"` (determinism).

**Depends on.** Components 2, 3 (the parsed `--config` path and the loader).

**Assumes.** A10 (`fnmatch` + forward slashes), A18, A22 (`files` is the
authoritative list), the design's "first match wins" + "cmp-misc always seeded"
rules (OQ-DISAMBIG-1 resolved: always seed cmp-misc).

**Interface shape.** Returns the grouping dict; the renderer-facing component
node objects are built in component 11 (id synthesis). Seeding is a separate
function (`seed_config`) called only by `bootstrap-config`.

**Decisions.**
- Q: How is the component `path` derived when the glob is not of the form
  `<dir>/**`? Options: common-prefix-of-matched-paths / strip-the-glob's-*.
  Leaning common-prefix because it is robust to arbitrary glob shapes.
- Q: When `bootstrap-config` finds no indexed files, what happens? Options:
  exit 1 ("no files indexed — run `codegraph init`") / write an empty config.
  Leaning exit 1, mirroring P1's `cmd_bootstrap` dying on no docs.

**Done when.** Every indexed `mkt_engine` file lands in exactly one component
(counts add up — `sum(len(files)) == total files`); files matching no glob land
in `cmp-misc`; a config with two globs matching one path triggers a stderr
warning AND first-match assignment (the test "First-match wins + multi-match
warning" in component 14); `bootstrap-config` writes a config with one entry
per top-level dir + a `cmp-misc` row.

---

### 6. Micro selection (file vs dominant class)

**Goal.** Decide, for each file, whether the micro is the whole file or the
single dominant class inside it.

**Build.** A `select_micros(con, component_grouping) -> list[micro]` function.
For each file path in each component: query `nodes` for `kind='class' AND
file_path = <path>`. If exactly ONE class node exists, the micro is that class
(micro id `micro:<relpath>#<qualified_name>`, signature from `di.slice_hash`
over the class span via `di.symbol_spans`). Otherwise (zero or 2+ classes), the
micro is the file (micro id `micro:<relpath>`, signature from
`di.file_content_hash`). The dominant-class case carries `dominant_class:
<qualified_name>` on the micro node; the file-dominant case carries
`dominant_class: null`.

**Depends on.** Component 5 (grouping).

**Assumes.** A20 ("dominant" = the only class in the file; mkt_engine has only
10 class nodes across 10 files, so this rarely triggers), A2 (use
`di.file_content_hash`, not `nodes.signature`), A3 (qualified_name alone is
ambiguous — but here we query by `(kind, file_path)` which is unique).

**Interface shape.** Returns a list of micro dicts (partial — they get
`children`, `edges`, `decisions` from later components). Each micro's `id` is
the path-derived form, NOT `nodes.id`.

**Decisions.**
- Q: When a file has 2+ classes, is the micro the file (with no dominant
  class) or each class its own micro? Options: file (the design says "exactly
  one class and that class is the bulk of the file") / each class. Leaning
  file because A20 pins "dominant" to the single-class case.

**Done when.** Every `mkt_engine` file produces exactly one micro; a file with
no classes produces a file-micro with `dominant_class: null`; a file with one
class produces a class-micro with `dominant_class: <qname>`; the micro id is
path-derived, never `nodes.id`.

---

### 7. Nano selection + cap + collapse (the rank + tiebreak)

**Goal.** For each micro, pick the top N (default 8) nano functions/methods by
caller count, and collapse the rest into one honest `+K more` node.

**Build.** A `select_nanos(con, micros, nano_cap) -> list[nano]` function. For
each micro, query `nodes` for `kind IN ('function', 'method') AND file_path =
<micro path>`. For each nano, compute:
- `caller_count` = count of incoming `calls` + `instantiates` edges to that
  node's `nodes.id` (NOT `references` — A15; NOT `imports` — design's
  "imports excluded from rank" rule).
- `signature` = `di.slice_hash(root, relpath, start, end)` (via
  `di.symbol_spans`).
- `qualified_name`, `start_line`, `end_line` from `nodes`.
- `docstring` from `nodes.docstring` (may be null).
- `is_exported` from `nodes.is_exported`.

Sort the nanos by: primary `caller_count` DESC, secondary `qualified_name` ASC,
tertiary `path` ASC (A17). Take the first N as the visible nanos. The rest
(sorted the same way) collapse into one `kind=collapsed` node with id
`nano:+collapsed@micro:<micro_id>`, `name="+K more"`, `collapsed_count=K`,
`signature` = sha256 over the sorted list of the K members' `signature` fields
(contract C3, deterministic).

**Depends on.** Component 6 (micros).

**Assumes.** A15 (references excluded from rank), A16 (instantiates folded
into calls for the rank — they count as caller edges), A17 (the exact
tiebreak), A23 (docstring + is_exported columns exist), the design's
§Nano-cap selection.

**Interface shape.** Returns a list of nano dicts (visible + one collapsed per
micro that overflowed). Each nano's `micro_id` back-pointer is set here.

**Decisions.**
- Q: Should the collapsed node carry `children[]` listing the collapsed nano
  ids? Options: yes (P5 could expand on click) / no (the design only specifies
  `collapsed_count`). Leaning no — out of scope for P3; P5 can request it as a
  Block 4b amendment.
- Q: When a micro has fewer than N nanos, is a collapsed node emitted?
  Options: never (the design implies this) / always with `collapsed_count: 0`.
  Leaning never — `collapsed_count: 0` would be noise.

**Done when.** A micro with 12 functions and `--nano-cap 8` produces 8 visible
nanos + 1 collapsed with `collapsed_count: 4`; the selected 8 and the 4
collapsed are exactly the ones the deterministic sort picks (the synthetic
fixture test in component 14); a micro with 5 functions and cap 8 produces 5
nanos + 0 collapsed; the collapsed node's `signature` is sha256 over the 4
members' hashes (recompute and assert equality).

---

### 8. Edge roll-up (calls + instantiates, imports two-shape, references)

**Goal.** Turn the codegraph `edges` table into per-node rolled-up edge lists
with counts and a stable 3-row `sample_callers[{file, line}]` (no `symbol`
field).

**Build.** A `roll_up_edges(con, micros, nanos, components) -> dict[node_id, list[edge]]`
function. It reads the raw `edges` table once into memory, joins both ends to
`nodes` (on `nodes.id` — A11) to recover each end's `kind`, `file_path`, and
`qualified_name`. Then dispatches by the `edges.kind` column:

- **`calls` + `instantiates`** (fold): both roll up as `kind: "calls"` in the
  model. Source is `function`/`method`/`file:` node; target is
  `function`/`method`/`class`. Aggregate by
  `(source_micro, target_micro)` for nano-level and micro-level edges; by
  `(source_component, target_component)` for component-level edges. Within-
  component edges appear only at micro/nano level (roadmap.md line 96).
- **`implements`** (drop): emit nothing. (A16.)
- **`references`** (keep as edges, exclude from rank): emit as
  `kind: "references"`, aggregated the same way as calls.
- **`imports`** (two sub-shapes — A14):
  - (a) target `kind == 'import'` (placeholder node): DROP as self-loop (all
    440 are same-file; never cross-component).
  - (b) target is a real symbol: roll as `file → target-symbol's-owning-micro`
    (target micro = the target symbol's file's micro, NOT the target treated
    as a nano). `count` = number of intra-repo import edges between that
    source-file/target-micro pair. `kind: "imports"`.
- **`contains`**: NOT an edge (it is the tree-parent relationship, already
  expressed by `children[]` / back-pointers).

For each rolled-up edge, build `sample_callers`: collect all source call-sites
`(source.file_path, edges.line)` for that source/target pair; emit the 3
lexicographically smallest by `(file, line)` ascending. For symbol-sourced
edges, `file` = source function's `file_path`; for file-sourced edges (source
is a `file:` node), `file` = source `file:` node's `file_path`. NO `symbol`
field (A13). Edge `direction`: `source → target` means "source depends on
target" (matches the DB's `source`/`target` orientation — design §Direction).

**Depends on.** Components 5, 6, 7 (the grouped components + micros + nanos so
the roll-up knows the source/target micro and component for each edge).

**Assumes.** A11 (two-id reality — join on `nodes.id`, emit path-derived
model ids), A13 (no symbol field; file-sourced case), A14 (imports two-shape),
A15 (references kept as edges, excluded from rank), A16 (instantiates folds,
implements drops), A19 (dispatch on `nodes.kind`), A21 (`edges.line` column).

**Interface shape.** Returns the per-node edge dict keyed by model `id`. The
edges array on each node is sorted by `(source, target, kind)` ascending
(determinism).

**Decisions.**
- Q: For component-level edges, do within-component edges appear? Options: no
  (only cross-component at the macro level — roadmap.md line 96) / yes.
  Leaning no per the roadmap.
- Q: For a `references` edge into an `interface` node that lives in a file
  with no nanos (no micro), how is the target resolved? Options: the file's
  micro still exists (every file → one micro) / skip the edge. Leaning the
  file's micro — A22 says every file → one micro.
- Q: When `edges.line` is null (some codegraph builds may not populate it for
  every edge kind), what goes in `sample_callers[].line`? Options: skip that
  call-site / emit line: null / emit line: 0. Leaning skip — a null line is
  not a usable call site; A21 says the column exists but does not promise it
  is non-null for every edge.

**Done when.** Every nano micro node in `mkt_engine` whose function has
incoming calls carries a non-empty `edges[]`; the imports two-shape test
(component 14) confirms zero self-micro `imports` edges AND every intra-repo
symbol import appears; the `caller_count` excludes `references` test confirms
a nano with 5 incoming references and 0 calls has `caller_count = 0` AND the
references still appear in `edges[]`; the `instantiates`/`implements` test
confirms the 2 instantiates appear as `kind: "calls"` and the 1 implements
does not appear anywhere.

---

### 9. Decision-node merge (verified anchors + worst-case badge)

**Goal.** Attach `decision:<ADR-ID>@<component-id>` nodes to every component
owning ≥1 verified anchor, with a live FRESH/STALE/ORPHANED/superseded badge
that is consistent across all attachments of the same decision.

**Build.** A `merge_decisions(con, root, index, component_grouping, micros) ->
list[decision_node]` function. For each decision in the index:
1. Filter to anchors with `verified: true`. If zero verified anchors, skip
   (no decision node — contract C5).
2. For each verified anchor, call `di.parse_ref(a["ref"])` to extract the path.
   A `file:<path>` anchor → the file's component. A `<qname>@<path>` anchor →
   the symbol's file's component (the symbol is flagged as the anchor target
   inside that micro's `decisions[]` extra). Use the path to look up the
   component via the config grouping (component 5) — do NOT re-resolve via the
   bare name (which would be ambiguous per A3, A4).
3. For each anchor, call `di.anchor_status(con, root, a)` to get the live
   status (`FRESH`/`STALE`/`ORPHANED`/`AMBIGUOUS` — A5). The decision's badge
   is the WORST status across its verified anchors
   (`ORPHANED > STALE > AMBIGUOUS > FRESH`).
4. Attach `decision:<ADR-ID>@<component-id>` to every component owning ≥1
   verified anchor's micro. Same status across all attachments.
5. Read `supersedes` from the index; a decision whose `supersedes` chain
   points at it renders `status: "superseded"` (the renderer treats it as
   disabled — design §Decision-node merge step 4).
6. The decision node's `signature` = sha256 over the sorted list of the
   decision's verified anchor `sig` values (so the node changes iff any
   anchor's content changes — exactly when the L1 badge flips).
7. The decision node's `anchor_count` = number of verified anchors.

The component node's `decisions[]` and the micro node's `decisions[]` arrays
are populated here as forward-pointers to the decision node ids.

**Depends on.** Components 5, 6 (grouping + micros to find owning components),
component 10 (the pre-extract guard must run first per contract C5 — but the
guard only warns; merge proceeds regardless).

**Assumes.** A3 (qualified_name ambiguous — pins path from ref), A4 (`parse_ref`
returns the path), A5 (status vocabulary), A8 (the pre-extract guard can reuse
`di._evaluate` for the not-fresh warning — though merge recomputes
`anchor_status` per anchor for the badge), A9 (pilot index is fully curated),
the design's §Decision-node merge 4 steps.

**Interface shape.** Returns a list of decision nodes; mutates the component +
micro nodes to add their `decisions[]` forward-pointers.

**Decisions.**
- Q: When a `<qname>@<path>` anchor's symbol no longer exists (ORPHANED
  status), does the decision node still attach? Options: yes with ORPHANED
  badge / no. Leaning yes — contract C4 says "every component owning ≥1
  verified anchor" attaches; ORPHANED is a badge, not a skip condition.

**Done when.** The 8 `mkt_engine` ADRs (all verified, all FRESH per A9) produce
8 decision nodes, each attached to ≥1 component, each badge = FRESH (the
"verified-anchored decision appears once" test in component 14); a synthetic
fixture with one anchor flipped to `verified: false` produces NO decision node
for that ADR; a synthetic fixture with one anchor's symbol deleted (ORPHANED
status) produces a decision node with the ORPHANED badge (worst-case).

---

### 10. Pre-extract guard (warn-and-continue on not-verified / not-FRESH)

**Goal.** Before emitting, warn on stderr if the index has any `verified:false`
anchor or any not-FRESH anchor; always exit 0 and always still emit (contract
C5). The model stays truthful regardless.

**Build.** A `pre_extract_guard(con, root, index) -> list[str]` function. It
calls `di._evaluate(con, root, index["decisions"])` to get the
`(did, ref, state)` rows + `n_not_fresh` count (A8). It also scans for any
anchor with `verified: false`. If either condition is true, it warns on
stderr listing each offending `<ADR-ID>` + `ref` + reason, pointing at
`decision_index refresh <id>`. Returns control to `extract`, which proceeds to
emit (exit 0 always). The warning text is sorted by `(ADR-ID, ref)` for
determinism (R3 posture).

**Depends on.** Components 2, 3 (parsed args + index loaded via `di.load_index`),
A8 (`_evaluate`'s return shape).

**Assumes.** A8 (`_evaluate` returns `(rows, n_not_fresh)` with rows =
`(did, ref, state)`), A9 (pilot index is fully fresh, so the guard warns on
nothing in the golden test).

**Interface shape.** Returns the list of warning strings (also printed to
stderr). The caller (`extract`) ignores the return for control flow — the
guard never aborts.

**Decisions.**
- Q: Does the guard run before or after the schema guard (component 4)?
  Options: before / after. Leaning after — the schema guard is a hard fail
  (exit 1 on drift); the pre-extract guard is a soft warn (exit 0); running
  the hard fail first avoids loading the index if the DB is unusable.

**Done when.** Against the live `mkt_engine` index (all verified, all FRESH
per A9), the guard emits nothing and `extract` proceeds; against a synthetic
fixture with one `verified: false` anchor, the guard emits a stderr warning
pointing at `decision_index refresh <id>` and `extract` still exits 0 and still
writes the model (with no decision node for the unverified anchor — verified
by the merge test in component 14).

---

### 11. Component + model id synthesis + child pointers

**Goal.** Build the final component/micro/nano node objects with their
model-derived ids, forward `children[]` pointers, and back-pointers
(`component_id`, `micro_id`), so the renderer can traverse either direction.

**Build.** An `assemble_nodes(components, micros, nanos, decisions) -> dict`
function. It synthesizes ids per the design's id forms:
- component: `cmp-<slug-from-config-id>` (use the config's `id` directly — it
  is already `cmp-<slug>` by convention; never `nodes.id` — A1, A11)
- micro (file-dominant): `micro:<relpath>`
- micro (class-dominant): `micro:<relpath>#<qualified_name>`
- nano: `nano:<qualified_name>@<relpath>`
- collapsed: `nano:+collapsed@micro:<micro_id>`
- decision: `decision:<ADR-ID>@<component-id>` (contract C4)

Populate `children[]` on each component (forward-pointers to its micros' ids)
and on each micro (forward-pointers to its nanos' ids + its collapsed node id
if any). Populate `component_id` on each micro and `micro_id` on each nano
(back-pointers). Populate `file_count` + `symbol_count` on each component,
`collapsed_count` on collapsed nodes, `anchor_count` on decision nodes.
Populate `edges[]` on each node from the roll-up (component 8). Populate
`decisions[]` on each component + micro from the merge (component 9).

**Depends on.** Components 5, 6, 7, 8, 9.

**Assumes.** A1, A11 (synthesize ids, never use `nodes.id`), the design's id
forms.

**Interface shape.** Returns the assembled node dict (component → micro → nano
with both forward and back pointers). No DB access.

**Decisions.**
- Q: Are the model's top-level arrays `components`, `micros`, `nanos`,
  `decisions` (flat lists, as the design's example shows) or a single nested
  tree? Options: flat lists with `children[]` pointers (the design's example)
  / nested tree. Leaning flat lists — the design's example payload uses flat
  arrays + pointers, and the renderer traverses via pointers.

**Done when.** Every component node's `children[]` lists its micros' ids; every
micro node's `children[]` lists its nanos' ids (+ collapsed id); every micro
node's `component_id` points back to its component; every nano node's
`micro_id` points back to its micro; no node's `id` equals a `nodes.id` value
(the "never pass through" rule is checkable by comparing the model's ids
against `nodes.id` in the DB).

---

### 12. JSON serialization (byte-deterministic writer)

**Goal.** Write the assembled model to `diagram-model.json` with byte-identical
output across runs given identical inputs — the exit criterion from
`roadmap.md` line 113. This is the strictest serialization in the repo:
stricter than P1's `save_index` (A6).

**Build.** A `serialize_model(model_doc, out_path) -> None` function. The model
doc is the assembled node dict (component 11) wrapped in a top-level envelope:
`{version: 1, generated_at: null, root: <relpath>, nano_cap: N,
components: [...], micros: [...], nanos: [...], decisions: [...]}`. The writer:
- `json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` —
  `sort_keys=True` is the key difference from P1 (A6: P1's `save_index` does
  NOT sort; P3 must, because P3 emits from dict iteration whereas P1's index
  is human-curated to a stable order).
- All lists sorted by a deterministic key BEFORE serialization: components by
  `id`; micros by `path`; nanos by `qualified_name` then `path`; edges by
  `(source, target, kind)`; `sample_callers` by `(file, line)`; collapsed
  members by `qualified_name` then `path`; decisions by `id`; each component's
  + micro's `decisions[]` by decision id; each `children[]` by id.
- `generated_at` always null (a real timestamp breaks byte-determinism;
  consumers that want "when built" read the file mtime).
- `root` is the repo-relative root from `di.repo_root_for(db)`.
- No `set()` iteration order leaks anywhere — every collection is sorted
  explicitly before emission.
- The output file is written atomically: serialize to a string, then write to
  `out_path` (the design does not require a temp-file-rename dance, but the
  planner may add one if the test environment needs it).

The `--update-golden` flag (component 2) routes here: instead of asserting
against the committed golden, the writer writes its output to the golden
artifact path directly.

**Depends on.** Component 11 (the assembled nodes); components 2, 3 (the
`--out` path + `--update-golden` flag from the CLI).

**Assumes.** A6 (P3 stricter than P1 — `sort_keys=True`), the design's
§Determinism (every list sorted by a deterministic key; `generated_at` null;
no set() order leaks), A18 (the `root` path's separator is forward-slash per
A10, so no normalization needed at serialization time).

**Interface shape.** `serialize_model(model_doc, out_path)` — the only writer
P3 has. The function is pure: same `model_doc` ⇒ same bytes. No DB access.

**Decisions.**
- Q: Atomic write (temp file + rename) vs direct write? Options: direct (the
  design does not mention atomicity) / temp+rename (safer against a writer
  crash leaving a half-written file). Leaning direct — the design is silent
  and the test environment controls the output path; atomicity is a P6 concern
  (when the hook re-runs `extract` during a session).
- Q: Should `nano_cap` appear at the top level? Options: yes (the renderer
  reads it to know the cap) / no. Leaning yes — P5 needs it to render the
  "+K more" nodes correctly per the design's Consumer contracts.

**Done when.** Two consecutive `extract` runs on `mkt_engine` produce files
with identical sha256 (the determinism test in component 14); the produced JSON
has sorted keys (verified by re-parsing and comparing `sorted(doc.keys())` to
`doc.keys()`); no `set()` iteration order leak (verified by running `extract`
10× and asserting identical sha256 each time); `generated_at` is null in the
output; the golden model test (component 14) matches the committed artifact
byte-for-byte.

---

### 13. Manifest entry + bootstrap-config writer

**Goal.** Register `graph_model.py` in `manifest.json` so `piggyback
install/init/update` distributes it; implement the `bootstrap-config` writer
(the seed half of contract C2).

**Build.** Edit `manifest.json`: add one entry under key `diagram-model`:

```json
"diagram-model": {
  "script": "ssot-diagram/graph_model.py",
  "scope": "repo",
  "desc": "ssot-diagram P3 — extract diagram-model.json from codegraph DB + decision index",
  "hooks": []
}
```

`hooks: []` because P3 ships CLI-first; the PostToolUse hook that re-runs
`extract` on codegraph re-index is P6. `scope: "repo"` matches the other
ssot-diagram entry (`decision-index`) and the per-repo `.claude/settings.json`
model.

The `bootstrap-config` writer (component 5's `seed_config`) writes the seeded
config JSON. It refuses to overwrite an existing config without `--force`
(mirrors `cmd_bootstrap` at `decision_index.py:236-237` — A7): on existing
output without `--force`, exit 1 with "exists — refusing to overwrite a curated
config. Pass `--force` to reseed." With `--force`, reseed.

**Depends on.** Components 1, 2, 5 (the writer uses `seed_config` from
component 5's grouping logic).

**Assumes.** A7 (mirror P1's `--force` gate shape exactly), the manifest
shape (verified — 3 existing entries follow this shape), A25 (ADR 0001 exists,
so no new ADR deliverable).

**Interface shape.** The manifest entry is the public seam `piggyback` reads;
`bootstrap-config`'s stdout/exit-code is the user-facing seam.

**Decisions.**
- Q: Does `bootstrap-config` write `nano_cap: 8` in the seed? Options: yes /
  no. Leaning yes — the seed should be a complete, runnable config; omitting
  `nano_cap` would force `extract` to use the fallback.

**Done when.** `piggyback status` lists `diagram-model`; `bootstrap-config`
on a fresh repo writes a config with one component per top-level dir + a
`cmp-misc` default + `nano_cap: 8`; a second `bootstrap-config` without
`--force` exits 1 with the "refusing to overwrite" message;
`bootstrap-config --force` reseeds (the test in component 14).

---

### 14. Tests (golden + determinism + 5 red-team regressions)

**Goal.** Verify the byte-determinism contract, the model's correctness
against the curated pilot, and the 5 red-team fixes (A13-A17) stay fixed.

**Build.** Create `ssot-diagram/test_graph_model.py` and a golden model
artifact at `ssot-diagram/testdata/mkt_engine.model.json` (committed;
re-recorded only via `--update-golden`). Tests:
- **Golden model** — run `extract` against the live `mkt_engine` DB + index +
  config; assert the produced JSON matches the committed golden byte-for-byte
  (sha256 comparison). Re-recording is an explicit `--update-golden` action.
- **Determinism** — two consecutive `extract` runs produce byte-identical
  output (sha256 comparison). This is the roadmap.md exit criterion.
- **Verified-anchored decision appears once** — for `mkt_engine` (8 ADRs / 33
  verified anchors all FRESH per A9), assert 8 decision nodes appear, each
  attached to ≥1 component, each badge = FRESH.
- **Unverified anchor → no decision node** — synthetic fixture: flip one
  anchor's `verified` to false; assert no `decision:<that-ADR>@*` node is
  emitted.
- **Nano cap + collapse** — synthetic fixture with 12 functions in one micro,
  `--nano-cap 8`: assert 8 nano + 1 `collapsed` node whose `collapsed_count=4`
  and whose `signature` is sha256 over the 4 members' hashes. Assert the
  selected 8 + the 4 collapsed are the ones the deterministic sort
  (`caller_count` DESC, `qualified_name` ASC, `path` ASC) picks — including
  the zero-caller case (A17: 33% of nanos tie at zero; the secondary sort must
  break those ties deterministically).
- **Sample_callers shape (FATAL1 / A13)** — assert every `sample_callers`
  entry is `{file, line}` with NO `symbol` key. Synthetic fixture with 5
  call-sites into one target where 3 have a `file:` source and 2 have a
  `function:` source: assert the 3 emitted are the lexicographically
  smallest `(file, line)`, in that order, across two runs. Assert file-sourced
  edges populate `file`/`line` from the source `file:` node's `file_path` +
  the `edges.line` (the import/use site), not a call site.
- **imports two-shape roll-up (FATAL2 / A14)** — synthetic fixture: 2
  `file→import:` same-file edges + 3 `file→symbol` intra-repo edges. Assert
  ZERO self-micro `imports` edges appear in the model; assert the 3 intra-repo
  imports roll up to `file→target-micro` correctly (target micro = the target
  symbol's file's micro, NOT the target treated as a nano).
- **`caller_count` excludes `references` (SERIOUS1 / A15)** — synthetic
  fixture: a nano with 5 incoming `references` (target type mentions) and 0
  incoming `calls`/`instantiates`: assert `caller_count = 0` AND the
  `references` still appear in the node's `edges[]` array (Block 4c keeps
  them as edges; they just don't count toward the rank).
- **`instantiates` folds, `implements` drops (SERIOUS2 / A16)** — synthetic
  fixture: 2 `instantiates` edges + 1 `implements` edge into a class. Assert
  the 2 `instantiates` appear as `kind: "calls"` in the model; assert the 1
  `implements` does NOT appear anywhere in the model.
- **First-match wins + multi-match warning** — synthetic config where two
  globs match one path: assert the file lands in the first component AND a
  stderr warning fires.
- **No-config fail-loud** — run `extract` with no
  `ssot-diagram.config.json`: assert exit 1, stderr contains "run
  `bootstrap-config` first" (contract C2).
- **bootstrap-config --force** — assert a second `bootstrap-config` without
  `--force` exits 1 ("refusing to overwrite"); with `--force` it reseeds
  (contract C2 / A7).

**Depends on.** All prior components (the tests exercise the assembled
extractor).

**Assumes.** A9 (pilot index state, exercised by golden + verified-decision
tests), A24 (CI runs against the live pilot DB read-only + committed golden
JSON; no fixture DB copy needed), A13-A17 (the 5 red-team fixes, each
exercised by its named regression test).

**Interface shape.** pytest functions in `test_graph_model.py`; the golden
artifact at `ssot-diagram/testdata/mkt_engine.model.json`. The `--update-golden`
hidden flag (component 2) is the re-record seam.

**Decisions.**
- Q: How are synthetic fixtures built? Options: in-memory temp DB constructed
  per test / a committed fixture DB. Leaning in-memory (`sqlite3` can build a
  schema-matching DB in a tmp_path) — keeps tests hermetic and avoids fixture
  DB drift.
- Q: Does the golden model test run in CI (requires the live `mkt_engine` DB)?
  Options: yes (CI has the pilot repo checked out) / skip if DB absent. Leaning
  skip-if-absent (a `pytest.mark.skipif` on the DB path) so CI in other repos
  does not fail; the determinism + red-team tests are hermetic and always run.

**Done when.** `python3 -m pytest ssot-diagram/test_graph_model.py` passes all
the listed tests; the determinism test asserts two consecutive runs produce
identical sha256; the golden model matches the committed artifact (or is
re-recorded via `--update-golden` after a deliberate change); each of the 5
red-team regression tests fails if its corresponding fix is reverted.

---

## Handoff notes

- **Contract with P4 (narrative sidecar):** P3's `id` synthesis
  (`nano:<qualified_name>@<relpath>`, `micro:<relpath>`,
  `decision:<ADR-ID>@<component-id>`, etc.) is the stable key P4 narratives pin
  to; P3's `signature` (content hash from `di.slice_hash` /
  `di.file_content_hash` / sha256-over-members) is the pin P4 compares against.
  P4 compares a narrative's pinned `signature` to the model node's current
  `signature` to mark it `stale` (Block 5b trust rule — the same compare P1's
  `anchor_status` does for decision anchors). P4 must NOT re-derive signatures
  — it reads them from `diagram-model.json`.
- **Contract with P5 (renderer):** P5 reads the whole `diagram-model.json`.
  Block 4 = its contract. The flat arrays (`components`, `micros`, `nanos`,
  `decisions`) + `children[]` + back-pointers (`component_id`, `micro_id`) let
  P5 traverse either direction. Per-node `edges[]` carry `count` (label:
  "calls ×14"), decision nodes carry a `status` badge, the `collapsed` kind is
  the "+K more" treatment. `generated_at` is null (byte-determinism); P5 reads
  file mtime if it wants "when built."
- **Contract with plan-visualizer:** Given a `path::symbol` manifest entry, it
  resolves to a model node via the Block 1a resolver (honest
  AMBIGUOUS/UNRESOLVED — Block 4e), then reads that node's `edges[]` for
  `count` + `sample_callers[{file, line}]` (NO `symbol` — A13) WITHOUT opening
  the DB. The plan-visualizer's "blast" count = `caller_count` = incoming
  `calls` + `instantiates` only (A15 — `references` excluded).
- **Read-only DB coupling (load-bearing):** P3 connects `mode=ro&immutable=1`
  via `di.open_db` (reuses P1 — A1's "never write" rule). The extended schema
  guard (component 4) is a hard fail on drift; it does NOT mutate the DB. The
  golden test reads the live pilot DB read-only — if a CI environment lacks
  the pilot DB, the golden test skips (component 14's open decision).
- **Determinism contract (the exit criterion):** same DB + same index + same
  config ⇒ byte-identical JSON, verified by a two-run sha256 comparison test
  (component 14). `json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
  + "\n"`. All lists sorted by a deterministic key. `generated_at` always
  null. No `set()` iteration order leaks. Stricter than P1's `save_index`
  (A6).
- **Sibling-import reuse of P1's 11 symbols (named, per ADR 0001 + this spec's
  Already Built table):** `di.find_db` (locate DB), `di.open_db` (read-only
  connect), `di.verify_schema` (P1's schema guard, extended by component 4),
  `di.file_content_hash` (micro signature), `di.symbol_spans` (nano span
  lookup), `di.slice_hash` (nano + class-dominant micro signature),
  `di.parse_ref` (decision-node merge path extraction), `di.current_sig` (live
  signature + state), `di.anchor_status` (FRESH/STALE/ORPHANED/AMBIGUOUS per
  anchor — the worst-case badge), `di.load_index` (fail-loud index loader),
  `di._evaluate` (pre-extract guard's not-fresh walk). The Phase B
  consolidation target set (ADR 0001's table) is exactly these 11 symbols;
  when Phase B lands, `_shared/db.py` + `_shared/sig.py` lift them and P1 +
  the hook + P3 each cut over (clean cutover, no back-compat aliases).
- **Two-id reality (load-bearing for research):** the codegraph `nodes.id` is
  content-derived (`<kind>:<hex>`, A1) and is the DB join key for `edges`
  (A11); the model `id` is path-derived and is what the JSON emits. Research
  must confirm `edges.source`/`edges.target` join to `nodes.id` (not to a
  path-derived column) before the planner finalizes the edge roll-up code —
  if the join key is different, the roll-up's join logic changes.
- **Open uncertainty:** whether `edges.line` is non-null for every edge kind
  (A21 + component 8's open decision). If `edges.line` is null for some kinds
  (e.g. `references`), the `sample_callers[].line` for those edges must skip
  or fall back — research must sample `edges.line` grouped by `kind` against
  the live DB.
- **Suggested research (for `/factual-code-verification`):**
  - Verify A1-A12 against the live `mkt_engine` DB read-only (`mode=ro&
    immutable=1`) and against `decision_index.py` at the cited lines.
  - Verify A13-A17 (the 5 red-team fixes) by re-running the design's
    red-team verification query (one script, evidence in §Read-set).
  - Verify A18 (forward-slash path universality) by sampling `files.path`
    across the pilot — if any path uses backslashes, P3 needs a normalization
    step.
  - Verify A19 (`nodes.kind` is the dispatch key for the imports two-shape
    split) by confirming `import:` placeholder nodes have `kind='import'`,
    not just an id prefix.
  - Verify A20 (dominant class = only class in the file) by checking that no
    `mkt_engine` file has 2+ `class` nodes — the design says 10 classes across
    10 files, but research must confirm.
  - Verify A21 (`edges.line` column exists + population rate per kind).
  - Verify A22 (`files` is the authoritative file list — every `nodes.file_path`
    has a `files.path` row).
  - Verify A23 (`nodes.is_exported` + `nodes.docstring` columns exist).
  - Verify A24 (the golden-test fixture strategy: does CI have the live pilot
    DB, or does P3 need a committed fixture?).
  - Re-confirm the 5 red-team regression tests in component 14 fail if their
    fixes are reverted (this is a research + test-design task).

## Open Questions (deferred — do NOT resolve in this spec)

- **OQ-PERF-1 — Streaming edge roll-up.** Keep in-memory now (the pilot has
  2345 edges in calls+imports+references); revisit if a real repo proves
  `extract` takes > a few seconds. Defer.
- **OQ-DISAMBIG-1 — `cmp-misc` always seeded vs only-when-needed.** Resolved
  in the design: always seed `cmp-misc`. The "hide empty components" question
  is deferred to P5 (renderer concern). Closed here for P3.
- **OQ-P5-1 — External-module `import:` node bucketing.** P3 drops the 440
  `file→import:` placeholder edges as self-loops. P5 may want external-dep
  arrows later; if so, that is a deliberate design addition, not P3. Defer to
  P5.
- **OQ-P5-2 — Tooltip wording for file-sourced `sample_callers`.** An `imports`
  edge with a `file:` source is an import statement, not a call site. P3
  carries the truth in `kind`; the tooltip wording is the renderer's. Defer to
  P5.
- **OQ-Block4c-1 — `implements` as a fourth edge kind.** Dropped in P3 (A16).
  If P5 later wants type relations, that is a deliberate Block 4c amendment
  (`implements` reintroduced), not a P3 concern. Defer to a Block 4c change.
- **Synthetic-fixture strategy (component 14 open decision).** In-memory
  temp DB per test vs committed fixture DB. The spec leans in-memory; the
  planner confirms.
- **CI golden-test gating (component 14 open decision).** Skip-if-absent vs
  require-the-pilot-DB. The spec leans skip-if-absent; the planner confirms.
- **Component `path` derivation (component 5 open decision).** Common-prefix-
  of-matched-paths vs strip-the-glob's-`**`. The spec leans common-prefix; the
  planner confirms.
- **`--update-golden` shape (component 2 open decision).** Hidden flag on
  `extract` vs separate `update-golden` subcommand. The spec leans hidden
  flag; the planner confirms.
