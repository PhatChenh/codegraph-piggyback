# Red-team review — P4 Narrative Sidecar design

Target: `ssot-diagram/ai-artifacts/1_design/p4-narrative-sidecar.md`
Reviewer: adversarial, fresh-context. Verified against `graph_model.py` (commit on disk),
`decision_index.py`, `testdata/mkt_engine.model.json`, `skeleton-contracts.md`.

## Steelman

The design is disciplined and well-grounded. It reuses P3's proven machinery
(`_save_model`, `_sorted_sha256`, `di.*` discovery) instead of reinventing it, keeps
the file to the four frozen Block-5a fields, and correctly identifies that staleness
is a *comparison against the live model* rather than a badge you can mutate into the
file. The deny-by-default per-id approve gate mirrors `decision_index refresh` exactly,
so a human touches every trusted sentence — a faithful reading of Block 5b's intent.
The deterministic fallback guarantees the diagram is always readable before any human
work is done, which is the right posture for a non-coder SSOT tool. Most of the "assumptions
to verify" are in fact verified against the golden model. This is a solid design; the
findings below are about contract-interpretation risk and a handful of concrete bugs
that would surface at implementation, not a fundamental rethink.

---

## Findings

### F1 — Stored status ≠ frozen status vocabulary; the contract fidelity is a real fork
Where: design §Constraints (Block 5a), §Alternatives C (lines 151–174); contract Block 5a/5b
Severity: MAJOR
Confidence: VERIFIED
Impact: Two independent teams (P5 renderer, biography Phase F) will read `narratives.json`.
The frozen contract says the entry's `status` field is `proposed|approved|stale`
(skeleton-contracts.md:177). This design stores ONLY `proposed|approved` and *derives*
`stale` at read time (design lines 48–50, 166). Any consumer that follows the frozen
contract literally — reading `entry["status"]` and trusting `stale` to appear there —
will NEVER see a stale entry, because the file never contains that value. It will treat
a drifted, out-of-date sentence as `approved` and render it as trusted current prose.
That is the exact failure Block 5b exists to prevent.
Evidence: contract Block 5a: `status: proposed|approved|stale` (skeleton-contracts.md:177).
Design line 166: "The stored field in `narratives.json` carries only `proposed` or `approved`".
Design line 169–173 acknowledges the fork and reinterprets 5a as "a contract on the OUTPUT
… not on what is STORED" — but that reinterpretation is the design's own, not the frozen
text, and it is load-bearing for every downstream consumer. The design's own "Downstream
consumer contract" (lines 706–715) silently requires consumers to run P4's derivation logic;
nothing in the frozen contract obligates them to. This is a silent redesign of a FROZEN block.
The interpretation may well be the *right* one (a stored stale flag genuinely can lie —
Alt C is a good argument), but choosing it is a contract-amendment decision the human must
ratify, not something a design doc resolves unilaterally.
Check: `grep -n "proposed|approved|stale" docs/roadmap/skeleton-contracts.md` then confirm
with the contract owner whether "derive stale, store only proposed/approved" is an approved
reading or requires amending Block 5a to say so explicitly.

