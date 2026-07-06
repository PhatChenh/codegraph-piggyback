# Phase 5 — Interactive HTML renderer (`render.py`)

> Pipeline position: design (`../1_design/p5-html-renderer.md`, 868 lines, red-team
> folded F1–F6, OQ-P5-1..4 owner-resolved) → **spec (this doc)** →
> factual-code-verification → plan → implement.
> Binding companions: the design doc's Constraints (locked L1–L10 + FROZEN
> contracts), the UX addendum (`../1_design/p5-html-renderer-ux-addendum.md` —
> binding visual contract for the 4 new surfaces), and the archived spec
> (`~/all-projects/vibe-coding-setup/_archived/visualizer_guide/design-system/spec.md`
> — LOCKED for everything it covers). Nothing in those documents is reopened here.

## Purpose

In plain terms: everything below this phase already exists and is machine-checked —
the code map (`diagram-model.json`), the decisions with live freshness verdicts
inside it, and the human-gated plain-language sentences (`narratives.json`) pinned
to code fingerprints. P5 builds the picture: one new script, `render.py`, joins
those two files in Python and writes a single self-contained HTML file a non-coder
can open from disk, click from the system view down to an individual function, and
see what each piece is — in plain language — plus whether every explanation and
decision is still current. After this phase, the trust rules P4 fought for become
*visible*: a drifted explanation stops being an invisible database state and becomes
a red "needs review" badge on a card.

The one load-bearing property: **all trust verdicts are computed in Python at
render time** by importing P4's own functions. The browser JavaScript is a dumb
painter — it reads pre-joined fields out of one embedded `MODEL` constant and never
derives a status, a count, a default, or a sentence. If the JS is wrong it can only
draw ugly, never lie about trust (ADR-0002).

## Already built (reuse, do not rebuild)

Everything the renderer stands on already exists and is tested. The renderer
imports the trust recipe — it never copies it.

