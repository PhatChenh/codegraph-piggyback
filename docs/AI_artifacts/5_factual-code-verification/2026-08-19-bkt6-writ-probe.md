# Factual Code Verification: Bucket 6 — writ probe honesty + `writ codegraph-init` honest exit
_Last updated: 2026-08-20_

Spec: `docs/AI_artifacts/4_specs/2026-08-19-bkt6-writ-probe.md`
Design: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md` (Option A; r9 C1 ABSORB `ac4ecea7` supersedes design §7 AST walk)
Grill: `docs/AI_artifacts/_handoff/2026-08-19-bkt6-writ-probe-grill.md`
Protocol: `.village/runs/2026-08-19-bkt6-writ-probe/protocol-card.md`
Code home: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`
TD-01: OPEN (`docs/TECH_DEBT.md`). OQ-5.1 OPEN. OQ-6 OPEN. OQ-5.2 CLOSED 2-b. OQ-2/OQ-3 recorded, not this phase.

Runtime this session (2026-08-20): Python **3.12.13**; `sqlite3.sqlite_version` **3.51.0**; `codegraph --version` **999.0.0** → `~/.codegraph/versions/v1.0.1`. CodeGraph MCP indexes piggyback; falkor-writ bodies via Read/Grep + live temp-dir probes. No write to `.codegraph/codegraph.db`. No `npm i -g @colbymchenry/codegraph`.

Calibration (NON-INTERACTIVE, Recommended): deep-trace every spec Already-built / inventory file. Design §7 AST “fails by construction” treated as **superseded** (spec 9c / C1 ABSORB) — not verified into the plan.

No blocking conflicts. STATE.md Track J / plugin-cache nags ignored per brief. piggyback TD-01 still says “Bucket 6 (writ wrapper runs `index`)” — spec C-09 / comp 10 updates that note; not an assumption invalidation.

Structural audit: pass.

## Overview

`probe()` today is a three-name lie: file-absent and connect-fail both return `"missing"`; SELECT-fail / missing `schema_versions` returns `("unrecognized", frozenset(), {1,5})`. `freshness()` cache-then-probes and collapses every non-usable, non-missing state to `"unrecognized"`. Blast-gate `else:` treats anything else as stale. Wrapper guard-2 prints the raw probe and exits **0** when not usable. Four `bin/lib/` `sqlite3.connect` sites; none pass `timeout`; none retry `immutable=1`. A live `codegraph init` WAL-no-shm db is unreadable on plain `mode=ro` and readable on `immutable=1`. Spec A1–A14 + S1–S6 all match this code. **0 invalidated. 0 unverifiable.** Ready for `/plan`.

## Key Components

