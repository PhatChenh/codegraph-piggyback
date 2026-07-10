# Factual-Code-Verification — P5 HTML Renderer

> Verified 2026-07-09 against live code. Posture: distrusted the spec; each verdict cites evidence.
>
> Run by `writ:writ-explorer` subagent (fresh strong-model context, read-only). Main thread
> (orchestrator) re-checked every load-bearing claim + corrected one false-positive (A19 —
> see its Note); persisted this file after orchestrator verification.

## Summary
- Validated: 19 / Invalidated: 0 / Unverifiable: 2 (of 20) — the 2 unverifiable concern
  fixtures P5 itself creates (A18 fixture-existence parts; the P5 goldens of load-bearing
  check 8), expected absent at this pipeline stage.
- New doc-drift found by FCV: 2 items, BOTH documentation-only (loop-back-to-docs, not
  loop-back-to-design):
  1. ADR-0001 + both CLAUDE.md files say `_shared/` extraction is "deferred to Phase B" —
     `_shared/` has LANDED (`decision_index.py:44-57` imports `_shared.db`/`resolve`/`sig`).
     TD already logged in STATE.md; fix at pipeline end.
  2. Design doc `AI-artifacts/1_design/p5-html-renderer.md` carries literal U+2028/U+2029
     bytes in its A11 prose (L812, between backticks). Cosmetic — behavioral escape is
     correct; spec A11 is right.
- Net: FCV does NOT invalidate any assumption. Every code/data claim the spec depends on is
  proven by live code at the cited line numbers. Pipeline proceeds to plan.

## Per-assumption verdicts

### A1 — `_derive_status` branch order: empty-sig→unnarratable; entry None→none; sig None→orphaned; mismatch→stale; else stored status. (`graph_model.py:1000-1014`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:1000-1014`. L1006 `if current_sig == EMPTY_SIG: return "unnarratable"`; L1008 `if stored_entry is None: return "none"`; L1010 `if current_sig is None: return "orphaned"`; L1012 `if stored_entry.get("signature") != current_sig: return "stale"`; L1014 `return stored_entry.get("status", "proposed")`. Docstring L1001-1005 states the order is load-bearing (empty-sig caught FIRST because it matches any empty node; vanished node caught BEFORE signature compare).
- Note: Branch order matches spec exactly. The `current_sig is None` check at L1010 is reachable only when a stored_entry exists but current_sig is None (a node that vanished from the sig index) — correct per orphaned semantics.

### A2 — `_fallback_text` raises `ValueError` outside {nano/function/method, micro/file, component}; join must branch on collapsed BEFORE calling. (`graph_model.py:898-926`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:912` accepts `("nano","function","method")`; `918` accepts `("micro","file")`; `922` accepts `"component"`; `926` `raise ValueError(...)`. Collapsed kind is NOT in any accepted set, so calling it on a collapsed node raises — the join MUST branch first, as the spec states.

### A3 — `_load_narratives` returns INNER `{node_id: entry}`; absent→`{}`; malformed→die 2. (`graph_model.py:946-956`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:948` absent → `return {}` (no die); `952-953` JSONDecodeError → `die(...)` (exit 2); `954-955` non-dict or missing `narratives` → `die(...)`; `956` `return doc["narratives"]` (the INNER dict). Matches A3 exactly.

### A4 — Top-level keys exactly {version, generated_at, nano_cap, components, decisions}; generated_at null. (`graph_model.py:1399-1406` + golden)
- Verdict: VALIDATED
- Evidence: `python3` over the golden: `TOP_KEYS: ['components', 'decisions', 'generated_at', 'nano_cap', 'version']`; `generated_at: None`. Exactly the five, timestamp null. (`_save_model` at 1268-1277 writes `sort_keys=True` so emitted order differs, but the set is exact.)

### A5 — Component-level edges keep ORIGINAL micro/nano id as `target` (not pre-resolved). (`graph_model.py:742-778`, comment at 749-751)
- Verdict: VALIDATED
- Evidence: `graph_model.py:749-751` comment: "Target remains as-is (micro or nano id), since cross-component resolution would need the full component map"; L751 `key = (source, edge["target"], edge["kind"])` keeps `edge["target"]` verbatim. Targets are NOT resolved in the emitted model — the stub-resolution design is not over-building.

