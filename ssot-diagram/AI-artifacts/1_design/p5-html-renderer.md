# P5 — Interactive HTML renderer (`render.py`) — design

> Pipeline: design (this doc) → spec → factual-code-verification → plan → implement.
> Requirements were locked at the owner grill 2026-07-06 (10 decisions, restated
> under Constraints — they are NOT reopened here). Companion artifact:
> `p5-html-renderer-ux-addendum.md` (same folder) pins the 4 UX surfaces the
> archived design spec never saw.

## Cast of characters

Only project symbols referenced 3+ times in this doc. One-off symbols are
glossed inline where they appear.

| Symbol | Role in one line |
|---|---|
| `render.py` | The new P5 script: reads two JSON files, emits one interactive HTML file |
| `graph_model.py` | The shipped P3+P4 script; `render.py` imports its trust helpers, never copies them |
| `diagram-model.json` | The deterministic code map (components → files → functions) that P3 extracts |
| `narratives.json` | The signature-pinned plain-language sidecar that P4 curates |
| `_derive_status` | P4's trust-verdict function: given a stored entry + the node's live signature, returns approved/proposed/stale/none/orphaned/unnarratable |
| `_fallback_text` | P4's deterministic one-sentence description built from model fields only |
| `render_template.html` | The repo-owned HTML/CSS/JS shell `render.py` splices data into |
| `build_viewmodel` | The new Python join: model + narratives → one render-ready payload |
| `MODEL` | The single JS constant in the output HTML carrying that payload |
| view-model | The joined payload itself: every node already carries its final text, status, and labels |
| stub card | A labeled placeholder standing in for a neighbor component; never expands in place — navigable (jump link) in the full artifact, inert in `--component` scoped files |
| focus view | One screen of the drill-down: the expanded card's children laid out as the canvas |

## Summary

**In plain terms:** this phase builds the picture. Everything below it already
exists and is machine-checked — the code map (`diagram-model.json`), the
decisions with live freshness badges inside it, and the human-approved
plain-language sentences (`narratives.json`) pinned to code fingerprints. P5
adds one new script, `render.py`, that joins those two files in Python and
writes a single self-contained HTML file a non-coder can open, click from the
system view down to an individual function, and see what each piece is, in
plain language, plus whether every explanation and decision is still current.

The load-bearing design property: **all trust verdicts are computed in Python
at render time** by importing P4's own functions (`_derive_status`,
`_fallback_text` — import, never copy, per ADR-0001's sibling-import seam).
The browser JavaScript is a dumb painter: it reads pre-joined fields out of one
embedded `MODEL` constant and never derives a status, a count, a default, or a
sentence. If the JS is wrong it can only draw ugly, never lie about trust.

Six axes still had real options; this doc picks: repo-owned template with
marker splice; `json.dumps(ensure_ascii=True)` + `<`→`<` embed escaping;
drill-down focus views (not overlay-in-overlay) for 3-level expansion; a
three-golden pinned-sha256 + structural-assert test battery (two real-model
renders + one synthetic fixture covering every decision status); a flags-only
CLI with zero new config keys; default output `ssot-diagram/ssot-diagram.html`.

## Constraints

These are binding inputs, not options. Sources: owner grill 2026-07-06 (locked
decisions L1–L10), FROZEN skeleton contracts, repo CLAUDE.md critical rules.

**Locked decisions (grill 2026-07-06 — restated, not reopened):**

- **L1 — artifact:** new `ssot-diagram/render.py`, separate script, own
  `manifest.json` entry. Loads `diagram-model.json` + `narratives.json`, emits
  ONE self-contained interactive HTML file. Not a `graph_model.py` subcommand.
- **L2 — trust locus:** trust logic runs in PYTHON at render time; `render.py`
  imports `_derive_status` + `_fallback_text` from `graph_model.py`
  (sibling-import per `adrs/0001`; import, NEVER copy). Browser JS is a dumb
  painter: reads embedded fields only, derives NOTHING — no counts, no status,
  no defaults for missing fields.
- **L3 — status→treatment matrix (pinned verbatim as a contract):**

  | Derived status | Treatment |
  |---|---|
  | approved | narrative as trusted prose (normal treatment) |
  | proposed | prose rendered, muted + "PROPOSED — unreviewed" badge (owner chose marked-visible over hidden) |
  | stale | OLD prose rendered, muted + danger "needs review" badge |
  | unnarratable | fallback text only + badge |
  | none | fallback text |
  | orphaned | entry's node absent from model; never renders |

  Decision nodes: FRESH → positive badge, STALE/ORPHANED → danger,
  superseded → disabled. AMBIGUOUS was left to this design: **AMBIGUOUS renders
  with the danger badge palette and the literal label "AMBIGUOUS — anchor
  unclear"** (danger-adjacent per the grill's lean; distinct wording so it is
  never confused with a confirmed-stale decision). NEVER raw source dumps
  anywhere.

  **Matrix extension (red-team F2, 2026-07-06): tooltips INHERIT the node's
  trust treatment.** A node's hover tooltip shows the same prose the card
  shows, with the same muting and the same chip text carried into the tooltip
  body (e.g. a stale node's tooltip opens with "NEEDS REVIEW — CODE CHANGED"
  before the old prose). Stale/proposed/unnarratable prose never appears
  unmarked in a tooltip — hover is a rendering surface like any other, not a
  trust bypass.
- **L4 — HTML injection, escaped at BOTH points:** (a) JSON-embed into
  `const MODEL = …` must be script-safe (exact mechanism chosen in
  Alternatives, axis 2); (b) DOM-insert: all model/narrative-derived strings
  via `textContent` (or SVG-equivalent), never `innerHTML`. The exact functions
  where each happens are named in Chosen Approach §4 — which also pins the
  tooltip as a third named sink riding mechanism (b), per red-team F2 (raw
  prose is never stored in HTML attributes).
- **L5 — fonts:** DM Sans embedded as base64 `@font-face` (OFL license,
  attribution vendored); woff2 files vendored into this repo. ZERO network
  fetches in the output HTML — the archived reference files cheat with Google
  Fonts `<link>` tags (template.html:7-9); do not copy that.
- **L6 — `--component <id>` scoped view:** the chosen component's full 3-level
  tree + cross-component edges drawn to collapsed STUB cards of neighbor
  components (stub = non-expandable, labeled). Emits a per-component HTML file.
- **L7 — missing/malformed inputs:** missing `narratives.json` → render
  proceeds, every node gets fallback text, visible "no narratives yet" note in
  the artifact + stderr warning, exit 0. Malformed model or narratives → die
  exit 2 (P1/P3/P4 convention, `decision_index.die` at decision_index.py:327).
- **L8 — byte-determinism:** same inputs ⇒ byte-identical HTML. Stable ordering
  everywhere, no timestamps, atomic temp + `os.replace` write. Golden smoke
  test like P3/P4: pinned sha256 + structural asserts.
