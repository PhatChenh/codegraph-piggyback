# Red-team r3 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own model-specific quirks. Cross-model can catch opus-lineage blind spots; it cannot certify they are all caught. Closed r1 (unreadable→`codegraph index`) and r2 C1/M2 (private openers / PRE-INDEX copy) are not re-filed as the same IDs; this round attacks the **amend’s new gates** (OQ-4 A test list, one-opener grep, C-08 substring tests) and the residual Cursor deny that was “punted to spec” without an Open Question.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk source + live sqlite / `codegraph init` this session).
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

A fourth plain-string `"unreadable"` is still the cheapest honest name: `!= "usable"` consumers stay fail-closed, `unrecognized` stays a real foreign version, and a smashed file can no longer ride a greenfield marker. Dropping the post-init `codegraph index` hop matches live evidence. The WAL `_connect` retry (plain `ro` first, `immutable=1` only on `unable to open database file`) is the only way that fourth name does not also brand every healthy `codegraph init` as dead — live this session, a fresh init is WAL `write_version=2` with no sidecars, `mode=ro` ping fails, `immutable=1` reads `{1,5}` and writes no sidecar. Folding every production `mode=ro` open onto that helper is required so `probe == "usable"` cannot pair with a silent-empty C16/C12/blast read. That is the strongest honest case. It still pins the retry and the fold with assertions a DELETE-mode fixture already satisfies, and it still treats a Cursor copy-refresh as a deny.

## Verdict

**revise** — 1 CRITICAL, 2 MAJOR. Do not spec OQ-4 A or the one-opener fold until the named tests assert WAL `write_version=2` (plain `ro` ping fails). Do not ship C-08 / blast-gate tests as a substring ban on `codegraph index`. Do not treat a silent `diff` of the Claude-shaped Cursor copy as Write-deny.

---

## CRITICAL

### C1. OQ-4 A and the r2-C1 fold are pinned by assertions a non-WAL `make_index` fixture already satisfies. The retry and the private-opener fold can both be skipped; every listed pytest still greens; every fresh `codegraph init` still looks dead.

Where: Chosen Approach §7 OQ-4 A tests (a)–(c); one-opener tests (a)–(c); Assumption 11 (WAL evidence lives in prose, not in the assert list)
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): After this ships, `writ codegraph-init` / `codegraph init` still leaves an index the Write gate will call unreadable (or swallow as stale if the unreadable branch is also skipped). The operator is told to rebuild a map that was just built. That is the bucket’s headline bug, re-entered through the test scoreboard that was supposed to close it. C16 DENY on a freshly built index stays silent for the same reason r2 called CRITICAL — the new tests do not force the WAL fixture they name.

Evidence:

Design assertions (the only pytest pins):

> (a) that fixture → `probe() == "usable"`, and the directory still holds **no** `-shm`/`-wal`
> (b) `report_for_file` … returns **rows, not `[]`**
> (c) junk bytes and `chmod 000` still → `"unreadable"`
> one-opener (a)(b) `_c16_resolve_node` / `_c12_container` not `None`; (c) `mode=ro` in exactly one `bin/lib/` file

No listed assert requires `write_version == 2`, and none requires that plain `mode=ro` ping still fail. Existing fixture builders already produce the passing shape without any retry:

`falkor-writ/tests/test_codegraph_index.py:70` / `tests/test_writ_codegraph_init.py:98` — `sqlite3.connect(idx)` (default DELETE journal).

Live this session, that shape:

```
make_index-like write_version 1  read_version 1
listing [codegraph.db]
probe usable
ro ping [(1,)]          # no retry needed
after ro listing [codegraph.db]
```

Live this session, a real `codegraph init` (the state OQ-4 A exists for):

```
Indexed 1 files · 2 nodes
listing [.gitignore, codegraph.db]
write_version 2
ro ping  OperationalError('unable to open database file')
imm ping OK schema_versions=[(1,), (5,)]
imm nodes unique_rt3_symbol OK
after imm listing still [.gitignore, codegraph.db]
today's probe on this db = ('unrecognized', frozenset(), frozenset({1, 5}))
```

After the enum change with **no** `_connect` retry, that SELECT becomes `"unreadable"`. Wrapper exit 1, blast-gate deny, PRE-UNREADABLE deny — on a healthy fresh init.

Simulation (honest OQ-4 prose, bad-faith assertions):

1. Implement the enum + deny copy. Skip `_connect` retry. Skip folding `_c16_resolve_node` / `_c12_container` / `blast_radius._connect`.
2. Build OQ-4 / one-opener fixtures with the existing `make_index` / `_index_usable` helpers (write_version 1).
3. (a) probe usable, no sidecars. (b) `report_for_file` returns rows because DELETE-mode `mode=ro` works. (c) junk/chmod unreadable without touching WAL. C16/C12 not-None on the same DELETE fixture. Optionally rewrite C12/C16 to `sqlite3.connect(str(path))` so grep (c) also passes **and** a real WAL db starts working by creating `-shm`/`-wal` (C-12 / “fallback must not write” is only asserted on `probe()`, live this session RW open on a fresh-init db created both sidecars).
4. Every named pytest green. The one live `writ codegraph-init` is a manual step; wrapper pytest uses `fake_codegraph` + `_make_usable_index` (`test_writ_codegraph_init.py:47-54, 93-106`) and never sees WAL.

