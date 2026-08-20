# Red-team r7 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (band-2 design authored by **syn-3-kimi-k3**; reviewer is a different lineage) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own quirks. Cross-model can catch kimi-lineage blind spots; it cannot certify they are all caught. Closed r1–r6 IDs are not re-filed unless the band-2 amend reopened them. This round attacks the **band-2 amend’s new gates** only: two `sqlite3.connect` literals (first URI has no `immutable`); assert 5 `str(e)=="database is locked"` then `probe()=="unreadable"` (chmod forbidden); adversarial × honest matrix; C-04 Claude = source pytest only (no Claude deny ✅).

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk `_connect` / blast-gate / pytest HOOK path + live sqlite 3.51.0 this session).
SQLite URI: https://sqlite.org/uri.html §3.3 (fetched 2026-08-19) — `immutable=1` **and** `nolock=1` both skip file locking.
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

The band-2 pin set is the right *kind* of pin. Requiring two `sqlite3.connect(` sites whose *first* URI literal contains `mode=ro` and not `immutable`, with the retry sitting inside an `If` on `unable to open database file`, kills the r6 one-URI `mode=ro&immutable=1` opener (matrix variant a: 6a–d all F). Requiring the test’s own plain-`ro` execute to raise `str(e) == 'database is locked'` before `probe()=="unreadable"`, and naming chmod/junk/absent as forbidden substitutes, is the only behaviour that goes red when the first attempt skips locks. Running honest + a/b/c against real WAL and DELETE-EXCLUSIVE fixtures, and retracting Claude deny ✅ down to source-pytest + OQ-6, is the verification model r6 asked for. Together those were meant to make lock-laundering unsatisfiable. That is the strongest honest case. The structure pin only inspects string *constants* for the token `immutable`, assert 5 may live in a second function, and `timeout=0` applies only to the test’s own check — so a first URI of `mode=ro&nolock=1` (or a dead first connect, or `f"?mode=ro{extra}"`) still greens 6a–d, and chmod in that second function still greens 5b.

## Verdict

**revise** — 1 CRITICAL, 1 MAJOR. Do not spec OQ-4 A until assert 5 is bound the way asserts 1–3 already are (one `def`, same `db`/`repo`/`writer` variables) **and** assert 6b measures the runtime first URI (locking not skipped), not the absence of the substring `immutable` in JoinedStr constants.

---

## CRITICAL

### C1. The band-2 pin set is co-satisfiable with a lock-skipping `_connect`. 6a–d pass on `mode=ro&nolock=1`, on a dead first connect, and on `f"?mode=ro{extra}"` with `extra="&immutable=1"`. Assert 5 may be “a second named test function”; 5a is the test’s own connection (always T on the lock fixture); 5b on chmod is still `"unreadable"`. Live, those openers probe a `BEGIN EXCLUSIVE` DELETE db `"usable"`. C-04 fail-closed is gone.

Where: §7 assert 5 (`docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md:768-795`); assert 6b (`:819-822`); §1.0 (`:336-341`, `:343-347`); matrix (`:927-980`); bad-faith row assert 5 (`:915`); extra-instruction §4–§5 (band-2 required pins)
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): Pytest is green. A writer holding the index probes `"usable"`. The Write gate lets the edit through on a map SQLite refused to serve a locked reader. The operator is not told to wait. Grill fail-closed (“unreadable is never usable”) is false.

Evidence — design pins (band-2 amend):

> “In the **same function or a second named test function**”
> “Every reader connection in this test — the test's own plain-`ro` check — runs with **`timeout=0`**”
> “Forbidden substitutes for THIS assert's fixture: `chmod 000`, absent file, junk bytes”
> “extract the URI **literal of the first** call site — the string constants of its first argument … It contains `mode=ro` and does **not** contain `immutable`.”
> “the default lock timeout waits **≈5.1–5.3 s** … which is the exact incentive that pushed the r5 patch to reach for chmod instead”
> asserts 1–3: “must sit inside a single `def test_…(…)`, operating on the same `db` / `repo` variables” — assert 5 was not given that bind

Evidence — live this session, python sqlite 3.51.0, pins copied from `.village/runs/2026-08-19-bkt6-writ-probe/scratch/pin-set-harness.py` `literal_of` / `pin6_*` (JoinedStr constants only; FormattedValue skipped; connects sorted by lineno):

LOCKED DELETE + `BEGIN EXCLUSIVE` (timeout=0):
```
mode=ro                     OperationalError 'database is locked'
mode=ro&immutable=1         OK [(1,), (5,)]
mode=ro&nolock=1            OK [(1,), (5,)]     # same skip-locking class, SQLite URI §3.3
```

