# Red-Team Report — P5 Interactive HTML renderer (`render.py`) design

**Target:** `p5-html-renderer.md` + `p5-html-renderer-ux-addendum.md` + ADR-0002/0003
**Reviewer mode:** SAME-MODEL (Claude reviewing a Claude-authored artifact) — certifies
craft (contradictions, escaping math, contract compliance, test coverage), CANNOT
certify shared judgment. A cross-model pass (GPT-5.5 / GLM 5.2) is still owed on the
architecture calls.
**Verification:** all code claims checked against `graph_model.py`, the golden model,
and the archived reference HTML on disk. Escaping + marker behavior reproduced in Python.

## Steelman (the strongest honest case)

The design's spine is genuinely sound: it makes trust a *Python* computation
(`_derive_status` / `_fallback_text` imported, never re-implemented) so the browser is a
dumb painter that "can only draw ugly, never lie." That squarely satisfies Block 5b's
consumer obligation by construction, keeps one tested copy of the two-round-hardened
branch order, and the golden-#2-per-row + double-render sha tripwire is a real proof of
determinism. The escaping choice (`ensure_ascii=True` + `<`→`<`) is the correct,
verify-by-whitelist mechanism — I reproduced that it neutralises `</script>`, `<!--`, and
U+2028/9. Drill-down over overlay-in-overlay is the right call at the pilot's real 47-micro
scale. Most of the doc is defensible; the findings below are where the *contract the
implementer will actually follow* diverges from that spine.

## Findings

### F1 — MAJOR / VERIFIED — The binding UX contract contradicts the owner's ratified OQ-P5-1 (navigable stubs)
- **Where:** `p5-html-renderer.md:541-553` (resolved banner) vs `p5-html-renderer-ux-addendum.md:107-109` and `p5-html-renderer.md:468-472` (Chosen Approach §5).
- **Impact:** The owner *overrode* the recommendation and ruled stubs NAVIGABLE in the full artifact (inert only in `--component` files), and required "the visual cue distinguishing them." But the two sections an implementer actually builds from — the UX addendum §3 ("Non-expandable and **inert**: clicking a stub does nothing… OQ-P5-1 recommendation: inert everywhere") and Chosen Approach §5 ("same grammar… renders them non-expandable") — still encode the pre-override INERT behavior and specify NO distinguishing visual cue. An implementer following the "LOCKED UX contract" ships the exact behavior the owner rejected.
- **Evidence:** banner: "OQ-P5-1 → NAVIGABLE in the full artifact (owner overrode the inert recommendation)… Spec must pin both behaviors + the visual cue." Addendum §3 line 109: "(Design OQ-P5-1 recommendation: inert everywhere, one rule…)". The addendum was never reconciled to the resolution.
- **Check:** `grep -n "inert\|navigab\|OQ-P5-1" p5-html-renderer-ux-addendum.md p5-html-renderer.md` — the addendum says inert, the banner says navigable.

### F2 — MAJOR / VERIFIED — Tooltip is an unaccounted third DOM sink AND launders trust
- **Where:** `p5-html-renderer.md:439-456` (§4 "the two escape points"), `p5-html-renderer-ux-addendum.md:92-93` and §1 line 50; archived `spec.md` §7.2.
- **Impact (two distinct defects):**
  1. **Escaping-surface claim is incomplete.** L4/§4 states every model-derived string reaches the DOM through "exactly two helpers" (`setText`/`paintWrappedText`, both `textContent`). But §7.2 tooltips read `data-title`/`data-type`/`data-desc` **attributes** — a third sink. The archived files set them via `setAttribute` (safe), but the reference has **no tooltip render handler at all**, so P5 builds the display code net-new; how it puts `data-desc` on screen (innerHTML vs textContent) is unspecified. The "escaped at BOTH points" contract does not name this point.
  2. **Trust laundering on hover.** The addendum lists tooltip content as "name, kind label, **prose text**, and capped file:line" with no status/badge. So hovering a `stale` or `proposed` card shows the OLD/unreviewed prose as plain tooltip text with **no muting and no "NEEDS REVIEW" chip** — directly defeating "nothing outdated ever looks current" (addendum §2 intro). The card is marked; the tooltip is not.
