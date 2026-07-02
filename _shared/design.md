# _shared — Design

**Status:** not built (directory exists, empty). **Effort:** S per module — this is mostly
*moving* proven code, not writing new code. **Build order:** not a standalone item; it is
built as part of #3 (plan-verifier), which is the first tool whose needs trigger the
extraction. Later tools (#8 plan-visualizer, #9 changeset-context, #13 impact-precommit
and friends) consume it as it stands.

---

## What it is

The small toolbox every codegraph-derivative tool shares. Several tools in this repo need
the exact same abilities: find the codegraph database, open it safely without ever writing
to it, turn a name mentioned in a document into the real piece of code it refers to,
answer "who depends on this", keep printed output within a size budget, and behave
correctly when running as an editor hook. Today the first working versions of those
abilities live buried inside two shipped tools. This directory is where they get pulled
out into shared modules, so the next five tools reuse one proven implementation instead of
each rewriting (and each subtly diverging from) the same logic.

## Why it exists

Blueprint principles served:

- **Determinism before inference:** these modules ARE the deterministic layer — every
  verdict any tool emits flows through them, so their correctness is the correctness of
  the whole stack.
- **Signatures are the shared currency** (ground rule, verbatim-in-spirit): file =
  `files.content_hash`; symbol = sha256 of its source slice `[start_line, end_line]`;
  component = sha256 over member hashes. That recipe is already implemented in
  `ssot-diagram/decision_index.py` — extract it, don't reimplement it.

The failure it prevents: five tools each carrying a private copy of "resolve a token" or
"compute a signature" that drift apart, until a symbol counts as FRESH in one tool and
STALE in another and nobody can say which is right. One currency, one mint.

---

## The extraction rule (the actual contract of this doc)

**Extraction happens when the second consumer appears — never speculatively.**

A module moves into `_shared/` at the moment a *second* tool needs it, and the extraction
is done by lifting the working code out of its current home, not by rewriting it.
**plan-verifier needing the resolver is the natural trigger**: `decision_index.py` is the
first consumer of resolution/signature/db code, plan-verifier is the second — so `db.py`,
`resolve.py`, and `sig.py` get extracted as part of building plan-verifier, and
`decision_index.py` is refactored in the same change to import from `_shared/` (behavior
identical, its existing tests must still pass). Modules nothing needs yet stay unwritten.

## Extraction map

| Module | Contents | Source |
|---|---|---|
| `db.py` | `find_db()` walk-up discovery; read-only connect (`mode=ro` — in practice `mode=ro&immutable=1`, because codegraph uses WAL and a pure `mode=ro` open would need a `-shm` file; `immutable` keeps the zero-write coupling); schema guard that fails loudly on unrecognized codegraph schema instead of guessing | extract from `ssot-diagram/decision_index.py` |
| `sig.py` | file / symbol / component signature recipes (`files.content_hash`; sha256 of the symbol's source slice `[start_line, end_line]` — hashing content, not line numbers; component = sha256 over member hashes) | extract from `ssot-diagram/decision_index.py` |
| `resolve.py` | doc-token → node resolution with honest `AMBIGUOUS` / `UNRESOLVED` outcomes — never a guess | extract from `decision_index.py`'s `bootstrap` path |
| `queries.py` | blast-radius (incoming callers with `file:line`), in-degree ranking, nodes-for-files, nodes-overlapping-line-ranges, edge roll-up by component | new, ~6 small functions wrapping the two SQL idioms every tool shares |
| `budget.py` | token/line estimation + budgeted-emit helper (emit highest-priority first, stop at budget, collapse remainder to a count) | new, tiny |
| `hookio.py` | hook JSON stdin parsing (cwd, tool name, file path, transcript id); bounded fail-open output — silent when nothing to say, never blocks the session on the tool's own errors | extract from `impact-analyzer/impact.py` and `ssot-diagram/decision_hook.py` |

Code is extracted FROM: `ssot-diagram/decision_index.py` (db, sig, resolve),
`impact-analyzer` (hookio), `ssot-diagram/decision_hook.py` (hookio). `queries.py` and
`budget.py` are the only genuinely new code, and they are thin.

---

## Inputs / Core computation / Output contract

Not applicable in the per-tool sense — `_shared/` is a library, not a tool. Its contract
is the module table above plus these invariants every consumer may rely on:

- `db.py` either returns a verified read-only connection or refuses loudly; it never
  returns a connection to a schema it doesn't recognize (read-only coupling to codegraph
  internals means version drift must fail, not emit wrong answers).
- `sig.py` signatures are stable across re-index runs when content is unchanged — they
  hash content, never ids or line numbers.
- `resolve.py` returns exactly one of: a unique node, `AMBIGUOUS` (with the candidate
  list), or `UNRESOLVED`. It never silently picks a candidate.
- `queries.py` results are pure functions of the DB — same DB file, same answer.
- `budget.py`-shaped output never exceeds its budget; overflow collapses to counts.
- `hookio.py` guarantees a hook using it is silent on no-signal and exits cleanly (never
  raising into the session) on any internal error.

## Delivery

Not a manifest entry of its own — `_shared/` ships as the support directory the
piggyback-installed tools import (`piggyback install/init/update` copies it alongside any
tool that lists it). Plain Python files, stdlib only, no packaging ceremony.

---

## Ground rules inherited

`_shared/` doesn't just honor the ground rules — it *implements* them, once, for everyone:

- **Read-only DB** → enforced in `db.py` (the only sanctioned way to open the index).
- **Budgeted fail-open hooks** → `budget.py` + `hookio.py` (the pattern impact-analyzer
  set: 0 signal → silent; overflow → top-N only; own errors → never block).
- **Signatures as currency** → `sig.py` is the single mint.
- **Piggyback delivery rail** → distributed alongside the tools that import it.

## Dependencies

- Python 3 stdlib only (`sqlite3`, `hashlib`, `json`, `pathlib`, `re`). No third-party
  packages.
- The codegraph DB schema (`nodes`, `edges`, `files`, `nodes_fts`, `unresolved_refs`) —
  a read-only external coupling, guarded by the schema check.

Consumers (current and planned): plan-verifier (trigger), decision-index (refactored to
import), impact-analyzer (hookio, on its next touch), plan-visualizer, changeset-context,
impact-precommit, repo-map, drift-digest, biography, dead-code-finder, doc-coverage.

## Non-goals

- No write helpers for the codegraph DB — there is no legitimate consumer, ever.
- No speculative modules ("we'll probably need caching") — the rule above is the law.
- No framework: no base classes, no plugin registry, no config system. Flat modules of
  small functions.
- Not a public package — internal to this repo; consumers import by relative path the
  same way the piggyback layout already arranges.

## Open questions

- **[Human-judgment]** When `decision_index.py` is refactored to import `_shared/`,
  should its own file keep thin back-compat aliases (zero risk to its tests and hook
  wiring) or be cut over cleanly in one commit? Cleaner cutover recommended, but it
  touches a shipped tool.
- **[Technical research]** How does the piggyback installer copy `_shared/` for tools
  installed into other repos — duplicate the directory per install target, or a single
  shared location on the import path? Check what `piggyback.py` / `manifest.json` support
  today before deciding.
- **[Technical research]** `resolve.py` extraction boundary: `bootstrap`'s resolution is
  tuned to decision-doc anchors (`file:` / `qname@path` forms); plan-verifier needs
  `path::symbol` and bare-token forms too. Confirm one resolver cleanly serves both
  grammars or whether the grammar parsing stays per-tool with only the DB-lookup core
  shared.