Simpler design that removes the problem: the test is the fixture. Assert `header[18] == 2` (or `PRAGMA journal_mode` via a one-shot write that is then discarded is the wrong tool — assert the bytes), assert plain `file:?mode=ro` ping still raises `unable to open database file`, then assert `probe() == "usable"` and no sidecar. Same three asserts on `_c16_resolve_node` / `_c12_container` / `report_for_file` using **that** db, not `make_index`. Do not accept “or copy a codegraph.db alone” unless the copy’s header is WAL.

Check:

```
# DELETE fixture already usable without retry (this session):
python3 -c "..."  # write_version 1, probe usable, ro ping OK

# Real init still not usable today (this session):
T=$(mktemp -d); cd "$T"; git init -q .; echo 'def unique_rt3_symbol(): return 1' > unique_rt3.py
git add unique_rt3.py; git -c user.email=t@t -c user.name=t commit -qm i
codegraph init "$T"
# write_version 2, ro ping OperationalError, today's probe unrecognized
```

---

## MAJOR

### M1. C-08 + the named blast-gate / PRE-INDEX tests forbid the substring `codegraph index`. The specified deny and PRE-INDEX sentences contain that substring as a noun phrase. Honest copy fails the test; honest test forbids the copy.

Where: C-08; §3 unreadable / missing deny copy; §4 PRE-INDEX rewrite; §7 `test_blast_gate_hook.py` unreadable fixture; §7 PRE-INDEX / PRE-SCHEMA copy test
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The test that is supposed to stop the deny text from sending the operator to `codegraph index` cannot pass against the sentences the design itself writes. A worker will either gut the noun phrase (“this repo’s database file…”) or weasel the assert (`"Run \`codegraph index\`" not in`). Either way C1-a’s flagship pin does not actually pin the command, and pre-mortem 1 (“without this file the unreadable branch can be skipped”) is the scoreboard a lazy executor plays.

Evidence:

C-08:

> “`codegraph index` appears in none of them — **including the audit-seat findings** PRE-INDEX and PRE-SCHEMA”

Specified copy (noun phrase includes the two words):

> unreadable: “This repo's **codegraph index** file exists but cannot be read … Run `writ codegraph-init`”
> missing (unchanged): “This repo has no **codegraph index** …”
> PRE-INDEX rewrite: “No **codegraph index** for this repo. Run `writ codegraph-init` …”

Named tests (substring, matching this file’s existing style `assert "writ codegraph-init" in result.stdout` at `tests/test_blast_gate_hook.py:146`):

> unreadable deny reason **contains** `writ codegraph-init`, **does not contain** `codegraph index`, and **does not contain** `stale`
> PRE-INDEX / PRE-SCHEMA “do **not** contain `codegraph index` as the repair command”

Live this session, Python substring check on the specified strings:

```
unreadable contains 'codegraph index': True
PRE-INDEX contains 'codegraph index': True
missing deny contains 'codegraph index': True
PRE-SCHEMA contains 'codegraph index': False
unreadable contains 'writ codegraph-init': True
unreadable contains 'stale': False
```

Existing PRE-INDEX test (`tests/test_artifact_claims.py:1670`) asserts `"index" in msg.lower()` — that still passes, and does not save the new test.

Simulation: implement the specified unreadable sentence; add `assert "codegraph index" not in reason`. Pytest red. Change the assert to `assert "Run \`codegraph index\`" not in reason`. Pytest green. C-08 as written is still false. Leave the unreadable branch out entirely and map to `else` stale: the “does not contain `stale`” pin is the only thing that would catch it — if the worker also weasels that pin, pre-mortem 1 lands.

Check:

```
python3 -c 's="This repo'\''s codegraph index file exists..."; print("codegraph index" in s)'
```

---

### M2. Cursor Write-deny is still “refresh the byte-identical Claude copy.” `writ-doctor` still does not copy it. Dual-envelope was “carried into the spec as an open question” but is not in Open Questions. C-04 still treats the Cursor copy as a deny.

Where: Surface-capability matrix note (b) + “Status after RT r2”; §3 “Same step, second file”; C-04; Open Questions (OQ-1..4 only); Assumption 9
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): Claude gets the new `unreadable` sentence. Cursor keeps running a script that always exits 0 (`writ-blast-gate.sh:26`) and emits only `hookSpecificOutput.permissionDecision`. If that envelope still does not block a Write — live-documented for this machine — the operator on Cursor is not denied for missing, unrecognized, stale, *or* unreadable. A silent `diff` of the two files still counts the step done. Spec will not see an OQ to decide, because none was written.

Evidence:

Design:

