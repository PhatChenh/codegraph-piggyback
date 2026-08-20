# Red-team r4 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own model-specific quirks. Cross-model can catch opus-lineage blind spots; it cannot certify they are all caught. Closed r1 (unreadable→`codegraph index`), r2 C1/M2 (private openers / PRE-INDEX copy), and r3 M1/M2 (noun-substring ban / missing OQ-5) are not re-filed as the same IDs. This round attacks the **r3 amend’s new gates** (WAL asserts 1–2, “same test or its fixture”, `sqlite3.connect(` count, command-string ban, OQ-5).

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk source + live sqlite / `codegraph init` this session). SQLite URI `immutable=1` semantics: https://sqlite.org/uri.html (fetched 2026-08-19).
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

A fourth plain-string `"unreadable"` is still the cheapest honest name: `!= "usable"` consumers stay fail-closed, `unrecognized` stays a real foreign version, and a smashed file can no longer ride a greenfield marker. Dropping the post-init `codegraph index` hop matches live evidence. The WAL `_connect` retry (plain `ro` first, `immutable=1` only on `unable to open database file`) is the only way that fourth name does not also brand every healthy `codegraph init` as dead — live this session, a fresh init is WAL `write_version=2` with no sidecars, `mode=ro` ping fails, `immutable=1` reads `{1,5}` and writes no sidecar. Folding every production `sqlite3.connect(` under `bin/lib/` onto that helper is required so `probe == "usable"` cannot pair with a silent-empty C16/C12/blast read. Pinning the fixture by header bytes plus a raw `mode=ro` ping failure is the right discriminator against DELETE-mode `make_index`. C-08’s ban on the command string ``Run `codegraph index` `` (not the noun) lets the specified copy pass. OQ-5 now exists for the Cursor envelope. That is the strongest honest case. It still pins the fixture and the *outcome*, not `_connect`’s URI order or retry predicate, and the blast-gate unreadable test still accepts the original `{none}` lie.

## Verdict

**revise** — 1 CRITICAL, 1 MAJOR. Do not spec OQ-4 A until a single test function (not “or its fixture”) drives asserts 1–3 on one db **and** a locked db stays `"unreadable"` (so immutable-only / retry-on-busy cannot green). Do not spec the unreadable deny copy until the named blast-gate test requires a distinctive phrase and forbids `unrecognized`.

---

## CRITICAL

### C1. The r3 WAL patch pins the *fixture*, not `_connect`. Asserts 1–2 are raw `sqlite3.connect` in the test. “Same test or its fixture” still lets 1–2 and 3–4 run on different dbs. On one WAL db, `_connect = immutable=1` only (or retry on any `OperationalError`) still greens the list. Live, that launders a locked DELETE db to usable and false-denies a live WAL writer.

Where: Chosen Approach §1.0 steps 1–4; §7 OQ-4 A asserts 1–5 + “same test or its fixture”; bad-faith table rows “OQ-4 assert 3 given 1+2 in front”; Risk row “`immutable=1` reads a db that IS being written”
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): After pytest is green, `codegraph init` / `writ codegraph-init` can still leave an index the Write gate calls unreadable — the bucket’s headline bug, re-entered because the new asserts never look at `_connect`. Or the opposite lie: a locked index reads as usable, Writes proceed on a torn map, C-04 fail-closed is gone. The operator is told to rebuild a map that was just built, or is allowed to edit while another indexer holds the file.

Evidence:

Design (load-bearing `_connect` contract, prose only):

> “1. open `file:{path}?mode=ro` as today; 2. ping it with `SELECT 1`; 3. on `sqlite3.OperationalError` whose message is `unable to open database file`: close … retry **once** with `?mode=ro&immutable=1`”
> “**Plain `ro` leads; `immutable=1` is never the first attempt.** … leading with it would read a live db without its WAL and would silently launder the `busy` case”
> “asserts 1–2 above must run in the same test **or its fixture**, so `probe()` being `usable` is proven to come from the fallback”
> Forbidden builders: `make_index` / `_make_usable_index` / `_index_usable` — **prose, no grep**
> Bad-faith table: assert 3 with 1+2 in front “**no**”; alone “**yes** — that was the r3 CRITICAL”

Named pytest pins (the only scoreboard):

1. `header[18:20] == b'\x02\x02'` — file bytes, not `_connect`
2. raw `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` then `.execute("SELECT 1")` raises `unable to open database file` — **the test’s own URI**, not `_connect`’s first attempt
3. `probe() == "usable"` and no `-wal`/`-shm`
4. folded readers not empty on that db
5. junk/chmod still unreadable on both URIs

No listed assert reads `_connect`’s URI, requires the first attempt to be plain `ro`, or requires a `"database is locked"` probe to stay `"unreadable"`.

On-disk fixture builders still DELETE-journal (`write_version` 1), no retry needed:

