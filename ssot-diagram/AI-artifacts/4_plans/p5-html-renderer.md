# Plan: P5 — Interactive HTML renderer (`render.py` + `render_template.html`)
_Last updated: 2026-07-09_
_Status: [ ] pending_

## Analysis

P5 gives a non-coder owner a single self-contained HTML file they can open from
disk, click from a ten-box system view down to an individual function, and read —
in plain language — what each piece is and whether every explanation and decision
behind it is still current. Everything below this phase already exists and is
machine-checked (the code map `diagram-model.json`, the decisions with live
freshness verdicts, the human-gated `narratives.json` pinned to code
fingerprints). P5 builds the picture on top of that foundation.

The one load-bearing property, restated: **all trust verdicts are computed in
Python at render time by importing P3/P4's own functions** (`gm._derive_status`,
`gm._fallback_text`). The browser JavaScript is a dumb painter — it reads
pre-joined fields out of one embedded `MODEL` constant and derives nothing: no
status, no count, no default, no sentence. If the JS is wrong it can only draw
ugly, never lie about trust (ADR-0002). This is what makes the whole stack safe
to hand to an LLM for prose: a drifted explanation stops being an invisible
database state and becomes a red "needs review" badge on a card.

This build adds **two new repo-owned artifacts plus one new script**: new
`ssot-diagram/render.py` (the joiner + splicer + writer), new
`ssot-diagram/render_template.html` (the repo-owned shell holding all CSS + the
painter skeleton, browser-openable as a preview, two splice sentinels), and
vendored DM Sans binaries under `ssot-diagram/assets/`. It is **not** a
`graph_model.py` subcommand — separate file, own manifest entry, sibling-import
reusing P3/P4 (ADR-0001 pattern). Spec:
`AI-artifacts/2_specs/p5-html-renderer.md` (11 components — this plan owns HOW,
the spec owns WHAT). FCV:
`AI-artifacts/3_factual-code-verification/p5-html-renderer.md` (19 validated, 0
invalidated, 2 unverifiable-but-expected — fixtures nonexistent until built).

What this build connects to and why:

- **Reads `diagram-model.json` + `narratives.json`, never opens the codegraph
  DB.** Stronger than the repo's read-only rule: `render.py` calls
  `di.find_db` / `di.repo_root_for` ONLY to locate the repo root for default
  paths (existence-check walk, `_shared/db.py:22-31`, A9). The DB is never
  opened. The deliberate deviation from the P4 narrate precedent (A14): when
  `--model` + `--narratives` + `--out` are ALL explicit, discovery is skipped
  entirely so no-DB environments (CI) must NOT die.
- **Reuses P3/P1 helpers by sibling import, not re-writing them.** `render.py`
  opens with the same seam as `graph_model.py:26-28`
  (`sys.path.insert` + `import decision_index as di`, plus `import graph_model
  as gm`). It imports `_derive_status` (`graph_model.py:1000-1014`),
  `_fallback_text` (`:898-926`), `_load_model` (`:831-839`),
  `_load_narratives` (`:946-956`), `_load_narrate_config` (`:809-828`),
  `die`/`warn`/`ok`/`info` (`:47-60`, die = `di.die` exit 2), and the path
  constants `DEFAULT_OUTPUT_REL` / `DEFAULT_CONFIG_REL` (`:30-31`). The atomic
  write discipline of `_save_model` (`:1268-1277`) is REPLICATED (not reused —
  that function serializes JSON, render writes text) by a local `_save_text`.
- **Must NOT add config keys.** Axis 5A: P5 adds ZERO new config keys. The two
  P4 keys (`narrate_threshold: 4`, `narratives_path`) already live in
  `ssot-diagram.config.json` (L57-58) and are read via `_load_narrate_config`
  unchanged. The threshold is ignored by render; only `narratives_path` is used.
- **Honours the FROZEN contracts.** Block 4a (exactly three levels: component →
  micro → nano, no flat, no 4th level); Block 4b (importable fields `id` /
  `kind` / `name` / `path` / `signature` — non-frozen `caller_count` /
  `is_exported` / `docstring` read ONLY inside `_fallback_text`, no new read
  sites, loud guard deferred to P6 per STATE.md MINOR b); Contract 6 (edge kinds
  ⊆ `{calls, imports, references}`); Block 5a/5b + amendments (stored narrative
  status ∈ `{proposed, approved}`; `stale` DERIVED live never written;
  empty-signature nodes derive `unnarratable` — TD-P4-1 close). The renderer is
  the named "consumer obligation" holder: importing `_derive_status` is HOW it
  satisfies Block 5b.

Why this approach: the Python-join / JS-dumb split is the entire point of the
phase (ADR-0002) — it is what makes an LLM-authored narrative safe to render.
Three invariants make it safe and are load-bearing throughout the steps: (1)
**trust computed in Python, painter derives nothing** (if the JS could derive a
status, a stale sentence could render as trusted); (2) **the two splice
sentinels each contain a literal `<`**, and `_escape_viewmodel_json` converts
every `<` in the payload to `<`, so a payload can never corrupt the splice
or trip the count assert even if narrative prose discusses these very markers
(red-team F3 sentinel invariant); (3) **byte-determinism everywhere** — no
timestamps, stable ordering, atomic temp + `os.replace`, golden smoke test like
P3/P4.

## Files
- `ssot-diagram/render.py` — NEW script. Sibling-imports `graph_model as gm` +
  `decision_index as di`. Contains: path resolution (`_render_paths`), the trust
  join (`build_viewmodel`), the escape/font functions (`_escape_viewmodel_json`
  + `_font_face_css`), the splice + atomic writer (`_render_html`, `_save_text`),
  the CLI (`build_parser` + `cmd_render` + `main`). No existing file's symbol
  behavior changes; nothing is added to `graph_model.py`.
- `ssot-diagram/render_template.html` — NEW repo-owned HTML shell. Holds all CSS
  tokens transcribed from the LOCKED archived spec + the addendum, the page
  chrome, two `<`-bearing splice sentinels, and the dumb-painter JS body
  (focus views, breadcrumb, stubs, tooltips, legend, theme, pan/zoom). Browser-
  openable as a raw preview (sentinel placeholders keep the JS valid).
- `ssot-diagram/assets/DMSans-Regular.woff2`, `DMSans-Medium.woff2`,
  `DMSans-Bold.woff2`, `OFL.txt` — NEW vendored font binaries + license.
- `manifest.json` — add ONE `ssot-render` entry under `scripts` (`scope: repo`,
  `hooks: []`, P6 owns wiring).
- `ssot-diagram/test_render.py` — NEW pytest battery (beside the code, matching
  P3/P4 convention): three goldens + structural + injection + exit-code +
  template-hygiene + regression guard.
- `ssot-diagram/testdata/mkt_engine.narratives.fixture.json` — NEW fixture,
  against REAL golden-model ids, hitting every NARRATIVE treatment row.
- `ssot-diagram/testdata/injection.narratives.json` — NEW injection fixture
  (`</script>`, `<!--`, U+2028, literal sentinel text in prose).
- `ssot-diagram/testdata/trustmatrix.model.json` + `trustmatrix.narratives.json`
  — NEW synthetic golden #3 inputs (red-team F4) covering every DECISION status
  row the real golden cannot (its 11 decisions are all FRESH).

## Delegation Authority
Plain-English: the implementer may edit only the files listed in ## Files. The
frozen contracts, the golden model, P3/P4 behavior, and every other tool are
off-limits and must stay byte-for-byte unchanged.

- **Allowed set** = exactly the seven files above. Nothing outside it.
- A file in ## Files assigned to another Step is a dependency (follow
  ## Implementation Order), not a deviation.
- A file NOT in ## Files → STOP, do not silently edit. Record it in an
  `### Out-of-scope touches` block of the end-of-implementation report: the
  file, why the Step needed it, the change, and whether it signals a plan/spec
  gap.
- **Hard off-limits (escalate before touching):**
  - `../docs/roadmap/skeleton-contracts.md` — FROZEN contracts (Block 4a/4b, 5a,
    5b, Contract 6). The micro-stub extension below is an ADDENDUM note, NOT a
    skeleton-contracts amendment.
  - `ssot-diagram/graph_model.py` — sibling-import READ-ONLY. Use `gm.*` and
    `di.*`; never edit the module. Reuse `_derive_status` / `_fallback_text` /
    `_load_model` / `_load_narratives` / `_load_narrate_config` / `die` /
    `warn` / `ok` / `info` / `DEFAULT_OUTPUT_REL` / `DEFAULT_CONFIG_REL` by
    import. Do NOT add fields to the model or change any P3/P4 behavior.
  - `ssot-diagram/decision_index.py` (`di`) — read-only reuse of `find_db` /
    `repo_root_for` / `die` ONLY. Do NOT use `di.open_db`, never edit.
  - `ssot-diagram/testdata/mkt_engine.model.json` — the frozen P3 golden
    (FCV-verified sha256 `56df3d86…`, NOT the stale `5a1e2156…`). Render must
    NOT mutate it; the regression test byte-compares against it.
  - `AI-artifacts/1_design/p5-html-renderer.md` + `…-ux-addendum.md` — the
    binding design + UX contract. The ONE allowed exception is recording the
    micro-stub extension note against addendum §3 (owner-ratified, Step 5);
    do not otherwise amend.
  - `.codegraph/codegraph.db` — never opened by render, never written.
  - `CLAUDE.md`, `STATE.md`, `ssot-diagram/CLAUDE.md`, roadmap docs — doc-sync
    is the pipeline-end job, not the implementer's. (The orchestrator owns the
    STATE.md write for this plan.)