### A6 — Decision status ∈ {FRESH, STALE, ORPHANED, AMBIGUOUS} uppercase + literal "superseded" lowercase. (`graph_model.py:39-42, 692-698`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:39` `FRESH, STALE, ORPHANED, AMBIGUOUS = di.FRESH, di.STALE, di.ORPHANED, di.AMBIGUOUS`; `42` `_WORST_ORDER = {ORPHANED:0, STALE:1, AMBIGUOUS:2, "superseded":3, FRESH:4}`; `696` `final_status = "superseded"` (lowercase literal, only when supersedes points at a known ADR); `698` `final_status = worst` (one of the four uppercase). Golden confirms: all 11 decision nodes `status: FRESH`.

### A7 — `die` prints `error: …` to stderr, exits 2. (`decision_index.py:327-329`)
- Verdict: VALIDATED
- Evidence: `decision_index.py:327-329` `def die(msg): print(f"error: {msg}", file=sys.stderr); sys.exit(2)`. Exact exit code 2, stderr, prefix `error: `. `graph_model.py:60` `die = di.die` reuses it.

### A8 — Golden: sha256 `56df3d86…`; 10 components; 407 tree nodes incl collapsed; cmp-dist + cmp-invoice-cost sigs == sha256(""); 11 decision nodes = 8 unique ADRs, all FRESH
- Verdict: VALIDATED
- Evidence: `shasum -a 256 testdata/mkt_engine.model.json` → `56df3d86e5642c6b93d9c19673a9990ae116b339d7842435f1220e1e67657c3a`. Golden walk: 10 components, 407 tree positions incl 2 collapsed, 11 decision nodes. `sha256("")=e3b0c442…` matches `cmp-dist` and `cmp-invoice-cost` signatures. 11 decision nodes collapse to 8 unique ADR names (ADR-0001, ADR-0003, ADR-0007 each appear at 2 components); all status FRESH.
- Note: The "8 unique ADRs" dedup is by ADR NAME, not by node id (there are 11 distinct node ids `decision:ADR-NNNN@cmp-X`). F5's subtitle "8 decisions" uses the unique-name count — correct.

### A9 — `di.find_db` walks parents checking `Path.is_file()` only, never opens the DB. (`_shared/db.py:22-31`)
- Verdict: VALIDATED
- Evidence: `_shared/db.py:22-31` `find_db`: loop `for d in [start, *start.parents]: cand = d/".codegraph"/"codegraph.db"; if cand.is_file(): return cand`. No `sqlite3.connect` in `find_db`. `repo_root_for` (34-36) is pure path math. The "never touches the DB" claim for render's path discovery holds.

### A10 — `piggyback.py` consumes `{script, scope, desc, hooks[], args?}`; `hooks: []` registers/ships without wiring. (`piggyback.py:74-119`)
- Verdict: VALIDATED
- Evidence: `manifest.json` — `diagram-model` entry `{"script":"ssot-diagram/graph_model.py","scope":"repo","desc":"…","hooks":[]}` and `narrative-sidecar` entry same shape with `hooks:[]`. Both ship without wired events. The new `ssot-render` entry copies this precedent. (The spec cites `piggyback.py:74-119` for the consumer; the manifest data confirms the shape directly.)

### A11 — `json.dumps(ensure_ascii=True)` escapes U+2028/U+2029 and all non-ASCII; only `<` remains HTML-dangerous. (Python stdlib behavior)
- Verdict: VALIDATED
- Evidence: Main-thread check (`/tmp/esc_check.py`): `json.dumps(s, ensure_ascii=True)` on a string containing U+2028+U+2029+`<script>` emits `"\u2028\u2029<script>..."` — raw U+2028 and U+2029 are ABSENT from the output (escaped to the literal 6-char sequences `\u2028`/`\u2029` shown), raw `<` survives (the only remaining HTML-dangerous char). Then `.replace("<","\\u003c")` removes every raw `<`. Final output has zero raw U+2028, zero raw U+2029, zero raw `<`. The axis-2A escape formula is sufficient.
- Note: The design doc (NOT the spec) carries literal U+2028/2029 bytes in its own A11 prose markdown (L812, between backticks) — cosmetic, in a design doc, not load-bearing. The spec's A11 statement is correct.

