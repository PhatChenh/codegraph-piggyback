# P5 UX Delta Addendum — the 4 surfaces the archived spec never saw

> Companion to `p5-html-renderer.md` (same folder). The archived design spec
> (`_archived/visualizer_guide/design-system/spec.md`) is **LOCKED for
> everything it covers** — colors (§1), typography (§2), card anatomy (§3.2),
> edges (§4), spacing (§5), interactions (§7), page chrome (§8). This addendum
> pins ONLY the four surfaces that spec never saw, using its tokens. It decides
> nothing new: every choice below restates the design doc's Chosen Approach.
> Owner approves this addendum at the design gate.

---

## 1. Three-level expansion mechanics (drill-down focus views)

**In plain terms:** instead of cards ballooning open on top of the map (which
works for 2–4 children but not for a real component with 47 files), clicking a
card's expand button makes that card *become the screen*: its header stays at
the top as a panel, and its children lay out as the new canvas below. You go
down by expanding, back up with the breadcrumb or the panel's collapse button.

- **View state** is a single path (`viewPath`, 0–2 ids). Three possible
  screens: **components view** (all components as Macro cards, §3.1 level 1),
  **component focus view** (that component's files as Micro cards, level 2),
  **micro focus view** (that file's functions as Nano cards, level 3). Exactly
  three levels, matching §3.5's max nesting depth — a Nano card has no expand
  button, ever.
- **Expand button** stays as §3.2 anatomy item 5 (top-right of badge strip,
  `+`), but clicking it navigates instead of overlaying: push the id onto
  `viewPath`, re-render.
- **Focus header panel** reuses the §3.5 expanded-card look verbatim: badge
  strip, title row, description (the node's joined prose with its trust
  treatment, §2 below), then `border-top: 1.5px solid var(--border)` and the
  minimum `20px` padding before the first child card. The collapse button
  (`−`) in the panel pops one level.
- **Children layout** below the panel: grid with `ceil(sqrt(n))` columns,
  order = the embedded array order (which is the model's deterministic order),
  gaps per §5.2, container padding per §5.3 for the level being shown.
- **Edges** between children in the current view draw per §4 (rounded
  orthogonal, arrowheads, count labels precomputed in Python, e.g.
  "imports ×2"). An edge whose far end is *outside* the current view draws to
  a stub card (§3 below) — no edge silently disappears.
- **The §3.5 implementation note is honored** (CSS animation and SVG transform
  never on the same `<g>` containing `foreignObject`): position on an outer
  `<g>`, animate an inner `<g>` — the corrected pattern from the archived
  example file, not the template.
- **"+K more" collapsed card** appears in the micro focus view as a Nano-size
  card using `var(--bg-inset)` fill, `var(--fg-muted)` text, no badge strip,
  no expand button, no tooltip beyond its own label. It is honest overflow,
  not a navigable node.
- Pan/zoom (§7.4), theme toggle (§7.6), and edge highlight-on-click (§7.3)
  apply unchanged within every focus view. Tooltips keep §7.2's trigger,
  position, and box styling, but their CONTENT follows the trust rule in §2
  below (tooltips inherit the node's treatment) and is filled from the
  embedded data via `textContent` — never from raw prose stored in HTML
  attributes.

## 2. Trust-treatment visuals (the status→treatment matrix, painted)

**In plain terms:** every card's description is either a human-approved
sentence, an unreviewed draft, an outdated sentence, or a machine-written
fallback — and you can always tell which, at a glance, from muting and a small
chip. Nothing is ever hidden, and nothing outdated ever looks current.

All statuses are computed in Python and arrive pre-joined; the painter only
maps `prose.status` / decision `status` to the treatments below. Chips are
small pills in badge colors (§1.4), `--text-caption` size (10px / weight 500),
uppercase, placed directly under the title row.

| Arrives as | Prose color | Chip |
|---|---|---|
| `approved` | `var(--fg-body)` (normal §3.2 description) | none |
| `proposed` | `var(--fg-disabled)` (muted) | "PROPOSED — UNREVIEWED" in `--badge-action-bg`/`--badge-action-fg` |
| `stale` | `var(--fg-disabled)` (muted — this is deliberately the OLD text) | "NEEDS REVIEW — CODE CHANGED" in `--badge-danger-bg`/`--badge-danger-fg` |
| `unnarratable` | `var(--fg-body)` (fallback sentence) | "UNNARRATABLE" in `--fg-disabled` on `var(--bg-inset)` |
| `none` | `var(--fg-body)` (fallback sentence) | none |
| `orphaned` | never reaches the painter (dropped in the Python join) | — |

**Decision chips** (per node, in the inset section area of the card, one pill
per attached decision, labeled with the decision name e.g. "ADR-0006"):

| Decision status | Chip colors | Extra label text |
|---|---|---|
| `FRESH` | `--badge-positive-bg` / `--badge-positive-fg` | none |
| `STALE` / `ORPHANED` | `--badge-danger-bg` / `--badge-danger-fg` | "NEEDS REVIEW" |
| `AMBIGUOUS` | `--badge-danger-bg` / `--badge-danger-fg` | "AMBIGUOUS — ANCHOR UNCLEAR" (danger-adjacent per grill; distinct wording so it is never read as confirmed-stale) |
| `superseded` | `--fg-disabled` text on `var(--bg-inset)` | "SUPERSEDED" (whole chip greyed/disabled) |

- The **legend** (§8.3) gains a "Trust" block listing exactly the chips present
  in the current artifact, same auto-generation rule as node/edge entries.
- Badge-strip colors follow the archived script_spec badge-COLOR semantics
  where they map cleanly: components and micros use `neutral`; nanos use
  `neutral`; the badge strip communicates *level* (label text "COMPONENT" /
  "FILE" / "FUNCTION"), while *trust* lives exclusively in the chips — the two
  channels never share a surface, so a danger chip is always trust news, never
  node-type styling.
- Raw source code appears nowhere (locked).
- **Tooltips inherit the node's trust treatment (matrix extension, red-team
  F2).** A tooltip (§7.2 trigger/box) shows only joined fields — name, kind
  label, prose text, capped `file:line` caller samples — AND, whenever the
  node's status carries a chip, the tooltip opens with that same chip text
  (e.g. "NEEDS REVIEW — CODE CHANGED") and shows the prose in the same muted
  `var(--fg-disabled)` the card uses. Stale, proposed, or unnarratable prose
  never appears unmarked on hover: the tooltip is a rendering surface like the
  card, not a trust bypass. Content arrives precomputed from Python
  (`node.tooltip` in the embedded data) and is inserted via `textContent`;
  the archived `data-title`/`data-desc` attribute pattern is NOT carried over.

## 3. Stub cards (`--component` files AND the full artifact)

**In plain terms:** wherever an arrow points outside what you're looking at,
it lands on a small labeled placeholder for the neighbor component. In the
full diagram that placeholder is a shortcut — click it and you jump to that
neighbor. In a scoped per-component file the neighbor's insides genuinely
aren't in the file, so the placeholder is just a label you cannot open.

**This section is the binding contract for both behaviors (owner ruling on
OQ-P5-1, 2026-07-06: NAVIGABLE in the full artifact — overriding the earlier
inert-everywhere recommendation — INERT in `--component` scoped files).**

- **Shared stub visual (both contexts):** Micro-size card (§3.1 level 2
  dimensions) with page background fill (`var(--bg)`), standard
  `1px var(--border)` stroke, badge strip in `--badge-neutral-bg` with label
  "OTHER COMPONENT". No expand button, no details inset, no decision chips,
  no trust chip. Stubs never expand in place in either context.
- **Full artifact — NAVIGABLE stub:** title = neighbor component's `name` in
  `var(--fg-body)` followed by a trailing `→` glyph, also `var(--fg-body)`;
  `cursor: pointer`; on hover the card border switches to the §1.3 focus ring
  (`var(--ring)`) — the same affordance grammar the header buttons use (§8.2
  button hover). Clicking it jumps to that neighbor component's focus view (a
  `viewPath` navigation; the breadcrumb updates accordingly). The painter
  switches on the embedded `stub_nav: true` flag — it decides nothing itself.
- **`--component` scoped file — INERT stub:** title in `var(--fg-disabled)`,
  no `→` glyph, default cursor, no hover ring; clicking does nothing except
  the standard §7.3 edge-highlight (`stub_nav: false` in the embedded data —
  the neighbor's tree is absent from this file, so there is nowhere to go).
- **The cue IS the difference:** `→` glyph + body-color title + pointer +
  hover ring = "this goes somewhere"; no glyph + disabled-color title = "this
  is only a label". Same card size, same badge strip, so the reader parses
  both as "neighbor component, not part of this view".
- **Placement (both contexts):** stubs sit in a single column to the right of
  the current view's grid, sorted by component id, one stub per distinct
  neighbor component that any cross-view edge resolves to (resolution happens
  in Python via the id→owning-component map; stubs arrive flagged
  `"stub": true` in the embedded data). One visual grammar for "this arrow
  leaves what you're looking at", learned once.

## 4. Breadcrumb behavior at 3 levels

**In plain terms:** the top-center of the header always tells you where you
are — "SSOT diagram > lib > store.ts" — and every earlier segment is a link
back up. It is the primary way back; you can never get lost more than two
clicks from the top.

- All §8.2 tokens apply unchanged: `12px / 500`, separator `>` in
  `var(--fg-disabled)`, clickable segments in `var(--fg-body)` with hover
  underline, deepest segment `var(--fg)` / 700 and not clickable.
- **Hidden at top level** (components view), exactly as §8.2 specifies for "no
  cards expanded".
- **Segments are derived from `viewPath` by looking up embedded `name` fields
  only** — the painter never parses ids or recomputes anything. Depth 1:
  `SSOT diagram > <Component name>`. Depth 2:
  `SSOT diagram > <Component name> > <file name>`. (The root segment label is
  the artifact title; in a `--component` file the root segment is the
  component itself and depth maxes out one level earlier.)
- **Clicking a segment truncates `viewPath`** to that segment and re-renders —
  the same operation as the focus panel's `−` button, so breadcrumb and
  collapse can never disagree about where "up" goes.
- Maximum depth is 2 segments past the root: nanos never expand (Block 4a's
  three levels), so the breadcrumb never grows a fourth segment.
