# Red-team r5 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own quirks. Cross-model can catch opus-lineage blind spots; it cannot certify they are all caught. Closed r4-4d023a8d C1/M1 (`install.sh copy_pair` / backticked-only C-08 ban) are not re-filed. This round attacks the **r4 amend’s new gates** (`install -m 0755` + `diff -q` Done-cell; C-08 four-pin / equality) and the still-unpinned `_connect` contract the r4 patch brief told the author not to reopen.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk source + live sqlite / `codegraph init` this session). SQLite URI `immutable=1`: https://sqlite.org/uri.html (fetched 2026-08-19).
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

A fourth plain-string `"unreadable"` is still the cheapest honest name: `!= "usable"` consumers stay fail-closed, `unrecognized` stays a real foreign version, and a smashed file can no longer ride a greenfield marker. Dropping the post-init `codegraph index` hop matches live evidence. The WAL `_connect` retry (plain `ro` first, `immutable=1` only on the exact `unable to open database file` ping) is the only way that fourth name does not also brand every healthy `codegraph init` as dead — live this session a fresh init is WAL `write_version=2` with no sidecars, `mode=ro` ping raises that exact OperationalError, and `immutable=1` reads `{1,5}` and writes no sidecar. Folding every production `sqlite3.connect(` under `bin/lib/` onto that helper, probing before the freshness cache, pinning WAL asserts 1–2 before `usable`, replacing the unsatisfiable `install.sh copy_pair` Done-cell with a body-only `install -m 0755` + silent `diff -q`, and pinning PRE-INDEX by equality plus the un-backticked leftover, are the right closures of r2–r4. That is the strongest honest case. It still pins the WAL *fixture* and `probe()` *outcome*, not `_connect`’s URI order or retry predicate; the named unreadable deny test still accepts the original `{none}` lie; and the new Cursor Done-cell refreshes a script body whose Python (and Claude’s live hook) load from other trees.

## Verdict

**revise** — 1 CRITICAL, 2 MAJOR. Do not spec OQ-4 A until one test *function* drives asserts 1–3 on one db **and** a locked db stays `"unreadable"`. Do not spec the unreadable deny copy until the named blast-gate test requires a distinctive phrase and forbids `unrecognized`. Do not treat the Cursor `diff -q` as “the deny copy is live” until the Claude plugin cache (the file Claude execs) is a sibling Done-cell.

---

## CRITICAL

### C1. The OQ-4 A tests pin the *fixture*, not `_connect`. Asserts 1–2 are raw `sqlite3.connect` in the test. “Same test or its fixture” still lets 1–2 and 3–4 run on different dbs. On one WAL db, `_connect = immutable=1` only (or retry on any `OperationalError`) still greens the list. Live, that launders a locked DELETE db to `"usable"` — C-04 fail-closed is gone.

Where: Chosen Approach §1.0 steps 1–4; §7 OQ-4 A asserts 1–5 + “same test or its fixture”; bad-faith table rows “OQ-4 assert 3 given 1+2 in front”; Risk row “`immutable=1` reads a db that IS being written”; C-04
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): After pytest is green, a locked index (daemon mid-write, `BEGIN EXCLUSIVE`) probes `"usable"`. The Write gate lets the edit through on a map SQLite is not willing to give a locked reader. The operator is not told to wait; C-04’s promise that unreadable is never usable is false. The opposite lie also still greens: skip the retry, keep enum-only, split asserts 1–2 onto a WAL fixture and 3–4 onto `make_index` — live `codegraph init` still probes dead.

Evidence:

Design (load-bearing `_connect` contract, prose only):

> “1. open `file:{path}?mode=ro` as today; 2. ping it with `SELECT 1`; 3. on `sqlite3.OperationalError` whose message is `unable to open database file`: close … retry **once** with `?mode=ro&immutable=1`”
> “**Plain `ro` leads; `immutable=1` is never the first attempt.** … leading with it would read a live db without its WAL and would silently launder the `busy` case”
> “asserts 1–2 above must run in the same test **or its fixture**”
> Dual-predicate table does **not** list C-04 vs the immutable retry.

Named pytest pins (complete list for OQ-4 A):

1. `header[18:20] == b'\x02\x02'` — file bytes, not `_connect`
2. raw `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` then `.execute("SELECT 1")` raises `unable to open database file` — **the test’s own URI**, not `_connect`’s first attempt
3. `probe() == "usable"` and no `-wal`/`-shm`
4. folded readers not empty on that db
5. junk/chmod still unreadable on both URIs

