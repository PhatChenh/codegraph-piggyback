# Step 10 Implementation Report — test_render.py + Step-9 fixture fix

## Files changed
- `ssot-diagram/test_render.py` — NEW (24 tests: 3 pinned-sha goldens + structural +
  injection + exit-codes + template-hygiene + scoped-view + regression).
- `ssot-diagram/testdata/mkt_engine.narratives.fixture.json` — fixed the
  "proposed" entry's stored signature: was all-zeros `..aa` (mismatched the real
  node sig -> gm._derive_status derived 'stale' not 'proposed'); set to the
  node's REAL live sig `2a9436e7...` so it correctly derives proposed (Step-9
  fixture bug surfaced by Step-10's chip assertion).

## Pinned golden shas (rendered post-Step-8 painter, re-pinned after fixes)
- GOLDEN_NO_NARR_SHA      = b64e2136b6362a0d79d432c0094e0961894f71ef6e910b55c8e6784540901e27
- GOLDEN_WITH_NARR_SHA    = 1f6dadf1be98128d320a986d1300a7dcff60cfea1e6a372ab1cfe1f09a9816d1
- GOLDEN_TRUSTMATRIX_SHA = 2e2e2d98093e9b8574e8bed2529945797632dbaeb9586b39d87c5cb935192dc1

## Verify (2026-07-10)
- test_render.py: 24 passed.
- Full suite: 129 passed / 3 failed — the 3 = ONLY the pre-existing TestGoldenLive
  pilot-drift set (unchanged since the 105/3 baseline). 0 NEW failures.
  (105 -> 129 = +24 new render tests, exactly matching test_render.py.)
- golden model sha 56df3d86... intact after a full render run; graph_model.py +
  testdata/mkt_engine.model.json byte-unchanged.
- Double-oracle demo (Action 5): mutated the fixture's proposed-text -> sha
  drifted (1f6dadf1 -> 565de28c) -> test_golden_with_narr_sha_pinned FAILED on
  the sha; restored -> green (3 passed). Tripwire works.

## Orchestrator fixes to worker-shipped test bugs (all caught by independent runs)
1. Self-recursive regression test (test_full_suite_baseline_no_new_fails shelled
   out to run the WHOLE suite incl. itself -> ~2min+ / apparent hang). Fixed:
   nested run `-k "not test_full_suite_baseline_no_new_fails"` + 180s timeout.
2. Em-dash / middle-dot escape mismatch: chip + subtitle assertions used raw
   U+2014 / U+00B7; ensure_ascii=True escapes them in the payload -> impossible
   literal match. Fixed: assert encoding-invariant fragments.
3. No subprocess timeout on _run_render / missing-template run. Fixed: 60s +
   fail-on-timeout.

## Literal testCmd (Step-10 gate)
```
/Users/phatchenh/.cache/writ/.venv/bin/python -m pytest ssot-diagram/test_render.py -q
```

=== END REPORT ===
