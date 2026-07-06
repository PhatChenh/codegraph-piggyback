# Phase 4 — Narrative sidecar (`narrate` subcommands on `graph_model.py`)

## Purpose

P4 is the only layer in the ssot-diagram stack where a sentence is written by an
LLM and trusted by a human. It gives a non-coder owner a plain-language sentence
for every component, file, and function the diagram already shows — while keeping
the deterministic foundation honest: every sentence is pinned to the code's content
signature, so the moment the code drifts, the sentence is visibly marked stale,
never silently current.

After this phase the owner can: ask the tool "which nodes still need a human
sentence?" (`narrate worklist`), feed LLM-proposed sentences back in
(`narrate ingest`), sign each one off individually (`narrate approve`), drop one
(`narrate reject`), and ask "what is trusted, what is stale, what is missing?"
(`narrate status`). A deterministic fallback sentence is always available, so the
diagram is readable even before any human has approved a single sentence.

P4 adds **no new Python file** and **no hook events**. It is five new subcommands
on the existing `graph_model.py`, one new output file (`narratives.json`), and two
new optional keys on the existing config. Nothing unapproved, nothing out-of-date,
ever renders as trusted prose.

## Already built (reuse, do not rebuild)

Everything below is verified against the live P3 code (`graph_model.py` on disk)
and the golden model `testdata/mkt_engine.model.json` (sha256 `56df3d86…`).

| Function / constant | Location | What it does | How P4 uses it |
|---|---|---|---|
| `_save_model(path, model)` | `graph_model.py:796` | Atomic write: `path.parent.mkdir`, write `model.tmp` with `json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`, `os.replace`. Generic over any dict. | P4 writes `narratives.json` through this exact function — no new writer. Verified: body inspects no model-specific keys (A3). |
| `_sorted_sha256(parts)` | `graph_model.py:64` | sha256 over a sorted list of strings. | Not directly used by P4 (signatures come from the model), but listed because the design's `cast of characters` references it. |
| `die(msg)` | `graph_model.py:55` (local) and `decision_index.py:327` (`di.die`) | `print("error: …", file=sys.stderr); sys.exit(2)`. | P4 fatal errors use the local `die` (exit 2), matching P3. Verified: `di.die` and local `die` both exit 2 (A10). |
| `ok(msg)` / `warn(msg)` | `graph_model.py:50` / `:46` | Print success / warning to stderr. | P4 prints "wrote narratives.json", "skipped N fresh approved" etc. via these. |
| `build_parser()` | `graph_model.py:953` | Standard argparse: `sub = p.add_subparsers(dest="cmd", required=True)`; existing children `extract`, `bootstrap-config`. | P4 adds a `narrate` parent subparser with its own nested subparsers. Verified: standard pattern, no custom parser class (A8). |
| `cmd_extract(args)` | `graph_model.py:810` | P3 extractor: `db = di.find_db(cwd)` or die; `root = di.repo_root_for(db_path)`; default paths `root / DEFAULT_*_REL`. | P4 subcommands follow the SAME discovery pattern for `--model` / `--narratives` defaults (when the flag is absent, derive from repo root). |
| `DEFAULT_OUTPUT_REL` | `graph_model.py:30` | `"ssot-diagram/diagram-model.json"` | P4's `--model` default. |
| `DEFAULT_CONFIG_REL` | `graph_model.py:29` | `"ssot-diagram/ssot-diagram.config.json"` | P4's permissive config reader loads this when `--config` absent. |
| `load_config(path)` | `graph_model.py:72` | Strict validator: `die()` (exit 2) if `version`/`components`/`default_component` absent or `nano_cap` invalid. | P4 MUST NOT call this for its subcommands (a read-only `narrate status` on a minimal config would die). P4 uses a permissive reader instead. Verified (A7): body calls `die` on 5 missing-key paths. |
| `di.find_db(cwd)` | re-exported in `decision_index.py:49` from `_shared.db` | Returns `.codegraph/codegraph.db` Path found by searching upward, or `None`. | P4 uses it when `--model`/`--narratives` flags are absent (same as `cmd_extract`). |
| `di.repo_root_for(db_path)` | re-exported in `decision_index.py:49` from `_shared.db` | Returns the repo-root Path for a given DB path. | P4 derives default paths as `root / DEFAULT_OUTPUT_REL` and `root / "ssot-diagram/narratives.json"`. |
| `di.open_db`, `di.current_sig`, `di.load_index` | `decision_index.py:72` / `:97` / `:124` | DB open (read-only), live signature of a ref, decision-index load. | P4 needs NONE of these — it reads `diagram-model.json`, never the DB or the decision index directly. Listed only to make the "P4 does not touch these" boundary explicit. |
| Golden model `testdata/mkt_engine.model.json` | on disk | The frozen P3 output. top-level keys: `components, decisions, generated_at, nano_cap, version`. 10 components, 150 micros, 245 emitted nanos, 2 collapsed, 11 decision nodes (8 ADRs). | P4's id→signature index is built by walking this structure. Verified field sets (A1/A2/A5/A6/A9). |
| `manifest.json` `scripts` dict | repo root | Each entry: `{script, scope, desc, hooks}`. Existing ssot entries: `decision-index` (hooks Read), `diagram-model` (hooks []). | P4 adds a `narrative-sidecar` entry with `hooks: []` (CLI-only; P6 owns hook wiring). |
| `ssot-diagram/ssot-diagram.config.json` | on disk | v1 schema; `narrate_threshold` and `narratives_path` do NOT exist yet. | P4 reads the two new keys permissively; absence → defaults. |

## Feature overview

P4 sits entirely on top of `diagram-model.json` (the P3 output). It never opens the
codegraph DB and never opens the decision index. Its whole job is: read the model,
read `narratives.json` (or treat it as empty), and either report what needs doing
(worklist / status) or apply a human-or-LLM decision (ingest / approve / reject).