- **Evidence:** `template.html:430` / `example…html:583`: `'data-desc': node.tooltip || node.desc || ''` set via `svgEl`→`setAttribute`; no `mouseenter`/tooltip-show handler exists in either reference file (grep returns only the attribute declarations). Addendum line 92-93 enumerates tooltip fields with no trust channel.
- **Check:** `grep -n "data-desc\|tooltip\|mouseenter\|innerHTML" template.html diagrams/example-system-architecture.html` — attributes declared, no renderer; then confirm addendum §2 tooltip line carries no status field.

### F3 — MAJOR / VERIFIED — Splice markers survive the escape verbatim; "impossible in escaped output" is false
- **Where:** `p5-html-renderer.md:446-447` ("The marker string itself is chosen to be impossible in escaped output"), §2 step 5 splice, §1 markers `__SSOT_VIEWMODEL_JSON__` / `/*__SSOT_FONT_FACE__*/`.
- **Impact:** The chosen markers are pure ASCII with no `<`; the escape only removes `<` and non-ASCII. I reproduced that a view-model whose text contains `__SSOT_VIEWMODEL_JSON__` or `/*__SSOT_FONT_FACE__*/` yields an escaped payload that **still contains those substrings verbatim**. Since `--title` is user free text and narratives are LLM-authored (and this very repo's narratives discuss `render.py`'s markers — a real dogfooding path), the payload can carry a marker. Depending on splice order / when the "exactly once" assert runs, the second `.replace` then either (a) rewrites the marker occurrence **inside** the already-embedded MODEL JSON with the font CSS → invalid JS → silently blank artifact (exit 0), or (b) trips the occurrence-count assert → `die 2` on innocent content. Either way an availability/corruption bug is reachable from content `render.py` does not control, and the doc's stated safety property is provably wrong.
- **Evidence:** `python3` reproduction — escaped payload of `{"x":"see __SSOT_VIEWMODEL_JSON__ and /*__SSOT_FONT_FACE__*/"}` returns `marker VIEWMODEL in payload: True`, `marker FONT in payload: True`, `has < : False`.
- **Simpler fix (removes the problem):** make the data marker contain a `<` (e.g. `<<<SSOT_VIEWMODEL>>>`). Because the escape guarantees the payload has zero `<`, such a marker is genuinely collision-proof — which is the property the doc *claims* but its chosen marker lacks.
- **Check:** run the repro above; then grep the design for any pinned splice order (there is none: §2 step 5 doesn't fix ordering).

### F4 — MAJOR / VERIFIED — Golden test cannot exercise the decision half of the L3 matrix
- **Where:** `p5-html-renderer.md:482` (success criterion 3: "Every L3 matrix row is visibly distinct in golden #2"), Risks line 502-506 ("golden #2 pins one node per matrix row").
- **Impact:** The L3 matrix has TWO halves — narrative statuses (approved/proposed/stale/unnarratable/none/orphaned) and **decision** statuses (FRESH/STALE/ORPHANED/AMBIGUOUS/superseded, incl. the design-added "AMBIGUOUS — anchor unclear"). Narrative rows can be manufactured via the fixture, but decision statuses come from the MODEL, and the golden model's 11 decisions are **all FRESH** (verified). `narratives.json` cannot manufacture a STALE/ORPHANED/AMBIGUOUS/superseded decision. So the danger-badge decision painters — including the exact "STALE decision painted as FRESH-positive" laundering class the design exists to prevent — ship with **zero golden coverage**. The central mitigation ("any branch regression flips a pinned sha AND a data-trust assert") holds only for the narrative half.
- **Evidence:** golden survey: `decision statuses: ['FRESH']` (all 11). `_WORST_ORDER` (`graph_model.py:42`) confirms STALE/ORPHANED/AMBIGUOUS/superseded are reachable statuses the painter must switch on.
- **Check:** `python3 -c "import json;print(sorted({d['status'] for d in json.load(open('ssot-diagram/testdata/mkt_engine.model.json'))['decisions']}))"` → `['FRESH']`. A second small model fixture with non-FRESH decisions is required; the fixture-only approach cannot cover this.

### F5 — MINOR / VERIFIED — Header subtitle "11 decisions" double-counts ADRs
- **Where:** `p5-html-renderer.md:423` ("`10 components · 11 decisions`"), Summary line 65 addendum.
- **Impact:** The golden has 8 unique ADRs but 11 decision *nodes* (ADR-0001/0003/0007 are each attached to two components). A non-coder reads "11 decisions" as eleven distinct decisions. The precomputed subtitle counts attachments, not decisions.
- **Evidence:** `decision names: ['ADR-0001','ADR-0001','ADR-0002','ADR-0003','ADR-0003','ADR-0004','ADR-0005','ADR-0006','ADR-0007','ADR-0007','ADR-0008']` — 11 nodes, 8 unique ids.
- **Check:** `python3 -c "import json;d=json.load(open('ssot-diagram/testdata/mkt_engine.model.json'))['decisions'];print(len(d),len({x['name'] for x in d}))"` → `11 8`.

### F6 — MINOR / SUSPECTED (human-authority) — No recorded artifact-size / repo-scale ceiling
- **Where:** `p5-html-renderer.md:154-157` ("lands near 1–1.5 MB… Acceptable for a repo artifact"), Risks line 533.
- **Impact:** The author *decides* that a 1–1.5 MB self-contained HTML with ~407 painted nodes is acceptable, and asserts browser usability, with no recorded owner answer for the tool's target max repo size. ssot-diagram's whole value is a non-coder opening the file; at trezor-scale the model is many MB and the artifact could be tens of MB / thousands of DOM nodes that hang a browser, with `--component` as the only escape hatch. Also unspecified: whether `ssot-diagram.html` is committed (churning a ~1.5 MB diff each render) or gitignored. These are budget/scale/operating-burden calls the artifact may record but not silently decide.
- **Check:** confirm no scale target exists in `roadmap.md` §P5 or `skeleton-contracts.md`; ask the owner for a max-repo-size / artifact-size budget and the commit policy.

## Notes checked and cleared (not findings)
- Escape math A11: `ensure_ascii=True` + `<`→`<` neutralises `</script>`, `<!--`, U+2028/9 — reproduced true.
- Per-node decision-chip join: model nodes DO carry a full `decisions` id list resolving 100% against `model["decisions"]` (verified 26 non-empty, 0 unresolved) — the join is feasible as described.
- Collapsed-node branch: collapsed nodes carry only `{id,kind,name,collapsed_count,signature}` (no `decisions`/`children` mis-read); `_fallback_text` correctly raises on them — design's `kind=="collapsed"` guard is warranted.
- `legend`/`buildLegend`: the archived `innerHTML` interpolation (`template.html:744,751`) is genuinely a hazard, and §4(b) explicitly rewrites it to `createElement`+`textContent` — correctly caught.
- Non-frozen fields (`caller_count`/`is_exported`/`docstring`): read only inside `_fallback_text` with documented defaults; adds no new read site — acknowledged debt, not worsened.
- `orphaned` narratives: dropped via a narratives-minus-model pass; `_derive_status`'s orphaned branch is effectively unreachable in render's model-walk, but that is harmless (two mechanisms, same result).

## Verdict

**REVISE** — the trust spine is sound, but four MAJOR contract defects must be fixed before
spec: the UX addendum contradicts the owner's navigable-stub ruling (F1), the tooltip is an
un-escaped, un-trust-marked third sink (F2), the splice markers are not collision-proof and
the doc claims they are (F3), and half the trust matrix ships golden-untested (F4). None
require rethinking the architecture; all are spec/contract/test changes.
