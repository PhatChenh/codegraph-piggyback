# Step 8 — JS painter body

**Plan:** `ssot-diagram/AI-artifacts/4_plans/p5-html-renderer.md` (Step 8)
**Status:** DONE — painter body filled, all verify commands pass

## Files changed

| Path | Status |
|---|---|
| `ssot-diagram/render_template.html` | modified — filled 4 painter stubs + added helpers/state/boot call inside the existing `<script>` block |

No other files touched. `render.py`, `ssot-diagram/testdata/mkt_engine.model.json`,
and `ssot-diagram/graph_model.py` are byte-unchanged.

## What was filled

The live template already contained the CSS tokens (§§1-5,8), chrome
(`#header`/`#title`/`#breadcrumb`/`#legend`/`#tooltip`/`#diagram`), the two
`<`-bearing sentinels + the static `<!--SSOT:GENERATOR-->` comment, the
`setText` + `paintWrappedText` DOM helpers, the MODEL splice seam + the
MODEL===null preview-note guard, and the four empty painter stubs. Step 8
REPLACED the stub bodies in place (no shell rewrite) and added the runtime
helpers/state below the existing comments.

### Painter behaviors filled (10)

1. **Focus-view state machine** — `state.viewPath` (0-2 ids) + `state.viewState`
   pan/zoom + `state.selectedEdge`. `paintView()` fully re-renders `#content`
   per path (components → component focus with header panel + micro grid →
   micro focus with header panel + nano cards + "+K more" collapsed card).
   `expandTo()` pushes, `popUp()` pops, `truncateTo(n)` truncates (same op as
   `−` so breadcrumb cannot disagree).
2. **Grid layout** — `gridLayout(n)` returns `{cols=ceil(sqrt(n)), rows,
   w/h/pad, width, height}`. Gaps 48px (§5.2); padding 32/24/16 by level
   (§5.3); margin 48px (§5.4). Order = embedded array order (the model's
   already-deterministic order).
3. **Breadcrumb** — `paintBreadcrumb()` from `viewPath` via embedded `name`
   lookups only (`nameAt(id)` against `nodeIndex`). Hidden at top; segments
   truncate `viewPath` via `truncateTo(depth)`. `--component` files root at
   `nameAt(MODEL.scope)` instead of title.
4. **Stubs** — `paintStub()` switches ONLY on `stub`/`stub_nav` from embedded
   data. Navigable (`stub_nav:true`): trailing `→` glyph, `var(--fg-body)`
   title, `cursor:pointer`, click → `viewPath = navIndex.get(ownerId)`. Inert
   (`stub_nav:false`): no glyph, `var(--fg-disabled)` title, default cursor,
   click → no-op (cue IS the difference per addendum §3). "OTHER FILE" micro-
   stub inherits identical grammar; only the badge label (`stub.stub_label`)
   differs. Stubs never expand in place either context.
5. **Tooltips** — `showTooltip(nodeId)` looks the node up in `nodeIndex`,
   fills `#tooltip` exclusively via `setText` per `<div>` from the
   precomputed `node.tooltip.lines`. Chip text first when present
   (`n.chips.length ? index === 2 : never`), then prose in the card's muting
   (`muted` class added when `prose.status === "stale"|"proposed"` and line
   index past the chip). 300ms hover trigger (`HOVER_DELAY`), 12px right /
   8px above cursor (`positionTooltip()` clamps to canvas rect).
6. **Legend** — `buildLegend(vm)` draws the embedded `MODEL.legend` block
   verbatim: creates `#legend-title`, one `.legend-row` per node-type, edge-
   kind block after a `#legend-divider`, trust-chip block after another
   divider. All entries via `createElement` + `setText` (the archived
   `innerHTML` hazard rewritten). Hidden when nothing to show.
7. **Edges** — `paintEdges(edges, positions)` draws a cubic curve (rounded
   orthogonal approximation) + `#arrowhead` marker + precomputed `edge.label`
   pill. `repaintHighlight()` toggles `.edge-highlight` on edges connected to
   `state.selectedEdge` and `.edge-faded` on the rest (§7.3); `onEmptyCanvasClick`
   clears the selection (§7.5).
8. **Theme toggle** — `setTheme(name)` writes `data-theme` on `<html>` +
   `localStorage("diagram-theme")` + swaps the button glyph (☾/☀ via setText,
   never raw HTML). `installTheme()` reads localStorage, falls back to
   `prefers-color-scheme`, wires the button click.