No listed assert reads `_connect`’s URI, requires the first attempt to be plain `ro`, or requires a `"database is locked"` probe to stay `"unreadable"`. The repo already uses `inspect.getsource` for this class of pin (`falkor-writ/tests/test_pre_write_dispatch.py:329`).

On-disk `_connect` is still plain `ro` with no ping (`falkor-writ/bin/lib/codegraph_index.py:46-50`). Fixture builders are still DELETE-journal (`tests/test_codegraph_index.py:70` `make_index` — `sqlite3.connect(idx)`).

Live this session (python sqlite 3.51.0):

```
# real codegraph init:
header[18:20] = b'\x02\x02'
listing [.gitignore, codegraph.db]
ro SELECT 1  OperationalError('unable to open database file')  # str(e) == that exact string
imm schema_versions [(1,), (5,)]
today's probe = ('unrecognized', frozenset(), frozenset({1, 5}))

# DELETE db + BEGIN EXCLUSIVE (writer holds lock):
ro SELECT 1 / schema  OperationalError('database is locked')
imm schema            ok [(1,)]     # USABLE if _connect leads with immutable or retries any OperationalError
```

SQLite URI docs (https://sqlite.org/uri.html, fetched 2026-08-19): `immutable=1` “skips all file locking and change detection”; if the file changes anyway, “incorrect query results and/or SQLITE_CORRUPT”.

Simulation A (split across “or its fixture”):

1. Skip `_connect` retry. Fold the three extra `sqlite3.connect(` sites so the one-opener grep is 1.
2. `test_wal_fixture_shape` (real-init fixture): asserts 1–2 only.
3. `test_probe_usable` / assert 4: `make_index` (write_version 1). Probe usable, readers return rows, no sidecars.
4. Junk/chmod on their own files. Wrapper pytest still uses `fake_codegraph` + `_make_usable_index`.
5. Every named pytest green. Live `codegraph init` still probes unrecognized today; after the enum-only change it probes `"unreadable"`. Wrapper exit 1 on a healthy fresh init.

Simulation B (same WAL db, skip the order/predicate):

1. `_connect` opens `?mode=ro&immutable=1` first (or retries every `OperationalError`, including `database is locked`).
2. Asserts 1–2 still pass (they never call `_connect`). Assert 3–4 pass on the WAL-no-sidecar fixture. Assert 5 still fails both URIs on junk/chmod.
3. Pytest green. DELETE exclusive lock → probe `"usable"` (C-04). Writes proceed.

Simpler design that removes the problem: one test *function* (not “or its fixture”) that, in order, (1) asserts header `b'\x02\x02'`, (2) asserts raw `mode=ro` ping still raises `unable to open database file`, (3) asserts `probe() == "usable"` on **that same path object**, (4) opens a second connection with `BEGIN EXCLUSIVE` on a DELETE fixture and asserts `probe() == "unreadable"`. Pair with `inspect.getsource(codegraph_index._connect)` containing plain `mode=ro` before `immutable=1`, and the exact error string as the only retry predicate.

Check:

```
python3 - <<'PY'
import sqlite3, tempfile, os, subprocess
from pathlib import Path
# DELETE exclusive + immutable launders (this session):
d = Path(tempfile.mkdtemp()); (d/'.codegraph').mkdir()
db = d/'.codegraph'/'codegraph.db'
w = sqlite3.connect(db); w.execute('CREATE TABLE schema_versions(version INTEGER)'); w.execute('INSERT INTO schema_versions VALUES (1)'); w.commit()
w.execute('BEGIN EXCLUSIVE')
print('ro', sqlite3.connect(f'file:{db}?mode=ro', uri=True).execute('SELECT 1').fetchall() if False else 'expect locked')
try:
    sqlite3.connect(f'file:{db}?mode=ro', uri=True).execute('SELECT 1')
except sqlite3.Error as e: print('ro', type(e).__name__, e)
print('imm', sqlite3.connect(f'file:{db}?mode=ro&immutable=1', uri=True).execute('SELECT version FROM schema_versions').fetchall())
PY
```

---

## MAJOR

### M1. The named blast-gate unreadable test accepts the unrecognized deny copy. Freshness can return `"unreadable"` and the operator still sees “unknown schema, found none” — scope pre-mortem 1, one function later.

Where: §3 unreadable / unrecognized deny copy; §7 `tests/test_blast_gate_hook.py` unreadable fixture pins; C-08; Pre-mortem 1; `falkor-writ/.claude/hooks/writ-blast-gate.sh:180-195`
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The fourth name exists in `probe()` / `freshness()`. The Write deny the operator actually reads is still “unrecognized schema (found: {none})”. That is the lie this bucket exists to kill. Pytest is green because the new test never requires “cannot be read” and never forbids “unrecognized”. The r4 amend hardened PRE-INDEX/PRE-SCHEMA leftover imperatives; it did not harden this pin.

Evidence:

§7 blast-gate pins for the unreadable fixture (complete list after the r4 amend):

> deny reason **contains** `writ codegraph-init`, **does not contain** ``Run `codegraph index` `` **nor the un-backticked `Run the codegraph index`**, and **does not contain** `stale`

Specified unreadable sentence (§3) is distinctive (`cannot be read`, `corrupt`, `locked`). The test does not require any of those words. It does not forbid `unrecognized`, `found`, or `none`. Existing `test_unrecognized_deny_names_both_version_sets` (`tests/test_blast_gate_hook.py:181-193`) still only covers a foreign-version fixture.

Live unrecognized copy (`writ-blast-gate.sh:191-195`), which is what an unreadable-as-unrecognized path prints today when `found` is empty (`:189` `or "none"`):

```
This repo's codegraph index is at an unrecognized schema version
(found: {none}; reader supports: {1, 5}).
Run `writ codegraph-init` to rebuild the index, then retry the write.
```

Python on that string this session:

```
writ codegraph-init              True
Run `codegraph index`            False
Run the codegraph index          False
stale                            False
cannot be read                   False
unrecognized                     True
named §7 unreadable test PASSES  True
```

Specified unreadable also passes those four pins (`cannot be read True`, `unrecognized False`) — so the honest path is not forced; the lie is cheaper (reuse the unrecognized branch).

§7 freshness pin (`freshness()` on schema-less → `"unreadable"`) lives in a different file. It forces the pass-through. It does **not** force the deny sentence. `'stale' not in reason` only blocks the `else:` swallow; it does not block the original `{none}` sentence.

Simulation (bad-faith, equal cost to good-faith):

1. Implement enum + freshness pass-through. Add `elif verdict == 'unreadable':` whose `reason` is a copy of the live unrecognized template (or call that branch).
2. Named unreadable test: contains `writ codegraph-init` ✓; no ``Run `codegraph index` `` ✓; no `Run the codegraph index` ✓; no `stale` ✓.
3. Operator on a junk db still reads “unrecognized schema (found: {none})”.

Simpler design that removes the problem: `assert "cannot be read" in reason` (or equality with §3’s unreadable sentence) **and** `assert "unrecognized" not in reason`.

Check: the Python booleans above; `rg -n unreadable tests/test_blast_gate_hook.py` (zero hits this session).

---

### M2. The r4 Done-cell copies the Cursor *script body*. Claude Code execs the plugin cache; the Cursor body loads Python from the writ-root pin. C-04 “Claude Write verified” is the source test, not the live file. The design never names `writ-refresh-plugin-cache.sh`.

Where: §3 Cursor twin Done-cell (`install -m 0755` + `diff -q`); C-04 “Claude Write/Edit — verified deny”; Surface-capability matrix Claude row; grill “same strings on Claude and Cursor”; falkor-writ `CLAUDE.md` “git pull alone updates NOTHING that runs”
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): An honest worker edits falkor-writ, copies the hook onto `~/.cursor/hooks/`, and greens pytest (which execs the repo source). Claude Code still runs `~/.claude/plugins/cache/writ/writ/1.6.1/.claude/hooks/writ-blast-gate.sh` with that tree’s `bin/lib/`. After this bucket, Claude keeps the three-branch copy: `freshness() == "unreadable"` falls into `else: stale` — pre-mortem 1 on the harness C-04 calls verified. That is operating burden the design decided the human will do unaided (refresh + Claude restart), while making the Cursor copy mechanical.

