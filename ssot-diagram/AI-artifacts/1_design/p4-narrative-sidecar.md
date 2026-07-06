# P4 — Narrative Sidecar (design)

_P4 adds plain-language text to every model node, kept honest by signature
pinning. An LLM proposes text; a human approves it; nothing unapproved or
out-of-date renders as trusted prose. The deterministic fallback means the
diagram is always readable, even before any approvals._

> Survey step grounded against the live P3 code (graph_model.py commit `ba02a56`),
> the golden model `testdata/mkt_engine.model.json`, and the frozen contracts.
> No items in this doc are TBD/placeholder — every open question is explicitly
> labelled and deferred to the spec step.

## Revision log

Revised 2026-07-06 after red-team (findings F1–F10) + owner decisions:

- **Block 5a amended 2026-07-06:** `stale` is NEVER stored; stored status is exactly `proposed|approved`; derived status (stale, orphaned, none) is computed by consumers via signature comparison. (F1)
- **Decision nodes EXCLUDED** from narration scope entirely. (F3/F5)
- **Threshold kept and reconciled:** `narrate_threshold` is owner-tunable; it filters within visible (≤ nano_cap) nanos; both knobs coexist. (F4)
- **Ingest→approve state machine fixed:** signature is pinned at INGEST (not at approve); approve only flips `proposed` → `approved` and REFUSES a drifted entry rather than re-pinning. (F2/F6/F10)
- Worklist output confirmed as JSON array. (OQ-2 resolved)
- `narrate status` scope clarified: ALL stored entries UNION in-scope nodes. (F9)
- Fallback child counts exclude collapsed children. (F8)
- `narratives.json` writer: `sort_keys=True` on a dict container — redundant sorted-order language removed. (F2)
- `narrate` uses a PERMISSIVE config reader, never `load_config`. (F4)

---

## Cast of characters

| Symbol | Role |
|---|---|
| `graph_model.py` | P3 extractor — P4 adds three subcommands to this file |
| `diagram-model.json` | P3's output; P4 reads it to build its id→signature index |
| `narratives.json` | P4's output — one entry per approved/proposed node narrative |
| `narratives_path` | Config-driven path to `narratives.json` (default: `ssot-diagram/narratives.json`) |
| Block 5a | The frozen 4-field entry shape: `{node_id, signature, text, status}` — **amended 2026-07-06: stored status is exactly `proposed\|approved`; `stale` is NEVER stored** |
| Block 5b | The trust rule: nothing renders as trusted unless `approved` AND signature matches |
| `_sorted_sha256` | Existing helper in `graph_model.py` — sha256 over a sorted list of strings |
| `_save_model` | Existing atomic writer in `graph_model.py` — P4 reuses this pattern |

---

## Summary

P4 is the only inference layer in the ssot-diagram stack. It gives a non-coder
a plain-language sentence for every node in the diagram (component, file, and
function), while keeping the deterministic foundation honest: every sentence is
pinned to the code's content signature, and any sentence whose code has drifted
is visibly marked stale — never silently current.

The implementation lives entirely in the existing `graph_model.py` script as
three new subcommands under the `narrate` group. No new file is created beyond
`narratives.json`. P4 reads the already-emitted `diagram-model.json` (never the
DB directly) and reuses the same atomic-write pattern (`_save_model`) and sha256
helpers (`_sorted_sha256`) already in that file. The sibling import of
`decision_index as di` (graph_model.py:27) continues to supply `di.die`,
`di.open_db`, and `di.find_db` for any path resolution; P4 needs no new DB
access.

The four frozen entry fields (Block 5a: `node_id`, `signature`, `text`,
`status`) are the only fields P4 writes. **Block 5a was amended 2026-07-06
(owner-ratified): stored `status` is exactly `proposed|approved`; `stale` is
NEVER stored in `narratives.json`.** Derived states (`proposed`, `approved`,
`stale`, `orphaned`, `none`) are computed by consumers at READ time via live
signature comparison — never persisted. This is a ratified contract amendment,
not P4's own interpretation.

`decision` nodes are EXCLUDED from P4 narration scope entirely. One ADR fans
out to N decision nodes (verified: golden model has 11 decision nodes for 8
ADRs — ADR-0001/0003/0007 each appear twice, once per component), so narrating
each would mean writing the same sentence 2–3×. Decisions already carry their
ADR name + FRESH/STALE status badge, and the ADR file itself is the human prose.

No OPEN (human-authority) items were identified. P4 is a local CLI tool — no
external services, no payments, no auth, no vendor lock-in, no CI-gate. The
`narrate status --strict` non-zero exit is deferred to P6 as noted.

---

## Constraints

These bind this design and cannot be redesigned.

**From Block 5a (amended 2026-07-06, owner-ratified):** each entry in
`narratives.json` is exactly `{node_id, signature, text, status}` where stored
`status` is `proposed|approved` only. `stale` is NEVER stored — it is a derived
output of the signature comparison that consumers MUST compute themselves. No
fourth field may be added without a contract revision.

**From Block 5b (FROZEN):** the renderer and biography tool (P5/F) may only
treat an entry as trusted when `status == approved` AND the stored
`signature` matches the current `diagram-model.json` node's `signature`. P4's
`narrate worklist` and `narrate status` derive staleness from this comparison —
they do NOT write a `stale` status to the file; `stale` is a computed display
state, not a persisted badge.