## Rules Applied
A `--- WRIT RULES ---` block was injected into this planning session. The
injected IDs do not cleanly map to this plan's domain (DB connection pooling,
password reset, state-machine transitions — none apply to a deterministic
read-only renderer). The governing constraints are the project's own FROZEN
contracts and CLAUDE.md rules, enforced through ## Delegation Authority and the
per-Step `<!-- plan-verify -->` manifests:
- Block 4a / 4b / 5a / 5b + Contract 6 (`docs/roadmap/skeleton-contracts.md`) —
  three levels, node fields, trust rule, edge kinds.
- Repo `CLAUDE.md` Critical Rules — read-only DB (stronger: never opened here),
  manifest entry required, stdlib only, content-signature pinning, every
  LLM-written persisted thing pinned to a signature (the narratives are already;
  the HTML artifact is deterministic, not LLM-written).
- `ssot-diagram/CLAUDE.md` — sibling import (defer `_shared/`), byte-deterministic
  writer, Phase/Step naming, L5-invents-nothing (renderer is a dumb painter).
- ADR-0002 (Python-join / JS-dumb), ADR-0003 (proposed-renders-marked not
  hidden), the F3 sentinel invariant, the L1-L10 locked decisions.

## Decisions (closed before plan — do not re-litigate)
Each is low-blast and reversible except the first (visual contract, owner-
ratified). All other spec "Decisions" entries are resolved here so the
implementer is never guessing.
1. **Micro-stub grammar (OWNER-RATIFIED 2026-07-09, AskUserQuestion).** In a
   micro focus view, a cross-view edge to a SIBLING micro of the SAME component
   lands on an "OTHER FILE" stub card (micro-size, same §3 card grammar as
   "OTHER COMPONENT", badge label "OTHER FILE", navigable in the full artifact
   / inert in `--component` files — identical cue rules). This is a ONE-TOKEN
   EXTENSION of addendum §3 (same tokens, new badge label + sibling-micro
   resolution). Step 5 records it against the addendum; Step 8 paints it.
2. **Font provenance (comp 1).** Source URL + retrieval date recorded in the
   HTML-head attribution comment AND the git commit message body. No
   `assets/README` (scope discipline).
3. **Raw template preview (comp 2).** When `MODEL === null` (raw template opened
   directly), one guard clause renders the empty chrome with a small "template
   preview — no data spliced" note via `setText`. Makes "browser-previewable"
   observable.
4. **`--config` explicit + `--narratives` absent (comp 3).** Discovery runs
   (any defaulted path — including narratives, which is relative — triggers
   discovery). Rule stays "explicit flags for every path you don't want
   discovered".
5. **Empty-but-present narratives (comp 4).** Note fires absent-ONLY (L7 literal
   wording "missing narratives.json"). An existing empty `{}` file = curated P4
   state, no note, no warn (every node showing `none` fallback already tells it).
6. **Injection fixture location (comp 9).** Separate file
   (`injection.narratives.json`), keeping golden #2's sha stable if injection
   cases evolve. `--title` exercising the same characters flows through test
   invocations, not a committed file.
7. **Top-level self-edges (comp 5).** Omit at the components view (detail
   renders in the focus views, nothing lost — addendum §4 routing never defined
   self-loops).
8. **Duplicated nano positions, A15 (comp 5).** Emit the joined node at EACH
   tree position (mirrors the model; positions are what the painter lays out;
   identical content per A15 so last-write-wins is harmless).
9. **Icon key (comp 5).** Fixed kind→icon table precomputed in Python:
   component→`SERVICE`, micro→`default`, nano→`ACTION`. Icon selection in
   Python, never by JS keyword scan (ADR-0002).
10. **Scoped subtitle (comp 5).** Reuse the full-artifact formula scoped to the
    subtree with UNIQUE-decision counting (F5 applies unchanged):
    `"<K> files · <M> decisions"`.
11. **Tooltip id→node index (comp 8).** JS builds the index at load time from
    the embedded tree (pure indexing, not deriving); keeps the payload minimal.
    Stated explicitly so reviewers don't flag the one-time loop as "JS derives".

## Capabilities
- [ ] C1 — Vendored DM Sans (400/500/700) + OFL exist in `ssot-diagram/assets/`;
  each woff2 starts with `wOF2` magic; total ~60-70 KB; no fourth weight; the
  output HTML embeds them as base64 `@font-face` and makes ZERO network
  requests.
- [ ] C2 — The raw `render_template.html` opens from disk with zero console
  errors, zero network requests, shows page chrome + the "template preview"
  note; each `<`-bearing sentinel occurs exactly once; `innerHTML` appears only
  as the `= ''` clear idiom; no `<link>`/`@import` font loads.
- [ ] C3 — Bare `render.py` in an indexed repo writes
  `<root>/ssot-diagram/ssot-diagram.html` exit 0; `render.py --model M
  --narratives N --out O` in a NO-`.codegraph` directory succeeds (A14
  deviation); `--component cmp-lib` with no `--out` writes
  `ssot-diagram.cmp-lib.html`; `--title <text>` flows as free text through the
  escape; `--help` lists exactly six flags.
- [ ] C4 — Missing `narratives.json` → renders with every node's fallback text
  + visible "no narratives yet" note + stderr `!` warning, exit 0. Malformed
  model/narratives → exit 2, nothing written. Missing model → exit 2. Missing
  template → exit 2. Missing font asset → exit 2.
- [ ] C5 — `build_viewmodel` is a pure function over model + narratives. For
  every node it calls `gm._derive_status` (imported, never copied) and emits the
  L3 matrix treatment: approved→trusted prose; proposed→prose muted + "PROPOSED"
  badge; stale→OLD prose muted + danger "needs review"; unnarratable→fallback +
  badge (even if a stored entry exists — A1 branch order, `cmp-dist` fixture
  visible); none→fallback; orphaned entry never rendered, counted to stderr. A
  derived status outside the matrix vocabulary → die 2 (A17 guard, non-dead).
  Subtitle reads `"10 components · 8 decisions"` (8 = UNIQUE ADR names, F5).
  Two runs → equal payloads.
- [ ] C6 — `_escape_viewmodel_json(payload)` =
  `json.dumps(..., sort_keys=True, ensure_ascii=True,
  separators=(",",":")).replace("<", "\\u003c")`; output has zero `<`, zero bytes
  ≥ 0x80; escaping twice is byte-identical (A11). `_font_face_css()` base64-
  encodes the three woff2 into three `@font-face` rules, fixed file order, no
  `<`, no sentinel; a missing asset → die 2.
- [ ] C7 — `_render_html` asserts BOTH sentinels occur exactly once BEFORE any
  replace (die 2 otherwise), replaces font sentinel then view-model sentinel
  (pinned F3 order), asserts zero sentinels remain (die 2). `_save_text` writes
  temp + `os.replace` + trailing newline. Rendering twice → byte-identical files
  (sha256 equal).