**The signature is the honesty contract.** Every model node already carries a content
`signature` (P3). When an LLM proposes a sentence (`ingest`), P4 pins that sentence to
the node's signature *at ingest time*. When the owner approves it (`approve`), P4
checks the stored signature still matches the current model signature — if the model
was re-extracted since ingest, the node has drifted and approve refuses it. There is no
path to make old text look fresh: approve never re-pins, only flips `proposed`→`approved`
after a freshness check. This is the F6 fix from the red-team.
> **Known limit (TD-P4-1, accepted 2026-07-06):** the above holds for *distinct* code, but
> not for a degenerate collision where an id is REUSED for new code whose body hashes to
> the SAME signature (e.g. both empty-body: `cmp-dist` + `cmp-invoice-cost` both =
> sha256 of empty source). Narrow (needs id-reuse AND identical empty body), solo-builder
> low-probability; accepted as documented rather than amending Block 5a. See STATE.md.

**Staleness is never stored.** The `status` field written to `narratives.json` is exactly
`proposed` or `approved` — never `stale`. `stale` is a *derived* display state that
`narrate status` (and later the P5 renderer) computes by comparing the stored signature
to the current model signature. This is the Block 5a amendment (F1 fix): a stored stale
badge is a mutation side-effect of a read and can itself go out of date; deriving it
from a live comparison is always accurate.

**The five subcommands, happy path.** The owner runs `narrate worklist`, which writes a
JSON array (one object per node that needs a sentence) to stdout or `-o`. Each object
carries the node id, kind, name, current signature, a deterministic fallback sentence,
and a blank `text` field. The owner pastes this into an LLM session, the LLM fills the
`text` fields, the owner saves the filled file. Then `narrate ingest <file>` validates
every entry (required keys present, node still exists in the model, signature still
matches the current model — the model may have moved between worklist and ingest),
refuses a fresh-approved overwrite, and writes accepted entries as `status: proposed`.
Then `narrate approve <id>` (one id at a time, deny-by-default, mirroring
`decision_index refresh <id>`) flips the entry to `approved` after a final freshness
check. `narrate status` reports the full picture. `narrate reject <id>` deletes an entry.

**Scope.** Components and micros are ALWAYS in scope. Nanos are in scope when
`is_exported OR caller_count >= narrate_threshold` (default 4, owner-tunable). This scope
operates ONLY over nanos the model actually emitted — P3 collapses per-micro nanos beyond
`nano_cap` (default 8) into a single `collapsed` node (golden model: 2 collapsed, 245
emitted). Collapsed nanos have no addressable node id and are never narratable. The two
knobs coexist: `nano_cap` (P3) decides what is DISPLAYED; `narrate_threshold` (P4) decides
which displayed nanos need a hand-written sentence. This is the F4 reconciliation.

**Decisions are excluded.** One ADR fans out to N decision nodes in the model (golden:
11 decision nodes for 8 ADRs — ADR-0001, ADR-0003, ADR-0007 each appear twice, once per
component they attach to). Narrating each copy would mean writing the same sentence 2–3×.
Decisions already carry their ADR name + FRESH/STALE badge, and the ADR file itself is the
human prose. This is the F5 fix — decisions are out of P4 scope entirely.

**Deterministic fallback.** Before any human approves a sentence, every node still shows
a plain-language sentence derived purely from the model node's fields (no DB lookup). A
nano shows its name, "function", its caller count, and the first sentence of its
docstring (with separator-bar lines stripped — real pilot docstrings frequently start with
`──`/`---` bars). A micro shows its name, "file", and a count of non-collapsed children.
A component shows its name, "component", and a count of non-collapsed child micros. The
fallback is never persisted as an approved narrative; it is informational, shown in the
worklist and used by P5 when no entry exists.

## Out of scope

- **`narrate status --strict` non-zero exit.** P4's `status` is advisory (exit 0 always).
  A CI-gate that fails merges on stale narratives is a clear future use but is deferred to
  P6 (OQ-STRICT-1). Precedent: `decision_index status` established the advisory-then-strict
  pattern.
- **Orphaned-narrative garbage collection.** A renamed/deleted function leaves a stale
  entry in `narratives.json`; `narrate status` surfaces it as `orphaned` and the owner
  removes it with `narrate reject <id>`. A bulk `narrate gc` is deferred to P6
  (OQ-GC-1). Blast radius is low — orphaned entries are inert (no node renders them).
- **Persisted "declined" marker for rejected nodes.** A rejected node still in scope
  re-appears in the next worklist. The declined-vs-never-seen distinction (precedent:
  Block 1c rail picker) is deferred to P6 (OQ-DECLINED-1).
- **DB access.** P4 reads only `diagram-model.json`. It never opens
  `.codegraph/codegraph.db` and never reads the decision index directly. The sibling
  import `import decision_index as di` is reused ONLY for `di.find_db` /
  `di.repo_root_for` (path discovery) — not for `di.current_sig` or `di.open_db`.
- **Hook events / PostToolUse re-extract.** P4 ships CLI-only (`hooks: []` in the
  manifest). The PostToolUse hook that re-extracts the model and refreshes staleness is
  P6 scope — it will own hook wiring, per the ssot-diagram roadmap.
- **Renderer / biography consumer logic.** P4 only WRITES `narratives.json` and computes
  derived status for its own `status` command. The P5 renderer and Phase F biography tool
  are downstream consumers; they must obey the Block 5a/5b consumer obligation (compute
  derived status themselves via signature comparison). P4 exposes the contract; it does
  not implement their reading.
- **`_shared/` extraction.** P4 reuses `decision_index as di` by sibling import, matching
  P3's ADR-0001 decision. Extracting common code to `_shared/` stays Phase B.
- **Config schema bump.** Adding `narrate_threshold` and `narratives_path` keeps the config
  at `version: 1`. The two new keys are read permissively (`.get()` with defaults); a
  config that omits them (every existing config today) continues to work unchanged.

## Constraints

Non-negotiable. Each carries its source.

- **Block 5a (FROZEN; AMENDED 2026-07-06, owner-ratified) — entry shape.** Each entry in
  `narratives.json` is exactly `{node_id, signature, text, status}`. Stored `status` is
  `proposed` or `approved` ONLY — `stale` is NEVER written to the file; it is a derived
  display state every consumer MUST compute via signature comparison. No fourth field may
  be added without a contract revision. Source: `docs/roadmap/skeleton-contracts.md`
  Block 5a (lines 177–188).
- **Block 5b (FROZEN) — trust rule + consumer obligation.** Nothing renders or quotes as
  trusted prose unless `status == approved` AND the stored `signature` matches the
  current `diagram-model.json` node's `signature`. Because `stale` is never stored, every
  consumer (P5, biography) MUST compute the derived status itself — reading the stored
  `status` literally and trusting `approved` without the signature check would render
  drifted prose as current. Source: `skeleton-contracts.md` Block 5b (lines 190–196).
