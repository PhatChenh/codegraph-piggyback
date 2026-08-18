# Mini-RT re-run — 2026-08-18-bkt3-plan-verify design (post F1–F5 patch)

_Date:_ 2026-08-18 · _Target:_ `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md` (patched)
_Prior:_ `docs/AI_artifacts/7_reviews/2026-08-18-bkt3-plan-verify-mini-rt.md` (F1–F5)
_Mode:_ mini-RT re-run (three passes, independent — prior report not used as truth)
_Read-set:_ design §Done + §Surface-capability matrix + §Chosen Approach + actual code
(`plan-verifier/plan_verify.py:76-125,171-303,314-342,371-437`, `_shared/manifest.py:107-134`,
`_shared/db.py:34-47`, `plan-verifier/test_plan_verify.py:22-86,140-340`), plus a disk probe
(`docs/TECH_DEBT.md` exists; `.codegraph/codegraph.db` present).

**Verdict: NOT green — 1 finding must be fixed before dispatch, 3 more should be.**

Prior F1/F2/F4/F5 are all resolved (verified against code, not taken on trust). F3 is
re-opened: the patch added a swept test that cannot exercise the behaviour it claims to pin.

---

## F-1 — MEDIUM — A5 #13's swept token is filtered out of the sweep; the test is vacuous

Done 1 lists A5 #13: "plan prose with a backticked `hooks.json` (file on disk, absent from
the DB), no manifest block, swept row `OK` + suppressed from output; `strict_fail` empty".
That test cannot exercise the swept-on-disk fallback it is meant to pin.

`sweep_tokens` drops any token ending in a `_NONCODE_EXT` extension before it can become a
swept claim:

> `plan-verifier/plan_verify.py:108-109` — `_NONCODE_EXT = (".md", ".json", ".yaml", ...)`
> `plan-verifier/plan_verify.py:120` — `if "://" in tok or tok.lower().endswith(_NONCODE_EXT): continue`

A backticked `hooks.json` in prose → token ends with `.json` → skipped. The swept claim
never exists. The test then passes **vacuously**: `strict_fail` is empty because there is no
manifest block at all, and "suppressed from output" is true because there are zero swept rows.
No `_on_disk` call happens on a swept path-only token.

### Why it matters
The design sells "Swept claims inherit the fallback, harmlessly" (§Implications) as a benefit
and prior RT F3 demanded the pin. The patch's chosen token defeats its own test. A worker who
wires the fallback only in the manifest-claim loop (or not at all for the swept path) passes
every test while the claimed noise-reduction silently doesn't happen. (Mitigation to note: the
swept loop shares `verdict_claim`, so the fallback code *is* exercised by manifest tests #1–#8;
the unpinned part is specifically a swept path-only token reaching `_on_disk`.)

### Fix
Use a code-extension pathish token that survives the sweep filter — e.g. `probes/schema.prisma`
(`.prisma` not in `_NONCODE_EXT`; the `/` makes it pathish) written to `repo/probes/schema.prisma`,
absent from the DB. Assert: swept row verdict `OK`, evidence `on disk, not in index`, row absent
from `render(...)` output, `strict_fail` empty.

---

## F-2 — LOW — empty-symbol `::` slips the laundering guard; design AV-5 is factually wrong

Design claims the guard is absolute: AV-5 "A `::` entry sets both parts, so `_path_only`
excludes it" and §Implications "no `::Symbol` claim can ever reach it". `parse_entry` maps the
empty-symbol form to `symbol=None`:

> `_shared/manifest.py:129-131` — `p, s = raw.split("::", 1); return Claim(intent, raw, p.strip() or None, s.strip() or None)`

