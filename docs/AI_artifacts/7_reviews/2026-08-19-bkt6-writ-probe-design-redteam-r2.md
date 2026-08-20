# Red-team r2 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own model-specific quirks. Cross-model can catch opus-lineage blind spots; it cannot certify they are all caught. Closed r1 IDs (unreadable→`codegraph index` routing) are not re-filed; this round attacks the C1-a / OQ-4 A amend.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk source + live sqlite this session).
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

A fourth plain-string `"unreadable"` is the cheapest honest name: every `!= "usable"` consumer stays fail-closed, `unrecognized` stays a real foreign version, and a smashed file can no longer ride a greenfield marker. Dropping the post-init `codegraph index` hop is the right C1-a reading — live, `index` cannot repair junk, and Bucket 4 `init` already unlinks. The WAL `_connect` retry (plain `ro` first, `immutable=1` only on `unable to open database file`) is the only way that fourth name does not also brand every healthy `codegraph init` as dead: live this session, a fresh init is WAL with no sidecars, `mode=ro` ping fails, `immutable=1` reads `{1,5}` and writes no sidecar. Folding `blast_radius._connect` into that opener is required so `probe == "usable"` cannot pair with an empty blast report. That is the strongest honest case. It still leaves two sibling `mode=ro` opens on a DENY check, and it treats a Cursor copy-refresh as a deny.

## Verdict

**revise** — 1 CRITICAL, 2 MAJOR. Do not spec OQ-4 A as “one opener” until every production `mode=ro` open is on it. Do not treat a byte-identical Cursor copy of the Claude envelope as Write-deny.

---

## CRITICAL

### C1. OQ-4 A makes `probe()` usable on a fresh WAL index, then leaves C16 (DENY) and C12 on private `mode=ro` opens that still fail. Dispatch is unblocked; the consumer-sweep DENY goes silent.

Where: Chosen Approach §1.0 / §2 (OQ-4 A); consumer table rows 6–8; OQ-4 tests (a)–(c) only
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): After a successful `writ codegraph-init`, the audit seat will stop saying “unknown schema, found none” (that is the point of OQ-4). The check that is supposed to DENY a plan that renamed something without naming its other callers will not run. A freshly built index looks healthy and dispatch can proceed with that DENY class skipped. Today those same repos cannot dispatch at all (PRE-SCHEMA). The amend unblocks them without moving the DENY onto the new opener.

Evidence:

Design (the class it already named, applied only to `blast_radius`):

> “A probe that says `usable` while these opens still fail is worse than the original bug”
> “Fix: point `blast_radius._connect` at `codegraph_index._connect` … One opener, one fallback. Do **not** copy the retry into a second place”
> Consumer rows 6–8: C11/C12/C16 “no — silent by design (M5)” because `probe != "usable"`

On-disk, C11 does use `codegraph_index._connect` (`enclosing_symbol` / `callers_of` at `artifact_claims.py:2301-2304`). C16 and C12 do **not**:

```
2166:        con = sqlite3.connect(
2167:            f"file:{Path(repo) / '.codegraph' / 'codegraph.db'}?mode=ro",
```

(`_c16_resolve_node`, then `if node is None: continue` at `:2229-2230` — C16-CONSUMERSWEEP is **DENY**)

```
2488:        con = sqlite3.connect(
2489:            f"file:{Path(repo) / '.codegraph' / 'codegraph.db'}?mode=ro",
```

(`_c12_container`, then `if iface is None: continue` at `:2382-2384`)

Live this session, fresh `codegraph init` (WAL, listing = `.gitignore` + `codegraph.db` only):

```
probe            = ('unrecognized', frozenset(), frozenset({1, 5}))
report_for_file  symbols=[]  blast=set()
_c16_resolve_node('foo') = None
enclosing_symbol         = None
mode=ro ping             OperationalError('unable to open database file')
mode=ro&immutable=1      schema_versions=[(1,), (5,)]
```

After one read-write open, sidecars appear and the private openers start working. OQ-4 A’s named tests (probe usable, `report_for_file` rows, junk/chmod still unreadable) do not touch `_c16_resolve_node` / `_c12_container`. A lazy executor passes every listed test and ships the hole.

Simulation (honest OQ-4 A, bad-faith completeness):

1. Implement `_connect` retry + `blast_radius` delegate + enum. Skip C12/C16 opens (table says “no”).
2. `codegraph init` on a new repo → probe `usable`, PRE-SCHEMA gone, PRE-UNREADABLE gone.
3. Plan with a change-verb + identifier → `check_c16` enters (`probe == "usable"`), `_c16_resolve_node` execute fails, `continue`, findings `[]`.
4. `--strict` dispatch exits 0. Named OQ-4 tests still green.

Simpler design that removes the problem: there is already one private opener in `codegraph_index._connect`. Delete the two copies in `artifact_claims.py` (and keep the blast_radius delegate). Do not add a third retry.

Check:

```
python3 - <<'PY'
# fresh codegraph init → probe unrecognized today; _c16_resolve_node None
# grep -n "mode=ro" falkor-writ/bin/lib/*.py
PY
rg -n 'mode=ro' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib
```

---

## MAJOR

### M1. Cursor Write-deny is specified as “refresh the byte-identical Claude copy.” Live Cursor docs say that envelope did not block a Write. `writ-doctor` does not copy the file.