- **Block 4a (FROZEN) — three-level NESTED model.** The model P4 walks is
  `components[].children` = micros, `micros[].children` = nanos. No fourth level, no flat
  mode. The id→signature walker traverses exactly this shape. Source: `skeleton-contracts.md`
  Block 4a (lines 146–147) + `ssot-diagram/CLAUDE.md` tool-specific rules.
- **Block 4b (FROZEN) — node fields.** Every model node carries a deterministic `id` and
  content `signature`. P4 pins prose to the `signature` field at INGEST. Source:
  `skeleton-contracts.md` Block 4b (lines 149–152).
- **Read-only DB.** P4 never touches `.codegraph/codegraph.db`. (It never opens it at all,
  but if it ever needs DB access in a later phase, `mode=ro&immutable=1`.) Source:
  repo `CLAUDE.md` Critical Rules + `ssot-diagram/CLAUDE.md`.
- **Byte-deterministic writer.** `narratives.json` is written via `_save_model`:
  `json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` + atomic
  `os.replace`. No `generated_at` field. `sort_keys=True` orders all dict keys (including
  the `node_id` top-level keys) automatically — NO separate sort step is performed or
  needed. Source: repo `CLAUDE.md` Coding Patterns + design §narratives.json format.
- **stdlib only.** No new dependencies. P4 uses `argparse`, `json`, `os`, `sys`,
  `pathlib`. Source: repo `CLAUDE.md` Tech Stack.
- **Fail-loud, exit 2.** Fatal errors (missing model, malformed ingest, unknown id,
  signature-field absent on a node) call the existing `die` (exit 2), matching P3 and
  `di.die`. Source: P3 convention (`graph_model.py:55`, `decision_index.py:327`).
- **Sibling import, not `_shared/`.** P4 reuses `import decision_index as di`
  (`graph_model.py:27`) for path discovery only. Source: `ssot-diagram/CLAUDE.md` +
  ADR-0001.
- **Manifest entry required.** P4 adds a `narrative-sidecar` entry to `manifest.json` with
  `hooks: []`. A script not in the manifest does not ship. Source: repo `CLAUDE.md`
  Critical Rules.

## Assumptions

Each is a falsifiable claim about the live code. The factual-code-verification step
must confirm each one (and any the spec author missed) against the actual code — the
"Verified ✓" notes below are from this spec author's own targeted reads at spec time and
are NOT a substitute for independent verification. The design's A1–A10 are folded in here
as A1–A10 (same numbering, so research can trace back).

| ID | Assumption | Source | What would prove it wrong |
|---|---|---|---|
| A1 | `component`, `micro`, and `nano` nodes in the emitted `diagram-model.json` each carry a `"signature"` key (hex string). `collapsed` nodes carry one too but are excluded from P4 scope. `decision` nodes are excluded from P4 scope and not indexed. | design A1; golden model | Any narrated kind in the model whose dict lacks a `"signature"` key → the index has `None` and every comparison shows stale. |
| A2 | The model JSON is NESTED: a single top-level `"components"` array; each component has `"children"` (micros); each micro has `"children"` (nanos). There are NO flat top-level `micros`/`nanos` arrays. Top-level keys are exactly `components, decisions, generated_at, nano_cap, version`. | design A2; golden model | A model with top-level `micros`/`nanos` arrays, or a component/micro without `children` → the walker misses micros/nanos. |
| A3 | `_save_model(path, model)` (`graph_model.py:796`) is generic: it does `path.parent.mkdir`, atomic `tmp` write with `json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`, `os.replace(tmp, path)`. It does NOT inspect the dict structure or hardcode model-specific keys. | design A3; codegraph read | The function references `model["components"]` or any specific key → P4 cannot reuse it to write `narratives.json` and must add a new writer. |
| A4 | `di.find_db` and `di.repo_root_for` are resolvable as module-level names on `decision_index` (re-exported from `_shared.db` at `decision_index.py:49`). | design A4; codegraph read | `graph_model.py:27`'s `import decision_index as di` does NOT expose `di.find_db`/`di.repo_root_for` → every P4 subcommand must re-derive repo root differently. |
| A5 | Nano nodes do NOT carry `start_line`/`end_line` in the emitted JSON. Nano dict keys are exactly `caller_count, decisions, docstring, edges, id, is_exported, kind, name, path, qualified_name, signature`. | design A5; golden model | A fallback formula referencing `start_line`/`end_line` raises `KeyError` on every nano. |
| A6 | Micro nodes do NOT carry `caller_count`. Micro dict keys are exactly `children, decisions, dominant_class, edges, id, kind, name, path, signature`. The micro fallback must use the count of non-collapsed children, NOT `caller_count`. | design A6; golden model | A fallback formula using `micro["caller_count"]` raises `KeyError`. |
| A7 | `load_config` (`graph_model.py:72–120`) calls `die()` (exit 2) if `version`, `components`, `default_component`, or `nano_cap` are absent/invalid. Therefore `narrate` MUST NOT call `load_config` for its subcommands; it uses a permissive `.get()` reader for `narrate_threshold` and `narratives_path`. | design A7; codegraph read (`load_config` body has 5 `die()` paths) | If `load_config` does NOT die on missing keys, P4 could reuse it. Either way, the permissive reader is the safe path; this assumption confirms the reader is necessary, not optional. |
| A8 | `build_parser()` (`graph_model.py:953`) uses a standard `sub.add_subparsers(dest="cmd", required=True)` pattern with no custom parser class. A new `narrate` parent subparser with a nested `sub2 = narrate.add_subparsers(dest="narrate_cmd", required=True)` can be added without touching existing subcommands. | design A8; codegraph read | A custom parser class or a parser that forbids nesting → the `narrate` group cannot be added cleanly. |
| A9 | `collapsed` nodes appear as children of micros with `kind == "collapsed"` and keys `collapsed_count, id, kind, name, signature`. The id→signature walker excludes them by checking `child["kind"] != "collapsed"`. Including them would raise `KeyError` on `caller_count` (absent). | design A9; golden model | A `collapsed` child whose `kind` is not exactly `"collapsed"`, or a non-collapsed child missing `caller_count` → the exclusion predicate misfires. |
| A10 | `di.die` (`decision_index.py:327`) and the local `die` (`graph_model.py:55`) both call `sys.exit(2)`. P4 uses the local `die` for fatal errors and matches this exit code. | design A10; codegraph read | `die` exits with a code other than 2 → CI scripts handling P4 failures may misbehave. |
| A11 | `diagram-model.json`'s decision nodes are keyed `decision:{did}@{cid}` (one per ADR × component), so an ADR appears N times. Golden: 11 decision nodes / 8 ADRs. This is WHY decisions are excluded from narration scope (writing each copy = duplicate sentences). | design (F5 fix); golden model | If decisions were emitted once per ADR (not per component), the exclusion rationale weakens — but the exclusion stands regardless (the ADR file is the human prose). |
| A12 | `narrate`'s permissive config reader can read `narrate_threshold` and `narratives_path` from `ssot-diagram.config.json` via `.get()` with defaults, WITHOUT calling `load_config`. Unknown keys in the config survive a `json.loads` round-trip (the reader loads the JSON itself, not via `load_config`). | design §config reading; F3 fix | If the only way to read the config is `load_config` (which dies on missing required keys), a read-only `narrate status` on a minimal config aborts before printing. |
| A13 | `_save_model` appends a trailing `"\n"` and uses `ensure_ascii=False`. Determinism tests comparing `narratives.json` against a hand-built expected string must match this exactly (trailing newline, non-ASCII passthrough). | F2 fix; codegraph read of `_save_model` body | A test that builds an expected string without the trailing newline or with `ensure_ascii=True` fails on a correct writer. |
| A14 | An `approved` entry whose stored `signature` matches the current model node signature is FRESH and ingest MUST NOT overwrite it. An `approved` entry whose stored signature does NOT match is approved-but-stale and ingest MUST write fresh proposed text for it (the path that lets approved-but-stale nodes receive new text without a `reject`). | design §ingest (F6 fix) | If ingest skips all approved entries unconditionally, approved-but-stale nodes can never receive fresh text without a three-step reject→ingest→approve dance. |
| A15 | `approve` does NOT re-pin the signature. It only flips `proposed`→`approved` after verifying the stored signature still matches the current model node signature. If the signature has drifted since ingest, approve REFUSES the id with a clear message. | design §approve (F6 fix) | If approve re-pins to the current signature, a human can approve old text into fresh-looking status while the text still describes old code (the laundering hole). |

