# Mini-RT — Bucket 4 codegraph CLI design

_Date:_ 2026-08-17 · _Target:_ `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md`
_Verdict:_ **not green** — findings in all three sections.

---

## 1. Done-cell proxy audit

For each behaviour-contract row (design lines 237–246): does its test assert the
claim, or a proxy for it?

| Cell (input) | Claim | What the stated test asserts | Substitution |
|---|---|---|---|
| `--path '${workspaceFolder}'` | stderr names literal **and cwd is not used and no index opened/created** | exit code + stderr substring (R2, line 270: "asserting exit code + stderr substring") | **exit-code-and-stderr for the side-effect claim.** Neither "cwd untouched" nor "no index created" is asserted. A guard that printed the right text and exited non-zero would green the cell even if it had already touched cwd. |
| `init '${workspaceFolder}'` | same message; **no `.codegraph/` created anywhere** | exit code + stderr | **exit-and-stderr for the absence claim.** The literal-named-dir hazard (Implication A) is never checked — nothing asserts `${workspaceFolder}/.codegraph` does not appear. |
| `init <dir>` unreadable | **deletes `codegraph.db` + `-wal` + `-shm` only; every other file still present** | exit 0 + nodes>0 + R3 "asserts no `codegraph.db-wal` / `-shm` survives" | **absence-of-sidecars for preservation-of-everything-else.** "No sidecars remain" ≠ "only three files deleted." An over-deleting impl passes R3. |
| `init <dir>` empty | **opens, clears, full-indexes in place** | exit 0 + "prints the normal index result" | **printed text for an index that actually ran.** "Indexed N files" is output, not evidence of a clear+rebuild. |
| `init <dir>` busy | **no file deleted, no index run** | exit non-zero + stderr | **exit-and-stderr for the no-mutation claim.** No assertion checks the db file survived or its mtime/content is unchanged. |

Each proxy is the *observable* surface, not the *invariant* — the invariants
("cwd untouched", "only three files deleted", "nothing mutated on busy") are the
load-bearing part of the locked promise and none of them is directly asserted.

---

## 2. Gaming sim — honest-but-lazy executor

One path per cell an executor can green without building the thing.

| Cell | Gaming path |
|---|---|
| `empty` → re-index in place | **Alias `empty` to `unreadable`.** Delete the db and take the fresh-`init` path instead of "open + clear". Observables (exit 0, "Indexed N files", nodes>0) are byte-identical; the in-place-vs-replace distinction is invisible to the stated test. |
| `busy` → error, touch nothing | **Omit the errcode-5 branch entirely.** Implication H admits busy is "rare on read under WAL" — a read-only probe cannot even reach it. The concurrent-writer test is non-deterministic to construct, so nothing in the happy-path suite forces the branch. Green by deletion of the branch. |
| `unreadable` → delete three files only | **`rm -rf` the whole `.codegraph/` and re-init** (the explicitly-rejected "auto-uninit wipe"). R3's "no `-wal`/`-shm` survives" still passes; only a full before/after directory listing catches the over-delete. |
| `${...}` → cwd not used | **Exit before `path.resolve`.** Exiting pre-resolve trivially guarantees "cwd not used"; the test checks only exit+stderr, so the claim is green regardless of whether a regression later touches cwd. |
| `unreadable` errcode 11 branch | **Never verify errcode 11.** The recorded probe (claim 2 / assumption 13) enumerates only 26 and 5; the 11 branch has no reproducing test, so it ships unexercised. |

The `busy` and `empty` rows are the two where the honest implementation and the
cheap one are observably indistinguishable under the stated tests.

---

## 3. Chain contradictions, read off the capability matrix

**(a) A hop that must BLOCK on a "no"-enforcement row.**
The `serve --mcp --path '${…}'` hop (matrix row 3, "Vendor-enforced? **no**").
The design's entire point is that this hop *fails closed* (blocks the wrong
index) via `process.exit(1)`. The blocking action is codegraph's own exit — so
the "block" is ours, yet the matrix's "no" describes the *surfacing* of the
block, not the block itself. The design already reconciles this (line 144: "this
design does not claim the refusal alerts the agent… claims exactly one thing: the
process does not serve a wrong index"). **Not an unfixed contradiction — a
naming tension the design closed — but the matrix reads the same guard as
enforced in rows 1–2 and unenforced in row 3, and any reader who misses line 144
will assume the fail-closed guarantee is weaker than it is.**

**(b) Output type does not match the next hop's input.**

1. **The probe's `'busy'` union member is unreachable from the probe's own
   mechanism.** `probeIndexHealth` (Option A step 2) declares
   `'usable' | 'empty' | 'unreadable' | 'busy'`, and `init` dispatches on all
   four. But the probe is a read-only minimal connection running one `COUNT(*)`
   over `nodes` (Implication I). Under WAL a reader is not blocked by a writer
   (Implication H), so a read-only COUNT can never observe errcode 5 — `'busy'`
   can only surface on the *repair's write step*, a different hop *after* the
   probe returns. The probe's declared output type overpromises: three members
   are computable, the fourth is dead code in the probe. (Design half-owns this
   via R5 — "map errcode 5 at *every* step of the repair" — but still keeps
   `'busy'` in the probe's return union, so the signature and the honest
   dispatch disagree.)

2. **The errcode dispatch has a hole at errcode 1.** The classification mixes
   two payload kinds: *error codes* (`26/11 ⇒ unreadable`, `5 ⇒ busy`) and an
   *error message* ("or a missing core table ⇒ unreadable"). But a db that opens
   yet lacks the `nodes` table throws `SQLITE_ERROR` (errcode **1**, "no such
   table"), which is neither 5 nor 26/11. The load-bearing pair (line 251) claims
   the classification "is a single first-error dispatch on the SQLite error code
   (5 wins, exclusively)" — that framing has no bucket for errcode 1, so the
   "missing core table" branch must be message-string matching the dispatch
   framework never names. The input type (error code) and the next hop's
   discriminator (mixed code + message) do not line up.

**(c) A named failure surface that cannot accept the payload kind sent to it.**

The `unreadable` bucket is asked to accept **errcode 11 (SQLITE_CORRUPT)** as a
payload, but the only recorded evidence on either runtime (junk and dev node,
assumption 13) produced errcode **26** (NOTADB) and **5** (BUSY). Errcode 11
appears in the contract (lines 169, 244) and constraint 6 without ever being
reproduced — a corrupt db on `node:sqlite` may surface as 1, 26, or some other
shape, not necessarily 11. The classification accepts a payload kind whose
existence on the deployed runtime is unverified, so a genuinely corrupt db could
fall through the dispatch (see (b)2) rather than land in `unreadable`.

---

## Summary

- **§1 proxies:** 5 of 7 contract rows assert the observable (exit/stderr/printed
  text), not the invariant (cwd untouched / only-three-files-deleted /
  nothing-mutated-on-busy / an index actually ran). The invariants are the locked
  promise; the tests as stated proxy for them.
- **§2 gaming:** `empty` (alias to delete+reinit) and `busy` (omit the branch —
  unreachable on read) are greenable without the real implementation; `unreadable`
  is greenable via the rejected auto-uninit wipe.
- **§3 chains:** (a) serve --mcp blocks on a "no" row — reconciled at line 144
  but a reading hazard; (b) the probe's `'busy'` union member is unreachable from
  a read-only probe, and the errcode dispatch has no bucket for errcode 1 ("no
  such table"); (c) errcode 11 / SQLITE_CORRUPT is accepted by the classification
  but never reproduced on either runtime.
