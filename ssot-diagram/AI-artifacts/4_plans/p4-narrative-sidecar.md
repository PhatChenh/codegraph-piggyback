# Plan: P4 — Narrative Sidecar (`narrate` subcommands on `graph_model.py`)
_Last updated: 2026-07-06_
_Status: [ ] pending_

## Analysis

P4 gives a non-coder owner a plain-language sentence for every box the diagram
already shows (each component, file, and function), and keeps those sentences
honest: each one is pinned to the code's content signature, so the moment the
code changes the sentence is visibly marked stale instead of silently trusted.
It is the only layer in the whole ssot-diagram stack where an LLM writes a
sentence and a human signs it off; everything below it is deterministic.

This build adds **no new Python file and no hook events**. It is five new
`narrate` subcommands bolted onto the existing extractor
(`ssot-diagram/graph_model.py`), one new output file (`narratives.json`), two new
optional config keys, one new manifest entry, and new tests. Spec:
`ai-artifacts/2_specs/p4-narrative-sidecar.md` (components 1–12 — this plan owns
HOW, the spec owns WHAT). Verification:
`ai-artifacts/3_factual-code-verification/p4-narrative-sidecar.md` (13 validated,
2 unverifiable-but-sound, 0 invalidated).

What this build connects to and why:

- **Sits entirely on top of P3's output** (`diagram-model.json`) — it never opens
  the codegraph DB and never reads the decision index. The whole job is: read the
  model, read `narratives.json` (or treat it as empty), and either report what
  needs doing (`worklist`, `status`) or apply a human/LLM decision (`ingest`,
  `approve`, `reject`).
- **Reuses P3/P1 helpers by sibling import, not by re-writing them.** The atomic
  byte-deterministic writer `_save_model` (`graph_model.py:796`) is generic
  (verified A3) and is reused verbatim to write `narratives.json`. Path discovery
  reuses `di.find_db` / `di.repo_root_for` (re-exported on `decision_index` at
  `decision_index.py:49`, imported as `di` at `graph_model.py:27`). Fatal exit
  reuses `die` (`graph_model.py:55`, which the FCV confirms is the alias
  `die = di.die`, exit 2 — not a separate local function).
- **Must NOT reuse the strict config validator.** `load_config`
  (`graph_model.py:72`) calls `die()` on any config missing `version` /
  `components` / `default_component` (FCV counted 11 `die()` paths). A read-only
  `narrate status` on a minimal config would abort. P4 therefore ships its own
  permissive `.get()`-based reader (`_load_narrate_config`) and leaves
  `load_config`'s 8 existing callers untouched.
- **Honours the FROZEN contracts.** Block 5a fixes the on-disk entry shape to
  exactly `{node_id, signature, text, status}` with `status` ∈ `{proposed,
  approved}` — `stale` is NEVER written; it is a derived display state computed
  live by comparing the stored signature to the current model node's signature.
  Block 5b is the trust rule: nothing counts as trusted prose unless
  `status == approved` AND the stored signature still matches. Block 4a/4b fix
  the nested `components[].children` (micros) `.children` (nanos) shape the sig
  index walks, and the per-node `signature` field prose pins to.

Why this approach, not another: the signature-pinning contract is the entire
point of the phase — it is what lets an LLM draft prose without the owner having
to trust it blindly. Two design invariants make it safe and are load-bearing
throughout the steps below: (1) **staleness is never stored** (F1 fix — a stored
badge is a write-side-effect of a read and can itself go stale; derive it live),
and (2) **approve never re-pins the signature** (F6 fix — re-pinning would let old
text be laundered into fresh-looking `approved` status while still describing old
code). Ingest is the ONLY command that pins a signature.

## Files
- `ssot-diagram/graph_model.py` — add module constants (`DEFAULT_NARRATE_THRESHOLD`,
  `DEFAULT_NARRATIVES_REL`), the permissive config reader (`_load_narrate_config`),
  the model loader + sig-index builder (`_load_model`, `_build_sig_index`), the
  fallback-text function (`_fallback_text` + `_first_sentence` helper), the narrate
  shared internals (`_narrate_root_paths`, `_load_narratives`, `_write_narratives`,
  `_compute_scope`, `_derive_status`), the five subcommand functions
  (`cmd_narrate_worklist`, `cmd_narrate_ingest`, `cmd_narrate_approve`,
  `cmd_narrate_reject`, `cmd_narrate_status`), and the `narrate` subparser group in
  `build_parser`. No existing symbol's behavior changes.
- `ssot-diagram/ssot-diagram.config.json` — add two optional keys
  (`narrate_threshold: 4`, `narratives_path: "ssot-diagram/narratives.json"`);
  version stays 1.
- `manifest.json` — add a `narrative-sidecar` entry under `scripts` (same
  `graph_model.py` script, `scope: repo`, `hooks: []`).
- `ssot-diagram/test_graph_model.py` — extend with P4 tests T1–T11 (beside the
  code, matching P3's convention).
- `ssot-diagram/narratives.json` — NEW output file, created at runtime by `ingest`
  (not committed by this plan; created only when the tool runs).

## Delegation Authority
Plain-English: the implementer may edit only the four files listed in ## Files.
Everything else — especially the frozen contracts, the golden model, and the P3
extract behavior — is off-limits and must stay byte-for-byte unchanged.

- **Allowed set** = exactly the four files in ## Files
  (`ssot-diagram/graph_model.py`, `ssot-diagram/ssot-diagram.config.json`,
  `manifest.json`, `ssot-diagram/test_graph_model.py`) plus the runtime-created
  `ssot-diagram/narratives.json`. Nothing outside it.
- A file in ## Files assigned to another Step is a dependency (follow
  ## Implementation Order), not a deviation.
- A file NOT in ## Files → STOP, do not silently edit. Record it in an
  `### Out-of-scope touches` block of the end-of-implementation report: the file,
  why the Step needed it, the change, and whether it signals a plan/spec gap.
- **Hard off-limits (escalate before touching):**
  - `../docs/roadmap/skeleton-contracts.md` — FROZEN contracts (Block 4a/4b, 5a,
    5b). P4 conforms to them; it does not amend them.
  - `ssot-diagram/testdata/mkt_engine.model.json` — the frozen P3 golden. P4 must
    NOT regenerate or mutate it. The regression test byte-compares against it
    (real sha256 `56df3d86…`, NOT the stale `5a1e2156…` in the spec/CLAUDE.md).
  - Existing symbols in `graph_model.py`: `_save_model`, `load_config`,
    `cmd_extract`, `cmd_bootstrap_config`, `bootstrap_config`, `_verify_model_schema`,
    and all P3 `_build_*` / `_roll_up_*` helpers — reuse `_save_model` and the
    `cmd_extract` path-discovery pattern, but do not change their signatures or
    bodies. The `extract` and `bootstrap-config` subparsers must stay unchanged.
  - `ssot-diagram/decision_index.py` (`di`) — sibling import, read-only reuse of
    `find_db` / `repo_root_for` / `die` ONLY. Do not use `di.open_db`,
    `di.current_sig`, or `di.load_index`, and do not edit the module.
  - `.codegraph/codegraph.db` — never opened by P4, never written.
  - `CLAUDE.md`, `STATE.md`, `ssot-diagram/CLAUDE.md`, roadmap docs — doc-sync is
    the pipeline-end job, not the implementer's. (The orchestrator owns the STATE.md
    write for this plan.)