- `falkor-writ/tests/test_codegraph_index.py:70` `make_index` — `sqlite3.connect(idx)`
- `falkor-writ/tests/test_writ_codegraph_init.py:93-106` `_make_usable_index` — same
- `falkor-writ/tests/test_artifact_claims.py:1609` `_index_usable`

Live this session (python sqlite 3.51.0):

```
# real codegraph init (the state OQ-4 A exists for):
header[18:20] = b'\x02\x02'
listing [.gitignore, codegraph.db]
ro SELECT 1  OperationalError('unable to open database file')  # str(e) == that exact string
imm schema_versions [(1,), (5,)]
today's probe = ('unrecognized', frozenset(), frozenset({1, 5}))

# make_index-like DELETE:
# (r3 already: write_version 1, ro ping OK, probe usable)

# DELETE db + BEGIN EXCLUSIVE (writer holds lock):
ro SELECT 1 / schema  OperationalError('database is locked')
imm schema            ok [(1,)]     # USABLE if _connect leads with immutable or retries any OperationalError

# WAL + BEGIN IMMEDIATE (sidecars present, writer dirty):
ro  schema            ok [(1,), (5,)]   # design's "ro first succeeds while indexer holds -shm"
imm schema            OperationalError('no such table: schema_versions')  # false unreadable if immutable-first
```