Evidence:

Claude live path (this machine, 2026-08-19):

- `~/.claude/plugins/installed_plugins.json:49-57` — `writ@writ` `installPath`: `/Users/phatchenh/.claude/plugins/cache/writ/writ/1.6.1` (not the clone). `lastUpdated` 2026-08-04.
- falkor-writ `hooks/hooks.json:245,258` — `bash ${CLAUDE_PLUGIN_ROOT}/.claude/hooks/writ-blast-gate.sh`
- `bin/writ-refresh-plugin-cache.sh:4-10` — “Claude Code copies a plugin into `~/.claude/plugins/cache/...` and runs hooks/agents FROM THAT COPY (via `--plugin-dir`). The copy does not follow `git pull`… Restart Claude Code afterwards.” Same file `:27-30` names this defect class: “A remediation tool that cannot affect the thing it remediates is the same defect class as a guard that cannot go red — it manufactures confidence.”

Pytest / Cursor Done-cell (design §3 / §7):

- `tests/test_blast_gate_hook.py:32-33` — `HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"`
- Done-cell is only `install -m 0755` source → `~/.cursor/hooks/writ-blast-gate.sh` then `diff -q`. Artifact grep for `writ-refresh-plugin-cache` / `plugin cache` / `CLAUDE_PLUGIN_ROOT` / `installPath`: **zero hits**.