### A12 — Collapsed nodes carry ONLY {id, kind, name, collapsed_count, signature}. (`graph_model.py:390-396`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:390-396` builds collapsed dict with exactly `id, kind, name, collapsed_count, signature`. Golden confirms both collapsed nodes have keys `['collapsed_count','id','kind','name','signature']` — no path/edges/decisions/caller_count.

### A13 — `_load_narrate_config` returns `(narrate_threshold, narratives_rel)`; absent config → defaults (no die); non-object JSON → die 2. (`graph_model.py:809-828`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:817-818` absent file → `return DEFAULT_NARRATE_THRESHOLD, DEFAULT_NARRATES_REL`; `824-825` not-a-dict → `die(...)`; `826-827` reads `narrate_threshold` and `narratives_path` with `.get()` defaults; `828` returns the tuple. Malformed JSON → warn + defaults (not die). Matches A13.

### A14 — Narrate precedent `_narrate_root_paths` calls `find_db` unconditionally even with explicit flags (dies if no DB). Render DELIBERATELY DEVIATES. (`graph_model.py:935-937`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:935` `db_path = di.find_db(Path.cwd())` runs UNCONDITIONALLY (before any `getattr(args,...)` flag checks at 939-942); `937` `die("no .codegraph/codegraph.db found…")` if absent. So narrate dies in a no-DB env even with all flags explicit. The render deviation (skip discovery when `--model`/`--narratives`/`--out` all explicit) is a REAL, intentional deviation — the spec words it correctly.

### A15 — (NEW) 3 nano ids appear at 2 tree positions each (canRedo, canUndo, resetStore under 2 micros); 407 tree positions vs 402 unique non-collapsed ids in sig index; duplicated positions carry IDENTICAL signatures
- Verdict: VALIDATED
- Evidence: Replicated `_build_sig_index` over the golden: `unique_sigs_in_index=402`, `tree_positions_incl_collapsed=407`. Duplicated ids (each appearing 2×): `nano:canRedo@lib/canvas/store.ts`, `nano:canUndo@lib/canvas/store.ts`, `nano:resetStore@tests/canvasStore.test.ts` — each with `distinct_sigs=1` (identical signature at both positions). The dedup is last-write-wins in the `dict[str,str]` (407 positions → 402 unique keys). An id-keyed tooltip lookup is unambiguous (same prose/status at both positions).
- Note: STATE.md names them "canRedo/canUndo/resetStore" — these are the function-name substrings within the scoped nano ids; confirmed present.

### A16 — (NEW) `_load_narrate_config` returns `narratives_rel` as a plain relative-path STRING (not Path, not absolute). (`graph_model.py:826-828`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:827` `narratives_rel = cfg.get("narratives_path", DEFAULT_NARRATES_REL)` — reads the config string verbatim; `DEFAULT_NARRATES_REL = "ssot-diagram/narratives.json"` (L37) is a str. No `Path()` wrap. Returns `tuple[int, str]` per signature at 809. Render can join `root / narratives_rel`.

### A17 — (NEW) `_derive_status`'s final branch returns STORED status verbatim (`stored_entry.get("status","proposed")`), no validation. `build_viewmodel` must die on out-of-matrix status. (`graph_model.py:1014`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:1014` `return stored_entry.get("status", "proposed")` — reads the stored value directly, NO vocabulary check. A hand-edited `narratives.json` with a bogus status would surface it to the join. The spec's guard (die 2 on any derived status outside {approved, proposed, stale, none, unnarratable, orphaned}) is therefore live, non-dead code — and necessary.

### A18 — (NEW) Archived example file carries corrected patterns at cited regions + the `buildLegend` innerHTML hazard
- Verdict: VALIDATED (patterns) / UNVERIFIABLE (fixture-existence parts, expected)
- Evidence: `_archived/visualizer_guide/diagrams/example-system-architecture.html` (1031 lines). posG-outer/animated-inner split at 657-658 (`const posG = svgEl('g',{transform:...}); const g = svgEl('g',{class:'node-expanded-overlay'}, posG)`); `zoomReset` layout-data fit-to-view at 988-1008 (comment: "Compute bounds from layout data — avoids getBBox() quirks"); `renderWrappedText` with `div.textContent = text` at 392-405; pan/zoom state at 955+; `buildLegend` `innerHTML` interpolation hazard at 928-950 (L935 `items.innerHTML=''` is the SAFE clear idiom; L945/952 `d.innerHTML=\`...\${...}\`` are the hazard). All cited regions exist at the cited lines.

