# Factual Code Verification: P3 — Diagram Model Extractor
_Last updated: 2026-07-04_

## Overview

This document verifies the spec for the next phase of the ssot-diagram pipeline:
a script (`ssot-diagram/graph_model.py`) that turns the codegraph SQLite database
plus the curated decision index into one deterministic diagram-model JSON file. The
spec is at `docs/AI_artifacts/2_specs/p3-diagram-model-extractor.md` and carries 25
falsifiable assumptions (A1–A25), five of them (A13–A17) explicitly flagged as
load-bearing "red-team fixes."

The verification verdict: **all 25 assumptions validate, with one nuance worth
flagging on A1.** Every line number, every P1 symbol signature, every column name,
every red-team count, and every "two-id reality" claim in the spec matches the
actual code and the live pilot database. The spec is ready to hand to /plan.

Plan-relevant takeaways the planner must know:
1. The spec's "Option A sibling import of P1" is correct and the ADR (0001, on disk)
   is real, so the planner does NOT add "write ADR" to the deliverables list.
2. The six frozen grill contracts and the five red-team fixes (A13–A17) all check
   out against the live DB — implementing them literally will produce correct
   behavior. No re-litigation needed.
3. The 3_factual-code-verification folder name: the dispatch says write here; the
   skill's own folder-rename note would call it `5_factual-code-verification` (see
   Open Questions). The dispatch is human authority and was followed.
4. The exit criterion "every verified anchor appears once" IS testable right now
   against the live pilot index (8 ADRs, 33 anchors, all verified, all FRESH).
5. `nodes.id` is a content-hash id for 226/232 function-kind nodes (`function:<32-hex>`)
   but the codegraph build also emits 6 `hook:` ids (`hook:<path>:<name>:<line>`)
   that are PATH-DERIVED. A1's prescription ("P3 synthesizes its own id; never
   passes `nodes.id` through") is unaffected and still correct, but its rationale
   ("one-line edit changes it") only holds for the content-hash form. Flagged below
   as a NUANCE, not an invalidation.

## Direct verification log (what was opened)

Source code:
- `ssot-diagram/decision_index.py` — full read via `codegraph node` (419 lines).
  Symbols verified at cited lines: `find_db` (53), `repo_root_for` (62),
  `default_index_path` (67), `open_db` (73), `verify_schema` (85),
  `file_content_hash` (96), `symbol_spans` (101), `_sha256` (111), `slice_hash`
  (115), `parse_ref` (125-133), `current_sig` (136-151), `anchor_status` (154-158),
  `load_index` (163-172), `save_index` (175-179), `_evaluate` (290-299),
  `cmd_bootstrap` (230, `--force` gate at 236-237).
- `ssot-diagram/decision_hook.py` — full read via `codegraph node` (89 lines).
  Sibling-import block at lines 22-23 confirmed verbatim:
  `sys.path.insert(0, str(Path(__file__).resolve().parent))` then
  `import decision_index as di  # noqa: E402`.
- `manifest.json` (32 lines, 3 entries: `impact-analyzer`, `codegraph-gate`,
  `decision-index`).
- `_shared/design.md` (the only file in `_shared/`; no `*.py` exist — confirms the
  "defer extraction to Phase B" premise of ADR 0001).
- `docs/roadmap/skeleton-contracts.md` — Block 1 (incl. 1e module invariants),
  Block 4 (the frozen `diagram-model.json` surface: 4a hierarchy, 4b node fields,
  4c edges, 4d decision nodes, 4e resolvability), Block 5a/5b.
- `docs/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`
  (ADR 0001, accepted 2026-07-04; Phase B consolidation table enumerates the 11
  symbols).
