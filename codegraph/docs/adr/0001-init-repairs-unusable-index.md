# ADR 0001 — `init` repairs an unusable index instead of trusting existence

## Status

Accepted (2026-08-17).

## Context

`isInitialized` is existence-only — it returns `fs.existsSync(<codegraph dir>/codegraph.db)`
and nothing more. Because `codegraph init` keyed its "already done" branch off that
predicate, a second `init` on a project whose index *existed but was not usable* exited 0
with "Already initialized" and touched nothing. Three failure shapes slipped through that
gap, all indistinguishable by file existence alone:

- **Hollow** — a real SQLite database with the full schema but zero rows in `nodes`.
  Everything downstream (MCP tools, `explore`, `node`) serves an empty graph and the
  agent falls back to Read/Grep, but `init` reported success.
- **Junk** — the db path holds bytes that are not SQLite at all (a truncated write, a
  stray file). The schema is absent, so opening it for a query throws.
- **Unreadable/corrupt** — SQLite rejects the file at open or at first query
  (`SQLITE_NOTADB` 26, `SQLITE_CORRUPT` 11, or a missing `nodes` table), yet `init`
  still said "already initialized".

This was correct when `init` was mkdir-only. It is wrong now that `init` also builds the
first index: once `init` owns "make the project usable", existence can no longer stand in
for usability.

## Decision

`codegraph init` now probes the health of an existence-true index and dispatches on the
result instead of unconditionally warning and returning:

| Health | Action |
|---|---|
| `usable` | warn "Already initialized" + return (exit 0) — nothing touched |
| `empty` | open in place, `clear()`, re-index — **never unlink** |
| `unreadable` | unlink exactly `codegraph.db` / `codegraph.db-wal` / `codegraph.db-shm`, then fresh `init` + index |
| `busy` | error naming the db path + `codegraph daemon`, exit 1 — **no unlink** |
| `unclassified` | error naming the raw errcode + message, exit 1 — **no unlink** |

The probe (`probeIndexHealth`) opens the db with raw `node:sqlite` in `{ readOnly: true }`
mode, runs `PRAGMA busy_timeout = 500` and a `SELECT COUNT(*) FROM nodes`, and classifies
by status + `errcode`. It never mutates the db, never runs `PRAGMA journal_mode = WAL`,
and imports nothing from the `db` layer (which would create a cycle with `getCodeGraphDir`).

## Why repair beats a `.codegraph/ready` stamp

A ready-stamp — "write a marker once the index is good, have `init` check it" — is either
redundant or a second source of truth that can drift. The graph already encodes readiness
in the one number that matters: `nodes` count > 0. A stamp written after a successful index
carries no information that the row count does not; a stamp written wrongly (or left behind
after the db is deleted out from under it) becomes a lie the very next command must learn to
ignore. Probing the db directly keeps a single source of truth — the index itself — and the
probe is a read-only COUNT, so it is cheaper and safer than maintaining and reconciling a
marker file.

## Why `busy` ≠ wipe

`busy` (SQLITE_BUSY, errcode 5) means another process — the shared `codegraph daemon` — holds
the database open. Unlinking files out from under a live daemon corrupts its open handle and
reproduces the exact "delete on ambiguity" behavior this change exists to remove. The same
rule covers `unclassified`: an error we cannot name is not a license to delete, because a
wipe on an unknown failure can destroy a recoverable index. The only branch allowed to unlink
is `unreadable`, where SQLite itself has already declared the file dead (26 / 11 / missing
`nodes`), and even then only the three db files under the `CODEGRAPH_DIR`-honoring
`getCodeGraphDir`, never a recursive rm.

## `probeIndexHealth` is not a public/MCP API

The probe is exported from `directory.ts` solely so `__tests__` can import it directly (the
same pattern as `isUnexpandedTemplatePath`). It is deliberately **not** added to the
`src/index.ts` barrel and **not** imported by `src/mcp/**`. Its raw `node:sqlite` read-only
open and its 500ms `busy_timeout` are CLI-repair mechanics, not a library or MCP surface —
the library's own `configureConnection` keeps its separate 5000ms timeout and WAL setup
untouched. Buckets 5 and 6 own their own health/ready unions (the MCP empty-warning
threshold, any future ready-stamp or daemon-visible health signal) independently; this ADR
does not pre-empt them.

## Consequences

Positive:

- An existence-true but hollow/junk/corrupt index is repaired by the command that owns the
  project's usability, instead of being blessed with a false "Already initialized".
- `busy` and `unclassified` refuse with a named error and touch nothing — no silent data
  loss, no unlink on ambiguity.
- The repair path reuses the existing `CodeGraph.open` / `clear()` / index flow and the
  existing fresh-`init` flow, so there is no third index mechanism to maintain.

Negative:

- `init` now opens the db read-only on every existence-true invocation. This is a cheap
  COUNT, but it means `init` is no longer a pure filesystem check.
- The probe must stay in lockstep with SQLite's errcode vocabulary (5 / 26 / 11 / 1). Those
  are pinned by tests (`probe-index-health.test.ts`) and re-derived in the FCV, not assumed.

## References

- Plan: `docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md` — Step 4 (init
  dispatch) and Step 6 (this ADR).
- Spec: `docs/AI_artifacts/4_specs/2026-08-17-bkt4-codegraph-cli.md` — components 3–5, 8.
- FCV: `docs/AI_artifacts/5_factual-code-verification/2026-08-17-bkt4-codegraph-cli.md`
  — A13/A19 (probe errcode map, nodes-only open failure).
- Fork survival record: `codegraph/UPDATING.md` — patch table row for `init` repair.
