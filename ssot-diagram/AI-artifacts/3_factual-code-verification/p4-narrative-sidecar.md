# Factual Code Verification: P4 Narrative Sidecar (`narrate` subcommands)
_Last updated: 2026-07-06_

## Overview

P4 adds five `narrate` subcommands to the existing `ssot-diagram/graph_model.py` so a
non-coder owner can attach a plain-language sentence to each diagram node, keep each
sentence honestly pinned to the code's content signature, and see at a glance which
sentences are trusted, stale, missing, or orphaned. This step does not build P4 — it
independently re-checks every factual claim the spec makes about the code P4 will sit on
top of, without trusting the spec author's "pre-verified" labels.

**Bottom line for planning: all 15 numbered assumptions hold.** Thirteen (A1–A13) are
directly confirmed against the live code or the golden model. Two (A14, A15) describe how
the *not-yet-written* ingest/approve logic must behave; they cannot be confirmed against
code that does not exist yet, but the mechanism they rely on (a per-node `signature` field
that can be compared) is real and validated. **No assumption is invalidated. Planning is
not blocked.**

Three factual imprecisions were found that do NOT change any verdict but the implementer
must know about them:
1. **The golden model's real sha256 is `56df3d86e564…`, not `5a1e2156…`** as the spec (and
   CLAUDE.md / STATE.md) repeat. The existing P3 test byte-compares against the golden file
   on disk, so nothing is broken — but any new P4 test or doc that hardcodes `5a1e2156…`
   would be wrong. Use `56df3d86…` (or, better, byte-compare the file like P3 does).
2. The spec's note that `load_config` "has 5 `die()` paths" is low — the body has **11**
   `die()` calls. The assumption (A7) still holds: `load_config` DOES die on missing keys.
3. The spec calls `graph_model.py`'s `die` a "local" function distinct from `di.die`. It is
   actually an **alias** — `die = di.die` (`graph_model.py:55`). Same object, same exit 2.

## Key Components

P4 lives entirely inside one already-shipped file and reuses helpers from a sibling module.

- **`ssot-diagram/graph_model.py`** (994 lines) — the P3 extractor. P4 adds new functions
  and a `narrate` subparser group here. Load-bearing existing symbols P4 reuses:
  - `_save_model(path, model)` (`:796`) — the atomic, byte-deterministic JSON writer.
  - `build_parser()` (`:953`) — the argparse entry point P4 hangs `narrate` off.
  - `cmd_extract(args)` (`:810`) — the path-discovery pattern P4 copies for defaults.
  - `load_config(path)` (`:72`) — the STRICT config validator P4 must NOT call.
  - `die` (`:55`) — `die = di.die`, exit 2.
  - `DEFAULT_CONFIG_REL` (`:29`) / `DEFAULT_OUTPUT_REL` (`:30`) / `_sorted_sha256` (`:64`).
- **`ssot-diagram/decision_index.py`** (373 lines) — imported as `di` at
  `graph_model.py:27`. P4 reuses `di.find_db` / `di.repo_root_for` (re-exported from
  `_shared.db` at `decision_index.py:49`) for path discovery, and `di.die` (`:327`) for
  fatal exit.
- **`ssot-diagram/testdata/mkt_engine.model.json`** — the frozen golden P3 model P4's
  index walker is verified against.
- **`manifest.json`** / **`ssot-diagram/ssot-diagram.config.json`** — P4 adds one manifest
  entry and two optional config keys.

## How It Works

When the owner runs a `narrate` subcommand, P4 will (per spec) load `diagram-model.json`,
walk its nested `components → micros → nanos` tree to build a `{node_id: signature}` map,
load `narratives.json` (or treat it as empty), then either report status (`worklist`,
`status`) or apply a decision (`ingest`, `approve`, `reject`). It never opens the codegraph
DB and never reads the decision index. Every write goes through the existing `_save_model`.

The one behavior that is the whole point of the phase — signature pinning — rests on a fact
this verification confirmed: **every component, micro, and nano node in the golden model
carries a `"signature"` hex string** (see A1). Because that field exists, P4 can pin prose
to it at ingest and refuse to "launder" stale prose at approve.

## Spec Verification