- `docs/AI_artifacts/1_design/p3-diagram-model-extractor.md` (design, Revision 2
  post-red-team; the carried-forward Assumptions-to-verify #1-17).
- `docs/AI_artifacts/2_specs/p3-diagram-model-extractor.md` (the spec under
  verification).
- `CLAUDE.md` (repo + global). No STATE.md exists in this repo — its function is
  served by CLAUDE.md and skeleton-contracts.md (the constraint-preload was empty).

Database (read-only, `mode=ro&immutable=1` against
`~/all-projects/mkt_engine/.codegraph/codegraph.db`):
- `PRAGMA table_info(nodes)` — 21 columns confirmed.
- `PRAGMA table_info(files)` — 8 columns confirmed.
- `PRAGMA table_info(edges)` — 8 columns confirmed.
- Edge-kind counts (calls 1124, contains 961, imports 793, references 428,
  instantiates 17, implements 5).
- A1: nodes.id samples (function vs file vs hook sub-shapes).
- A2: nodes.signature text samples (CODE signatures, not hashes).
- A3: `requireEnv` in 2 files; multi-file qualified_name distribution.
- A11: edges.source/target sample rows (join to nodes.id).
- A13/FATAL1: 831/1124 calls have file: source; 689/902 incoming calls+references
  to fn/method/class have file: source (76%).
- A14/FATAL2: imports target dist = import 440 + real symbols 353 (function 151,
  interface 113, constant 49, type_alias 24, class 12, file 4); all 440
  file→import: edges are same-file.
- A15/SERIOUS1: references target dist = interface 348, type_alias 77, function 3
  (99% type references).
- A16/SERIOUS2: implements = 5 class→interface; instantiates = 17 file/function→class.
- A17/NOTE: 82 of 252 fn/method nanos (33%) have ZERO incoming calls+instantiates.
- A18: 0 backslash paths in `files`.
- A19: 439 nodes with `kind='import'` (the placeholder targets).
- A20: 10 class nodes across 10 files; no file has 2+ classes.
- A21: `edges.line` populated 100% for calls/imports/references/instantiates/
  implements; 0% for contains.
- A22: 0 nodes.file_path rows missing a files.path counterpart.

Curated index (read-only, `~/all-projects/mkt_engine/docs/decision-index.json`):
- 8 ADRs (ADR-0001..ADR-0008), 33 anchors, 33 verified, 33 with sig.
- `decision_index.py status` against the live DB: 33/33 FRESH, 0 not-fresh, exit 0.

## Spec Verification

Each assumption row is verified against the actual code or live DB. Every claim
was opened and read; no "pre-validated" label was trusted.

| ID | Spec Claim (paraphrased) | Verdict | Evidence |
|----|--------------------------|---------|----------|
| A1 | `nodes.id` is content-derived, not path-derived; sample `function:1160d09796260bc002cfa4023f655680`; `file:app/api/auth/logout/route.ts`. P3 must synthesize its own id. | ✅ Validated (with NUANCE) | Live DB query: function ids are `function:<32-hex>` (226 of 232 function-kind nodes); file-kind node ids are `file:<relpath>`. The exact sample string `function:1160d09796260bc002cfa4023f655680` is a real row. **NUANCE:** 6 of 232 function-kind nodes have path-derived `hook:<path>:<name>:<line>` ids (React hooks: `useGroupPoll`, `useFeedStore`, `useCanvasStore`, `useFillStore`, `useResizeStore`, `useGroupPollList`). The spec's prescription ("P3 synthesizes a path-derived id; never pass `nodes.id` through") is STILL CORRECT — the 6 hook ids already happen to be path-stable, but mixing content-hash and path-derived source ids in one model would be inconsistent, and the rule "never pass through" remains the right call. The spec's *rationale* ("one-line edit changes the id") is true for content-hash ids only; flag this nuance to the planner so the id-synthesis code comment does not over-claim. |
| A2 | `nodes.signature` holds CODE signature text like `(request: Request): Promise<NextResponse>`, NOT a sha256. Don't propagate it. | ✅ Validated | Live DB query: `nodes.signature` for kind=function/method holds text like `(request: Request): Promise<NextResponse>\|POST`, `(name: string): string\|requireEnv` — CODE signatures, not hashes. `decision_index.py:96-98` reads file hashes from `files.content_hash`, never `nodes.signature`. |
| A3 | `qualified_name` is NOT unique across the repo. `requireEnv` appears in both `lib/ai/llm/providers/openai-compat/index.ts` and `lib/storage/s3.ts`. | ✅ Validated | Live DB query: `requireEnv` confirmed in exactly those two files. Also `../../types` in 6 files, `../db`/`../storage`/`./_shared`/`./config` in 3 each — qualified_name non-uniqueness is pervasive. |
| A4 | `parse_ref('CapabilitySlot::listModels@lib/ai/image/index.ts')` → `('sym', 'CapabilitySlot::listModels', 'lib/ai/image/index.ts')`. | ✅ Validated | `decision_index.py:125-133`. `parse_ref` splits on the rightmost `@` (`rsplit("@", 1)`, so the path may itself contain `@`), requires both halves non-empty, returns `('sym', name, path)`. The example shape holds. Edge: if `ref` has no `@` and doesn't start with `file:`, `parse_ref` calls `die` (exit 2). |
| A5 | `anchor_status` returns `FRESH \| STALE \| ORPHANED \| AMBIGUOUS` (vocabulary via `current_sig`). | ✅ Validated | `decision_index.py:154-158` (`anchor_status` returns one of the four) + `136-151` (`current_sig` returns `('OK', sig)` / `(ORPHANED, None)` / `(AMBIGUOUS, None)`). Constants at line 48. `ORPHANED` and `AMBIGUOUS` short-circuit; `OK` is mapped to `FRESH` or `STALE`. No `SUPERSEDED` in this layer (it's emitted by the merge logic from the index's `supersedes` field — the spec's component 9 step 5). |
| A6 | `save_index` writes `json.dumps(doc, indent=2) + "\n"` with NO `sort_keys`. P3 must be stricter (`sort_keys=True`). | ✅ Validated | `decision_index.py:175-179`. Body is `tmp.write_text(json.dumps(doc, indent=2) + "\n")` then `os.replace(tmp, path)` — atomic write, no `sort_keys`, no `ensure_ascii`. P3's stricter writer is justified. (Note: P1 already does atomic temp+rename; the spec's component 12 leaves atomicity open — the planner may inherit P1's pattern.) |
| A7 | `cmd_bootstrap`'s `--force` gate refuses overwrite; message "exists — refusing to overwrite a curated index." | ✅ Validated | `decision_index.py:236-237`: `if out.exists() and not args.force: die(f"{out} exists — refusing to overwrite a curated index. Pass --force to reseed.")`. `--force` is `action="store_true"` (line 391). Exact gate shape. (`die` exits 2, not 1 — see Edge Cases.) |
| A8 | `_evaluate` returns `(rows, n_not_fresh)` where each row is `(did, ref, state)`. Pre-extract guard can reuse it. | ✅ Validated | `decision_index.py:290-299`. Returns `(rows, not_fresh)`; each row is `(did, a["ref"], state)` where state is one of the four from `anchor_status`. Leading-underscore name; sibling import (the same move `decision_hook.py` makes at line 64) is the established pattern. |
| A9 | `mkt_engine/docs/decision-index.json` is fully curated (8 ADRs / 33 anchors / all verified:true / all FRESH) as of 2026-07-04. | ✅ Validated | Live index: 8 ADRs (ADR-0001..ADR-0008), 33 anchors, 33 `verified:true`, 33 with `sig`. `decision_index status` against the live DB: "33/33 anchors FRESH; 0 need review", exit 0. The handoff's "0/25 verified, 4 STALE in ADR-0007" framing is stale; P3 ships against the curated baseline now. |
| A10 | File paths use forward slashes throughout; `fnmatch.fnmatch(relpath, glob)` works without OS-separator dance. P1 uses raw strings everywhere (no `os.sep`). | ✅ Validated | Live DB: 0 paths contain a backslash. `decision_index.py` grep for `os.sep`, `pathlib.*match`, `PurePath`, `os.path.sep` returns no matches. `fnmatch` is stdlib on all supported Pythons; works without normalization for this DB. |
| A11 | `edges.source`/`target` reference `nodes.id` (the content-hash id); P3 must join `edges` to `nodes` on `nodes.id` to recover file_path + qualified_name. | ✅ Validated | Live DB query: `edges.source`/`target` hold values like `file:app/api/auth/logout/route.ts` and `import:3414cac54eb3b1fdb06596bca2dce75f`, which are `nodes.id` values. Direction: `source` → `target` = source depends on target (the design's §Direction claim holds). The model `id` is path-derived and is NOT a DB join key. |
| A12 | "There is no `docs/adrs/` directory yet." (This was authored at design time.) | ✅ Validated (stale-at-design-time, resolved now) | `find docs/` shows `docs/adrs/` exists today with `0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`. The spec's A12 wording is "the repo has no `docs/adrs/` directory yet" — at design time that was true; A25 correctly notes ADR 0001 now supersedes the open question. No contradiction. |
| A13 | FATAL1: 831 of 1124 `calls` edges have `file:` source; 689 of 902 incoming calls+references to fn/method/class have `file:` source (76%). Block 4c only requires `sample_callers[file:line ×3]` (no symbol). | ✅ Validated | Live DB query. calls total = 1124, with file: source = 831 (74%). Incoming calls+references to fn/method/class = 902, with file: source = 689 (76%). Both numbers reproduce exactly. The "no symbol field" rule is contract-compliant (Block 4c only specifies `sample_callers[file:line ×3]`). The red-team fix is load-bearing and verified. |
| A14 | FATAL2: `imports` has two sub-shapes. 440 of 793 target an `import:` placeholder node (all 440 same-file); 353 target a real symbol (function 151, interface 113, constant 49, type_alias 24, class 12, file 4). | ✅ Validated | Live DB queries. imports target-kind distribution: `import` 440, function 151, interface 113, constant 49, type_alias 24, class 12, file 4 = 793 total. All 440 `file → import:` edges have `source.file_path == import:.file_path` (verified: 440 same-file, 440 total). The two sub-shapes must not roll together. The red-team fix is load-bearing and verified. |
| A15 | SERIOUS1: 348 of 428 `references` target `interface`, 77 `type_alias`, only 3 `function` (99% type-references). Excluded from `caller_count`. | ✅ Validated | Live DB query. references target dist: interface 348, type_alias 77, function 3 (sum = 428). Folding `references` into `caller_count` would rank functions by signature-type mentions, not incoming calls. The red-team fix is load-bearing and verified: `caller_count` is pinned to incoming `calls` + `instantiates` only. |
| A16 | SERIOUS2: `implements` = 5 edges, ALL `class → interface` (type relations); `instantiates` = 17 edges, `file`/`function → class` (call-deps). `instantiates` folds into `calls`; `implements` is dropped. | ✅ Validated | Live DB query. implements source/target kind: `class → interface` ×5 (all 5). instantiates: `file → class` ×8, `function → class` ×9 (= 17). Both confirmed exactly. Folding `instantiates` into `calls` (emit `kind: "calls"`) and dropping `implements` is contract-compliant (Block 4c/contract 6 freezes `{calls, imports, references}`). The red-team fix is load-bearing and verified. |
| A17 | NOTE: 82 of 252 fn/method nanos (33%) have ZERO incoming calls+instantiates edges; ties at zero need a deterministic secondary sort. Sort: caller_count DESC, qualified_name ASC, path ASC. | ✅ Validated | Live DB query. fn/method nano total = 252; zero-caller nanos = 82 (33%). Ties are common; without a secondary sort, the cap would be non-deterministic across runs (Python set/dict order). The spec's sort prescription is the correct fix and is required for the byte-determinism exit criterion (roadmap.md line 113). The red-team fix is load-bearing and verified. |
| A18 | mkt_engine paths use forward slashes throughout (A10) extends to ALL codegraph builds P3 will target — codegraph does not emit OS-separator paths on macOS/Linux. | ⚠️ Unverifiable (cross-build generalization) | Verified for the one DB P3 will target (mkt_engine: 0 backslash paths). The generalization "extends to ALL codegraph builds" CANNOT be verified from a single DB. The codegraph extractor is at `codegraph/` in this repo; whether it normalizes separators on Windows is a codegraph-internal question I did not deep-trace (it would require reading the codegraph extractor's path emission paths for Windows, which is out of scope for this P3 verification). The dispatch's C1 ("pilot = mkt_engine") means P3's golden test runs only against this DB; the falsifier ("a Windows codegraph build emitting backslashes") is real but does not block P3. Mark OPEN (human-authority: codegraph cross-platform behavior) for any future P3 retargeting decision. |
| A19 | `nodes.kind` vocabulary includes function/method/class/interface/type_alias/constant/file/import; the `import:` placeholder nodes have `kind='import'` (the dispatch key is `nodes.kind`, not `nodes.id` prefix matching). | ✅ Validated | Live DB. `nodes.kind` full vocab: import 439, function 232, file 148, constant 136, interface 92, method 20, type_alias 20, variable 12, class 10, property 6. All 439 `import:`-prefixed ids have `kind='import'`. So dispatch-on-`nodes.kind` works for the imports two-shape split. (Note: spec text said "440" placeholder edges/`import:` nodes — exact reconciliation: 440 edges target 439 distinct `import` nodes, because one `import` node is referenced by 2 edges. No contradiction.) |
| A20 | A "dominant class" exists when a file holds exactly ONE `class` node. The design claims mkt_engine has 10 class nodes across 10 files. | ✅ Validated | Live DB: exactly 10 `class` nodes across 10 distinct file_paths; no file has 2+ classes. The "dominant class" rule is well-defined for the pilot (every file with a class has exactly one). The spec's open decision (component 6: "a file with 2+ classes — micro = the file with no dominant class") is consistent with A20's pin to the single-class case. |
| A21 | `edges.line` column exists and holds the call/import/reference-site line (1-based). | ✅ Validated | Schema: `edges.line` is `INTEGER` (nullable). Population by kind: calls 1124/1124 non-null, imports 793/793, references 428/428, instantiates 17/17, implements 5/5, contains 0/961. So `line` is fully populated for every edge kind P3 reads AND fully null for `contains` (which P3 does not read as an edge anyway — it's the tree-parent relationship). `sample_callers[].line` will always have a value for calls/imports/references. The spec's component 8 open question ("what if `edges.line` is null for some kinds") is answered: it isn't, for the kinds P3 reads. |
| A22 | The `files` table contains every indexed file (`path` = repo-relative) and `nodes.file_path` joins to `files.path`. `files` is the authoritative file list. | ✅ Validated | Live DB: 148 distinct `nodes.file_path` values, 0 of them missing a `files.path` row. `files` table has 150 rows (148 source-tracked files + 2 root-level special paths `.claude/hooks/fal-spend-warn.py` and others — actually 150 distinct paths, all of which are the indexed surface; two file_paths in `nodes` are JSON config files that have a `files` row but no nodes). P3 building the micro set from `files.path` is correct. |
| A23 | `nodes.is_exported` / `nodes.docstring` columns exist (P1's `verify_schema` does NOT check them; P3's extended schema guard does). Both present and populated (may be null). | ✅ Validated | Schema: `is_exported` (INTEGER notnull=0), `docstring` (TEXT notnull=0) both exist. P1's `verify_schema` (lines 90-92) only checks `need_nodes = {name, qualified_name, file_path, start_line, end_line}` and `need_files = {path, content_hash}` — it does NOT check `is_exported`, `docstring`, `kind`, `signature`, `id`, `start_column`, `end_column`, `language`. P3's `_verify_model_schema` (component 4) extending P1's check is justified. Population: 153/252 fn/method exported, 123/252 with non-empty docstring. |
| A24 | The pilot DB at `~/all-projects/mkt_engine/.codegraph/codegraph.db` is the golden-test fixture source. CI does not need a fixture DB copy (skip-if-absent). | ✅ Validated (fixture strategy is sound) + ⚠️ OPEN (CI environment possession) | The live DB exists and opens read-only with `mode=ro&immutable=1` from this repo's tooling (verified: returns 150 for `COUNT(*) FROM files`). The golden-test fixture strategy (committed `mkt_engine.model.json` re-recorded only via `--update-golden`; tests run against the live DB read-only with `pytest.mark.skipif` on the DB path) is implementable. **OPEN:** whether the CI environment has the pilot repo checked out is NOT verifiable from this repo's code alone — it depends on CI configuration, which I did not inspect. Mark OPEN (human-authority: CI environment) — does not block spec; the skip-if-absent posture means CI without the DB still passes (the golden test is skipped, the hermetic determinism + red-team tests still run). |
| A25 | ADR 0001 is on disk and accepted; it supersedes design OQ-ADR-1. P3 deliverables list does NOT include writing a new ADR. | ✅ Validated | `docs/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` exists (verified via `find docs/adrs/`). Status: "Accepted (2026-07-04)". The ADR enumerates the exact Phase B `_shared/` consolidation targets (11 symbols with line numbers matching `decision_index.py`). P3 deliverables list correctly excludes "write ADR". |

### Extra assumptions I found while reading (not in the spec's A1–A25)

These were discovered during verification and are listed for completeness; none
invalidate the spec, but the planner should be aware.

| ID | Claim I checked | Verdict | Evidence |
|----|-----------------|---------|----------|
| E1 | `die()` exits with code 2, not 1. The spec's component 4 / contract C2 say "exit 1" for fail-loud cases (`bootstrap-config`'s "run `bootstrap-config` first", schema drift "refusing to guess"). | ⚠️ discrepancy in exit code convention | `decision_index.py:372-374` `die()` calls `sys.exit(2)`. P1 universally exits 2 on errors; the spec's text "exit 1" in contract C2 and component 12 is therefore internally inconsistent with P1's convention. **Not an assumption row** (A7's "exit 1 if the output exists" is the same wording drift). Suggested resolution (INPUT ONLY): the spec author picks one — either follow P1 exactly (`sys.exit(2)`, which `die()` already does) or document the divergence if P3 uses exit 1. Recommendation: mirror P1's `die()` (exit 2) for consistency across the ssot-diagram tool family. |
| E2 | `parse_ref` uses `rsplit("@", 1)` — the rightmost `@` is the separator, so a path containing `@` is preserved, but a qualified_name containing `@` would be split wrong. | ✅ verified behavior, worth noting | `decision_index.py:130`. Real impact: TS/JS qualified_names with `@` are rare (e.g. decorators), and the existing decision index's anchors use simple qnames. Not an assumption row; a planner note. |
| E3 | The mkt_engine repo has 15 top-level filesystem entries (8 dirs: `.claude, app, components, docs, lib, prisma, scripts, tests`; 7 top-level files like `docker-compose.yml`, `next.config.ts`, etc.). The spec's `bootstrap-config` seeds "one component per top-level dir". | ⚠️ design choice, not contradiction | Top-level files (no directory) would not get their own component under `glob = "<dir>/**"` and would land in `cmp-misc`. The design's handoff said "8 top-level dirs" — that count is correct for directories. The spec's component 5 "open decision" handles this implicitly (cmp-misc catches unmatched). Not blocking; the planner may decide whether top-level files deserve `cmp-root` or stay in `cmp-misc`. |

## Edge Cases & Silent Failure Modes

These are not assumption failures; they are behaviors the planner should not be
surprised by.

- **`die()` exit code is 2, not 1.** P1's `die()` (`decision_index.py:372-374`)
  exits 2. The spec's contract C2 and component 4 say "exit 1" for fail-loud
  cases. This is a wording drift; mirroring P1 (`die()`, exit 2) is the consistent
  choice. See E1 above.

- **`nodes.id` is a mix of content-hash and path-derived forms.** 226/232
  function-kind nodes have `function:<32-hex>` content-hash ids; 6 have
  `hook:<path>:<name>:<line>` path-derived ids (React hooks). The model rule
  "synthesize your own id; never pass `nodes.id` through" is correct for BOTH
  forms — content-hash ids change on edit (bad for narrative pinning), and
  path-derived ids would collide with P3's own `nano:<qualified_name>@<relpath>`
  scheme (kind-pollution). The planner should ensure the id-synthesis code path
  never branches on the source id's prefix (which would couple P3 to codegraph's
  id-emission quirks). See A1's NUANCE.

- **`edges.line` is null for `contains`, fully populated for everything else.**
  P3 does not read `contains` (it is the tree-parent relationship, expressed via
  `children[]`/back-pointers). For the kinds P3 reads (calls, imports, references,
  instantiates, implements), `line` is non-null in 100% of rows. The spec's
  component 8 open decision ("what if `edges.line` is null for some kinds — skip
  vs null vs 0") is answered: it isn't null for any kind P3 reads. The spec can
  pin "always read `line`; if a future codegraph build makes it nullable for calls
  etc., the schema guard (component 4) catches the build difference, not the
  roll-up."

- **`metadata` JSON column exists on `edges`** (schema column 4). The spec's
  component 4 open decision explicitly chooses "no, P3 reads `edges.line`, not
  `metadata`". Verified: `line` is a top-level column, so the choice is sound.

- **`save_index` already does atomic temp+rename** (`decision_index.py:175-179`).
  The spec's component 12 leaves atomicity open ("the design does not require a
  temp-file-rename dance, but the planner may add one"). P1's pattern is right
  there to inherit; the planner should mirror it for P3's writer.

- **`anchor_status` returns `AMBIGUOUS` when a `qualified_name@path` anchor's
  symbol resolves to >1 row in `nodes`.** This is the multi-definition case (e.g.
  a method overloaded in the same file). The spec's "worst-case across anchors"
  reduce (`ORPHANED > STALE > AMBIGUOUS > FRESH`) treats it as worse than FRESH,
  which is conservative and correct. No special handling needed; the planner just
  needs to include `AMBIGUOUS` in the worst-case ordering.

- **`bootstrap-config --force` gate mirrors `cmd_bootstrap`'s wording.** The
  spec's A7 quotes "exists — refusing to overwrite a curated index." The actual
  P1 code says "exists — refusing to overwrite a curated index. Pass `--force` to
  reseed." The spec omits the "Pass `--force` to reseed" suffix in A7 but adds it
  back in component 13. Mirror the full P1 string verbatim to keep the tools'
  user-facing contract identical.

## Dependencies & Coupling

- **P3 imports `decision_index` as a sibling** (the ADR 0001 decision). The
  import seam is exactly `decision_hook.py:22-23` (verified verbatim). P3 becomes
  the *third* caller of P1's recipe (P1 itself, the hook, now P3) until Phase B's
  `_shared/` cutover. The ADR's "Phase B consolidation targets" table enumerates
  the 11 symbols and their line numbers; all 11 are at the cited lines
  (find_db 53, open_db 73, verify_schema 85, file_content_hash 96, symbol_spans
  101, slice_hash 115, parse_ref 125, current_sig 136, anchor_status 154,
  load_index 163, _evaluate 290).

- **`di._evaluate` is a "private" (leading-underscore) symbol.** P3 reaching
  across it is the same move `decision_hook.py` makes at line 64
  (`di._evaluate(con, root, hits)`). Acceptable per the ADR; documented so a
  future reader does not flag it as a leak.

- **P3 reads codegraph DB columns P1 does not check.** P1's `verify_schema`
  (lines 90-92) checks only `nodes.{name, qualified_name, file_path, start_line,
  end_line}` + `files.{path, content_hash}`. P3 also reads `nodes.{kind, id,
  docstring, is_exported, signature}` and `edges.{source, target, kind, line,
  metadata}`. The spec's component 4 extended schema guard is required and
  justified by R4. Verified: every column P3 reads exists in the live DB schema.

- **`diagram-model.json` consumers** (P5 renderer + plan-visualizer + P4
  narratives worklist) are not built yet; they consume the OUTPUT, not the import
  seam. The Block 4 frozen contract is the seam they will read.

## Extension Points

- **Adding a new model edge kind** (e.g. `implements` if P5 wants type relations):
  the contract-6 freeze is `{calls, imports, references}`. Adding `implements`
  is a deliberate Block 4c amendment, not a P3 change. The spec's OQ-Block4c-1
  correctly defers this. Today the roll-up dispatches on `edges.kind` in
  `graph_model.py`'s `roll_up_edges`; extending means adding a case + a model kind.

- **Adding a new node kind** (e.g. `variable`, `property` — both already in the
  codegraph `nodes.kind` vocab per A19): P3's component grouping (component 5) and
  micro/nano selection (components 6-7) currently pin to `function`/`method`
  nanos and `class`-dominant micros. `variable` and `property` nodes are silently
  not selected as nanos today; whether to surface them is a future decision, not
  blocked by the spec.

- **Adding a new anchor ref shape** beyond `file:<path>` and `<qname>@<path>`
  (e.g. `path::symbol` for plan manifests): Block 1a says notation parsing stays
  per-tool. `di.parse_ref` (P1) handles the two decision-index forms; P3 reuses
  it. New forms belong to a new tool's notation parser, not here.

- **Streaming edge roll-up.** mkt_engine has 2345 edges in calls+imports+
  references (sum 1124+793+428). Trivial for in-memory roll-up. The spec's
  OQ-PERF-1 defers streaming; revisit only if a real repo's `extract` takes more
  than a few seconds.

## Open Questions

These cannot be resolved from code or DB alone and are deferred to the next
human-authored step (the spec's own Open Questions list captures most of these
already — only ones I newly surface are marked NEW).

1. **(NEW) Folder name drift: this artifact is at `3_factual-code-verification/`
   per the dispatch, but the SKILL.md folder-rename note says the canonical
   folder is now `5_factual-code-verification/`.** The dispatch's path is human
   authority and was followed verbatim. The repo has both `3_factual-code-verification/`
   (this file) and NO `5_factual-code-verification/` directory today. The repo
   maintainer should reconcile: either (a) update the skill's folder-rename note
   to match this repo's numbering (3_ = the "spec-verification" stage here), or
   (b) rename this folder to 5_ to match the skill. I did not rename — folder
   structure is human-authority territory. **OPEN (human-authority: repo artifact
   numbering convention).** I wrote here because the dispatch told me to, not
   because I resolved this.

2. **A18 — does codegraph emit OS-separator paths on Windows?** Verified NO for
   the one pilot DB (mkt_engine, all forward slashes). Verifying for all builds
   would require reading codegraph's path-emission code, which is the codegraph
   tool's responsibility (in `codegraph/src/`), out of scope for P3 verification.
   The C1 pilot = mkt_engine constraint means P3 is fine today. **OPEN
   (human-authority: codegraph cross-platform behavior).** Resurface only if P3
   is ever retargeted to a Windows-codegraph build.

3. **A24 — does the CI environment have the pilot DB checked out?** Not
   verifiable from this repo's code; depends on CI configuration, which I did
   not inspect. The skip-if-absent posture in the spec's component 14 open
   decision makes this non-blocking (CI without the DB still passes; the golden
   test is skipped, the hermetic tests run). **OPEN (human-authority: CI
   environment possession of pilot DB).** The spec author / owner decides.

4. **(NEW) E1 — should P3 use exit code 2 (P1's `die()` convention) or exit code
   1 (the spec's contract C2 / component 4 wording)?** Mirroring P1 (exit 2) is
   the consistent choice across the ssot-diagram tool family. **OPEN
   (human-authority: tool exit-code convention).** The spec author resolves this
   before /plan; suggested resolution: use `die()` (exit 2) verbatim.

## Technical Debt Spotted

- **P1's `verify_schema` does not check `nodes.kind`, `nodes.id`,
  `nodes.signature`, `nodes.docstring`, `nodes.is_exported`, or any `edges`
  columns.** This is intentional (P1 only verifies what it reads), but it means
  P3's `_verify_model_schema` (component 4) is doing real work that P1 doesn't.
  Verified: all these columns exist in the live DB and are populated, so the
  guard will pass today; the guard is the spec's R4 mitigation for codegraph
  schema drift.

- **`nodes.id` for React hooks uses a different prefix (`hook:`) than the kind
  suggests (`function`).** The codegraph build emits `function` as the kind but
  `hook:<path>:<name>:<line>` as the id for React hooks. This is a codegraph
  emission quirk that P3 should NOT depend on — the spec's "synthesize your own
  id; never pass `nodes.id` through" rule is the correct defense. Worth a
  code comment in P3's id-synthesis explaining why dispatch-on-source-id is
  forbidden (so a future contributor does not "simplify" by reading `nodes.id`).

- **`save_index`'s atomic write (temp + rename) is not in the spec's component 12
  determinism section, but P1 already does it.** The spec's writer (component 12)
  leaves atomicity open; inheriting P1's pattern is the lowest-risk choice and
  avoids half-written files on a future P6 hook re-extract. Not a bug today; a
  "planner should mirror P1" note.

## Invalidated Assumptions

None. All 25 assumptions in the spec's table (A1–A25) are validated. The 5
load-bearing red-team fixes (A13–A17) all reproduce their counts exactly against
the live DB. The 5 carried-forward design revisions (also A13–A17) are verified
individually below.

### A13–A17 individual verdicts (load-bearing — verified at full depth)

- **A13 (FATAL1) — ✅ Validated.** 831/1124 `calls` edges have `file:` source
  (74%); 689/902 incoming calls+references to fn/method/class have `file:` source
  (76%). Both numbers reproduce exactly. The "no `symbol` field on
  `sample_callers`" rule is contract-compliant (Block 4c specifies only
  `sample_callers[file:line ×3]`). Implementing this fix literally will produce
  correct behavior.

- **A14 (FATAL2) — ✅ Validated.** imports target distribution: `import:` 440 +
  real symbols 353 (function 151, interface 113, constant 49, type_alias 24,
  class 12, file 4) = 793 total. All 440 `file → import:` edges are same-file
  (`source.file_path == target.file_path`). The two sub-shapes are real and
  distinct. Dispatch-on-target-`kind` is the correct roll-up rule.

- **A15 (SERIOUS1) — ✅ Validated.** references target distribution: interface
  348, type_alias 77, function 3 (sum = 428, 99% type references). Excluding
  `references` from `caller_count` is correct; keeping them in the model
  `edges[]` array is contract-compliant (Block 4c includes them).

- **A16 (SERIOUS2) — ✅ Validated.** implements = 5 edges, all `class → interface`
  (type relations); instantiates = 17 edges (`file → class` 8, `function →
  class` 9, genuine call-deps). Folding `instantiates` into `calls` and dropping
  `implements` is contract-compliant (contract 6 freezes `{calls, imports,
  references}`).

- **A17 (NOTE) — ✅ Validated.** 82 of 252 fn/method nanos (33%) have ZERO
  incoming `calls`+`instantiates` edges. The deterministic secondary sort
  (`caller_count` DESC, `qualified_name` ASC, `path` ASC) is required for the
  byte-determinism exit criterion. Without it, the cap is non-deterministic
  across runs (Python set/dict order).

No Q4 conflict diagram is needed — no assumption required redesign. All fixes
are mechanical/verified.

## Self-review pass

1. **Unsupported claims?** Removed. Every verdict cites a file:line from
   `decision_index.py` or a query result against the live DB. The two ⚠️
   Unverifiable rows (A18, A24's CI-environment half) explicitly state what was
   checked and why the rest can't be answered from code alone.

2. **Gaps disguised as confidence?** The A1 nuance (6 hook-shaped ids) is flagged
   explicitly rather than glossed; the planner sees it as a NUANCE, not silent
   confidence.

3. **Spec Verification completeness?** All 25 spec assumptions (A1–A25) are
   covered, plus 3 extras (E1, E2, E3) I found while reading. Every component
   (1–14) in the spec was reviewed; the only component-level concerns surface as
   Open Questions (folder name, exit code) and the planner-facing notes (atomic
   write inheritance).

4. **Missing downstream impact?** P4/P5 contracts are addressed (the Block 4/5
   frozen contracts are verified; the two-id reality and signature pinning rules
   hold; the worst-case reduce vocabulary is confirmed).

5. **Contradictions with existing research?** No prior factual-code-verification
   file existed in this repo (the `3_factual-code-verification/` folder was empty;
   no `5_` folder exists). No contradictions to flag.

6. **Voice rule compliance?** Every section leads with a plain-English sentence
   before any file:line or query citation.

✅ Factual code verification complete → docs/AI_artifacts/3_factual-code-verification/p3-diagram-model-extractor.md
Spec assumptions: 23 ✅ Validated  2 ⚠️ Unverifiable (A18 cross-build, A24 CI-env)  0 ❌ Invalidated
A13 ✅ Validated  A14 ✅ Validated  A15 ✅ Validated  A16 ✅ Validated  A17 ✅ Validated
Open questions remaining: 4 (folder naming, A18 cross-build, A24 CI-env, E1 exit code)

Ready for: /plan p3-diagram-model-extractor