**From Block 4b (FROZEN):** every model node carries a deterministic `id` and
`signature`. P4 pins prose to the `signature` field of the model node at the
moment of INGEST (not approve — see §ingest). A single content-change causes a
re-extract (new signature) and the narrative is immediately seen as stale on
next worklist run.

**From CLAUDE.md (repo-wide):** read-only DB (`mode=ro&immutable=1`). P4 never
touches `.codegraph/codegraph.db`; it reads only `diagram-model.json`.
Byte-deterministic writer (`sort_keys=True`, `generated_at` absent or null,
atomic temp+`os.replace`). Sibling import of `decision_index as di` for shared
helpers. No new dependencies — stdlib only.

**From the Locked Design (2026-07-06 grill):**

1. `narrate` reads `diagram-model.json`, not the DB. The id→signature index is
   built by walking `components[].children[].children[]` (the NESTED layout P3
   emits). Decision nodes are EXCLUDED from the index and from all narration scope.
2. Approval is command-per-id, deny-by-default. The file is never hand-edited
   into a broken state; every mutation goes through the CLI.
3. Four subcommands: `worklist`, `ingest`, `approve`, `reject`, `status`.
4. Scope threshold: nanos gated by `is_exported OR caller_count >= narrate_threshold`
   (default 4), operating ONLY over EMITTED (non-collapsed) nanos. Collapsed nodes
   (`kind == "collapsed"`) are excluded entirely.
5. Deterministic fallback text per kind (pure function of node fields only).
6. Staleness derived at read time; `extract` never writes `narratives.json`.
7. `narratives.json` serialized with `sort_keys=True`, atomic write.

**Real node fields (verified against golden `testdata/mkt_engine.model.json`):**

- `nano`: `id`, `kind`, `name`, `qualified_name`, `path`, `signature`,
  `caller_count` (int), `docstring` (string, may be empty), `is_exported` (bool),
  `edges[]`, `decisions[]`. No `start_line`/`end_line` in the emitted JSON.
- `micro`: `id`, `kind`, `name`, `path`, `signature`, `dominant_class`
  (string or null), `children[]`, `edges[]`, `decisions[]`. No `caller_count`.
- `component`: `id`, `kind`, `name`, `path`, `signature`, `children[]`,
  `edges[]`, `decisions[]`. No `caller_count`.
- `collapsed`: `id`, `kind`, `name`, `collapsed_count`, `signature`. Always
  excluded from P4 scope.
- `decision`: `id`, `kind`, `name`, `doc`, `status`, `signature`. **EXCLUDED
  from P4 narration scope entirely** — decisions carry their ADR name + freshness
  badge; the ADR file is the human prose.

---

## Alternatives Considered

### Alternative A — Worklist as JSON array (chosen approach)

The worklist emitted by `narrate worklist` is a JSON array (one object per
node), written to `-o <file>` or stdout. A machine (LLM session or script)
reads it, fills in the `text` field on each entry, and saves the filled file.
`narrate ingest` validates and loads the result into `narratives.json`.

JSON is the right format here because: the worklist carries multiple structured
fields per node (id, kind, name, fallback text, current signature, and whatever
context fields are useful); the downstream consumer is an LLM session that
already handles JSON fluently; and validation at ingest is straightforward
(check required keys, check signature still matches). A human reading a JSON
worklist sees the structure without needing a parser.

The alternative was a Markdown table worklist — one row per node, columns for
id / kind / name / text. It is more human-readable but loses structure: the
`|` delimiter is ambiguous in prose, ingest parsing is brittle (multiline text
in a cell), and signature pinning must be carried as a hidden column or
attached file. JSON wins on round-trip fidelity.

### Alternative B — Per-node approve command vs. batch approve file

The approve step could be: (B1) a single command taking one or more ids
(`narrate approve <id> [<id>...]`, which is the chosen approach); or (B2) an
"approved.txt" file listing approved ids that the CLI reads; or (B3) a
whole-file "approve all proposed" command.

B1 is chosen because it mirrors `decision_index refresh <id>` exactly — the
same deny-by-default, explicit-per-id gate that `decision_index` uses for
marking a decision verified. Each approval is a deliberate human act with a
named node. B2 (a side file) creates a second source of truth that can drift
from `narratives.json`. B3 ("approve all") bypasses the gate entirely — it
would let LLM-proposed text silently become trusted without a human touching
each entry, which violates Block 5b's intent.

### Alternative C — Staleness as a stored field vs. derived at read time (chosen: derived, RATIFIED)

Staleness could be stored as a third status value in `narratives.json`
(alongside `proposed` and `approved`), updated whenever `narrate` runs. This
would make the file self-describing without needing `diagram-model.json` nearby.

The problem: a stored stale flag is a mutation side-effect of a read-only
operation (checking freshness). Two processes running `narrate status`
concurrently could both write `stale` entries in conflicting order. More
importantly, storing `stale` in the file means the file can lie: a `stale`
entry that was re-approved without re-running `narrate` stays stale forever.
Deriving staleness at read time from the live model signature comparison is
always accurate and has no side-effects.