Every numbered assumption was re-checked against the actual file (not the spec's labels).
A1/A2/A5/A6/A9/A11 were checked by loading the golden model and reading its real dict keys.
A3/A4/A7/A8/A10/A13 were checked by reading the actual function bodies. A12/A14/A15 are
design prescriptions for code that does not exist yet; A12 is feasibility-confirmed, A14/A15
are marked unverifiable (no code to test) with the mechanism confirmed.

| ID | Spec Claim | Verdict | Evidence |
|----|-----------|---------|----------|
| A1 | component/micro/nano nodes each carry a `"signature"` hex key; collapsed carries one but is out of scope; decisions excluded | Validated | Golden: component keys include `signature`; micro keys include `signature`; nano keys include `signature`; collapsed keys `[collapsed_count,id,kind,name,signature]`; decision keys `[doc,id,kind,name,signature,status]` |
| A2 | Model is NESTED: top-level `components[]`; component `children`=micros; micro `children`=nanos; NO flat arrays; top keys exactly `components,decisions,generated_at,nano_cap,version` | Validated | Golden top keys `['components','decisions','generated_at','nano_cap','version']`; 10 components → 150 micros → 245 nanos all via `children` |
| A3 | `_save_model` is generic: `mkdir`, atomic tmp write `json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False)+"\n"`, `os.replace`; inspects no model-specific keys | Validated | `graph_model.py:796–805` — body references only `model` opaquely; no `model["components"]` etc. |
| A4 | `di.find_db` / `di.repo_root_for` resolvable as module-level names on `decision_index` (re-exported from `_shared.db` at line 49) | Validated | `decision_index.py:49` `from _shared.db import SchemaError, find_db, repo_root_for` |
| A5 | Nano nodes have NO `start_line`/`end_line`; keys exactly `caller_count,decisions,docstring,edges,id,is_exported,kind,name,path,qualified_name,signature` | Validated | Golden nano keys match exactly; no line-number keys |
| A6 | Micro nodes have NO `caller_count`; keys exactly `children,decisions,dominant_class,edges,id,kind,name,path,signature`; fallback must count non-collapsed children | Validated | Golden micro keys match exactly; no `caller_count` |
| A7 | `load_config` calls `die()` (exit 2) on missing `version`/`components`/`default_component`/invalid `nano_cap`, so `narrate` must use a permissive reader instead | Validated (note) | `graph_model.py:82–118` dies on all those keys. NOTE: spec says "5 die() paths"; body actually has **11** `die()` calls — figure is low, verdict unchanged |
| A8 | `build_parser()` uses standard `sub.add_subparsers(dest="cmd", required=True)`, no custom class; a nested `narrate` subparser can be added cleanly | Validated | `graph_model.py:953–976`; `:959` `sub = p.add_subparsers(dest="cmd", required=True)`; existing children use `set_defaults(fn=…)` (matches spec's `narrate` example) |
| A9 | `collapsed` children have `kind == "collapsed"` and keys `collapsed_count,id,kind,name,signature`; exclusion predicate `kind != "collapsed"` | Validated | Golden: 2 collapsed nodes, keys `[collapsed_count,id,kind,name,signature]`, kind literally `"collapsed"` |
| A10 | `di.die` (`decision_index.py:327`) and local `die` (`graph_model.py:55`) both `sys.exit(2)` | Validated (note) | `decision_index.py:327–329` `print("error: …"); sys.exit(2)`. NOTE: `graph_model.py:55` is `die = di.die` — an ALIAS, not a separate "local" definition; same object, exit 2 |
| A11 | Decision nodes keyed `decision:{did}@{cid}` (one per ADR × component); golden 11 nodes / 8 ADRs; excluded from narration | Validated | Golden 11 decision ids; ADR-0001/0003/0007 each appear twice (per component); 8 distinct ADRs ADR-0001…0008 |
| A12 | Permissive reader can `.get()` `narrate_threshold`/`narratives_path` via a direct `json.loads`, without `load_config` | Validated (feasibility) | Config is plain JSON; `load_config` itself does `json.loads(path.read_text())` at `graph_model.py:84`, proving direct JSON load works independent of validation |
| A13 | `_save_model` appends trailing `"\n"` and uses `ensure_ascii=False` | Validated | `graph_model.py:804` `… ensure_ascii=False) + "\n"` |
| A14 | Ingest must skip a FRESH approved entry but WRITE fresh proposed text for an approved-but-stale entry (one-step refresh, no reject dance) | Unverifiable | Prescriptive behavior for `cmd_narrate_ingest`, which does NOT exist yet. Underlying mechanism (signature compare) confirmed via A1; nothing in existing code contradicts it |
| A15 | Approve does NOT re-pin the signature; it flips proposed→approved only if the stored signature still matches, else refuses | Unverifiable | Prescriptive behavior for `cmd_narrate_approve`, which does NOT exist yet. Signature field to compare against is confirmed (A1); no existing code contradicts it |

**Counts: 13 Validated · 0 Invalidated · 2 Unverifiable (A14, A15).**

## Edge Cases & Silent Failure Modes

Plain English: a few real-data quirks the implementer must not trip over.

- **Separator-bar docstrings are real, not hypothetical.** 26 nano docstrings in the golden
  model start with `──`/`----`/`==` bars (e.g. `validatePixelSize` → `"── Validation
  helpers ──"`, `EditTopBar` → `"----"`, `ResizeTool` → `"── Component ──"`). The spec's
  fallback bar-stripping rule (component 3, FM6) is grounded — a fallback that does NOT
  strip bars would emit `"── Validation helpers ──"` as the "sentence."
- **The `store.ts` fixture the spec cites is exactly as claimed.** `micro:lib/canvas/store.ts`
  has 9 children: 8 nanos + 1 collapsed. Non-collapsed count = 8. A fallback using
  `len(children)` would wrongly say "9 function(s)"; the spec's `kind != "collapsed"` count
  gives 8. Confirmed.
- **Index size arithmetic is exact.** 10 components + 150 micros + 245 emitted nanos = 405
  index entries; 2 collapsed + 11 decision nodes excluded. Matches the spec's component-2
  "done when" (405) precisely.
- **`load_config` is a landmine if reused.** It dies on a config that merely omits
  `version`/`components`/`default_component`. A read-only `narrate status` on today's config
  would abort if it called `load_config`. The permissive reader (component 1) is mandatory,
  not optional — A7/A12 both confirm this.

## Dependencies & Coupling

- P4 is coupled to the P3 model schema. If a future P3 change drops the `signature` key on
  any node kind, P4's index builder (spec component 2) is designed to die at startup (FM3).
  That coupling is intentional and asserted, not silent.
- P4 reuses `decision_index as di` for path discovery ONLY (`di.find_db`, `di.repo_root_for`).
  It does NOT use `di.open_db` / `di.current_sig` / `di.load_index` — confirmed those exist
  (`decision_index.py:72/97/124`) but are outside P4's stated boundary.
- The manifest entry shape is `{script, scope, desc, hooks}` (confirmed on the existing
  `diagram-model` entry). P4's `narrative-sidecar` entry sharing the same `graph_model.py`
  script with `hooks: []` is consistent with the existing `diagram-model` entry (also
  `hooks: []`).

## Extension Points

- New subcommands hang cleanly off `build_parser()` because it uses stock argparse
  subparsers and a `set_defaults(fn=…)` dispatch via `main()` → `args.fn(args)`
  (`graph_model.py:988–990`). The `narrate` group can nest its own subparsers without
  touching `extract` / `bootstrap-config`.
- The writer (`_save_model`) is fully generic, so `narratives.json` needs no new writer —
  confirmed (A3).
- The two new config keys are additive and optional; existing configs (which lack them)
  keep working via `.get()` defaults. Confirmed the shipped config has neither key today.

## Open Questions

- **A14 / A15 runtime behavior (ingest skip-fresh / approve refuse-drift)** cannot be
  verified until the code is written — they are the spec's own prescriptions for functions
  that do not exist yet. What was checked: the signature field they depend on is present on
  every node (A1), and no existing code contradicts the intended behavior. These move from
  "unverifiable" to "test-enforced" once P4's `cmd_narrate_ingest` / `cmd_narrate_approve`
  and tests T4/T5/T6 exist. Not a blocker — flagged so the planner knows T4–T6 are the
  only place these get real teeth.

## Technical Debt Spotted

- **Stale golden sha256 in three docs.** `spec`, `CLAUDE.md:41`, and `STATE.md:39/66/123`
  all cite golden sha256 `5a1e2156…`. The on-disk golden is `56df3d86e5642c6b93…`. The P3
  test (`test_golden_byte_match`, `test_graph_model.py:367–386`) byte-compares against the
  file, so no test fails today — but the docs are wrong and a new P4 test that hardcodes
  `5a1e2156…` would fail. Recommend the P4 work either byte-compare the file (like P3) or
  use the correct current hash. This is documentation drift, not a code defect.
- **"5 die() paths" undercount** in the spec's A7 note — `load_config` has 11 `die()` calls.
  Harmless (verdict unchanged) but worth correcting if the spec is edited.

## Human-Authority Items (not assumed by this verification)

- **`narrate_threshold` default = 4 (operating burden).** The spec does NOT silently assume
  this — it explicitly records the value as owner-ratified in the design revision log and
  config-tunable. No re-approval needed at build. Noted, not flagged.
- **OQ-MANIFEST-1 (product identity).** Separate `narrative-sidecar` manifest key vs
  extending `diagram-model`'s desc — explicitly resolved by owner 2026-07-06 (separate key).
  Confirmed the manifest currently has NO `narrative-sidecar` entry, so P4 adds it as
  specified. Noted, not flagged.

## Invalidated Assumptions

None. All 15 numbered assumptions hold (13 validated against live code/golden, 2
unverifiable-but-mechanism-sound). No redesign required; no Q4 conflict diagram needed.
Ready for `/plan p4-narrative-sidecar`, subject to the implementer using the correct golden
sha256 (`56df3d86…`) and not reusing the strict `load_config`.
