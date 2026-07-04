---
name: ssot-curate
description: Hand-hold a non-coder through curating a repo's decision index — walk every unverified anchor, judge keep/drop/re-anchor, apply edits, then `decision_index refresh` to flip verified:true. Use when `decision_index.py status` shows anchors as `verified:false` (a freshly-bootstrapped or partially-curated index at `docs/decision-index.json`).
---

# ssot-curate — interactive decision-index curation

You are hand-holding a **non-coder solo builder** through making a repo's
`docs/decision-index.json` honest. Bootstrap (`decision_index.py bootstrap`)
seeds anchors as `verified:false` because it cannot tell a real dependency from
a backtick token that happened to resolve — that judgment is a human call.
Your job: be that human's eyes + hands, **one anchor at a time, asking before
every change.**

> **Frozen principle (from BLUEPRINT + `decision_index.py` docstring):** an LLM
> may *propose* and *explain*, but the `verified:true` flip is human-owned. You
> apply the flip only after the user explicitly confirms each judgment
> (CLAUDE.md §2 decision checkpoints). Never auto-verify.

You edit: `docs/decision-index.json` (add/drop/re-anchor) + run
`decision_index refresh <id>` (the only sanctioned way to flip
`verified:false → true`). You never touch `.codegraph/codegraph.db`.
You never run `bootstrap` (would reseed + overwrite curated work).

## Tools this skill calls

All run from the **target repo root** (where `.codegraph/` lives) so DB walk-up
finds it. The tool itself lives at
`~/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/decision_index.py`.

| Command | What it does | When you call it |
|---|---|---|
| `python3 .../decision_index.py status --json` | JSON of every anchor + FRESH/STALE/ORPHANED/AMBIGUOUS + verified flag | Start. Parse to find unverified anchors. |
| `codegraph explore "<symbol or question>"` / `codegraph node <symbol-or-file>` | Read anchor's real code without opening files (gate requires codegraph before Read on .ts/.tsx/.py/etc) | For every anchor you judge. MCP `codegraph_explore` / `codegraph_node` equivalent. |
| `decision_index refresh ADR-000X` | Re-snapshot sigs from current code + set `verified:true` on that ADR's existing anchors | Once per ADR, AFTER the user has settled its anchors. |
| `decision_index status` | Human-readable final report | End — exit 0 confirms all green. |

## What the tags mean (so you can explain to the user)

`decision_index status` recomputes each anchor's live signature from the
codegraph DB (current code) and compares to the stored snapshot:

- **FRESH** — stored sig == current sig. Code unchanged since snapshot.
- **STALE** — sig differs. Code drifted since the ADR was last confirmed. The
  anchor still resolves — open the ADR, confirm the decision still holds
  against the *new* code → refresh.
- **ORPHANED** — the symbol/file is gone (renamed, deleted). Re-anchor to the
  new location, or drop if the decision no longer depends on it.
- **AMBIGUOUS** — the symbol name resolves to >1 definition. Re-anchor with the
  fully-qualified `QName@path` so it pins one.

A freshly-bootstrapped anchor is `verified:false` regardless of tag — bootstrap
is a seed, not a confirmation.

## Scope (what this skill handles vs not)

**Handles:** every anchor where `verified == false` — seed curation. The tag
(FRESH/STALE/ORPHANED/AMBIGUOUS) informs the per-anchor judgment; the skill
walks all four.

**Does NOT handle:** an anchor that is already `verified:true` and later went
STALE (drift detected *after* curation). That's the roadmap's P7 drift-advisory
layer — out of scope here. If you see verified:true + STALE during `status`,
note it in the final report and move on (do not re-verify it).

## The curation loop

### 1. Gather the worklist

Run from the target repo root:

```bash
python3 ~/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/decision_index.py status --json
```

Parse the JSON. Group by ADR. Note:
- ADRs with zero anchors (will need additions — step 4).
- Per-ADR: which anchors are `verified:false` (your worklist), and their tag.

Tell the user, in plain English, what you see: "Repo X has N ADRs, M anchors,
K are unverified. ADR-0003 has 0 anchors — we'll add some. Here's the plan:
we go ADR by ADR, I read the decision + the anchor's code, I tell you my
judgment, you confirm, I apply, then we lock it with `refresh`."

### 2. Per ADR — read the decision first

Before judging any anchor, read the ADR markdown (`docs/adrs/ADR-XXXX-*.md`).
You cannot judge "does this decision depend on this code" without knowing what
the decision *is*. Summarize the decision to the user in 1-2 plain-English
sentences before the first anchor of each ADR.

### 3. Per anchor — judge, then ask

For each unverified anchor in the ADR:

**a. Read the anchor's reality via codegraph (NOT Read, NOT grep — the repo is
codegraph-indexed and there is a gate).** Two shapes:

- `file:<relpath>` → read the file: `codegraph node <relpath>` (or
  `codegraph_explore "<relpath>"`).
- `<QName>@<relpath>` → read the symbol: `codegraph node <symbol-or-file>` /
  `codegraph_explore "<symbol names or question>"`.

MCP equivalents (`codegraph_node` / `codegraph_explore`) when available; shell
fallback always works. **Verify the symbol resolves uniquely** — if
`codegraph_node` reports "N definitions named X", the anchor is AMBIGUOUS and
you must re-anchor with the fully-qualified name, or switch to a `file:` anchor.

**b. Judge, against the decision you read in step 2:**