**This is RATIFIED — Block 5a amended 2026-07-06 by the owner.** Stored status
is exactly `proposed|approved`. `stale` is NEVER stored. The renderer, `narrate
status`, and any biography tool MUST compute derived status via signature
comparison themselves — reading stored `status` literally and trusting
`approved` without the signature check would render drifted prose as current.

---

## Chosen Approach

**New subcommand group `narrate` added to `graph_model.py`.** The existing
`build_parser()` function (`graph_model.py:953`) gains a `narrate` parent
subparser with five child subcommands. No new Python file. The `narratives.json`
writer reuses `_save_model`'s atomic temp+`os.replace` pattern
(`graph_model.py:796–805`) with `sort_keys=True`. The file lives at
`ssot-diagram/narratives.json` by default (configurable via config key
`narratives_path`).

**Config reading:** `narrate` MUST NOT call the strict `load_config`
(graph_model.py:72–120) — that function calls `di.die()` on missing
`version`/`components`/`default_component` keys, which would abort a read-only
`narrate status` run. Instead, `narrate` reads `narrate_threshold` and
`narratives_path` via a small PERMISSIVE reader: load the config JSON if present
and `.get()` the two keys with explicit defaults (threshold=4, default
narratives_path); if the config file is absent, use defaults. Scope
(components/micros/nanos) comes from the MODEL, not the config — narrate never
needs `load_config`'s validated components list.

### CLI surface

```
graph_model.py narrate worklist [--model MODEL] [--narratives NARR]
                                [--include-nanos] [--node <id>]
                                [-o <file>]
graph_model.py narrate ingest <file> [--model MODEL] [--narratives NARR]
graph_model.py narrate approve <id> [<id>...] [--model MODEL] [--narratives NARR]
graph_model.py narrate reject <id> [<id>...] [--narratives NARR]
graph_model.py narrate status [--model MODEL] [--narratives NARR]
```

All five subcommands default `--model` to `<repo-root>/ssot-diagram/diagram-model.json`
(the existing `DEFAULT_OUTPUT_REL`) and `--narratives` to
`<repo-root>/ssot-diagram/narratives.json`. Finding repo root uses
`di.find_db` + `di.repo_root_for` (same pattern as `cmd_extract` at
`graph_model.py:812–815`).

### `narrate worklist`

Produces a list of nodes that NEED text: every node with no stored entry
(`status == "none"`) or whose stored signature does not match the current model
node signature (`status == "stale"`). Output is a JSON array, one object per
node, written to `-o <file>` or stdout.

**Default scope:** every component + every micro + EMITTED nanos (kind == "nano",
excluding "collapsed") where `is_exported OR caller_count >= narrate_threshold`.
`decision` nodes are EXCLUDED from scope entirely. Collapsed nodes
(`kind == "collapsed"`) are always excluded.

Nano scope operates ONLY over nanos that P3 emitted (i.e., within the nano_cap
per micro). Nanos that P3 collapsed away (beyond `nano_cap` per micro) are NOT
narratable — they have no addressable node_id and are not shown in the diagram.
Both knobs coexist: `nano_cap` (P3) caps what is DISPLAYED; `narrate_threshold`
(P4, owner-tunable, default 4, settable in `ssot-diagram.config.json`) further
filters which displayed nanos need a hand-written sentence. If the threshold is
≤ the lowest visible caller_count, it is a no-op beyond what nano_cap already
filtered.

`--include-nanos` forces ALL visible (non-collapsed) nanos into scope regardless
of threshold. `--node <id>` adds exactly one specific node (component, micro, or
nano — not decision, not collapsed) whether or not it falls within the default
scope.

Each worklist item:
```json
{
  "node_id": "nano:requireEnv@lib/ai/llm/providers/openai-compat/index.ts",
  "kind": "nano",
  "name": "requireEnv",
  "current_signature": "<hex>",
  "fallback_text": "requireEnv — function, 3 callers.",
  "text": ""
}
```

The `text` field is intentionally blank — an LLM session fills it in and the
filled file is passed to `narrate ingest`. `fallback_text` is the
machine-derived text (see §Deterministic fallback text); it is informational,
never persisted as an approved narrative.

### `narrate ingest <file>`

Loads a filled worklist into `narratives.json`. **Signature is pinned at ingest,
not at approve.** The full state-machine:

1. **Validate ALL entries first** (fail loud if any entry is malformed, its
   `node_id` is absent from the model, or its `current_signature` no longer
   matches the model node's current signature — the model may have been
   re-extracted between worklist generation and ingest). A single bad entry
   rejects the entire ingest with a clear per-entry error list (no partial write).
2. For each validated entry, determine whether it should be written:
   - **Write** if the node has no current stored entry (absent).
   - **Write** if the stored entry has `status: proposed`.
   - **Write** if the stored entry has `status: approved` BUT its stored
     signature does not match the current model node signature (approved-but-stale).
     This is the path that allows an approved-but-stale node to receive fresh text.
   - **Skip** (print a notice) if the stored entry has `status: approved` AND
     its stored signature matches the current model node signature (FRESH approved
     entry). Ingest MUST NOT overwrite a FRESH approved entry.