## Rules Applied
No `--- WRIT RULES ---` block was injected into this planning session, so no rule
IDs are cited. The governing constraints are the project's own FROZEN contracts and
CLAUDE.md rules, enforced through ## Delegation Authority and the per-Step
`<!-- plan-verify -->` manifests rather than Writ rule IDs:
- Block 5a / 5b / 4a / 4b (`docs/roadmap/skeleton-contracts.md`) — entry shape,
  trust rule, nested model, per-node signature.
- Repo `CLAUDE.md` Critical Rules — read-only DB, manifest entry required, stdlib
  only, content-signature pinning.
- `ssot-diagram/CLAUDE.md` — sibling import (defer `_shared/`), byte-deterministic
  writer, Phase/Step naming.

## Capabilities
- [ ] C1 — A missing or minimal config never crashes a read-only `narrate` command:
  `narrate status` on an absent/threshold-less config exits 0 and prints.
- [ ] C2 — `narrate_threshold` is honored from config (e.g. `7` widens the
  non-exported-nano scope to `caller_count >= 7`); absent key defaults to 4.
- [ ] C3 — A config that is present but not a JSON object dies with exit 2 and a
  clear message.
- [ ] C4 — The id→signature index over the golden model has exactly 405 entries
  (10 components + 150 micros + 245 emitted nanos), no `None` value, and excludes
  all 2 collapsed and all 11 decision nodes.
- [ ] C5 — A model node missing a `signature` key makes the index builder die at
  startup naming the node (schema-drift guard).
- [ ] C6 — `_fallback_text` returns a non-empty, plain-language sentence for every
  narratable kind, strips separator-bar docstrings, ends at the first sentence
  boundary (or ≤70 chars if no period), counts non-collapsed children for
  micro/component, and never raises on a real-model node.
- [ ] C7 — `narrate worklist` on the golden + empty narratives emits exactly the
  in-scope nodes (all components + micros + threshold/export nanos), no
  collapsed/decision ids, each item `{node_id, kind, name, current_signature,
  fallback_text, text: ""}`; `--include-nanos` widens to all visible nanos;
  `--node <decision|collapsed id>` is rejected with exit 2.
- [ ] C8 — `narrate ingest` validates the whole batch first (required keys, node
  exists, signature matches current model), writes nothing on any error, pins the
  signature at ingest, writes accepted entries as `status: proposed`, and skips a
  FRESH approved entry without overwriting it.
- [ ] C9 — `narrate ingest` writes fresh proposed text for an approved-but-stale
  entry (one-step refresh, no reject dance).
- [ ] C10 — `narrate approve <id>` flips proposed→approved only when the stored
  signature still matches the current model; it REFUSES a drifted entry with exit 2
  and never re-pins the signature or changes the text (laundering hole closed).
- [ ] C11 — `narrate reject <id>` removes entries and fails loud (exit 2, no write)
  on an unknown id.
- [ ] C12 — `narrate status` reports every stored entry UNION every in-scope
  unnarrated node, each with a DERIVED status (`none`/`proposed`/`approved`/`stale`/
  `orphaned`), shows `stale` for a drifted approved entry, shows `orphaned` for a
  vanished node, still watches an `--include-nanos` entry now below threshold, never
  writes the file, and exits 0.
- [ ] C13 — `narratives.json` is byte-deterministic: two identical ingest runs
  produce byte-identical files (sha256 equal), keys sorted, trailing `\n`,
  `ensure_ascii=False`, no `generated_at` field, and the literal string `stale`
  appears nowhere in the file.
- [ ] C14 — `python3 graph_model.py narrate --help` lists all five subcommands;
  `narrate` with no subcommand exits 2 (argparse `required=True`); `extract` and
  `bootstrap-config` are unchanged.
- [ ] C15 — `piggyback status` lists the `narrative-sidecar` tool; a config with
  the two new keys is read correctly; a config without them still works.
- [ ] C16 — No regression: `graph_model.py extract` still produces the
  byte-identical golden (`56df3d86…`), `decision_index status` still exits 0, and
  `python3 -m pytest ssot-diagram/` is green (existing 32 + new P4 tests).

## Implementation Order
Plain-English: the four foundation helpers (config reader, model+index, fallback
text, narrate internals) come first and are independent of each other, so they can
be built in parallel. The five subcommands each depend on some subset of those
helpers and can then be built in parallel with one another (they all live in the
same file, so in practice they are written sequentially to avoid edit churn, but
they have no logical dependency among themselves). CLI wiring depends on all five
subcommand functions existing. Config-seed + manifest depend only on the config
reader (Step 1) knowing the key names. Tests come last but each Step also carries
its own unit-test criteria.

Dependency facts derived from codegraph on the touched symbols:
- `build_parser` (`graph_model.py:953`) has 2 callers inside `graph_model.py`
  (`main` at `:989`, plus test coverage in `test_graph_model.py`). Editing it to
  add the `narrate` group requires every `cmd_narrate_*` function to exist first —
  hence Step 10 depends on Steps 5–9.
- `main` (`:989`) dispatches via `args.fn(args)` (`set_defaults(fn=…)`), so each
  subcommand only needs to be reachable through `build_parser`; no change to `main`.
- `_save_model` (`:796`) is generic (FCV A3) — reused by the writer wrapper
  (Step 4) and thus by ingest/approve/reject (Steps 6–8).
- `load_config` (`:72`) has 8 callers today; P4 adds ZERO — the permissive reader
  is separate, so no blast radius on `load_config`.