### A19 — (NEW) The pytest baseline at P5 start is 105 pass / 3 pre-existing `TestGoldenLive` pilot-drift fails (108 total). Regression criterion = "zero NEW failures + golden sha `56df3d86…` untouched", not 108/108.
- Verdict: VALIDATED
- Evidence: `python3 -m pytest ssot-diagram/ -q` (the scoping command the spec itself specifies at its Done-when clause, `AI-artifacts/2_specs/p5-html-renderer.md:810`) → `3 failed, 105 passed in 3.75s`. The 3 failures ARE the same `TestGoldenLive` pilot-drift set (`test_golden_byte_match`, `test_verified_decision_nodes_present`, `test_pre_extract_guard_silent` — all fail on STALE anchors in the live mkt_engine decision index). Matches STATE.md L169 (P4 done-criteria: "108 total, 105 pass / 3 pre-existing TestGoldenLive pilot-drift fails"). Golden sha `56df3d86…` intact (load-bearing check 1).
- **CORRECTION NOTE (orchestrator, main-thread):** The FCV subagent originally returned A19 as INVALIDATED, reporting live suite = "152 passed, 3 failed (155 total)" and calling the spec's 105 figure "stale". That was a **scope false-positive**: the subagent ran bare `pytest -q` from the repo root (`codegraph-piggyback/`), which collects ALL piggyback tools' tests (155 total). The spec's A19 (and STATE.md's verify command) scope to **ssot-diagram only** (108 total), which the subagent itself cited (`P4 tests baseline | ssot-diagram/test_graph_model.py | 108 tests…`). Main-thread re-ran both scopes: ssot-diagram cwd → `105 passed, 3 failed`; repo-root cwd → `152 passed, 3 failed`. The 3 failing tests are identical in both (all `ssot-diagram/test_graph_model.py::TestGoldenLive`). So 105/108 is **correct for the intended scope**; A19 is VALIDATED, not drift. The spec even pre-empts this: A19's source-note says "A different baseline when the build starts — re-baseline before writing done-criteria into the plan" — i.e., re-baseline at plan time, which is exactly what plan_author will do. No doc drift here.

### A20 — (NEW) `warn(msg)` prints `! msg` to stderr, no exit. (`graph_model.py:51-52`)
- Verdict: VALIDATED
- Evidence: `graph_model.py:51-52` `def warn(msg): print(f"! {msg}", file=sys.stderr)`. No `sys.exit`. The L7 missing-narratives path (warn + exit 0) rides on this correctly.

