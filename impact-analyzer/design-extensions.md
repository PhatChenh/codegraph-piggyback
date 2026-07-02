# Impact Analyzer — Extensions Design

**Status:** extension of a shipped tool (`impact-analyzer.py` is live; see `design.md`
in this directory for the base design — this file changes nothing there) · **Effort:**
small — three XS/S items, listed in priority order · **Build order:** not scheduled in
the build-order table; opportunistic — each extension can land independently, any time
after `_shared/` exists.

---

## What it is

The shipped impact analyzer watches the AI read planning documents. Whenever a plan
mentions a piece of code by name, the analyzer looks up how many other places depend on
that piece and quietly warns the AI — "careful, seven things call this" — before it
starts implementing. These three extensions sharpen that warning: (1) tell the AI
*exactly where* each mentioned piece lives, so its follow-up look is one precise glance
instead of reading a whole file; (2) flag names the index could only see being used
*dynamically*, meaning the danger count is an undercount; (3) stop the analyzer from
repeating the same warning when the same document is read twice in one session.

## Why it exists

All three serve principle 3, **determinism before inference** — each replaces something
the agent would otherwise rediscover (or miss) with a database fact pushed at the right
moment. Extension 2 also serves principle 1, **trust artifacts, not claims**: an
honest "this count is understated" label keeps the artifact from overstating its own
authority.

Failures prevented, per extension:

1. **Definition-line pointer** — prevents the wasteful follow-up: agent sees a warning
   about `retry_with_backoff`, then reads the entire file hunting for it.
2. **`unresolved_refs` cross-check** — prevents false confidence: a symbol reached via
   dynamic dispatch shows a *low* static caller count precisely when it is *most*
   dangerous.
3. **Per-session dedup** — prevents context pollution: the same doc read twice injecting
   the same block twice, eating the token budget for zero new information.

## Inputs

- **Hook payload** (`PostToolUse:Read`, `.md` files only — unchanged from the base
  tool): the file path read, plus session/transcript identity and cwd from the hook
  JSON on stdin.
- **The codegraph database** at `.codegraph/codegraph.db` (read-only), walk-up
  discovery — unchanged. Newly used columns/tables:

  | Table | Newly load-bearing columns |
  |---|---|
  | `nodes` | `file_path, start_line` (already selected; now *emitted*) |
  | `unresolved_refs` | `reference_name` |
  | `files` | `content_hash` (for the dedup key) |

## Core computation

Deltas on the shipped pipeline only; extraction, thresholds (LOW 1–2 / MEDIUM 3–5 /
HIGH 6–15 / CRITICAL >15, top-10 cap), and silence-on-zero all stay as designed.

**1. Definition-line pointer.** For each flagged name, the node lookup already returns
`file_path, start_line`; append the definition location to the output line:

```
retry_with_backoff [HIGH] (8 callers) — defined at src/queue/retry.py:41
```

so the agent's follow-up read can target that file and line range, surgical instead of
whole-file.

**2. `unresolved_refs` cross-check.** For each extracted name, one extra membership
check:

```sql
SELECT 1 FROM unresolved_refs WHERE reference_name = ? LIMIT 1;
```

On a hit, append a flag to that name's line (and emit it even if the static caller
count alone would have been silent/LOW):

```
handle_event [MEDIUM] (4 callers) ⚠ dynamic dispatch — blast radius under-counted
```

The wording carries the meaning: codegraph saw uses it could not statically resolve, so
the printed caller count is a floor, not the truth.

**3. Per-session dedup.** Before emitting anything, compute a key =
`(transcript id, content hash of the .md file read)`. Keep a tiny state file of keys
already injected this session; on a repeat key, exit silently. Keyed by *content* hash
deliberately: if the doc changed between reads, the key changes and the analysis
re-fires (correct — the mentions may have changed).

## Output contract

- Same bounded block as the shipped tool (header, per-name lines, footer), still
  ≤ ~30 lines, still silent when nothing qualifies.