Where: Surface-capability matrix Cursor Write row; §3 “Same step, second file”; C-04; Assumption 9
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The new `unreadable` sentence is written into a script Cursor is already running. If Cursor still does not treat Claude’s nested `permissionDecision` as a deny, the operator on Cursor never sees a block for missing, unrecognized, stale, *or* unreadable — and a silent `diff` of the two files will still count the step done. `writ-doctor` only prints a freshness line; it cannot refresh the twin.

Evidence:

Design:

> “the copy emits Claude's `hookSpecificOutput.permissionDecision` shape, while Cursor's documented deny field is `permission`; … whether Cursor honors *this envelope* as a deny is **not verified here**”
> “The step is not done until the copy is refreshed through the supported path (`writ-doctor` / the install script that placed it) and a `diff` between the two files is silent.”
> C-04: “denied is the Claude Write/Edit path plus the Cursor Write copy wired at `~/.cursor/hooks.json`”

Cursor contract, `agent_village/docs/cursor/CURSOR-KNOWLEDGE.md:246-255`:

```
Deny shape is **flat**:
{"permission":"deny","user_message":"…","agent_message":"…"}
… Claude nesting alone did NOT block a Write on this machine LIVE.
Emit both shapes in one object if a script must serve both harnesses.
```

Live this machine: `~/.cursor/hooks.json:84-86` runs `bash /Users/phatchenh/.cursor/hooks/writ-blast-gate.sh` on `preToolUse` / `Write` with `failClosed: true`. The script (source `:204-211`) still emits only `hookSpecificOutput.permissionDecision`. Exit is always 0 (source `:26`).

`writ-doctor.sh:365-373` prints `freshness()`; it never copies `~/.cursor/hooks/`. The path that does is `agent_village/scripts/hooks/install.sh` `copy_pair` over manifest row `writ-blast-gate` (`manifest.json:640-649`).

Grill R15: blast-gate registered on Claude and Cursor; deny copy is command text. Dual envelope is a script-body edit already in this step, not a `hooks.json` edit (grill: no settings/hooks.json edit).

Simulation: edit `.claude/hooks/writ-blast-gate.sh`, run `writ-doctor`, `diff` still dirty or operator skips install.sh, Cursor keeps the pre-fix copy; **or** run install.sh, `diff` silent, Cursor still does not deny because the JSON shape is unchanged. Both satisfy a “refresh the copy” reading; neither produces a verified Cursor deny.

Check:

```
sed -n '246,255p' /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/docs/cursor/CURSOR-KNOWLEDGE.md
rg -n 'cursor/hooks|copy_pair|blast-gate' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-doctor.sh
rg -n 'permissionDecision' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh
```

---

### M2. C-08 / C1-a: `codegraph index` appears in none of the three audit/deny messages. The missing-index audit line, marked unchanged, still tells the operator to “Run the codegraph index”.

Where: C-08; Chosen Approach §4 `elif probe == "missing": …unchanged marker logic`
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The amend’s whole point was to stop naming a command that cannot repair the file. The Write-deny copy and the new PRE-UNREADABLE line were updated. The audit seat’s missing-index DENY was explicitly left alone, so an agent following the pre-dispatch finding still runs `codegraph index`, which live exits 1 with “Run codegraph init first” when the db is absent — the same operator loop r1 called CRITICAL, now only on the dispatch path.

Evidence:

Design C-08:

> “Three split deny/audit messages, all naming **`writ codegraph-init`** … `codegraph index` appears in none of them.”

Design §4:

> `elif probe == "missing": …unchanged marker logic…`

Live `artifact_claims.py:987-989`:

```
"No codegraph index for this repo. Run the codegraph index "
"before dispatch, or mark the repo greenfield "
```

PRE-SCHEMA (`:1002-1004`) also still says “Rebuild the index at a known schema version” with no wrapper name. Named tests pin the blast-gate deny reason and PRE-UNREADABLE; they do not pin PRE-INDEX wording. A lazy executor follows “unchanged marker logic” and C-08 fails with every listed test green.

Check:

```
rg -n 'Run the codegraph index' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py
```

---

## Audits (what was verified, not restated)

1. **Fact:** WAL-no-shm / junk / chmod 000 / init-on-chmod errcode 14 / `FRESH_CACHE_TTL = 300` at `blast_radius.py:69` / `cli.py:990-992` passthrough — live or read this session. Consumer sweep under-counted production `mode=ro` opens (C1).
2. **Consistency:** C-08 vs §4 unchanged PRE-INDEX (M2). C-04 vs matrix note (b) vs Cursor LIVE envelope (M1).
3. **Gaming:** transcripts in C1 / M1 / M2. OQ-4 test list is the scoreboard a lazy executor plays.
4. **Feasibility:** `_connect` retry string is exactly `unable to open database file` (live). chmod 000 fails at **connect**, WAL-no-shm at **ping** — both usable as `unreadable` if connect-raise is not retried. Writer+`-shm` present: plain `ro` ping **succeeds** (busy-as-unreadable is rarer than the copy claims; not load-bearing).
5. **Contracts:** C1-a hop-drop holds in this text. Scope ITEM-1-writ still names a `codegraph index` retry; grill C1-a supersedes — not re-filed. OQ-4 A is an extra surface the grill called “one contract: probe + four consumers”; incomplete fold is C1.
6. **Missing-by-construction:** author position “one opener” hides the two `artifact_claims` copies; “Cursor twin = diff silent” hides envelope and install path.

Human-authority: OQ-4 A closed “owner not re-asked.” Treated as craft only insofar as it is required to keep `"unreadable"` from meaning “every fresh init.” The defect is the incomplete fold (C1), not the choice to retry.

No MINOR filed (dispatch asked CRITICAL/MAJOR only).