- [ ] C8 — The painter derives NOTHING (ADR-0002 review standard). Focus-view
  state = `viewPath` (0-2 ids) + pan/zoom; `paintView()` fully re-renders per
  path; components → component focus (header panel + micro grid) → micro focus
  (header panel + nano cards + "+K more" collapsed). Nano cards have no expand
  button (Block 4a). Breadcrumb tracks + navigates back. Tooltips (F2) carry
  the SAME trust treatment as the card (chip text first when present, prose in
  the card's muting), filled via `setText` from the precomputed `node.tooltip`,
  never from HTML attributes (cards carry only `data-node-id`). Stubs switch
  ONLY on `stub`/`stub_nav` flags: navigable (full artifact) = `→` glyph +
  body title + pointer + hover ring + click sets `viewPath=[neighborId]`; inert
  (`--component` file) = no glyph + disabled title. Legend draws the embedded
  block verbatim. Theme toggles + persists. Pan/zoom + fit-to-view (from layout
  data, never `getBBox`) work in every focus view.
- [ ] C9 — Fixtures committed: `mkt_engine.narratives.fixture.json` hits every
  NARRATIVE status row against real golden ids (incl. an `cmp-dist` entry that
  derives `unnarratable` despite storage, + an unknown-id orphaned entry);
  `injection.narratives.json` carries `</script><script>`, `<!--`, U+2028, and
  the literal `/*<SSOT:VIEWMODEL_JSON>*/` in prose;
  `trustmatrix.model.json` + `trustmatrix.narratives.json` are schema-valid AND
  cover every DECISION status (FRESH/STALE/ORPHANED/AMBIGUOUS/"superseded").
- [ ] C10 — `python3 -m pytest ssot-diagram/` shows all new render tests green
  AND zero NEW failures vs the 105-pass/3-prefail baseline (A19, re-baselined
  below). Golden #1 (no narratives) + #2 (fixture) + #3 (trustmatrix) shas
  pinned; structural asserts carry the safety load (embedded node count == 407
  tree positions; exactly one `</script>`; zero `<` in payload region; render
  twice → byte-identical). Injection test: hostile `--title` + injection
  fixture → exactly one `</script>`, no `<` in payload, both sentinel-count
  asserts pass. Flipping one fixture status locally fails BOTH a sha AND a
  `data-trust` structural assert (double-oracle before ship).
- [ ] C11 — `piggyback status` lists `ssot-render`; existing entries unchanged;
  `manifest.json` still parses; P5 adds ZERO config keys (the two P4 keys are
  reused unchanged).

## Implementation Order
Plain-English: font binaries come FIRST because the base64 `@font-face` blocks
are part of every hashed golden's bytes (shas pin only after fonts land — the
spec's key sequencing judgment). The template shell + CLI plumbing + load + join
+ escape are independent enough to wave; the splice/assembly Step joins them;
tests are last. Sibling files (`render.py`, `render_template.html`) are edited
by one implementer sequentially in wave order to avoid edit churn.

Dependency facts (FCV-verified line numbers, `graph_model.py` unless noted):
- `gm._derive_status` (`:1000-1014`) branch order is load-bearing (A1) — render
  imports it, never re-orders. Step 5's join keys on the exact order
  empty-sig→unnarratable caught FIRST.
- `gm._fallback_text` (`:898-926`) raises on collapsed/decision (A2) — the join
  branches on `kind == "collapsed"` BEFORE calling it.
- `gm._load_model` (`:831-839`) dies 2 on absent/malformed; `gm._load_narratives`
  (`:946-956`) conflates absent with empty (returns `{}`) — render checks
  `is_file()` itself before calling it (component 4 distinction).
- `gm._load_narrate_config` (`:809-828`) returns `(threshold, narratives_rel)` —
  render ignores threshold, uses `narratives_rel` (A16: plain relative str).
- `di.find_db` (`_shared/db.py:22-31`) never opens the DB (A9) — render's
  "never touches the DB" claim rides on this.
- `decision_index.py` sibling-import seam is at `graph_model.py:26-28`; render
  mirrors it verbatim + adds `import graph_model as gm`.

**Dependency table:**
| Step | Produces | Depends on | Why |
|---|---|---|---|
| 1 | font binaries + OFL | — | base64 blocks part of golden bytes (shas can't pin before) |
| 2 | `render_template.html` (shell + sentinels + helpers) | — | skeleton the painter hangs on; raw-previewable now |
| 3 | `render.py` CLI plumbing (`build_parser`, `_render_paths`, `cmd_render` shell, `main`) | — | flags-only, no logic; everything hangs off it |
| 4 | INPUT-LOAD inside `cmd_render` | 3 | needs resolved paths; calls `gm._load_*` |
| 5 | `build_viewmodel` (trust join) + the micro-stub addendum note | 4 | the heart; reads loaded inputs; produces the payload |
| 6 | `_escape_viewmodel_json` + `_font_face_css` | 1, 5 | escapes the payload; embeds the fonts |
| 7 | `_render_html` splice + `_save_text` + `cmd_render` assembly | 2, 3, 5, 6 | splices escaped payload + font CSS into the template; atomic write |
| 8 | JS painter body inside `render_template.html` | 2 (shell), 5 (view-model shape — dual-language contract) | written against component 5's Interface shape |
| 9 | fixtures (3 sets) | 5 (semantics), 1 (real golden ids/sigs) | each row reachable; goldens #1/#2/#3 inputs |
| 10 | `test_render.py` battery + shas pinned | 1-9 | tests last; shas pin only after fonts (1) + painter (8) land |
| 11 | manifest `ssot-render` entry | 3 (script runs standalone) | ships the tool, no hooks (P6) |

**Parallel waves** (disjoint symbols across the two sibling files — safe to
parallelize; one implementer owning both serializes in wave order):
- Wave A (no deps): Step 1, Step 2, Step 3.
- Wave B (after A): Step 4.
- Wave C (after B): Step 5 (+ the addendum note record inside it).
- Wave D (after C): Step 6, Step 9 (fixtures depend on Step 5's semantics, not
  on Step 6/7/8 — safe alongside 6).
- Wave E (after D): Step 7.
- Wave F (after E, needs the view-model shape from 5): Step 8.
- Wave G (after F): Step 10 (shas pin after fonts land + painter renders).
- Wave H (solo, any time after 3): Step 11.

**Critical path:** 1/2/3 → 4 → 5 → 6 → 7 → 8 → 10. (Step 9 inserts at C/D; Step
11 is parallel-solo.) Solo linear order: 1 → 2 → 3 → 4 → 5 → 6 → 9 → 7 → 8 → 10 → 11.

## Implementer Notes (weak-model — read before Step 1)

This section removes the guesswork the prose Steps leave to a strong implementer.
Copy these signatures and skeletons verbatim; fill the bodies the Steps
describe. Everything here is verified against live code (`graph_model.py`,
`decision_index.py`, `_shared/db.py`) and the golden
(`testdata/mkt_engine.model.json`, sha256 `56df3d86…`) as of 2026-07-09 (FCV).

**1. Sibling import — mirror `graph_model.py:26-28` + add the gm import.**
```python
# render.py header
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decision_index as di  # noqa: E402
import graph_model as gm     # noqa: E402
die = gm.die                 # di.die alias, exit 2
warn, info, ok = gm.warn, gm.info, gm.ok
DEFAULT_OUTPUT_REL = gm.DEFAULT_OUTPUT_REL   # "ssot-diagram/diagram-model.json"
DEFAULT_CONFIG_REL = gm.DEFAULT_CONFIG_REL   # "ssot-diagram/ssot-diagram.config.json"
SENTINEL_VM = "/*<SSOT:VIEWMODEL_JSON>*/null"    # template's replace target (incl "null")
SENTINEL_FONT = "/*<SSOT:FONT_FACE>*/"          # inside <style>
DEFAULT_OUT_REL = "ssot-diagram/ssot-diagram.html"
DEFAULT_TITLE = "SSOT diagram"
```
NOTE: `SENTINEL_VM` is the WHOLE token `/*<SSOT:VIEWMODEL_JSON>*/null` (the raw
template stays valid JS — `const MODEL = /*…*/null;`). The escaped payload
replaces the whole token, becoming the object literal `const MODEL = {…};`. Both
sentinels contain a literal `<` (F3 invariant — `_escape_viewmodel_json` kills
every `<` in the payload, so the escaped payload can never contain its own
sentinel).

**2. Model node field names (verified against the golden — do NOT guess).**
- component/micro dict: `id, kind, name, path, signature, children, edges,
  decisions` (micro also has `dominant_class`). `kind` is `"component"` / `"file"`.
- nano dict: `id, kind, name, qualified_name, path, signature, caller_count,
  is_exported, docstring, edges, decisions`. `kind` is `"function"` (or `"method"`).
- collapsed placeholder (inside a micro's `children`):
  `{id, kind:"collapsed", name, signature, collapsed_count}` — NO
  `caller_count`/`docstring`/`is_exported`/`path`/`edges`/`decisions`. Bypass the
  join entirely; branch on `kind == "collapsed"` BEFORE calling `_fallback_text`
  (it raises — A2, A12).
- decisions live under top-level `model["decisions"]` (a DICT), NEVER under
  `components[].children`. Every node ALSO has a per-node `decisions` LIST field
  (reference ids, not child nodes). Top-level keys (A4): exactly
  `{version, generated_at, nano_cap, components, decisions}`, `generated_at: null`.
- A15: 3 nano ids (`nano:canRedo@lib/canvas/store.ts`,
  `nano:canUndo@lib/canvas/store.ts`, `nano:resetStore@tests/canvasStore.test.ts`)
  appear at 2 tree positions each with IDENTICAL signatures — 407 tree positions
  vs 402 unique sig-index keys. Emit the joined node at EACH position (Decision 8).

**3. The view-model Interface shape (component 5's seam — painter written
against it; do not rename without a contract note).** Top-level keys:
```python
{
  "title": str,            # --title or "SSOT diagram"
  "subtitle": str,         # "10 components · 8 decisions" (UNIQUE ADR names — F5)
  "note": str | None,      # L7 "no narratives yet …" or None
  "scope": "full" | <cid>, # full or the --component id
  "components": <nested tree, dropped generated_at, signatures kept>,
  "view_edges": <list, top-level view only>,
  "legend": {"node_types": […], "edge_kinds": […], "trust_chips": […]},
}
```
Per-node trust-bearing fields: `prose: {text, status, source: "narrative"|"fallback"}`,
`chips: [{id, name, doc, status, badge}]`, `tooltip: {…precomputed…}`,
and on stubs `stub: true` + `stub_nav: true|false`. Payload carries ONLY
painter-needed fields — `signature` IS copied (the fallback/narratable pinning
chain reads it via `_derive_status` at join time, but it is NOT needed by the
painter; DO NOT copy `dominant_class` / raw `docstring` / `caller_count` /
`is_exported` through). Copy `name`, `kind`, `path` for display + breadcrumbs.

**4. `build_viewmodel` skeleton — the trust join (L2 heart, import NEVER copy).**
```python
def build_viewmodel(model: dict, narratives: dict, *,
                    component: str | None = None, title: str | None = None) -> dict:
    # 1. build id->owning-component + id->owning-micro maps in one walk (A5)
    # 2. resolve decision-chip dict once from model["decisions"]; unknown id -> die 2
    # 3. for each node (component/micro/nano) in a nested walk:
    #    if kind == "collapsed": passthrough name + collapsed_count (NO join call)
    #    else:
    #      status = gm._derive_status(narratives.get(node_id), node["signature"])
    #      assert status in {approved,proposed,stale,none,unnarratable,orphaned} else die 2  # A17
    #      prose text: approved/proposed/stale -> narratives[...]["text"]; none/unnarratable -> gm._fallback_text(node)
    #      chips: precompute per L3 (FRESH->positive, STALE/ORPHANED->danger+"NEEDS REVIEW",
    #             AMBIGUOUS->danger+"AMBIGUOUS — anchor unclear", superseded->disabled)
    #      tooltip block (F2): name, kind label, chip text first when present, joined prose, capped samples
    #    emit node at EACH tree position if duplicated (Decision 8)
    # 4. orphaned entries (id not in model) -> gm.info count to stderr, NEVER enter payload
    # 5. per-view edge + stub precompute (dumb-painter enabler):
    #    for each container (top, each component, each micro): view_edges (endpoints
    #    resolved to ids present in that view) + stubs (one per distinct outside owner).
    #    MICRO focus view: sibling micro of same component -> "OTHER FILE" stub (Decision 1).
    #    Top level: omit edges whose BOTH endpoints resolve to same component (Decision 7).
    #    Full artifact stubs: stub_nav=True. --component stubs: stub_nav=False.
    # 6. --component cid: unknown -> die 2 listing known; else scope to that subtree only, all stubs inert.
    # 7. legend block (artifact-scope, what's present), title/subtitle/note.
    # 8. determinism: assembled from model's sorted arrays + sorted() on dict-derived lists; no timestamp.
    return viewmodel
```

**5. The escape + font functions (exact, axis 2A, F3 invariant — copy verbatim).**
```python
def _escape_viewmodel_json(viewmodel: dict) -> str:
    return (json.dumps(viewmodel, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")).replace("<", "\\u003c"))

def _font_face_css(assets_dir: Path) -> str:
    rules = []
    for weight, fname in [(400,"DMSans-Regular.woff2"),(500,"DMSans-Medium.woff2"),
                          (700,"DMSans-Bold.woff2")]:
        p = assets_dir / fname
        if not p.is_file():
            die(f"missing font asset: {p}")   # fail-loud, never silent system-font fallback
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        rules.append(f'@font-face{{font-family:"DM Sans";font-weight:{weight};'
                     f'font-style:normal;src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    return "\n".join(rules)
```
`ensure_ascii=True` escapes U+2028/U+2029 (and all non-ASCII) — verified via
`/tmp/esc_check.py` in FCV. After the `.replace("<","\\u003c")` the output has
zero `<`, zero raw U+2028/29 — which is WHY the `<`-bearing sentinels are
collision-proof.

**6. Splice + atomic writer (pinned F3 order).**
```python
def _render_html(template_text: str, viewmodel: dict, font_css: str) -> str:
    # (1) assert BOTH sentinels occur exactly once BEFORE any replace (die 2 otherwise)
    assert template_text.count(SENTINEL_VM) == 1, die("sentinel drift: VIEWMODEL_JSON")
    assert template_text.count(SENTINEL_FONT) == 1, die("sentinel drift: FONT_FACE")
    # (2) replace font sentinel first (font_css has no sentinel)
    out = template_text.replace(SENTINEL_FONT, font_css)
    # (3) replace view-model sentinel (escaped payload has no '<', hence no sentinel)
    out = out.replace(SENTINEL_VM, _escape_viewmodel_json(viewmodel))
    # (4) assert zero sentinels remain (die 2)
    assert SENTINEL_VM not in out and SENTINEL_FONT not in out, die("sentinel survived splice")
    return out

def _save_text(path: Path, html: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(html + ("" if html.endswith("\n") else "\n"))
    os.replace(tmp, path)
```
(Atomicity discipline replicated from `gm._save_model` at `graph_model.py:1268-
1277`, NOT reused — that serializes JSON.)

**7. CLI block — NOT a subcommand group, one verb (mirrors the existing
`extract`/`bootstrap-config` argparse style; `main` dispatches via
`args.fn(args)`).**
```python
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="render", description="render diagram-model + narratives into a self-contained HTML file")
    sub = p.add_subparsers(dest="render_cmd", required=True)
    pr = sub.add_parser("render", help="render the HTML artifact")
    pr.add_argument("--model", help=f"diagram-model.json (default: <root>/{DEFAULT_OUTPUT_REL})")
    pr.add_argument("--narratives", help="narratives.json (default: config narratives_path)")
    pr.add_argument("--config", help=f"config (default: <root>/{DEFAULT_CONFIG_REL})")
    pr.add_argument("--out", help="output HTML (default: <root>/ssot-diagram/ssot-diagram.html)")
    pr.add_argument("--component", help="scoped view: one component id (emits ssot-diagram.<cid>.html)")
    pr.add_argument("--title", help=f"artifact title (default: {DEFAULT_TITLE!r})")
    pr.set_defaults(fn=cmd_render)
    return p

def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)
```
`_render_paths(args)` mirrors `gm._narrate_root_paths` at `graph_model.py:931-943`
BUT with the A14 deviation: root discovery (`di.find_db(Path.cwd())` + `di.repo_root_for`)
runs ONLY if at least one of `--model`/`--narratives`/`--out` is absent; when all
three explicit, NO discovery + NO die on absent DB (Decision 4: a defaulted
`--narratives` STILL triggers discovery since `narratives_rel` is relative).
Defaults: model=`<root>/ssot-diagram/diagram-model.json`; config=`<root>/ssot-
diagram/ssot-diagram.config.json` (overridable via `--config` without triggering
discovery when the other three are explicit); narratives=`<root>/<narratives_rel
from gm._load_narrate_config>`; out=`<root>/ssot-diagram/ssot-diagram.html`, or
with `--component <cid>` → `<root>/ssot-diagram/ssot-diagram.<cid>.html` (cid is
already a filename-safe slug); `--out` beats both.

**8. Test harness — REUSE `test_graph_model.py` helpers, do not invent.**
`test_render.py` opens with the same sibling-import seam
(`sys.path.insert` + `import graph_model as gm`). Available helpers:
`GOLDEN = TESTDATA / "mkt_engine.model.json"` (the frozen model, sha256
`56df3d86…`), `TESTDATA = HERE / "testdata"`, the `_synthetic_db()` /
`_add_file/_add_node/_add_edge` / `_minimal_config` / `_mini_model` builder
pattern. For UNIT tests of `build_viewmodel`, `_escape_viewmodel_json`, etc.,
build a MODEL DICT LITERAL directly (fast, no DB) using the `_mini_model()` shape
from P4's plan §7. The A19 baseline: `python3 -m pytest ssot-diagram/ -q` →
`3 failed, 105 passed` (108 total) — the 3 fails are the SAME pre-existing
`TestGoldenLive` pilot-drift set; P5's bar is ZERO NEW failures + golden sha
`56df3d86…` untouched. Re-baseline on build-start day per A19's source-note.

## Steps

### Step 1 — Vendored DM Sans binaries + OFL
**Goal**: The font files exist in the repo so the output HTML embeds them and
never touches the network. Implements spec component 1.

**Design**:
Fonts are the FIRST thing to land because the base64 `@font-face` blocks are
part of every hashed golden's bytes — shas cannot pin until the binaries exist.
Fetch once at implementation time (OQ-P5-2 resolution: fetch + commit), from
the google/fonts OFL directory (DM Sans is OFL-1.1). Provenance recorded in the
HTML-head attribution comment + the git commit message body (Decision 2 — no
`assets/README`). Archived §2.3 assigns weight 600 (legend title/header) but
only 400/500/700 are vendored — 600 renders via browser synthesis from 500,
matching how the archived files themselves behaved; never vendor a fourth file.

**Actions**:
1. Fetch `DMSans-Regular.woff2` (400), `DMSans-Medium.woff2` (500),
   `DMSans-Bold.woff2` (700) — static weights from the google/fonts OFL dir.
2. Fetch `OFL.txt` (the DM Sans OFL-1.1 license text), verbatim, beside them.
3. Place all four in `ssot-diagram/assets/`.
4. Record source URL + retrieval date 2026-07-09 in (a) the HTML-head attribution
   comment authored in Step 2, (b) this commit's message body.

**Files to modify**:
- `ssot-diagram/assets/DMSans-Regular.woff2` — new
- `ssot-diagram/assets/DMSans-Medium.woff2` — new
- `ssot-diagram/assets/DMSans-Bold.woff2` — new
- `ssot-diagram/assets/OFL.txt` — new

<!-- plan-verify
tier:  C
qualifiers: byte-unchanged ssot-diagram/testdata/mkt_engine.model.json ; byte-unchanged ssot-diagram/graph_model.py
note: data-only step — vendored binaries + license, not codegraph-indexed code, so no touch:/new: symbol claims apply; the wOF2-magic-byte existence check is asserted by the Step-10 test criteria, not a plan_verify qualifier.
-->

**Test criteria** (added to `test_render.py` in Step 10):
- [ ] The three `.woff2` files + `OFL.txt` exist in `ssot-diagram/assets/`.
- [ ] Each woff2 starts with the `wOF2` magic bytes.
- [ ] Total font size is in the ~60-70 KB band; no fourth weight present.

**Status**: [ ] pending

---

### Step 2 — `render_template.html`: chrome, tokens, sentinels, safe DOM helpers
**Goal**: A browser-openable HTML shell holding all CSS + the painter skeleton +
two `<`-bearing sentinels + the safe DOM helpers. Implements spec component 2.

**Design**:
Every UX tweak becomes an HTML edit someone can preview — never a Python edit.
The CSS tokens are transcribed VERBATIM from the LOCKED archived spec
(`_archived/visualizer_guide/design-system/spec.md` §§1-5, 8) + the addendum's
chip styles (§2) + stub styles (§3, incl. the "OTHER FILE" variant — Decision 1).
The two sentinels each contain a literal `<` (F3 invariant). The raw template
stays valid, browser-previewable JS because the view-model sentinel's replace
target includes the trailing `null` (`const MODEL = /*…*/null;`). Raw preview
(`MODEL === null`) shows the empty chrome + a "template preview — no data
spliced" note via one `setText` guard clause (Decision 3). The §3.5 conflict is
avoided by construction: SVG positioning on an outer `<g>`, CSS animation on an
inner `<g>` (example:657-658); fit-to-view computes bounds from layout data,
never `getBBox`. Two DOM-insert helpers (L4 mechanism b): `setText(el, s)`
(assigns `el.textContent`) and `paintWrappedText(...)` (the `foreignObject`
writer adapting example:392-405's `div.textContent` assignment). The archived
`buildLegend` `innerHTML` hazard (example:928-950) is REWRITTEN with
`createElement` + `textContent`; the template hygiene rule (machine-enforced by
Step 10): `innerHTML` may appear only as the literal clearing idiom `= ''`. A
`@font-face`-less fallback chain (`'DM Sans', system-ui, …` per §2.1) so the raw
template previews with system fonts before splice.

**Actions**:
1. Create `ssot-diagram/render_template.html`.
2. Transcribe CSS tokens: §1 palette (light + dark via `data-theme`), §2 type
   scale/weights, §3 card anatomy + per-level sizes + shadow/hover, §4 edge
   styles/arrowheads/labels, §5 spacing, §8 chrome (header w/ title+subtitle+
   note+breadcrumb+zoom+theme-toggle, full-viewport SVG canvas, legend panel,
   tooltip container). Add addendum §2 chip styles + §3 stub styles (incl.
   "OTHER FILE" badge label variant — Decision 1).
3. Add the two `<`-bearing sentinels in their places:
   `const MODEL = /*<SSOT:VIEWMODEL_JSON>*/null;` (inside `<script>`) and
   `/*<SSOT:FONT_FACE>*/` (inside `<style>`). Add the static
   `<!--SSOT:GENERATOR-->` comment (fixed note, no timestamp, NOT a splice
   target).
4. Add `setText(el, s)` + `paintWrappedText(...)`. Add the `MODEL === null`
   preview-note guard.
5. Ensure the §3.5 outer-`<g>`/inner-`<g>` discipline is structural in the SVG
   skeleton. Add the `@font-face`-less fallback chain.

**Files to modify**:
- `ssot-diagram/render_template.html` — new

<!-- plan-verify
new:   ssot-diagram/render_template.html
tier:  A
qualifiers: byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
note: render_template.html is a non-indexed HTML asset — 'new:' as a bare path resolves UNRESOLVED in codegraph (HTML is _NONCODE_EXT; manifest 'new:' on an absent path is OK). render.py symbols are claimed in Steps 3-7. The sentinel-once + innerHTML-hygiene invariants are asserted by the Step-10 test criteria, not plan_verify qualifiers.
-->

**Test criteria** (Step 10):
- [ ] Opening raw `render_template.html` from disk: zero console errors, zero
  network requests; shows chrome + the preview note.
- [ ] Each `<`-bearing sentinel occurs exactly once.
- [ ] `grep innerHTML` finds only `= ''` occurrences.
- [ ] No `<link>`/`@import` font loads.

**Status**: [ ] pending

---

### Step 3 — CLI plumbing: `build_parser`, `_render_paths`, `cmd_render` shell, `main`
**Goal**: One script, one verb, six flags, zero new config keys — works bare
(inside an indexed repo) and fully-explicit (CI, no `.codegraph`). Implements
spec component 3.

**Design**:
Flags-only, argparse `required=True` subparser so bare `render` with no verb
exits 2 (matches P4 narrate's pattern). Sibling import seam mirrors
`graph_model.py:26-28` + adds `import graph_model as gm`. The A14 deviation is
THE load-bearing path rule: root discovery runs ONLY if at least one of
`--model`/`--narratives`/`--out` is absent; all three explicit → no discovery,
no-DB env must NOT die. This Step delivers the plumbing only — `cmd_render` is a
shell that the later Steps fill with load → join → escape → splice → write;
here it just resolves paths + prints them (so Step 3 is independently testable
before Steps 4-7 land). Exit 0 success / 2 die, nothing else. Registration in
manifest (Step 11) makes the bare command work after `piggyback install`.

**Actions**:
1. Create `ssot-diagram/render.py` with the sibling-import seam + constants
   (Implementer Notes §1).
2. Add `build_parser()` + `main()` per Notes §7 (one `render` verb,
   `set_defaults(fn=cmd_render)`).
3. Add `_render_paths(args) -> tuple[Path, Path|None, Path|None, Path, str]`
   returning `(model, narratives_default, config, out, title)` per Notes §7 +
   Decision 4 (a defaulted `--narratives` triggers discovery since
   `narratives_rel` is relative).
4. Add `cmd_render(args)` as a shell: resolve paths (3) → print a resolved-paths
   summary to stderr (placeholder for Steps 4-7) → exit 0.

**Files to modify**:
- `ssot-diagram/render.py` — new (header + `build_parser` + `_render_paths` +
  `cmd_render` shell + `main`)

<!-- plan-verify
new:   ssot-diagram/render.py::build_parser
new:   ssot-diagram/render.py::_render_paths
new:   ssot-diagram/render.py::cmd_render
new:   ssot-diagram/render.py::main
tier:  B
qualifiers: grep-absent "sqlite3.connect" ssot-diagram/render.py ; byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
-->

**Test criteria** (Step 10, exit-code tests):
- [ ] `render.py --help` lists exactly six flags.
- [ ] Bare `render.py` in an indexed repo resolves repo-root defaults (observable
  in the Step-3 path summary) + exit 0.
- [ ] `render.py --model M --narratives N --out O` in a NO-`.codegraph` directory
  → exit 0 (A14 deviation, no die).
- [ ] `render.py --component cmp-lib` with no `--out` resolves the
  `ssot-diagram.cmp-lib.html` out path.
- [ ] `render.py` with no verb → exit 2.

**Status**: [ ] pending

---

### Step 4 — INPUT-LOAD: load model + narratives + config + template (the L7 split)
**Goal**: The two input files load through P4's own loaders, and every failure
mode lands exactly where L7 pinned it: absent narratives is a note, everything
malformed is a loud exit 2. Implements spec component 4.

**Design**:
Load through imports, never re-write. The absent-vs-malformed split is L7's
entire behavior contract. Because `gm._load_narratives` (`:946-956`) returns
`{}` for BOTH absent and empty, render checks `narratives_path.is_file()` ITSELF
first: absent → use `{}`, set view-model `note` to the literal
`"no narratives yet — run graph_model.py narrate"`, `gm.warn(...)` to stderr,
continue to exit 0 (Decision 5: existing empty `{}` file → NO note, no warn —
curated state). The template is read from the SCRIPT's own dir
(`Path(__file__).parent / "render_template.html"`), NOT the target repo — it
ships WITH the tool. Model absent/malformed → die 2. Narratives present-but-
malformed → die 2. Config via `gm._load_narrate_config` (threshold ignored, only
`narratives_rel`). This Step replaces Step 3's placeholder `cmd_render` body
with the load half; the join/splice come in Steps 5-7.

**Actions**:
1. In `cmd_render`: resolve paths (Step 3) →
   `model = gm._load_model(model_path)` (absent/malformed → die 2).
2. Narratives: if `narratives_path.is_file()`: `narratives =
   gm._load_narratives(narratives_path)` (malformed → die 2; empty `{}` → no
   note). Else: `narratives = {}`, set `note` + `gm.warn(...)`.
3. `(threshold, narratives_rel) = gm._load_narrate_config(config_path)`
   (permissive; threshold ignored).
4. `template_text = (Path(__file__).parent / "render_template.html").read_text()`
   (absent/unreadable → die 2).
5. Pass loaded inputs forward (the shell now holds them for Step 5's join).

**Files to modify**:
- `ssot-diagram/render.py` — flesh out `cmd_render` (load half)

<!-- plan-verify
touch: ssot-diagram/graph_model.py::_load_model
touch: ssot-diagram/graph_model.py::_load_narratives
touch: ssot-diagram/graph_model.py::_load_narrate_config
tier:  B
qualifiers: byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json ; grep-absent "sqlite3.connect" ssot-diagram/render.py
note: the touch: claims are gm functions IMPORTED (read-only reuse), not edited — they exist at graph_model.py:831/946/809 and must stay byte-identical; the _load_model/_load_narratives/_load_narrate_config symbols resolve UNIQUE in codegraph (FCV-verified) so touch verdicts are OK. cmd_render was declared new: in Step 3; Step 4 fills its load half — no new symbol claim here (matches P4's one-claim-per-symbol discipline).
-->

**Test criteria** (Step 10, exit-code tests):
- [ ] Missing model → exit 2, no output file. Malformed model → exit 2.
- [ ] Missing narratives file → renders + note present + `!` warning + exit 0.
- [ ] Malformed narratives file → exit 2, nothing written.
- [ ] Existing empty `{}` narratives file → renders, NO note, no warn, exit 0.
- [ ] Missing template → exit 2.

**Status**: [ ] pending

---

### Step 5 — `build_viewmodel`: the trust join (L2 heart) + the micro-stub addendum note
**Goal**: One pure Python function turns model + narratives into a render-ready
payload where every card's final text, badge, tooltip, edge label, and stub flag
is already decided — so the painter can be dumb. Implements spec component 5 +
records the Decision-1 micro-stub extension against the binding addendum.

**Design**:
`build_viewmodel(model, narratives, *, component=None, title=None) -> dict`.
Import `_derive_status` + `_fallback_text` from gm (L2 — import, NEVER copy,
never re-order branches; A1 order is load-bearing). One nested-model walk (same
shape as `gm._build_sig_index` at `:842-865`). Trust join per node calls
`gm._derive_status(narratives.get(node_id), node["signature"])`; final prose per
the L3 matrix; a derived status outside the 6-value vocabulary → die 2 (A17 —
hand-edited narratives must fail loud, never silent default). Collapsed nodes
bypass the join (`_fallback_text` raises — A2); they carry name +
`collapsed_count` and paint per addendum §1's collapsed treatment. Decision
chips precomputed in Python per L3 (FRESH→positive, STALE/ORPHANED→danger +
"NEEDS REVIEW", AMBIGUOUS→danger palette + literal "AMBIGUOUS — anchor unclear",
superseded→disabled); an unresolved decision id → die 2 (model self-inconsistent).
Every display string precomputed: edge labels (`"calls ×12"`), child-count
subtitles, kind labels, per-node `tooltip` block (F2: chip text first when
present, the node's joined prose, capped `sample_callers`), the header subtitle
(`"10 components · 8 decisions"` — 8 = UNIQUE ADR names per F5). Per-view edge +
stub precompute (A5's id→owning-component + id→owning-micro maps): for each
container (top, each component, each micro) emit `view_edges` (endpoints
resolved to ids present in that view) + `stubs` (one per distinct outside owner).
MICRO focus view: sibling micro of the SAME component → "OTHER FILE" stub
(Decision 1). Top level: omit edges whose BOTH endpoints resolve to the same
component (Decision 7). Full artifact stubs: `stub_nav: true`; `--component`
stubs: `stub_nav: false` (OQ-P5-1). Scoped mode: unknown cid → die 2 listing
known ids; else scope to that subtree + inert stubs + breadcrumb root = the
component (addendum §4). Duplicated nano ids emitted at EACH tree position
(Decision 8 — A15, identical sigs). Legend block precomputed (artifact-scope, what
is present — the painter draws verbatim). Determinism: from the model's already-
sorted arrays + `sorted()` on any dict-derived list; no timestamps; payload
carries ONLY painter-needed fields (drop `dominant_class`, raw `docstring`);

**ADDENDUM NOTE (Decision 1, owner-ratified 2026-07-09):** record the "OTHER FILE"
micro-stub against `AI-artifacts/1_design/p5-html-renderer-ux-addendum.md` §3 —
one token extension: same §3 card grammar as "OTHER COMPONENT", badge label
"OTHER FILE", stub = one per distinct sibling micro that any cross-view edge in
a micro focus view resolves to, identical navigable/inert + cue rules. This is a
NOTE appended to §3, not a redesign of the FROZEN skeleton contracts.

**Actions**:
1. Add `build_viewmodel(...)` to `render.py` per Implementer Notes §4.
2. Build the id→owning-component + id→owning-micro maps in the same nested walk.
3. Resolve decision-chip dict once from `model["decisions"]`; unknown id → die 2.
4. Per node: collapsed → passthrough; else trust join + L3 matrix prose +
   precomputed chips + tooltip block. Emit at each tree position if duplicated.
5. Orphaned entries (id not in model) → `gm.info` count to stderr, never enter
   the payload.
6. Per-container `view_edges` + `stubs`; "OTHER FILE" micro-stub in micro focus
   views; omit same-component top-level edges; full/inert `stub_nav`.
7. Scoped mode handling; legend block; title/subtitle/note.
8. Append the Decision-1 "OTHER FILE" note to the addendum §3.

**Files to modify**:
- `ssot-diagram/render.py` — add `build_viewmodel`
- `AI-artifacts/1_design/p5-html-renderer-ux-addendum.md` — append the "OTHER
  FILE" note to §3 (the ONE authorized addendum edit)

<!-- plan-verify
new:   ssot-diagram/render.py::build_viewmodel
touch: ssot-diagram/graph_model.py::_derive_status
touch: ssot-diagram/graph_model.py::_fallback_text
tier:  A
qualifiers: grep-absent "def _derive_status" ssot-diagram/render.py ; grep-absent "def _fallback_text" ssot-diagram/render.py ; byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
note: _derive_status + _fallback_text are IMPORTED (grep-absent asserts render.py never re-defines them — proves the "import, never copy" L2 invariant). build_viewmodel writes its OWN id->owner maps in a nested walk that only MIRRORS _build_sig_index's shape; it does not call or edit _build_sig_index, so no touch claim on it. The touch: symbols resolve UNIQUE in codegraph (FCV-verified). The addendum edit is a doc mutation, not a codegraph-indexed code claim — guarded by the byte-unchanged graph_model.py golden qualifier + the addendum being explicitly listed in ## Files modified.
-->

**Test criteria** (Step 10, the matrix goldens + structural):
- [ ] Golden + fixture: every L3 NARRATIVE row appears on ≥1 node with the exact
  pinned prose-source/status pairing; `cmp-dist` carries fallback +
  `unnarratable` despite a stored entry (A1 branch order visible); orphaned
  fixture entry nowhere in the payload but counted on stderr; subtitle exactly
  `"10 components · 8 decisions"`.
- [ ] Trustmatrix fixture: every DECISION status maps to its pinned badge, incl.
  literal `"AMBIGUOUS — anchor unclear"` + disabled superseded.
- [ ] Full view-model stubs all `stub_nav: true`; `--component` stubs all
  `stub_nav: false`; micro focus view of a cross-sibling-micro edge shows an
  "OTHER FILE" stub.
- [ ] Two `build_viewmodel` runs → equal payloads.
- [ ] A derived status outside the 6-value vocab → die 2 (A17).

**Status**: [ ] pending

---

### Step 6 — `_escape_viewmodel_json` + `_font_face_css`
**Goal**: The payload between `<script>` tags can never break out of them, and
the fonts arrive as deterministic base64 — the two inert-by-construction steps.
Implements spec component 6.

**Design**:
`_escape_viewmodel_json` (axis 2A, exact formula, F3 invariant) =
`json.dumps(viewmodel, sort_keys=True, ensure_ascii=True,
separators=(",",":")).replace("<", "\\u003c")`. `ensure_ascii=True` escapes
U+2028/U+2029 + all non-ASCII (A11, FCV-verified via `/tmp/esc_check.py` — the
escaped output has zero raw line-separators); the sole remaining dangerous ASCII
char `<` becomes `<`, simultaneously valid JSON + valid JS, so `</script`,
`<!--`, and any HTML-ish payload in narrative text or a `--title` is inert + the
sentinel is collision-proof (the invariant lives in the `<` char, not obscurity).
`_font_face_css` base64-encodes the three vendored woff2 into three `@font-face`
rules (weights 400/500/700), fixed file order, standard base64, deterministic; a
missing asset → die 2 (fail-loud beats silent system-font fallback masking the
zero-network rule). Emitted CSS is repo-controlled, contains no `<` and no
sentinel.

**Actions**:
1. Add `_escape_viewmodel_json(viewmodel) -> str` per Notes §5 (VERBATIM formula).
2. Add `_font_face_css(assets_dir) -> str` per Notes §5 (400/500/700 fixed order,
   die 2 on missing asset).

**Files to modify**:
- `ssot-diagram/render.py` — add `_escape_viewmodel_json` + `_font_face_css`

<!-- plan-verify
new:   ssot-diagram/render.py::_escape_viewmodel_json
new:   ssot-diagram/render.py::_font_face_css
tier:  A
qualifiers: byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
-->

**Test criteria** (Step 10):
- [ ] Any fixture-built view-model: escaped payload has zero `<`, zero bytes
  ≥ 0x80; escaping twice is byte-identical.
- [ ] Deleting one woff2 → render exits 2 naming the missing asset.

**Status**: [ ] pending

---

### Step 7 — `_render_html` splice + `_save_text` + `cmd_render` assembly
**Goal**: The escaped data + the font CSS land in the template at exactly one
place each, loudly failing on template drift, then the file hits disk atomically.
Implements spec component 7.

**Design**:
`_render_html(template_text, viewmodel, font_css)` — pinned F3 order: (1) assert
BOTH sentinels occur exactly once BEFORE any replace (die 2 otherwise); (2)
replace the font sentinel (font CSS contains no sentinel); (3) replace the
view-model sentinel (`/*<SSOT:VIEWMODEL_JSON>*/null` whole token) with the
escaped payload (contains no `<`, hence no sentinel); (4) assert zero sentinels
remain (die 2). Splice = `str.replace` with count checks, deterministic. With
`<`-bearing sentinels the order is no longer collision-load-bearing, but pinning
it keeps the asserts' meaning unambiguous. `_save_text(path, html)` = temp +
`os.replace` + trailing newline (the `_save_model` discipline replicated, not
reused). `cmd_render` assembles the full pipeline: resolve paths (3) → load (4)
→ `build_viewmodel` (5) → `_font_face_css` + `_escape_viewmodel_json` (6) →
`_render_html` → `_save_text` → `gm.ok(f"wrote {out_path}")`.

**Actions**:
1. Add `_render_html(template_text, viewmodel, font_css) -> str` per Notes §6.
2. Add `_save_text(path, html) -> None` per Notes §6.
3. Complete `cmd_render`: path → load → join → escape+font → splice → save → ok.

**Files to modify**:
- `ssot-diagram/render.py` — add `_render_html` + `_save_text`; finish `cmd_render`

<!-- plan-verify
new:   ssot-diagram/render.py::_render_html
new:   ssot-diagram/render.py::_save_text
tier:  B
qualifiers: byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
note: cmd_render was declared new: in Step 3; Steps 4-7 fill its body (load → join → escape+font → splice+save) — no re-claim per P4's one-claim-per-symbol discipline (a symbol is claimed new: once at first definition).
-->

**Test criteria** (Step 10):
- [ ] Same inputs twice → byte-identical files (sha256 equal).
- [ ] A template with a duplicated or deleted sentinel → exit 2, nothing written.
- [ ] An interrupted write leaves the previous output intact (temp + `os.replace`).
- [ ] Written file ends with exactly one newline.

**Status**: [ ] pending

---

### Step 8 — JS painter body: focus views, breadcrumb, stubs, tooltips, legend, theme, pan/zoom
**Goal**: The interactive layer a non-coder touches — every behavior a pure
function of the embedded data + two integers of view state, deriving nothing.
Implements spec component 8.

**Design**:
Extends Step 2's shell. The painter's allowed operations, pinned: read embedded
fields, index them by id (one-time loop at load — Decision 11, indexing ≠
deriving), compute layout geometry, toggle view state. It NEVER computes a
status, count, label, or fallback (ADR-0002 review standard: "no arithmetic, no
conditionals on trust fields, no `.get`-style defaulting").
- **Focus-view state machine (axis 3A, addendum §1):** `viewPath` (0-2 ids) +
  `viewState` (pan/zoom, adapted verbatim from example:955-1014). `paintView()`
  fully re-renders the canvas per path (example's full-re-render discipline):
  components → component focus (header panel + micro grid) → micro focus (header
  panel + nano cards + the "+K more" collapsed card). Expand pushes onto
  `viewPath`; panel `−` pops one. At most ONE node expanded per level by
  construction. Nano cards have NO expand button (Block 4a).
- **Grid layout:** `ceil(sqrt(n))` columns, order = embedded array order, row
  heights from the tallest card per row (generalizes example:480-533); gaps §5.2,
  padding §5.3, margin §5.4. Focus header panel reuses the §3.5 expanded-card look.
- **Breadcrumb (addendum §4):** from `viewPath` via embedded `name` lookups only;
  hidden at top; segments truncate `viewPath` on click (same op as `−`, so they
  can never disagree); §8.2 tokens; scoped files root at the component.
- **Stubs (addendum §3 + Decision 1):** painter switches ONLY on `stub`/`stub_nav`
  flags. Navigable: trailing `→` glyph, `var(--fg-body)` title, `cursor: pointer`,
  hover `var(--ring)` border; click → `viewPath = [neighborId]`. Inert: no glyph,
  `var(--fg-disabled)` title, default cursor, no hover ring; click only does §7.3
  edge-highlight. "OTHER FILE" micro-stub uses the same grammar + the "OTHER FILE"
  badge label. Stubs never expand in place either context.
- **Tooltips (L4 sink b′, F2):** cards carry only `data-node-id`;
  `showTooltip(nodeId)` looks the node up in the JS-built index, fills the tooltip
  DOM exclusively via `setText` from the precomputed `node.tooltip` block (chip
  text first when present, prose in the card's muting). §7.2 trigger (300ms),
  position, box styling unchanged. No prose in attributes, ever.
- **Legend:** draws the embedded `legend` block verbatim with `createElement` +
  `textContent`; §8.3 styling.
- **Edge painting:** rounded orthogonal + arrowheads + precomputed pill labels
  (§4); highlight-on-click + unconnected fade (§7.3); deselect on empty-canvas
  click (§7.5).
- **Theme toggle (§7.6):** `data-theme`, `localStorage` key `diagram-theme`,
  `prefers-color-scheme` default.
- **Pan/zoom (§7.4):** drag, wheel, 0.25-4x, buttons, fit-to-view from layout
  data (never `getBBox`), double-click, touch.

This Step is written against Step 5's view-model Interface shape (the dual-
language contract). The painter is dumb; if a behavior needs a status/count/label
the model doesn't precompute, that is a Step-5 gap, NOT a painter derivation.

**Actions**:
1. Fill `render_template.html`'s `<script>` body with the focus-view state
   machine, `paintView()`, grid layout, breadcrumb, stub switch (incl. "OTHER
   FILE"), tooltip handler, legend, edge painting, theme toggle, pan/zoom.
2. Add the one-time id→node index build at load (Decision 11).
3. Add the `MODEL === null` preview-note guard (Decision 3) if not already in
   Step 2.

**Files to modify**:
- `ssot-diagram/render_template.html` — fill the painter body

<!-- plan-verify
tier:  C
qualifiers: byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
note: HTML asset edit only — Step 8 fills the painter JS body inside render_template.html (declared new: in Step 2). No new symbol/file claim here: re-claiming the same new file as touch: would be MISSING (not yet indexed) and as new: would collide with Step 2. The sentinel-once + innerHTML-only-as-='' invariants are asserted by the Step-10 test criteria, not plan_verify qualifiers.
-->

**Test criteria** (Step 8 + Step 10, observed live — the E2E carries these):
- [ ] Components view shows 10 macro cards; drilling `cmp-lib → store.ts`
  reaches nano cards incl. a "+K more"; breadcrumb tracks + navigates back.
- [ ] Hovering a stale/proposed/unnarratable card shows the same chip text +
  muting in the tooltip (F2).
- [ ] Clicking a navigable stub jumps to that neighbor's focus view; in a
  `--component` file the same stub is inert (no `→`, no navigation).
- [ ] A micro focus view with a cross-sibling-micro edge shows an "OTHER FILE"
  stub.
- [ ] Theme toggles + persists across reopen; pan/zoom + fit-to-view work in
  every focus view.

**Status**: [ ] pending

---

### Step 9 — Fixtures: the three test input sets
**Goal**: Committed, hand-written inputs making every row of both matrix halves
— and every escaping hazard — reachable by tests. Implements spec component 9.

**Design**:
Goldens #1 and #2 share the REAL golden model (sha256 `56df3d86…`, FCV-verified);
golden #3 is synthetic (red-team F4) because the real golden's 11 decisions are
ALL FRESH — it cannot provide the DECISION half of the matrix without a
synthetic model carrying at least one decision in every L3 status.
- **`mkt_engine.narratives.fixture.json`** — small, against REAL golden ids,
  hitting every NARRATIVE treatment row: one approved entry whose signature is
  copied from the golden (→ approved), one proposed entry (fresh sig → proposed),
  one approved entry with a deliberately WRONG pinned signature (→ stale, OLD
  text), one entry for `cmp-dist` (empty-sig component → derives `unnarratable`
  DESPITE the stored entry — makes the A1 branch order visible), and one entry
  with an unknown node id (→ orphaned, dropped + counted). `cmp-invoice-cost` gets
  NO entry (unnarratable-without-entry, the other flavor). Block 5a shape:
  `{node_id, signature, text, status}` (status ∈ {proposed, approved}) wrapped in
  `{"narratives": {...}}`.
- **`injection.narratives.json`** (separate file — Decision 6, keeps golden #2's
  sha stable): narrative text containing `</script><script>`, `<!--`, a literal
  U+2028, AND the literal sentinel text `/*<SSOT:VIEWMODEL_JSON>*/` inside prose
  (the F3 collision case) — plus a `--title` exercising the same chars in test
  runs.
- **`trustmatrix.model.json` + `trustmatrix.narratives.json`** (golden #3, F4):
  a SMALL synthetic model — 2 components, 2 micros, ~3 nanos + 1 collapsed node,
  one empty-signature component — schema-valid for the join (nested children,
  `signature` on every node, resolvable `decisions` ids, top-level keys per A4).
  Its `decisions` list contains ≥1 decision in EVERY status the L3 matrix names —
  FRESH, STALE, ORPHANED, AMBIGUOUS, and literal `"superseded"` — attached to
  visible nodes; the narratives file hits every derived narrative status
  (approved-fresh, proposed, stale, unnarratable, none, orphaned).

**Actions**:
1. Author `testdata/mkt_engine.narratives.fixture.json` against real golden
   ids/signatures (read them from the golden via a one-off script at authoring
   time, paste verbatim — do not hardcode a sha).
2. Author `testdata/injection.narratives.json` (separate file).
3. Author `testdata/trustmatrix.model.json` + `testdata/trustmatrix.narratives.json`
   covering every decision + narrative status row.

**Files to modify**:
- `ssot-diagram/testdata/mkt_engine.narratives.fixture.json` — new
- `ssot-diagram/testdata/injection.narratives.json` — new
- `ssot-diagram/testdata/trustmatrix.model.json` — new
- `ssot-diagram/testdata/trustmatrix.narratives.json` — new

<!-- plan-verify
tier:  C
qualifiers: byte-unchanged ssot-diagram/testdata/mkt_engine.model.json ; byte-unchanged ssot-diagram/graph_model.py
note: data-only step — JSON fixtures, not codegraph-indexed code; no touch:/new: symbol claims. None of the four fixture paths exist yet (UNRESOLVED) but they are inputs the plan creates, not claims about existing code. The frozen golden model + graph_model.py stay byte-unchanged.
-->

**Test criteria** (Step 10):
- [ ] All four fixture files committed + loadable through the real loaders.
- [ ] For each L3 row (both halves), ≥1 fixture node/decision derives exactly
  that status through the REAL `_derive_status`/join (no mocks).

**Status**: [ ] pending

---

### Step 10 — `test_render.py`: three goldens + structural + injection + exit codes + regression
**Goal**: Byte-determinism proven, the trust matrix pinned row-by-row, the
escaping properties asserted directly — so any regression flips a test, not a
reader's trust. Implements spec component 10.

**Design**:
New `ssot-diagram/test_render.py` (pytest, beside the code). Shas pin ONLY after
fonts (Step 1) + painter (Step 8) land. The battery (axis 4A): golden #1 (real
golden, no narratives — pinned sha + "no narratives yet" note + every node
`source == "fallback"` + exit 0), golden #2 (real golden +
`mkt_engine.narratives.fixture.json` — pinned sha + every expected `data-trust`
present + subtitle present + note absent), golden #3 (trustmatrix pair — pinned
sha + per-row structural asserts covering BOTH matrix halves incl. the literal
"AMBIGUOUS — anchor unclear" + disabled superseded). Structural asserts carry
the safety load: embedded node count == 407 tree positions incl. collapsed
(A8/A15); exactly one `</script>` in the whole file; zero `<` in the payload
region; render twice ⇒ byte-identical. Injection test: exactly one `</script>`,
no `<` in payload, both sentinel-count asserts pass. Exit-code tests cover every
L7 failure. Template hygiene: `innerHTML` only as `= ''`; each sentinel once; no
`<link>`/`@import`. Scoped view: `--component cmp-lib` →
`ssot-diagram.cmp-lib.html`; full stubs `stub_nav: true`, scoped `false`. The
A19 regression guard: golden sha `56df3d86…` untouched (renderer never writes
model/narratives) + zero NEW failures vs the `105 pass / 3 pre-existing
TestGoldenLive fails` baseline (RE-BASELINE on build-start day per A19's own
source-note). Sha regeneration procedure documented in the test file header
(mirroring P3's golden discipline): shas are a determinism tripwire, not the
only oracle; every deliberate template edit re-pins them via a stated command.

**Actions**:
1. Create `test_render.py` with the sibling-import seam + golden helpers reuse.
2. Add the three goldens (shas pinned after Steps 1+8 land via the regeneration
   procedure).
3. Add the structural + injection + exit-code + template-hygiene + scoped-view
   + regression tests.
4. Run `python3 -m pytest ssot-diagram/` — new render tests green, zero NEW
   failures vs the re-baselined A19 count; golden NOT skipped (pilot DB present
   for the `TestGoldenLive` set, which stays as 3 pre-existing fails).
5. Deliberately flip one fixture status locally — confirm BOTH a sha AND a
  `data-trust` structural assert fail (double-oracle demo before ship).

**Files to modify**:
- `ssot-diagram/test_render.py` — new

<!-- plan-verify
new:   ssot-diagram/test_render.py::GOLDEN_VM
new:   ssot-diagram/test_render.py::test_golden_no_narratives
new:   ssot-diagram/test_render.py::test_golden_with_fixture
new:   ssot-diagram/test_render.py::test_trustmatrix
new:   ssot-diagram/test_render.py::test_injection_escape
new:   ssot-diagram/test_render.py::test_exit_codes
tier:  C
qualifiers: byte-unchanged ssot-diagram/testdata/mkt_engine.model.json ; byte-unchanged ssot-diagram/graph_model.py
note: test symbols resolve UNRESOLVED until authoring (new: intent → OK). The test file cites the real golden sha `56df3d86…` (FCV-verified) wherever a hash is asserted — never the stale `5a1e2156…`.
-->

**Test criteria**:
- [ ] `python3 -m pytest ssot-diagram/` = new render tests green + zero NEW
  failures vs re-baselined A19.
- [ ] Two renders of golden #1 → byte-identical (sha256 equal).
- [ ] Golden #2 embeds every expected `data-trust` value; subtitle present; note
  absent.
- [ ] Golden #3 covers BOTH matrix halves row-by-row.
- [ ] Embedded node count == 407; exactly one `</script>`; zero `<` in payload;
  render twice ⇒ byte-identical.
- [ ] Flipping one fixture status locally fails BOTH a sha AND a structural assert.
- [ ] Golden sha `56df3d86…` untouched after a full render run.

**Status**: [ ] pending

---

### Step 11 — Manifest: `ssot-render` registration
**Goal**: The tool ships — piggyback knows about it, no hook events (P6 owns
wiring). Implements spec component 11.

**Design**:
Add one entry to `manifest.json` under `scripts`, mirroring the
`diagram-model` / `narrative-sidecar` precedent (A10): `hooks: []` ships without
wiring events. P5 adds ZERO config keys (the two P4 keys are reused unchanged).

**Actions**:
1. Add to `manifest.json` `scripts`:
   `"ssot-render": {"script": "ssot-diagram/render.py", "scope": "repo", "desc":
   "ssot-diagram P5 — render diagram-model + narratives into one self-contained
   interactive HTML", "hooks": []}`.

**Files to modify**:
- `manifest.json` — add `ssot-render` under `scripts`

<!-- plan-verify
tier:  C
qualifiers: byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
gates: human:manifest-edit
note: data-only step — manifest.json is JSON, not codegraph-indexed code, so no touch:/new: symbol claims apply; the edit is guarded by the byte-unchanged golden qualifier + the ## Files list. Human gate because manifest entries are outward-facing (piggyback status).
-->

**Test criteria** (Step 11, observable):
- [ ] `piggyback status` lists `ssot-render`; existing entries unchanged.
- [ ] `manifest.json` still parses as JSON; `diagram-model` + `narrative-sidecar`
  entries unchanged.

**Status**: [ ] pending

---

## E2E Done Criteria
Plain-English: unit tests passing is necessary but not enough. Before "done",
run the real `render.py` end-to-end against the live pilot repo (the one with
`.codegraph/codegraph.db` + the shipped `diagram-model.json`) and watch the actual
HTML artifact behave the way the contract says — especially the trust verdicts
visible on cards + the escape never breaking, the two load-bearing properties of
the phase. (Per OQ-P5-5: the rendered mkt_engine artifact is PRODUCED + verified
but NOT committed to THIS repo — the first committed render lives in the pilot
repo via P6. Plan's final-commit checklist must reflect this.)

**Prerequisites:** the live pilot repo with `.codegraph/codegraph.db` present, a
freshly extracted `ssot-diagram/diagram-model.json` (`graph_model.py extract`),
the shipped `ssot-diagram.config.json`, the vendored DM Sans binaries, and
`render_template.html` all present. No mocks.

**Walkthrough** (action → observe → expected; mapped to ## Capabilities):
1. Run `render.py` bare in the pilot repo → observe stderr `✓ wrote
   <root>/ssot-diagram/ssot-diagram.html` → expected (C3, C7).
2. Open the rendered file with the network disabled → observe 10 macro cards,
   zero console errors, zero network requests, DM Sans rendering (not system
   fallback) → expected (C1, C8, the L5 zero-network rule).
3. With NO `narratives.json` present: observe every card shows fallback text +
   a visible "no narratives yet" note + the stderr `!` warning + exit 0 → expected
   (C4, C5).
4. Drill `cmp-lib → store.ts`: observe the micro focus view's nano cards incl. a
   "+K more" collapsed card; the breadcrumb tracks and navigates back → expected
   (C8, Block 4a).
5. Ingest the `mkt_engine.narratives.fixture.json` entries into a temp
   `narratives.json`, re-render → observe the `cmp-dist` card shows fallback text
   + an "UNNARRATABLE" badge DESPITE a stored entry (the A1 branch order, the
   whole point); the stale fixture entry shows OLD text + a danger "needs review"
   badge; the proposed entry shows muted prose + a "PROPOSED" badge → expected
   (C5, A1).
6. Hover the stale card → observe the tooltip opens with "NEEDS REVIEW — CODE
   CHANGED" before the old prose, same muting (F2) → expected (C8).
7. In the micro focus view of a file with a cross-sibling-micro edge: observe an
   "OTHER FILE" stub (Decision 1) → expected (C5, C8).
8. Render with `--component cmp-lib` → observe `ssot-diagram.cmp-lib.html`
   written; its stubs have no `→` glyph (inert); the full artifact's stubs do
   (navigable) — click one to jump → expected (C3, C8).
9. Render with `--title "<script>alert(1)</script>"` + the injection narratives →
   observe exactly one `</script>` in the file, zero `<` in the payload region,
   both sentinel counts = 1 → expected (C6, C7, the F3 invariant).
10. Render the same inputs twice → observe byte-identical files (sha256 equal) →
    expected (C7, byte-determinism).
11. Run `render.py --model M --narratives N --out O` from a directory with NO
    `.codegraph` anywhere above → observe success exit 0 (the A14 deviation) →
    expected (C3).
12. Run `python3 -m pytest ssot-diagram/` → observe new render tests green + the
    SAME 3 pre-existing `TestGoldenLive` fails + zero NEW failures; the frozen
    golden sha `56df3d86…` unchanged → expected (C10, C11, A19).
13. Run `piggyback status` → observe `ssot-render` listed → expected (C11).

**Done gate:** every walkthrough line observed + matching, evidence captured,
and `python3 -m pytest ssot-diagram/` (new tests green + zero NEW failures) + the
golden byte-match (`56df3d86…`) all pass. If a live observation diverges from a
passing unit test, the live observation wins — fix and re-run before marking done.

**Final-commit checklist (per OQ-P5-5):** P5 commits the TOOL + FIXTURES + TESTS
only (`render.py`, `render_template.html`, `assets/`, `manifest.json` entry,
`test_render.py`, the four `testdata/` fixtures). The first COMMITTED rendered
mkt_engine artifact lives in the PILOT repo (mkt_engine) via P6's regen loop —
NOT committed to codegraph-piggyback at P5 close. E2E still renders + clicks the
live mkt_engine model (steps 1-8 produce + verify the artifact; it just isn't
committed here).

## Open Questions
- **"OTHER FILE" micro-stub (comp 5 Decision) — RESOLVED BY OWNER 2026-07-09
  (AskUserQuestion, this plan's design gate): pick (a), show the file name.**
  One-token extension of addendum §3 recorded in Step 5 + painted in Step 8.
  Reversible; if the owner later prefers option (b) (always-resolve-to-component),
  it is a Step-5 stub-resolution change + a Step-8 badge-label change only. Not
  blocking.
- **Font weight 600 (archived §2.3 legend title/header) — RESOLVED by design
  (browser synthesis from 500).** Restated; do not vendor a fourth file. Not a
  blocker.
- **P6-deferred items** carried from P4/design/spec: `status --strict`, narrative
  GC, declined markers, non-frozen-field loud guard (STATE.md MINOR b), hook
  wiring / PostToolUse re-render (P6). Not blockers.

## Out of Scope
Per spec `## Out of scope` (do not restate — link): hook wiring / auto-
regeneration (P6); `status --strict` roll-up, narrative GC, declined markers
(P6); plan-visualizer's overlay fields (Phase D — only the reuse seam is
committed here); writing anything back to `narratives.json` / the model / the DB
(renderer's only persisted output is the HTML artifact); committing a rendered
pilot artifact in THIS repo at P5 close (OQ-P5-5); any JS/graph library /
static SVG-PNG export / per-component iframe stitching / hand-authored layout
hints (rejected design alternatives); the loud startup guard for P3's non-frozen
fields (P6, STATE.md MINOR b). Additionally out of scope for this plan: editing
`graph_model.py` / `decision_index.py` / the frozen golden model / the FROZEN
skeleton contracts; any change to `extract` / `bootstrap-config` / `narrate`
behavior; `_shared/` extraction (Phase B); a config schema version bump.