WAL no-sidecar (real `codegraph init`, header `b'\x02\x02'`):
```
mode=ro                     OperationalError 'unable to open database file'
mode=ro&immutable=1         OK [(1,), (5,)]
mode=ro&nolock=1            OperationalError 'unable to open database file'  # retry still needed
```

chmod 000: all three URIs → `'unable to open database file'`.

Three `_connect` shapes, all 6a–d **T**, warning docstring included:

| shape | 6a–d | WAL probe | LOCKED probe | chmod probe |
|---|---|---|---|---|
| honest (`?mode=ro` then gated immutable) | TTTT | usable | unreadable | unreadable |
| **nolock** first (`?mode=ro&nolock=1`) | TTTT | usable | **usable** | unreadable |
| **dead** first (`raise OperationalError(GATE)` then immutable) | TTTT | usable | **usable** | unreadable |
| **fmt** (`f"?mode=ro{extra}"` with `extra="&immutable=1"`) | TTTT (lit1=`file:?mode=ro`) | usable | **usable** | unreadable |

Assert 5 split (exactly the r6 gaming transcript, still allowed by “second named test function”):
```
5a (test’s own connect on lock): str(e)=='database is locked'  PASS  # fixture fact; independent of _connect
5b gamed onto chmod:             probe==unreadable              PASS  # all four shapes, including the three defects
5b honest on lock:               defect shapes probe==usable    FAIL  # the pin that would have caught them
```

§1.0 production `_connect` still has **no** `timeout=0`. The harness honest variant *does* (`SRC_HONEST` lines 26–31 of `pin-set-harness.py`). Matrix 5b was therefore cheap. Production 5b on a real EXCLUSIVE lock waits the measured **5.14s** — the incentive the design itself names — while 5a is already instant. Assert 7 already owns a chmod function. Putting 5b there is the cheap green.

SQLite (https://sqlite.org/uri.html §3.3, fetched 2026-08-19): `immutable=1` “skips all file locking and change detection”; `nolock=1` “disables all calls to the xLock, xUnlock, and xCheckReservedLock methods”. 6b bans only the token `immutable`.

Band-2 matrix ran variants a/b/c only. It did not run nolock / dead / fmt. Extra-instruction §5 gate (“cheapest implementation that still carries the defect and would pass”) was therefore not executed. Variants a/b/c fail 6b or 6a; the cheapest lock-skip that **passes 6** is nolock, and it greens the set once 5b is the second function.

Gaming transcript (lazy executor, all band-2 gates green):

```
def _connect(repo):
    """Never open with immutable=1 first. Use mode=ro, then retry…"""
    path = _index_path(repo)
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro&nolock=1", uri=True)
        con.execute("SELECT 1"); return con
    except sqlite3.OperationalError as e:
        if str(e) == "unable to open database file":
            con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
            con.execute("SELECT 1"); return con
        raise

def test_wal_fallback(tmp_path):          # ONE def, asserts 1-3 (unchanged bind)
    db = real_codegraph_init(...)         # header b'\x02\x02'; plain ro raises; probe=="usable"

def test_lock_message(tmp_path):          # assert 5 part 1 — "second named test function"
    db, writer = begin_exclusive_delete(...)
    with pytest.raises(sqlite3.OperationalError) as ei:
        sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0).execute("SELECT 1")
    assert str(ei.value) == "database is locked"

def test_probe_unreadable(tmp_path):      # assert 5 part 2 — chmod already required by assert 7
    db.chmod(0o000)
    assert probe(repo) == "unreadable"
```

Check:
```
python3 - <<'PY'
# 1) BEGIN EXCLUSIVE DELETE + file:…?mode=ro&nolock=1 must return schema_versions rows
# 2) pin6 on the nolock/dead/fmt sources: 6a–d True (use pin-set-harness literal_of)
# 3) probe(lock)=="usable" and probe(chmod) startswith unreadable
PY
```

---

## MAJOR

### M1. Assert 6b measures JoinedStr constants for the absence of `immutable`, not “plain `mode=ro` with locking.” That is a weaker predicate than the property §1.0 / pre-mortem 4 name. `nolock=1`, a dead first `connect`, and a FormattedValue-hidden `&immutable=1` all 6a–d T. 6 therefore does not independently kill lock-skip; only an honest 5b does — and C1 shows 5b is not bound.

Where: §7 assert 6b (`:819-822`); 6 extractor (“ast JoinedStr constants, or regex the quoted first argument”); §1.0 “Plain `ro` leads; `immutable=1` is never the first attempt” (`:343-347`); pre-mortem 4 (`:1144-1155`); matrix claim “discriminating load is carried by **5b and 6a–6d**” (`:979-980`)
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): A later plan can weaken or split 5b (r5 did this to 1–3) and 6 will still be green on a lock-skipping opener. The structure pin that was added so source cannot lie about the first attempt cannot see the first attempt.

