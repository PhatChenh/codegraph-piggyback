# Mini-RT round 4 — patched design

_Date:_ 2026-08-17 · _Target:_ `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md` (patched)
_Prior:_ rounds 1–3 · _Verdict:_ **not green** — three residual findings; the substantive round-3 defects are closed.

Round-3 closes that hold (verified against source, not just the text):
- **Constructor-inside-try** — closed. Step 2 (line 197) now wraps `new DatabaseSync`, the `busy_timeout` pragma, and the `COUNT(*)` in one `try`, and Hold 7 + amended assumption 13 (line 457) scope "the constructor does not throw" to junk files only. F6 gone.
- **Code-vs-message dispatch tension** — closed. Implication G retitled "decidable from the *thrown value* — not from an error code alone" (line 108), and the matrix row (line 169) now encodes the message-gated errcode-1 arm inline. F5 gone.
- **Node-count proxy** — materially closed. The repair-proof (lines 302–316) replaces "count > 0" with named-symbol + call-edge assertions; a hand-inserted dummy node fails them. F1 (round 3) substantially addressed.

---

## 1. Done-cell proxy audit

**F1 — the repair proof claims "cross-file" but asserts a same-file edge.** Line 316: "a resolved **cross-file** call edge between two named symbols can [distinguish a real index]." The assertion it actually specifies (line 311) is "the callees of `greet` include `hello`" — and `greet` and `hello` are **both in `a.ts`** (`index-command.test.ts:53-54`). The genuinely cross-file edge in the fixture is `main → greet` (b.ts imports greet from a.ts), which the design does **not** assert. So the prose invokes cross-file *import* resolution as the sharp discriminator, while the test checks *same-file* name resolution. Both require the resolver to have run, so the gaming value is low — but the claim is factually misstated, and the stronger proof is sitting unused in the same fixture.

**F2 — "call edge survives" is checked through `getCallees`, which conjoins four edge kinds.** `getCallees` (traversal.ts:305) returns targets of `calls`, `references`, `imports`, **and** `instantiates`. The assertion "`greet`'s callees include `hello`" therefore passes on a `references` or `imports` edge as readily as on a `calls` edge. The honest index produces a `calls` edge (the `hello(name)` call), so the fixture passes for the right reason — but the assertion as written does not distinguish "greet calls hello" from "greet references hello," which is the specific edge the prose (line 310: "the edge exists only if resolution ran") names. If a future fixture edit turns the call into a bare reference, the test keeps greening while no longer proving a call graph.

## 2. Gaming sim

**F3 — the known-answer digest is not mandated to be independent of the helper.** Line 289 requires "a known-answer case (hash a fixture whose sha256 is written literally into the test)" and correctly states that only a literal digest catches a self-consistent-but-wrong helper. But it never requires the literal to come from an oracle *outside* the helper under test. The round-3 gaming path is therefore still open at one remove: a lazy executor writes a helper that returns `''`, runs it once to obtain `''`, and hardcodes `''` as the "literal expected digest" — the known-answer test then passes and the five mutation rows green. The fix is one sentence ("compute the expected digest with an independent tool — `shasum`/`openssl dgst`, or a hand-derived constant — never by running the helper"), but the text stops short of it.

**F4 — the `<unreadable>` sentinel cannot see an in-place mutation of the very file it guards.** Hold 1's premortem (line 343) concedes this: `'<unreadable>'` equals itself regardless of the bytes underneath, and recording `ino` alongside only catches a *replace*, not an *in-place* rewrite of a file that stays unreadable. The design flags it and defers the remedy ("restore the mode at the end and hash once before cleanup") to the plan. For the `busy`/`unclassified` no-mutation rows, this means the one file whose bytes the row most needs to vouch for (`chmod 000 codegraph.db`) is exactly the one the snapshot cannot hash. It is self-acknowledged, but it is not closed in the contract — the remedy is an instruction to a future plan, not a Done assertion.

## 3. Chain contradictions

**F5 — the `unclassified` row's no-mutation invariant is unverifiable on its own fixture (same root as F4, stated as a chain).** The `unclassified`/`busy` Done assertions require "db file sha256 and inode unchanged" (lines 299–300), while the fixture that produces the arm is a `chmod 000` file whose sha256 is unobtainable and is snapshotted as the `<unreadable>` sentinel. The row's "unchanged" predicate therefore reads "ino unchanged + sentinel unchanged" for the db file — which cannot detect the one mutation class the row is supposed to exclude (a write to that file). This is the surviving consequence of the sentinel design, not a new contradiction, and it is the reason "no file deleted" is the only part of the `unclassified` promise that is actually testable.

---

## Summary

Three findings, all minor and all on the test/verification surface rather than the repair mechanics:

1. **F1** — repair proof says "cross-file" but asserts the same-file `greet→hello` edge; the real cross-file `main→greet` edge is unused.
2. **F2** — `getCallees` conjoins `calls`/`references`/`imports`/`instantiates`, so "callees include hello" doesn't prove a call edge.
3. **F3/F4/F5** — the known-answer digest isn't required to be helper-independent, and the `<unreadable>` sentinel (plus ino) cannot observe an in-place mutation of the `chmod 000` file the `unclassified`/`busy` rows must vouch for.

The constructor-inside-try and the thrown-value dispatch are genuinely closed. These residuals do not threaten the locked promises; they are the remaining seams a plan-compliance pass should pin down.