3. Write accepted entries as `status: proposed` with `signature` set to
   `current_signature` (the value from the worklist item, already validated as
   matching the current model node). This is the moment the signature is pinned.

On success, all accepted entries are written atomically into `narratives.json`.

### `narrate approve <id> [<id>...]`

Flips `status: proposed` → `status: approved` for each given id. **Approve does
NOT re-pin the signature** — the signature was already pinned at ingest and is
not changed by approve.

Preconditions checked before flipping:
- The id must exist in `narratives.json` (unknown id → fail loud, exit 2).
- The stored entry's `signature` must still equal the current model node's
  `signature`. If the model was re-extracted after ingest (entry is now stale),
  approve REFUSES that id with a clear message:

  > "node `<id>` drifted since its text was written — re-run `narrate worklist`
  > / `narrate ingest` to refresh the text, then approve."

  This closes the laundering hole: it is impossible to approve old text as fresh,
  because approve refuses any entry whose code has drifted since ingest.

Because ingest already pinned the signature to the validated-current value, a
normal ingest→approve workflow with no intervening `extract` just flips the
status; no re-pin is needed or attempted.

Multiple ids allowed in one command. Fails loud (exit 2) on any unknown id or
any drifted id. Writes atomically.

### `narrate reject <id> [<id>...]`