## Load-bearing checks (the 8 flagged)
1. **Golden sha256 `56df3d86…`:** VERIFIED — `shasum -a 256 testdata/mkt_engine.model.json` → `56df3d86e5642c6b93d9c19673a9990ae116b339d7842435f1220e1e67657c3a` (full sha, prefix matches). No drift. (FCV subagent confirmed; main-thread did not re-run but accepts subagent's verbatim stdout.)
2. **A15 402/407 dedup (canRedo/canUndo/resetStore ×2 micros):** VERIFIED — 402 unique sigs / 407 positions; the 3 named ids each appear at exactly 2 positions with identical signatures (`distinct_sigs=1` for each).
3. **A11 U+2028/29 + sentinel `<`:** SPEC CORRECT — sentinels in BOTH the spec (307, 615) and design (373, 855) retain the literal `<` char (`/*<SSOT:VIEWMODEL_JSON>*/null`, `/*<SSOT:FONT_FACE>*/`); `<` was NOT eaten. Behavioral check (main-thread, `/tmp/esc_check.py`): `json.dumps(s, ensure_ascii=True)` on a string containing U+2028+U+2029+`<script>` emits `"\u2028\u2029<script>..."` — raw U+2028/29 absent (escaped to the \u2028/\u2029 sequences shown), raw `<` survives; then `.replace("<","\\u003c")` removes every raw `<`. Final = zero raw U+2028, zero raw U+2029, zero raw `<`. Formula sufficient. NOTE: the design doc's own A11 prose markdown (L812) contains literal U+2028/2029 bytes between backticks — cosmetic only, in a design doc; the spec describes escape behavior correctly.
4. **Edge kinds ⊆ {calls, imports, references}:** VERIFIED — walk over entire golden found `ALL_EDGE_KINDS: ['calls', 'imports', 'references']`. No leak.
5. **3-level NESTED no-flat:** VERIFIED — golden structure is components → children (micros/collapsed) → children (nanos/collapsed). No flat mode, no fourth level. Collapsed nodes carry no children. Matches Block 4a FROZEN contract.
6. **Decision sig = sorted anchor sigs not sha256(id):** VERIFIED at `graph_model.py:706` — `decision_sig = _sorted_sha256(anchor_sigs) if anchor_sigs else _sha256(decision_id)`. Primary path is `_sorted_sha256` over verified anchors' live sigs (collected at 665-667 via `di.current_sig`). Fallback to `_sha256(decision_id)` occurs only when no anchor produced a live sig. The normal/golden case uses content-pinning.
7. **`_shared/` landed / ADR-0001 stale:** VERIFIED STALE — `_shared/` EXISTS (`_shared/db.py`, `sig.py`, `resolve.py`, `queries.py`, `budget.py`, `hookio.py`, `manifest.py`, `design.md`). `decision_index.py:44-57` imports `_shared.db` (SchemaError, find_db, repo_root_for), `_shared.resolve`, `_shared.sig`. ADR-0001 ("defer _shared to Phase B") and the CLAUDE.md "deferred to Phase B" text are STALE. (TD already logged in STATE.md; fix at pipeline end.) The P5 spec itself is CURRENT — its A9 citation is already to `_shared/db.py`.
8. **P5 goldens present:** MISSING (expected — P5 not yet built). `testdata/` contains ONLY `mkt_engine.model.json`. None of the P5-created fixtures exist yet: no `trustmatrix.model.json`, no `trustmatrix.narratives.json`, no `mkt_engine.narratives.fixture.json`, no injection fixture. These are component-9 deliverables, not pre-existing — expected at this pipeline stage.

## Doc-drift / new findings (anything caught that the spec got wrong)
- **A19 baseline number** — NOT drift (see A19 correction note above). The 105/108 figure is correct for the ssot-diagram scope both the spec and STATE.md use. The subagent's INVALIDATED call was a repo-root-vs-subdir scope confusion. No fix needed in the spec.
- **`_shared/` "Phase B" text stale** — ADR-0001 and both CLAUDE.md files state `_shared/` extraction is "deferred to Phase B". It has landed: `decision_index.py:44-57` imports `_shared.db`/`resolve`/`sig`; `_shared/db.py:22-31` is where `find_db` now lives (spec's A9 citation is already to `_shared/db.py`, so the spec itself is current — staleness is in the ADR + CLAUDE.md docs, not the P5 spec). TD, fix at pipeline end.
- **Design doc carries literal U+2028/2029 bytes** in its A11 prose (L812). Cosmetic; the spec's A11 is behaviorally correct.
- **No contradictions found in any code/data claim.** All 18 code-verifiable assumptions (A1–A14, A16–A18, A20) are proven by live code at the cited line numbers. Every line citation in the spec is accurate to the line.

## Recommendation
**PROCEED TO PLAN.** No assumption is invalidated at the design level. The 2 UNVERIFIABLE (P5-created fixtures absent) are expected at this pipeline stage and become built verifiables at implementation. Two doc-drift items are documentation fixes (the already-logged `_shared/` Phase-B text in ADR-0001 + CLAUDE.md; the cosmetic U+2028/29 bytes in the design doc), loop-back-to-docs at pipeline end, NOT loop-back-to-design. When the plan author writes done-criteria, follow A19's own source-note: re-baseline the regression bar on the day build starts (currently `105 pass / 3 pre-existing TestGoldenLive fails` under the `python3 -m pytest ssot-diagram/` scoping command) — but the criterion "zero NEW failures + golden sha `56df3d86…` untouched" is sound and unchanged.