| Symbol | Site | Role now |
|---|---|---|
| `KNOWN_SCHEMA_VERSIONS` | `falkor-writ/bin/lib/codegraph_index.py:27` | `frozenset({1, 5})` — frozen C-11 |
| `_index_path` | `codegraph_index.py:42-43` | `repo/.codegraph/codegraph.db` |
| `_connect` | `codegraph_index.py:46-50` | `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` + `Row`; **no timeout, no ping, no retry** |
| `probe` | `codegraph_index.py:53-79` | absent → `"missing"`; connect `Error` → `"missing"`; SELECT `Error` → empty-found tuple; `found <= known` → `"usable"` |
| `enclosing_symbol` / `_nodes_with_ids` / `interface_members` / `_edges` | `codegraph_index.py:86-206` | readers via `_connect`; connect-fail → `None`/`[]` |
| `blast_radius._connect` | `blast_radius.py:133-137` | **duplicate** same URI open |
| `blast_radius._index_path` | `blast_radius.py:129-130` | sibling duplicate; used by `nodes_in_file` / `_db_mtime` — keep (fold is `_connect` body only) |
| `nodes_in_file` / `blast_nodes` / `report_for_file` | `blast_radius.py:160-184` / `:187-208` / `:403-420` | empty on sqlite error |
| `FRESH_CACHE_TTL` | `blast_radius.py:69` | `300` |
| `freshness` | `blast_radius.py:256-312` | **cache then probe**; `state != "usable"` → `"unrecognized"`; write path only `"fresh"` |
| `check_predispatch` | `artifact_claims.py:931-1039` | five branches; `except Exception: probe = "missing"` `:979-980` comment `unreadable index == missing`; consume `probe == "usable"` `:1031` |
| `PRE_SECTION`/`PRE_INDEX`/`PRE_MARKER`/`PRE_SCHEMA` | `artifact_claims.py:858-861` | no `PRE_UNREADABLE` |
| `_c16_resolve_node` | `artifact_claims.py:2155-2184` | `import sqlite3` **inside** `:2164`; private `mode=ro` open `:2166-2168` |
| `_c12_container` | `artifact_claims.py:2478-2509` | same inner import `:2486` + private open `:2488-2490` |
| `check_c11`/`check_c12`/`check_c16` | `artifact_claims.py:2271` / `:2351` / `:2187` | `if probe != "usable": return []` |
| blast-gate Write deny | `.claude/hooks/writ-blast-gate.sh:169-211` | missing / unrecognized / `else: # stale`; envelope `permissionDecision: "deny"` |
| wrapper | `bin/writ-codegraph-init.sh:165-175` | `print(probe(...))`; `!= "usable"` → stderr + **exit 0** |
| `codegraph_init` | `writ/cli.py:966-992` | locate script, pass exit — CONSUMER-ONLY |
| pytest `HOOK` | `tests/test_blast_gate_hook.py:33` | `REPO / ".claude" / "hooks" / "writ-blast-gate.sh"` |
| `make_index` | `tests/test_codegraph_index.py:65-79` | DELETE-journal (`header[18:20]==b'\x01\x01'`) |
| `_make_usable_index` / `fake_codegraph` | `tests/test_writ_codegraph_init.py:47-54,93-106` | DELETE fixture; fake init `exit 0` |
| `test_unusable_index_leaves_marker` | `tests/test_writ_codegraph_init.py:143-151` | asserts **exit 0** |
| `project_rules._connect` | `bin/lib/project_rules.py:76` | FalkorDBLite — not sqlite |
| `docs/adr/` | **absent** | `ls` → No such file |

## How It Works

**`probe`.** `is_file()` first (`:63-64`) → `"missing"`. Else `_connect` (`:66`); `sqlite3.Error` → `"missing"` (`:67-68`). Else `SELECT version FROM schema_versions` (`:70`); `sqlite3.Error` → `("unrecognized", frozenset(), KNOWN_SCHEMA_VERSIONS)` (`:71-72`); `finally: con.close()` (`:73-74`). `found <= known` → `"usable"` (`:77-78`) else tuple (`:79`). Empty found-set (valid sqlite, empty table) is **usable** (OQ-3, frozen).

**Live this session (`/tmp/bkt6-fcv-PDjv`):**
- absent path → `is_file False`, `probe='missing'`
- `chmod 000` existing file → `is_file True`, `probe='missing'`; connect/select `OperationalError 'unable to open database file'`
- junk bytes → connect OK, select `DatabaseError 'file is not a database'`, `probe=('unrecognized', frozenset(), {1,5})`
- sqlite without `schema_versions` → connect OK, select `OperationalError 'no such table: schema_versions'`, same empty-found tuple
- DELETE-journal fixture (`sqlite3.connect(path)` no URI) → `header[18:20]=b'\x01\x01'`, plain `ro` SELECT 1 OK, `probe='usable'`
- live `codegraph init` → `header[18:20]=b'\x02\x02'`, listing `[.gitignore, codegraph.db]`, plain `ro` `unable to open database file`, `immutable=1` returns schema rows `(1,),(5,)`

**`_connect` today.** One URI `file:{db}?mode=ro`, no `timeout=` (stdlib default **5.0s**), no `SELECT 1`, no retry. WAL-no-shm therefore looks like connect-fail → `"missing"` (chmod-class) rather than usable.

**`freshness`.** Reads `.codegraph/.freshness-verdict.json` **before** `probe` (`:270-283`). Hit: `verdict=="fresh"` + TTL + matching `db_mtime` → return `"fresh"` without probing. Then `probe` (`:285`); `"missing"` pass-through; `state != "usable"` → `"unrecognized"` (`:288-289`). Cache write only `"fresh"` (`:303-308`). Comp 4 must probe **first** or a chmod/lock with restored mtime stays `"fresh"` inside TTL (M1).