## Component dependency order

These are the buildable components, in dependency order. Execution order (which a
developer writes first, parallelization) is owned by `/plan-from-specs`. Each component
names the files it touches; the planner decides exact code, signatures, and test names.

### 1. Permissive config reader + two new default constants

**Goal.** Read `narrate_threshold` and `narratives_path` from
`ssot-diagram.config.json` without ever calling the strict `load_config`, so a read-only
`narrate status` on a minimal or absent config never aborts.

**Build.** In `graph_model.py`:
- A module-level constant `DEFAULT_NARRATE_THRESHOLD = 4`.
- A module-level constant for the default narratives path, derived as
  `"ssot-diagram/narratives.json"` (sibling of `DEFAULT_OUTPUT_REL`).
- A function `_load_narrate_config(config_path: Path) -> tuple[int, Path]` that: if the
  config file is absent, returns `(DEFAULT_NARRATE_THRESHOLD, <default>)`; if present,
  `json.loads` it (NOT `load_config`), and `.get("narrate_threshold", DEFAULT_NARRATE_THRESHOLD)`
  + `.get("narratives_path", <default>)`. Treats a malformed JSON as a warn-and-default
  (read-only commands must not die on a bad config the way `load_config` would) — but a
  present-and-non-dict config is a `die` (exit 2), because that is a corrupt file, not a
  missing one.

**Depends on.** None (first component).

**Assumes.** A7, A12.

**Interface shape.** Caller sees `_load_narrate_config(path) -> (threshold, narratives_path)`.
Hidden: the strict-vs-permissive distinction is entirely behind this function; no other
P4 code calls `load_config`. One adapter (the narrate subcommands) — not speculative,
it has 5 callers within P4.

**Done when.** Given a config file that is missing, `narrate status` returns exit 0 and
prints (no crash). Given a config with `narrate_threshold: 7`, `narrate worklist` includes
non-exported nanos with `caller_count >= 7`. Given a config with no `narrate_threshold`
key, the default 4 is used. Given a config that is not a JSON object (e.g. a JSON array),
the command dies with exit 2 and a clear message.

### 2. Model loader + id→signature index builder

**Goal.** Load `diagram-model.json` once per subcommand and build the complete
id→signature map P4 uses to (a) validate ingest entries, (b) check freshness at approve,
(c) derive staleness at status.

**Build.** In `graph_model.py`:
- A function `_load_model(model_path: Path) -> dict` that opens the model JSON; on
  `FileNotFoundError`/`JSONDecodeError`, `die` (exit 2) with
  `"diagram-model.json not found — run graph_model.py extract first"`.
- A function `_build_sig_index(model: dict) -> dict[str, str]` that walks the NESTED
  structure (components → micros → emitted nanos), asserts `"signature" in node` for every
  non-collapsed node (fail-loud, exit 2 — catches schema drift at startup, FM3), and
  returns `{node_id: signature}`. Collapsed children (`kind == "collapsed"`) are skipped.
  Decision nodes are NOT walked (they live under `model["decisions"]`, not under
  `components[].children`).

**Depends on.** None.

**Assumes.** A1, A2, A9.

**Done when.** Given the golden model, the index has exactly
`10 + 150 + 245 = 405` entries (all components + all micros + all emitted nanos; 2
collapsed nodes and 11 decision nodes excluded). No entry has value `None`. If a future
P3 change emits a nano without a `signature`, the builder dies at startup with a clear
message naming the node, before any read or write.

### 3. Deterministic fallback text (`_fallback_text`)

**Goal.** A pure function that produces a non-empty plain-language sentence for every
narratable node kind, using only the model node's fields — so the diagram is readable
before any human work and so the worklist can pre-fill a candidate sentence.

**Build.** In `graph_model.py`, a function `_fallback_text(node: dict) -> str`:

