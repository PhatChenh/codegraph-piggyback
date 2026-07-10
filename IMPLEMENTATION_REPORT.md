# Step 5 Implementation Report — `build_viewmodel` + OTHER FILE addendum note

## Files changed (declared set, exactly two)

```
M ssot-diagram/render.py                                        (build_viewmodel + 8 helpers added)
M ssot-diagram/AI-artifacts/1_design/p5-html-renderer-ux-addendum.md  (§3.1 OTHER FILE note appended)
```

No other file touched. `git diff --stat` on the byte-unchanged guards
(`ssot-diagram/graph_model.py`, `ssot-diagram/testdata/mkt_engine.model.json`)
returns empty.

## build_viewmodel symbol present

```
$ grep -n '^def build_viewmodel' ssot-diagram/render.py
363:def build_viewmodel(
```

Signature verbatim from Implementer Notes §4:
`(model: dict, narratives: dict, *, component: str | None = None, title: str | None = None) -> dict`.

Imports `_derive_status` (gm:1000-1014) and `_fallback_text` (gm:898-926) by
name only — both branches' load-bearing order (A1 empty-sig caught FIRST;
cmp-dist / cmp-invoice-cost derive `unnarratable` DESPITE a stored entry)
preserved by routing every node through `gm._derive_status(stored, sig)`
unchanged. A17 guard (unknown status vocabulary) raises `die` (exit 2) on
out-of-set derivations.

## Verify output

### Verify 1 — `-c` (subtitle + comps)

```
$ python3 -c "
import sys
sys.path.insert(0, 'ssot-diagram')
import render as r
import graph_model as gm
from pathlib import Path
m = gm._load_model(Path('ssot-diagram/testdata/mkt_engine.model.json'))
vm = r.build_viewmodel(m, {})
print('keys', sorted(vm))
print('subtitle', vm['subtitle'])
print('comps', len(vm['components']))
"
keys ['components', 'legend', 'note', 'scope', 'subtitle', 'title', 'view_edges']
subtitle 10 components · 8 decisions
comps 10
```

Matches expected: `subtitle == '10 components · 8 decisions'`, `comps == 10`
(8 = UNIQUE ADR names per F5; golden has 11 decision ids / 8 unique names
ADR-0001..ADR-0008).

### Verify 2 — grep-0 for the two forbidden defs

```
$ grep -c 'def _derive_status\|def _fallback_text' ssot-diagram/render.py
0
```

`0` = both helpers IMPORTED from `gm`, never re-defined in render.py.
Step-5 qualifier satisfied.

### Verify 3 — pytest ssot-diagram/ -q

```
$ /Users/phatchenh/.cache/writ/.venv/bin/python -m pytest ssot-diagram/ -q 2>&1 | tail -2
3 failed, 105 passed in 3.75s
```

3 fails = the SAME pre-existing `TestGoldenLive` pilot-drift set
(`test_golden_byte_match`, `test_verified_decision_nodes_present`,
`test_pre_extract_guard_silent`) — the A19 baseline. **0 new fails** vs the
105-pass / 3-prefail baseline. Step 5 introduces no regressions.

### Verify 4 — cmd_render happy-path (Step 5 join not yet wired in cmd_render)

```
$ python3 ssot-diagram/render.py render --model ssot-diagram/testdata/mkt_engine.model.json --out /tmp/vm.html 2>&1 | tail -2
out         = /tmp/vm.html
title       = SSOT diagram
exit: 0
```

cmd_render still exits 0 on the happy path; build_viewmodel is not yet
called from cmd_render (that is Step 7's splice+write wiring). The Step-5
`-c` verify (Verify 1) exercises build_viewmodel directly. No MINIMAL
plumbing edit needed.

## Byte-unchanged guards

```
$ git diff --stat ssot-diagram/graph_model.py ssot-diagram/testdata/mkt_engine.model.json
```

Empty. `graph_model.py` and the golden model are untouched per the
plan-verify qualifiers (A1 / A2 / A9 / frozen-skeleton-contracts / A11 / A19).

## Addendum edit (the ONE authorized doc edit)

`ssot-diagram/AI-artifacts/1_design/p5-html-renderer-ux-addendum.md` §3
gains a new `§3.1 — "OTHER FILE" micro-stub extension` subsection
recording Decision 1 (owner-ratified 2026-07-09). One-token extension:
same card grammar as "OTHER COMPONENT", new badge label, sibling-micro
resolution scope. Identical navigable/inert + cue rules. Noted as a NOTE
appended to §3 — explicitly NOT a redesign of the FROZEN skeleton
contracts. Reversible per the closing sentence.

## Behavioral spot-checks (observed, not asserted by plan-verify)

- **A1 branch order on cmp-dist (empty-sig component) with a stored
  entry:** `prose.status == 'unnarratable'`, `prose.source == 'fallback'`,
  chip = `('prose:unnarratable', 'UNNARRATABLE')`. The bogus stored entry
  (`signature: 'deadbeef'`, `status: 'approved'`) does NOT win — the empty
  source signature is caught first.
- **A17 guard:** monkey-patched `gm._derive_status` to return
  `'BOGUS_STATUS'` — `build_viewmodel` dies on the first node with
  `error: derive_status: unknown status 'BOGUS_STATUS' for 'cmp-app' (A17
  guard)`, exit 2.
- **Determinism:** two `build_viewmodel(m, narratives)` runs produce
  byte-equal payloads under `json.dumps(..., sort_keys=True)`.
- **Scoped mode (`component='cmp-lib'`):** `scope == 'cmp-lib'`, 1 component
  in payload, subtitle `'46 files · 8 decisions'` (46 micros under
  cmp-lib, 8 unique ADR names reach at least one subtree chip).
- **Unknown cid:** `component='cmp-nope'` → `die` listing all 10 known ids
  in the canonical-sorted order the golden produces, exit 2.

## Stubs and edges (per-view precompute, dumb-painter enabler)

Each component and each micro carries its own `view_edges` and `stubs` in
the joined payload. The top-level payload also carries `view_edges` (the
top view) and `legend`. The precompute applies:

- Top view: Decision 7 — omit edges whose BOTH endpoints resolve to the
  same component.
- Component focus view: cross-component targets → `OTHER COMPONENT` stub.
- Micro focus view: cross-sibling-micro target in the same component →
  `OTHER FILE` stub (Decision 1); cross-component → `OTHER COMPONENT`.
- `stub_nav` is True iff the artifact is full (no `--component`); False
  for the `--component` scoped file (OQ-P5-1 + Decision 1 inert
  extension).
- Edge labels precomputed as `<kind> ×<count>` (e.g. `imports ×11`).

## Step-5 scope closing

The L2 heart (`build_viewmodel`) is callable, deterministic, and the
A1/A2/A11/A12/A17/A19 invariants are mechanically enforced. Step 6
(`_escape_viewmodel_json` + `_font_face_css`) and Step 7 (`_render_html` +
`_save_text` + cmd_render assembly) are the next gates.

`python3 -c "import sys;sys.path.insert(0,'ssot-diagram');import render;print(callable(render.build_viewmodel))"`

=== END REPORT ===
