# Red-team r8 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design continuation authored by **syn-2-kimi-k3**; reviewer is a different lineage) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own quirks. Cross-model can catch kimi-lineage blind spots; it cannot certify they are all caught. Closed r1–r7 IDs are not re-filed unless the r8 text reopened them. This round attacks the **r8 amend’s new gates**: runtime 6b (first URI has neither `immutable` nor `nolock`; two recorded calls; `timeout=0`); asserts 5a/5b bound in the same `def` as 1–4; production `_connect` `timeout=0`.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk `_connect` / blast-gate / pytest HOOK path) plus live sqlite **3.51.0** and a real `codegraph init` WAL fixture this session.
SQLite URI: https://sqlite.org/uri.html §3.3 (fetched 2026-08-19) — `immutable=1`, `nolock=1`, **and `vfs=NAME`**.
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

The r8 pin set is the right *kind* of pin for the hole r7 named. Putting 5a and 5b in the same `def` as asserts 1–4, with the EXCLUSIVE writer held open, kills the “second named test function + chmod-000” split. Recording the *evaluated* first URI and banning both `immutable` and `nolock` kills the three r7 cheats that JoinedStr constants could not see (`nolock` first, `f"?mode=ro{extra}"`, constants-clean `mode=ro&nolock=1`). Pinning `timeout=0` on every production connect removes the 5-second wait that made chmod look cheaper than a lock. Together those were meant to make “first attempt skips locks → probe usable on a held writer” unsatisfiable. That is the strongest honest case. 6b then calls an exact URI equality and a two-token ban “equivalent,” 5b still asserts only `probe()=="unreadable"` (5a is a different connection), and SQLite URI §3.3 still has a third lock-skip (`vfs=unix-none`) that the token ban never names.

## Verdict

**revise** — 1 CRITICAL, 2 MAJOR. Do not spec OQ-4 A until 6b’s first-URI predicate is one thing (plain `file:{db}?mode=ro`, no extra query keys) **and** 5b asserts that `_connect`’s own first attempt raised `database is locked` (not merely that some path object later probes `unreadable`).

---

## CRITICAL

### C1. 6b’s two predicates are not equivalent. The laxer one — which the prose calls “equivalent” and which encodes the “both §3.3 lock-skips” rationale — greens `vfs=unix-none` on the WAL recorder. That opener probes a `BEGIN EXCLUSIVE` DELETE db `"usable"`. 5b still does not pin that `_connect` saw the lock. C-04 fail-closed is gone if the worker implements the “equivalent” clause.

Where: §7 assert 6b (`docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md:837-850`); §1.0 (`:347-353`); matrix gate verdict (`:1026-1038`); assert 5b (`:800-807`)
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): Pytest is green. A writer holding the index probes `"usable"`. The Write gate lets the edit through on a map SQLite refused to serve a locked reader. The operator is not told to wait. Grill fail-closed (“unreadable is never usable”) is false.

Evidence — 6b states two predicates and calls them the same:

> `recorded[0].uri` — the **evaluated** string the recorder sees — equals `f"file:{db}?mode=ro"`; **equivalently** it contains `mode=ro` and contains **neither `immutable` nor `nolock`**. **Both** SQLite URI §3.3 lock-skips are banned

Those are not equivalent. Exact equality rejects any extra query key. The token ban accepts any extra key that is not those two words.