| Function / artifact | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| `_derive_status(stored_entry, current_sig)` | `graph_model.py:1000-1014` | The trust verdict: empty-sig → `unnarratable`; no entry → `none`; vanished node → `orphaned`; sig mismatch → `stale`; else the stored status. Branch order is load-bearing (TD-P4-1). | Called once per narratable node inside `build_viewmodel`. Import, NEVER copy, never re-order (L2, ADR-0002). | deep |
| `_fallback_text(node)` | `graph_model.py:898-926` | Deterministic one-sentence description from model fields only; raises `ValueError` on decision/collapsed kinds. | The prose for `none`/`unnarratable` nodes. The join branches on `kind == "collapsed"` BEFORE calling it. | deep |
| `_load_model(model_path)` | `graph_model.py:831-839` | Loads `diagram-model.json`; dies (exit 2) if absent or unparseable, with a "run extract first" message. | Render's model load — absent model = die 2 (L7). | deep |
| `_load_narratives(narratives_path)` | `graph_model.py:946-956` | Returns the INNER `{node_id: entry}` dict. Absent file → `{}`; malformed → die 2. | Render's narratives load. Render checks file existence itself first (the absent-vs-empty distinction drives the L7 "no narratives yet" note). | deep |
| `_load_narrate_config(config_path)` | `graph_model.py:809-828` | Permissive config reader → `(narrate_threshold, narratives_rel)`. Absent config → defaults; malformed JSON → warn + defaults; present-but-non-object → die 2. | Supplies the `narratives_path` default. Render ignores the threshold. | deep |
| `die` / `warn` / `info` / `ok` | `graph_model.py:47-60` (die = `di.die`, `decision_index.py:327-329`) | `die` prints `error: …` to stderr, exits 2. `warn` prints `! …` to stderr, no exit. | All fatal paths exit 2; the missing-narratives warning uses `warn` and exits 0 (L7). | deep |
| `di.find_db(cwd)` / `di.repo_root_for(db)` | `_shared/db.py:22-31` / `:34-36` (re-exported via `decision_index.py:49`) | Walks parent dirs checking `Path.is_file()` only — never opens the DB — then derives the repo root. | Default-path discovery ONLY. `render.py` never opens the DB at all (stronger than the repo's read-only rule). | deep |
| `EMPTY_SIG` | `graph_model.py:80` | sha256 of the empty string — the quarantined signature. | Not read directly by render (it lives inside `_derive_status`), listed so nobody re-derives it. | deep |
| `_save_model` pattern | `graph_model.py:1268-1277` | Atomic temp + `os.replace` write with trailing newline. | NOT reused directly (it serializes JSON); its atomicity discipline is replicated by render's text writer `_save_text`. | deep |
| `DEFAULT_CONFIG_REL`, `DEFAULT_OUTPUT_REL` | `graph_model.py:30-31` | `"ssot-diagram/ssot-diagram.config.json"`, `"ssot-diagram/diagram-model.json"`. | Render's `--config`/`--model` defaults. | deep |
| Golden model | `ssot-diagram/testdata/mkt_engine.model.json` (sha256 `56df3d86…`) | Frozen P3 output: 10 components, 150 micros, 407 tree positions incl. 2 collapsed; empty-sig components `cmp-dist`, `cmp-invoice-cost`; 11 decision nodes = 8 unique ADRs, all FRESH. | Input to goldens #1 and #2. Its all-FRESH decisions are WHY golden #3 (synthetic) exists. | deep |
| Config file | `ssot-diagram/ssot-diagram.config.json` (59 lines) | v1 schema; already carries `narratives_path: "ssot-diagram/narratives.json"` and `narrate_threshold: 4`. | Render reads `narratives_path` via `_load_narrate_config`. ZERO new config keys (axis 5A). | shallow (data) |
| `manifest.json` entry shape | repo root; consumed at `piggyback.py:74-119` | `{script, scope, desc, hooks[], args?}`; `hooks: []` registers/ships without wiring events. | The new `ssot-render` entry copies the `diagram-model`/`narrative-sidecar` precedent. | deep |
| Archived design spec | `_archived/visualizer_guide/design-system/spec.md` (569 lines) | LOCKED visual contract: colors §1, typography §2, card anatomy §3, edges §4, spacing §5, groups §6, interactions §7, chrome §8. | The template transcribes its tokens verbatim. The UX addendum overrides exactly one clause it covers: §7.2's tooltip-content-from-attributes channel (superseded by F2 — no prose in attributes, ever). | deep (as a document) |
| Archived example file | `_archived/visualizer_guide/diagrams/example-system-architecture.html` (1032 lines) | Carries the CORRECTED patterns: posG-outer/animated-inner split (657-658), layout-data fit-to-view (988-1008), `renderWrappedText` via `textContent` (392-405), pan/zoom (955-1014), full-re-render discipline (845-886). Also one hazard: `buildLegend` uses `innerHTML` interpolation (928-950) — must be REWRITTEN, not copied. | Source patterns for the template's JS. The sibling `template.html` carries the §3.5 in-place-expand bug (renderCard 418-539) — never adapt from it. | shallow (copy-with-care) |
| P4 tests baseline | `ssot-diagram/test_graph_model.py` | 108 tests; currently 105 pass / 3 pre-existing `TestGoldenLive` pilot-drift fails. | P5's regression bar is "zero NEW failures", not 108/108 (A19). | deep |
| ADRs 0001/0002/0003 | `ssot-diagram/adrs/` | Sibling-import seam; Python-join/JS-dumb-painter; proposed-renders-marked. | Constraints below restate them; the build must not contradict them. | deep (decisions) |

## Feature overview

In plain terms, the happy path: the owner runs one command. The script finds the
code map and the sentences (or is pointed at them with flags), computes every
node's final text and trust verdict in Python, pours the result plus the embedded
fonts into a repo-owned HTML shell, and saves one file. Opening that file shows the
system view: ten labeled cards, arrows between them, decision chips painted with
live freshness. Clicking a card's expand button makes that card become the screen —
its files lay out as the new canvas (drill-down focus views, never
overlay-in-overlay); clicking a file drills to its functions, including the honest
"+K more" overflow card. A breadcrumb always shows the way back. Hovering any card
shows a tooltip that carries the SAME trust marking as the card — hover is never a
trust bypass. Arrows that leave the current screen land on labeled stub cards: in
the full artifact clicking a stub jumps to that neighbor; in a `--component`
scoped file the stub is inert because the neighbor's data genuinely isn't there.

Edge cases, all deterministic: no `narratives.json` yet → everything renders with
machine fallback sentences plus a visible "no narratives yet" note, exit 0. A
malformed input → loud exit 2, nothing written. A narrative whose code drifted →
the OLD sentence, muted, with a danger badge. A narrative whose node vanished →
never rendered (counted to stderr). A node whose signature pins nothing
(empty-source) → fallback text + "UNNARRATABLE" badge, even if someone hand-edited
an entry for it. Same inputs ⇒ byte-identical HTML, always.

## Out of scope

Things a reader might assume are included, and are not:

- **Hook wiring / auto-regeneration** — `render.py` ships CLI-only (`hooks: []`).
  The PostToolUse re-extract + re-render chain is Phase P6.
- **`status --strict` roll-up, narrative GC, declined markers** — P6 (carried from
  P4's OQ-STRICT-1 / OQ-GC-1 / OQ-DECLINED-1).
- **plan-visualizer's overlay fields** — this phase commits only to the reuse seam
  (sentinel names, top-level view-model keys, the F3 sentinel invariant); it defines
  nothing about plan overlays. Phase D tool.
- **Writing anything back to `narratives.json`, the model, or the DB** — the
  renderer's only persisted output is the HTML artifact. Deriving
  `stale`/`unnarratable` and writing them back would violate Block 5a; rejected in
  the design's alternatives.
- **Committing a rendered pilot artifact in THIS repo at P5 close** — OQ-P5-4
  settled that generated `ssot-diagram.html` is committed (not gitignored) in the
  consuming repo, but not where the FIRST committed render lives. Deferred as
  OQ-P5-5 (human-authority: scope) — see Open Questions.
- **Any JS/graph library, static SVG/PNG export, per-component iframe stitching,
  hand-authored layout hints** — all explicitly rejected in the design's
  alternatives; do not resurrect.
- **Loud startup guard for P3's non-frozen fields** (`caller_count` /
  `is_exported` / `docstring`) — stays with P6 per STATE.md MINOR (b). This phase
  adds no new read site of those fields (all reads stay inside `_fallback_text`).

## Constraints

Non-negotiable rules, each with its source. The locked decisions and frozen
contracts below are transcribed from the design doc — they are binding inputs and
none is reopenable here.

**Locked decisions (owner grill 2026-07-06, restated not reopened):**

- **L1 — artifact:** new `ssot-diagram/render.py`, separate script, own
  `manifest.json` entry. Loads `diagram-model.json` + `narratives.json`, emits ONE
  self-contained interactive HTML file. Not a `graph_model.py` subcommand.
- **L2 — trust locus:** trust logic runs in PYTHON at render time; `render.py`
  imports `_derive_status` + `_fallback_text` from `graph_model.py`
  (sibling-import per `adrs/0001`; import, NEVER copy). Browser JS is a dumb
  painter: reads embedded fields only, derives NOTHING — no counts, no status, no
  defaults for missing fields. Source: ADR-0002.
- **L3 — status→treatment matrix (CONTRACT, transcribed exactly):**

  | Derived status | Treatment |
  |---|---|
  | approved | narrative as trusted prose (normal treatment) |
  | proposed | prose rendered, muted + "PROPOSED — unreviewed" badge (owner chose marked-visible over hidden) |
  | stale | OLD prose rendered, muted + danger "needs review" badge |
  | unnarratable | fallback text only + badge |
  | none | fallback text |
  | orphaned | entry's node absent from model; never renders |

  Decision nodes: FRESH → positive badge, STALE/ORPHANED → danger, superseded →
  disabled. AMBIGUOUS renders with the danger badge palette and the literal label
  "AMBIGUOUS — anchor unclear" (danger-adjacent per the grill's lean; distinct
  wording so it is never confused with a confirmed-stale decision). NEVER raw
  source dumps anywhere.

  **Matrix extension (red-team F2): tooltips INHERIT the node's trust
  treatment.** A node's hover tooltip shows the same prose the card shows, with
  the same muting and the same chip text carried into the tooltip body (e.g. a
  stale node's tooltip opens with "NEEDS REVIEW — CODE CHANGED" before the old
  prose). Stale/proposed/unnarratable prose never appears unmarked in a tooltip —
  hover is a rendering surface like any other, not a trust bypass.

  Exact colors/chips per row: UX addendum §2 (binding). Source: design Constraints
  L3 + ADR-0003.
- **L4 — HTML injection, escaped at BOTH points, three named sinks (CONTRACT):**
  (a) JSON-embed into `const MODEL = …` must be script-safe — the exact mechanism
  is `_escape_viewmodel_json` (component 6); (b) DOM-insert: all
  model/narrative-derived strings via `textContent` (or SVG-equivalent), never
  `innerHTML` — the exact helpers are `setText(el, s)` and `paintWrappedText(...)`
  (component 2); (b′) the tooltip is a third named sink riding mechanism (b): raw
  prose is never stored in HTML attributes; cards carry only `data-node-id`; the
  tooltip handler fills the tooltip DOM exclusively via `setText` from the
  Python-precomputed `node.tooltip` block. Source: design Constraints L4 + Chosen
  Approach §4.
- **L5 — fonts:** DM Sans embedded as base64 `@font-face` (OFL license,
  attribution vendored); woff2 files vendored into this repo. ZERO network fetches
  in the output HTML — the archived reference files cheat with Google Fonts
  `<link>` tags (template.html:7-9); do not copy that. OQ-P5-2 resolved: fetch +
  commit the binaries at implementation time.
- **L6 — `--component <id>` scoped view:** the chosen component's full 3-level
  tree + cross-component edges drawn to collapsed STUB cards of neighbor
  components (stub = non-expandable, labeled). Emits a per-component HTML file.
- **L7 — missing/malformed inputs:** missing `narratives.json` → render proceeds,
  every node gets fallback text, visible "no narratives yet" note in the artifact
  + stderr warning, exit 0. Malformed model or narratives → die exit 2 (P1/P3/P4
  convention, `decision_index.die` at decision_index.py:327).
- **L8 — byte-determinism:** same inputs ⇒ byte-identical HTML. Stable ordering
  everywhere, no timestamps, atomic temp + `os.replace` write. Golden smoke test
  like P3/P4: pinned sha256 + structural asserts.
- **L9 — scope ladder:** CORE = trust matrix, escaping, 3-level expansion,
  determinism + golden test, fallback text, embedded fonts. STANDARD (cut only
  visibly, announced in the run report) = breadcrumb, legend, tooltips, dark mode,
  pan/zoom, `--component` stub views. STRETCH = empty.
- **L10 — UX contract:** the archived spec is LOCKED for everything it covers; the
  UX addendum pins ONLY the 4 surfaces it never saw (3-level drill-down mechanics
  §1, trust-treatment visuals §2, stub cards §3, breadcrumb at 3 levels §4). The
  owner's OQ-P5-1 ruling is baked into addendum §3: stubs NAVIGABLE in the full
  artifact, INERT in `--component` scoped files, with the pinned visual cue.

**Sentinel invariant (red-team F3, CONTRACT — pinned for this repo AND the
plan-visualizer seam):** every splice sentinel MUST contain a character the
payload escape guarantees absent from the escaped payload — here `<`, since
`_escape_viewmodel_json` converts every `<` to `\u003c`. Pure-ASCII underscore
markers are NOT collision-proof: they survive the escape verbatim, so free text
(a `--title`, an LLM narrative discussing these very markers) could corrupt the
splice or trip the count assert.

**FROZEN skeleton contracts (do not redesign):**

- Block 4a: exactly three levels (component → micro → nano), no flat mode
  (skeleton-contracts.md:146-147).
- Block 4b: importable node fields = `id`, `kind`, `name`, `path`, content
  `signature` (skeleton-contracts.md:149-152). `caller_count`, `is_exported`,
  `docstring` are NON-frozen — render adds no new reads of them (all stay inside
  `_fallback_text`).
- Contract 6: edge kinds ⊆ `{calls, imports, references}` (ssot-diagram/CLAUDE.md)
  — legend and edge styling may assume nothing beyond these three.
- Block 5a/5b + amendments: stored narrative status ∈ {proposed, approved};
  `stale` is DERIVED live; empty-signature nodes derive `unnarratable`
  (skeleton-contracts.md:177-205). The renderer is a named "consumer obligation"
  holder — importing `_derive_status` is how it satisfies the obligation.
- L5-invents-nothing (ssot-diagram/CLAUDE.md layered model): the renderer is a
  dumb painter of L3+L4.
- Read-only DB, stronger here: **`render.py` never opens the DB at all.**
  `di.find_db` is used purely to locate the repo root for default paths
  (existence-only walk, `_shared/db.py:22-31`).

**Repo rules:** manifest registration required (new `ssot-render` entry); CLI must
run standalone; stdlib only, no new dependencies; tests live beside the code
(`test_render.py`); tool-owned outputs live under `ssot-diagram/`.

## Assumptions

Claims about existing code and data this spec depends on. The
factual-code-verification step confirms each independently. **A1–A14 are carried
verbatim from the design doc (they are a floor); A15–A20 are new, introduced by
this spec's decomposition.** Each is falsifiable — the last column says what would
prove it wrong.

| ID | Assumption | Source | What would prove it wrong |
|---|---|---|---|
| A1 | `_derive_status(stored_entry, current_sig)` branch order is: empty-sig → "unnarratable"; entry None → "none"; sig None → "orphaned"; sig mismatch → "stale"; else stored status. `graph_model.py:1000-1014`. The entire trust matrix keys on this exact order. | design A1 | Any other branch order in the live function. |
| A2 | `_fallback_text` raises `ValueError` for kinds outside {nano/function/method, micro/file, component}. `graph_model.py:898-926`. The join must branch on `collapsed` BEFORE calling it. | design A2 | The function returning (not raising) on a collapsed/decision node. |
| A3 | `_load_narratives` returns the INNER dict `{node_id: entry}`; absent file → `{}`; malformed → die 2. `graph_model.py:946-956`. L7's behavior split (absent-vs-malformed) rides on this. | design A3 | It returning the outer `{"narratives": …}` wrapper, or dying on an absent file. |
| A4 | Model top-level keys are exactly {version, generated_at, nano_cap, components, decisions}; `generated_at` is null. `graph_model.py:1399-1406` + golden survey. The view-model deliberately drops `generated_at`. | design A4 | Extra/missing top-level keys or a non-null timestamp. |
| A5 | Component-level edges keep the ORIGINAL micro/nano id as `target` (may belong to another component). `graph_model.py:742-778` (comment at 749-751). Stub resolution requires the id→component map; if targets were pre-resolved this design over-builds. | design A5 | Targets already resolved to component ids in the emitted model. |
| A6 | Decision node `status` ∈ {FRESH, STALE, ORPHANED, AMBIGUOUS, "superseded"}, uppercase for the four, lowercase literal for superseded. `graph_model.py:39-42, 692-698`. The badge precompute switches on these exact strings. | design A6 | Any other casing or vocabulary in emitted decision nodes. |
| A7 | `die` prints `error: …` to stderr and exits 2. `decision_index.py:327-329`. All L7 failure modes assume exit code 2. | design A7 | A different exit code or stdout printing. |
| A8 | Golden fixture: sha256 `56df3d86…`; 10 components; 407 tree nodes including collapsed; `cmp-dist` and `cmp-invoice-cost` signatures == sha256(""). Verified programmatically in the design session; FCV re-confirms. The golden test's node-count assert and the unnarratable fixture row depend on it. | design A8 | Differing sha/counts/signatures on the committed file. |
| A9 | `di.find_db` walks parents checking `Path.is_file()` only — it never opens the DB. `_shared/db.py:22-31`. This is what lets the renderer claim "never touches the DB" while reusing root discovery. | design A9 | Any `sqlite3.connect` inside `find_db`. |
| A10 | `piggyback.py` consumes manifest entries as `{script, scope, desc, hooks[], args?}` and an entry with `hooks: []` wires nothing but still registers/ships. `piggyback.py:74-119` + `manifest.json` `diagram-model` precedent. The new `ssot-render` entry copies that shape. | design A10 | `hooks: []` entries being skipped by `piggyback status`/`register`. |
| A11 | `json.dumps(..., ensure_ascii=True)` escapes U+2028/U+2029 (as `\u2028`/`\u2029`) and ALL non-ASCII; the only remaining HTML-dangerous character in its output is `<` (and the `>` in `-->`, which is inert once `<` is escaped since `<!--` can no longer open). Python stdlib behavior — verify with a one-liner in FCV; the axis-2A escape's sufficiency rides on it. | design A11 | Any non-ASCII or unescaped line terminator surviving `ensure_ascii=True`. |
| A12 | Collapsed nodes carry ONLY {id, kind, name, collapsed_count, signature} — no path/edges/decisions/caller_count. `graph_model.py:390-396`. The join's collapsed branch reads nothing else. | design A12 | Extra fields present, or one of the five absent. |
| A13 | `_load_narrate_config` returns `(narrate_threshold, narratives_rel)` and never dies on an absent config (defaults) — but dies if config is a non-object. `graph_model.py:809-828`. Render's `--config` handling reuses it unchanged. | design A13 | It dying on an absent file, or not dying on a JSON array. |
| A14 | The ssot-diagram narrate CLI precedent for default discovery dies when no `.codegraph` exists even if all paths are explicit (`_narrate_root_paths` calls `find_db` unconditionally, `graph_model.py:936-937`). Render deliberately DEVIATES (explicit-flags path skips discovery) — FCV should confirm the deviation is real (i.e. that the precedent behaves as described) so the spec words it as intentional. | design A14 | `_narrate_root_paths` already tolerating a missing DB when flags are explicit. |
| A15 | (NEW) Three nano ids in the golden appear at TWO tree positions each (per STATE.md P4 adjudication: `canRedo`, `canUndo`, `resetStore` under 2 micros each) — 407 tree positions vs 402 unique non-collapsed ids in the sig index. The duplicated positions carry IDENTICAL signatures, so the join yields the same prose/status at both positions and an id-keyed tooltip lookup is unambiguous (last-write-wins is harmless). | STATE.md "Plan/substrate contradictions"; this spec's node-count assert + tooltip design | The two positions of any duplicated id carrying different signatures — then `data-node-id` tooltip lookup could show the wrong trust verdict and the join must key tooltips per-position instead. |
| A16 | (NEW) `_load_narrate_config` returns `narratives_rel` as a plain relative-path STRING (not a `Path`, not absolute); render joins it as `root / narratives_rel`. `graph_model.py:826-828`. | this spec, component 3 | It returning an absolute path or `Path` object, breaking the join. |
| A17 | (NEW) `_derive_status`'s final branch returns the STORED status verbatim (`stored_entry.get("status", "proposed")`, `graph_model.py:1014`) — it does NOT validate the vocabulary. A hand-edited `narratives.json` can therefore surface an out-of-matrix status string to the join; `build_viewmodel` must fail loud (die 2) on any derived status outside {approved, proposed, stale, none, unnarratable, orphaned} rather than default silently. | this spec, component 5 | The function itself clamping/validating stored status — then the join's guard is dead code (keep it anyway; belt-and-braces on a trust path). |
| A18 | (NEW) The archived example file carries the corrected patterns at the cited regions — posG-outer/animated-inner split (657-658), layout-data `zoomReset` (988-1008), `renderWrappedText` assigning `div.textContent` (392-405), pan/zoom state (955-1014) — and the `buildLegend` `innerHTML` hazard at 928-950. Template authoring adapts ONLY the corrected regions. | design Read-set; this spec, components 2+8 | Those regions absent/moved in the archived file — the template author must re-locate them before adapting. |
| A19 | (NEW) The pytest baseline at P5 start is 105 pass / 3 pre-existing `TestGoldenLive` pilot-drift fails (108 total). P5's regression criterion is "zero NEW failures + golden sha `56df3d86…` untouched", not 108/108. | STATE.md verify section | A different baseline when the build starts — re-baseline before writing done-criteria into the plan. |
| A20 | (NEW) `warn(msg)` in `graph_model.py:51-52` prints `! msg` to stderr and does not exit; the L7 missing-narratives path (warn + exit 0) rides on it. | this spec, component 4 | `warn` exiting or printing to stdout. |

## Component dependency order

Eleven buildable components. This section documents what must exist before each
component can work — execution order and parallelization are owned by
`/plan-from-specs`. Every implementation choice left open is an explicit
**Decisions** entry; the plan must close all of them.

---

### 1. FONT-ASSETS — vendored DM Sans binaries + license

**Goal.** The three font files and their license live in the repo, so the output
HTML can embed them and never touch the network.

**Build.** Fetch once at implementation time (OQ-P5-2 resolution: fetch + commit)
and commit:
- `ssot-diagram/assets/DMSans-Regular.woff2` (weight 400),
  `DMSans-Medium.woff2` (500), `DMSans-Bold.woff2` (700) — static weights from the
  google/fonts OFL directory, ~60–70 KB total.
- `ssot-diagram/assets/OFL.txt` — the license, verbatim, beside the binaries.

The archived spec's two uses of weight 600 (legend title, header elements, §2.3)
render via browser synthesis from 500 — identical to how the archived files behaved
with only 400/500/700 loaded. No fourth file.

**Depends on.** None.

**Assumes.** None (the files don't exist yet — that's the point; the design
verified their absence by search).

**Decisions.**
- Q: Where does fetch provenance (source URL + retrieval date) get recorded?
  Options: HTML-head attribution comment only (the design already mandates one) /
  additionally in the git commit message / an extra `assets/README`. Leaning
  attribution comment + commit message — the design's file list names no README,
  and scope discipline says don't add one.

**Done when.** The three `.woff2` files and `OFL.txt` exist in
`ssot-diagram/assets/`; each woff2 starts with the `wOF2` magic bytes; total size
is in the expected ~60–70 KB band; no other font weight is present. (The golden
shas in component 10 CANNOT be pinned before this lands — the base64 blocks are
part of the bytes.)

---

### 2. TEMPLATE-SHELL — `render_template.html`: chrome, tokens, sentinels, safe DOM helpers

**Goal.** A real, browser-openable HTML file holding all CSS and the painter's
skeleton, with two splice sentinels — so every UX tweak is an HTML edit someone can
preview, never a Python edit.

**Build.** New `ssot-diagram/render_template.html` containing:
- **CSS tokens transcribed from the LOCKED archived spec**: §1 palette (light +
  dark via `data-theme`), §2 type scale/weights, §3 card anatomy + per-level
  sizes/typography + shadow/hover, §4 edge styles/arrowheads/labels, §5 spacing,
  §8 chrome (header, breadcrumb, buttons, legend panel, tooltip box per §7.2's
  trigger/position/box styling). Plus the addendum's chip styles (§2 tables) and
  stub styles (§3).
- **Page chrome**: header (title, subtitle, note slot, breadcrumb, zoom buttons,
  theme toggle), full-viewport canvas (SVG), legend panel, tooltip container.
- **The two splice sentinels, each containing a literal `<`** (sentinel invariant,
  Constraints): `const MODEL = /*<SSOT:VIEWMODEL_JSON>*/null;` — the whole token
  `/*<SSOT:VIEWMODEL_JSON>*/null` is the replace target, so the raw template is
  still valid, browser-previewable JS — and `/*<SSOT:FONT_FACE>*/` inside the
  `<style>` block. A static comment `<!--SSOT:GENERATOR-->` carries a fixed
  generator note (no timestamp; NOT a splice target — never replaced).
- **The two DOM-insert helpers (L4 mechanism (b))**: `setText(el, s)` (assigns
  `el.textContent`) and `paintWrappedText(...)` (the `foreignObject` writer,
  adapted from the example file's `renderWrappedText`, which assigns
  `div.textContent`). Every model-derived string reaches the DOM through exactly
  these two. The archived `buildLegend`'s `innerHTML` interpolation is REWRITTEN
  with `createElement` + `textContent`.
- **Template hygiene rule (repo rule, machine-enforced by component 10):**
  `innerHTML` may appear only as the literal clearing idiom `= ''`.
- **§3.5 conflict avoided by construction**: SVG positioning on an outer `<g>`,
  CSS animation on an inner `<g>` (example:657-658 pattern); fit-to-view computes
  bounds from layout data, never `getBBox`.
- A `@font-face`-less fallback chain (`'DM Sans', system-ui, …` per §2.1) so the
  RAW template previews with system fonts before splice.

**Depends on.** None (component 8 fills in the painter behaviors; this component
delivers the shell they hang on).

**Assumes.** A18.

**Interface shape.** The template's public contract (a real seam — `render.py`
today, plan-visualizer tomorrow): the two sentinel tokens, the `MODEL` constant
name, and the expectation that MODEL is either `null` (raw preview) or a
component-5 view-model. Hidden: all CSS, all painter internals.