For `touch: foo.py::`, `s = ""` → `s.strip() or None` → **None**. `_path_only` (A1:
`bool(claim.path) and not claim.symbol and not claim.external`) → True → `_on_disk` fires → an
on-disk `foo.py` verdicts `OK`. Before this change it was `MISSING` (UNRESOLVED). So a claim
written with a trailing `::` (user meant a symbol, typo'd) is laundered by disk presence —
exactly the class of claim the guard exists to keep index-bound. None of A5's 13 cases pins it
(#2 uses a non-empty symbol, which is correctly guarded).

### Fix (pick one)
- Tighten the predicate: `_path_only` also requires `"::" not in claim.raw` (then `foo.py::` stays
  `MISSING`), and pin it with a test; OR
- Keep the parser's path-only treatment but state it deliberately in the design and add a test
  pinning `foo.py::` → `OK` on disk, so the behaviour is a decision, not an accident.

---

## F-3 — LOW — Done 2 "no NEW failures" has no recorded baseline

`python3 -m pytest -q` (whole repo) shows no NEW failures vs the pre-change baseline — but the
baseline is not recorded anywhere in the design. The repo ships 3 known pre-existing
`TestGoldenLive` pilot-drift failures. Without a pinned failure list, "no NEW" is unverifiable:
a worker who never runs a baseline can still declare Done 2 green by eyeballing the tail of a
pytest run. This is a proxy assertion (pytest-green → "no NEW"), unchanged from prior RT's
Done-cell audit.

### Fix
Record the pre-change failure set in the Done cell (or an explicit exception list), so "NEW"
is computable.

---

## F-4 — LOW — Done 4/5 are content-presence proxies

- Done 4 "`plan-verifier/adrs/0001-….md` exists **and states the four rules**" — no test asserts
  content. A two-line stub ADR passes. File-existence proxies for substance.
- Done 5 "`plan-verifier/design.md` verdict table records the disk fallback" — a one-line table
  note passes; nothing checks the contract-of-record row actually reads correctly.

Both are docs, so a content assertion is unusual — the cheap fix is to quote the four rules'
exact sentences (and the table row's text) in the Done cells so the reviewer verifies by eye.
If accepted as known doc-proxies, say so.

---

## Section 1 — Done-cell proxy audit

| Done | Verdict | Note |
|---|---|---|
| 1 | **WEAK** | 12/13 cases are direct behavior pins (evidence equality in #1/#3/#4, laundering guard #2, dir→MISSING #5, absolute-refused #7, `../`-escape #12, CLI exit-0 #8, REUSE normalize #9/#10, warn-only #11). **#13 is vacuous** — token is sweep-filtered (F-1). |
| 2 | WEAK | pytest-green proxies for "no NEW"; baseline unpinned (F-3). |
| 3 | PASS | Exit-1 now honest and arithmetically forced (`new:`→COLLISION ∈ `STRICT_FAILS`, `touch: docs/`→MISSING, `strict_fail` reads manifest only, `:433` exits 1). Probe disk facts verified: `docs/TECH_DEBT.md` exists, `docs/` is a dir, index present. Exit-0 correctly relocated to A5 #8. |
| 4 | WEAK | File-existence proxy for "states the four rules" (F-4). |
| 5 | WEAK | Grep-able cell proxy for "records the disk fallback" (F-4). |

## Section 2 — Gaming sim (honest-but-lazy executor, one path per cell)

1. **#13 swept-on-disk (Done 1)** — write the test exactly as spec'd with `hooks.json`: passes
   with zero swept rows, no `_on_disk` call. Green without wiring the fallback into the swept
   path. The test spec itself enables this (F-1).
2. **ADR (Done 4)** — write an empty/stub `0001-*.md` → passes.
3. **Baseline (Done 2)** — run whole pytest, see the 3 known golden failures, report "no NEW";
   no recorded baseline to disprove it.
4. **Table (Done 5)** — add a one-line table row → passes.
5. **Empty-symbol `::` (Done 1)** — implement `_path_only` as spec'd; `foo.py::` on disk → OK.
   No test pins it either way, so the edge ships by accident (F-2).

Not gameable: the core manifest fallback (#1/#3/#4 verdicts + exact evidence string),
laundering guard (#2, non-empty symbol), containment (#7 absolute, #12 `../`), CLI exit-0 (#8),
REUSE normalization (#9/#10).

## Section 3 — Chain contradictions (capability matrix)

**None found.** Read off the matrix rows:

- **Hook row (enforcement *no*)**: the design makes no blocking claim for the hook surface, and
  `hook_main` returns 0 unconditionally (`plan_verify.py:390`). No hop that must BLOCK sits on a
  *no* row. The design's explicit disclaimer (§matrix) matches the code.
- **CLI row (enforcement *yes*)**: Done 3's exit-1 is consistent — COLLISION+MISSING both sit in
  `STRICT_FAILS`, `strict_fail` reads manifest claims only (`:289`), CLI exits 1 (`:433`).
- **Output-type match**: `repo_root_for(db)` → `Path` matches `verdict_claim(..., repo_root: Path | None)`;
  `_on_disk` is only reached under the `_path_only` short-circuit, so `claim.path` is a non-empty
  `str`, not `None`.
- **Payload-kind match**: hook `emit_context` receives a string (joined budgeted rows) — matches
  the matrix's `additionalContext`. `--json` gains only a new evidence *value*; no field renamed;
  the design names it as a deliberate surface change.

One nit, not a contradiction: the pre-dispatch audit's hook row ("fewer advisory rows") is true
for touch/remove but a `new:`-on-disk claim flips from suppressed `OK` to a rendered `COLLISION`
— a `new:`-heavy plan grows hook rows. The hook is advisory and 28-line budgeted, so no gate is
affected; the "fewer" phrasing is partial, not wrong.

---

## Prior-finding disposition

| Prior | Status | Evidence |
|---|---|---|
| F1 exit-0 impossible | **FIXED** | Done 3 now asserts exit 1; arithmetic verified against `STRICT_FAILS`/`strict_fail`/`:433`. |
| F2 `../` untested | **FIXED** | A5 #12 added; fixture root = `tmp_path` (`make_db` → `tmp_path/.codegraph/codegraph.db`), `../outside.json` resolves outside → MISSING. |
| F3 swept unpinned | **RE-OPENED** | #13 added but vacuous (F-1). |
| F4 dynamic-note drop | **FIXED** | A2 snippet now shows the `:224-227` note block after the if/else, before the return. |
| F5 OQ-1 unilateral | **FIXED** | OQ-1 CLOSED 2026-08-18 (ORCH, away Tier A); tool-local recorded. |

---

_F-1 must be fixed before dispatch — a claimed behaviour is unpinned and the test as written
cannot catch a worker who skips the swept wiring. F-2/F-3/F-4 are cheap design-text pins._