| Situation | Judgment |
|---|---|
| Decision genuinely rests on this code; tag FRESH or STALE-but-holds | **keep** → confirm via user → `refresh` will re-snapshot + verify |
| Decision still rests on the code; code legitimately changed since ADR (STALE) and decision still holds vs new code | **keep** → same — `refresh` re-snapshots the new sig + verifies |
| Anchor is wrong — bootstrap attached a token that resolved but the decision doesn't depend on it (e.g. `model` → an LLM field the ADR never uses) | **drop** the anchor object from the JSON |
| Anchor is AMBIGUOUS (>1 def) | **re-anchor** with fully-qualified `QName@path`, or fall back to `file:<path>` if no single symbol is the right one |
| A field/method is mentioned but the decision is really about the owning type/file | **re-anchor** to the owning type or file |
| Code/symbol is gone (ORPHANED) | **re-anchor** to the new location, or **drop** if the dependency is gone |
| ADR has 0 anchors but genuinely depends on code | **add** anchors (step 4) |

**c. Ask the user** (AskUserQuestion, 2-4 options, recommend one first with
"(Recommended)"):

> ADR-0001 (per-generation image-model picker) anchor
> `OpenAiCompatClient::model` — this is an LLM text-model field. The ADR is
> about the *image* model picker and explicitly says the LLM model is NOT
> exposed. Decision doesn't rest on this code.
>
> - Drop it, re-anchor to curated-set contract (Recommended)
> - Keep it
> - Re-anchor to something else

**d. Apply the user's choice immediately:**
- keep → leave the anchor as-is (it gets verified at the `refresh` step).
- drop → delete the anchor object from `docs/decision-index.json`.
- re-anchor → edit the `ref` field to the new `QName@path` or `file:<path>`.
- add → append a new anchor object `{"ref": "...", "sig": null, "verified": false}`.

Edits are direct JSON edits. **Set `sig: null`** on any new/changed anchor —
`refresh` will fill the real signature from current code.

### 4. Empty ADRs — add anchors

For any ADR with zero anchors (bootstrap skipped its tokens as ambiguous, or
it's a real decision with real deps the heuristics missed):

- Read the ADR → identify what code the decision actually depends on.
- Resolve each candidate via `codegraph node <symbol>` / `codegraph_explore`
  — confirm it resolves uniquely before anchoring.
- Propose the anchor set to the user with judgment + reasoning, ask to confirm,
  then add the anchor objects (sig: null, verified: false).

If an ADR is genuinely a meta-decision with no code dependency, **say so
explicitly** in your final report — do not leave it silently empty.

### 5. Supersedes chains — read the prose

For every ADR, read its prose for "supersedes", "replaces", "obsoletes".
If ADR-X replaces ADR-Y:
- set `decisions[ADR-X].supersedes = "ADR-Y"`.
- set `decisions[ADR-Y].status` to reflect it (`superseded`) so it renders
  disabled.

Only set a chain when the prose genuinely states it. "Extends", "aligns with",
"builds on" are NOT supersedes — leave `null`. When in doubt, ask the user.

### 6. Lock the ADR — `refresh`

After the user has settled every anchor in one ADR (kept/dropped/re-anchored/
added, supersedes decided), run:

```bash
python3 ~/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/decision_index.py refresh ADR-000X
```

This re-snapshots every anchor's sig from current code AND flips
`verified:false → true`. It refuses to refresh an ORPHANED/AMBIGUOUS anchor
(fix the anchor first). Watch for the stderr warning `"<ref>: <state> — not
refreshing (fix the anchor first)"` and fix before continuing.

Repeat per ADR until all 8 (or however many) refreshed.

### 7. Final report

Run `decision_index status` (no `--json`) → should print all FRESH + exit 0.
Then report to the user, per ADR:
- anchors kept / dropped / re-anchored / added.
- supersedes set (or "none").
- any verified:true + STALE drift noted for separate handling (P7).
- the final `status` output.

Leave the working tree dirty — the user reviews the diff before committing.

## Guardrails

- **Never run `bootstrap`.** It would reseed + overwrite curated work
  (`--force` required anyway).
- **Never write to `.codegraph/codegraph.db`.** It is read-only, always.
- **Never auto-flip `verified:true`.** Only `refresh` does that, and only
  after the user has confirmed every anchor's judgment.
- **Ask before every change.** Keep the user in the loop per CLAUDE.md §2.
  The only batched action at the end is `refresh` per ADR, and only after the
  user has settled that ADR's anchors.
- **codegraph before Read.** This repo is indexed; the gate requires
  `codegraph_explore` / `codegraph_node` before Read on code. Use shell
  `codegraph explore` / `codegraph node` if MCP is unavailable.
- **Caveman off for ADR prose you quote.** Read it to the user verbatim when
  the decision reasoning matters.

## Reference: anchor ref notation

- `file:<relpath>` — a file anchor; sig = `files.content_hash`.
- `<qualified_name>@<relpath>` — a symbol anchor; sig = sha256 of source slice.
  - qualified_name for methods is `Class::method` (e.g.
    `CapabilitySlot::listModels@lib/ai/image/index.ts`).
  - bare `name@path` is fine **only** if the name is unique in that file;
    `codegraph node <symbol>` confirms uniqueness.

## Exit criteria (done when ALL hold)

1. `decision_index.py status` exits 0 (every anchor FRESH — no
   STALE/ORPHANED/AMBIGUOUS).
2. Every anchor in the index has `verified: true`.
3. Every `supersedes` chain that should exist does exist; superseded ADRs
   flagged in `status`.
4. Every ADR with 0 anchors is either given real anchors, or documented as a
   meta-decision in the final report (never silently empty).
