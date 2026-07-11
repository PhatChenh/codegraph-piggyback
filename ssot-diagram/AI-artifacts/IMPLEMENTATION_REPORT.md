# Step 9 — Fixtures Implementation Report

**Plan:** `ssot-diagram/ai-artifacts/4_plans/p5-html-renderer.md` (Step 9)
**Status:** DONE — 4 fixture files committed, all verify commands pass

## Files changed

| Path | Status |
|---|---|
| `ssot-diagram/testdata/mkt_engine.narratives.fixture.json` | NEW |
| `ssot-diagram/testdata/injection.narratives.json` | NEW |
| `ssot-diagram/testdata/trustmatrix.model.json` | NEW |
| `ssot-diagram/testdata/trustmatrix.narratives.json` | NEW |

No other files touched. `ssot-diagram/testdata/mkt_engine.model.json` and
`ssot-diagram/graph_model.py` are byte-unchanged.

## L3 row coverage (per-fixture)

### `mkt_engine.narratives.fixture.json` — narrative treatment rows (real golden ids)

| Status | Node id | Live sig (golden) | Stored sig (fixture) | Why |
|---|---|---|---|---|
| approved | `micro:app/layout.tsx` | `c02ea15f8f13acb8…630` | `c02ea15f8f13acb8…630` (copy) | sig matches, status=approved |
| proposed | `nano:Home@app/page.tsx` | `2a9436e73561c29d…` | `0000…00aa` | stored sig mismatches, status=proposed → derived "proposed" via stored status branch |
| stale | `micro:app/api/auth/login/route.ts` | `e03bd9925fd2497b…700` | `0000…00bb` | sig mismatch → "stale" (OLD text rendered) |
| unnarratable-via-empty-sig | `cmp-dist` | `e3b0c442…b855` (EMPTY_SIG) | `c02ea15f…` | A1 branch 1 fires FIRST — empty sig → unnarratable, stored entry ignored |
| unnarratable-without-entry | `cmp-invoice-cost` | `e3b0c442…b855` (EMPTY_SIG) | (no entry) | same A1 branch — no entry needed |
| orphaned (counted, not rendered) | `nano:does-not-exist@app/ghost.tsx` | — | `0000…00cc` | id not in `model_ids` → `gm.info("…N orphaned narrative entries dropped")`, payload stays clean |

### `injection.narratives.json` — F3 escape hazards (Decision 6, separate file)

Two real-golden-id entries whose `text` field carries every F3 hazard:

| Node id | Hazard in `text` |
|---|---|
| `cmp-prisma` | `</script><script>`, `<!--`, U+2028 LINE SEPARATOR, literal sentinel `/*<SSOT:VIEWMODEL_JSON>*/` |
| `micro:prisma/seed.ts` | U+2028 + nested `<!--` |

Paired with hostile `--title` in test invocations (Decision 6 — title hazards flow
through tests, not a committed file).

### `trustmatrix.model.json` — synthetic golden #3 (F4 coverage)

Top-level shape per A4: `{version:1, generated_at:null, nano_cap:8, components[], decisions[]}`.

| Component | Live sig | Notes |
|---|---|---|
| `cmp-tm-alpha` | `aaaa…aa` (real) | 1 micro, 2 nanos |
| `cmp-tm-beta` | `e3b0c442…b855` (EMPTY_SIG) | 1 micro, 1 nano + 1 collapsed placeholder |

Decisions (one per L3 status row, attached to visible nodes):

| Decision id | Status | Attached to |
|---|---|---|
| `dec-tm-fresh` | `FRESH` | `nano:alphaOne@tm/alpha.ts` |
| `dec-tm-stale` | `STALE` | `nano:alphaTwo@tm/alpha.ts` |
| `dec-tm-orphan` | `ORPHANED` | `nano:betaOne@tm/beta.ts` |
| `dec-tm-ambig` | `AMBIGUOUS` | `micro:tm/alpha.ts` |
| `dec-tm-super` | `superseded` | `micro:tm/beta.ts` |

### `trustmatrix.narratives.json` — derived narrative status coverage (paired with trustmatrix.model.json)

| Status | Node id | Mechanism |
|---|---|---|
| approved | `nano:alphaOne@tm/alpha.ts` | sig matches live `cccc…cc`, stored status=approved |
| proposed | `micro:tm/alpha.ts` | sig matches live `bbbb…bb`, stored status=proposed |
| stale | `nano:alphaTwo@tm/alpha.ts` | stored sig `ffff…ff` ≠ live `dddd…dd`, stored status=approved → derived "stale" |
| unnarratable | `cmp-tm-beta` | A1 branch 1 — live sig == EMPTY_SIG, stored entry ignored |
| none | `nano:betaOne@tm/beta.ts` | no entry present → `_derive_status` returns "none" |
| orphaned | `fake:nano-ghost@tm/ghost.ts` | id not in `model_ids` → `gm.info` count, dropped from payload |

## Verify output (paste real output, no redaction)