**Dependency category.** in-process (a text file read by `render.py`; tested by
grepping + by the golden renders).

**Decisions.**
- Q: What does the raw template (MODEL === null) show when opened directly?
  Options: empty chrome + a small "template preview — no data spliced" note via
  `setText` / fully blank canvas. Leaning the note — it makes "browser-previewable"
  observable and costs one guard clause.

**Done when.** Opening the raw `render_template.html` from disk shows the page
chrome with zero console errors and zero network requests; each sentinel occurs
exactly once in the file; a grep for `innerHTML` finds only `= ''` occurrences;
the file contains no `<link>`/`@import` font loads.

---

### 3. CLI-PATHS — argument surface + path resolution

**Goal.** One script, one verb, flags-only, zero new config keys — and it works
both bare (inside an indexed repo) and fully-explicit (CI, no `.codegraph`
anywhere).

**Build.** In new `ssot-diagram/render.py`: `main → build_parser → cmd_render`
(no subcommands). Sibling import: `sys.path.insert(0, <script dir>); import
graph_model as gm` (mirrors graph_model.py:26-28). Flags:

- `--model`, `--narratives`, `--config`, `--out` — path overrides.
- `--component <component-id>` — scoped view (single value).
- `--title <text>` — optional (OQ-P5-3 resolution); absent → the fixed default
  title `"SSOT diagram"`. The value is user free text and flows through
  `_escape_viewmodel_json` like any narrative prose.