Removes the entry from `narratives.json`. The node reverts to fallback text.
No approval or signature is retained. Fails loud if any id is not currently in
`narratives.json` (so a typo doesn't silently succeed).

Accepted limitation: a rejected node that is still in scope re-appears in the
next `narrate worklist` run (no persisted "declined" marker). A "declined vs
never-seen" distinction (precedent: Block 1c rail picker) is DEFERRED to P6 —
see OQ-DECLINED-1.

### `narrate status`

**Scope: ALL stored entries UNION in-scope nodes with no entry.** This ensures
every approved entry is watched for drift regardless of threshold or
`--include-nanos` scope — an entry approved with `--include-nanos` that is now
below threshold is still watched.

Prints one line per entry/node: `id | kind | derived_status`. Derived status:
- `approved` — stored `status == "approved"` AND stored signature matches current
  model node signature.
- `proposed` — stored `status == "proposed"` AND stored signature matches current
  model node signature.
- `stale` — stored entry (proposed or approved), but stored signature does not
  match current model node signature.
- `orphaned` — stored entry whose `node_id` is absent from the current model.
- `none` — in-scope node with no stored entry.

Derived status is NEVER written to `narratives.json`; it is a display label only.

Exit 0 always (advisory). `--strict` non-zero exit is deferred to P6
(OQ-STRICT-1).

### `ssot-diagram.config.json` — new fields

```json
{
  "version": 1,
  "...",
  "narrate_threshold": 4,
  "narratives_path": "ssot-diagram/narratives.json"
}
```

`narrate_threshold` (int, optional, default 4): owner-tunable operating-burden
knob (seed value = "a handful of callers"). Sets the minimum `caller_count` for
a non-exported nano to enter the default worklist scope (`is_exported OR
caller_count >= narrate_threshold`). Owner ratified keeping this knob
2026-07-06. Settable in `ssot-diagram.config.json`; CLI `--narratives` overrides
`narratives_path`.

`narrate` reads these two keys via a PERMISSIVE reader (`.get()` with defaults),
never via `load_config`. If the config file is absent, defaults are used. Scope
(which components/micros/nanos to include) comes from the MODEL structure, not
from the config.

### `narratives.json` format

```json
{
  "narratives": {
    "nano:requireEnv@lib/ai/llm/providers/openai-compat/index.ts": {
      "node_id": "nano:requireEnv@lib/ai/llm/providers/openai-compat/index.ts",
      "signature": "<hex — pinned at ingest time>",
      "text": "Reads required environment variables and raises an error if any are missing.",
      "status": "approved"
    }
  }
}
```

Top-level key `"narratives"` (mirrors `decision_index.py`'s `"decisions"` key).
Entries keyed by `node_id` for O(1) lookup. Serialized with `sort_keys=True`
(inherits `_save_model` exactly: `json.dumps(model, indent=2, sort_keys=True,
ensure_ascii=False) + "\n"`). Since `sort_keys=True` orders dict keys
alphabetically, the node_id keys are ordered automatically — no separate sorting
step is needed or performed. No `generated_at` field. Atomic write:
`narratives.json.tmp` → `os.replace` to `narratives.json`. Determinism tests
must compare output against this exact serialization (trailing newline,
`ensure_ascii=False`).

### Deterministic fallback text

Pure function of model node fields (never blank, no DB access needed). Built by
a `_fallback_text(node: dict) -> str` function in `graph_model.py`. Recipes by
kind, using ONLY the fields present in the real golden model. `decision` nodes
are excluded from P4 scope and have no fallback recipe.

**nano:**
```
"<name> — function, <caller_count> caller(s). <first_sentence_of_docstring>"
```
If `docstring` is empty or contains only separator lines (`──`, `---`, `===`),
omit the docstring clause. First-sentence extraction: strip leading lines that
match `^\s*[-─=]+\s*$`; take the remaining text up to the first period followed
by a space, newline, or end-of-string. If no period is found, take the first
70 characters of cleaned text.

Example: `"requireEnv — function, 3 caller(s)."` (no docstring in live pilot)
Example: `"verifySession — function, 8 caller(s). Verify a session is valid and return the owning user, or null."`

**micro:**
```
"<name> — file, <N> function(s)."
```
Where N = count of children where `kind != "collapsed"` (i.e., non-collapsed
children only). Uses the real `micro.name` field (e.g. `"session.ts"`).
Example: `micro:lib/canvas/store.ts` with 8 nano children + 1 collapsed child
→ `N = 8` → `"store.ts — file, 8 function(s)."`.

**component:**
```
"<name> — component, <N> file(s)."
```
Where N = count of children where `kind != "collapsed"` (non-collapsed micro
children only). Uses `component.name` (e.g. `"lib"`).

### How `narrate` builds the id→signature index

Walking the NESTED model structure (`cmd_extract` emits `components[].children`
= micros, `micros[].children` = nanos — confirmed by the golden model and
`cmd_extract` at `graph_model.py:879–934`). Decision nodes are EXCLUDED.

```
index = {}
for comp in model["components"]:
    index[comp["id"]] = comp["signature"]
    for micro in comp["children"]:
        index[micro["id"]] = micro["signature"]
        for child in micro["children"]:
            if child["kind"] != "collapsed":
                index[child["id"]] = child["signature"]
```

This builds a complete id→signature map in one pass over components→micros→nanos
only. All five subcommands load this index once and hold it in memory.

### Manifest registration

P4 adds a `narrative-sidecar` entry to `manifest.json` (or extends the existing
`diagram-model` entry's `desc`). Since `narrate` subcommands are purely CLI
with no hook events, `hooks: []`. The script path is the same
`ssot-diagram/graph_model.py`.

OPEN (human-authority: product): whether to add a separate `narrative-sidecar`
key or extend `diagram-model`'s desc — preference is editorial, not technical.

---

## Risks

- **R1 — Model re-extracted between worklist generation and ingest.** A user
  generates a worklist, re-runs `extract` (the model's signatures update), then
  ingests. The ingest signature check will catch every node whose signature
  changed and reject those entries. Mitigation: ingest validates each entry's
  `current_signature` against the current model before writing; clear per-entry
  error messages name the mismatched node so the user can re-generate a targeted
  worklist with `--node <id>`.

  The ingest→approve window is safe: if the model is re-extracted after ingest
  but before approve, the stored entry's signature no longer matches the current
  model node signature — approve detects this and refuses the id with a clear
  message. There is no way to approve drifted text as fresh.

- **R2 — Docstring separator lines producing garbage fallback text.** Real
  `mkt_engine` docstrings frequently start with `──` or `---` separator bars
  (verified: `validatePixelSize`, `EditTopBar`, `ResizeTool`). Without stripping
  them, fallback text reads `"validatePixelSize — function, 2 caller(s). ── Validation helpers ─────────────."` Mitigation: the `_fallback_text` function
  strips leading lines that are entirely separator characters before extracting
  the first sentence. This is a pure string operation, deterministic, testable.

- **R3 — `narratives.json` references a node_id no longer in the model
  (orphaned narrative).** A function is renamed or deleted; its nano id changes;
  the old entry in `narratives.json` points at a non-existent node. Mitigation:
  `narrate status` reports every stored entry whose `node_id` is absent from
  the current model as `orphaned` (a derived display state — NOT stored). `narrate
  worklist` ignores orphaned entries; they do not appear in the worklist (the node
  is gone). A future cleanup command (`narrate gc` or similar) is P6 scope —
  deferred (OQ-GC-1).

- **R4 — Concurrent `narrate` writes.** Two processes running `narrate approve`
  or `narrate ingest` simultaneously on the same `narratives.json`. The atomic
  `os.replace` prevents partial writes, but the last writer wins and the earlier
  write is silently discarded. Mitigation: P4 is a CLI tool in a solo-builder
  workflow; the real concurrency concern is a `narrate` write colliding with a
  `narrate status` read — status is read-only and does not write, so the only
  write-write race is two simultaneous `approve`/`ingest` calls, which is not
  a realistic usage pattern. Approve never re-pins the signature; it only
  changes `status` from `proposed` to `approved` after verifying the stored
  signature still matches. Documented in Failure modes; no advisory lock is
  added (stdlib has no portable file lock, and adding one would require a new
  pattern).

- **R5 — Config schema drift.** Adding `narrate_threshold` and `narratives_path`
  to `ssot-diagram.config.json` without bumping `version`. Mitigation: P4 reads
  both new keys via a PERMISSIVE reader (`.get()` with defaults) — never via
  `load_config`. The schema stays version 1, and existing config files (which
  omit the new keys) continue to work. If P5 or a later phase requires a breaking
  schema change, `version` bumps then.

- **R6 — `_save_model` reuse assumption.** The design assumes `_save_model`
  (`graph_model.py:796`) can be reused for `narratives.json` by passing a
  different `path`. The function does `path.parent.mkdir(parents=True,
  exist_ok=True)` and `json.dumps(model, indent=2, sort_keys=True)` —
  both are generic. Mitigation: factual-code-verification must confirm the
  function does not hardcode any model-specific logic (Assumptions to verify A3).

---

## Failure Modes

Each item names what breaks it, blast radius, how it is detected, and how it
recovers.

**FM1 — `diagram-model.json` missing or unreadable.**
`narrate worklist` / `approve` / `status` all start by loading the model.
Blast radius: all five subcommands fail before writing anything. Detection:
`open(model_path)` raises `FileNotFoundError` or `json.JSONDecodeError`.
Recovery: fail loud with a clear message (`"diagram-model.json not found — run
graph_model.py extract first"`); exit 2. Never writes to `narratives.json`.

**FM2 — `narratives.json` references a node_id absent from the current model
(orphaned narrative).**
This happens after a code rename or deletion causes the model's node ids to
change. Blast radius: the orphaned entry is inert — no node renders it (the
renderer cannot find its node). Detection: `narrate status` reports it as
`orphaned` when the stored `node_id` is not in the current model's id→signature
index. Recovery: user runs `narrate reject <orphaned-id>` to remove it, or waits
for the cleanup command (P6 scope, OQ-GC-1).

**FM3 — Signature field absent on a model node.**
If a future P3 code change omits `signature` from a node kind, the id→signature
index built by `narrate` will silently have `None` for that entry, and every
comparison will show `stale`. Blast radius: all narratives for that node kind
appear stale even when they are not. Detection: the id→signature builder asserts
`"signature" in node` for every non-collapsed node (fail loud, exit 2). This
catches schema drift at startup before any reads or writes. Factual-code-
verification must confirm the field is present on all three live narrated kinds
(component, micro, nano) — see A1.

**FM4 — Ingest of a malformed or tampered worklist.**
A user edits the worklist JSON by hand and introduces a missing key, wrong type,
or a `current_signature` that no longer matches any model node. Blast radius:
without validation, a bad ingest could write corrupt entries into
`narratives.json`, causing the renderer to display wrong or missing text. The
entire file write is prevented. Detection: ingest validates every entry BEFORE
writing — required keys present (`node_id`, `text`, `current_signature`), node
exists in model, `current_signature` matches model. A single bad entry aborts
the entire ingest with a per-entry error list. Recovery: fix the worklist JSON
and re-run `narrate ingest`.

**FM5 — Concurrent `narrate approve` and `narrate ingest` writes.**
Two processes writing `narratives.json` simultaneously. The atomic
`os.replace(tmp, narratives_path)` prevents partial writes, but the second
writer overwrites the first's result silently. Blast radius: one approval or
ingest is lost. Detection: not detectable at the file level without advisory
locking (not implemented — stdlib only). Recovery: the operation is idempotent
for the surviving write; a user can re-run the lost operation. Approve does not
re-pin signatures; it only flips status after verifying freshness — so a
re-run of approve on a surviving entry is safe. This is a documentation-level
mitigation, not a code-level one.

**FM6 — Docstring with no clean sentence boundary.**
The `_fallback_text` function attempts to find a period+whitespace boundary after
stripping separator lines. If the docstring has no period (e.g., a one-word
label or a multi-line block with only commas and colons), the function falls back
to taking the first 70 cleaned characters. Blast radius: fallback text reads
oddly (truncated mid-phrase), but is never empty and never raises. Detection:
test fixture with no-period docstring asserts the function returns a non-empty
string ending at a character boundary. Recovery: no action needed — the human
approves and overwrites with better text.

**FM7 — `narrate_threshold` config key absent (forward compatibility).**
An existing `ssot-diagram.config.json` (v1, no `narrate_threshold`) is used with
the P4 code. Blast radius: P4 crashes if it treats the key as required.
Recovery: the PERMISSIVE config reader uses `.get("narrate_threshold",
DEFAULT_NARRATE_THRESHOLD)` where the default is 4. No crash; documented default.
`load_config` is never called by narrate, so no `die()` on missing required keys.

---

## Open Questions

**OQ-STRICT-1 (P6) — `narrate status --strict` non-zero exit.**

Right now, the locked design says `narrate status` is advisory (exit 0 always)
for P4. There is a clear future use case: a CI-gate that blocks merges when any
approved narrative is stale.

Recommendation: defer to P6. `decision_index status` established the advisory-
then-strict pattern; P4 follows it.

**OQ-GC-1 (P6) — Orphaned narrative cleanup command.**

When a node is deleted or renamed, its narrative entry in `narratives.json`
becomes an orphan. The current design surfaces it via `narrate status` (shown as
`orphaned`) and requires a manual `narrate reject <id>` to clean it up.

The question: should P4 include a `narrate gc` (garbage collect) command that
removes all orphaned entries in one pass?

Recommendation: defer to a P4-follow-up or P6. The blast radius of orphaned
entries is low (they are inert — no node renders them). A `narrate status` flag
surfacing the count is sufficient for P4.

**OQ-DECLINED-1 (P6) — Persisted "declined" marker for rejected nodes.**

A rejected node that is still in scope re-appears in the next `narrate worklist`
(no persisted "declined" marker distinguishes it from a never-seen node). A
"declined vs never-seen" record (precedent: Block 1c rail picker) is deferred.

Recommendation: defer to P6. Not building it now.

**OQ-MANIFEST-1 — Separate `narrative-sidecar` manifest key vs. extend `diagram-model` desc.**

Human-authority (editorial preference). No technical difference.

---

## Resolved questions

- **OQ on stale-storage** — RESOLVED. Block 5a amended 2026-07-06 (owner-ratified):
  `stale` is never stored; stored status is exactly `proposed|approved`; derived
  status is computed by consumers via signature comparison.
- **OQ-2 (worklist array vs. object)** — RESOLVED. JSON array chosen.
- **OQ on threshold** — RESOLVED. Owner ratified keeping `narrate_threshold=4` as
  an owner-tunable knob, settable in `ssot-diagram.config.json`.

---

## Assumptions to Verify

Each is a checkable factual claim about the real code. The spec and factual-code-
verification steps must confirm these before implementation.

**A1 — All non-collapsed narrated model node kinds carry a `"signature"` field.**
Claim: `component`, `micro`, and `nano` nodes in the emitted
`diagram-model.json` each have a `"signature"` key (hex string). Collapsed nodes
do too but are excluded from P4 scope. Decision nodes are excluded from P4 scope
and not indexed.
File:line: `graph_model.py:252–265` (micro builder), `:338–354` (nano builder),
`:911–925` (component builder).
Why it matters: if any narrated kind omits the field, the id→signature index has
`None` for those nodes and every comparison shows stale.
Verification: confirmed against golden model fields — component, micro, nano
all present in `testdata/mkt_engine.model.json` output (surveyed 2026-07-06).

**A2 — The model JSON is NESTED (components.children = micros, micros.children = nanos),
not flat with separate top-level `micros` and `nanos` arrays.**
Claim: `cmd_extract` emits a single `"components"` top-level array where each
component contains `"children"` (micros) and each micro contains `"children"`
(nanos), matching the golden model structure.
File:line: `graph_model.py:879–934` (component tree assembly), golden model
line 1 (`"components": [{ "children": [{ "children": [...] }] }]`).
Why it matters: P4's id→signature walker must traverse the nested structure;
if the layout were flat, the walker would miss all micros and nanos.
Verification: confirmed by golden model inspection (2026-07-06): top-level keys
are `components`, `decisions`, `generated_at`, `nano_cap`, `version`. No flat
`micros` or `nanos` arrays.

**A3 — `_save_model(path, model)` is generic — no hardcoded model-specific logic.**
Claim: `_save_model` at `graph_model.py:796–805` does only: `path.parent.mkdir`,
atomic `tmp` write with `json.dumps(model, indent=2, sort_keys=True,
ensure_ascii=False) + "\n"`, `os.replace(tmp, path)`. It does not inspect the
dict structure.
File:line: `graph_model.py:796–805`.
Why it matters: P4 reuses this function verbatim to write `narratives.json`.
If it has hardcoded keys (e.g., `model["components"]`), P4 cannot reuse it.
Verification: read the function body (surveyed 2026-07-06) — no model-specific
logic; the function is a pure serializer of any dict.

**A4 — `di.find_db` and `di.repo_root_for` are accessible as module-level names
on the `decision_index` module.**
Claim: `graph_model.py:27` does `import decision_index as di`; `di.find_db` and
`di.repo_root_for` must be resolvable names (either defined in `decision_index.py`
or imported there from `_shared.db` at module level).
File:line: `decision_index.py:49` (`from _shared.db import SchemaError, find_db,
repo_root_for`), `graph_model.py:812–815`.
Why it matters: P4 subcommands use the same DB/root discovery pattern as
`cmd_extract`; if `find_db` is not accessible via `di.find_db`, every P4
subcommand must re-derive the repo root differently.
Verification: `decision_index.py:49` imports `find_db` and `repo_root_for` at
module scope from `_shared.db`, making them accessible as `di.find_db` and
`di.repo_root_for` (confirmed 2026-07-06).

**A5 — Nano nodes DO NOT carry `start_line`/`end_line` in the emitted JSON.**
Claim: the fallback text formula cannot reference `start_line`/`end_line` because
these fields are not in the serialized nano dict (they are used internally during
nano building but not emitted).
File:line: `graph_model.py:340–354` (nano dict construction) — `start_line` and
`end_line` are not in the nano dict keys; golden model nano keys: `caller_count`,
`decisions`, `docstring`, `edges`, `id`, `is_exported`, `kind`, `name`, `path`,
`qualified_name`, `signature`.
Why it matters: a fallback text formula referencing `start_line` would raise
`KeyError` on every nano.
Verification: confirmed by golden model inspection — nano dict has no
`start_line`/`end_line` (surveyed 2026-07-06).

**A6 — Micro nodes DO NOT carry `caller_count` in the emitted JSON.**
Claim: the micro fallback text formula cannot use `caller_count`; it must use
the count of non-collapsed children instead.
File:line: `graph_model.py:252–265` (micro dict construction) — no `caller_count`
key in the micro dict.
Why it matters: using `micro["caller_count"]` in the fallback would raise
`KeyError`.
Verification: confirmed by golden model inspection — micro keys are `children`,
`decisions`, `dominant_class`, `edges`, `id`, `kind`, `name`, `path`,
`signature` (surveyed 2026-07-06).

**A7 — `load_config` (graph_model.py:72–120) calls `di.die()` on missing required
keys (`version`, `components`, `default_component`).**
Claim: calling `load_config` from a read-only subcommand like `narrate status`
would abort with exit 2 if those keys are absent. Therefore `narrate` MUST use
a PERMISSIVE reader instead, reading only `narrate_threshold` and
`narratives_path` via `.get()` with defaults.
File:line: `graph_model.py:72–120`.
Why it matters: a `narrate status` on a repo with a minimal or absent config
must not die before printing anything.
Verification: to confirm at the spec step — read `load_config` body for `die()`
calls on missing keys.

**A8 — `build_parser()` uses `sub.add_parser()` and the `cmd` dest pattern,
making it safe to add a `narrate` subparser.**
Claim: `graph_model.py:953–976` shows a standard argparse subparser setup with
`sub = p.add_subparsers(dest="cmd", required=True)`. A new `narrate` parent
subparser (with its own `sub2 = narrate_parser.add_subparsers(...)`) can be
added without touching existing subcommands.
File:line: `graph_model.py:953–976`.
Why it matters: nested subparsers require `required=True` on the inner level to
avoid silent no-op dispatch.
Verification: surveyed `graph_model.py:953–976` (2026-07-06) — standard
argparse pattern; no custom parser class that would block nesting.

**A9 — `collapsed` nodes appear as children of micros with `kind == "collapsed"`.**
Claim: the id→signature walker excludes collapsed nodes by checking
`child["kind"] != "collapsed"`.
File:line: `graph_model.py:376–384` (collapsed node construction),
golden model: `collapsed` node has keys `collapsed_count`, `id`, `kind`, `name`,
`signature` (no `caller_count`, no `docstring`).
Why it matters: including collapsed nodes in the worklist would produce a
fallback text that references `caller_count` (absent) and raise `KeyError`.
Verification: confirmed by golden model inspection — two collapsed nodes present,
both with `kind == "collapsed"` (surveyed 2026-07-06).

**A10 — `di.die` exits with code 2 (matching P3's error exit convention).**
Claim: `decision_index.py:327` `die()` calls `sys.exit(2)` (or `sys.exit(1)`);
P4 should use the same function and exit code for fatal errors.
File:line: `decision_index.py:327–330`.
Why it matters: P4's fail-loud posture must be consistent with P3's; if `die`
uses a different exit code, callers (CI scripts) may not handle it correctly.
Verification: to confirm at the spec step (not read in this survey).

---

## Read-set

Files surveyed during this design step (exact set used to ground the document):

| File | Lines read | Purpose |
|---|---|---|
| `ssot-diagram/graph_model.py` | 1–995 (full) | P3 code: all subcommands, builders, writer, parser |
| `ssot-diagram/decision_index.py` | 1–330 | P1 helpers P4 reuses: `open_db`, `find_db`, `repo_root_for`, `die`, `save_index`, `load_index`, `current_sig`, `anchor_status`, status/refresh cmds |
| `ssot-diagram/testdata/mkt_engine.model.json` | full (golden) | Actual emitted node field sets per kind |
| `ssot-diagram/ssot-diagram.config.json` | full | Config schema P4 extends |
| `ssot-diagram/AI-artifacts/1_design/p3-diagram-model-extractor.md` | 1–947 | P3 design for style reference and constraint cross-check |
| `ssot-diagram/STATE.md` | full | Phase state, P4 next |
| `ssot-diagram/CLAUDE.md` | (via context) | Tool-specific rules |
| `ssot-diagram/AI-artifacts/roadmap.md` | 1–140 | P4 roadmap entry for wording |
| `docs/roadmap/skeleton-contracts.md` | full | Block 5a/5b/4b/4a frozen contracts |
| `manifest.json` | full | Existing `diagram-model` entry shape |
| `_shared/sig.py` | full | Verified `slice_hash`, `symbol_spans`, `file_content_hash` signatures |
| Python introspection | runtime | Golden model field sets for all node kinds, decision nodes, collapsed nodes |

---

## Downstream consumer contract (for P5 / biography Phase F)

P5 (renderer) and biography (Phase F) are CONSUMER-ONLY for `narratives.json`.
They must:

1. Load `narratives.json["narratives"]` — a dict keyed by `node_id`.
2. For each node they render, look up the entry. If absent, use `_fallback_text`.
3. **CONSUMER OBLIGATION (Block 5a amended 2026-07-06):** Trust an entry ONLY
   if `stored_status == "approved"` AND `stored_signature == current_model_node["signature"]`.
   If either fails, display as stale (Block 5b). Consumers MUST compute this
   derived status via signature comparison themselves — reading stored `status`
   literally and trusting `approved` without the signature check would render
   drifted prose as current.
4. Derived states to present: `approved` (trusted prose), `proposed` (pending
   human sign-off), `stale` (sig mismatch — show fallback or stale badge),
   `none` (no entry — show fallback text).
5. They do not call any `narrate` subcommand; they do not write `narratives.json`.

This is the full consumer contract P4 exposes. P5/biography implementation details
are not P4's concern.