SQLite URI §3.3 (https://sqlite.org/uri.html, fetched 2026-08-19) lists a third recognized parameter in the same section the design cites for the two-token ban:

> The vfs query parameter causes the database connection to be opened using the VFS called NAME.

Live this session, python sqlite 3.51.0, real `codegraph init` WAL-no-sidecar (`header[18:20] == b'\x02\x02'`, listing `.gitignore` + `codegraph.db` only) and a DELETE db held with `BEGIN EXCLUSIVE`, `timeout=0`:

```
WAL  mode=ro                     OperationalError 'unable to open database file'
WAL  mode=ro&immutable=1         OK
WAL  mode=ro&nolock=1            OperationalError 'unable to open database file'
WAL  mode=ro&vfs=unix-none       OperationalError 'unable to open database file'   # retry still needed
LOCKED mode=ro                   OperationalError 'database is locked'
LOCKED mode=ro&nolock=1          OK [(1,), (5,)]
LOCKED mode=ro&immutable=1       OK [(1,), (5,)]
LOCKED mode=ro&vfs=unix-none     OK [(1,), (5,)]     # third skip-locking class
```

unix-none-first `_connect` (plain `mode=ro&vfs=unix-none`, then the specified exact-string retry with `immutable=1`, `timeout=0` on both) against 6b’s **operational** (“equivalent”) clauses, WAL fixture:

```
recorded calls: 2
recorded[0].uri contains mode=ro, contains neither immutable nor nolock    # 6b substring T
recorded[0].uri == f"file:{db}?mode=ro"                                    # 6b equality F  (has &vfs=unix-none)
recorded[1].uri contains immutable=1                                       # 6c T
kwargs timeout == 0 on both                                                # 6b T
source sqlite3.connect( count == 2                                         # 6a T
retry sits in If str(e) == 'unable to open database file'                  # 6d T
WAL probe == "usable", no -wal/-shm                                        # asserts 1–3 T
LOCKED probe == "usable"                                                   # 5b F if honest; T if poisoned (below)
```

The matrix (`:1026-1038`) ran a/b/c/n/d/f. It did not run `vfs=`. The header of 6b still says “the runtime first URI carries no lock-skip.” The token ban does not implement that sentence. Extra-instruction “cheapest implementation that still carries the defect and would pass” was therefore not executed for §3.3’s remaining lock-skip.

5b is still not a pin on `_connect`. Specified 5a is the **test’s own** `sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0)` raising `database is locked`. Specified 5b is `codegraph_index.probe(repo) == "unreadable"` on “that same locked fixture, with `writer` still open.” 5a does not observe `_connect`. 5b does not assert the error `_connect` saw.

Gaming transcript (lazy executor, all r8 gates green under the “equivalent” reading of 6b):

```
def _connect(repo):
    """Never open with immutable=1 or nolock=1 first."""
    path = _index_path(repo)
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro&vfs=unix-none", uri=True, timeout=0)
        con.execute("SELECT 1"); return con
    except sqlite3.OperationalError as e:
        if str(e) == "unable to open database file":
            con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True, timeout=0)
            con.execute("SELECT 1"); return con
        raise

def test_wal_fallback_and_lock(tmp_path):   # ONE def, asserts 1–4 then 5a/5b
    db = real_codegraph_init(...)           # header b'\x02\x02'; plain ro raises; probe=="usable"
    # 6b recorder on this db: 2 calls, first URI has mode=ro, no immutable, no nolock
    lock_db, writer = begin_exclusive_delete(...)
    with pytest.raises(sqlite3.OperationalError) as ei:
        sqlite3.connect(f"file:{lock_db}?mode=ro", uri=True, timeout=0).execute("SELECT 1")
    assert str(ei.value) == "database is locked"          # 5a: fixture fact; independent of _connect
    os.chmod(lock_db, 0o000)                              # not a rebuild; writer still open
    assert probe(lock_repo) == "unreadable"               # 5b: chmod fails EVERY URI (measured)
```

Live chmod-after-5a (same path, writer held, no rebuild) this session:

```
5a pre-chmod  plain ro     -> 'database is locked'
5b post-chmod plain ro     -> 'unable to open database file'
5b post-chmod immutable=1  -> 'unable to open database file'
5b post-chmod vfs=unix-none-> 'unable to open database file'
```

The design forbids chmod as a *starting* fixture for assert 5 (`:792-798`). It does not forbid mutating that fixture after 5a. The only between-step ban is “no intervening rebuild” (`:728-729`). chmod is not a rebuild. Assert 7 already owns chmod as an unreadable gate in the same numbered list, which is the invitation.

If 6b is implemented as **equality** with `f"file:{db}?mode=ro"`, unix-none-first goes red on 6b and this finding shrinks to “the word equivalently is a lie.” The design as written authorizes the laxer pin. A worker will ship the laxer pin. That is the gate.

Check:
```
python3 - <<'PY'
# 1) BEGIN EXCLUSIVE DELETE + file:…?mode=ro&vfs=unix-none must return schema_versions rows
# 2) WAL-no-sidecar (real codegraph init): unix-none-first records 2 connects;
#    recorded[0] has mode=ro, has neither immutable nor nolock, has vfs=unix-none
# 3) probe(lock)=="usable" for that _connect; probe(chmod(lock))=="unreadable"
PY
```

---

## MAJOR

### M1. The “one opener” pair (grep `sqlite3.connect(` count == 1 under `bin/lib/` + assert 3’s no-sidecar check) does not catch an unfolded C12/C16. `from sqlite3 import connect` makes the grep silent. Assert 3 runs *before* assert 4, so a RW `connect(str(path))` in the folded readers creates `-wal`/`-shm` after the listing has already passed.

Where: §7 one-opener (`:891-910`); assert 3 then 4 order (`:753-766`); r3 gaming note the pair claimed to close (`:905-909`); C-12 (`:207-208`)
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The shared opener can stay unfixed in C12/C16. On a healthy fresh index the audit checks either go quiet (plain `mode=ro`, the original OQ-4 silent-empty) or they work by opening the file read-write and leaving sidecar files next to the index Writ promised never to write. CI stays green. The next WAL-related sqlite quirk has two copies to miss.

Evidence — specified pair:

> The guard is on `sqlite3.connect(`, **not** on the string `mode=ro`, precisely because the r3 reviewer showed a `mode=ro` grep is satisfied by rewriting C12/C16 to `sqlite3.connect(str(path))` — which passes the grep, opens read-write, and creates `-wal`/`-shm` on a real WAL index. Pairing the `sqlite3.connect(` count with assert 3's no-sidecar check closes both doors.

Both doors stay open.

Door 1, grep. Live this session:

```
from sqlite3 import connect
con = connect(f"file:{path}?mode=ro&immutable=1", uri=True)
# "sqlite3.connect(" in that source == False
```

On-disk today the four `bin/lib/` hits are still the unfolder `sqlite3.connect(` forms (`codegraph_index.py:48`, `blast_radius.py:135`, `artifact_claims.py:2166`, `:2488`). After a fold of blast_radius plus an alias rewrite of C12/C16, the grep the plan will copy reports exactly one file.

Door 2, sidecar timing. Specified order in the one `def`: assert 1, 2, **3 (listing has no `-wal`/`-shm`)**, then **4 (`_c16_resolve_node` / `_c12_container` not None, `report_for_file` symbols not `[]`)**. Live on a real `codegraph init` WAL-no-sidecar db this session:

```
assert3 listing = ['.gitignore', 'codegraph.db']     # PASS
connect(str(db))  # RW, the r3 rewrite, via `from sqlite3 import connect`
SELECT name FROM nodes WHERE name='unique_band1_symbol' -> [('unique_band1_symbol',)]
after RW listing = ['.gitignore', 'codegraph.db', 'codegraph.db-shm', 'codegraph.db-wal']
```

Assert 3 has already passed. No later listing check exists. Private `mode=ro&immutable=1` via the same alias also returns the symbol and creates **no** sidecars — so even a post-4 listing would still be green while the opener remains copied, not folded. `_c12_container` / `_c16_resolve_node` return `None` on sqlite errors (`artifact_claims.py:2171-2183`, `:2493-2507`), so `is not None` is a real pin on “this call got rows” and is satisfied by either private immutable or RW. It does not pin *which* opener produced those rows.

Simulation (lazy executor):

```
# blast_radius._connect -> codegraph_index._connect   # honest fold; report_for_file rows on WAL
# artifact_claims._c16_resolve_node / _c12_container:
from sqlite3 import connect
con = connect(f"file:{Path(repo)/'.codegraph'/'codegraph.db'}?mode=ro&immutable=1", uri=True)
# grep sqlite3.connect( under bin/lib/ == 1 file (codegraph_index.py only)
# assert 4 not-None: PASS on the WAL fixture
# assert 3 already passed; immutable creates no sidecars anyway
```

Check:
```
python3 - <<'PY'
# real codegraph init WAL db; assert listing; then
# `from sqlite3 import connect; connect(str(db))`; listing now has -wal/-shm
# confirm "sqlite3.connect(" not in the aliased source
PY
```

### M2. OQ-5.2 closes a live-machine hook overwrite as a merge Done-cell. OQ-6 correctly refuses the same class of operating burden for Claude. The owner did not close this. Human-authority domain 3 (and 11) was decided by a red-team round, not recorded as an owner answer.

Where: OQ-5.2 (`:1276-1292`); OQ-6 (`:1294-1319`); grill “No settings/hooks.json edit”; C-04 Cursor row (`:140-146`)
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): Implementation of this bucket is specified to overwrite the hook file the owner’s running Cursor actually executes (`~/.cursor/hooks/writ-blast-gate.sh`). That is a live, machine-wide change. The same design refuses to require the Claude cache refresh because it is operating burden on the live machine. After merge, Cursor may carry the new deny sentence while Claude (the harness C-04 actually claims) still says “stale” until the owner happens to refresh — or the impl step mutates home-directory Cursor state the owner did not agree to treat as in-scope.