### F2 — Byte-determinism claim collides with `_save_model`'s actual serialization
Where: design §narratives.json format (lines 314–317), §Constraints (line 81)
Severity: MINOR
Confidence: VERIFIED
Impact: The design repeatedly says the writer omits `generated_at` ("No `generated_at`
field — the file's mtime is the timestamp", line 316; "generated_at absent or null", line 81).
But it also says it reuses `_save_model` verbatim (lines 39, 184, 601). `_save_model` does
NOT add or strip `generated_at` — it serializes whatever dict you hand it, and appends a
trailing `"\n"` with `ensure_ascii=False` (graph_model.py:804). The determinism story is
fine as long as the narratives dict is built deterministically, but two specifics in the
design are wrong-as-written: (a) "sort_keys=True … entries written in node_id-sorted order"
is redundant — `sort_keys=True` already orders dict keys, so a plain dict keyed by node_id
serializes in sorted order automatically; the "entries sorted by node_id" step (line 96, 185)
is a no-op if the container is the `{"narratives": {node_id: entry}}` dict shown on line 301,
and is only meaningful if the container were a list (which it is not). (b) the design must
match `_save_model`'s trailing newline + `ensure_ascii=False` or determinism tests comparing
against a hand-built expected string will fail on the newline. Neither breaks the design,
but the spec text is internally inconsistent about what produces the ordering.
Evidence: graph_model.py:804 `tmp.write_text(json.dumps(model, indent=2, sort_keys=True,
ensure_ascii=False) + "\n")`. Design line 301 shows a dict-of-dicts container, line 96/185/314
describe list-style "sorted by node_id" ordering.
Check: `sed -n '804p' ssot-diagram/graph_model.py`

### F3 — `load_config` will reject the two new config keys — schema is strict, not permissive
Where: design §config new field (lines 284–296), §R5 (430–435), §FM7 (506–510)
Severity: MAJOR
Confidence: VERIFIED
Impact: The design assumes adding `narrate_threshold` and `narratives_path` to
`ssot-diagram.config.json` is free because they are "optional with explicit defaults"
and "the schema stays version 1" (line 433). It also assumes P4 reads them via
`cfg.get("narrate_threshold", …)`. But `load_config` (graph_model.py:72–120) is a *strict
validator* that P4's own `worklist`/`status` commands must call to get `config["components"]`
for scope. It validates `version`, `components`, `default_component`, `nano_cap` and returns.
It does NOT read or preserve unknown keys destructively — unknown keys survive in the returned
dict, so `cfg.get("narrate_threshold", 4)` will in fact work. The real trap is the reverse:
the design never states P4 *needs* the components list at all, yet `narrate worklist` scope
("every component + every micro") requires walking the MODEL, not the config — so `load_config`
may not even be needed by P4. If P4 does call `load_config` (e.g. to read `narrate_threshold`),
it inherits every `die()` in that function: a config missing `default_component` aborts a
read-only `narrate status`. Worse, `nano_cap` in the config is already 8 while `narrate_threshold`
default is 4 — the design silently introduces a SECOND threshold with different semantics than
the existing `nano_cap` (which caps DISPLAYED nanos), and nothing reconciles "a nano collapsed
away by nano_cap=8" against "a nano in worklist scope by caller_count>=4". A collapsed nano
can be in narrate scope by threshold yet have no addressable node in the model (it's inside a
`collapsed` node). See F4.
Evidence: graph_model.py:72–120 (strict validator, multiple `die()` paths). Config file has
`nano_cap: 8`, design proposes `narrate_threshold: 4` (design line 288).
Check: `python3 -c "import graph_model; graph_model.load_config.__doc__"` and read 72–120;
confirm whether P4 reads config via load_config or a separate permissive reader.

### F4 — Threshold scope can name nanos that were collapsed out of the model → no node to pin
Where: design §worklist scope (212–216), §index builder (365–376), §A9 (664–673)
Severity: MAJOR
Confidence: VERIFIED
Impact: Worklist default scope is "nanos where `is_exported OR caller_count >= narrate_threshold`"
(line 212). But P3 collapses per-micro nanos beyond `nano_cap` into a single `collapsed` node;
those collapsed nanos DO NOT appear as addressable nodes in `diagram-model.json` — only an
aggregate `{kind: collapsed, collapsed_count, …}` remains (verified: `micro:lib/canvas/store.ts`
has 8 nanos + 1 collapsed, `collapsed_count` hides the rest). The design's scope predicate is
described as if it runs over all functions, but the ONLY nanos P4 can see are the ones P3 chose
to emit. So a highly-called exported function that got collapsed away is silently absent from
the worklist — the non-coder never gets prompted to narrate it, and there is no node_id to pin
to. The design's index builder correctly skips `collapsed` (line 372), but never reconciles the
scope predicate against nano_cap collapsing. The worklist is therefore a function of nano_cap,
not of the threshold the design advertises.
Evidence: golden model `micro:lib/canvas/store.ts` children = 8 nano + 1 collapsed (len 9),
collapsed node id `nano:+collapsed@micro:micro:lib/canvas/store.ts` carries only
`collapsed_count`. Design line 212 states the scope predicate as if over raw functions.
Check: `python3 -c "import json;m=json.load(open('ssot-diagram/testdata/mkt_engine.model.json'));
print([na['kind'] for c in m['components'] for mi in c['children'] for na in mi['children'] if mi['id']=='micro:lib/canvas/store.ts'])"`

### F5 — One ADR fans out to N decision nodes; the human narrates the same decision N times
Where: design §deterministic fallback decision (352–357), §worklist scope
Severity: MAJOR
Confidence: VERIFIED
Impact: The design treats each `decision` node as one worklist item with fallback
`"<name> — decision, <status>."` using `decision["name"]` (line 356). But P3 emits ONE decision
node per (ADR × component it attaches to): the golden model has `decision:ADR-0001@cmp-components`
AND `decision:ADR-0001@cmp-lib`, both with `name == "ADR-0001"`, `status == "FRESH"`, and DIFFERENT
signatures (each pins its own component's anchor sigs). So the worklist asks the human to write a
plain-language sentence for "ADR-0001" twice, once per component, with identical fallback text but
distinct node_ids and distinct signatures. Approving one does not approve the other; drift in one
component's anchors staleness-flags only that copy. For a non-coder SSOT tool this is confusing
duplication the design never surfaces (it implicitly assumes one node per ADR). Not a data-loss bug
(ids are unique, no double-count in the file), but a real UX/scope hole: the flagship promise is
"a plain-language sentence for every node", and this multiplies decision work by fan-out.
Evidence: golden model decision ids include both `decision:ADR-0001@cmp-components` and
`decision:ADR-0001@cmp-lib`; `_merge_decisions` builds `decision:{did}@{cid}` per component
(graph_model.py:688). 11 decision nodes for 8 ADRs.
Check: `python3 -c "import json;m=json.load(open('ssot-diagram/testdata/mkt_engine.model.json'));
import collections;print(collections.Counter(d['name'] for d in m['decisions']))"`

### F6 — State-machine hole: an approved entry that drifts stale can never regain fresh text
Where: design §ingest (241–243), §approve (250–261), §status (272–277)
Severity: MAJOR
Confidence: VERIFIED
Impact: Trace the loop. `ingest` writes entries as `proposed` and explicitly "does NOT touch
existing `approved` entries" (line 242–243). `approve` re-pins signature and sets `approved`.
Now: an `approved` entry drifts stale (code changed → new model signature). To get correct new
text, the human must re-run worklist (the node appears because stored sig ≠ current sig, line 210),
have an LLM fill new text, then `ingest`. But ingest "does NOT touch approved entries" — so the
new proposed text is silently dropped for exactly the nodes that most need it (approved-but-stale).
The only escape is `reject` (delete) then re-`ingest` then re-`approve` — a three-step dance the
design never documents, and `reject` throws away the human-approved history. There is no single
"the code changed, here is fresh text, approve it" path; the design's own ingest rule blocks it.
Meanwhile `approve` re-pins the signature to CURRENT without changing text (line 253–254) — so a
human can "approve" a stale entry into fresh-looking status while the TEXT still describes old code,
because approve never checks that the text was updated. That is a silent-trust hole: re-pin makes
old prose look current.
Evidence: design line 242 "Existing `approved` entries are NOT touched by ingest — only nodes
with no current entry or with `status: proposed` are updated." Design line 253 approve re-pins
signature to current with no text-change requirement.
Check: read design lines 241–261 and trace: approved+stale node → worklist → ingest (skipped) →
no path to new text without reject.

### F7 — `reject` of a node still in scope silently resurrects it next worklist run (no "declined" state)
Where: design §reject (263–267), §worklist (205–210)
Severity: MINOR
Confidence: VERIFIED
Impact: `reject` deletes the entry; the node reverts to fallback. But if the node is still in
default scope, the very next `worklist` run lists it again (status derives to `none`), and the LLM
re-proposes text for it. There is no "declined/skip" record, so a human who deliberately rejected a
node's narrative is nagged forever. This mirrors a gap the frozen rail contract (Block 1c) solved
for the piggyback picker with a per-repo "declined vs never-seen" record — the same distinction is
absent here. Low blast radius, but it makes the worklist noisy over time and there is no way to say
"this node is fine with fallback, stop asking".
Evidence: design line 265 reject "Removes the entry"; line 277 status `none` = "no entry; node would
appear in the next worklist run"; contract Block 1c (skeleton-contracts.md:39–44) records "declined"
vs "never seen" — precedent the design does not follow.
Check: read design 263–277; confirm no persisted "declined" marker exists.

### F8 — Micro fallback `len(micro["children"])` counts the collapsed node as a function
Where: design §fallback micro (338–342)
Severity: MINOR
Confidence: VERIFIED
Impact: The literal formula on line 341 is `"<name> — file, <N> function(s)."` with
`N = len(micro["children"])`. Prose on line 342 says "excluding the collapsed node if present",
but the formula does not. A micro with 8 real nanos + 1 collapsed node has `len(children) == 9`
(verified: `micro:lib/canvas/store.ts`), so the fallback reads "9 function(s)" when there are 8
(plus more hidden). For a non-coder SSOT the number is simply wrong. Trivial spec fix, but as written
the two sentences contradict and the wrong one is the executable one.
Evidence: golden `micro:lib/canvas/store.ts` children length 9, last kind `collapsed`. Design line 341
formula vs line 342 caveat.
Check: `python3 -c "import json;m=json.load(open('ssot-diagram/testdata/mkt_engine.model.json'));
print([len(mi['children']) for c in m['components'] for mi in c['children'] if mi['id']=='micro:lib/canvas/store.ts'])"`

### F9 — `--include-nanos` scope diverges between worklist and status → orphaned proposed entries
Where: design §worklist scope (212–216), §status scope (271)
Severity: MINOR
Confidence: SUSPECTED
Impact: `worklist --include-nanos` forces ALL visible nanos into scope; `status` uses "same default
scope as worklist" (line 271) but has no `--include-nanos` flag documented. So a nano ingested/approved
via `--include-nanos` (below threshold, not exported) is a valid stored entry that `narrate status`
never lists (it is outside default scope) and default `worklist` never re-checks for staleness. The
entry becomes invisible to the two commands that surface drift — trusted-but-unwatched prose. The
design says orphans are surfaced by status (R3/FM2) but a below-threshold approved entry is not an
orphan (its node exists); it is simply out of scope, and nothing watches it.
Evidence: design line 271 status scope = worklist default scope; no `--include-nanos` on status
(CLI surface line 196). worklist has `--include-nanos` (line 190).
Check: read CLI surface lines 189–197; confirm `status` has no scope-widening flag.

### F10 — Concurrency dismissal understates the real single-user race (worklist→ingest window)
Where: design §R4 (419–428), §FM5 (487–494)
Severity: MINOR
Confidence: VERIFIED
Impact: The design dismisses write-write races as "not a realistic usage pattern" for a solo builder.
Fair for two simultaneous `approve` calls. But the real single-user race is already documented as R1:
model re-extracted between worklist and ingest. The design catches that via signature check at ingest —
good. However the same window exists between ingest and approve, and the design's mitigation (approve
re-reads current model, re-pins) means approve silently pins to a NEWER signature than the text was
written against (see F6). So the "safe" re-pin is itself the trust hole. The concurrency section looks
complete but the genuinely dangerous interleaving (extract during the human's fill step) is only partly
handled and interacts with F6.
Evidence: design line 260–261 "Approve always re-reads the current model, ensuring the pin is fresh" —
which pins possibly-newer code to possibly-older text.
Check: cross-read design R1 (395–401) + approve (250–261) + F6 above.

---

## Human-authority audit

- `narrate_threshold` default = 4 (design line 293): a silently-chosen scale/scope value that
  determines HOW MUCH narration burden the non-coder owner takes on. This is exactly an operating-burden
  knob (§human-authority). The design picks 4 with no rationale tied to the pilot repo and no ASK. It also
  sits unreconciled next to the existing `nano_cap = 8`. MAJOR by the audit rule — the principal should
  set/ratify the worklist volume, not inherit a silent 4. (Folds into F3/F4.)
- `narratives_path` default location and the manifest question (line 388) are correctly flagged OPEN.

## Verdict

**REVISE.** No CRITICAL rethink — the architecture (derive-stale, reuse P3 writer, per-id gate) is sound
and mostly verified. But three MAJOR items must be resolved before build: (F1) the store-only-proposed/approved
reading is a unilateral reinterpretation of a FROZEN contract and needs the owner's ratification plus an
explicit downstream-consumer obligation, or P5/biography will render stale prose as current; (F6) the
approve/ingest state machine has no path to refresh approved-but-stale text and lets re-pin launder old prose
as fresh; and (F4/F3) worklist scope is silently governed by `nano_cap` collapsing and a second unratified
threshold, so the "sentence for every node" promise leaks. F5 (per-component ADR fan-out) and the
human-authority threshold default should be surfaced to the principal in the same pass.
