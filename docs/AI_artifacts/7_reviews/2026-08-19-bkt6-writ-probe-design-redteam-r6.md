# Red-team r6 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own quirks. Cross-model can catch opus-lineage blind spots; it cannot certify they are all caught. Closed r1–r5 IDs are not re-filed. This round attacks the **r5 amend’s new gates** only: one `def` for asserts 1–3; DELETE `BEGIN EXCLUSIVE` → `probe()=="unreadable"`; `inspect.getsource(_connect)` URI order; unreadable deny equality + `cannot be read` / no `unrecognized`; C-04 Claude = source pytest only (OQ-6).

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk `_connect` / `probe` / blast-gate + live sqlite 3.51.0 this session).
SQLite `immutable=1`: https://sqlite.org/uri.html §3.3 (fetched 2026-08-19) — “skips all file locking and change detection”.
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

The r5 amend is the right *kind* of pin. Asserts 1–3 in one `def` on one path object stops the DELETE-fixture `usable` split; a real `BEGIN EXCLUSIVE` on a DELETE db is the only behaviour that goes red when `immutable=1` leads or the retry is any `OperationalError`; `inspect.getsource` is the house style already used at `tests/test_pre_write_dispatch.py:325-333`; equality plus `cannot be read` / no `unrecognized` is the only copy pin the live `{none}` unrecognized sentence fails; and C-04 scoped to “source pytest + OQ-6” matches falkor-writ’s own rule that Claude runs the plugin cache, not the clone. Together those were meant to make always-immutable and unrecognized-as-unreadable unsatisfiable. That is the strongest honest case. The source-order pin is satisfied by the *retry URI itself* (`mode=ro&immutable=1`), and `probe()=="unreadable"` is also the output of the chmod-000 test already named in the same §7 block — so the C-04 behaviour pin still greens with a single always-immutable opener.

## Verdict

**revise** — 1 CRITICAL, 2 MAJOR. Do not spec OQ-4 A until assert 6 requires two `sqlite3.connect` calls whose *first* URI has no `immutable`, and assert 5 requires the discriminator `database is locked` (not merely `probe=="unreadable"`). Do not mark Claude deny ✅ while OQ-6 is the live path.

---

## CRITICAL

### C1. The r5 pin set is co-satisfiable with a single `file:{path}?mode=ro&immutable=1` opener. Asserts 1–3 (one `def`) pass on WAL. Assert 6 (`src.index('mode=ro') < src.index('immutable=1')` + predicate substring + “no bare except”) passes on that same URI. Assert 5 (`probe()=="unreadable"`) passes if implemented as the chmod-000 case §7 already lists. Live, that opener launders `BEGIN EXCLUSIVE` to `"usable"` — C-04 fail-closed is gone.

Where: §1.0 retry URI (`docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md:331-341`); §7 asserts 1–3 (`:712-749`); assert 5 (`:764-780`); assert 6 (`:781-789`); bad-faith table rows assert 5 / 6 (`:854-855`); C-04 (`:123-137`); Risk row immutable (`:975`)
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): Pytest is green. A daemon holding the index (`BEGIN EXCLUSIVE`) probes `"usable"`. The Write gate lets the edit through on a map SQLite refused to serve a locked reader. The operator is not told to wait. Grill fail-closed (“unreadable is never usable”) is false.

Evidence — design pins (r5 amend):

> “Asserts 1, 2 and 3 must sit inside a single `def test_…(…)`, operating on the same `db` / `repo` variables”
> “hold `BEGIN EXCLUSIVE` open on a second connection, and assert `codegraph_index.probe(repo) == "unreadable"`”
> “`src = inspect.getsource(codegraph_index._connect)`; assert plain `mode=ro` appears **before** `immutable=1` (`src.index('mode=ro') < src.index('immutable=1')`), and assert the retry predicate is the exact string `unable to open database file` and nothing broader (no bare `except sqlite3.OperationalError:` that retries unconditionally)”
> “retry **once** with `file:{path}?mode=ro&immutable=1`”
> bad-faith: assert 6 alone “**yes on its own** — source text can lie about behaviour, which is why assert 5 is mandatory”

Evidence — live this session, python sqlite 3.51.0:

DELETE + `BEGIN EXCLUSIVE` (timeout=0.2):
```
plain ro:                  EXECUTE OperationalError: database is locked
file:…?mode=ro&immutable=1: OK [(1,)]
today's probe while locked: ('unrecognized', frozenset(), frozenset({1, 5}))
```

Simulated always-immutable `_connect` (`?mode=ro&immutable=1` only) on that same locked DELETE db: `probe → "usable"`.