- **nano:** `"<name> — function, <caller_count> caller(s). <first_sentence_of_docstring>"`
  with the docstring clause OMITTED if `docstring` is empty or contains only separator
  lines. First-sentence extraction: strip leading lines matching `^\s*[-─=]+\s*$` (real
  pilot docstrings start with `──`/`---` bars — `validatePixelSize`, `EditTopBar`,
  `ResizeTool`), then take remaining text up to the first period followed by a space,
  newline, or end-of-string. If no period is found, take the first 70 cleaned characters
  (FM6).
- **micro:** `"<name> — file, <N> function(s)."` where `N` = count of children with
  `kind != "collapsed"` (NOT `len(children)` — F8 fix; `len` would count the collapsed
  child as a function). Uses the real `micro.name` field.
- **component:** `"<name> — component, <N> file(s)."` where `N` = count of children with
  `kind != "collapsed"`.
- **decision / collapsed:** no recipe (excluded from scope). If called on one, raise
  `ValueError` (programmer error — the scope predicate should have excluded it).

**Depends on.** None (pure function).

**Assumes.** A5, A6, A9.

**Done when.** For a nano with a normal docstring, the fallback ends at the first
sentence boundary (e.g. `"verifySession — function, 8 caller(s). Verify a session is
valid and return the owning user, or null."`). For a nano with a separator-bar docstring,
the bars are stripped (NOT `"── Validation helpers ─────."`). For a nano with no
docstring, the fallback is `"<name> — function, <N> caller(s)."` (no trailing dot after
callers unless the docstring clause fires). For a nano with a no-period docstring, the
fallback is non-empty, never raises, and ends at a character boundary (≤70 chars). For
`micro:lib/canvas/store.ts` (8 nanos + 1 collapsed), the fallback reads `"8 function(s)"`
(NOT 9). The function never returns an empty string and never raises on a real-model
node.

### 4. `narrate worklist` subcommand

**Goal.** Emit a JSON array of nodes that need a human sentence: every in-scope node with
no stored entry (`status == "none"`) OR whose stored signature does not match the current
model (`status == "stale"`).

**Build.** In `graph_model.py`, function `cmd_narrate_worklist(args)`:
- Resolve `--model` (default `root / DEFAULT_OUTPUT_REL` via `di.find_db` +
  `di.repo_root_for`, same as `cmd_extract`); `--narratives` (default `root /
  "ssot-diagram/narratives.json"`); load narrate config (component 1).
- Build the sig index (component 2). Load `narratives.json` (absent → empty dict).
- Compute default scope: every component id + every micro id + every emitted nano id
  where `is_exported OR caller_count >= narrate_threshold`. Collapsed + decision excluded.
- `--include-nanos` forces ALL visible (non-collapsed) nanos into scope regardless of
  threshold. `--node <id>` adds exactly one named node (component/micro/nano — not
  decision, not collapsed) whether or not it is in default scope.
