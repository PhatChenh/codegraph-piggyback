# Mini-RT — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer seat:_ clx-deepseek-v4-flash (same-model, tier 1) · _Date:_ 2026-08-19
_Mode:_ same-model fresh-context mini-RT, NON-INTERACTIVE, report-only, fixes nothing.
_Not certified:_ cross-model judgment blind spots (a same-lineage reviewer shares the author's
assumptions); Cursor-desktop live behavior beyond the wiring files read.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md` · Repo verified:
`/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (current on-disk source, not the
design's cites).

## Verdict

**Not green — 1 MAJOR, 4 MINOR, 0 CRITICAL.** Section 1 (proxy audit): 3 of 4 consumers are
honest-testable and honestly specified; one (blast-gate deny) is unpinned by any named test. The
freshness cache is a second proxy. Sections 2/3 findings are the same core gaps under their own
lenses.

---

## 1. Done-cell proxy audit

For each threaded consumer, does the named change test the honest state or a proxy?

| Consumer | Verdict |
|---|---|
| `freshness()` pass-through | **Honest at the probe→verdict layer, proxied by the cache.** Existing harness proves honesty is the norm: `tests/test_blast_radius.py:304-359` builds **real** sqlite indexes (`make_index`), and `:395-407` proves mtime-change cache invalidation. The new "schema-less db → unreadable" test forces the pass-through. **Gap:** the cache read-path (`blast_radius.py:270-283`) returns `"fresh"` without re-probing when `db_mtime == _db_mtime(repo)`. `chmod 000` and a locked/busy db do **not** change mtime — one of the design's own three reproduced fixtures. So a fresh-cached repo whose db becomes chmod-unreadable within the 300 s TTL still gates as `"fresh"`; Write proceeds. The design's "unreadable is never cached" test covers the **write** side only; no named test covers the **read-side mask**. The design's stated invariant ("never masks a state change — db mtime is re-read on every call", `blast_radius.py:267-268`) is **false for this state**. → **MINOR** |
| Blast-gate deny branch | **Unpinned — proxy can ship.** `tests/test_blast_gate_hook.py` **exists**, runs the **real** script against real fixture indexes, and already tests the missing/unrecognized/stale deny reasons (`:138-206`). §7's test list omits it entirely. Pre-mortem #1 *promises* "a test asserts the deny reason for an unreadable index contains `codegraph index` and not the word 'stale'" — §7 does not deliver it. Without it, the unreadable branch can be skipped/misordered and the four named test files still pass green. → **MAJOR** |
| Pre-dispatch `PRE-UNREADABLE` | **Honest.** `tests/test_artifact_claims.py:1596-1636` builds real git repos + real sqlite dbs (`pre_repo`, `_index_usable`, `_index_unknown_schema`, `_marker`); probe is read from the real repo path. The named test "unreadable index **plus a matching greenfield marker** still denies" is feasible and, if written as specified, behaviorally pins the branch. → **green** |
| Init wrapper retry | **Honest for the pinned outcomes; two message paths unpinned.** `tests/test_writ_codegraph_init.py` uses a fake `codegraph` on PATH + real git + real sqlite (`:46-126`). The junk-db (retry-once, exit 1, no delete) and missing-db (no retry, exit 1) tests pin the core. **Gap:** the `unrecognized`-after-retry message and re-probe-`missing`-after-retry path have no named test; C-08's three-way message split is unverified. → **mostly green, minor gap** |

## 2. Gaming sim (honest-but-lazy executor; one path per hole)

1. **Deny copy.** Skip the `elif verdict == 'unreadable'` branch (or emit the `missing` advice for
   it). `verdict == "unreadable"` then falls into the final `else` at
   `writ-blast-gate.sh:196-202` → *"This repo's codegraph index is stale (older than
   `stale_index_days` = 3)…"* — the pre-mortem's own failure mode #1, and no named test fails.