**Blast-gate.** `verdict = freshness(repo)` (`:169`). Write: missing sentence `:174-178`; unrecognized re-probes for version sets `:180-195`; **`else: # stale`** `:196-202` swallows any new word (including future `"unreadable"`) as stale. Envelope `:204-211` `permissionDecision: "deny"`. Read WARN interpolates verdict (`:158`) — no new branch needed. Pytest `HOOK` is **source** (`test_blast_gate_hook.py:33`), not `~/.cursor/hooks/`. Live Cursor: `~/.cursor/hooks.json:84-86` runs `~/.cursor/hooks/writ-blast-gate.sh` on `preToolUse` matcher `Write` `failClosed: true`. OQ-5.2=2-b: impl must **not** overwrite that copy.

**Audit seat.** `probe=="missing"` → PRE-INDEX / marker (`:982-997`). Tuple `"unrecognized"` → PRE-SCHEMA (`:998-1005`). Comment `:980` `unreadable index == missing`. A future `"unreadable"` **string** currently falls through both arms (no PRE-* deny) while consume still requires `"usable"` (`:1031`). Comp 6 adds PRE-UNREADABLE **before** missing. C11/C12/C16: `probe != "usable"` → `[]` (M5 silence) — fail-closed with zero edits.

**Wrapper.** After `codegraph init` exit 0 + guards 3/4, prints `probe(...)` as one line (`:169`) then `if [ "$PROBE" != "usable" ]` (`:172`) → `codegraph index not usable (probe='$PROBE'); marker left…` + **exit 0** (`:173-174`). Tuple unrecognized stringifies via `print()`. No `codegraph index` hop today (C1-a already true in source; honesty is the exit code). CLI `writ/cli.py:990-992` already passes nonzero through.

**Openers.** `rg sqlite3.connect bin/lib/` = four sites: `codegraph_index.py:48`, `blast_radius.py:135`, `artifact_claims.py:2166`, `:2488`. No `from sqlite3 import connect`. No `sqlite3.dbapi2`. `_c16`/`_c12` look up `sqlite3.connect` at call time (inner import). Tests + `writ/origin_context.py` out of `bin/lib/` scope.

## Spec Verification

