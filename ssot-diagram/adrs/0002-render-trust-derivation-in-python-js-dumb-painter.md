# ADR 0002 — Render-time trust derivation lives in Python; browser JS is a dumb painter

## Status

Accepted (2026-07-06). Owner-ratified at the P5 requirements grill (locked
decision 2); recorded here at the P5 design step.

## Context

P5's renderer (`render.py`) turns two files — the deterministic code map
(`diagram-model.json`, P3) and the signature-pinned plain-language sidecar
(`narratives.json`, P4) — into one self-contained interactive HTML file. The
HTML necessarily contains JavaScript, which raises the question of WHERE the
trust verdicts are computed: which sentence a node shows, and whether it is
approved / unreviewed / stale / fallback.

Block 5b (skeleton-contracts.md:190-205) puts a "consumer obligation" on every
consumer of `narratives.json`: `stale` is never stored, so a consumer MUST
derive it live by comparing the entry's pinned signature to the current model
node's signature. A consumer that reads the stored `status` field literally and
trusts `approved` will render drifted prose as current — the exact failure P4's
red-team rounds spent two fixes (F6, TD-P4-1) closing.

The derivation already exists as tested Python: `_derive_status`
(graph_model.py:1000-1014, branch order load-bearing: empty-signature
quarantine first, then missing entry, then vanished node, then signature
mismatch) and `_fallback_text` (graph_model.py:898-926). ADR-0001 established
the sibling-import seam for reusing shipped helpers without copying them.

## Decision

All trust logic runs in PYTHON at render time. `render.py` imports P4's
`_derive_status` and `_fallback_text` from `graph_model.py` via the ADR-0001
sibling-import pattern — import, NEVER copy. It joins every model node with a
final `{text, status, source}` and embeds the joined result as one `MODEL`
constant in the HTML.

The browser JavaScript is a dumb painter: it reads embedded fields only and
derives NOTHING — no status, no counts, no fallback sentences, no defaults for
missing fields. Every display string (edge labels like "calls ×12",
child-count subtitles, badge labels, tooltip lines) is precomputed in the
Python join. If the JS is wrong it can only draw badly; it cannot misreport
trust.

## Alternatives Considered

### Option B — derive status in the browser JS

Embed the raw model + raw narratives and let JS compare signatures and pick
fallbacks. Rejected: it forks the trust recipe into a second language with no
test harness parity — the `_derive_status` branch order (empty-sig before
equality; vanished before mismatch) took two red-team rounds to get right in
Python, and a JS re-implementation would drift silently. It also bloats the
artifact with fields the painter never needs (signatures, raw docstrings).

### Option C — hybrid (status in Python, counts/labels in JS)

Smaller embedded payload; JS formats counts and labels from raw fields.
Rejected: it blurs the audit line. "JS derives nothing" is checkable by
inspection and by test (no arithmetic, no conditionals on trust fields, no
`.get`-style defaulting in the painter); "JS derives only harmless things"
requires case-by-case judgment forever, and count/label bugs still lie to a
non-coder (a wrong "+K more" or edge count misstates the code map).

## Consequences

Positive:

- One copy of the trust recipe, already tested (66 `TestNarrate*` + 10
  `TestNarrateEmptySig` tests guard it); Block 5b's consumer obligation is
  satisfied by construction, not by re-implementation.
- The catastrophic failure class (drifted prose rendered as current) is
  confined to Python, where the golden render test pins one node per
  status→treatment row.
- The painter is portable: plan-visualizer can reuse the template + view-model
  seam without inheriting any trust logic.

Negative:

- The embedded payload is a render-ready view-model, not the raw model — a
  third artifact shape to document (mitigated: it is ephemeral, regenerated on
  every render, never persisted as state).
- Any new display affordance needs a Python change + re-render, even
  cosmetic-with-data ones (accepted: regeneration is P6's whole job).
- `render.py` becomes a second consumer of `graph_model.py` internals,
  widening the sibling-import seam Phase B must eventually consolidate
  (tracked in ADR-0001's consolidation notes).

## References

- Design doc: `../AI-artifacts/1_design/p5-html-renderer.md` (Constraints L2;
  Chosen Approach §3-§4)
- Contract: `../../docs/roadmap/skeleton-contracts.md` Block 5a/5b + empty-sig
  amendment (the consumer obligation this decision satisfies)
- Recipe source: `../graph_model.py` `_derive_status` (1000-1014),
  `_fallback_text` (898-926)
- Seam precedent: `0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`