WAL, no sidecars (header `b'\x02\x02'`), asserts 1–3 against a combined-URI opener:
```
plain ro:                   EXEC OperationalError: unable to open database file   # assert 2
mode=ro&immutable=1:        OK [(1,), (5,)]                                      # assert 3 usable
listing after reads:        ['codegraph.db']                                     # no sidecar
```

`inspect.getsource` on a one-connect combined-URI function (predicate in docstring, **zero** `except`):
```
mode=ro@218 imm@226 order_ok=True
pred=True
except OperationalError=False
sqlite3.connect count=1
```
The allowed *retry* URI is the string that satisfies the order pin. A function with no `except` vacuously satisfies “no bare `except sqlite3.OperationalError:`”.

chmod 000 after close (the other §7 unreadable fixture, `:641-643` / `:791-792`):
```
plain ro / combined / imm: CONNECT OperationalError: unable to open database file
```
So `probe()=="unreadable"` is green on chmod for *both* the honest opener and the always-immutable opener. Assert 5 as specified does not require the message `database is locked`. Default `sqlite3.connect` timeout on a real EXCLUSIVE lock is **5.25s** (timed this session) — `_connect` as specified does not set `timeout=0` — so the cheapest green assert 5 is the chmod-000 test already in the same list.

SQLite (https://sqlite.org/uri.html §3.3, fetched 2026-08-19): `immutable=1` “skips all file locking and change detection”. Combined `mode=ro&immutable=1` is still immutable; query-parameter order in one URI is not two attempts.

On-disk today (`falkor-writ/bin/lib/codegraph_index.py:46-50,63-72`): one `mode=ro` connect, no ping, no retry — so this is the worker’s implementation choice, not a current-code bug. The r5 gates are what would have to make always-immutable unsatisfiable. They do not.

Gaming transcript (lazy executor, all r5 gates green):

```
def _connect(repo):
    """Retry on unable to open database file."""
    path = _index_path(repo)
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)  # assert 6 order+pred
    con.execute("SELECT 1"); return con

def test_wal_fallback(tmp_path):          # ONE def, asserts 1-3
    db = real_codegraph_init(...)         # header b'\x02\x02'; plain ro raises; probe=="usable"

def test_locked_db_unreadable(tmp_path):  # "second named test function"
    db = make_index(...)                  # or chmod 000
    db.chmod(0o000)
    assert probe(repo) == "unreadable"    # assert 5 green; BEGIN EXCLUSIVE never used
```

Check:
```
python3 - <<'PY'
import inspect, sqlite3, tempfile, os
from pathlib import Path
# 1) BEGIN EXCLUSIVE + ?mode=ro&immutable=1 must return rows (defect)
# 2) inspect.getsource of a combined-URI _connect: index('mode=ro') < index('immutable=1')
# 3) chmod 000 + combined URI must still fail open (assert 5 substitute)
PY
```

---

## MAJOR

### M1. Assert 6 is first-substring order over the whole function (docstring+comments+body), not URI-attempt order. Honest safety docs fail it; a leading `# mode=ro` comment (or the retry URI alone) passes it. Pre-mortem 4 described exactly this lie.

Where: §7 assert 6 (`:781-789`); Pre-mortem 4 (`:1005-1009`); §1.0 “Plain `ro` leads; `immutable=1` is never the first attempt” (`:343-347`)
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The pin that was added so comments cannot lie about URI order *rewards* a comment that mentions `mode=ro` first and *punishes* the warning the design itself wants in the docstring. A worker documenting “never open with immutable=1 first” gets a red test and will either drop the warning or stick `mode=ro` in a dummy comment — the shape pre-mortem 4 said was the failure.

Evidence — live `inspect.getsource` this session:

Honest body (plain `ro` first, retry with immutable, predicate checked) with docstring starting “Never open with immutable=1 first. Use mode=ro, then retry…”:
```
honest_with_warning_doc: mode=ro@81 imm@58 order_ok=False
```

Same body, docstring starting “Plain mode=ro first; immutable=1 only on…”:
```
honest_with_safe_doc: order_ok=True
```

Immutable-only body with comment `# Try mode=ro first (documented)`:
```
comment_lie_immutable_first: mode=ro@49 imm@170 order_ok=True
```
(`pred=False` on that one only because the error string was omitted; add it to the comment and every assert-6 clause listed in §7 is green.)

Two-connect helper that *leads* with `?mode=ro&immutable=1` and falls back to plain `ro`, with a `# mode=ro appears in a comment first` line:
```
two_connects_but_imm_first: order_ok=True  pred=True  sqlite3.connect count=2
```

Cite: `tests/test_pre_write_dispatch.py:325-333` is `assert "_can_write_check" in src` — membership, not index-order. The r5 pin copied the import style and then used a metric the cited test does not use.

Check: `python3 -c "import inspect, codegraph_index; src=inspect.getsource(codegraph_index._connect); print(src.index('mode=ro'), src.index('immutable=1') if 'immutable=1' in src else None)"` after impl; also eval the three function shapes above.

---

### M2. Option A marks Claude deny ✅. C-04’s own harness split and OQ-6 say the live session does not run that file. The checklist is a downstream claim the design forbids.

Where: Option A constraints check (`:902-904`); C-04 Claude row (`:124-137`); OQ-6 (`:1088-1113`); grill lock 4 / R15 (same strings, fail-closed); `falkor-writ/hooks/hooks.json:245,258`; `falkor-writ/tests/test_blast_gate_hook.py:32-33`
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): Spec/plan copy “Claude deny ✅” and skip cache refresh. After merge the owner’s live Claude session still runs the pre-fix three-branch hook (`unreadable` → `else stale`). Edits stay blocked (wrong name), which is how pre-mortem 1 / 5 fail in production without a red test. OQ-6 correctly says this is operator work; the ✅ takes that decision back.