| Assumption ID | Spec Claim | Verdict | Evidence |
| A1 | `_connect` failure reachable only for an existing file; `is_file` precedes connect; chmod 000 today → `missing` | ✅ Validated | `codegraph_index.py:63-68`. Live: absent `is_file False` `probe='missing'`; chmod 000 `is_file True` `probe='missing'` |
| A2 | Junk / schema-less db reaches SELECT, not connect | ✅ Validated | Live: junk connect OK + `DatabaseError 'file is not a database'` → empty-found tuple; noschema connect OK + `no such table: schema_versions` → same tuple |
| A3 | Every non-listed consumer compares against `"usable"` | ✅ Validated | C11 `:2278` / C12 `:2358` / C16 `:2198` `if probe != "usable": return []`. Consume `:1031` `probe == "usable"`. Listed special-cases: freshness `:288`, predispatch `:982/:998`, blast-gate `:174/:180`, wrapper `:172`. `writ-doctor.sh:367` prints freshness (OUT). No consumer treats other strings as usable |
| A4 | `freshness()` narrows every non-usable, non-missing state to one word | ✅ Validated | `blast_radius.py:286-289`. No third probe-narrowing site (`rg freshness(` → blast-gate + doctor print) |
| A5 | Freshness cache only ever writes `fresh` | ✅ Validated | `blast_radius.py:303-308` `"verdict": "fresh"`. Tests `:333-359` refuse caching missing/stale/unrecognized |
| A6 | Wrapper guard-2 is string compare on a printed probe | ✅ Validated | `writ-codegraph-init.sh:169` `print(codegraph_index.probe(sys.argv[1]))`; `:172` `if [ "$PROBE" != "usable" ]`. Not JSON/tuple parse |
| A7 | `codegraph index` fails both retry-target states; `init` repairs junk | ✅ Validated | Live this session: no-db `index` exit **1** `Run "codegraph init" first`; junk `index` exit **1** `Failed to index: file is not a database`; same junk `init` exit **0** `Indexed 1 files` |
| A8 | Bucket 4 repair live in installed binary | ✅ Validated | `~/.codegraph/versions/v1.0.1/lib/dist/bin/codegraph.js:578` ``Cannot repair index (errcode ${health.errcode})``; unreadable arm `unlinkUnreadableIndex` follows. Built 2026-08-18 (`ls -l` Aug 18 11:38). PATH → that tree |
| A9 | Deny is Claude-shaped; pytest HOOK is source not Cursor copy | ✅ Validated | Envelope `writ-blast-gate.sh:204-207` `"permissionDecision": "deny"`. `HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"` (`test_blast_gate_hook.py:33`). Cursor wiring live `~/.cursor/hooks.json:84-86` — operator copy, not pytest |
| A10 | falkor-writ has no `docs/adr/` yet | ✅ Validated | `ls docs/adr` → No such file; `docs/decisions/` absent |
| A11 | Fresh init is WAL-no-shm unreadable on plain `ro`; fixtures are DELETE | ✅ Validated | Live init `header[18:20]=b'\x02\x02'`, listing `[.gitignore, codegraph.db]`, plain `ro` `unable to open database file`, `immutable=1` schema rows. `make_index`-style `b'\x01\x01'`, plain `ro` already usable. chmod 000 fails **both** URIs |
| A12 | Exactly four `sqlite3.connect` under `bin/lib/` | ✅ Validated | `rg sqlite3.connect bin/lib/` → four lines above. `from sqlite3 import` empty. Fifth would be a new site |
| A13 | `_c16`/`_c12` `import sqlite3` inside the function | ✅ Validated | `artifact_claims.py:2164` / `:2486` then `sqlite3.connect(` `:2166` / `:2488`. Module-level import absent in those functions |
| A14 | `sqlite3.connect` timeout is second positional | ✅ Validated | Official Python 3.14 docs (fetched 2026-08-20) `sqlite3.connect(database, timeout=5.0, …)` — https://docs.python.org/3/library/sqlite3.html . Positional timeout deprecated 3.13, keyword-only 3.15. This machine 3.12.13: `sqlite3.connect(":memory:", 0)` accepted. kwargs-only pin would miss positional `0` |
| S1 | Assumptions falsifiable | ✅ Validated | each A-row has a disproof column |
| S2 | Done-when observable | ✅ Validated | comps 1–10 name probe strings, URIs, exit codes, message equality, recorder counts — not “pytest green” |
| S3 | Independently testable | ✅ Validated | depends-on is earlier comps only; fold verifiable by delegate + grep before WAL pin |
| S4 | No silent HOW deferrals | ✅ Validated | C1 ABSORB = runtime wrap (9c); production `timeout=0` keyword (comp 9 Decisions); OQ-5.1/5.2/6 explicit |
| S5 | Data model declared | ✅ Validated | enum four names; PRE_UNREADABLE; cache `{verdict,db_mtime,checked_at}`; recorder `(uri, timeout, stack)`; wrapper kind/detail |
| S6 | Dependency order sound | ✅ Validated | 1→2→{3,4,6,7}; 5 after 4; 8 after 2+7; 9 after 1–7; 10 after 7. Design AST walk is Out-of-scope |

## Edge Cases & Silent Failure Modes