- For each scoped node, derive its status (`none` / `stale` / `proposed` / `approved` —
  see component 7's derivation rules). Emit a worklist item ONLY for `none` and `stale`.
  Each item: `{node_id, kind, name, current_signature, fallback_text, text: ""}`.
- Write the JSON array to `-o <file>` or stdout (pretty-printed, 2-space indent, trailing
  newline — match the writer's serialization style so round-trip is clean).

**Depends on.** Components 1, 2, 3.

**Assumes.** A1, A2, A9, A14 (a stale approved node IS emitted — it needs fresh text).

**Done when.** Given the golden model and an empty `narratives.json`, the worklist contains
exactly the in-scope nodes (all 10 components + all 150 micros + the emitted nanos passing
the threshold/export predicate). No collapsed or decision id appears. Each item's
`current_signature` matches the model node's `signature`. Each item's `fallback_text` is
non-empty. Each item's `text` is `""`. `--node <id>` for a decision id or a collapsed id is
rejected with a clear message and exit 2.

### 5. `narrate ingest <file>` subcommand

**Goal.** Load a filled worklist into `narratives.json`, pinning the signature at INGEST
and refusing to overwrite a FRESH approved entry. This is the only command that creates
new entries.

**Build.** In `graph_model.py`, function `cmd_narrate_ingest(args)`:
- Resolve `--model` / `--narratives` defaults; build the sig index; load existing
  `narratives.json` (absent → empty).
- Parse the input worklist file (the filled worklist from component 4). On JSON parse
  error or non-array, `die` (exit 2) with the parse error.
- **Validate ALL entries first, fail loud on any bad entry, no partial write (FM4).** For
  each entry: required keys present (`node_id`, `text`, `current_signature`); `node_id`
  exists in the sig index; `current_signature` matches `sig_index[node_id]` (the model may
  have been re-extracted between worklist generation and ingest — R1). Collect ALL errors;
  if any, `die` with a per-entry error list and exit 2; write nothing.
- For each VALIDATED entry, decide write/skip:
  - **Write** if no stored entry exists (absent).
  - **Write** if stored `status == "proposed"`.
  - **Write** if stored `status == "approved"` BUT stored signature does NOT match
    `sig_index[node_id]` (approved-but-stale — the F6 fix path). This is how a drifted
    approved node receives fresh text.
  - **Skip** (print a notice) if stored `status == "approved"` AND stored signature MATCHES
    `sig_index[node_id]` (FRESH approved — ingest must not overwrite).
- For each written entry, set the persisted entry to
  `{node_id, signature: current_signature (validated), text, status: "proposed"}`. This
  is the moment the signature is pinned.
- Write the whole `narratives.json` atomically via `_save_model` (component 8's writer).
  Print `"ingested N entries (M skipped fresh-approved)"`.

**Depends on.** Components 1, 2, 8.

**Assumes.** A3, A13, A14.

**Done when.** Given a valid filled worklist against the current model, ingest writes all
entries as `status: "proposed"` with `signature` pinned to the model's current signature.
Re-ingesting the SAME file against the same (unchanged) model skips every entry (all are
now FRESH approved or proposed) and writes nothing. Ingesting against a model re-extracted
since the worklist was generated rejects the whole batch with a per-entry list naming the
mismatched nodes (no partial write). Ingesting a malformed entry (missing key, unknown
node id, wrong signature) rejects the whole batch. Ingest never overwrites a FRESH
approved entry.

**Decisions (open for the planner).**
- Q: When ingest skips a FRESH approved entry, is the skip message per-id or a single count?
  Options: per-id (verbose) / single count (concise). Leaning single count — the entries
  that WERE written are the actionable output; skipped-fresh is informational.

### 6. `narrate approve <id> [<id>...]` subcommand

**Goal.** Flip `proposed`→`approved` per id, deny-by-default, mirroring
`decision_index refresh <id>` — but REFUSE any id whose signature has drifted since ingest
(no re-pin, no laundering old text as fresh).

**Build.** In `graph_model.py`, function `cmd_narrate_approve(args)`:
- Resolve `--model` / `--narratives` defaults; build the sig index; load `narratives.json`.
- For each id:
  - If the id is not in `narratives.json` → `die` (exit 2) with `"unknown node id <id>"`.
    Collect all unknown ids and fail loud (no partial approval).
  - If the stored `status != "proposed"` → `die` (exit 2) with
    `"node <id> is not proposed (status=<status>) — only proposed entries can be approved"`.
  - If the stored `signature` does NOT match `sig_index[node_id]` → `die` (exit 2) with:
    `"node <id> drifted since its text was written — re-run narrate worklist / narrate
    ingest to refresh the text, then approve"`. This closes the laundering hole (F6/F10).
- For each surviving id, flip `status` to `"approved"`. Do NOT touch `signature` (already
  pinned at ingest). Do NOT touch `text`.
- Write atomically via `_save_model`. Print `"approved N entries"`.

**Depends on.** Components 1, 2, 8.

**Assumes.** A15.

**Done when.** Given a proposed entry whose signature still matches the model, approve
flips it to `approved` and exits 0. Given an approved-but-stale entry (signature drifted
since ingest), approve refuses it with the drift message and exit 2 — the entry stays
`approved` with its old (now-stale) signature; the owner must re-run worklist→ingest to
get fresh text. Given an unknown id, approve fails loud. Approve never changes the
`signature` field and never changes the `text` field.

### 7. `narrate reject <id> [<id>...]` subcommand

**Goal.** Remove an entry from `narratives.json` so the node reverts to fallback text. No
approval or signature is retained.

**Build.** In `graph_model.py`, function `cmd_narrate_reject(args)`:
- Resolve `--narratives` default; load `narratives.json` (no model needed — reject does not
  check freshness, it just deletes). But still resolve the repo root for the default path.
- For each id: if not in `narratives.json` → `die` (exit 2) with `"unknown node id <id>"`
  (a typo must not silently succeed). Collect all unknown ids and fail loud.
- Remove each surviving entry. Write atomically via `_save_model`. Print
  `"rejected N entries"`.

**Depends on.** Components 1, 8 (no sig index, no model load).

**Done when.** Given entries that exist, reject removes them and the nodes revert to
fallback text on the next `narrate status`. Given an unknown id, reject fails loud (exit 2)
and writes nothing. A rejected node still in scope re-appears in the next worklist
(accepted limitation — OQ-DECLINED-1, deferred to P6).

### 8. `narrate status` subcommand + derived-status engine

**Goal.** Report the full picture: every stored entry (regardless of how it entered
scope) UNION every in-scope node with no entry, each labeled with its DERIVED status.
Derived status is computed live and is NEVER written to `narratives.json`.

**Build.** In `graph_model.py`:
- A function `_derive_status(stored_entry, current_sig) -> str` implementing the Block 5a
  derivation:
  - `approved` — stored `status == "approved"` AND stored signature matches current.
  - `proposed` — stored `status == "proposed"` AND stored signature matches current.
  - `stale` — stored entry (proposed or approved) whose stored signature does NOT match
    current.
  - `orphaned` — stored entry whose `node_id` is absent from the current model's sig index.
  - `none` — in-scope node with no stored entry.
- A function `cmd_narrate_status(args)`:
  - Resolve `--model` / `--narratives` defaults; build the sig index; load `narratives.json`.
  - Scope = ALL stored entries UNION in-scope nodes with no entry (F9 fix — this ensures an
    entry approved via `--include-nanos` that is now below threshold is STILL watched for
    drift; it is not an orphan, its node exists, but it is watched). "In-scope" here =
    default worklist scope (components + micros + threshold/export nanos; NOT
    `--include-nanos`, which is a worklist-only flag — but EVERY stored entry is included
    regardless of scope).
  - Print one line per entry/node: `id | kind | derived_status`, sorted by id for stability.
  - Exit 0 always (advisory). `--strict` non-zero exit is deferred to P6 (OQ-STRICT-1).

**Depends on.** Components 1, 2.

**Assumes.** A1, A2, A9, A14 (an approved-but-stale entry shows as `stale`, not
`approved`).

**Done when.** Given the golden model and an empty `narratives.json`, status reports one
`none` line per in-scope node (and nothing for out-of-scope emitted nanos, collapsed, or
decisions). Given an approved entry whose code has drifted, status shows `stale` (NOT
`approved`). Given an entry whose `node_id` no longer exists in the model (renamed/deleted
function), status shows `orphaned`. Given an entry approved via `--include-nanos` for a
nano now below threshold, status still shows that entry (it is watched, not invisible —
F9 fix). Status never writes to `narratives.json`. Status exits 0.

### 9. CLI wiring (`narrate` subparser group in `build_parser`)

**Goal.** Wire the five subcommands into `build_parser()` so `graph_model.py narrate …`
dispatches to them, with the correct default paths and flags — without touching the
existing `extract` / `bootstrap-config` subcommands.

**Build.** In `build_parser()` (`graph_model.py:953`), after the existing subparsers:
```
narrate = sub.add_parser("narrate", help="plain-language narrative sidecar")
narrate_sub = narrate.add_subparsers(dest="narrate_cmd", required=True)

pw = narrate_sub.add_parser("worklist", help="list nodes needing a sentence")
pw.add_argument("--model", help=f"path to diagram-model.json (default: <root>/{DEFAULT_OUTPUT_REL})")
pw.add_argument("--narratives", help="path to narratives.json (default: <root>/ssot-diagram/narratives.json)")
pw.add_argument("--config", help=f"path to config (default: <root>/{DEFAULT_CONFIG_REL})")
pw.add_argument("--include-nanos", action="store_true", help="force all visible nanos into scope")
pw.add_argument("--node", help="add exactly one node id to scope")
pw.add_argument("-o", "--out", help="output file (default: stdout)")
pw.set_defaults(fn=cmd_narrate_worklist)

pi = narrate_sub.add_parser("ingest", help="load a filled worklist into narratives.json")
pi.add_argument("file", help="filled worklist JSON file")
pi.add_argument("--model", ...)
pi.add_argument("--narratives", ...)
pi.add_argument("--config", ...)
pi.set_defaults(fn=cmd_narrate_ingest)

pa = narrate_sub.add_parser("approve", help="flip proposed→approved per id")
pa.add_argument("ids", nargs="+", help="node ids to approve")
pa.add_argument("--model", ...)
pa.add_argument("--narratives", ...)
pa.add_argument("--config", ...)
pa.set_defaults(fn=cmd_narrate_approve)

pr = narrate_sub.add_parser("reject", help="remove entries per id")
pr.add_argument("ids", nargs="+", help="node ids to reject")
pr.add_argument("--narratives", ...)
pr.add_argument("--config", ...)
pr.set_defaults(fn=cmd_narrate_reject)

ps = narrate_sub.add_parser("status", help="report derived status of all entries + in-scope nodes")
ps.add_argument("--model", ...)
ps.add_argument("--narratives", ...)
ps.add_argument("--config", ...)
ps.set_defaults(fn=cmd_narrate_status)
```
(Exact flag-set/per-arg defaults left to the planner; the shapes above are the contract.)

**Depends on.** Components 4–8 (all subcommand functions must exist before wiring).

**Assumes.** A8.

**Done when.** `python3 graph_model.py narrate --help` lists the five subcommands.
`narrate worklist` with no subcommand fails with exit 2 and a message pointing at the
subcommands (argparse `required=True`). `graph_model.py extract` and
`graph_model.py bootstrap-config` are unchanged (no regression). `--model` / `--narratives`
absent resolves to the repo-root-derived defaults.

### 10. `narratives.json` writer + format

**Goal.** A byte-deterministic `narratives.json` matching the Block 5a entry shape and the
repo's writer convention, so identical inputs ⇒ byte-identical output.

**Build.** In `graph_model.py`:
- The top-level shape is `{"narratives": {node_id: entry, ...}}` (mirrors
  `decision_index.py`'s `{"decisions": {...}}` key). Each entry is exactly
  `{node_id, signature, text, status}` with `status` ∈ `{proposed, approved}` — no fifth
  field, no `stale`, no `generated_at`.
- The writer REUSES `_save_model` (`graph_model.py:796`) directly:
  `_save_model(narratives_path, {"narratives": entries_dict})`. Because `_save_model` uses
  `sort_keys=True`, the `node_id` keys AND the per-entry field keys are ordered
  automatically — NO separate sort step (F2 fix). `indent=2`, `ensure_ascii=False`, trailing
  `"\n"`, atomic `os.replace`.
- Build `entries_dict` deterministically: iterate the in-memory narratives dict and write
  it; `sort_keys=True` handles ordering at serialization.

**Depends on.** Component 1 (path), and is consumed by components 5/6/7.

**Assumes.** A3, A13.

**Done when.** Two runs of `narrate ingest` against the same worklist + same model produce
byte-identical `narratives.json` (sha256 equal). The file has no `generated_at` field, no
`stale` value anywhere. Keys are sorted. The file ends with a single `"\n"`. An
`os.replace` interruption leaves a `.narratives.json.tmp` file and an intact
`narratives.json` (the previous version). The serialization matches
`json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` exactly.

### 11. Config schema additions + manifest entry

**Goal.** Add the two new optional config keys and register P4 in `manifest.json`.

**Build.**
- `ssot-diagram.config.json`: add `"narrate_threshold": 4` and
  `"narratives_path": "ssot-diagram/narratives.json"` as optional keys. Version stays 1.
  (The seed config is updated; existing configs without these keys use the defaults from
  component 1.)
- `manifest.json`: add a `narrative-sidecar` entry under `scripts`:
  `{script: "ssot-diagram/graph_model.py", scope: "repo", desc: "ssot-diagram P4 — narrate
  subcommands: plain-language sidecar for diagram nodes, signature-pinned", hooks: []}`.
  (OQ-MANIFEST-1 RESOLVED 2026-07-06 owner: separate `narrative-sidecar` key chosen —
  P4 is a distinct phase with its own subcommands, so it gets its own `piggyback status`
  line; `diagram-model`'s desc stays P3-only.)

**Depends on.** Component 1 (so the config keys are read by the reader that defines them).

**Assumes.** None new.

**Done when.** `piggyback status` lists the `narrative-sidecar` tool. A config with the
two new keys is read correctly by component 1's reader. A config WITHOUT the two new keys
(every existing config) still works — `narrate status` returns defaults.

### 12. Tests

**Goal.** Prove the contract holds: signature pinning, no laundering, no stale-storage,
deterministic output, exclusion of decisions/collapsed, the F6 round-trip
(worklist→ingest→drift→approve-refuses→ingest→approve).

**Build.** In `ssot-diagram/test_graph_model.py` (extend the existing test file; P4's
tests live beside the code, matching P3's convention). Tests:
- **T1 — sig index is complete + excludes collapsed + decisions.** Against the golden
  model, the index has `405` entries; no collapsed or decision id; no `None` values.
- **T2 — fallback text per kind.** nano with docstring ends at sentence boundary; nano
  with separator-bar docstring has bars stripped (use a fixture: the real
  `validatePixelSize`/`EditTopBar`/`ResizeTool` shape); nano with no docstring has no
  trailing docstring clause; nano with no-period docstring returns ≤70 chars non-empty;
  micro counts non-collapsed children (the `micro:lib/canvas/store.ts` case → `8`, not
  `9`); component counts non-collapsed child micros. No fallback is empty. No fallback
  raises on a real-model node.
- **T3 — worklist scope.** Empty `narratives.json` → worklist = all in-scope nodes; no
  collapsed/decision. `--include-nanos` widens to all visible nanos. `--node <decision id>`
  and `--node <collapsed id>` are rejected (exit 2). Each item's `current_signature`
  matches the model; each `text` is `""`.
- **T4 — ingest pins at ingest + skips FRESH approved.** Ingest a valid worklist → all
  entries `proposed`, signature pinned to model. Re-ingest same file (unchanged model) →
  all skipped (fresh), nothing written. Ingest a malformed entry → whole batch rejected,
  no partial write. Ingest against a re-extracted model (signature changed) → batch
  rejected with per-entry list.
- **T5 — approve refuses drift (F6 laundering hole).** Ingest + approve a node (model
  unchanged) → `approved`, exit 0. Drift the model (swap the golden for a fixture whose
  node signature differs) → approve on the now-stale approved entry REFUSES with the drift
  message, exit 2, signature unchanged, text unchanged.
- **T6 — approved-but-stale gets fresh text via ingest (F6 path).** Take an
  approved-but-stale entry. `narrate worklist` lists it (stale). Ingest fresh text → entry
  rewritten as `proposed` with the new text and the new (current) signature. Approve →
  `approved`. No `reject` needed. This is the one-step refresh path F6 demanded.
- **T7 — derived status (Block 5a).** `none` / `proposed` / `approved` / `stale` /
  `orphaned` each exercise a fixture. `stale` is NEVER written to the file (assert the
  file contains no `"stale"` string anywhere after a `status` run). An entry approved via
  `--include-nanos` for a nano now below threshold still appears in `narrate status` (F9
  fix). Status exits 0.
- **T8 — byte-determinism.** Two `narrate ingest` runs against the same worklist + model
  produce byte-identical `narratives.json` (sha256 equal). No `generated_at` field. Keys
  sorted. Trailing newline + `ensure_ascii=False`.
- **T9 — reject.** Existing entries removed; node reverts to fallback. Unknown id → exit 2,
  no write.
- **T10 — `narrate status` never writes.** Run `narrate status` on a repo; assert
  `narratives.json` mtime unchanged (read-only command).
- **T11 — P1/P3 regression clean.** `decision_index status` still exits 0;
  `graph_model.py extract` still produces byte-identical golden (sha256 `56df3d86…`);
  `python3 -m pytest ssot-diagram/` still green (existing 32 tests + new P4 tests).

**Depends on.** Components 1–11 (tests are last).

**Assumes.** A1–A15 (each test maps to one or more assumptions).

**Done when.** `python3 -m pytest ssot-diagram/` is green (existing 32 + new P4 tests, golden
NOT skipped — pilot DB present). The F6 round-trip (T5+T6) passes. `narratives.json`
contains no `"stale"` string. `narrate status` is read-only (T10). P3 golden sha256
unchanged.

## Handoff notes

- **Contract with P5 (renderer) + Phase F (biography):** P4 writes `narratives.json` as
  `{"narratives": {node_id: {node_id, signature, text, status}}}` with `status` ∈
  `{proposed, approved}`. P5/F MUST compute derived status themselves via signature
  comparison (Block 5a/5b consumer obligation) — they MUST NOT read `status` literally
  and trust `approved` without the signature check, or they will render drifted prose as
  current. P4 exposes this contract; it does not implement their reading. P5/F also use
  `_fallback_text` (component 3) when no entry exists for a node — that function is public
  to the module (`_fallback_text`), not private to the `narrate` subcommands.
- **Contract with P6 (PostToolUse re-extract hook):** P6 will wire a hook that re-runs
  `extract` on code change and then `narrate status` to surface drift. P4's `narrate
  status --strict` (non-zero exit on any stale/orphaned) is deferred to P6 — P4's `status`
  is advisory (exit 0). P6 also owns the orphaned-narrative `gc` (OQ-GC-1) and the
  declined-marker (OQ-DECLINED-1).
- **Resolved (editorial, human-authority):** OQ-MANIFEST-1 RESOLVED 2026-07-06 —
  separate `narrative-sidecar` manifest key (not extending `diagram-model`'s desc).
  Chosen so P4's five `narrate` subcommands get their own `piggyback status` line; both
  entries share the same `graph_model.py` script with `hooks: []`.
- **Open uncertainty (operating burden, human-authority):** `narrate_threshold` default =
  4 is an owner-tunable knob that sets how many nanos the non-coder owner is asked to
  narrate. It is settable in `ssot-diagram.config.json` and RATIFIED by the owner
  (design revision log). It does NOT need re-approval at build — the owner already chose
  4 as the seed ("a handful of callers"). If the pilot shows the worklist is too long,
  the owner raises it in the config; no code change.
- **Suggested research (for factual-code-verification):** confirm A7 (`load_config`'s
  `die()` paths) and A10 (`di.die` exit code) by reading the function bodies — these two
  were explicitly deferred from the design step ("to confirm at the spec step") and THIS
  spec author has read them (A7 confirmed 5 `die` paths; A10 confirmed exit 2), but the
  verification step must re-confirm independently per rule 3 (it trusts code, not the spec
  or the spec author's reads). Also confirm A3 (`_save_model` is generic) by reading its
  body — this spec author read it via codegraph (generic, no model-specific keys), but
  verification must re-check.
- **Read-set warm-start for the planner:** the design doc's `## Read-set` lists the exact
  files surveyed. The planner should start from those, not re-survey. The load-bearing
  symbols are: `_save_model` (`graph_model.py:796`), `build_parser` (`:953`),
  `cmd_extract` (`:810`), `load_config` (`:72`), `_sorted_sha256` (`:64`),
  `DEFAULT_OUTPUT_REL` (`:30`), `DEFAULT_CONFIG_REL` (`:29`), and on `decision_index.py`:
  `die` (`:327`), `find_db`/`repo_root_for` (re-exported `:49`), `default_index_path`
  (`:65`). The golden model is `testdata/mkt_engine.model.json`.

## Open Questions (deferred — do NOT resolve in this spec)

- **OQ-STRICT-1 (P6):** `narrate status --strict` non-zero exit. Advisory for P4; strict
  is P6. Precedent: `decision_index status`.
- **OQ-GC-1 (P6):** `narrate gc` to bulk-remove orphaned entries. Low blast radius
  (orphans are inert); manual `narrate reject <id>` suffices for P4.
- **OQ-DECLINED-1 (P6):** persisted "declined" marker for rejected-in-scope nodes.
  Without it, a rejected node re-appears in the next worklist. Mirrors Block 1c rail picker.
- **OQ-MANIFEST-1 (RESOLVED 2026-07-06):** separate `narrative-sidecar` manifest key
  chosen. Editorial, human-authority (product) — resolved.