- **L9 — scope ladder:** CORE = trust matrix, escaping, 3-level expansion,
  determinism + golden test, fallback text, embedded fonts. STANDARD (cut only
  visibly, announced) = breadcrumb, legend, tooltips, dark mode, pan/zoom,
  `--component` stub views. STRETCH = empty.
- **L10 — UX contract:** the archived spec
  (`_archived/visualizer_guide/design-system/spec.md`) is LOCKED for everything
  it covers; the separate addendum pins ONLY the 4 surfaces it never saw.

**FROZEN contracts (do not redesign):**

- Block 4a: exactly three levels (component → micro → nano), no flat mode
  (skeleton-contracts.md:146-147).
- Block 4b: importable node fields = `id`, `kind`, `name`, `path`, content
  `signature` (skeleton-contracts.md:149-152). `caller_count`, `is_exported`,
  `docstring` are NON-frozen — see tech-debt handling in Chosen Approach §3.
- Contract 6: edge kinds ⊆ `{calls, imports, references}`
  (ssot-diagram/CLAUDE.md:57) — the renderer's legend and edge styling may
  assume nothing beyond these three.
- Block 5a/5b + amendments: stored narrative status ∈ {proposed, approved};
  `stale` is DERIVED live; empty-signature nodes derive `unnarratable`
  (skeleton-contracts.md:177-205). The renderer is an explicitly named
  "consumer obligation" holder: it MUST compute derived status itself — that is
  exactly what importing `_derive_status` satisfies.
- L5-invents-nothing (ssot-diagram/CLAUDE.md layered model): the renderer is a
  dumb painter of L3+L4.
- Read-only DB — stronger here: **`render.py` never opens the DB at all.** It
  uses `di.find_db` (walks directories checking file existence only,
  `_shared/db.py:22-31`) purely to locate the repo root for default paths.

**Repo critical rules honored:** manifest registration (new entry), CLI runs
standalone, signature pinning respected (renderer only reads signatures, never
writes any persisted state except the HTML artifact itself).

## Implications

- The trust rules that P4 fought for become visible for the first time — a
  drifted explanation stops being an invisible database state and becomes a red
  "needs review" badge a non-coder sees.
  - `_derive_status(stored_entry, current_sig)` (graph_model.py:1000-1014) is
    called once per narratable node inside `build_viewmodel`; its branch order
    (empty-sig first, then none, then orphaned, then sig-mismatch) is
    load-bearing and MUST NOT be re-implemented in JS or re-ordered.
- A second consumer of P4's helpers appears, which slightly widens the
  sibling-import seam but keeps one copy of the trust recipe.
  - `render.py` does `sys.path.insert(0, …); import graph_model as gm`
    (mirrors graph_model.py:26-28 importing `decision_index`). It reuses
    `gm._derive_status`, `gm._fallback_text`, `gm._load_model`,
    `gm._load_narratives`, `gm._load_narrate_config`, `gm.die`, `gm.warn`.
- The output file is big but self-sufficient — it can be emailed, opened from
  disk, archived; nothing in it phones home.
  - Golden model is 653 KB; the joined view-model plus ~90 KB of base64 font
    plus the template lands near 1–1.5 MB. Acceptable for a repo artifact;
    `sample_callers` stays capped at 3 per edge (graph_model.py:531) so it
    cannot balloon.
- The renderer inherits the model's honesty features rather than re-deriving
  them: the "+K more" collapsed node arrives pre-counted and pre-named
  (graph_model.py:390-396), so the painter just draws it.
  - Collapsed nodes lack `path`/`edges`/`decisions`/`caller_count` fields —
    the Python join must branch on `kind == "collapsed"` and must NOT call
    `_fallback_text` on them (it raises `ValueError`, graph_model.py:926).
- Component-level edges can point INTO other components, which is what makes
  both cross-component arrows and stub cards possible without opening the DB.
  - `_aggregate_component_edges` keeps the original micro/nano id as `target`
    (graph_model.py:742-778); the join builds an `id → owning component` map
    from one model walk to resolve foreign endpoints.
- Two shallow-module checks pass: `render.py` is a deep module (interface = one
  CLI + one template contract; implementation = join + escape + layout + tests)
  and deleting it re-scatters that complexity into every future consumer
  (plan-visualizer explicitly wants to reuse this template — real seam, 2nd
  adapter named in BLUEPRINT). `render_template.html` passes the deletion test
  the same way: fold it into Python strings and every template edit becomes a
  Python edit nobody can preview in a browser.

## Alternatives Considered

Six axes had genuinely open options. Everything else was locked (Constraints).
Each axis: viable options with tradeoffs, one recommended.

### Axis 1 — Template strategy

**Option 1A — repo-owned `render_template.html` + marker splice (Recommended).**
*What this means:* the HTML/CSS/JS shell lives as a real, browser-openable file
in the repo; `render.py` reads it, replaces two unique sentinel markers (the
data payload, the font block), and writes the result. Adapted from the archived
example file's corrected overlay pattern
(example-system-architecture.html:649-738), not from template.html — the
template carries the in-place expand bug the spec's §3.5 implementation note
warns about (CSS animation + SVG transform on one `<g>` with `foreignObject`
children); the example file already fixes it (posG outer / animated inner,
lines 657-658) and computes fit-to-view from layout data instead of `getBBox`
(lines 988-1008). Cost: dev effort medium; zero runtime deps; maintenance = one
HTML file. Risk: marker drift — mitigated by `render.py` dying (exit 2) unless
each marker occurs exactly once before splice and zero times after. Splice =
`str.replace` with occurrence-count checks, deterministic. New interface (the
marker contract) is a real seam: `render.py` today, plan-visualizer tomorrow
(BLUEPRINT names it).

**Option 1B — full Python generation (viable, not recommended).** Assemble the
whole HTML from Python string parts. Pro: single file, no marker contract.
Con: ~800 lines of CSS/JS trapped inside Python string literals — no browser
preview, no syntax highlighting, every UX tweak is a Python diff; escaping the
escaping (JS template literals inside Python f-strings) is a standing foot-gun.

**Option 1C — template as a Python string module (`render_template.py`)
(viable, not recommended).** Middle ground; importable, no file-read. Same
no-browser-preview drawback as 1B with none of 1A's designer ergonomics.

### Axis 2 — `MODEL` embed mechanism (the exact L4(a) escape)

**Option 2A — `json.dumps(…, sort_keys=True, ensure_ascii=True,
separators=(",", ":"))` then `.replace("<", "\\u003c")` (Recommended).**
*What this means:* every non-ASCII character (including the JS-line-terminator
troublemakers U+2028/U+2029) is escaped by the serializer itself, and the one
remaining dangerous ASCII character `<` is converted to its JSON escape — which
is simultaneously valid JSON and valid JS, so `</script`, `<!--`, and any
HTML-ish payload in narrative text become inert. One mechanism, two properties,
trivially testable (assert `"<" not in embedded_payload`).