Path resolution (`_render_paths(args)`, mirrors `_narrate_root_paths` at
graph_model.py:931-943 but with the DELIBERATE deviation of A14): root discovery
(`di.find_db` + `di.repo_root_for` — existence check only, DB never opened) runs
ONLY if at least one of `--model`, `--narratives`, `--out` is absent; when all
three are explicit, no discovery happens and no-DB environments must NOT die.
Defaults: model = `<root>/ssot-diagram/diagram-model.json`
(`DEFAULT_OUTPUT_REL`); config = `<root>/ssot-diagram/ssot-diagram.config.json`
(`DEFAULT_CONFIG_REL`), overridable via `--config` without triggering discovery
when the other three are explicit; narratives = `<root>/<narratives_rel>` from
`gm._load_narrate_config` (threshold ignored); out =
`<root>/ssot-diagram/ssot-diagram.html`, or with `--component <cid>` →
`<root>/ssot-diagram/ssot-diagram.<cid>.html` (axis 6A; component ids are already
filename-safe slugs). `--out` beats both defaults. Discovery needed but no DB
found → die 2 with the standard "no .codegraph/codegraph.db found" message. Exit
0 success / 2 die, nothing else.

**Depends on.** None (pure argument plumbing; later components hang off it).

**Assumes.** A9, A13, A14, A16.