Cursor body is not self-contained (`writ-blast-gate.sh:29-36`):

```
HOOK_DIR=…/$(dirname "$0")
WRIT_DIR="$(cd "$HOOK_DIR/../.." && pwd)"   # from ~/.cursor/hooks this is $HOME
if [ ! -f "$WRIT_DIR/bin/lib/common.sh" ]; then
  WRIT_DIR="$(cat …/agent-village/writ-root)"
fi
sys.path.insert(0, os.path.join(WRIT_DIR, "bin", "lib"))
```

Live this session: walk-up from `~/.cursor/hooks` → `WRIT_DIR=/Users/phatchenh`, no `common.sh`; pin is `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`. Deny *strings* come from the copied body; `probe()` / `freshness()` come from whatever tree the pin names. A worktree impl that copies the body and leaves writ-root on the clone makes the new `unreadable` branch dead code.

Human-authority (domain 3, operating burden): C-04 writes Claude deny as verified. The live Claude file updates only if the operator runs `bin/writ-refresh-plugin-cache.sh` and restarts Claude — unstated, while Cursor’s analogous refresh was promoted to a Done-cell. A subagent cannot close that.

Simulation (in-place clone edit, the happy path the design assumes):

1. Implement enum + unreadable deny branch in falkor-writ. Pytest greens (`HOOK = REPO/…`).
2. `install -m 0755` + silent `diff -q` vs `~/.cursor/hooks/`. Done-cell green. Cursor python = writ-root clone (new). Cursor strings new.
3. Do not run `writ-refresh-plugin-cache.sh`. Claude `CLAUDE_PLUGIN_ROOT` = cache 1.6.1. Cache hook still three-branch; cache `codegraph_index.probe` still maps junk to unrecognized / chmod to missing.
4. Claude operator sees `stale` or `{none}` unrecognized. C-04’s “Claude verified deny” was the source test.

Simpler design that removes the problem: sibling Done-cell `bin/writ-refresh-plugin-cache.sh` with `diff -q` of source vs the `installPath` from `installed_plugins.json` (the script already resolves that path). Or retract C-04 to “source script emits deny; live Claude is cache, refresh is operator.” Do not claim Claude is the verified harness until the cache row exists.

Check:

```
python3 -c 'import json; d=json.load(open("/Users/phatchenh/.claude/plugins/installed_plugins.json")); print(d["plugins"]["writ@writ"][0]["installPath"])'
# /Users/phatchenh/.claude/plugins/cache/writ/writ/1.6.1
sed -n '32,33p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py
sed -n '29,36p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh
rg -n 'writ-refresh-plugin-cache|plugin cache|CLAUDE_PLUGIN_ROOT|installPath' \
  /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
```

---

## Mode

Cross-model (opus design, grok-4.6 reviewer). Certifies craft against the r4-patched text and live code/sqlite this session. Cannot certify shared-judgment blind spots this reviewer shares.

## Open (not re-filed)

OQ-5.1 Cursor envelope — recorded, allowed residual. OQ-3 empty `schema_versions` table — frozen. OQ-2 busy fold — recorded. PRE-SCHEMA belt asserts catch the r4 keep-`Rebuild` game; leftover append-to-specified is MINOR and omitted here.
