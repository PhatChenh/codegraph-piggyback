# Step 8 Implementation Report — JS painter body

## Files changed
- `ssot-diagram/render_template.html` — filled the painter stubs (showTooltip,
  paintView, buildLegend, boot + supporting helpers). Template 325 -> 1007 lines.

## Painter behaviors filled (Step 8 + UX addendum §1-4)
Focus-view state machine (viewPath 0-2 + viewState pan/zoom, paintView fully
re-renders per path); grid layout (ceil(sqrt(n)) cols, §5.2/5.3/5.4 spacings);
focus header panel (§3.5 look); breadcrumb (from viewPath via name lookups,
segments truncate path on click = same as panel `-`, hidden at top, scoped root);
stubs (switch on stub/stub_nav flags only — navigable `->`+body+pointer+hover
ring click->viewPath, inert disabled+no-glyph+edge-highlight-only, OTHER FILE
badge label + OTHER COMPONENT); tooltips (data-node-id only, showTooltip fills
via setText from precomputed node.tooltip, §7.2 trigger/position/box); legend
(draw embedded legend verbatim via createElement+textContent); edge painting
(rounded orthogonal + arrowhead + precomputed pill labels, highlight-on-click +
unconnected fade, deselect on empty-click); theme toggle (data-theme +
localStorage diagram-theme + prefers-color-scheme); pan/zoom (drag, wheel,
0.25-4x, buttons, fit-to-view from layout data never getBBox, dblclick, touch).

## Dumb-painter invariant (ADR-0002)
No arithmetic/conditionals on trust fields, no .get defaulting — every
status/chip/label/tooltip is read from the embedded precomputed MODEL. load-time
id->node index (Decision 11) built once; boot() wired only when MODEL !== null.

## Verify (2026-07-10, static)
- sentinels each exactly once (VM 1 / FONT 1 / GENERATOR 1) — Step 7 splice
  assert holds.
- raw-HTML-sink word absent (0) — all model-derived strings via setText /
  paintWrappedText / createElement+textContent. No prose in HTML attributes.
- no <link>/@import (self-contained, zero network).
- node --check on extracted <script> (29352 chars) -> JS-syntax OK.
- boot() (line 997) called only when MODEL !== null (line 1004) — raw template
  still previews clean.
- E2E render: writes 338962-byte HTML exit 0; byte-deterministic across two
  renders (sha b64e2136b6362a0d). Output grew vs Step 7 (was 313K) because the
  painter JS now adds render content — expected; determinism is what holds.
- graph_model.py + golden byte-unchanged; pytest 105/3 (0 new).

NOTE: live interactive behavior (click/hover/pan/zoom/theme-persist) is NOT
assertable headlessly — deferred to the phase-end E2E browser check.

## Literal testCmd (Step-8 gate)
```
python3 ssot-diagram/render.py render --model ssot-diagram/testdata/mkt_engine.model.json --out /tmp/p5_s8.html
```

=== END REPORT ===
