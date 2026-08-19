# ADR 0001 — A path-only claim for a file on disk is not MISSING

## Status

Accepted (2026-08-19, Bucket 3 — plan_verify disk-stat for path-only claims).

## Context

plan-verifier's verdicts are pure lookups against `.codegraph/codegraph.db`. A
`touch:` / `remove:` of a path-only token that the index never parsed (a file the
indexer skipped, a config file, a freshly created file) always resolved to
`UNRESOLVED`, and the two `UNRESOLVED` arms emitted `MISSING` /
`no existing match` unconditionally — even when the file is a real, regular file
in the working tree. That is a false negative: the plan claims the file exists,
and the file does exist; the index is just not aware of it.

Bucket 3 adds a private disk fallback (`_on_disk` / `_path_only` /
`ON_DISK_EVIDENCE` in `plan_verify.py`), applied in `verdict_claim` **after**
the resolver returns `UNRESOLVED`, never before. This ADR records what the
fallback does and — just as importantly — what it deliberately refuses to do, so
the next reader does not re-litigate the carve-outs or mistake `OK` for
"checked against the index".

## Decision

The fallback is narrow and fail-closed. Its whole behaviour is:

- **(a)** A path-only regular file under the indexed root is **not** `MISSING` —
  it is `OK` with evidence `on disk, not in index` (the single constant
  `ON_DISK_EVIDENCE`; tests assert equality, never substring).
- **(b)** `path::Symbol` is excluded, including `foo.py::` — a `::` suffix means
  the plan claims a **symbol**, and a symbol that the index never parsed is still
  `MISSING` (`no node or file matches ...`). An on-disk file does not make an
  unindexed symbol real.
- **(c)** `new:` of a path-only file that already exists on disk under the repo
  root is `COLLISION` with the same evidence `on disk, not in index` (not `OK` /
  `no existing match`). Indexed existence keeps today's `exists: …` COLLISION.
- **(d)** Directories do not count — the check is `is_file()`, never `exists()`.
  A `touch: docs/` for an unindexed directory stays `MISSING`.

Only `touch:` / `remove:` / swept path-only claims take the `OK` disk fallback.
A path-only `new:` of an on-disk file is the `COLLISION` case above. The verdict
enum and `STRICT_FAILS` membership are untouched — no new verdict, no
`UNINDEXED`, no change to which verdicts gate `--strict`.

**Accepted consequences, stated explicitly:**

- **R1 — Blast-radius blindness.** A path-only `OK` from disk skips
  blast-radius analysis — the index genuinely has no callers for a file it never
  parsed, and the alternative is a fabricated verdict. `OK` here means "this
  file is on disk", not "this file is known safe".
- **R2 — Verdicts are working-tree-dependent.** The same plan + same DB can
  verdict differently before and after a file is created, and a re-verify in CI
  on a fresh checkout may differ from the author's machine. The evidence string
  `on disk, not in index` keeps the reason visible in every row and in `--json`.
- **R4 — Symlink to an out-of-repo file is refused.** A repo-internal symlink
  resolving outside the root fails containment and stays `MISSING` (loud),
  not silently `OK`. Deliberate: refusing is the fail-closed direction.
- **OQ-RT-M1 — Symlink loop returns False without raising.** A two-node symlink
  loop (`loop/a` ↔ `loop/b`) makes `Path.resolve` raise `RuntimeError` on this
  runtime, so `_on_disk` catches **both** `OSError` and `RuntimeError` and
  returns `False` — `verify` and the CLI never traceback on a loop.
- **Constraint 3 / OQ-RT-M2 — The stat root is the DB's repo, not the plan's.**
  The fallback stats `repo_root_for(db)` of the **opened** database (the parent
  of `.codegraph/`), not the plan file's directory. A plan verified against
  another checkout via `--db` stats *that* checkout.

**Non-claims.** This change does **not** promise net-fewer CLI failures: a
path-only on-disk `touch:`/`remove:` no longer fails `--strict` as a false
`MISSING`, but a path-only `new:` of an on-disk file now fails as `COLLISION`,
so the combined failure count can stay flat or rise. It does **not** cover
`Makefile` / `.env` (not path-only under the current parser), does **not**
export a disk-aware resolver, and does **not** treat `path::Symbol` as `OK`
just because the file exists.

## Consequences

- `touch:` / `remove:` of a real, unindexed, path-only file now reports `OK` +
  `on disk, not in index` instead of a false `MISSING` — the plan is factually
  correct about the file existing.
- A plan that `new:`s a file already present on disk is flagged `COLLISION`
  instead of passing — catching "the file already exists" without needing the
  index to know about it.
- Every disk-derived row is visibly labeled, so reviewers can tell index
  evidence from working-tree evidence at a glance.