Evidence — OQ-6 (OPEN, correctly identified as operating burden, explicitly not a Done-cell):

> Running a cache refresh plus a Claude restart is operating burden on the owner's live machine, and no grill lock requires this bucket to carry it — the grill froze one contract surface (`probe()` + four consumers) and no wiring edits. Making `bin/writ-refresh-plugin-cache.sh` a required step would put a machine-wide, session-restarting action inside a bucket whose scope is a Python enum and a deny string.

Evidence — OQ-5.2 (CLOSED by “RT-r4 C1”, owner not named):

```
install -m 0755 <falkor-writ>/.claude/hooks/writ-blast-gate.sh ~/.cursor/hooks/writ-blast-gate.sh
diff -q …   # must be silent
```

> The plan's Done cell for the blast-gate step is the silent `diff -q`

That command overwrites `$HOME/.cursor/hooks/writ-blast-gate.sh`. Wiring verified this session at `~/.cursor/hooks.json:84-86` (`command` is that file, `matcher` Write, `failClosed` true). Grill freeze: “No settings/hooks.json edit.” The body copy does not edit `hooks.json`. It does edit the live hook body the owner’s Cursor already runs. Human-authority skill domain 3 (anything the user must run, maintain, or that mutates what they run) and domain 11 (destructive overwrite of a live file). Protocol: an artifact may ask or record the human’s answer; a subagent/review round cannot close it. OQ-6 follows the protocol. OQ-5.2 does not.