**Dependency table:**
| Step | Produces | Depends on | Why (codegraph fact) |
|---|---|---|---|
| 1 | `_load_narrate_config` + constants | — | none (first) |
| 2 | `_load_model`, `_build_sig_index` | — | none |
| 3 | `_fallback_text`, `_first_sentence` | — | pure function, none |
| 4 | narrate internals (`_narrate_root_paths`, `_load_narratives`, `_write_narratives`, `_compute_scope`, `_derive_status`) | 1, 2 | `_write_narratives` wraps `_save_model` (`:796`); `_compute_scope` walks the index from Step 2; path helper mirrors `cmd_extract` (`:810`) discovery |
| 5 | `cmd_narrate_worklist` | 1,2,3,4 | needs config, index, fallback, scope+derive |
| 6 | `cmd_narrate_ingest` | 1,2,4 | needs config, index, writer wrapper |
| 7 | `cmd_narrate_approve` | 1,2,4 | needs config, index, writer wrapper |
| 8 | `cmd_narrate_reject` | 1,4 | needs config + narratives load/write only (no index) |
| 9 | `cmd_narrate_status` | 1,2,4 | needs config, index, scope+derive |
| 10 | `narrate` subparser in `build_parser` | 5,6,7,8,9 | `set_defaults(fn=cmd_narrate_*)` references all five functions |
| 11 | config keys + manifest entry | 1 | key names owned by Step 1's reader |
| 12 | tests T1–T11 | 1–11 | tests exercise the finished commands + regression |