> “whether Cursor honors *this envelope* as a deny is **not verified here**”
> “The step is not done until the copy is refreshed through the supported path (`writ-doctor` / the install script that placed it) and a `diff` between the two files is silent.”
> “the dual-envelope question … is a **residual MAJOR carried into the spec as an open question** — deliberately not designed this round”
> C-04: “denied is the Claude Write/Edit path plus the Cursor Write copy wired at `~/.cursor/hooks.json`”

Open Questions (§) lists OQ-1 CLOSED, OQ-2 busy, OQ-3 empty `schema_versions`, OQ-4 CLOSED. No dual-envelope / `permission` slot.

Live this session:

- `diff` of `falkor-writ/.claude/hooks/writ-blast-gate.sh` vs `~/.cursor/hooks/writ-blast-gate.sh` → IDENTICAL (Claude envelope only; exit always 0).
- `rg cursor/hooks|copy_pair|writ-blast-gate` on `falkor-writ/bin/writ-doctor.sh` → no match. Doctor prints `freshness()` at `:367`.
- Copy path is `agent_village/scripts/hooks/install.sh` `copy_pair` over manifest row `writ-blast-gate` (`manifest.json:640-649`).
- Cursor contract, `agent_village/docs/cursor/CURSOR-KNOWLEDGE.md:246-255`: deny is flat `{"permission":"deny",...}`; “Claude nesting alone did NOT block a Write on this machine LIVE.”
- `~/.cursor/hooks.json:84-86` runs the copy on `preToolUse` / `Write` with `failClosed: true`.

Grill R15: deny copy is command text, not a Claude-only hook event. Dual envelope is a script-body edit already in this step, not a `hooks.json` edit (grill: no settings/hooks.json edit).

Simulation: edit `.claude/hooks/writ-blast-gate.sh`, run `writ-doctor`, Cursor copy unchanged (doctor never copies). Or run `install.sh`, `diff` silent, JSON shape unchanged, Cursor still does not deny. Both satisfy “refresh the copy.” Spec never asked, because OQ does not exist.

Simpler design that removes the copy-refresh half: move `deny_reason(verdict, …)` into `blast_radius.py` (the Cursor copy already imports Python from `WRIT_DIR`). The twin cannot drift on strings. Envelope still needs a live Cursor check — that is the OQ that must actually appear in Open Questions.

Check:

```
diff -q falkor-writ/.claude/hooks/writ-blast-gate.sh ~/.cursor/hooks/writ-blast-gate.sh
rg -n 'cursor/hooks|copy_pair' falkor-writ/bin/writ-doctor.sh
sed -n '655,688p' docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
sed -n '246,255p' agent_village/docs/cursor/CURSOR-KNOWLEDGE.md
```

---

## Audits (what was verified, not restated)

1. **Fact:** WAL-no-shm / junk `DatabaseError` / chmod 000 `OperationalError('unable to open database file')` at **connect** / schema-less `no such table` / `FRESH_CACHE_TTL = 300` at `blast_radius.py:69` / `cli.py:990-992` passthrough / `codegraph.ts:615,623,631,749-751` quotes — live or read this session. OQ-4 test list does not assert `write_version=2` (C1). Specified deny strings contain `codegraph index` (M1).
2. **Consistency:** C-08 vs §3/§4 noun phrases (M1). C-04 + “carried into spec as OQ” vs Open Questions OQ-1..4 (M2). Option A “C-12 ✅ mode=ro connect unchanged” vs §1.0 `immutable=1` retry — not filed (constraint holds; the check-box text is sloppy).
3. **Gaming:** transcripts in C1 / M1 / M2. Extra: C12/C16 rewritten as RW `sqlite3.connect(str(path))` satisfies one-opener (a)–(c) on any fixture and creates sidecars on a real WAL db (live this session).
4. **Feasibility:** `_connect` retry string matches live WAL ping and chmod connect. Dirty WAL with `-wal` and no `-shm`: plain `ro` **succeeds** (and recreates `-shm`); `immutable=1` then reads a stale main file (`no such table: t`). Design’s “ro first” order is load-bearing; crashed leftover is **not** the fresh-init case. Not re-filed as laundering.
5. **Contracts:** C1-a hop-drop holds. Scope ITEM-1-writ still names an `index` retry; grill C1-a supersedes — not re-filed. Grill “one surface: probe + four consumers” grew `_connect` + two private openers; incomplete test pin is C1, not a surface-count nit.
6. **Missing-by-construction:** author position “WAL-no-sidecar fixture” hides that every listed assert is already true of DELETE-mode `make_index`; “Cursor twin = diff silent” hides envelope and install path; “residual MAJOR into spec as OQ” hides that OQ was not written.

Human-authority: Cursor deny-envelope is security posture / fail-closed operating burden. The design notes it unverified then files C-04 as ✅ on the Cursor copy and omits the OQ (M2). OQ-4 A “owner not re-asked” treated as craft: without the retry, `"unreadable"` means every fresh init; the defect is the test pin (C1), not the choice to retry.

No MINOR filed (dispatch asked CRITICAL/MAJOR only).