2. **Freshness cache.** Leave `blast_radius.py:270-283` untouched. Fresh-cache → `chmod 000` the db
   (mtime invariant) → still `"fresh"`. No named test ("fresh-cache, then unreadable, then not
   fresh") exists to catch it.
3. **probe() collapse sites.** Both are pinned by the three new fixture tests (junk / schema-less /
   chmod-000). Residual corner: the `chmod 000` test fails when the suite runs as root (root can
   still open a mode-000 file); a lazy executor "fixes" it with skip/xfail, leaving collapse #1
   unverified.
4. **Pre-dispatch.** Add `PRE-UNREADABLE` but merge it with the missing branch
   (`if probe in ("missing","unreadable"):` → marker logic). A matching marker launders the
   unreadable db. Caught **only** by the named marker-still-denies test — which the design does
   include. Residual corner: `except Exception: probe = "missing"` (`artifact_claims.py:980`) has no
   test pinning its value; silently changing it to `"unreadable"` turns a sibling-module *import*
   failure into a bogus `PRE-UNREADABLE` deny. The design's §4 prose forbids this, but no gate does.
5. **Wrapper.** Reuse the `unreadable` retry message for the `unrecognized`-after-retry case (C-08
   split unverified); or emit the wrong text on re-probe-`missing`. The three outcome tests pass
   because they assert exit code / invocation count / marker / file-existence, never the message.

## 3. Chain contradictions, read off the capability matrix

1. **"Must BLOCK" hop on an enforcement=no row.** The Write deny is Claude-only today, verified:
   `.cursor/hooks.json` wires only `cursor-guard.mjs` on `beforeReadFile` (a deny-set reader,
   unrelated to codegraph freshness); no blast-gate in falkor-writ `.claude/settings.json` or
   `~/.claude/settings.json`. So on Cursor the new `unreadable` state is **fail-open** — same as
   missing/unrecognized/stale today. The design declares this honestly ("declared loss,
   consistent with grill R15"); it is **not** a hidden contradiction. **Spec-fix:** C-04's "edits
   stay denied" is written harness-unqualified; a later reader will assume it covers Cursor.
2. **Claude vs Cursor copy of the deny script.** There is exactly **one** deny script
   (`writ-blast-gate.sh`), updated once. No Cursor copy exists to drift. The design's "same strings"
   dual-predicate holds. Verified. (Latent trap, pre-existing, out of scope: if Cursor ever wires
   this script, its Claude-shaped `hookSpecificOutput.permissionDecision` envelope is unparseable
   by Cursor → inert/fail-open.)
3. **`PRE-UNREADABLE` ordered after `missing`.** Not realized — the design places it before.
   **But the stated mechanism is wrong:** with the existing `if/elif` chain
   (`artifact_claims.py:982-1005`), the marker-consume is unreachable for a `"unreadable"` probe
   **regardless of order** (the missing branch requires `probe == "missing"`). The only way a
   marker launders an unreadable db is a *conflated* condition. The load-bearing guard is therefore
   the marker-still-denies **test**, not the branch order. The design happens to include that test,
   so the outcome is correct — but a future editor who reads "order matters" and reorders into an
   `elif` is fine, while one who reads "order doesn't matter" can conflate. **Spec-fix:** name the
   test as the guard.

---

## Findings summary

- **MAJOR — blast-gate deny branch ships unpinned.** §7 omits `tests/test_blast_gate_hook.py`
  despite it being the existing, honest harness for exactly this copy; pre-mortem #1's promised
  test is absent. `unreadable` can fall into the `else: stale` reason and the design's own four
  named test files pass.
- **MINOR — freshness cache still prints the old "fresh" lie** for an unreadable db whose mtime is
  invariant (`chmod 000`, locked/busy), contradicting the design's "never masks a state change"
  invariant; only the write-side ("never cached") is tested.
- **MINOR — `PRE-UNREADABLE` ordering rationale is cargo-culted** (elif exclusivity already
  protects); the marker-still-denies test is the real guard. C-04 is harness-unqualified (Cursor
  fail-open, verified un-wired).
- **MINOR — wrapper C-08 three-way split untested** (unrecognized-after-retry message,
  re-probe-missing path); §7 also doesn't name the existing `test_unusable_index_leaves_marker`
  (asserts exit 0 at `:149`) that the new missing-db exit-1 behavior flips.
- **MINOR — `except Exception: probe = "missing"` fallback value is unpinned**; gameable to
  `"unreadable"` → bogus `PRE-UNREADABLE` deny on sibling-module import failure.