**Decisions.**
- Q: When `--config` is explicit but `--narratives` is not, the narratives default
  still needs the repo root (narratives_rel is relative). Options: run discovery
  in that case (consistent with "any defaulted path triggers discovery") / require
  `--narratives` whenever no DB exists. Leaning: discovery runs — the rule stays
  "explicit flags for every path you don't want discovered".

**Done when.** In a checkout with `.codegraph/` and an extracted model, bare
`python3 ssot-diagram/render.py` writes `<root>/ssot-diagram/ssot-diagram.html`
and exits 0. In a directory with NO `.codegraph` anywhere above it,
`render.py --model M --narratives N --out O` succeeds (this is the A14 deviation,
observable). `--component cmp-lib` with no `--out` writes
`ssot-diagram.cmp-lib.html`. `render.py --help` lists exactly the six flags.

---

### 4. INPUT-LOAD — loading + the L7 failure split

**Goal.** The two input files load through P4's own loaders, and every failure
mode lands exactly where L7 pinned it: absent narratives is a note, everything
malformed is a loud exit 2.

**Build.** Inside `cmd_render`:
- Model: `gm._load_model(model_path)` — absent or malformed → die 2 ("run extract
  first" for absent, per the existing function).
- Narratives: `render.py` checks `narratives_path.is_file()` ITSELF first
  (because `gm._load_narratives` conflates absent with empty): file absent → use
  `{}`, set the view-model `note` to the literal
  `"no narratives yet — run graph_model.py narrate"`, call `gm.warn(...)` to
  stderr, and continue to exit 0. File present → `gm._load_narratives(path)`
  (malformed → die 2; present-but-empty `{}` → NO note, no warn — the file exists,
  it's just empty).
- Config: `gm._load_narrate_config(config_path)` — used only for the narratives
  default (component 3); its die-on-non-object behavior is inherited unchanged.
- Template: read `render_template.html` from the script's own directory
  (`Path(__file__).parent`), NOT from the target repo — the template ships with
  the tool. Absent/unreadable template → die 2.

**Depends on.** Component 3 (paths).

**Assumes.** A3, A7, A13, A20.

**Decisions.**
- Q: Does the "no narratives yet" note also appear when the file exists but
  contains zero entries? Options: absent-only (L7's literal wording) / absent-or-
  empty. Leaning absent-only — L7 says "missing narratives.json"; an existing
  empty file is a curated state (P4 wrote it), and every node showing `none`
  fallback already tells the story.

**Done when.** With no narratives file: the artifact renders, contains the visible
note, stderr carries the `!` warning, exit 0. With a corrupt narratives file: exit
2, no output file written. With a corrupt or missing model: exit 2, no output
file written. (Observable via the component-10 exit-code tests.)

---

### 5. VIEWMODEL — `build_viewmodel`, the trust join (the heart of L2)

**Goal.** One Python function turns model + narratives into a render-ready
payload where every card's final text, badge, tooltip, edge label, and stub flag
is already decided — so the painter can be dumb.

**Build.** `build_viewmodel(model, narratives, component=None, title=None) ->
dict` in `render.py`. One walk of the nested model (same traversal shape as
`_build_sig_index`, graph_model.py:842-865). Behavior:

- **Trust join, per node (component/micro/nano):**
  `status = gm._derive_status(narratives.get(node_id), node["signature"])`. Final
  prose per the L3 matrix: status in {approved, proposed, stale} → the STORED
  entry's `text` (for stale that is deliberately the OLD text); {none,
  unnarratable} → `gm._fallback_text(node)`. Emitted as
  `prose: {"text": …, "status": …, "source": "narrative"|"fallback"}`. A derived
  status outside {approved, proposed, stale, none, unnarratable, orphaned} → die 2
  (hand-edited narratives vocabulary — fail loud, never a silent default; A17).
- **Orphaned entries** (id not in the model) are counted to stderr (`gm.info`)
  and never enter the view-model — the L3 orphaned row.
- **Collapsed nodes** (`kind == "collapsed"`) bypass the join entirely: they carry
  `name` ("+K more") and `collapsed_count` from the model; `_fallback_text` is
  never called on them (it raises — A2, A12). They paint per addendum §1's
  collapsed-card treatment (no badge strip, no tooltip beyond the label, not
  navigable).
- **Decision chips:** each node's `decisions` id list resolves against a dict
  built once from `model["decisions"]`; an id that fails to resolve → die 2 (model
  self-inconsistent — fail loud). Chip = `{id, name, doc, status, badge}` where
  `badge` is precomputed in Python per L3: FRESH→positive, STALE/ORPHANED→danger
  (+"NEEDS REVIEW" label), AMBIGUOUS→danger palette + literal
  "AMBIGUOUS — anchor unclear", superseded→disabled. Exact colors: addendum §2.
- **Every display string precomputed:** edge labels (`"calls ×12"` from `kind` +
  `count`), child-count subtitles per card, kind labels ("COMPONENT" / "FILE" /
  "FUNCTION" — addendum §2: badge strip communicates level, trust lives only in
  chips), per-node `tooltip` block (F2: name, kind label, the chip text when the
  status has one, the node's joined prose, capped `"file.ts:123"` samples from
  `sample_callers` — model-capped at 3), the header subtitle. **Subtitle semantics
  (red-team F5, pinned):** the decision count is the number of UNIQUE decision
  names, not attachment nodes — the golden renders `"10 components · 8 decisions"`
  (11 decision NODES collapse to 8 unique ADRs). This is what "no counts in JS"
  means operationally.
- **Per-view edge + stub precompute (dumb-painter enabler):** build an
  `id → owning component` map (and `id → owning micro`) in one model walk (A5).
  For each container (the top level, each component, each micro), emit
  `view_edges` — edges drawable in that container's focus view with endpoints
  RESOLVED to ids present in that view — and `stubs`, one per distinct outside
  owner any cross-view edge resolves to, each `{id, name, "stub": true,
  "stub_nav": true|false}` (true only in the full artifact's view-model; false in
  `--component` scoped view-models — OQ-P5-1). Stub placement/sorting per
  addendum §3 (single right-hand column, sorted by id). Top level: edges whose
  BOTH endpoints resolve to the same component are omitted there (their detail is
  visible inside the focus views — see Decisions). No edge is silently lost: every
  model edge either draws in some view or lands on a stub.
- **Scoped mode (`component=cid`):** unknown cid → die 2 listing known component
  ids. Otherwise the view-model carries only that component's full 3-level tree +
  its stubs (neighbors referenced by cross-component edges), all stubs
  `stub_nav: false`; the breadcrumb root is the component (addendum §4).
- **Legend block precomputed in Python (artifact-scope, addendum §2):**
  `legend: {node_types, edge_kinds, trust_chips}` listing exactly what is present
  in THIS artifact — the painter draws it verbatim, deriving nothing.
- **Title/subtitle/note:** `title` = the `--title` value or the fixed default
  `"SSOT diagram"`; subtitle as above; `note` = the L7 string or null.
- **Non-frozen-field debt not worsened:** the join reads
  `caller_count`/`is_exported`/`docstring` only INSIDE `gm._fallback_text` (which
  applies documented defaults). `render.py` adds no new reads; the loud-guard
  stays deferred to P6 per STATE.md MINOR (b) — stated, not silent.
- **Determinism:** assembled exclusively from the model's already-sorted arrays
  plus `sorted()` on any dict-derived list; no timestamps; `generated_at` is not
  copied. Payload carries ONLY painter-needed fields — signatures,
  `dominant_class`, raw `docstring` are NOT copied through.

**Depends on.** Component 4 (loaded inputs).

**Assumes.** A1, A2, A4, A5, A6, A8, A12, A15, A17.

**Interface shape.** The second half of the plan-visualizer seam. Top-level
view-model keys (renaming any needs a contract note): `title`, `subtitle`, `note`,
`scope` (`"full"` or the component id), `components` (nested tree), `view_edges`
(top level), `legend`. Per-node trust-bearing fields: `prose {text, status,
source}`, `chips[]`, `tooltip`, `stub`/`stub_nav` on stubs. Hidden: the join,
maps, resolution. Two adapters exist for the seam (render.py now, plan-visualizer
named in BLUEPRINT) — a real seam, not speculative.

**Dependency category.** in-process (pure function over two dicts; tested
directly).

**Decisions.**
- Q: In a MICRO focus view, an edge endpoint living in a SIBLING micro of the
  SAME component — stub as that sibling micro, or as the owning component
  (degenerate: the current component)? Addendum §3 defines only
  component-flavored stubs ("OTHER COMPONENT" badge), so a micro-flavored stub
  (e.g. badge "OTHER FILE") is a one-token EXTENSION of the binding addendum.
  Options: (a) sibling-micro stub with an "OTHER FILE" badge variant — most
  informative, needs the addendum extension recorded; (b) resolve to the owning
  component always — no extension, but a same-component arrow pointing at a card
  labeled with the CURRENT component is confusing. Leaning (a); the plan must
  record the extension against addendum §3 (same tokens, new badge label) or
  escalate if the owner considers it a visual-contract change.
- Q: Top-level self-edges (component edges resolving back into the same
  component): omit at the components view (leaning — the detail renders in the
  focus views, so nothing is lost) or draw as self-loops (§4 routing never
  defined self-loops)?
- Q: View-model tree duplication for the 3 duplicated nano ids (A15): emit the
  joined node at each tree position (leaning — mirrors the model, positions are
  what the painter lays out; identical content per A15) or dedupe to one position?
- Q: Icon keys (archived §3.4 resolves icons from label keywords in JS — a
  derivation the painter must not do): precompute `icon` per node in Python via a
  fixed kind→key table. Options for the table: component→`SERVICE`,
  micro→`default`, nano→`ACTION` / all-`default`. Leaning a fixed table chosen at
  plan time; the pinned rule is only "icon selection happens in Python, never by
  JS keyword scan".
- Q: Scoped-file subtitle text. Options: reuse the full-artifact formula scoped to
  the subtree (`"<K> files · <M> decisions"`) / omit. Leaning the scoped formula
  with unique-decision counting (F5 rule applies unchanged).

**Done when.** For the golden model + the component-9 narratives fixture: every
L3 NARRATIVE row appears on at least one node with the exact pinned
prose-source/status pairing; `cmp-dist` carries fallback text + `unnarratable`
even though the fixture ships an entry for it (branch order visible); the orphaned
fixture entry appears nowhere in the payload but is counted on stderr; the
subtitle string is exactly `"10 components · 8 decisions"`; stubs in the full
view-model all carry `stub_nav: true`, in `--component` view-models
`stub_nav: false`; running the join twice yields equal payloads. For the
trustmatrix fixture: every DECISION status maps to its pinned badge, including
literal `"AMBIGUOUS — anchor unclear"`.

---

### 6. EMBED-ESCAPE — `_escape_viewmodel_json` + `_font_face_css`

**Goal.** The payload that goes between `<script>` tags can never break out of
them, and the fonts arrive as deterministic base64 — the two "inert by
construction" steps.

**Build.** In `render.py`:
- `_escape_viewmodel_json(viewmodel) -> str` (L4 mechanism (a), axis 2A, exact
  formula pinned): `json.dumps(viewmodel, sort_keys=True, ensure_ascii=True,
  separators=(",", ":")).replace("<", "\\u003c")`. Every non-ASCII character
  (including JS line terminators U+2028/U+2029) is escaped by the serializer
  itself; the one remaining dangerous ASCII character `<` becomes its JSON escape
  — simultaneously valid JSON and valid JS, so `</script`, `<!--`, and any
  HTML-ish payload in narrative text (or a `--title`) is inert. The payload is
  spliced as a bare JS object literal. The escaped output contains no `<` — which
  is exactly what makes the `<`-bearing sentinels collision-proof (the invariant
  lives in that character, not in sentinel obscurity).
- `_font_face_css() -> str`: base64-encodes the three vendored woff2 files into
  three `@font-face` rules (weights 400/500/700), fixed file order, standard
  base64 — deterministic. Any asset file absent → die 2 (fail-loud beats silently
  falling back to system fonts and masking the zero-network rule). The emitted
  CSS is repo-controlled and contains no `<` and no sentinel.

**Depends on.** Components 1 (font files), 5 (the payload it escapes).

**Assumes.** A11.

**Done when.** For any view-model built from the fixtures: the escaped payload
contains zero `<` characters and zero bytes ≥ 0x80; escaping the same payload
twice is byte-identical. Deleting one woff2 file makes a render exit 2 with a
message naming the missing asset.

---

### 7. SPLICE-WRITE — sentinel splice + atomic write + `cmd_render` assembly

**Goal.** The escaped data and the font CSS land in the template at exactly one
place each, loudly failing if the template drifted — then the file hits disk
atomically.

**Build.** In `render.py`:
- `_render_html(template_text, viewmodel, font_css) -> str` — pinned order
  (red-team F3): (1) assert BOTH sentinels occur exactly once BEFORE any replace
  (die 2 otherwise); (2) replace the font sentinel `/*<SSOT:FONT_FACE>*/` (the
  font CSS contains no sentinel); (3) replace the view-model sentinel
  `/*<SSOT:VIEWMODEL_JSON>*/null` with the escaped payload (which contains no `<`,
  hence no sentinel); (4) assert zero sentinels remain (die 2). Splice =
  `str.replace` with occurrence-count checks, deterministic. With `<`-bearing
  sentinels the order is no longer collision-load-bearing, but pinning it keeps
  the asserts' meaning unambiguous.
- `_save_text(path, html)` — temp file + `os.replace`, trailing newline; the same
  atomicity discipline as `_save_model` (graph_model.py:1268-1277), not reused
  directly because that function serializes JSON.
- `cmd_render(args)` assembles the full pipeline: resolve paths (3) → load (4) →
  `build_viewmodel` (5) → `_font_face_css` + `_escape_viewmodel_json` (6) →
  `_render_html` → `_save_text` → `gm.ok(f"wrote {out_path}")`.

**Depends on.** Components 2, 3, 4, 5, 6.

**Assumes.** A7.

**Done when.** Rendering the same inputs twice produces byte-identical files
(sha256 equal). A template with a duplicated or deleted sentinel makes the render
exit 2 before writing anything. An interrupted write leaves the previous output
intact (temp + `os.replace`). The written file ends with exactly one newline.

---

### 8. JS-PAINTER — focus views, breadcrumb, stubs, tooltips, legend, theme, pan/zoom

**Goal.** The interactive layer a non-coder actually touches — every behavior a
pure function of the embedded data plus two integers of view state, deriving
nothing.

**Build.** Inside `render_template.html` (extends component 2's shell). The
painter's allowed operations, pinned: read embedded fields, index them by id,
compute layout geometry (positions/sizes), toggle view state. It NEVER computes a
status, count, label, or fallback (ADR-0002 — "no arithmetic, no conditionals on
trust fields, no `.get`-style defaulting" is the review standard).

- **Focus-view state machine (axis 3A, addendum §1):** state = `viewPath` (array
  of 0–2 ids) + `viewState` (pan/zoom, adapted verbatim from example:955-1014).
  `paintView()` fully re-renders the canvas for the current path (the example
  file's full-re-render discipline): components view → component focus view
  (header panel + micro grid) → micro focus view (header panel + nano cards +
  the collapsed card). Expand button pushes onto `viewPath`; the header panel's
  `−` pops one level. At most ONE node expanded per level by construction. Nano
  cards have no expand button, ever (Block 4a).
- **Grid layout:** `ceil(sqrt(n))` columns, order = embedded array order, row
  heights from the tallest card per row (generalizes example:480-533); gaps per
  archived §5.2, container padding per §5.3, canvas margin §5.4. Focus header
  panel reuses the §3.5 expanded-card look (badge strip, title, prose with its
  trust treatment, divider, 20px minimum padding).
- **Breadcrumb (addendum §4):** derived from `viewPath` by looking up embedded
  `name` fields only; hidden at top level; segments truncate `viewPath` on click
  (same operation as `−`, so they can never disagree); §8.2 tokens unchanged;
  scoped files root at the component.
- **Stubs (addendum §3, the binding contract):** painter switches ONLY on the
  embedded `stub`/`stub_nav` flags. Navigable stub: trailing `→` glyph, title
  `var(--fg-body)`, `cursor: pointer`, hover `var(--ring)` border; click sets
  `viewPath = [neighborId]`. Inert stub: no glyph, title `var(--fg-disabled)`,
  default cursor, no hover ring; click does nothing beyond §7.3 edge-highlight.
  Stubs never expand in place in either context.
- **Tooltips (L4 sink (b′), F2):** cards carry only `data-node-id`;
  `showTooltip(nodeId)` looks the node up in the in-memory MODEL index and fills
  the tooltip DOM exclusively via `setText` from the precomputed `node.tooltip`
  block — chip text first when present, prose in the card's muting. §7.2 trigger
  (300ms), position, box styling unchanged. No prose in attributes, ever.
- **Legend:** draws the embedded `legend` block verbatim (node types, edge
  styles, the Trust chip block) with createElement + `textContent`; §8.3 styling.
- **Edge painting:** rounded orthogonal + arrowheads + precomputed pill labels
  (§4); highlight-on-click + unconnected fade (§7.3); deselect on empty-canvas
  click (§7.5).
- **Theme toggle:** §7.6 verbatim (`data-theme`, `localStorage` key
  `diagram-theme`, `prefers-color-scheme` default).
- **Pan/zoom:** §7.4 verbatim (drag, wheel, 0.25–4x, buttons, fit-to-view from
  layout data — never `getBBox` — double-click, touch).

**Depends on.** Components 2 (shell + helpers), 5 (view-model shape — the
dual-language contract; the painter is written against component 5's Interface
shape).

**Assumes.** A15 (id-keyed lookup unambiguous), A18.

**Decisions.**
- Q: The id→node index the tooltip needs — built by JS at load time from the
  embedded tree (pure indexing, not derivation), or emitted by Python as a flat
  map beside the tree (payload duplication)? Leaning JS-builds-index: indexing is
  not deriving, and it keeps the payload minimal; the plan states this explicitly
  so reviewers don't flag the loop as "JS derives".

**Done when.** Opening the full artifact locally with the network disabled:
components view shows 10 macro cards; drilling `cmp-lib → store.ts` reaches nano
cards including one "+K more"; the breadcrumb tracks and navigates back;
hovering a stale/proposed/unnarratable card shows the same chip text + muting in
the tooltip; clicking a stub jumps to that neighbor's focus view; in a
`--component` file the same stub is inert (no `→`, no navigation); theme toggles
and persists across reopen; pan/zoom and fit-to-view work in every focus view.

---

### 9. FIXTURES — the three test input sets

**Goal.** Committed, hand-written inputs that make every row of both matrix
halves — and every escaping hazard — actually reachable by tests.

**Build.** Under `ssot-diagram/testdata/`:
- **`mkt_engine.narratives.fixture.json`** — small, against REAL golden-model
  ids, hitting every NARRATIVE treatment row: one approved entry whose signature
  is copied from the golden (→ approved), one proposed entry (fresh sig →
  proposed), one approved entry with a deliberately wrong pinned signature (→
  stale, OLD text), one entry for `cmp-dist` (empty-sig component → derives
  `unnarratable` DESPITE the stored entry — makes the A1 branch order visible),
  one entry with an unknown node id (→ orphaned, dropped + counted).
  `cmp-invoice-cost` gets NO entry (unnarratable-without-entry, the other flavor).
  Block 5a shape (`{node_id, signature, text, status}`, status ∈
  {proposed, approved}) wrapped in `{"narratives": {...}}`.
- **Injection fixture** (a narratives file, or an entry set within the fixture
  above — planner's choice, see Decisions): narrative text containing
  `</script><script>`, `<!--`, a literal U+2028, AND the literal sentinel text
  `/*<SSOT:VIEWMODEL_JSON>*/` inside prose (the F3 collision case) — plus a
  `--title` exercising the same characters in test runs.
- **`trustmatrix.model.json` + `trustmatrix.narratives.json`** (golden #3 inputs,
  red-team F4): a SMALL synthetic model — 2 components, 2 micros, ~3 nanos + 1
  collapsed node, one empty-signature component — schema-valid for the join
  (nested children, `signature` on every node, resolvable `decisions` ids,
  model top-level keys per A4). Its `decisions` list contains at least one
  decision in EVERY status the L3 matrix names — FRESH, STALE, ORPHANED,
  AMBIGUOUS, and literal `"superseded"` — attached to visible nodes; the
  narratives file hits every derived narrative status (approved-fresh, proposed,
  stale, unnarratable, none, orphaned). The real golden CANNOT provide the
  decision half (its 11 decisions are all FRESH) — without this fixture the
  danger-badge decision painters, including the "STALE decision painted as
  FRESH-positive" laundering class, would ship untested.

**Depends on.** Component 5 (fixtures are written against the join's semantics —
which statuses derive from which shapes), A8 (real golden ids/signatures).

**Assumes.** A4, A6, A8.

**Decisions.**
- Q: Injection strings as a separate fixture file or extra entries inside the
  main narratives fixture? Separate keeps golden #2's sha stable if injection
  cases evolve; combined is fewer files. Leaning separate file (the design lists
  "an injection fixture" as its own artifact).

**Done when.** All fixture files are committed; loading each through the real
loaders succeeds; for each L3 row (both halves) at least one fixture node/decision
derives exactly that status through the REAL `_derive_status`/join (no mocks).

---

### 10. TEST-BATTERY — `test_render.py`: three goldens + structural + injection + exit codes

**Goal.** Byte-determinism is proven, the trust matrix is pinned row-by-row, and
the escaping properties are asserted directly — so any regression flips a test,
not a reader's trust.

**Build.** New `ssot-diagram/test_render.py` (pytest, beside the code). The
battery (axis 4A):
- **Golden #1** — real golden model, NO narratives file: pinned sha256; the
  "no narratives yet" note present; stderr warning; exit 0; every node prose
  `source == "fallback"`.
- **Golden #2** — real golden model + `mkt_engine.narratives.fixture.json`:
  pinned sha256; every expected `data-trust` value present; note ABSENT;
  subtitle `"10 components · 8 decisions"` present.
- **Golden #3** — trustmatrix synthetic fixture pair: pinned sha256; per-row
  structural asserts covering BOTH matrix halves — each decision status's badge
  (incl. the literal "AMBIGUOUS — anchor unclear" and disabled superseded) and
  each narrative status's treatment.
- **Structural asserts** (carry the safety load; survive template edits better
  than shas): embedded node count == model tree-walk count (407 for the golden,
  tree POSITIONS incl. collapsed — A8/A15); exactly one `</script>` sequence in
  the whole file (the template's own closer); zero `<` characters inside the
  embedded payload region; render twice ⇒ byte-identical.
- **Injection test:** the injection fixture (incl. sentinel-text-in-prose and a
  hostile `--title`) renders to a file with exactly one `</script>`, no `<` in
  the payload region, and both sentinel-count asserts passing.
- **Exit-code tests:** missing model → 2; malformed model → 2; malformed
  narratives → 2; missing narratives → 0; unknown `--component` → 2 (message
  lists known ids); template with duplicated/deleted sentinel → 2; missing font
  asset → 2; no-DB + all-flags-explicit → 0 (the A14 deviation).
- **Template hygiene:** grep `render_template.html` — `innerHTML` only as
  `= ''`; each sentinel exactly once; no `<link>`/`@import` font loads.
- **Scoped view:** `--component cmp-lib` emits `ssot-diagram.cmp-lib.html`; its
  payload stubs all carry `stub_nav: false`; the full artifact's stubs carry
  `stub_nav: true`.
- **Regression guard:** golden model file sha `56df3d86…` untouched (renderer
  never writes model/narratives); full-suite baseline = zero NEW failures vs the
  105-pass/3-prefail baseline (A19).
- **Sha regeneration procedure documented in the test file header** (mirroring
  P3's golden discipline): shas are a determinism tripwire, not the only oracle;
  every deliberate template edit re-pins them via a stated command.

**Depends on.** Components 1–9 (tests are last; shas pin only after fonts land).

**Assumes.** A7, A8, A11, A14, A15, A19.

**Done when.** `python3 -m pytest ssot-diagram/` shows all new tests green and
zero new failures elsewhere; deliberately flipping one fixture status (locally)
fails BOTH a sha and a `data-trust` structural assert — demonstrating the
double-oracle before shipping.

---

### 11. MANIFEST — `ssot-render` registration

**Goal.** The tool ships: piggyback knows about it, with no hook events (P6 owns
wiring).

**Build.** Add to `manifest.json` `scripts`:
`"ssot-render": {"script": "ssot-diagram/render.py", "scope": "repo", "desc":
"ssot-diagram P5 — render diagram-model + narratives into one self-contained
interactive HTML", "hooks": []}` (entry shape per piggyback.py:74-119, `hooks: []`
precedent per `diagram-model`/`narrative-sidecar`).

**Depends on.** Component 3 (the script must exist and run standalone).

**Assumes.** A10.

**Done when.** `piggyback status` lists `ssot-render`; existing entries unchanged.

---

## Handoff notes

What research/planning needs beyond the components:

- **Contract with P6 (regeneration plumbing):** the stable surface P6 chains on
  is exactly: the six flags (`--model --narratives --config --out --component
  --title`), the default paths (axis 5A/6A), exit 0/2 semantics, and
  byte-determinism. No config keys were added, so P6 can invoke `render.py` bare
  inside an indexed repo. The committed-artifact policy (OQ-P5-4: committed, ~1MB
  diffs accepted) is executed operationally by P6's regen loop.
- **Contract with plan-visualizer (Phase D):** the reuse seam is two artifacts —
  `render_template.html`'s sentinel contract and `build_viewmodel`'s top-level
  keys + trust-bearing node fields (component 5 Interface shape). This phase
  commits to not renaming the two sentinels or the top-level view-model keys
  without a contract note, and binds any future producer to the F3 sentinel
  invariant (a splice sentinel must contain a character the payload escape
  guarantees absent — here `<`).
- **Sequencing constraint the planner owns:** golden shas (component 10) can only
  pin AFTER the font binaries (component 1) land — the base64 blocks are part of
  the bytes. The design's delegation verdict flags this as the plan's key
  sequencing judgment (fixture-before-or-after-sha-pinning; template-first vs
  join-first).
- **Open uncertainty — micro-view stub grammar:** addendum §3 defines stubs only
  at component granularity; same-component cross-micro edges in a micro focus
  view need the component-5 Decisions entry resolved. If the plan picks the
  "OTHER FILE" badge variant it is a one-token extension of the binding addendum
  and must be recorded there (or escalated if treated as a visual-contract
  change).
- **Suggested research (for factual-code-verification):** (1) A11 via a Python
  one-liner (`json.dumps` on a string containing U+2028/U+2029/`<`); (2) A15 via
  a golden walk (find the 3 duplicated nano ids, compare their signatures across
  positions, confirm 407 positions / 402 unique non-collapsed ids); (3) A18 by
  opening the archived example file at the cited line regions; (4) A14 by reading
  `_narrate_root_paths` (confirms the deviation is a deviation); (5) re-confirm
  A1–A13 independently against live code per FCV rules (this spec author's reads
  are not a substitute).
- **Weight-600 note for the template author:** archived §2.3 assigns weight 600
  to legend title/header; only 400/500/700 are vendored — 600 renders via browser
  synthesis from 500, matching how the archived files themselves behaved. Not a
  gap; do not vendor a fourth file.

## Open Questions (deferred — do NOT resolve in this spec)

- **OQ-P5-5 — RESOLVED BY OWNER 2026-07-06 (AskUserQuestion, spec gate): the
  first COMMITTED rendered artifact lives in the PILOT repo (mkt_engine) via P6.**
  P5 ships the tool + test fixtures only; no rendered mkt_engine snapshot is
  committed into codegraph-piggyback. P5's E2E done-criteria still include
  rendering the live mkt_engine model and clicking through it — the artifact is
  produced and verified, just not committed here. Plan's final-commit checklist
  must reflect this. (Historical context: OQ-P5-4 settled committed-not-gitignored
  in the consuming repo; this settles WHICH repo commits first.)
- **OQ-P5-1..4 — RESOLVED by owner 2026-07-06** (navigable stubs in the full
  artifact / fonts fetch+commit / `--title` flag / 1–1.5MB + committed artifact).
  Restated in Constraints and baked into components 1, 3, 5, 8. Do not reopen.
- **P6-deferred items** carried from P4/design: `status --strict`, narrative GC,
  declined markers, non-frozen-field loud guard (STATE.md MINOR (b)).