The two files are the same *class* of live-harness mutation. Treating Cursor as a required Done-cell and Claude as an optional operator follow-up is a silent product-identity / operating-burden split (R15 same-strings vs which harness is allowed to stay stale).

Check: read OQ-5.2 vs OQ-6 in the artifact; `sed -n '83,87p' ~/.cursor/hooks.json`; confirm no owner compact-reply line closes “impl may overwrite ~/.cursor/hooks/”.

---

## Simulation transcripts (audits 3 and 4)

### Audit 3 — gaming, highest-stakes claims

**Claim A — “runtime first URI carries no lock-skip” (C-04).** Bad-faith: first URI `mode=ro&vfs=unix-none`. 6b substring form: pass. WAL: two recorded calls, retry still needed. Locked DELETE: first attempt returns `[(1,),(5,)]`, probe `"usable"`. Honest 5b would go red; chmod-after-5a (writer held, no rebuild) makes 5b green because every URI then raises `unable to open database file`. Passes as easily as good-faith *under the “equivalently” reading of 6b*. Transcript in C1.

**Claim B — “exactly one production opener.”** Bad-faith: fold `blast_radius._connect`; rewrite C12/C16 to `from sqlite3 import connect` + private `immutable=1` (or RW `connect(str(path))`). Grep `sqlite3.connect(` → one file. Assert 4 not-None → pass. Assert 3 already passed before any reader that would create sidecars. Transcript in M1.

**Claim C — “Cursor and Claude get the same deny strings.”** Bad-faith: implement the pytest-covered source only; skip `install -m 0755`. Design already names this (Done-cell is `diff -q` because pytest never reads the Cursor file). Not re-filed. The new hole is making that overwrite in-scope without an owner answer (M2).

### Audit 4 — assumption feasibility