### 1. All four load through the real loaders
```
$ python3 -c "import sys;sys.path.insert(0,'ssot-diagram');import graph_model as gm;from pathlib import Path;print('fixture narr:',len(gm._load_narratives(Path('ssot-diagram/testdata/mkt_engine.narratives.fixture.json'))));print('inj narr:',len(gm._load_narratives(Path('ssot-diagram/testdata/injection.narratives.json'))));print('tm model:',list(gm._load_model(Path('ssot-diagram/testdata/trustmatrix.model.json')).keys()));print('tm narr:',len(gm._load_narratives(Path('ssot-diagram/testdata/trustmatrix.narratives.json'))))"
fixture narr: 5
inj narr: 2
tm model: ['version', 'generated_at', 'nano_cap', 'components', 'decisions']
tm narr: 5
```

### 2. cmp-dist derives unnarratable DESPITE its stored entry (A1 branch order)
```
$ python3 -c "import sys,json;sys.path.insert(0,'ssot-diagram');import render as r,graph_model as gm;from pathlib import Path;m=gm._load_model(Path('ssot-diagram/testdata/mkt_engine.model.json'));n=gm._load_narratives(Path('ssot-diagram/testdata/mkt_engine.narratives.fixture.json'));vm=r.build_viewmodel(m,n);cd=[c for c in vm['components'] if c['id']=='cmp-dist'][0];print('cmp-dist prose.status=',cd['prose']['status'],'(want unnarratable)')"
build_viewmodel: 1 orphaned narrative entries dropped
cmp-dist prose.status= unnarratable (want unnarratable)
```

### 3. trustmatrix: every decision status present + per-node derived status via the REAL join
```
$ python3 -c "import sys;sys.path.insert(0,'ssot-diagram');import render as r,graph_model as gm;from pathlib import Path;m=gm._load_model(Path('ssot-diagram/testdata/trustmatrix.model.json'));n=gm._load_narratives(Path('ssot-diagram/testdata/trustmatrix.narratives.json'));vm=r.build_viewmodel(m,n);print('dec statuses:',sorted(set(d['status'] for d in m['decisions'])))"
build_viewmodel: 1 orphaned narrative entries dropped
dec statuses: ['AMBIGUOUS', 'FRESH', 'ORPHANED', 'STALE', 'superseded']
```

Per-node derived narrative status (sanity walk through the joined payload):
```
build_viewmodel: 1 orphaned narrative entries dropped
  cmp-tm-alpha                               -> none
  micro:tm/alpha.ts                          -> proposed
  nano:alphaOne@tm/alpha.ts                  -> approved
  nano:alphaTwo@tm/alpha.ts                  -> stale
  cmp-tm-beta                                -> unnarratable
  micro:tm/beta.ts                           -> none
  nano:betaOne@tm/beta.ts                    -> none
  collapsed:tm/beta.ts                       -> collapsed
```
Every row of the L3 narrative matrix is present on at least one node; the `orphaned`
count surfaces on stderr as `gm.info` (matches the A1 + spec note that orphan entries
are counted but never rendered).

### 4. pytest baseline (A19 regression guard)
```
$ /Users/phatchenh/.cache/writ/.venv/bin/python -m pytest ssot-diagram/ -q 2>&1 | tail -1
3 failed, 105 passed in 3.51s
```
Failed list — same 3 pre-existing `TestGoldenLive` pilot-drift set; ZERO new failures:
```
FAILED ssot-diagram/test_graph_model.py::TestGoldenLive::test_golden_byte_match
FAILED ssot-diagram/test_graph_model.py::TestGoldenLive::test_verified_decision_nodes_present
FAILED ssot-diagram/test_graph_model.py::TestGoldenLive::test_pre_extract_guard_silent
```

### 5. Golden model + graph_model.py byte-unchanged
```
$ git diff --stat ssot-diagram/testdata/mkt_engine.model.json ssot-diagram/graph_model.py | tail -1
(empty — no output, confirming both files are untouched)
```

## Notes for downstream steps

- `mkt_engine.narratives.fixture.json` is referenced by the Step 10 tests as
  golden #2 input. Its `cmp-dist` row is the canonical A1 branch-order probe.
- `injection.narratives.json` keeps golden #2's sha stable (Decision 6) — hostile
  payloads evolve in this file without disturbing the baseline.
- `trustmatrix.model.json` + `trustmatrix.narratives.json` are golden #3 — every
  L3 status row (FRESH/STALE/ORPHANED/AMBIGUOUS/`superseded` + the 6 derived
  narrative statuses) is exercised through the real `_derive_status` join, no mocks.
- All four files use the Block 5a shape `{node_id, signature, text, status}`
  wrapped in `{"narratives": {...}}`, matching `_load_narratives` exactly.

## Out-of-scope touches
None. No file outside the declared 4-file list was edited.

=== END REPORT ===

testCmd: python3 -c "import sys;sys.path.insert(0,'ssot-diagram');import graph_model as gm;from pathlib import Path;print(len(gm._load_narratives(Path('ssot-diagram/testdata/mkt_engine.narratives.fixture.json'))))"