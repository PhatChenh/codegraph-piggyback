# Mini-RT round 2 — patched design

_Date:_ 2026-08-17 · _Target:_ `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md` (patched)
_Prior:_ `2026-08-17-bkt4-codegraph-cli-mini-rt.md`
_Verdict:_ **not green** — findings in all three sections, but the four round-1 defect classes are closed.

---

## Round-1 closes that hold

- **serve --mcp row** — now states the block is ours/enforced and the "no" is surfacing-only (line 161, 165). Fail-closed ≠ fail-visible is in the row, not the prose. Closed.
- **`busy` unreachable from a read-only probe** — fixed with a non-WAL fixture (line 30, Implication H, R5): a `PRAGMA journal_mode=DELETE` db in `BEGIN EXCLUSIVE` makes the probe's own `COUNT(*)` throw errcode 5. Deterministic, not a race. Closed.
- **errcode 11 unverified** — now reproduced on the deployed runtime (page-smashed fixture, line 32). Closed.
- **`empty`-via-delete and `unreadable`-via-`rm -rf` games** — killed by the inode assertion (row 5) and the full before/after entry listing with the ⊆-three-files predicate (row 6). Closed.

The four "holds" (lines 290–304) are honest premortems and each names the correct successor failure.

---

## 1. Done-cell proxy audit (residual)

**Row 1 (`--path '${…}'`).** The Done assertion says the cwd snapshot is "full entry list + each file's **size + mtime**" and then concludes "**byte-identical**". Those two halves disagree: size+mtime is metadata identity, not byte identity. A write that keeps size unchanged and lands inside the same 1-second mtime window passes a size+mtime compare and is not byte-identical. Hold 1's premortem flags the helper ("mtime read at 1-second granularity") but only *delegates* the fix to plan; the row's own wording still asserts byte-identity while specifying a metadata mechanism. Same weak spot, lower stakes, in rows 4 and 7, where "unchanged" is anchored to `mtime` rather than bytes — for the no-mutation rows the honest implementation *does* nothing, so the proxy only fails to catch a same-second same-size mutation bug, which is exactly what the snapshot exists to catch.

**Row 8 (`unclassified`).** The Done assertion is "same no-mutation snapshot as the busy row" — but unlike every other row it names **no fixture** that produces the `unclassified` input state. An assertion with no way to reach the state asserts nothing. (Cross-ref §2.)

## 2. Gaming sim

**`unclassified` — green by omission.** Rows 5/6/7 are un-gameable now (inode preservation forces a real open+clear+index; the entry-listing forces a real three-file unlink; busy's correct behaviour *is* to do nothing). The one cell an honest-but-lazy executor can green without building is the new `unclassified` arm: no reproducible fixture is named for it (contrast 26/11/1 which have recipes at lines 28–32, and `busy` which has its non-WAL recipe at line 30). If no fixture is recorded, the arm ships unexercised and the row greens vacuously — the exact "errcode 11 unexercised" defect from round 1, relocated onto the arm invented to close it. Hold 3's own premortem concedes this ("`unclassified` becoming a graveyard… nobody would notice").

## 3. Chain contradictions (incl. new gates)

**(a) `unclassified` — the exemplar's payload kind is not the discriminator's.** The probe is described as dispatching "totally on the SQLite error code" (`errcode`), and `unclassified` is exemplified as "permissions / IO". But a permission/IO failure is a **Node errno** (`err.code === 'EACCES'` / `ERR_SQLITE_CANTOPEN`), thrown at `new DatabaseSync(dbPath)` construction — *before any SQLite statement runs* — with **no `errcode` property**. Assumption 13 establishes "the constructor does not throw" for a junk file, but says nothing about EACCES/CANTOPEN. So the arm that is the *safe default* actually has two distinct fall-through mechanisms conflated into one: an unknown-but-present `errcode`, and a missing-`errcode` Node SystemError that must be caught at a different point in the probe than the code it enumerates. The "total on code" framing elides that the probe's catch must also recognize a non-SQLite error shape to reach the very arm the matrix promises.

**(b) errcode 1 is a generic bucket mapped to the destructive arm.** `SQLITE_ERROR` (code 1) is SQLite's catch-all; the total-dispatch rule (lines 190, 275) maps it wholesale to `unreadable`, which is the *delete* branch. The design's own table (lines 111–112) carries a `message` column — "no such table: nodes" — but the machine dispatches on code alone, and the message is not part of the rule. For the probe's *fixed* single `COUNT(*)` this is currently defensible (the realistic code-1 outcomes are "no such table" / "malformed schema", both reparable), but the arm's specificity lives entirely in the probe's query, not in the dispatch. Any future widening of the probe (a second table check) silently widens the delete branch, because code 1 is not the specific signature the message column implies. The "total on code" framing cannot express a message-disambiguated arm; the table and the rule are in tension.

**(c) Matrix says "no error ⇒ node count decides empty/usable" — but that decision is not final.** On a WAL tree whose writer holds the lock over an *empty* db, the probe reads through the lock, sees 0 nodes, and reports `empty`; the repair then opens + `clear()`s, and that **write** throws errcode 5, aborting into `busy`. The design handles this correctly (R5, line 275), but the matrix's "node count decides empty/usable" presents the probe's verdict as terminal when the next hop (the repair write) can reclassify it. Not a hard break — a wording overstatement of finality, exactly the "output type vs next-hop input" mismatch the lens asks about.