Evidence:

C-04 body (r5 retract):
> “the SOURCE script emits a deny Claude honors; the LIVE file is the plugin cache”
> “A live Claude session does **not** run that file”
> “C-04 on Claude claims exactly this much: **the source emits the deny, proven by test.** Landing it in a running session is an operator step (refresh the cache, restart Claude) — **OQ-6**, deliberately **not** a Done-cell”
> “no downstream doc may claim the live Claude session denies until the cache is refreshed”

Option A constraints check, same artifact:
> “**C-04 ⚠️ partial** — the consumer half ✅ … and the **Claude deny ✅**; the **Cursor deny is unverified**”

On-disk:
- pytest HOOK = clone `.claude/hooks/writ-blast-gate.sh` (`tests/test_blast_gate_hook.py:32-33`)
- live Claude = `bash ${CLAUDE_PLUGIN_ROOT}/.claude/hooks/writ-blast-gate.sh` (`hooks/hooks.json:245,258`)
- falkor-writ `CLAUDE.md` “What AI Gets Wrong”: “`git pull` alone updates NOTHING that runs” / plugin cache copy

The r5 gate “C-04 Claude = source pytest only” is internally consistent *only if* no checklist row says Claude deny ✅. That row is the overclaim.

Check: `rg -n "Claude deny" docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`; `sed -n '32,33p;204,211p' falkor-writ/tests/test_blast_gate_hook.py falkor-writ/.claude/hooks/writ-blast-gate.sh`; `rg -n "CLAUDE_PLUGIN_ROOT" falkor-writ/hooks/hooks.json`

---

## Not re-filed (r5 gates that held this round)

Unreadable deny **equality** plus `cannot be read` / no `unrecognized`: the live unrecognized `{none}` sentence still has `unrecognized` and lacks `cannot be read` (recomputed this session). Combined with `==` on the §3 sentence, reusing that branch is red. No remaining CRITICAL/MAJOR hole on that gate.

One-`def` for asserts 1–3: stops the r5 split of 3 onto a DELETE fixture. It does not constrain `_connect` (see C1). Not a separate ID.

## Mode

Cross-model (claude-opus design, cursor-grok-4.6-high reviewer). Certifies craft of the r5 gates against live sqlite + on-disk source. Does not certify this reviewer has no matching blind spot.

## Six audits (r5 gates only)

1. Fact: sqlite 3.51.0; DELETE lock → `database is locked` on plain `ro`, rows on `mode=ro&immutable=1`; WAL no-sidecar header `b'\x02\x02'`; chmod 000 → `unable to open database file` on both URIs; default lock timeout 5.25s. All recomputed this session.
2. Consistency: assert 6 vs pre-mortem 4 (M1); Claude deny ✅ vs OQ-6 (M2); C-04 vs always-immutable (C1).
3. Gaming: transcript under C1.
4. Feasibility: `BEGIN EXCLUSIVE` on WAL (sidecars present) does **not** block `mode=ro` readers (this session) — DELETE is load-bearing, as specified. Production `_connect` has no `timeout=0`, so a literal EXCLUSIVE test blocks ~5s.
5. Contract: grill fail-closed / C-04 broken by C1; falkor-writ cache rule honored by OQ-6 and then contradicted by the ✅ (M2).
6. Missing: assert 6 never requires two `sqlite3.connect` calls or “first URI has no `immutable`”; assert 5 never requires the `database is locked` discriminator that assert 2 used for WAL.

Fix nothing.