- **WAL-no-shm init looks `missing` today** (connect `unable to open database file` → `:67-68`). Comp 1 retry must fire **only** on that exact string; `'database is locked'` must propagate (default timeout 5.0s would make 5b ~5s — production `timeout=0`).
- **Junk/no-table look `unrecognized` with empty found** (`:71-72`). Comp 2 maps both to `"unreadable"`. Foreign version `9` stays the tuple.
- **`freshness` cache-before-probe** (`:270-285`): chmod/lock + `os.utime` restore inside TTL returns `"fresh"`. Comp 4 probe-first.
- **Blast-gate `else: # stale`** (`:196`): new `"unreadable"` would deny as stale (contains `stale_index_days`, not the unreadable sentence). Comp 5 inserts `elif verdict == 'unreadable'` **before** else.
- **Predispatch fall-through:** a `"unreadable"` string is neither `== "missing"` nor unrecognized tuple → no PRE-* deny (dispatch proceeds). Comp 6 branch-before-missing. Marker not consumed (`:1031`).
- **Wrapper exit 0** on still-unusable (`:174`) + `test_unusable_index_leaves_marker` asserts that (`:149`). Comp 7 flips to exit 1. Tuple `print()` is one line — spec wants kind then detail as **two** printed lines.
- **`make_index` / `_make_usable_index` / `fake_codegraph` are DELETE + fake exit 0** — forbidden as WAL-fixture builders (spec 9b). Keep for enum/consume tests.
- **`report_for_file` / `_c16` / `_c12` silent-empty** on WAL until fold (comp 3) because private `mode=ro` cannot ping-retry.
- **chmod 000 is not a lock stand-in** (A11 + spec 9a). Both URIs fail `unable to open database file`, not `'database is locked'`.
- **Python 3.15** makes timeout keyword-only (docs 3.13 deprecation). Production uses keyword `timeout=0` (spec Decisions). Test pin must accept kwarg **or** positional 0.
- **Inner `import sqlite3`** means a wrap of stdlib `sqlite3.connect` observes `_c16`/`_c12` **until** fold; after fold only `_connect` should appear (A13).
- **C1 ABSORB:** do **not** implement design §7 AST walk. Private `import sqlite3 as sq` / `dbapi2.connect` would fool a file-count, not a runtime wrap.
- **Empty `schema_versions` table** still `usable` (`found=frozenset() <= known`) — OQ-3, do not “fix”.
- **Read WARN** interpolates `verdict` (`:158`); after pass-through it will say `unreadable` for free. No new Read branch.
- **Existing PRE-INDEX test** `:1670` `assert "index" in msg.lower()` still passes the replacement (contains `codegraph index` noun phrase). Spec: that assert does **not** substitute for equality.

## Dependencies & Coupling

- `blast_radius.py:36` already `import codegraph_index` — fold `_connect` delegates; **no** new `_shared` module.
- Fold `_c16`/`_c12` keep try/except + return contract; copy retry **nowhere**.
- C11/C12/C16 probe-guards **untouched**. Marker consume predicate **untouched**.
- `writ/cli.py` CONSUMER-ONLY. `writ-doctor.sh` prints new word for free (OUT).
- Blast-gate source only; no `hooks.json`; no `install.sh --all/--only`; no overwrite of `~/.cursor/hooks/writ-blast-gate.sh`.
- Wrapper’s only repair is Bucket 4 `codegraph init` (A7/A8). No post-init `codegraph index`.
- pytest stays in falkor-writ (R4-a). piggyback change = TD-01 dated note only.
- R15: same `probe()` + wrapper; deny copy harness-agnostic **in source**.

## Extension Points

- `_connect` `[closed]` — sole production opener after fold; retry is hidden behind `_connect(repo) -> Connection`.
- `probe` enum `[closed]` — four names frozen; no fifth `busy`.
- Blast-gate deny branches `[closed]` — insert `unreadable` between missing and unrecognized; else stays stale.
- `check_predispatch` branches `[closed]` — sixth branch before missing.
- C1 pin `[closed]` — runtime wrap of real `sqlite3.connect`, not AST.

## Open Questions

- **OQ-5.1 OPEN** — Cursor deny envelope (flat `permission`). Do not emit dual envelope. Do not claim Cursor blocks.
- **OQ-6 OPEN** — Claude plugin-cache refresh is operator (`bin/writ-refresh-plugin-cache.sh`), not a Done-cell.
- **OQ-5.2 CLOSED 2-b** — live `~/.cursor/hooks/writ-blast-gate.sh` refresh is operator, same class as OQ-6.
- **OQ-2** — `busy` as a fifth writ name later; SQLITE_BUSY folds into `unreadable` this phase.
- **OQ-3** — empty `schema_versions` table stays `usable`.

No new code-undeterminable questions. A7/A8/A11 re-verified live this session.

## Technical Debt Spotted

- piggyback `docs/TECH_DEBT.md` TD-01 still OPEN and still says Bucket 6 wrapper runs `index` — **stale vs C1-a**. Spec comp 10: dated note, status stays OPEN. Do not close TD-01.
- Default sqlite timeout 5.0s on production `_connect` — load-bearing for 5b wall-clock; spec already requires `timeout=0`.
- Duplicate `blast_radius._index_path` / `_connect` — fold removes duplicate **open**, not the path helper.