| Assumed | Verified this session |
|---|---|
| sqlite 3.51.0; WAL-no-sidecar after real `codegraph init` is `header[18:20]==b'\x02\x02'`; plain `ro` execute → `unable to open database file`; `immutable=1` reads it; no sidecars created | YES (`codegraph` `~/.codegraph/versions/v1.0.1/bin/codegraph`, init rc=0, Indexed 1 files) |
| DELETE + `BEGIN EXCLUSIVE` + `timeout=0` → `database is locked`; `immutable=1` and `nolock=1` return rows | YES |
| `vfs=unix-none` is a usable VFS on this Python sqlite and skips the lock | YES (locked → rows; WAL-no-sidecar → still `unable to open database file`) |
| `unix-nolock` VFS exists | NO — `no such vfs: unix-nolock` |
| `IMMUTABLE=1` (wrong case) skips locks | NO — still `database is locked` |
| `im%6dutable=1` percent-encoding is decoded as immutable | YES on both WAL and LOCKED (WAL: 1 recorded call, so 6b’s two-call clause catches this as a *first* URI; not a 6b-passing cheat) |
| chmod 000 fails plain / immutable / unix-none identically | YES — all `unable to open database file` |
| RW `connect(str(db))` on WAL-no-sidecar creates `-wal`/`-shm` | YES |
| `from sqlite3 import connect` is invisible to `sqlite3.connect(` | YES |
| Line cites: `codegraph_index.py:63-79` collapse; `blast_radius.py:285-289` narrow + `:69` TTL 300; `writ-codegraph-init.sh:172-175` exit 0; `artifact_claims.py:979-980` except-missing; `writ-blast-gate.sh:169-202` three-branch deny; pytest HOOK `:32-33`; `hooks/hooks.json:245,258`; `~/.cursor/hooks.json:84-86` | YES (read this session). `codegraph.ts` “CodeGraph not initialized” is `:750` not claimed `:749-751` (off-by-one, not load-bearing). `unlinkUnreadableIndex` call is `:631`; “Index database is locked” is `:615`. `directory.ts` empty/usable return is `:134`. |
| `_c12_container` / `_c16_resolve_node` return `None` on error, so `is not None` is not vacuous | YES (`artifact_claims.py:2172,2183,2494,2507`) |

Assumed-but-absent relative to 6b’s header: a pin that the first *attempt takes locks*. The two named tokens are not that pin. `vfs=` is in the same SQLite section.

---

## Human-authority

Silent / review-closed values found: **OQ-5.2** (M2) — live `~/.cursor/hooks/` overwrite as Done-cell; owner not recorded. `timeout=0` is a fail-closed implementation of the grill’s busy→unreadable fold, not a new SLO; not filed. OQ-4 A (WAL retry) is craft to keep the frozen four-name enum honest on a healthy init; recorded as ORCH away-craft, not re-filed as HA.

---

## Contract compliance (audit 5, no extra CRIT/MAJOR)

- Grill C1-a (no post-init `codegraph index`; unreadable names `writ codegraph-init`) is followed. Scope ITEM-1-writ still says the wrapper runs `codegraph index`; the grill owner-amendment supersedes it for this bucket. Not re-filed.
- C-11 OUT list (auto-index, `KNOWN_SCHEMA_VERSIONS`, piggyback clone, MCP, plugin bus, `.codegraph/ready`) is not reopened.
- falkor-writ house rule “never writes to the index” is the rule M1’s RW unfold breaks.

## Missing-by-construction (audit 6)

The author’s position is “we named both §3.3 lock-skips, so 6b measures no lock-skip.” That hides `vfs=`. The position “5a+5b in one def, writer held, chmod forbidden as fixture” hides that 5a never calls `_connect` and that chmod-after-5a is not a rebuild. The position “OQ-6 is operating burden so it stays open” hides that OQ-5.2 is the same burden on the other harness.

---

## Mode

**Cross-model.** Certifies craft vs the r8 gates and vs on-disk falkor-writ + live sqlite 3.51.0 this session. Cannot certify that a same-lineage reviewer would not also miss `vfs=` once `nolock` was banned by name.

**proceed / revise / rethink:** **revise**