**Parallel waves** (steps in a wave touch disjoint symbols within the one shared
file — safe to develop in parallel; if one implementer owns the file, serialize in
wave order):
- Wave A (no deps): Step 1, Step 2, Step 3.
- Wave B (after A): Step 4.
- Wave C (after B): Step 5, Step 6, Step 7, Step 8, Step 9 (independent of each
  other), and Step 11 (independent — needs only Step 1's key names).
- Wave D (after C's subcommands): Step 10 (CLI wiring).
- Wave E (after all): Step 12 (tests + full-suite regression).

**Critical path:** Step 1/2 → Step 4 → Step 5–9 → Step 10 → Step 12. Solo linear
order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12.

## Implementer Notes (weak-model — read before Step 1)

This section removes the guesswork the prose Steps leave to a strong implementer.
Copy these signatures and skeletons verbatim; fill the bodies the Steps describe.
Everything here is verified against the live code (`graph_model.py`) and the golden
model (`testdata/mkt_engine.model.json`) as of 2026-07-06.

**1. Exact node field names (verified against the golden — do NOT guess).**
- component/micro dict: `id, kind, name, path, signature, children, edges, decisions`
  (micro also has `dominant_class`). `kind` is `"component"` / `"file"`.
- nano dict: `id, kind, name, qualified_name, path, signature, caller_count,
  is_exported, docstring, edges, decisions`. `kind` is `"function"` (or `"method"`).
- collapsed placeholder (lives inside a micro's `children`):
  `{id, kind:"collapsed", name, signature, collapsed_count}` — NO `caller_count` /
  `docstring` / `is_exported`. Exclude it everywhere by `kind == "collapsed"`.
- decisions are under top-level `model["decisions"]` (a dict), NEVER under
  `components[].children`. Every node ALSO has a per-node `decisions` LIST field —
  that is a reference list, not a child node; never index it.

**2. Serialization is one function — never hand-roll `json.dumps`.** Write every
persisted file through the existing `_save_model` (`graph_model.py:796`), whose body
is exactly:
```python
tmp.write_text(json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
os.replace(tmp, path)
```
- `narratives.json`: `_write_narratives` calls `_save_model(path, {"narratives": entries})`.
  Because `_save_model` already sorts keys, do NOT add your own sort — that is the F2 fix.
- `narrate worklist` output (an ARRAY, not the narratives file) → use the SAME params:
  `json.dumps(items, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` to `-o`
  file or stdout. This is what "match the writer's serialization" means in Step 5.

**3. `_derive_status` — branch ORDER is load-bearing (Step 4).** Check `None`
BEFORE comparing signatures, or a vanished node is mislabeled `stale`:
```python
def _derive_status(stored_entry: dict | None, current_sig: str | None) -> str:
    if stored_entry is None:            # nothing stored for this node
        return "none"
    if current_sig is None:             # node vanished from the model — check FIRST
        return "orphaned"
    if stored_entry["signature"] != current_sig:
        return "stale"                  # drifted; never a stored value, only derived
    return stored_entry["status"]       # "approved" or "proposed"
```

**4. `_first_sentence` — keep the `─` (U+2500) intact (Step 3).** It sits in a raw
string (`r"..."`), so a `─` escape would NOT work here (raw strings don't decode
`\u`) — copy the literal `─` as-is. Skeleton:
```python
import re
_SEP_LINE = re.compile(r"^\s*[-─=]+\s*$")   # matches a line of ─ (U+2500), -, or =
def _first_sentence(docstring: str) -> str:
    lines = (docstring or "").split("\n")
    while lines and _SEP_LINE.match(lines[0]):    # strip leading separator bars
        lines.pop(0)
    text = " ".join(s.strip() for s in lines).strip()
    if not text:
        return ""
    m = re.search(r"\.(\s|$)", text)              # first period + space/newline/end
    return text[: m.start() + 1] if m else text[:70]
```

**5. Function signature index — all 15 (+2 constants). Copy verbatim:**
```python
DEFAULT_NARRATE_THRESHOLD = 4
DEFAULT_NARRATIVES_REL = "ssot-diagram/narratives.json"

def _load_narrate_config(config_path: Path) -> tuple[int, str]: ...     # Step 1
def _load_model(model_path: Path) -> dict: ...                          # Step 2
def _build_sig_index(model: dict) -> dict[str, str]: ...                # Step 2
def _first_sentence(docstring: str) -> str: ...                        # Step 3
def _fallback_text(node: dict) -> str: ...                             # Step 3
def _narrate_root_paths(args) -> tuple[Path, Path, Path]: ...          # Step 4 -> (model, config, narratives)
def _load_narratives(narratives_path: Path) -> dict[str, dict]: ...    # Step 4
def _write_narratives(narratives_path: Path, entries: dict) -> None: ... # Step 4
def _compute_scope(model: dict, sig_index: dict, threshold: int, *,
                   include_nanos: bool = False, extra_node: str | None = None) -> list[str]: ...  # Step 4
def _derive_status(stored_entry: dict | None, current_sig: str | None) -> str: ...  # Step 4 (see note 3)
def cmd_narrate_worklist(args) -> None: ...                            # Step 5
def cmd_narrate_ingest(args) -> None: ...                              # Step 6
def cmd_narrate_approve(args) -> None: ...                             # Step 7
def cmd_narrate_reject(args) -> None: ...                              # Step 8
def cmd_narrate_status(args) -> None: ...                              # Step 9
```
`_narrate_root_paths` resolves in this order: `root = di.repo_root_for(di.find_db(Path.cwd()) or die(...))`;
`config = Path(args.config) if args.config else root / DEFAULT_CONFIG_REL`; read
`(threshold, narratives_rel) = _load_narrate_config(config)`; `narratives =
Path(args.narratives) if args.narratives else root / narratives_rel`; `model =
Path(args.model) if args.model else root / DEFAULT_OUTPUT_REL`; return
`(model, config, narratives)`.

**6. argparse block for Step 10 — matches the existing `extract`/`bootstrap-config`
pattern (`main` dispatches via `args.fn(args)`). Insert before `return p` in
`build_parser` (`graph_model.py:953`):**
```python
    pn = sub.add_parser("narrate", help="plain-language sidecar for diagram nodes")
    nsub = pn.add_subparsers(dest="narrate_cmd", required=True)

    def _common(sp):
        sp.add_argument("--model", help=f"diagram-model.json (default: <root>/{DEFAULT_OUTPUT_REL})")
        sp.add_argument("--narratives", help="narratives.json (default: config narratives_path)")
        sp.add_argument("--config", help=f"config (default: <root>/{DEFAULT_CONFIG_REL})")

    pw = nsub.add_parser("worklist", help="list nodes needing a sentence"); _common(pw)
    pw.add_argument("--include-nanos", action="store_true")
    pw.add_argument("--node", help="restrict to one node id")
    pw.add_argument("-o", "--out", help="write JSON array here (default: stdout)")
    pw.set_defaults(fn=cmd_narrate_worklist)

    pi = nsub.add_parser("ingest", help="load a filled worklist file"); _common(pi)
    pi.add_argument("file", help="filled worklist JSON file")
    pi.set_defaults(fn=cmd_narrate_ingest)

    pa = nsub.add_parser("approve", help="approve proposed entries"); _common(pa)
    pa.add_argument("ids", nargs="+", help="node id(s)")
    pa.set_defaults(fn=cmd_narrate_approve)

    prj = nsub.add_parser("reject", help="remove entries"); _common(prj)
    prj.add_argument("ids", nargs="+", help="node id(s)")
    prj.set_defaults(fn=cmd_narrate_reject)

    ps = nsub.add_parser("status", help="show derived status of every node"); _common(ps)
    ps.add_argument("--include-nanos", action="store_true")
    ps.set_defaults(fn=cmd_narrate_status)
```

**7. Test fixtures (Step 12 + per-Step unit tests).** `test_graph_model.py` already
has helpers — REUSE them, do not invent a harness:
- `GOLDEN` (module constant) = the golden model path; `json.load(open(GOLDEN))` gives
  the real nested model for integration tests (worklist/status counts, index size 405).
- DB-based helpers `_synthetic_db()`, `_add_file/_add_node/_add_edge`, `_write_config`,
  `_minimal_config(tmp_path)` build a tiny repo and run `extract` — use these only if
  you need a real end-to-end model.
- For UNIT tests of `_build_sig_index` / `_fallback_text` / `_derive_status`, build a
  MODEL DICT LITERAL directly (faster, no DB). Minimal shape:
```python
def _mini_model():
    nano = {"id": "nano:x/a.ts#foo", "kind": "function", "name": "foo",
            "qualified_name": "foo", "path": "x/a.ts", "signature": "n1",
            "caller_count": 9, "is_exported": True, "docstring": "Does a thing. More.",
            "edges": [], "decisions": []}
    micro = {"id": "micro:x/a.ts", "kind": "file", "name": "a.ts", "path": "x/a.ts",
             "signature": "m1", "dominant_class": None, "edges": [], "decisions": [],
             "children": [nano]}
    comp = {"id": "comp:x", "kind": "component", "name": "X", "path": "x",
            "signature": "c1", "edges": [], "decisions": [], "children": [micro]}
    return {"version": 1, "nano_cap": 8, "generated_at": None,
            "decisions": {}, "components": [comp]}
```
  Mutate `nano["signature"]` to a new value to simulate drift; delete `"signature"`
  from a node to test the schema-drift `die`; add `{"kind":"collapsed", ...}` to a
  micro's `children` to test collapsed exclusion.

## Steps

### Step 1 — Permissive config reader + default constants
**Goal**: Read the two new config knobs without ever aborting on a minimal or
absent config. Implements spec component 1.

**Design**:
Today the only config reader is `load_config`, which dies if the config omits
`version` / `components` / `default_component`. A read-only `narrate status` on a
bare config would therefore crash before printing. This Step adds a separate,
permissive reader that loads the JSON itself and uses `.get()` with defaults, so
missing keys are fine — but a config that is present yet not a JSON object is a
corrupt file and still dies with exit 2.

**Actions**:
1. Add module-level constant `DEFAULT_NARRATE_THRESHOLD = 4` (owner-ratified value
   — no re-approval needed).
2. Add module-level constant `DEFAULT_NARRATIVES_REL = "ssot-diagram/narratives.json"`
   (sibling of `DEFAULT_OUTPUT_REL`).
3. Add `_load_narrate_config(config_path: Path) -> tuple[int, str]` returning
   `(threshold, narratives_rel)`: if the file is absent →
   `(DEFAULT_NARRATE_THRESHOLD, DEFAULT_NARRATIVES_REL)`; if present, `json.loads`
   it directly (NOT `load_config`), `warn`-and-default on `JSONDecodeError`, `die`
   (exit 2) if the parsed value is not a dict, else return
   `.get("narrate_threshold", DEFAULT_NARRATE_THRESHOLD)` and
   `.get("narratives_path", DEFAULT_NARRATIVES_REL)`.

**Files to modify**:
- `ssot-diagram/graph_model.py` — add two constants + `_load_narrate_config`.

<!-- plan-verify
touch: ssot-diagram/graph_model.py::DEFAULT_OUTPUT_REL
new:   ssot-diagram/graph_model.py::_load_narrate_config
tier:  A
-->

**Test criteria** (added to `test_graph_model.py`):
- [ ] Absent config → returns `(4, "ssot-diagram/narratives.json")`, no raise.
- [ ] Config with `narrate_threshold: 7` → returns `7`.
- [ ] Config with no `narrate_threshold` key → returns `4`.
- [ ] Config that is a JSON array (not object) → `SystemExit` code 2.
- [ ] Malformed-JSON config → warns and returns defaults (no exit).

**Status**: [ ] pending

---

### Step 2 — Model loader + id→signature index builder
**Goal**: Load `diagram-model.json` once and build the complete `{node_id:
signature}` map every narrate command uses. Implements spec component 2.

**Design**:
The model is the nested Block-4a shape: one top-level `components` array, each with
`children` (micros), each with `children` (nanos). This Step walks exactly that
shape and records every non-collapsed node's signature, dying at startup if any
node lacks one (schema-drift guard) — so a future P3 change that drops `signature`
is caught before any read or write, not silently turned into false staleness.
Collapsed children (`kind == "collapsed"`) and decision nodes (which live under
`model["decisions"]`, never under `components[].children`) are excluded.

**Actions**:
1. Add `_load_model(model_path: Path) -> dict`: open + `json.loads`; on
   `FileNotFoundError` or `JSONDecodeError`, `die` (exit 2) with
   `"diagram-model.json not found — run graph_model.py extract first"`.
2. Add `_build_sig_index(model: dict) -> dict[str, str]`: iterate
   `model["components"]`; for each component, its micros (`component["children"]`),
   and each micro's nanos (`micro["children"]`), skip children with
   `kind == "collapsed"`, `die` if `"signature"` absent on any indexed node (name
   the node id), and record `id → signature`. Do NOT walk `model["decisions"]`.

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `_load_model` + `_build_sig_index`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::_load_model
new:   ssot-diagram/graph_model.py::_build_sig_index
tier:  B
-->

**Test criteria** (T1):
- [ ] Golden model → index has exactly 405 entries.
- [ ] No collapsed id (2 excluded) and no decision id (11 excluded) in the index.
- [ ] No value is `None`.
- [ ] A synthetic model with a nano missing `signature` → `SystemExit` code 2,
  message names the node.
- [ ] `_load_model` on a nonexistent path → `SystemExit` code 2.

**Status**: [ ] pending

---

### Step 3 — Deterministic fallback text
**Goal**: A pure function giving a non-empty plain-language sentence for every
narratable node, from model fields only (no DB). Implements spec component 3.

**Design**:
Before any human approves a sentence, and whenever no entry exists, the diagram
still needs readable prose. This Step derives it from the node's own fields. Nanos
show name + "function" + caller count + the first sentence of the docstring — with
the very real separator-bar prefixes (`──` / `----` / `==`; 26 such docstrings in
the golden per FCV) stripped first. Micros and components count their
NON-collapsed children (using `len(children)` would miscount the collapsed
placeholder as a real function — the `store.ts` case must read 8, not 9).

**Actions**:
1. Add `_first_sentence(docstring: str) -> str`: strip leading lines matching
   `^\s*[-─=]+\s*$`; take remaining text up to the first period followed by space /
   newline / end; if no period, take the first 70 cleaned characters (FM6). Return
   `""` if nothing remains.
2. Add `_fallback_text(node: dict) -> str`:
   - nano → `"<name> — function, <caller_count> caller(s)."` plus
     ` <first_sentence>` appended only when non-empty.
   - micro → `"<name> — file, <N> function(s)."` where N = children with
     `kind != "collapsed"`.
   - component → `"<name> — component, <N> file(s)."` where N = children with
     `kind != "collapsed"`.
   - decision / collapsed → `raise ValueError` (programmer error; scope predicate
     should have excluded it).

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `_first_sentence` + `_fallback_text`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::_fallback_text
new:   ssot-diagram/graph_model.py::_first_sentence
tier:  A
-->

**Test criteria** (T2):
- [ ] Nano with a normal docstring ends at the first sentence boundary.
- [ ] Nano with a separator-bar docstring (fixture shaped like `validatePixelSize`
  / `EditTopBar` / `ResizeTool`) has the bars stripped, no `──` in output.
- [ ] Nano with no docstring → `"<name> — function, <N> caller(s)."`, no trailing
  docstring clause.
- [ ] Nano with a no-period docstring → non-empty, ≤70-char clause, never raises.
- [ ] `micro:lib/canvas/store.ts` (8 nanos + 1 collapsed) → `"8 function(s)"`,
  not 9.
- [ ] Component counts non-collapsed child micros.
- [ ] Called on a decision/collapsed node → `ValueError`.
- [ ] No fallback over any real-model node is empty or raises.

**Status**: [ ] pending

---

### Step 4 — Narrate shared internals (paths, load/write, scope, derived status)
**Goal**: The reusable plumbing every subcommand needs — path defaults, the
narratives load/write pair, scope computation, and the live derived-status
function. Implements spec component 10 (writer/format) + the shared scope/derive
logic referenced by spec components 4 and 8.

**Design**:
Each subcommand resolves the same default paths (mirroring `cmd_extract`'s
`di.find_db` → `di.repo_root_for` discovery), loads `narratives.json` (absent →
empty), and writes it back through the generic `_save_model` under a single
`{"narratives": {...}}` top-level key (mirrors `decision_index.py`'s
`{"decisions": {...}}`). Because `_save_model` already sorts keys, no separate sort
step exists (F2 fix). Scope and derived status are the two pieces of shared logic
worklist and status both need, so they live here once. **Derived status is computed
live and NEVER written** — `stale` is a display state, never an on-disk value
(Block 5a / F1 fix).

**Actions**:
1. Add `_narrate_root_paths(args) -> tuple[Path, Path, Path]` (or equivalent):
   resolve repo root via `di.find_db(Path.cwd())` (die if none) →
   `di.repo_root_for`; derive `--model` default `root / DEFAULT_OUTPUT_REL`,
   `--config` default `root / DEFAULT_CONFIG_REL`, `--narratives` default
   `root / <narratives_rel from _load_narrate_config>`. Honor explicit flags when
   present.
2. Add `_load_narratives(narratives_path: Path) -> dict[str, dict]`: read the
   `{"narratives": {...}}` file; absent → `{}`; malformed → `die` (exit 2).
3. Add `_write_narratives(narratives_path: Path, entries: dict) -> None`: call
   `_save_model(narratives_path, {"narratives": entries})` — reuse, no new writer.
4. Add `_compute_scope(model, sig_index, threshold, *, include_nanos=False,
   extra_node=None) -> list[str]`: every component id + every micro id + every
   emitted nano id where `is_exported OR caller_count >= threshold`; collapsed +
   decision excluded; `include_nanos` widens to all visible nanos; `extra_node`
   adds one named node (reject a decision/collapsed id with exit 2).
5. Add `_derive_status(stored_entry: dict | None, current_sig: str | None) -> str`
   returning `approved` / `proposed` / `stale` / `orphaned` / `none` per the Block
   5a derivation table (spec component 8).

**Files to modify**:
- `ssot-diagram/graph_model.py` — add the five internal helpers above.

<!-- plan-verify
touch: ssot-diagram/graph_model.py::_save_model
new:   ssot-diagram/graph_model.py::_load_narratives
new:   ssot-diagram/graph_model.py::_write_narratives
new:   ssot-diagram/graph_model.py::_compute_scope
new:   ssot-diagram/graph_model.py::_derive_status
new:   ssot-diagram/graph_model.py::_narrate_root_paths
tier:  B
qualifiers: grep-absent "\"stale\"" ssot-diagram/graph_model.py
-->

**Test criteria** (unit-level; fuller coverage in Steps 5/9):
- [ ] `_derive_status`: matching-sig approved → `approved`; matching-sig proposed →
  `proposed`; mismatched-sig (either) → `stale`; `current_sig is None` (node gone)
  → `orphaned`; no stored entry → `none`.
- [ ] `_write_narratives` round-trips through `_load_narratives` unchanged.
- [ ] `_compute_scope` on the golden excludes every collapsed + decision id.
- [ ] The literal `"stale"` never appears as a written status value (grep the
  writer path).

**Status**: [ ] pending

---

### Step 5 — `narrate worklist` subcommand
**Goal**: Emit a JSON array of nodes needing a human sentence — every in-scope node
with no entry (`none`) or a drifted signature (`stale`). Implements spec component 4.

**Design**:
The owner runs this, gets one object per node that needs prose, pastes it into an
LLM, the LLM fills the blank `text` fields, and the owner saves the file for
`ingest`. A stale approved node IS emitted (A14) — it needs fresh text. Fresh
approved and fresh proposed nodes are NOT emitted (nothing to do).

**Actions**:
1. Resolve paths (Step 4 helper); read config (Step 1); load model + build index
   (Step 2); load narratives (Step 4).
2. Compute scope (Step 4), honoring `--include-nanos` and `--node`.
3. For each scoped node, derive status (Step 4); emit a worklist item ONLY for
   `none` and `stale`. Item = `{node_id, kind, name, current_signature,
   fallback_text (Step 3), text: ""}`.
4. Write the JSON array to `-o <file>` or stdout, pretty-printed 2-space indent +
   trailing newline (match the writer's serialization so round-trip is clean).

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `cmd_narrate_worklist`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::cmd_narrate_worklist
tier:  B
-->

**Test criteria** (T3):
- [ ] Golden + empty narratives → worklist = all 10 components + all 150 micros +
  the emitted nanos passing the threshold/export predicate; no collapsed/decision.
- [ ] `--include-nanos` widens to all visible nanos.
- [ ] `--node <decision id>` and `--node <collapsed id>` → exit 2.
- [ ] Each item's `current_signature` matches the model node; each `fallback_text`
  non-empty; each `text` is `""`.
- [ ] A stale approved fixture node appears in the worklist; a fresh approved node
  does not.

**Status**: [ ] pending

---

### Step 6 — `narrate ingest <file>` subcommand
**Goal**: Load a filled worklist into `narratives.json`, pin the signature at
ingest, refuse to overwrite a FRESH approved entry. Implements spec component 5.
The ONLY command that creates entries.

**Design**:
Validate the WHOLE batch first, write nothing on any error (FM4 — no partial
write): required keys present, node exists in the index, and the entry's
`current_signature` still matches the current model (the model may have been
re-extracted between worklist and ingest — R1). Then per validated entry: write if
absent, write if stored `proposed`, write if stored `approved` but signature
drifted (the F6 one-step refresh path — A14), skip if stored `approved` and
signature fresh. Each written entry becomes `{node_id, signature:
current_signature, text, status: "proposed"}` — this is the pin. Write via Step 4's
`_write_narratives`.

**Actions**:
1. Resolve paths, config, index, narratives (Steps 1/2/4).
2. Parse the input file; non-array or bad JSON → `die` (exit 2).
3. Validate all entries, collecting every error; if any, `die` with a per-entry
   list, write nothing.
4. Decide write/skip per the four-case rule above.
5. Set each written entry, `_write_narratives` the whole dict, print
   `"ingested N entries (M skipped fresh-approved)"` (single count, per the spec's
   leaning — see Open Questions).

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `cmd_narrate_ingest`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::cmd_narrate_ingest
tier:  B
-->

**Test criteria** (T4 + part of T8):
- [ ] Valid worklist vs current model → all entries `proposed`, signature pinned.
- [ ] Re-ingest same file, unchanged model → all skipped, nothing written.
- [ ] Malformed entry (missing key / unknown id / wrong signature) → whole batch
  rejected, no partial write.
- [ ] Ingest vs a re-extracted model (signature changed) → batch rejected with a
  per-entry list.
- [ ] FRESH approved entry is never overwritten.
- [ ] Two identical ingest runs → byte-identical `narratives.json` (T8).

**Status**: [ ] pending

---

### Step 7 — `narrate approve <id> [<id>...]` subcommand
**Goal**: Flip proposed→approved per id, deny-by-default, and REFUSE any drifted
entry (no re-pin — closes the laundering hole). Implements spec component 6.

**Design**:
Mirrors `decision_index refresh <id>` (one-id-at-a-time, deny by default). Approve
NEVER re-pins the signature (A15/F6) — it only flips status after confirming the
stored signature still matches the current model. If it drifted, approve refuses,
the entry keeps its old status and signature, and the owner must re-run
worklist→ingest to get fresh text.

**Actions**:
1. Resolve paths, config, index, narratives (Steps 1/2/4).
2. For each id, collect fatal conditions and fail loud (no partial approval):
   unknown id → `die`; `status != "proposed"` → `die` naming the current status;
   stored signature ≠ `sig_index[node_id]` → `die` with the drift message telling
   the owner to re-run worklist/ingest.
3. For each surviving id, set `status = "approved"`; do NOT touch `signature` or
   `text`.
4. `_write_narratives`; print `"approved N entries"`.

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `cmd_narrate_approve`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::cmd_narrate_approve
tier:  B
-->

**Test criteria** (T5 + T6, the F6 round-trip):
- [ ] Proposed entry, matching sig → flips to `approved`, exit 0.
- [ ] Approved-but-stale (sig drifted since ingest) → approve REFUSES, exit 2,
  signature + text unchanged.
- [ ] Unknown id → exit 2, no write.
- [ ] Approve never changes `signature` or `text`.
- [ ] Full F6 round-trip (with Steps 5/6): worklist → ingest → drift model →
  approve refuses → re-ingest fresh text → approve succeeds. No `reject` needed.

**Status**: [ ] pending

---

### Step 8 — `narrate reject <id> [<id>...]` subcommand
**Goal**: Remove entries so the node reverts to fallback text. Implements spec
component 7. No model load, no freshness check — pure delete.

**Design**:
Reject just deletes entries by id (it does not check freshness), but a typo must
not silently succeed, so an unknown id fails loud. It still resolves the repo root
for the default `--narratives` path.

**Actions**:
1. Resolve `--narratives` default (Step 4 path helper) + config (Step 1); load
   narratives (Step 4). No sig index, no model.
2. For each id, unknown → collect; if any unknown, `die` (exit 2), write nothing.
3. Remove surviving entries; `_write_narratives`; print `"rejected N entries"`.

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `cmd_narrate_reject`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::cmd_narrate_reject
tier:  B
-->

**Test criteria** (T9):
- [ ] Existing entries removed; node reverts to fallback on next `narrate status`.
- [ ] Unknown id → exit 2, nothing written.

**Status**: [ ] pending

---

### Step 9 — `narrate status` subcommand
**Goal**: Report every stored entry UNION every in-scope unnarrated node, each with
its DERIVED status, never writing the file. Implements spec component 8.

**Design**:
Scope for status = ALL stored entries (regardless of how they entered scope — so an
entry approved via `--include-nanos` that is now below threshold is STILL watched
for drift, F9 fix) UNION the default worklist scope of unnarrated nodes. Each line
`id | kind | derived_status`, sorted by id. Advisory only — exit 0 always
(`--strict` is deferred to P6, OQ-STRICT-1). It NEVER writes `narratives.json`.

**Actions**:
1. Resolve paths, config, index, narratives (Steps 1/2/4).
2. Build the display set: every stored entry's id UNION every default-scope node
   with no entry.
3. For each, look up `current_sig = sig_index.get(id)` and derive status
   (Step 4 `_derive_status`).
4. Print sorted `id | kind | derived_status`. Exit 0. Write nothing.

**Files to modify**:
- `ssot-diagram/graph_model.py` — add `cmd_narrate_status`.

<!-- plan-verify
new:   ssot-diagram/graph_model.py::cmd_narrate_status
tier:  B
-->

**Test criteria** (T7 + T10):
- [ ] Golden + empty narratives → one `none` line per in-scope node; nothing for
  out-of-scope nanos / collapsed / decisions.
- [ ] Drifted approved entry → `stale` (not `approved`).
- [ ] Vanished node id → `orphaned`.
- [ ] `--include-nanos` entry now below threshold → still shown (F9 fix).
- [ ] `narratives.json` mtime unchanged after a status run (read-only, T10).
- [ ] Exit 0.

**Status**: [ ] pending

---

### Step 10 — CLI wiring (`narrate` subparser group)
**Goal**: Wire the five subcommands into `build_parser` so `graph_model.py narrate
…` dispatches, without touching `extract` / `bootstrap-config`. Implements spec
component 9.

**Design**:
Add a `narrate` parent subparser with its own nested subparsers
(`required=True`), each `set_defaults(fn=cmd_narrate_*)` — the exact pattern the
existing `extract`/`bootstrap-config` subparsers use, so `main`'s `args.fn(args)`
dispatch is unchanged. Flag set per the spec's component-9 sketch (`--model`,
`--narratives`, `--config` on all; `--include-nanos`, `--node`, `-o/--out` on
worklist; positional `file` on ingest; positional `ids` nargs="+" on
approve/reject).

**Actions**:
1. In `build_parser` (`graph_model.py:953`), after the existing subparsers, add
   `narrate = sub.add_parser("narrate", …)` and
   `narrate_sub = narrate.add_subparsers(dest="narrate_cmd", required=True)`.
2. Add the five child parsers (`worklist`, `ingest`, `approve`, `reject`,
   `status`) with their flags and `set_defaults(fn=…)`.
3. Do NOT modify the `extract` or `bootstrap-config` parsers or `main`.

**Files to modify**:
- `ssot-diagram/graph_model.py` — edit `build_parser` (add the `narrate` group).

<!-- plan-verify
touch: ssot-diagram/graph_model.py::build_parser
tier:  B
qualifiers: grep-absent "def main_narrate" ssot-diagram/graph_model.py
-->

**Test criteria** (T-CLI):
- [ ] `graph_model.py narrate --help` lists all five subcommands.
- [ ] `graph_model.py narrate` with no subcommand → exit 2.
- [ ] `graph_model.py extract --help` and `bootstrap-config --help` unchanged (no
  regression in the existing subcommands).
- [ ] `--model` / `--narratives` absent → resolves to repo-root defaults.

**Status**: [ ] pending

---

### Step 11 — Config schema additions + manifest entry
**Goal**: Add the two optional config keys and register P4 in `manifest.json`.
Implements spec component 11.

**Design**:
The two keys are additive and optional (version stays 1); existing configs that
omit them keep working via Step 1's `.get()` defaults. The manifest gets a separate
`narrative-sidecar` entry (OQ-MANIFEST-1 resolved 2026-07-06, owner: separate key)
so P4 gets its own `piggyback status` line, sharing the `graph_model.py` script
with `hooks: []`.

**Actions**:
1. `ssot-diagram/ssot-diagram.config.json`: add `"narrate_threshold": 4` and
   `"narratives_path": "ssot-diagram/narratives.json"`. Keep `version: 1`.
2. `manifest.json`: add under `scripts` a `narrative-sidecar` entry:
   `{"script": "ssot-diagram/graph_model.py", "scope": "repo", "desc":
   "ssot-diagram P4 — narrate subcommands: plain-language sidecar for diagram
   nodes, signature-pinned", "hooks": []}`. Leave the `diagram-model` desc P3-only.

**Files to modify**:
- `ssot-diagram/ssot-diagram.config.json` — add two keys.
- `manifest.json` — add `narrative-sidecar` under `scripts`.

<!-- plan-verify
tier:  B
qualifiers: byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
gates: human:manifest-and-config-edit
note: data-only step — manifest.json + ssot-diagram.config.json are JSON, not codegraph-indexed code, so no touch:/new: symbol claims apply; the edits are guarded by the byte-unchanged golden qualifier + the ## Files list.
-->

**Test criteria** (T-CONFIG):
- [ ] `piggyback status` lists `narrative-sidecar`.
- [ ] The updated config is read correctly by `_load_narrate_config` (threshold 4,
  path present).
- [ ] A config WITHOUT the two keys still works (defaults).
- [ ] `manifest.json` still parses as JSON; `diagram-model` entry unchanged.

**Status**: [ ] pending

---

### Step 12 — Tests + regression sweep
**Goal**: Prove the whole contract holds and nothing regressed. Implements spec
component 12 (T1–T11 aggregate) with the cross-cutting tests that span multiple
commands (byte-determinism T8, F6 round-trip T5+T6, regression T11).

**Design**:
Steps 1–11 each carry their own unit tests; this Step adds the cross-cutting ones
that no single earlier Step owns — full byte-determinism, the multi-command F6
round-trip, the "no `stale` string anywhere" file assertion, and the P1/P3
regression gate — then runs the full suite. Tests live in
`ssot-diagram/test_graph_model.py` beside the code, matching P3.

**Actions**:
1. Add T8 (byte-determinism: two ingest runs sha256-equal; no `generated_at`; keys
   sorted; trailing `\n`; `ensure_ascii=False`).
2. Add the "no `"stale"` string anywhere in `narratives.json` after any `status`
   run" assertion (part of T7).
3. Add T11 regression: `decision_index status` exits 0; `graph_model.py extract`
   byte-matches the golden on disk (byte-compare the file like the existing
   `test_golden_byte_match` at `test_graph_model.py:367–386` — do NOT hardcode the
   sha; if a hash is asserted anywhere use the real `56df3d86…`, never `5a1e2156…`).
4. Run `python3 -m pytest ssot-diagram/` — existing 32 + new P4 tests green, golden
   NOT skipped (pilot DB present).

**Files to modify**:
- `ssot-diagram/test_graph_model.py` — add cross-cutting P4 tests + regression.

<!-- plan-verify
touch: ssot-diagram/test_graph_model.py::GOLDEN
tier:  C
qualifiers: byte-unchanged ssot-diagram/testdata/mkt_engine.model.json
-->

**Test criteria**:
- [ ] `python3 -m pytest ssot-diagram/` green (32 existing + new P4 tests).
- [ ] Two ingest runs → byte-identical `narratives.json` (sha256 equal).
- [ ] `narratives.json` contains no `"stale"` string.
- [ ] `graph_model.py extract` still byte-matches the golden (`56df3d86…`).
- [ ] `decision_index status` still exits 0.

**Status**: [ ] pending

---

## E2E Done Criteria
Plain-English: unit tests passing is necessary but not enough. Before "done", run
the real `narrate` commands end to end against the live pilot repo (the one with
`.codegraph/codegraph.db` + the shipped `diagram-model.json`) and watch the actual
CLI output and the actual `narratives.json` contents change the way the contract
says they should — especially the F6 laundering-hole close, which is the whole
point of the phase.

**Prerequisites:** the live pilot repo with `.codegraph/codegraph.db` present, a
freshly extracted `ssot-diagram/diagram-model.json` (`graph_model.py extract`), the
shipped `ssot-diagram.config.json`, and `piggyback` on PATH. No mocks.

**Walkthrough** (action → observe → expected; mapped to ## Capabilities):
1. Run `graph_model.py narrate status` with NO `narratives.json` present → observe
   stderr/stdout: exit 0, one `… | none` line per in-scope node, no crash →
   expected (C1, C12).
2. Run `graph_model.py narrate worklist -o /tmp/wl.json` → observe `/tmp/wl.json`:
   a JSON array, every item `{node_id, kind, name, current_signature,
   fallback_text, text:""}`, no `decision:`/`collapsed` ids, fallback sentences
   read as plain English with no `──` bars → expected (C6, C7).
3. Hand-fill a few `text` fields in `/tmp/wl.json`, run
   `graph_model.py narrate ingest /tmp/wl.json` → observe stderr
   `"ingested N entries …"` and `ssot-diagram/narratives.json` now exists with
   those entries `status: "proposed"`, each `signature` equal to the model node's
   signature → expected (C8, C13).
4. Run `graph_model.py narrate approve <one id>` → observe stderr `"approved 1
   entries"` and that entry now `status: "approved"`, signature unchanged →
   expected (C10).
5. Re-run `graph_model.py narrate status` → observe the approved id shows
   `approved`, the still-proposed ids show `proposed`, unnarrated in-scope nodes
   show `none`; `narratives.json` mtime unchanged after the run → expected (C12).
6. Edit a narrated function's source, re-run `codegraph` index + `graph_model.py
   extract` (signature drifts), then `graph_model.py narrate approve <that id>` →
   observe exit 2 + the drift message, entry still `approved` with the OLD
   signature and OLD text (NOT laundered) → expected (C10, the F6 close).
7. Re-run `graph_model.py narrate worklist` → observe the drifted node reappears
   (derived `stale`); `ingest` fresh text for it → observe it is rewritten
   `proposed` with the NEW signature; `approve` it → succeeds. One-step refresh, no
   `reject` → expected (C9).
8. Run `graph_model.py narrate reject <an id>` → observe `"rejected 1 entries"` and
   that node reverts to fallback on the next `status` → expected (C11).
9. `grep stale ssot-diagram/narratives.json` → observe NO match → expected (C13).
10. Run `graph_model.py extract` again and diff its output vs the committed golden;
    run `piggyback status` → observe golden byte-identical (`56df3d86…`) and a
    `narrative-sidecar` line present → expected (C15, C16).

**Done gate:** every walkthrough line observed + matching, evidence captured, and
`python3 -m pytest ssot-diagram/` + `decision_index status` (exit 0) + the golden
byte-match all pass. If a live observation diverges from a passing unit test, the
live observation wins — fix and re-run before marking done.

## Open Questions
- **Ingest skip-message granularity (planner-deferred from spec component 5).** When
  ingest skips FRESH approved entries, is the notice a single count or per-id? Plan
  adopts the spec's lean: single count (`"ingested N (M skipped fresh-approved)"`),
  since the WRITTEN entries are the actionable output. Reversible; no contract
  impact. Not blocking.
- **`narrate_threshold` default = 4** — OPEN (human-authority: operating burden),
  but ALREADY RATIFIED by the owner in the design revision log; no re-approval at
  build. Recorded here only for traceability, not as a blocker.
- **`narrative-sidecar` separate manifest key** — OPEN (human-authority: product
  identity), but RESOLVED by owner 2026-07-06 (OQ-MANIFEST-1). Not a blocker.

## Out of Scope
Per spec `## Out of scope` (do not restate — link): `narrate status --strict`
non-zero exit (P6, OQ-STRICT-1); orphaned-narrative `gc` (P6, OQ-GC-1); persisted
"declined" marker (P6, OQ-DECLINED-1); any DB access; hook events / PostToolUse
re-extract (P6); the P5 renderer / Phase F biography reading logic; `_shared/`
extraction (Phase B); a config schema version bump. Additionally out of scope for
this plan: editing `decision_index.py`, regenerating or mutating the golden model,
and any change to the `extract` / `bootstrap-config` behavior.