- Per-name line grows two optional suffixes, both shown above verbatim in spirit:
  - ` — defined at <file>:<line>` (extension 1, always when the node resolved),
  - ` ⚠ dynamic dispatch — blast radius under-counted` (extension 2, only on an
    `unresolved_refs` hit).
- A deduped repeat read produces **no output at all** — indistinguishable from the
  existing "nothing to say" case (extension 3).

## Delivery

- **No new manifest entry, no new hook events.** The existing `manifest.json` entry
  (`impact-analyzer`, `PostToolUse` matcher `Read`, scope `global`) is untouched; all
  three extensions are internal to the existing script. `piggyback update` distributes
  them as an ordinary script update.

## Ground rules inherited

- **Read-only DB:** still `mode=ro`. The dedup state file is the tool's *own* derived
  state and must live outside `.codegraph/` (see open question 1) — the rule is "no
  tool ever writes the DB; derived state lives in the tool's own file."
- **Budgeted, fail-open:** the suffixes cost width, not new lines, but the block must
  stay ≤ ~30 lines — when over, keep the top-callers ordering and drop pointer suffixes
  from the lowest-severity lines first. Any failure in the new code paths (state file
  unwritable, `unresolved_refs` missing in an old DB) degrades to the shipped behavior,
  never blocks the session. Dedup makes the tool *more* silent, never louder.
- **Signatures as currency:** the dedup key is exactly the shared currency — a content
  hash of the file read — so drift (doc edited) is visible and re-triggers analysis
  instead of being silently suppressed.
- **Piggyback rail:** unchanged — same entry, same rail.

## Dependencies

- `_shared/hookio.py` — hook stdin parsing + bounded fail-open output (the base tool is
  the extraction *source* for this module; adopt it here when it exists rather than
  keeping a private copy).
- `_shared/db.py` — walk-up + read-only connect (same story).
- `_shared/sig.py` — content-hash recipe for the dedup key, so the hash matches the
  currency used everywhere else.
- **Other tools:** none. No dependency on plan-verifier or the diagram stack.

## Non-goals

- No change to trigger conditions (`.md` reads only), extraction strategy, thresholds,
  or the never-block policy — those are settled in `design.md`.
- No cross-session dedup memory — the state is per session/transcript and disposable.
- No attempt to *resolve* dynamic dispatch (that would be inference); the tool only
  labels the uncertainty honestly.
- This file does not modify or supersede `design.md`; it is additive.

## Open questions

1. **[Technical research] State-file location and lifecycle.** Where does the per-
   session dedup file live — OS tempdir keyed by transcript id? `~/.claude/` cache dir?
   It must survive across hook invocations within a session, be safely writable from a
   hook, and be cheap to abandon (stale files from dead sessions need a cleanup story:
   TTL on read, or key the filename by transcript id so leftovers are inert). Verify
   which field of the hook JSON reliably carries a transcript/session id.
2. **[Technical research] `unresolved_refs` matching precision.** Bare-name matching on
   `reference_name` will hit common names (`run`, `main`) and could splash the
   "dynamic dispatch" warning too widely. Measure hit rates on the pilot repos
   (codegraph-piggyback, falkor-writ) before shipping; decide whether to require the
   name to also resolve to exactly one node before flagging.
3. **[Human-judgment] Should an `unresolved_refs` hit *promote* severity?** The
   blueprint says flag it; it doesn't say whether a 0-caller name with a dynamic hit
   should break the "0 callers → silent" rule. Recommended: yes, emit it at LOW with
   the warning (the whole point is that 0 is a lie there) — but this changes the
   shipped silence contract, so it needs a sign-off.
4. **[Human-judgment] Pointer verbosity under the 30-line budget.** When a doc mentions
   many names, definition pointers compete with caller lists for the budget. Confirm
   the drop order proposed above (drop pointers from lowest-severity lines first)
   or choose an alternative (e.g. always keep pointers, truncate caller lists harder).