**Option 2B — `ensure_ascii=False` + targeted replaces of `<`, U+2028, U+2029
(viable, not recommended).** Smaller output for non-ASCII prose, but the safety
now depends on remembering an enumerated blacklist; 2A's whitelist (ASCII only,
then no `<` at all) is strictly easier to verify and the size delta is noise
next to the base64 font.

**Option 2C — `<script type="application/json">` + runtime `JSON.parse`
(viable, not recommended).** Still needs the same `</script` escaping, adds a
parse step and a failure mode (malformed JSON = blank page), buys nothing.

### Axis 3 — 3-level state machine shape (JS)

Grounding numbers from the golden model: 10 components, 150 micros (largest
component `cmp-tests` = 47 micros), nano rows capped at 8 + 1 collapsed.

**Option 3A — drill-down focus views (Recommended).** *What this means:* the
screen always shows exactly one level as the canvas. View state is a single
path array (`viewPath = []` → components view; `[cid]` → that component's
micros; `[cid, mid]` → that micro's nanos). Expanding a card re-renders the
canvas with the expanded card drawn as a full-width header panel (same card
anatomy §3.2: badge strip, title, prose, divider per §3.5) and its children
laid out in a grid below; the breadcrumb (§8.2) is derived from `viewPath` by
looking up embedded `name` fields only, segments navigate back up. Handles 47
children per view where a floating overlay cannot; collapse/expand is O(1)
state + one deterministic re-render, matching the example file's
full-re-render discipline (render() at example:845-886). At most ONE node
expanded per level by construction — no combinatorial overlay states.

**Option 3B — overlay-in-overlay (the example file's pattern extended one
level) (viable only for toy models, not recommended).** Faithful to the
archive, but a 47-child overlay is ~9,000 px wide floating over the macro map,
and a nano overlay inside it compounds the §3.5 foreignObject hazard. Fails at
the pilot's real size; rejected on the grounding numbers above.

**Option 3C — hybrid (overlay for component→micro, drill-down for micro→nano)
(viable, not recommended).** Two interaction grammars to learn and to test;
inherits 3B's width blowup exactly where it hurts most.

### Axis 4 — Golden-test assertion set

**Option 4A — three pinned goldens + structural battery + injection fixture
(Recommended).** *What this means:* the test renders the golden model twice —
once with no narratives (exercises L7's "no narratives yet" path) and once with
a small committed narratives fixture engineered to hit every NARRATIVE
treatment row (approved, proposed, stale via a wrong pinned signature,
unnarratable via the golden's real empty-signature components
`cmp-dist`/`cmp-invoice-cost`, orphaned via an unknown node id) — and pins
both sha256s. The golden model's 11 decisions are ALL FRESH (verified), so it
CANNOT exercise the decision half of the L3 matrix (red-team F4); a third,
purpose-built SYNTHETIC model fixture covers it — golden #3, detailed under
Chosen Approach §1. Structural asserts
(survive template edits better than the shas): embedded node count == model
walk count (407 for the golden incl. collapsed); exactly one `</script>`
sequence in the whole file (the template's own closer); zero `<` characters
inside the embedded payload; every expected `data-trust` value present in
golden #2 and the "no narratives yet" note present only in golden #1; render
twice ⇒ byte-identical; a dedicated injection fixture whose narrative text
contains `</script><script>` + `<!--` + U+2028 renders inert. Plus exit-code
tests: missing model → 2, malformed narratives → 2, missing narratives → 0.

**Option 4B — structural-only, no pinned sha (viable, not recommended).**
Robust to template churn but abandons the byte-determinism *proof* P3/P4
established (golden sha `56df3d86…` precedent); drift could hide in bytes no
structural assert covers.

**Option 4C — sha-only (viable, not recommended).** One-line test, but every
failure is opaque ("bytes differ") and the escaping/trust properties are only
tested incidentally.

### Axis 5 — CLI + config surface

**Option 5A — flags-only; ZERO new config keys (Recommended).** *What this
means:* the P6 chain gets exactly the stable surface it asked for and the
curated config file doesn't grow. Flags: `--model`, `--narratives`, `--config`,
`--out`, `--component <component-id>`, plus `--title <text>` (added by the
owner's OQ-P5-3 resolution 2026-07-06: optional; absent → fixed default title;
the value is user free text and flows through `_escape_viewmodel_json` like
any narrative prose). Defaults mirror the narrate commands'
discovery (graph_model.py:931-943): locate repo root via `di.find_db` +
`di.repo_root_for` (existence check only — the DB is never opened), then
model = `<root>/ssot-diagram/diagram-model.json`, narratives = the config's
existing `narratives_path` key via `gm._load_narrate_config`, out = axis 6
default. Every default overridable, so CI without a `.codegraph/` dir passes
explicit flags and never needs root discovery (no-DB + all-flags-given must
NOT die — this deliberately avoids reproducing P4's `cmd_narrate_reject`
tech-debt (a)). Exit 0 success / 2 die. No subcommands — one script, one verb.

**Option 5B — add a `render_out_path` config key (viable, not recommended).**
Symmetric with `narratives_path`, but it's a second place the output path can
be set (flag vs config precedence to document and test) for a path nobody has
asked to move; add it when a consumer actually needs it.

**Option 5C — all flags required, no discovery (viable, not recommended).**
Simplest code, but breaks the P6 one-command chain and the bare
`python3 render.py` workflow every sibling tool supports.

### Axis 6 — Output default path

**Option 6A — `<root>/ssot-diagram/ssot-diagram.html`; `--component` default
`<root>/ssot-diagram/ssot-diagram.<component-id>.html` (Recommended).** Sits
beside `diagram-model.json` (same `DEFAULT_OUTPUT_REL` directory convention,
graph_model.py:30-31), matches the roadmap exit criterion's artifact name
("a non-coder can open `ssot-diagram.html`", roadmap.md:157), deterministic for
P6. Component ids are already url/filename-safe slugs (`cmp-lib` shape,
load_config guarantees non-empty strings; bootstrap slugs at
graph_model.py:148).

**Option 6B — repo root `ssot-diagram.html` (viable, not recommended).** More
discoverable but pollutes the consuming repo's root and breaks the
"tool-owned files live in the tool's directory" pattern.

**Option 6C — beside whatever `--model` points at (viable, not recommended).**
Clever for ad-hoc runs, surprising for P6 (output location varies with input
location).

### Rejected alternatives (one line each)

- Any JS/graph library (d3, cytoscape, mermaid) — violates the zero-external-deps rule and the L5 dumb-painter principle.
- Static SVG/PNG export instead of interactive HTML — fails the roadmap exit criterion (click from system view down to a function).
- Deriving status/counts/fallbacks in browser JS — violates L2 and Block 5b's consumer obligation; the whole point is that the painter cannot lie.
- Writing derived `stale`/`unnarratable` back into `narratives.json` at render time — violates Block 5a (stored set is proposed|approved only) and makes a read a mutation.
- Making render a `graph_model.py narrate render`-style subcommand — overruled by locked L1.
- Google Fonts `<link>`/`@import` like the archived files — overruled by locked L5.
- One HTML per component stitched with iframes for the full view — multiple files violate L1's ONE self-contained artifact.
- Hand-authored `col`/`row` layout hints in the model (example file's approach) — the model is machine-emitted; layout hints would be un-curated noise and Block 4 lists layout hints as never-frozen.

## Chosen Approach

**In plain terms:** one new Python script joins the map and the sentences,
stamps every card with its final text and an honest badge, pours the result
into a repo-owned HTML shell, and saves it atomically. The browser file that
comes out knows nothing about signatures or trust — it just draws what Python
already decided.

### 1. Files

- `ssot-diagram/render.py` — the CLI (new).
- `ssot-diagram/render_template.html` — the shell (new): CSS tokens + card/edge
  painters adapted from the archived example file's corrected patterns; carries
  two splice sentinels, each containing a literal `<`:
  `/*<SSOT:VIEWMODEL_JSON>*/null` (the whole token, in
  `const MODEL = /*<SSOT:VIEWMODEL_JSON>*/null;` — so the raw template is
  still valid, browser-previewable JS) and `/*<SSOT:FONT_FACE>*/` (inside the
  `<style>` block). **Sentinel invariant (red-team F3, pinned for this repo
  AND the plan-visualizer seam): every splice sentinel MUST contain a
  character the payload escape guarantees absent from the escaped payload —
  here `<`, since `_escape_viewmodel_json` converts every `<` to `<`.**
  Pure-ASCII underscore markers are NOT collision-proof: they survive the
  escape verbatim, so free text (a `--title`, an LLM narrative discussing
  these very markers) could corrupt the splice or trip the count assert. A
  static comment `<!--SSOT:GENERATOR-->` carries a fixed generator note (no
  timestamp; not a splice target — never replaced).
- `ssot-diagram/assets/DMSans-Regular.woff2`, `DMSans-Medium.woff2`,
  `DMSans-Bold.woff2` + `ssot-diagram/assets/OFL.txt` — vendored (weights
  400/500/700 exactly as the locked spec §2.1 loads; the spec's two uses of
  weight 600 render via browser synthesis from 500, identical to how the
  archived files behaved with only 400/500/700 loaded).
- `ssot-diagram/test_render.py` — pytest battery (axis 4A) +
  `ssot-diagram/testdata/mkt_engine.narratives.fixture.json` (small, committed,
  hits every NARRATIVE treatment row against the real golden model) + an
  injection fixture.
- `ssot-diagram/testdata/trustmatrix.model.json` +
  `ssot-diagram/testdata/trustmatrix.narratives.json` — golden #3's inputs
  (red-team F4): a SMALL hand-written synthetic model (2 components, 2 micros,
  ~3 nanos + 1 collapsed node, one empty-signature component) whose
  `decisions` list contains at least one decision in EVERY status the L3
  matrix names — FRESH, STALE, ORPHANED, AMBIGUOUS, and literal
  `"superseded"` — with attachments on visible nodes, plus a narratives file
  hitting every derived narrative status (approved-fresh, proposed, stale,
  unnarratable, none, orphaned). The real golden model cannot provide this
  (its 11 decisions are all FRESH), so without this fixture the danger-badge
  decision painters — including the "STALE decision painted as
  FRESH-positive" laundering class — would ship untested. Render of this
  fixture is pinned as the third golden sha + per-row `data-trust`/badge
  structural asserts covering BOTH matrix halves.
- `manifest.json` — new entry `"ssot-render"`: `{"script":
  "ssot-diagram/render.py", "scope": "repo", "desc": "ssot-diagram P5 — render
  diagram-model + narratives into one self-contained interactive HTML",
  "hooks": []}` (CLI-first; P6 owns hook wiring; entry shape per
  piggyback.py:115-119 which honors optional `args`).

### 2. Pipeline inside `render.py`

`main → build_parser → cmd_render`:

1. Resolve paths (axis 5A). `_render_paths(args)` mirrors
   `_narrate_root_paths` (graph_model.py:931-943) but tolerates a missing
   `.codegraph` when every path is given explicitly.
2. Load inputs. `gm._load_model` (die 2 on absent/bad — absent model means
   "run extract first", matching L7) and `gm._load_narratives` (absent → `{}`;
   malformed → die 2). If the narratives FILE is absent (distinct from empty):
   set `viewmodel.note = "no narratives yet — run graph_model.py narrate"` and
   `gm.warn(...)` to stderr; exit stays 0.
3. Join: `build_viewmodel(model, narratives, component=None, title=None) ->
   dict` — §3. `title` carries the optional `--title` value (OQ-P5-3
   resolution); `None` → the fixed default, so goldens pin the default path
   and same flags ⇒ same bytes either way.
4. Fonts: `_font_face_css()` base64-encodes the three vendored woff2 files into
   `@font-face` rules (deterministic: fixed files, fixed order, standard
   base64).
5. Splice: `_render_html(template_text, viewmodel, font_css) -> str` — pinned
   order (red-team F3): assert BOTH sentinels occur exactly once BEFORE any
   replace (die 2 otherwise); replace the font sentinel (font CSS is
   repo-controlled base64 + fixed rules, contains no sentinel); replace the
   view-model sentinel (the escaped payload contains no `<`, hence no
   sentinel); assert zero sentinels remain (die 2). With `<`-bearing sentinels
   the order is no longer collision-load-bearing, but pinning it keeps the
   asserts' meaning unambiguous.
6. Write: `_save_text(path, html)` — temp + `os.replace`, trailing newline,
   the same atomicity discipline as `_save_model` (graph_model.py:1268-1277;
   not reused directly because that function serializes JSON).
7. `--component <cid>`: unknown id → die 2 listing known component ids;
   otherwise `build_viewmodel(..., component=cid)` emits the scoped view-model
   (chosen component's full tree + stub cards, §5) into the axis-6A per-component
   default path.

### 3. `build_viewmodel` — the trust join (the heart of L2)

One walk of the nested model (same traversal as `_build_sig_index`,
graph_model.py:842-865). For every component/micro/nano:

- `status = gm._derive_status(narratives.get(node_id), node["signature"])`.
- Final prose per the L3 matrix: status in {approved, proposed, stale} → the
  STORED entry's `text` (for stale that is deliberately the OLD text);
  {none, unnarratable} → `gm._fallback_text(node)`. Emitted as
  `prose: {"text": …, "status": …, "source": "narrative"|"fallback"}`.
- Orphaned narrative entries (id not in the model) are counted to stderr
  (`info`) and never enter the view-model — L3's orphaned row.
- Collapsed nodes (`kind == "collapsed"`) bypass the join entirely: they carry
  `name` ("+K more") and `collapsed_count` from the model; `_fallback_text` is
  never called on them (it raises, graph_model.py:926).
- Decision chips: each node's `decisions` id list is resolved against a dict
  built once from `model["decisions"]`; an id that fails to resolve → die 2
  (model is self-inconsistent — fail loud, never a silent default). Chip =
  `{id, name, doc, status, badge}` where badge is precomputed in Python from
  the status per L3 (FRESH→positive, STALE/ORPHANED→danger, AMBIGUOUS→danger
  palette + "AMBIGUOUS — anchor unclear" label, superseded→disabled).
- Every display string the painter needs is precomputed: edge labels
  (`"calls ×12"` from `kind` + `count`), child-count subtitles, per-node
  `tooltip` blocks (F2: name, kind label, chip text, joined prose, capped
  `"file.ts:123"` samples), the header subtitle. **Subtitle semantics pinned
  (red-team F5):** the decision count is the number of UNIQUE decision names,
  not attachment nodes — the golden renders `"10 components · 8 decisions"`
  (its 11 decision NODES collapse to 8 unique ADRs; ADR-0001/0003/0007 attach
  to two components each). A non-coder reads "decisions" as distinct
  decisions, so that is what the number counts. This is what "no counts in
  JS" means operationally.
- **Non-frozen-field tech debt (STATE.md MINOR (b)) — not worsened:** the join
  reads `caller_count`/`is_exported`/`docstring` only INSIDE
  `gm._fallback_text`, which already applies documented defaults
  (`.get("caller_count", 0)` etc., graph_model.py:911-925). `render.py` adds
  no new reads of non-frozen fields; JS receives only the finished sentence,
  so a P3 rename degrades exactly one shared code path (P4's), already tracked
  for the P6 startup-guard fix. Handled-in-Python with documented defaults;
  loud-guard deferred to P6 — stated, per the dispatch requirement.
- Determinism: the view-model is assembled exclusively from the model's
  already-sorted arrays plus `sorted()` on any dict-derived list; serialization
  is `sort_keys=True`; no timestamps anywhere (`generated_at` is null in the
  model and is not copied into the view-model).

### 4. The escape points (L4, named exactly — two MECHANISMS, three named sinks)

- **(a) JSON-embed — `_escape_viewmodel_json(viewmodel) -> str` in
  `render.py`:** `json.dumps(viewmodel, sort_keys=True, ensure_ascii=True,
  separators=(",", ":")).replace("<", "\\u003c")` (axis 2A). The payload is
  spliced as a bare JS object literal (`const MODEL = <payload>;`), valid
  because the escaped JSON is simultaneously valid JS. The splice sentinel
  contains a literal `<` (see §1), which the escape guarantees absent from the
  payload — the collision-proofing lives in that character, not in the
  sentinel's obscurity (red-team F3). Test asserts the embedded region
  contains no `<`.
- **(b) DOM-insert — template JS:** every model-derived string reaches the DOM
  through exactly two helpers, `setText(el, s)` (assigns `el.textContent`) and
  `paintWrappedText(...)` (the `foreignObject` writer, which like the archived
  `renderWrappedText` at example:392-405 assigns `div.textContent`). The
  archived `buildLegend` uses `innerHTML` with interpolation
  (example:928-950); the template REWRITES it with
  `createElement` + `textContent`. Repo rule for the template: `innerHTML` may
  appear only as the literal clearing idiom `= ''`; `test_render.py` greps the
  template to enforce it.
- **(b′) Tooltip sink — same mechanism (b), pinned explicitly (red-team F2):**
  the archived files declare `data-title`/`data-type`/`data-desc` attributes
  but ship NO tooltip display code, so P5's tooltip renderer is net-new. This
  design does NOT carry the attribute pattern over: **no model-derived prose
  is ever stored in HTML attributes.** Cards carry only `data-node-id`; the
  tooltip handler (`showTooltip(nodeId)`) looks the node up in the in-memory
  `MODEL` map at hover time and fills the tooltip DOM exclusively via
  `setText` — mechanism (b), third sink. Tooltip CONTENT is precomputed in
  Python as `node.tooltip` (name, kind label, the chip text when the status
  has one, the node's joined prose, capped `file:line` samples) so the tooltip
  inherits the trust treatment (L3 matrix extension) with zero JS derivation.

### 5. Three-level interaction (axis 3A; UX pinned in the addendum)

State = `viewPath` (array of 0–2 ids) + `viewState` (pan/zoom, reused verbatim
from the example file, lines 955-1014). `paintView()` re-renders the canvas
for the current path: components view (macro cards, component edges, decision
chips) → component focus view (header panel + micro grid + micro edges) →
micro focus view (header panel + nano cards + nano edges + the collapsed
card). Grid layout: `ceil(sqrt(n))` columns, order = embedded array order,
row heights from the tallest card per row (generalizes example:480-533).
Breadcrumb derives labels from embedded `name` fields along `viewPath` only.
Edges whose far endpoint is outside the current view render to stub cards
(same card visual as L6's `--component` stubs) — one consistent grammar, no
silent edge loss. Stub cards never expand in place, but their click behavior
splits per the owner's OQ-P5-1 resolution (2026-07-06): **in the FULL
artifact, clicking a stub NAVIGATES** — it sets `viewPath = [neighborId]` and
jumps to that neighbor component's focus view (the data is embedded, the jump
is pure `viewPath` state); **in `--component` scoped files, stubs are INERT**
(the neighbor's tree is genuinely absent from that file) beyond the standard
§7.3 edge-highlight. Python precomputes the distinction: stubs carry
`"stub": true` plus `"stub_nav": true|false` (true only in the full
artifact's view-model) — the painter switches on the embedded flag, deriving
nothing. Visual cue distinguishing the two (spec tokens): a navigable stub
shows a trailing `→` glyph after its title, title in `var(--fg-body)`,
`cursor: pointer`, and the §1.3 focus ring (`var(--ring)` border) on hover;
an inert stub has no glyph, title in `var(--fg-disabled)`, default cursor, no
hover ring. Exact treatment pinned in the UX addendum §3 (the binding
contract).
The §3.5 foreignObject/animation conflict is avoided by construction: the
posG-outer/animated-inner split (example:657-658) is kept for the focus-view
header, and fit-to-view computes bounds from layout data, not `getBBox`
(example:988-1008).

### 6. Success criteria (done =)

1. `python3 ssot-diagram/render.py --model ssot-diagram/testdata/mkt_engine.model.json --narratives <fixture> --out /tmp/x.html` exits 0; rendering twice is byte-identical; sha matches the pinned golden.
2. Opening the artifact locally (no network): components view shows 10 macro cards; drilling `cmp-lib → store.ts` reaches nano cards incl. one "+K more"; breadcrumb tracks and navigates.
3. Every NARRATIVE matrix row is visibly distinct in golden #2 (data-trust attributes + badges); `cmp-dist` shows fallback text + unnarratable badge; every DECISION matrix row (FRESH/STALE/ORPHANED/AMBIGUOUS/superseded) is visibly distinct in golden #3 (the `trustmatrix` synthetic fixture); hovering a stale/proposed/unnarratable card shows the same chip text + muting in the tooltip (F2 inheritance).
4. Missing narratives file → artifact renders with the visible note, exit 0; corrupt narratives → exit 2; corrupt model → exit 2.
5. Injection fixture: narrative text containing `</script><script>`, `<!--`, U+2028 produces a file with exactly one `</script>` and no `<` in the payload region.
6. `--component cmp-lib` emits `ssot-diagram.cmp-lib.html` with full 3-level tree for cmp-lib and INERT labeled stubs (no `→` glyph, no navigation) for every neighbor referenced by a cross-component edge; in the FULL artifact, clicking the same stub navigates to the neighbor's focus view (OQ-P5-1 resolution).
7. `python3 -m pytest ssot-diagram/` — all new tests green, zero P1/P3/P4 regressions, golden model sha `56df3d86…` untouched (renderer never writes model/narratives).
8. `piggyback status` lists `ssot-render`.

### 7. Seam for plan-visualizer (consumer-only note)

BLUEPRINT's plan-visualizer wants "a plan as a picture over the code map". The
reusable seam is exactly two artifacts: `render_template.html`'s marker
contract (a second producer can splice its own view-model) and
`build_viewmodel`'s output shape (nodes with `prose`/`badge`/`stub` already
joined). This design deliberately does NOT define plan-visualizer's overlay
fields; it only commits to not renaming the two sentinels or the top-level
view-model keys without a contract note, and it binds any future producer to
the F3 sentinel invariant: a splice sentinel must contain a character the
payload escape guarantees absent (here `<`).

## Risks

- **A trust bug in the join silently launders drifted prose (the one
  catastrophic failure).** Mitigation: the join calls P4's `_derive_status`
  verbatim (import, no copy); golden #2 pins one node per NARRATIVE matrix row
  (stale manufactured via a wrong pinned signature; unnarratable via the
  golden's real empty-sig components) and golden #3 (the `trustmatrix`
  synthetic fixture, red-team F4) pins one decision per DECISION matrix row —
  so any branch regression on either matrix half flips a pinned sha AND a
  `data-trust`/badge structural assert.
- **Pinned-sha brittleness: every deliberate template edit breaks two shas.**
  Mitigation: structural asserts carry the safety load (escaping, counts,
  trust rows) so the sha is a determinism tripwire, not the only oracle;
  regeneration procedure documented in the test file header, mirroring P3's
  golden discipline.
- **Layout collapse at real-repo scale (47-micro component).** Mitigation:
  drill-down (axis 3A) bounds every view; grid layout tested against the
  golden's largest component; pan/zoom (STANDARD rung) is the escape hatch,
  and if cut it is cut visibly per L9.
- **foreignObject text mispositioning (the documented §3.5 browser conflict).**
  Mitigation: adopt only the example file's corrected pattern (outer transform
  `<g>` / inner animated `<g>`); never attach the animation class to a
  transformed group; fit-to-view avoids `getBBox`.
- **Font vendoring goes wrong (missing file, wrong license artifact).**
  Mitigation: `_font_face_css()` dies (exit 2) if an asset file is absent —
  fail-loud beats emitting an HTML that silently falls back to system fonts
  and masks the zero-network rule; `OFL.txt` ships beside the woff2 files and
  the HTML head carries an attribution comment.
- **Marker contract drift (someone edits the template and mangles a
  sentinel).** Mitigation: occurrence-count checks around the splice (exactly
  1 before, exactly 0 after, die 2 otherwise) plus the golden test.
- **P3's non-frozen fields (`caller_count`/`is_exported`/`docstring`) rename
  and fallback sentences degrade silently.** Mitigation: renderer confines all
  reads to `_fallback_text` (single shared path, documented defaults);
  explicitly deferred loud-guard stays with P6 per STATE.md — this design adds
  no second read site, so the debt does not widen.
- **Output size creep on bigger repos.** Mitigation: view-model carries only
  painter-needed fields (signatures, `dominant_class`, raw `docstring` are NOT
  copied through — prose is already joined); `sample_callers` stays model-capped
  at 3. The overall artifact-size ceiling and the commit-vs-gitignore policy
  for the generated HTML are OPEN with the owner (OQ-P5-4, red-team F6) — this
  bullet mitigates creep, it does not set the budget.

## Open Questions

> **ALL THREE RESOLVED BY OWNER 2026-07-06 (design gate, AskUserQuestion):**
> **OQ-P5-1 → NAVIGABLE in the full artifact** (owner overrode the inert
> recommendation): clicking a stub card in the full artifact jumps to that
> neighbor component's focus view; stubs stay inert in `--component` scoped
> files (the neighbor's data is genuinely absent there). Spec must pin both
> behaviors + the visual cue distinguishing them.
> **OQ-P5-2 → FETCH + COMMIT the woff2 binaries** (+ `OFL.txt`) at
> implementation time, per the recommendation.
> **OQ-P5-3 → ADD `--title` flag** (owner overrode the fixed-title
> recommendation): optional `--title <text>`; when absent, the fixed default
> title + precomputed subtitle apply. Flag value flows through the same
> escaping path as narrative text (it is user-supplied free text). Determinism:
> same flags ⇒ same bytes; title participates in goldens via the default.
> The sections below are kept as the historical record of the fork.

**OQ-P5-1 — What are the exact stub-card semantics inside the FULL artifact's
focus views?**

Right now, locked decision 6 defines stub cards for the `--component` scoped
FILES, and this design (Chosen Approach §5) proposes reusing the same stub
grammar inside the full artifact's focus views so cross-component edges never
silently vanish. The question: in the full artifact, should clicking a stub
card navigate to that neighbor component's focus view (stubs become links), or
stay inert exactly as in the scoped files?

**If navigate:** better exploration flow, but stubs are no longer "non-expandable" everywhere and the two contexts behave differently.
**If inert everywhere:** one rule, simplest painter, matches the locked wording; the user pans back up via breadcrumb instead.

Recommendation: inert everywhere for this phase. One consistent rule is easier
to trust and to test; navigation-from-stub is a cheap later addition. Not a
blocker.

**OQ-P5-2 — Where do the vendored DM Sans woff2 bytes come from, exactly?**

Right now, no woff2 exists anywhere in the workspace (verified by search), so
implementation must fetch the three static-weight files once (google/fonts OFL
directory) and commit them. The question: is committing ~60–70 KB of binary
font assets to this repo acceptable to the owner (it is what locked decision 5
says, but the fetch-and-commit act itself happens at implementation time and
installs a binary blob).

**If commit the binaries:** locked decision 5 satisfied literally; builds are hermetic forever.
**If a build-time download step instead:** repo stays text-only, but rendering gains a network dependency — which contradicts the spirit of L5.

Recommendation: commit the binaries with `OFL.txt` beside them — that is the
plain reading of locked decision 5. Flagged only because adding binaries is
externally visible and hard to shrink from history later. Not a blocker for
spec/plan; the implementer needs the files before the golden shas can pin.

**OQ-P5-3 — Should the full artifact's title/subtitle carry the pilot repo's
name?**

Right now, the model has no repo-name field, so the design uses a fixed title
("SSOT diagram") plus a Python-precomputed subtitle ("10 components · 11
decisions"). The question: add a `--title` flag now or keep zero cosmetic
flags.

**If add `--title`:** nicer artifact header for multi-repo use; one more flag to freeze for P6.
**If keep fixed:** smaller surface; P6 can pass nothing; a later flag addition is backward-compatible.

Recommendation: keep fixed this phase — scope discipline; adding a flag later
breaks nothing. Not a blocker.

**OQ-P5-4 — Artifact-size ceiling and commit-vs-gitignore policy for the
generated HTML (red-team F6). STATUS: RESOLVED BY OWNER 2026-07-06
(AskUserQuestion): size 1–1.5 MB per artifact ACCEPTED; the generated
`ssot-diagram.html` is COMMITTED to the repo (not gitignored) — a non-coder
can always open the last render with zero setup. Consequence accepted: a
~1 MB+ diff on each regeneration (P6 auto-regen will grow history; revisit
there if it hurts). No max-repo-size budget set — `--component` remains the
documented escape hatch for large repos.**

Right now, the design estimates the pilot artifact at 1–1.5 MB (~407 painted
nodes) and calls that acceptable, but no owner-ratified budget exists for the
tool's target maximum repo size, and nothing states whether
`ssot-diagram.html` is committed (a ~1.5 MB diff on every render) or
gitignored. At much larger repos the model is many MB and the artifact could
be tens of MB / thousands of DOM nodes, with `--component` as the only escape
hatch.

**If a size budget + gitignore:** predictable repos, but the artifact must be regenerated to be viewed (P6's regeneration plumbing becomes load-bearing).
**If committed artifacts:** a non-coder can always open the last render, at the cost of large binary-ish diffs each regeneration.

This is a budget/operating-burden call the design may record but not decide.
Blocker for: the plan's done-criteria wording only; not for spec structure.

## ADR references

- `adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` —
  the sibling-import seam this design extends (`render.py` → `graph_model.py`).
- `adrs/0002-render-trust-derivation-in-python-js-dumb-painter.md` — NEW,
  drafted with this design: records locked L2 (trust joined in Python; browser
  JS derives nothing) with its alternatives and consequences.
- `adrs/0003-proposed-narratives-render-marked-not-hidden.md` — NEW, drafted
  with this design: records the L3 posture that unreviewed (`proposed`) prose
  renders visibly marked rather than being suppressed.

## Read-set

Files actually surveyed for this design (line ranges = load-bearing regions):

- `ssot-diagram/graph_model.py` — FULL (1-1496). Key: `_derive_status`
  1000-1014; `_fallback_text` 898-926; `_first_sentence` 881-895;
  `_load_narratives` 946-956; `_load_model` 831-839; `_load_narrate_config`
  809-828; `_narrate_root_paths` 931-943; `_build_sig_index` 842-865;
  `_save_model` 1268-1277; `EMPTY_SIG` 80; collapsed-node shape 390-396;
  `_aggregate_component_edges` 742-778; decision node build 692-715; model
  assembly 1399-1406; CLI 1425-1478; defaults 30-37.
- `ssot-diagram/decision_index.py` — targeted: status constants 62; `die`
  327-329; `open_db` wrapper 72-75; `_shared` imports 50-57.
- `_shared/db.py` — `find_db` 22-31 (existence-only walk), `repo_root_for` 34.
- `ssot-diagram/ssot-diagram.config.json` — FULL (1-59): keys incl.
  `narratives_path`, `nano_cap`, `narrate_threshold`.
- `ssot-diagram/testdata/mkt_engine.model.json` — programmatic survey: 10
  components / 150 micros / 407 tree nodes; largest component 47 micros;
  largest micro 9 children; decisions all FRESH; empty-sig components
  `cmp-dist`, `cmp-invoice-cost`; file sha `56df3d86…`.
- `manifest.json` — FULL (1-58): entry shape incl. `hooks: []` precedent.
- `piggyback.py` — targeted: manifest consumption 74-119 (`script`, optional
  `args`, scope).
- `ssot-diagram/CLAUDE.md`, `../CLAUDE.md`, `ssot-diagram/STATE.md` (1-223),
  `ssot-diagram/CONTEXT.md`, `ssot-diagram/AI-artifacts/roadmap.md` 139-201,
  `docs/roadmap/skeleton-contracts.md` 139-209,
  `adrs/0001-…md` — FULL.
- Archived design inputs — FULL: `design-system/spec.md` (1-569; §3.5
  implementation note 207-220, §8.2 breadcrumb 504-515, §7.2 tooltips, §7.4
  pan/zoom), `design-system/template.html` (1-816; Google Fonts cheat 7-9;
  in-place expand renderCard 418-539 — carries the §3.5 bug),
  `diagrams/example-system-architecture.html` (1-1032; corrected
  `renderExpandedOverlay` 649-738 with posG split 657-658; `expandedNodes` +
  full re-render 845-923; `routeEdge` 535-567; layout-data `zoomReset`
  988-1008; `buildLegend` innerHTML hazard 928-950), `script_spec.md` (1-307).

**What `script_spec.md` adds (reported per dispatch):** it is a CONTENT
contract for hand-authored diagram data, not a renderer rule-set: node label
grammar (2-4 words, noun form), description grammar (present tense, what+why),
`details` rows (`Key: Value`, 2-4 max), edge labels (1-3 word verbs), badge
COLOR semantics (neutral=infrastructure, action=processing,
positive=external, danger=risk/boundary), `badgeLabel` vocabulary
(SERVICE/DATABASE/CACHE/API/ACTION/PROCESS — "don't invent new values"),
layout constraints (3-7 top-level nodes, 2-4 children) and anti-patterns. Most
of it targets an LLM writing diagram content — P5's content is machine-joined,
so only the badge-color semantics and edge-label brevity carry over (adopted
in the UX addendum's treatment table); its "2-4 children" constraint is
knowingly violated by real repos, which is one more reason axis 3A (drill-down)
replaces the overlay sizing assumptions.

## Assumptions to verify

Checkable factual claims the FCV step must confirm (floor, not ceiling):

- **A1** — `_derive_status(stored_entry, current_sig)` branch order is:
  empty-sig → "unnarratable"; entry None → "none"; sig None → "orphaned"; sig
  mismatch → "stale"; else stored status. `graph_model.py:1000-1014`. The
  entire trust matrix keys on this exact order.
- **A2** — `_fallback_text` raises `ValueError` for kinds outside
  {nano/function/method, micro/file, component}. `graph_model.py:898-926`.
  The join must branch on `collapsed` BEFORE calling it.
- **A3** — `_load_narratives` returns the INNER dict `{node_id: entry}`;
  absent file → `{}`; malformed → die 2. `graph_model.py:946-956`. L7's
  behavior split (absent-vs-malformed) rides on this.
- **A4** — Model top-level keys are exactly
  {version, generated_at, nano_cap, components, decisions};
  `generated_at` is null. `graph_model.py:1399-1406` + golden survey. The
  view-model deliberately drops `generated_at`.
- **A5** — Component-level edges keep the ORIGINAL micro/nano id as `target`
  (may belong to another component). `graph_model.py:742-778` (comment at
  749-751). Stub resolution requires the id→component map; if targets were
  pre-resolved this design over-builds.
- **A6** — Decision node `status` ∈
  {FRESH, STALE, ORPHANED, AMBIGUOUS, "superseded"}, uppercase for the four,
  lowercase literal for superseded. `graph_model.py:39-42, 692-698`. The badge
  precompute switches on these exact strings.
- **A7** — `die` prints `error: …` to stderr and exits 2.
  `decision_index.py:327-329`. All L7 failure modes assume exit code 2.
- **A8** — Golden fixture: sha256 `56df3d86…`; 10 components; 407 tree nodes
  including collapsed; `cmp-dist` and `cmp-invoice-cost` signatures ==
  sha256(""). Verified programmatically in this session; FCV re-confirms. The
  golden test's node-count assert and the unnarratable fixture row depend on it.
- **A9** — `di.find_db` walks parents checking `Path.is_file()` only — it
  never opens the DB. `_shared/db.py:22-31`. This is what lets the renderer
  claim "never touches the DB" while reusing root discovery.
- **A10** — `piggyback.py` consumes manifest entries as
  `{script, scope, desc, hooks[], args?}` and an entry with `hooks: []` wires
  nothing but still registers/ships. `piggyback.py:74-119` + `manifest.json`
  `diagram-model` precedent. The new `ssot-render` entry copies that shape.
- **A11** — `json.dumps(..., ensure_ascii=True)` escapes U+2028/U+2029 (as
  ` `/` `) and ALL non-ASCII; the only remaining HTML-dangerous
  character in its output is `<` (and the `>` in `-->`, which is inert once
  `<` is escaped since `<!--` can no longer open). Python stdlib behavior —
  verify with a one-liner in FCV; the axis-2A escape's sufficiency rides on it.
- **A12** — Collapsed nodes carry ONLY
  {id, kind, name, collapsed_count, signature} — no path/edges/decisions/
  caller_count. `graph_model.py:390-396`. The join's collapsed branch reads
  nothing else.
- **A13** — `_load_narrate_config` returns `(narrate_threshold,
  narratives_rel)` and never dies on an absent config (defaults) — but dies if
  config is a non-object. `graph_model.py:809-828`. Render's `--config`
  handling reuses it unchanged.
- **A14** — The ssot-diagram narrate CLI precedent for default discovery dies
  when no `.codegraph` exists even if all paths are explicit
  (`_narrate_root_paths` calls `find_db` unconditionally,
  `graph_model.py:936-937`). Render deliberately DEVIATES (explicit-flags path
  skips discovery) — FCV should confirm the deviation is real (i.e. that the
  precedent behaves as described) so the spec words it as intentional.

## Delegation verdict

| Stage | Verdict | Evidence (one line) |
|---|---|---|
| spec-writing | big-model-only | New public CLI + a dual-language (Python↔JS) marker/view-model contract with no in-repo precedent; a small model transcribing the trust matrix one branch wrong produces a spec that launders drifted prose. |
| plan-writing | big-model-only | ≥2 plausible decompositions post-grid (template-first vs join-first; fixture-before-or-after-sha-pinning) and the golden shas can only be pinned after the font binaries land — sequencing judgment is unstated-knowledge-heavy. |
| implementation | big-model-only | Tier heavy by rule (implementation row at minimum) AND genuinely: ~800 lines of interaction/layout JS with a documented browser rendering trap (§3.5 foreignObject) that bounded-execution workers (MiniMax M3 / DeepSeek V4 Flash class) reproduce from the buggy template rather than the corrected example. |

## Red-team resolution (2026-07-06)

Report: `p5-html-renderer-redteam.md` (verdict REVISE; F1–F4 MAJOR + F5 MINOR
confirmed by the orchestrator; F6 escalated to the owner). What changed where:

- **F1 (stub contradiction vs owner ruling)** — Chosen Approach §5, Cast of
  characters, success criterion 6, and UX addendum §3 rewritten: stubs
  NAVIGABLE in the full artifact (embedded `stub_nav` flag, `viewPath` jump),
  INERT in `--component` files; visual cue pinned (`→` glyph + `--fg-body` +
  hover `--ring` vs no glyph + `--fg-disabled`).
- **F2 (tooltip third sink + hover laundering)** — L4 constraint + §4 gain
  sink (b′): no prose in HTML attributes, tooltip filled via `setText` from a
  Python-precomputed `node.tooltip` block; L3 matrix extended (design +
  addendum §2): tooltips INHERIT the node's trust treatment (chip text +
  muting on hover); success criterion 3 updated.
- **F3 (markers not collision-proof + editing artifact)** — sentinels replaced
  with `<`-bearing tokens (`/*<SSOT:VIEWMODEL_JSON>*/null`,
  `/*<SSOT:FONT_FACE>*/`); the false "impossible in escaped output" claim
  corrected; sentinel invariant pinned in §1 + §7 (plan-visualizer seam);
  splice order pinned in §2 step 5; the "— wait, no:" self-correction removed
  from §4.
- **F4 (decision matrix rows golden-untested)** — third synthetic golden
  added: `testdata/trustmatrix.model.json` + `trustmatrix.narratives.json`
  (every decision status + every derived narrative status), pinned sha #3 +
  per-row structural asserts; axis 4A, §1 Files, Summary, Risks, success
  criterion 3 updated.
- **F5 (subtitle double-count)** — subtitle semantics pinned in §3: count
  UNIQUE decision names ("10 components · 8 decisions" for the golden), never
  attachment nodes.
- **F6 (size ceiling / commit policy)** — left OPEN as OQ-P5-4
  (human-authority); Risks size bullet now points at it; owner's answer to be
  injected.
- Also folded (same session, pre-red-team owner gate): `--title` flag
  (OQ-P5-3 resolution) integrated into axis 5A + pipeline step 3 so the CLI
  surface no longer contradicts the resolution banner.