SQLite URI docs (https://sqlite.org/uri.html, 2026-08-19): `immutable=1` “skips all file locking and change detection”; if the file changes anyway, “incorrect query results and/or SQLITE_CORRUPT”.

Simulation A (r3 C1 residual — split across “or its fixture”):

1. Skip `_connect` retry. Fold the three extra `sqlite3.connect(` sites so the one-opener grep is 1.
2. `test_wal_fixture_shape` (uses a real-init fixture): asserts 1–2 only.
3. `test_probe_usable` / assert 4: `make_index` / `_index_usable` (write_version 1). Probe usable, readers return rows, no sidecars.
4. Junk/chmod tests on their own files. Wrapper pytest still uses `fake_codegraph` + `_make_usable_index`.
5. Every named pytest green. Live `codegraph init` still probes unrecognized today; after the enum-only change it probes `"unreadable"`. Wrapper exit 1 on a healthy fresh init.

Simulation B (same WAL db, skip the order/predicate):

1. `_connect` opens `?mode=ro&immutable=1` first (or retries every `OperationalError`, including `database is locked`).
2. Asserts 1–2 still pass (they never call `_connect`). Assert 3–4 pass on the WAL-no-sidecar fixture.
3. Pytest green. DELETE exclusive lock → probe `"usable"` (C-04). Live WAL writer → `no such table` → `"unreadable"` false deny for the minutes an index run holds the WAL.

Simpler design that removes the problem: one test *function* (not a shared fixture name) that, in order, (1) asserts header `b'\x02\x02'`, (2) asserts raw `mode=ro` ping still raises `unable to open database file`, (3) asserts `probe() == "usable"` on **that same path object**, (4) opens a second connection with `BEGIN EXCLUSIVE` on a DELETE fixture and asserts `probe() == "unreadable"`. Do not accept “or its fixture”.

Check:

```
# DELETE exclusive + immutable launders (this session):
python3 -c '...'  # ro → database is locked; imm → [(1,)]

# Real init still not usable today:
T=$(mktemp -d); git -C "$T" init -q; echo 'def unique_rt4_symbol(): return 1' > "$T/unique_rt4.py"
git -C "$T" add unique_rt4.py; git -C "$T" -c user.email=t@t -c user.name=t commit -qm i
codegraph init "$T"
# header b'\x02\x02', ro ping OperationalError, today's probe unrecognized
```

---

## MAJOR

### M1. The named blast-gate unreadable test accepts the unrecognized deny copy. Freshness can return `"unreadable"` and the operator still sees “unknown schema, found none” — scope pre-mortem 1, one function later.

Where: §3 unreadable / unrecognized deny copy; §7 `tests/test_blast_gate_hook.py` unreadable fixture pins; C-08; Pre-mortem 1; `falkor-writ/.claude/hooks/writ-blast-gate.sh:180-195`
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The fourth name exists in `probe()` / `freshness()`. The Write deny the operator actually reads is still “unrecognized schema (found: {none})”. That is the lie this bucket exists to kill. Pytest is green because the new test never requires “cannot be read” and never forbids “unrecognized”.

Evidence:

§7 blast-gate pins for the unreadable fixture (complete list):

> deny reason **contains** `writ codegraph-init`, **does not contain** the command string ``Run `codegraph index` ``, and **does not contain** `stale`

Specified unreadable sentence (§3) is distinctive (`cannot be read`, `corrupt`, `locked`). The test does not require any of those words. It does not forbid `unrecognized`, `found`, or `none`.

Live unrecognized copy already in the hook (`writ-blast-gate.sh:191-195`), which is what an unreadable-as-unrecognized path prints today when `found` is empty (`:189` `or "none"`):

```
This repo's codegraph index is at an unrecognized schema version
(found: {none}; reader supports: {1, 5}).
Run `writ codegraph-init` to rebuild the index, then retry the write.
```

Python on that string this session:

```
writ codegraph-init     True
Run `codegraph index`   False
stale                   False
cannot be read          False
unrecognized            True
```

All three named pins pass. Existing `test_blast_gate_hook.py` has **zero** occurrences of `unreadable` / `cannot be read` (live count this session). `test_unrecognized_deny_names_both_version_sets` (`:181-193`) still only covers a foreign-version fixture.

§7 freshness pin (`freshness()` on schema-less → `"unreadable"`) lives in a different file. It forces the pass-through. It does **not** force the deny sentence.

C-08 / pre-mortem 1 claimed the blast-gate test is what stops the `else stale` swallow. That pin is real (`stale` not in reason). The original lie is the unrecognized `{none}` sentence, not the word `stale`.

Simulation:

1. Enum + freshness pass-through (schema-less → `"unreadable"`). Pytest in `test_blast_radius.py` green.
2. Blast-gate: `elif verdict == 'unreadable':` with the existing unrecognized f-string (or `found_s = "none"`). Cheaper than typing the new paragraph — the block is already in the file.
3. Unreadable fixture Write: contains `writ codegraph-init`, no ``Run `codegraph index` ``, no `stale`. Named test green.
4. Operator on a junk/chmod db still reads “unrecognized schema (found: {none})”.

Simpler design that removes the problem: assert `"cannot be read" in reason` and `"unrecognized" not in reason` (and keep the C-08 command-string + not-`stale` pins). The specified §3 sentence already satisfies that.

Check:

```
python3 -c 's="This repo'\''s codegraph index is at an unrecognized schema version (found: {none}; reader supports: {1, 5}). Run \`writ codegraph-init\` to rebuild the index, then retry the write."; print("writ" in s, "Run \`codegraph index\`" not in s, "stale" not in s)'
# True True True
rg -n 'unreadable|cannot be read' falkor-writ/tests/test_blast_gate_hook.py
# no matches
```

---

## Audits (what was verified, not restated)

1. **Fact:** WAL-no-shm / junk `DatabaseError` / chmod 000 connect `unable to open database file` on both URIs / `FRESH_CACHE_TTL = 300` at `blast_radius.py:69` / `cli.py:990-992` passthrough / four `sqlite3.connect(` under `bin/lib/` / doctor has no `copy_pair` — live or read this session. Exact `str(e) == "unable to open database file"` on WAL-no-shm execute. OQ-4 asserts 1–2 do not call `_connect` (C1). Unrecognized deny copy passes the new blast-gate pins (M1).
2. **Consistency:** §1.0 “plain `ro` leads” vs §7 pins that never observe `_connect`’s URI (C1). C-08 “three split messages” vs §7 pins that the unrecognized message satisfies (M1). OQ-5 exists — r3 M2 not re-filed. C-08 command-string vs noun: specified copy passes; current PRE-INDEX still fails the *positive* `writ codegraph-init` pin — not re-filed.
3. **Gaming:** transcripts in C1 (split + immutable-only + retry-on-busy) and M1 (clone unrecognized elif). Extra, not filed: `sqlite3.connect (` with a space evades the count grep; assert 4 on a real WAL fixture would still catch an unfolded C12; weaker than C1.
4. **Feasibility:** `_connect` retry string matches live WAL ping. DELETE exclusive + `immutable=1` reads committed rows (launder). WAL writer + `immutable=1` → `no such table`. Idle WAL *with* sidecars: both URIs read `{1,5}` (so immutable-only is not disproved by an idle-sidecar fixture). Header-poke `data[18:19]=2,2` on a DELETE db: raw `ro` execute raises `unable to open database file` and `immutable` reads `{1,5}` — a fake WAL header still needs the fallback for assert 3; not filed as a skip of the retry, only as proof asserts 1–2 are about bytes, not `_connect`.
5. **Contracts:** C1-a hop-drop holds. Scope ITEM-1-writ still names an `index` retry; grill C1-a supersedes — not re-filed. Grill “one surface” grew `_connect`; incomplete pin is C1. OQ-5 records the Cursor envelope — not re-filed. `apply_waivers` matches by id within ±2 lines (`artifact_claims.py:810`); PRE-UNREADABLE at line 1 is waivable without an allowlist, as claimed.
6. **Missing-by-construction:** author position “asserts 1–2 in front prove the fallback” hides that 1–2 never call `_connect` and “or its fixture” unbinds 3–4. Author position “not stale / not `Run codegraph index`” hides that those pins are true of the lie this bucket names.

Human-authority: Cursor deny remains OQ-5 (asked/deferred). OQ-4 A “owner not re-asked” treated as craft again: without *some* retry, `"unreadable"` means every fresh init; the defect is the test pin (C1), not the choice to retry. `install.sh --only` vs `--all` is inside OQ-5 half 2 — not filed separately.

No MINOR filed (dispatch asked CRITICAL/MAJOR only).