Evidence — specified extractor (harness `literal_of`, matches the design: “FormattedValue skipped: only constant parts carry URI keys”):

```
nolock first-arg constants: 'file:?mode=ro&nolock=1'  → mode=ro yes, immutable no → 6b T
fmt    first-arg constants: 'file:?mode=ro'            → extra="&immutable=1" not collected → 6b T
dead   first-arg constants: 'file:?mode=ro'            → first Call is the dead one → 6b T
```

Evidence — SQLite same section the design cites for immutable (https://sqlite.org/uri.html §3.3, fetched 2026-08-19): `nolock=1` is the sibling lock-skip query parameter. 6b’s ban list is one token.

Evidence — extra-instruction §3: “a pin on `_connect` must measure `_connect` itself — its source literals (structure pins) or its runtime I/O”. 6b’s literals are not the runtime URI. 6d asks only that the *second* connect sit inside the error `If`; a `raise GATE` before the first connect, or a first connect that never raises (`nolock`), never exercises that gate.

On-disk today (`falkor-writ/bin/lib/codegraph_index.py:46-50`): one `mode=ro` connect, no ping, no retry — so these are the worker’s implementation choices, not current-code bugs. The band-2 gates are what would have to make lock-skip unsatisfiable. 6b does not.

Check: the same snippet as C1; print `literal_of(first_arg)` for `f"file:{db}?mode=ro{extra}"`.

---

## Not re-filed (band-2 gates that held this round)

C-04 Claude = source pytest only, no Claude deny ✅: `rg` this session → two hits, both the retraction itself (`:990` sweep prose; `:1040` “Claude deny = source pytest proven”). Option A box is **C-04 ⚠️ partial**. pytest HOOK remains clone `.claude/hooks/writ-blast-gate.sh` (`tests/test_blast_gate_hook.py:32-33`). Live Claude remains `${CLAUDE_PLUGIN_ROOT}` (`hooks/hooks.json:245,258`). OQ-6 untouched. r6 M2 closed.

Asserts 1–3 one-`def` on one path object: still stops the DELETE-fixture split for WAL usable. Does not constrain `_connect` (see C1). Not a separate ID.

Matrix variants a/b/c vs *those three* pins: recomputed logic matches `pin-set-band2-output.txt` (honest all T except retracted `src.index`; a fails 5b+6*; b fails 5b+6b+6c; c fails 5b+6b). That scoreboard is true and too small.

`test_pre_write_dispatch.py:325-333` is still membership (`assert "_can_write_check" in src`). Band-2 no longer claims index-order from it.

## Mode

Cross-model (syn-3-kimi-k3 band-2 design, cursor-grok-4.6-high reviewer). Certifies craft of the band-2 gates against live sqlite 3.51.0 + on-disk source + the harness extractor. Does not certify this reviewer has no matching blind spot.

## Six audits (band-2 gates only)

1. Fact: sqlite 3.51.0; DELETE lock → `database is locked` on plain `ro`, rows on `immutable=1` **and** on `nolock=1`; WAL no-sidecar header `b'\x02\x02'`; chmod 000 → `unable to open database file` on all three URIs; default lock timeout 5.14s in the cited harness output. All recomputed this session.
2. Consistency: asserts 1–3 require one `def`; assert 5 allows a second function (C1). 6b “no `immutable`” vs §1.0 “plain `ro` leads / locking not skipped” (M1). C-04 ⚠️ vs leftover ✅: held.
3. Gaming: transcript under C1.
4. Feasibility: `BEGIN EXCLUSIVE` on WAL (this session) does **not** block `mode=ro` — DELETE remains load-bearing, as specified. `nolock=1` on WAL-no-sidecar still raises `unable to open database file`, so asserts 1–3 stay green on the nolock opener; the defect only shows on the lock fixture.
5. Contract: grill fail-closed / C-04 “never treated as usable” broken by C1. falkor-writ cache rule honored by OQ-6; Claude deny ✅ not re-introduced.
6. Missing: matrix a/b/c never included the cheapest 6-passing lock-skip; `timeout=0` was applied to the harness `_connect` and to 5a, not to the specified production `_connect` that 5b calls.

Fix nothing.