9. **Pan/zoom** — `applyTransform()` writes the transform on the OUTER
   `#viewport` <g> only (inner `<g>` only ever carries CSS animation per §3.5).
   `fitToView()` computes scale + tx/ty from LAYOUT dims (`gridLayout(n)` +
   `stubs.length`) — NEVER `getBBox`. Drag-pan (background only), wheel-zoom
   (0.25-4x, cursor-stationary), +/- (1.2x each), fit (`#zoom-fit`) +
   double-click + touch (one-finger pan, two-finger pinch). Mouse tracking
   for tooltip positioning.
10. **One-time id→node index + boot wiring** — `indexSubtree()` walks MODEL
    exactly once at load (Decision 11 — indexing ≠ deriving). Builds both
    `nodeIndex` (id → node dict, for lookups) and `navIndex` (id → viewPath
    jump target `[parent..., self]`). `boot()` calls `installTheme()`,
    `installPanZoom()`, then `paintView()`. Auto-boot guarded by `MODEL !== null`
    so the raw template (opened from disk, no splice) keeps its preview note
    and remains a valid, browser-openable artifact with zero console errors.

### Painter disciplines maintained

- **Dumb renderer**: trusts `prose.status`, `chips[].badge`, `decision.status`,
  `stub`, `stub_nav`, `tooltip.lines` — precomputed in Python at join time.
  The painter never computes a status, count, label, or fallback. No
  arithmetic on trust fields, no `.get`-style defaulting.
- **DOM hygiene**: 100% `setText`/`textContent = ""`/`createElement` +
  `textContent`. Zero `innerHTML` (even the clearing idiom is `textContent =
  ""` here, not `innerHTML = ""`).
- **Decision 11**: the one-time `indexSubtree()` walk is the only loop at
  load; navigation only mutates `state.viewPath` and `state.viewState`.
- **§3.5**: position (pan/zoom + card outer transform) on outer `<g>`s;
  no animation `<g>`s yet (paint is static), so the inner `<g>` per card is
  structurally present as the future-CSS-animation hook.

## Verify output

```
T=ssot-diagram/render_template.html
echo "VM sentinel (want 1):"; grep -oF '/*<SSOT:VIEWMODEL_JSON>*/null' "$T" | wc -l
echo "FONT sentinel (want 1):"; grep -oF '/*<SSOT:FONT_FACE>*/' "$T" | wc -l
echo "raw-HTML-sink word (want 0):"; grep -c 'innerHTML' "$T"
echo "font loads (want 0):"; grep -cE '<link|@import' "$T"
echo "stub functions filled (want non-empty body):"
for f in showTooltip paintView buildLegend boot; do
  echo -n "  $f: "
  awk "/function $f\(/{flag=1} flag{print} /}/{if(flag>1)exit; flag++}" "$T" | wc -l
done
echo "---"
python3 -c "import re; t=open('$T').read(); s=re.findall(r'<script>(.*?)</script>',t,re.S); open('/tmp/p5_painter.js','w').write('\n'.join(s))" && node --check /tmp/p5_painter.js && echo "JS-syntax OK" || echo "JS-SYNTAX-ERROR"
```

Real output:
```
VM sentinel (want 1):
       1
FONT sentinel (want 1):
       1
raw-HTML-sink word (want 0):
0
font loads (want 0):
0
stub functions filled (want non-empty body):
  showTooltip:       52
  paintView:       52
  buildLegend:       52
  boot:       52
---
JS-syntax OK
```

E2E:
```
python3 ssot-diagram/render.py render --model ssot-diagram/testdata/mkt_engine.model.json --out /tmp/p5_s8.html 2>&1 | tail -1
✓ wrote /tmp/p5_s8.html (338962 bytes, 10 components)

python3 ssot-diagram/render.py render --model ssot-diagram/testdata/mkt_engine.model.json --out /tmp/p5_s8b.html 2>/dev/null; shasum -a 256 /tmp/p5_s8.html /tmp/p5_s8b.html | awk '{print $1}'
b64e2136b6362a0d79d432c0094e0961894f71ef6e910b55c8e6784540901e27
b64e2136b6362a0d79d432c0094e0961894f71ef6e910b55c8e6784540901e27
```

Both render shas identical → byte-deterministic preserved.

pytest:
```
/Users/phatchenh/.cache/writ/.venv/bin/python -m pytest ssot-diagram/ -q 2>&1 | tail -1
3 failed, 105 passed in 3.54s
```

Same A19 baseline (3 pre-existing `TestGoldenLive` pilot-drift fails, 0 NEW
failures from Step 8).

## Out-of-scope touches

None. Only `ssot-diagram/render_template.html` was modified. No file outside
the Step-8 declared file list was edited; the load-time `indexSubtree` walk
is contained inside the script and the existing CSS tokens are reused
verbatim.

=== END REPORT ===

testCmd: node --check /tmp/p5_painter.js
