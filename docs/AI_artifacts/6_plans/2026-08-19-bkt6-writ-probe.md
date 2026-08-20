# Plan: Bucket 6 — writ probe honesty + `writ codegraph-init` honest exit
_Last updated: 2026-08-20_
_Status: [ ] pending_

Spec: `docs/AI_artifacts/4_specs/2026-08-19-bkt6-writ-probe.md` (components 1–10). FCV: `docs/AI_artifacts/5_factual-code-verification/2026-08-19-bkt6-writ-probe.md` (A1–A14 + S1–S6 ✅; **no** `## Invalidated Assumptions`). Design: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`. Grill LOCKED. TD-01 stays OPEN. OQ-5.1 / OQ-6 OPEN (operator). OQ-5.2 CLOSED 2-b. OQ-2 / OQ-3 recorded, not this phase.

Code home: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (impl cwd except Step 10). Artifact home: this piggyback tree.

gate-waive: C6-FICTION — falkor-writ symbols (`KNOWN_SCHEMA_VERSIONS`, `PRE_UNREADABLE`, probe enum names) cited by abs `external:` path; not piggyback symbols, not new in this index.

## Analysis

This phase extends falkor-writ `probe()` / `_connect` / freshness / blast-gate / audit / wrapper so file-exists-but-dead is the string `"unreadable"`, not `"missing"` or empty-found `"unrecognized"`. Spec owns WHAT (enum, exact sentences, C1 ABSORB runtime wrap). This plan owns TDD order, the `_connect` retry body, fold-not-copy, and the one-`def` WAL+lock pin.

**HOW lock A (OQ-4 A / C1-a):** production `_connect` uses keyword `timeout=0` on every `sqlite3.connect`. First URI **exact** `f"file:{path}?mode=ro"` (no `immutable` / `nolock` / `vfs=`). `SELECT 1`. Retry once `f"file:{path}?mode=ro&immutable=1"` **only** when `str(e) == "unable to open database file"`. `'database is locked'` propagates; retry does not fire. Never lead with `immutable=1`. Never `codegraph index`. Never unlink the db.

**HOW lock B (C1 ABSORB):** do **not** implement design §7 AST walk. One-opener pin = `unittest.mock.patch("sqlite3.connect", wraps=sqlite3.connect)` (or equivalent that still opens). Fresh `recorded.clear()` (or a new list) immediately before each `_connect`/`probe` drive that asserts a count. After fold, every `bin/lib/` connect’s first `bin/lib/` frame is `codegraph_index._connect`; URI ∈ the two pinned URIs.

**HOW lock C (copy, exact user-visible strings — equality pin):** paste these bytes. Tests `==` the full sentence (formatted PRE-SCHEMA uses the fixture’s sets).

Blast-gate `unreadable` `permissionDecisionReason` (new branch **between** missing and unrecognized):

```
This repo's codegraph index file exists but cannot be read (corrupt, truncated, or locked by another indexer), so Writ cannot verify what this write may affect. Run `writ codegraph-init` to rebuild it, then retry the write. If it still fails, the file is junk or unreadable by this user — inspect or fix permissions on `.codegraph/codegraph.db` yourself; Writ never deletes it.
```

PRE-UNREADABLE (new; branch **before** `missing`):

```
Codegraph index file exists but cannot be read (corrupt, truncated, or locked). Run `writ codegraph-init` to rebuild it before dispatch; if that fails, inspect or fix permissions on the file yourself.
```

PRE-INDEX replacement (delete `Run the codegraph index`):

```
No codegraph index for this repo. Run `writ codegraph-init` before dispatch, or mark the repo greenfield (`writ predispatch-audit --mark-greenfield <artifact>`).
```

PRE-SCHEMA replacement (delete sentence-initial `Rebuild the index`):

```
Codegraph index at an unrecognized schema version: found {sorted(found)} but this reader knows {sorted(known)}. Run `writ codegraph-init` to rebuild the index at a known schema version.
```

Wrapper still-not-usable (exit **1**, marker left, db not deleted; two probe print lines: `kind` then `detail`):

- `missing` → `writ-codegraph-init: codegraph init exited 0 but no index database exists at <db>; check the init output above. Marker left for audit-time consume.`
- `unreadable` → `writ-codegraph-init: codegraph init exited 0 but the index at <db> is still unreadable; the file was NOT deleted. Inspect it or fix its permissions yourself, then re-run 'writ codegraph-init'. Marker left for audit-time consume.`
- `unrecognized` → `writ-codegraph-init: index at <db> is at an unrecognized schema version (found {…}; this reader knows {1, 5}). Marker left for audit-time consume.`

Missing blast-gate copy **unchanged**. Unrecognized blast-gate copy **unchanged**. Envelope **unchanged**.

**HOW lock D:** impl must **not** overwrite `~/.cursor/hooks/writ-blast-gate.sh`. No `hooks.json`. No `install.sh --all/--only`. Cursor copy is operator (OQ-5.2 = 2-b). Do not write “the deny blocks on Cursor.”

**HOW lock E:** `make_index` / `_make_usable_index` / `fake_codegraph` stay DELETE-journal / fake `exit 0`. Forbidden as WAL-fixture builders. WAL db comes from real `codegraph init` in a temp git repo. chmod 000 is **not** the lock stand-in.

## Pre-dispatch audit

### 1. Consumer list per changed identifier

| Identifier | Consumers | Affected? |
|---|---|---|
| `probe` | `freshness`; `check_predispatch`; `check_c11`/`check_c12`/`check_c16`; wrapper; blast-gate unrecognized re-probe; tests | YES — enum grows `"unreadable"`. C11/C12/C16 guards **no edit**. Consume `:1031` **no edit**. |
| `_connect` | `probe`, `enclosing_symbol`, `_nodes_with_ids`, `interface_members`, `_edges`; after fold also `blast_radius._connect`, `_c16_resolve_node`, `_c12_container` | YES — ping + one retry; `timeout=0` |
| `freshness` | blast-gate Write/Read; `writ-doctor.sh` (OUT, prints for free) | YES — probe first; pass-through |
| `blast_radius._connect` | `nodes_in_file`, `blast_nodes`, `_nodes_with_ids` → `report_for_file` | YES — delegate |
| blast-gate deny `reason` | Claude PreToolUse (source); pytest `HOOK` | YES — new branch in source only |
| wrapper guard 2 | `codegraph_init` passthrough | YES — exit 1 + three messages. CLI **not** edited. |
| `KNOWN_SCHEMA_VERSIONS` | probe usable/unrecognized | NO — frozen |

### 2. Recorded command + output per scope claim

FCV session 2026-08-20, falkor-writ: four `sqlite3.connect` under `bin/lib/`; live `codegraph init` WAL `header[18:20]=b'\x02\x02'`; plain `ro` `unable to open database file`; `immutable=1` schema rows; junk/chmod as A2/A11. Do not re-derive.

### 3. One contradiction looked for and not found

No fifth `bin/lib/` opener. `project_rules._connect` is FalkorDBLite. Design §7 AST walk is superseded (spec 9c) — do not plan it.

## Facts (live-certified — do NOT re-derive)

- `_connect` is one URI, no timeout — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:48) — quote: "`con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)`"
- Row factory already set — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:49) — quote: "`con.row_factory = sqlite3.Row`"
- `KNOWN_SCHEMA_VERSIONS` is `{1, 5}` — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:27) — quote: "`KNOWN_SCHEMA_VERSIONS = frozenset({1, 5})`"
- `_index_path` is `repo/.codegraph/codegraph.db` — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:42-43) — quote: "`return Path(repo) / ".codegraph" / "codegraph.db"`"
- File-absent is first — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:63-64) — quote: "`if not _index_path(repo).is_file():`" / "`return "missing"`"
- Connect-fail is `"missing"` today — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:67-68) — quote: "`except sqlite3.Error:`" / "`return "missing"`"
- SELECT-fail is empty-found tuple — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:71-72) — quote: "`except sqlite3.Error:`" / "`return "unrecognized", frozenset(), KNOWN_SCHEMA_VERSIONS`"
- `finally` closes — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:73-74) — quote: "`finally:`" / "`con.close()`"
- Usable is subset — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:77-78) — quote: "`if found <= KNOWN_SCHEMA_VERSIONS:`" / "`return "usable"`"
- Probe surface omits unreadable — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:12) — quote: "`probe(repo)            -> "usable" | "missing" | ("unrecognized", found, known)`"
- Sibling already imports the reader — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:36) — quote: "`import codegraph_index  # noqa: E402  sibling — same discipline as artifact_claims.py`"
- Duplicate blast opener — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:135) — quote: "`con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)`"
- `FRESH_CACHE_TTL` is 300 — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:69) — quote: "`FRESH_CACHE_TTL = 300  # seconds`"
- Freshness cache then probe — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:270-285) — quote: "`cache = _verdict_cache_path(repo)`" / "`state = codegraph_index.probe(repo)`"
- Non-usable collapses to unrecognized — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:288-289) — quote: "`if state != "usable":`" / "`return "unrecognized"`"
- Cache write is fresh-only — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:306) — quote: "`"verdict": "fresh",`"
- `report_for_file` reads via `nodes_in_file` — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:412) — quote: "`symbols = nodes_in_file(repo, relpath)`"
- Predispatch comment lies — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:980) — quote: "`probe = "missing"                        # unreadable index == missing`"
- Predispatch missing arm — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:982) — quote: "`if probe == "missing":`"
- PRE-INDEX old sentence — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:987-989) — quote: "`"No codegraph index for this repo. Run the codegraph index "`"
- PRE-SCHEMA old Rebuild — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1003-1004) — quote: "`f"{sorted(found)} but this reader knows {sorted(known)}. Rebuild "`"
- Marker consume is usable-only — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1031) — quote: "`if probe == "usable" and not any(f.severity == "DENY" for f in findings):`"
- PRE ids lack UNREADABLE — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:859-861) — quote: "`PRE_INDEX = "PRE-INDEX"          # index missing and no greenfield marker`"
- `_c16_resolve_node` inner import — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2164-2168) — quote: "`import sqlite3`" / "`con = sqlite3.connect(`"
- `_c12_container` inner import — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2486-2489) — quote: "`import sqlite3`" / "`con = sqlite3.connect(`"
- C16 probe-guard — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2198) — quote: "`if probe != "usable":`"
- C11 probe-guard — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2278) — quote: "`if probe != "usable":`"
- C12 probe-guard — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2358) — quote: "`if probe != "usable":`"
- Blast-gate missing copy — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:174-178) — quote: "`if verdict == 'missing':`" / "`Run \`writ codegraph-init\` to build the index, `"
- Blast-gate else is stale — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:196) — quote: "`else:  # stale`"
- Deny envelope is Claude-shaped — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:204-206) — quote: "`print(json.dumps({"hookSpecificOutput": {`" / "`"permissionDecision": "deny",`"
- Header omits unreadable — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:6) — quote: "`#   - code Write|Edit when the codegraph index is missing / unrecognized /`"
- Wrapper prints probe — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:169) — quote: "`print(codegraph_index.probe(sys.argv[1]))`"
- Guard-2 is string compare + exit 0 — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:172-174) — quote: "`if [ "$PROBE" != "usable" ]; then`" / "`exit 0`"
- CLI passes exit — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/writ/cli.py:990-992) — quote: "`proc = subprocess.run([str(script), *ctx.args], env=env)`" / "`raise typer.Exit(code=proc.returncode)`"
- Pytest HOOK is source — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py:33) — quote: "`HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"`"
- `test_unusable_index_leaves_marker` asserts exit 0 — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py:149) — quote: "`assert proc.returncode == 0, proc.stderr`"
- `make_index` uses path connect — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_codegraph_index.py:70) — quote: "`con = sqlite3.connect(idx)`"
- `_make_usable_index` is DELETE fixture — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py:98) — quote: "`con = sqlite3.connect(idx)`"
- `fake_codegraph` is exit 0 — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py:52) — quote: "`fake.write_text("#!/usr/bin/env bash\nexit 0\n")`"
- PRE-INDEX test is substring — (external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_artifact_claims.py:1670) — quote: "`assert "index" in msg.lower()`"
- Timeout is second positional (Py 3.14 docs, fetched 2026-08-20) — (https://docs.python.org/3/library/sqlite3.html) — quote: "`sqlite3.connect(database, timeout=5.0, detect_types=0, isolation_level='DEFERRED', check_same_thread=True, factory=sqlite3.Connection, cached_statements=128, uri=False, *, autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)`"
- TD-01 still says wrapper runs index — (`docs/TECH_DEBT.md:6`) — quote: "`Native plugin/event bus still later.`"
- Installed init repair string — (external: /Users/phatchenh/.codegraph/versions/v1.0.1/lib/dist/bin/codegraph.js:578) — quote: "`Cannot repair index (errcode`"
- FCV: live init WAL header + four `bin/lib/` connect sites — (`docs/AI_artifacts/5_factual-code-verification/2026-08-19-bkt6-writ-probe.md:21`) — quote: "`Spec A1–A14 + S1–S6 all match this code.`"
- `docs/adr/` absent in falkor-writ (create it). Reuse names: `enclosing_symbol`, `callers_of`, `interface_members`, `_edges`, `report_for_file`, `check_predispatch`, `PRE_INDEX`, `_c16_resolve_node`, `_c12_container`, `check_c11`, blast-gate deny envelope, blast-gate missing / unrecognized copy, wrapper guards 1, 3, 4, `codegraph_init`, pytest HOOK path, `make_index`.

## Files

- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py` — extend `_connect` + `probe`
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py` — fold `_connect`; rewrite `freshness`
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py` — fold `_c16_resolve_node` / `_c12_container`; `PRE_UNREADABLE`; `check_predispatch` branch + PRE-INDEX/PRE-SCHEMA sentences
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh` — unreadable branch + header word
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh` — guard-2 kind/detail + exit 1 messages
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/docs/adr/0001-unreadable-is-not-unrecognized.md` — create
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_codegraph_index.py` — enum / chmod / junk / both-URI pins
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_radius.py` — freshness pass-through + cache-mask
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py` — unreadable deny equality
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_artifact_claims.py` — PRE-UNREADABLE + PRE-INDEX/PRE-SCHEMA equality
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py` — exit 1 + live WAL wrapper
- `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_connect_wal_lock.py` — create; one-def WAL+lock+runtime wrap
- `docs/TECH_DEBT.md` — TD-01 dated note; status stays OPEN

## Delegation Authority

- **Allowed set** = the union of every step's "Files to modify" (= ## Files). Nothing outside it.
- A file in ## Files assigned to ANOTHER step = a dependency (run per ## Implementation Order), not a deviation.
- A file NOT in ## Files → STOP, don't silently edit. Record in an `### Out-of-scope touches` block of the end-of-implementation report (file, why the step needed it, the change, whether it signals a plan/spec gap).
- **Hard off-limits (escalate before touching):** `writ/cli.py`; C11/C12/C16 probe-guard bodies; marker-consume predicate `probe == "usable"`; `KNOWN_SCHEMA_VERSIONS` value; `~/.cursor/hooks/writ-blast-gate.sh`; any `hooks.json`; `agent_village/scripts/hooks/install.sh`; post-init `codegraph index`; unlink/delete of `.codegraph/codegraph.db`; design §7 AST walk; `writ-doctor.sh`; piggyback `manifest.json` / Claude `settings.json`; `npm i -g @colbymchenry/codegraph`; write to `.codegraph/codegraph.db`; `CLAUDE.md` / `STATE.md`.
- **Escalate, don't improvise (verbatim — copy into the plan):** *If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*

## Rules Applied

No matching rules (no WRIT `PROJ-*` / `--- WRIT RULES ---` block in this dispatch). Binding MUSTs: spec C-01–C-12 + R15 + C1 ABSORB.

## Capabilities

- [ ] C1 — `_connect` first URI exact `file:{db}?mode=ro`; retry URI contains `immutable=1`; every connect `timeout=0`; locked DELETE: one connect, `'database is locked'`, retry did not fire
- [ ] C2 — `probe` junk / no-`schema_versions` / chmod 000 / lock → `"unreadable"`; absent → `"missing"`; version `9` still tuple; empty table still `"usable"`
- [ ] C3 — after fold, runtime wrap: every `bin/lib/` connect is `codegraph_index._connect`; URI ∈ the two pinned URIs; `report_for_file` symbols nonempty; `_c16_resolve_node` / `_c12_container` not None on the WAL fixture; no `-wal`/`-shm` after assert 4
- [ ] C4 — schema-less `freshness() == "unreadable"`; warm fresh cache + chmod 000 + restore mtime inside TTL → `"unreadable"` not `"fresh"`; unreadable never written to cache
- [ ] C5 — pytest HOOK: unreadable Write `permissionDecisionReason` **equals** HOW lock C sentence; contains `writ codegraph-init`; does not contain `unrecognized`, `Run the codegraph index`, ``Run `codegraph index` ``, or `stale`. No `diff -q` vs `~/.cursor/hooks/`
- [ ] C6 — unreadable → `PRE-UNREADABLE` DENY; unreadable + matching marker still DENY; PRE-INDEX / PRE-SCHEMA messages **equal** HOW lock C (PRE-SCHEMA formatted); belts: `writ codegraph-init`; no `Run the codegraph index`; PRE-SCHEMA no `Rebuild the index`. Existing `:1670` substring does not substitute
- [ ] C7 — fake init leaving junk: wrapper exit 1, marker survives, db file still exists, invocation log exactly one `init` and zero `index`. Missing-db / unrecognized messages **equal** HOW lock C. `test_unusable_index_leaves_marker` asserts exit 1
- [ ] C8 — `docs/adr/0001-unreadable-is-not-unrecognized.md` exists and states the four reasons (unreadable ≠ unrecognized; never delete; four vs five names; no `index` retry)
- [ ] C9 — one `def test_wal_and_lock_one_opener` holds asserts 1–4, 5a–5b, 6a–6d in order with runtime wrap + fresh recorded list per drive; live `writ codegraph-init` on real-init WAL: probe usable, marker consumed, exit 0
- [ ] C10 — piggyback TD-01 note present; **Status:** still OPEN; no plugin bus; no `.codegraph/ready`

## Implementation Order

`probe` calls `_connect` (same file). `freshness` calls `probe`. Blast-gate calls `freshness`. `check_predispatch` / C11/C12/C16 call `probe`. Wrapper prints `probe`. `report_for_file` → `nodes_in_file` → `blast_radius._connect`. `_c16_resolve_node` / `_c12_container` private opens until fold. Verbatim sites in ## Facts.

**Dependency table:**

| Step | Produces | Depends on | Why |
|---|---|---|---|
| 1 | `_connect` WAL fallback | none | spec comp 1; `probe` inherits |
| 2 | `probe` enum | 1 | connect-fail mapping only honest after retry |
| 3 | fold three openers | 1 | WAL readers need the helper |
| 4 | `freshness` pass-through | 2 | needs the word |
| 5 | blast-gate deny copy | 4 | verdict word |
| 6 | audit PRE-* | 2 | needs the word |
| 7 | wrapper exit 1 | 2 | prints kind |
| 8 | ADR | 2, 7 | records decisions |
| 9 | WAL+lock one-def + live wrapper | 1–7 | assert 4 needs fold |
| 10 | TD-01 note | 7 | describes wrapper |

**Parallel waves:** Wave A: Step 1. Wave B: Step 2. Wave C: Steps 3+4 sequential on `blast_radius.py` — run 3 then 4 (same file). After 2: Steps 5, 6, 7 disjoint. Wave D: Step 8 (after 2+7). Wave E: Step 9 (after 1–7). Wave F: Step 10 (after 7; piggyback file).
**Critical path:** 1 → 2 → 3 → 9. Solo linear: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10.

## Steps

### Step 1 — `_connect` WAL fallback
**Goal**: Spec component 1 — healthy WAL-no-shm init is readable; locked DELETE is not laundered to usable.
**Design** (imperative — decision already made, no design freedom): Rewrite `codegraph_index._connect` only. `path = _index_path(repo)`. `uri = f"file:{path}?mode=ro"` — this string is the first connect database argument (**equality**; no extra query keys). `con = sqlite3.connect(uri, uri=True, timeout=0)` (keyword `timeout=0`). `con.row_factory = sqlite3.Row`. `try: con.execute("SELECT 1"); return con`. `except sqlite3.OperationalError as e:` if `str(e) != "unable to open database file"`: `con.close(); raise`. Else `con.close()`; `uri2 = f"file:{path}?mode=ro&immutable=1"`; `con = sqlite3.connect(uri2, uri=True, timeout=0)`; Row factory; `con.execute("SELECT 1")`; return `con`. Any other `sqlite3.Error` (including `'database is locked'`) and a failing immutable ping **propagate**. Docstring: never lead with `immutable=1`. Do not change `probe` yet. Do not copy this retry into other files.
**Actions**: 1. In `tests/test_codegraph_index.py` **first** (TDD): (a) static: `_connect` source contains exactly two `sqlite3.connect(`; the second literal contains `immutable=1`; second connect is inside an `If` whose test compares against exact `'unable to open database file'`. (b) runtime on a **real** `codegraph init` WAL fixture (not `make_index`): wrap `sqlite3.connect` with `wraps=sqlite3.connect`; `recorded.clear()` then `_connect(repo)`; `recorded[0]` URI `== f"file:{db}?mode=ro"`; `recorded[1].uri` contains `immutable=1`; every resolved timeout is `0` (kwarg `timeout=0` **or** positional second arg `0`). (c) locked DELETE (`schema_versions={1,5}`, `BEGIN EXCLUSIVE` writer held, reader `timeout=0`): `_connect` raises `OperationalError` `'database is locked'`; recorder length exactly 1. If (c) takes ~5 s, production missed `timeout=0`. 2. Implement `_connect` as Design. 3. Run the test command.
**Files to modify**:
- `tests/test_codegraph_index.py` — `_connect` retry / lock / timeout pins (not the Step 9 combined def)
- `bin/lib/codegraph_index.py` — `_connect` body

<!-- plan-verify
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py::_connect
tier: A
qualifiers: grep-present "timeout=0" bin/lib/codegraph_index.py
qualifiers: grep-present "unable to open database file" bin/lib/codegraph_index.py
qualifiers: grep-present "immutable=1" bin/lib/codegraph_index.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_codegraph_index.py -q` pass. First URI equality. Lock: one connect.
**Do not regress**: `KNOWN_SCHEMA_VERSIONS = frozenset({1, 5})`. File-absent still first in `probe` (unchanged this step).
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 2 — `probe()` enum
**Goal**: Spec component 2 — file-exists-but-dead is `"unreadable"`.
**Design**: Keep `is_file()` → `"missing"` **first**. `_connect` raises `sqlite3.Error` → `"unreadable"` (today `"missing"`). `SELECT version FROM schema_versions` raises `sqlite3.Error` → `"unreadable"` (today empty-found tuple). Keep `finally: con.close()`. `found <= KNOWN_SCHEMA_VERSIONS` → `"usable"`. Else tuple unrecognized. Module docstring surface: `probe(repo) -> "usable" | "missing" | "unreadable" | ("unrecognized", found, known)`. No fifth `busy` name. Empty table stays `"usable"` (OQ-3).
**Actions**: 1. Add tests in `tests/test_codegraph_index.py` **first**: junk bytes → `"unreadable"`; sqlite without `schema_versions` → `"unreadable"`; `chmod 000` → `"unreadable"`; foreign version `9` still tuple; absent path still `"missing"`; junk + chmod 000 fail **both** URIs (`mode=ro` and `mode=ro&immutable=1`) as `"unreadable"` / raise (spec 9a/7). Keep `test_probe_usable_when_all_known`. 2. Edit `probe` as Design. 3. Run the test command.
**Files to modify**:
- `tests/test_codegraph_index.py` — unreadable fixtures
- `bin/lib/codegraph_index.py` — `probe` branches + docstring

<!-- plan-verify
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py::probe
tier: A
qualifiers: grep-present "unreadable" bin/lib/codegraph_index.py
qualifiers: grep-present "KNOWN_SCHEMA_VERSIONS = frozenset({1, 5})" bin/lib/codegraph_index.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_codegraph_index.py -q` pass.
**Do not regress**: unrecognized still names both sets. Empty `schema_versions` table still `"usable"`.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 3 — One opener fold
**Goal**: Spec component 3 — every `bin/lib/` index open goes through `codegraph_index._connect`.
**Design**: `blast_radius._connect` body becomes `return codegraph_index._connect(repo)` (sibling already imported). `_c16_resolve_node` and `_c12_container`: replace the private `sqlite3.connect(...)` with `con = codegraph_index._connect(repo)` (import sibling the same way `check_predispatch` does). Keep each function’s try/except and return contract (`None` / empty). **Copy the retry nowhere.** Do not extract `_shared`. Do not delete `blast_radius._index_path` (still used by `nodes_in_file` / `_db_mtime`).
**Actions**: 1. Add tests **first**: on a DELETE usable fixture (`make_index` OK here), `report_for_file` still returns a dict; `_c16_resolve_node` / `_c12_container` still return None on missing name / no container (contract unchanged). 2. Fold the three bodies as Design. 3. `rg sqlite3.connect bin/lib/` must show connect calls **only** inside `codegraph_index._connect` (two sites). 4. Run tests.
**Files to modify**:
- `bin/lib/blast_radius.py` — `_connect` delegates
- `bin/lib/artifact_claims.py` — `_c16_resolve_node` + `_c12_container` opener
- `tests/test_blast_radius.py` — smoke that fold still reads
- `tests/test_artifact_claims.py` — C16/C12 resolve still None-on-miss

<!-- plan-verify
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py::_connect
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py::_c16_resolve_node
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py::_c12_container
tier: A
qualifiers: grep-present "codegraph_index._connect" bin/lib/blast_radius.py
qualifiers: grep-present "codegraph_index._connect" bin/lib/artifact_claims.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_blast_radius.py tests/test_artifact_claims.py tests/test_codegraph_index.py -q` pass. `rg sqlite3.connect bin/lib/` only `codegraph_index.py`.
**Do not regress**: C11/C12/C16 `if probe != "usable": return []` **byte-unchanged**. Marker consume predicate **byte-unchanged**.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 4 — `freshness()` pass-through
**Goal**: Spec component 4 — gate sees `"unreadable"`; chmod/lock without mtime change cannot stay `"fresh"` inside TTL.
**Design**: In `freshness`, **always** `state = codegraph_index.probe(repo)` **before** any cache read. Then: `if state == "missing": return "missing"`; `if state == "unreadable": return "unreadable"`; `if state != "usable": return "unrecognized"`; then existing cache / stale arithmetic only (write path still only `"fresh"`). Docstring return: `"missing" | "unreadable" | "unrecognized" | "stale" | "fresh"`. Cache paragraph names `unreadable` in the never-cached list.
**Actions**: 1. Tests in `tests/test_blast_radius.py` **first**: schema-less db → `freshness() == "unreadable"` (not `"unrecognized"`). Warm `"fresh"` cache, `chmod 000` + restore mtime via `os.utime`, call inside TTL → `"unreadable"` not `"fresh"`. Unreadable never written to cache (`verdict_file` absent or not containing unreadable). Keep existing cache-refuses-missing/stale/unrecognized tests. 2. Edit `freshness` as Design. 3. Run tests.
**Files to modify**:
- `tests/test_blast_radius.py` — pass-through + cache-mask
- `bin/lib/blast_radius.py` — `freshness` order + docstring

<!-- plan-verify
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py::freshness
tier: B
qualifiers: grep-present "return \"unreadable\"" bin/lib/blast_radius.py
qualifiers: grep-present "FRESH_CACHE_TTL = 300" bin/lib/blast_radius.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_blast_radius.py -q` pass.
**Do not regress**: missing still `"missing"`; foreign version still `"unrecognized"`; fresh-only cache write.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 5 — Blast-gate deny copy (source only)
**Goal**: Spec component 5 — unreadable Writes denied with the specified sentence, not stale / unrecognized `{none}`.
**Design**: Edit `.claude/hooks/writ-blast-gate.sh` only. Header comment (`:6`) adds `unreadable`. After `if verdict == 'missing':` … `elif verdict == 'unrecognized':` … insert `elif verdict == 'unreadable': reason = (` HOW lock C unreadable sentence `)` **before** `else:  # stale`. Read WARN interpolates verdict — no new branch. Envelope keys unchanged. Do **not** edit `~/.cursor/hooks/writ-blast-gate.sh`. Do **not** edit `hooks.json`. Do **not** invoke `install.sh`.
**Actions**: 1. Tests in `tests/test_blast_gate_hook.py` **first** against `HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"`: code Write on unreadable fixture (junk or chmod 000 db under `.codegraph/` with a project marker) → `permissionDecisionReason` **equals** HOW lock C unreadable sentence; contains `writ codegraph-init` and `cannot be read`; does not contain `unrecognized`, ``Run `codegraph index` ``, `Run the codegraph index`, or `stale`. **No** `diff -q` against `~/.cursor/hooks/`. Keep missing/unrecognized/stale existing tests. 2. Edit `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh` as Design. 3. Run tests.
**Files to modify**:
- `tests/test_blast_gate_hook.py` — unreadable equality
- `.claude/hooks/writ-blast-gate.sh` — new elif + header

<!-- plan-verify
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh
tier: B
qualifiers: grep-present "cannot be read" .claude/hooks/writ-blast-gate.sh
qualifiers: grep-present "writ codegraph-init" .claude/hooks/writ-blast-gate.sh
qualifiers: grep-present "permissionDecision" .claude/hooks/writ-blast-gate.sh
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_blast_gate_hook.py -q` pass. Equality pin. No Cursor-copy Done-cell.
**Do not regress**: missing copy `:174-178` unchanged; unrecognized copy unchanged; envelope `permissionDecision: "deny"`.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 6 — Audit seat
**Goal**: Spec component 6 — unreadable cannot ride a greenfield marker; PRE-INDEX / PRE-SCHEMA no longer instruct `codegraph index`.
**Design**: Add `PRE_UNREADABLE = "PRE-UNREADABLE"  # index file present but unreadable` beside `PRE_INDEX`. In `check_predispatch`, after `probe = ...`, branch **before** `if probe == "missing"`: if `probe == "unreadable"`: append Finding `PRE_UNREADABLE` DENY HOW lock C PRE-UNREADABLE sentence. Keep `except Exception: probe = "missing"` **value**; comment becomes “module import failure → greenfield path”, **not** “unreadable == missing”. Replace PRE-INDEX and PRE-SCHEMA message strings with HOW lock C (PRE-SCHEMA still uses `sorted(found)` / `sorted(known)`). Docstring branch list grows the sixth. Do **not** edit `:1031` consume. Do **not** edit C11/C12/C16 guards.
**Actions**: 1. Tests in `tests/test_artifact_claims.py` **first**: unreadable index → `PRE_UNREADABLE` / `PRE-UNREADABLE` DENY and message **equals** HOW lock C. Unreadable **plus matching marker** still DENY (not proceed). Red audit still preserves marker. PRE-INDEX / PRE-SCHEMA messages **equal** the replacements (PRE-SCHEMA formatted with fixture version `99` vs `{1,5}`). Belts: contains `writ codegraph-init`; no `Run the codegraph index`; PRE-SCHEMA no `Rebuild the index`. Keep `:1670` `"index" in msg.lower()` — it does **not** substitute for equality. 2. Edit `check_predispatch` in `artifact_claims.py` as Design (add `PRE_UNREADABLE`). 3. Run tests.
**Files to modify**:
- `tests/test_artifact_claims.py` — PRE-UNREADABLE + equality
- `bin/lib/artifact_claims.py` — `PRE_UNREADABLE` + `check_predispatch`

<!-- plan-verify
new:   external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py::PRE_UNREADABLE
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py::check_predispatch
tier: A
qualifiers: grep-present "PRE-UNREADABLE" bin/lib/artifact_claims.py
qualifiers: grep-present "writ codegraph-init" bin/lib/artifact_claims.py
qualifiers: grep-absent "Run the codegraph index" bin/lib/artifact_claims.py
qualifiers: grep-absent "Rebuild the index" bin/lib/artifact_claims.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_artifact_claims.py -q` pass. Equality on all three PRE messages.
**Do not regress**: consume only `probe == "usable"`. Import-fail still `probe = "missing"`.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 7 — Wrapper honest exit
**Goal**: Spec component 7 — after `codegraph init`, still-not-usable is exit 1, marker left, db not deleted, `index` never invoked.
**Design**: Replace guard-2 block in `bin/writ-codegraph-init.sh` (`:165-175`). Probe once. Print **two** lines: `kind` then `detail` (`found=…;known=…` for unrecognized, empty otherwise). Parse kind as the first printed line (not JSON). `usable` → consume marker, exit 0 (unchanged messages). Else **no** `codegraph index`, **no** unlink: emit HOW lock C missing / unreadable / unrecognized stderr line (substitute `<db>` with the real db path) → exit 1. Guards 1/3/4 unchanged. Do not edit `writ/cli.py`.
**Actions**: 1. Update `test_unusable_index_leaves_marker` **first** from exit 0 → exit 1; assert db still exists; invocation log (fake that records argv) holds **exactly one** `init` and **zero** `index`. Add missing-db: exit 1 with the init-output sentence **equals** HOW lock C. Add unrecognized: exit 1 names both version sets **equals** HOW lock C (with fixture sets). Junk-db fake init: exit 1, marker survives, db file still exists. Happy path with `_make_usable_index` may stay for consume-on-usable — WAL happy path is Step 9. 2. Edit `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh` as Design. 3. Run tests.
**Files to modify**:
- `tests/test_writ_codegraph_init.py` — exit 1 + no-unlink + one `init`
- `bin/writ-codegraph-init.sh` — guard-2

<!-- plan-verify
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh
touch: external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py::test_unusable_index_leaves_marker
tier: A
qualifiers: grep-present "still unreadable" bin/writ-codegraph-init.sh
qualifiers: grep-present "exit 1" bin/writ-codegraph-init.sh
qualifiers: grep-absent "ast.walk" tests/test_writ_codegraph_init.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_writ_codegraph_init.py -q` pass. Exit 1. Db not deleted. Zero `index` in invocation log.
**Do not regress**: guards 1/3/4 messages. CLI passthrough (do not touch `writ/cli.py`).
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 8 — ADR
**Goal**: Spec component 8 — next session does not re-litigate the four names or auto-delete.
**Design**: Create directory `docs/adr/` in falkor-writ. Write `docs/adr/0001-unreadable-is-not-unrecognized.md` stating: (1) `unreadable` ≠ `unrecognized` (empty found-set is not a version claim); (2) writ never deletes (codegraph `init` owns unlink); (3) writ’s four names vs codegraph’s five (`busy` folds; `empty` is Bucket 5); (4) no `codegraph index` retry (C1-a). Record OQ-3 hole and OQ-2 fold as consequences, not as reopen.
**Actions**: 1. Create `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/docs/adr/0001-unreadable-is-not-unrecognized.md` with those four reasons. 2. Confirm `docs/adr/` did not already exist (A10).
**Files to modify**:
- `docs/adr/0001-unreadable-is-not-unrecognized.md` — create

<!-- plan-verify
new:   external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/docs/adr/0001-unreadable-is-not-unrecognized.md
tier: C
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] File exists in falkor-writ and states the four reasons (`grep -n unreadable docs/adr/0001-unreadable-is-not-unrecognized.md`).
**Do not regress**: do not invent `docs/adr/0001` if a file already exists (A10 said absent — STOP if present).
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 9 — WAL+lock one-def + C1 ABSORB pin + live wrapper
**Goal**: Spec component 9 — pins cannot green a lock-skipping `_connect`, a private `bin/lib/` opener, or a mixed recorder.
**Design**: Create `tests/test_connect_wal_lock.py` with **one** function `def test_wal_and_lock_one_opener`. WAL `db`/`repo` from **real `codegraph init`** in a temp git repo. Then, same function, locked DELETE db + `BEGIN EXCLUSIVE` writer **held open** through 5b. **No mutation of any kind between 5a and 5b** (no rebuild, chmod, unlink, rewrite). Forbidden WAL builders: `make_index`, `_make_usable_index`, `_index_usable`, copy-a-db-alone unless step 1 of the test asserts WAL header. Wrap the **real** `sqlite3.connect` (`unittest.mock.patch("sqlite3.connect", wraps=sqlite3.connect)`). Recorder captures `(uri, timeout, stack)`. A connect whose first `bin/lib/` frame is not `codegraph_index._connect` **fails**. Every such URI ∈ `{f"file:{db}?mode=ro", f"file:{db}?mode=ro&immutable=1"}`. **`recorded.clear()` or a new list immediately before each `_connect`/`probe` drive** that asserts a count. Do not implement an AST file walk. Order inside the one def: (1) `header[18:20] == b'\x02\x02'`. (2) `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` + `SELECT 1` raises `OperationalError` `unable to open database file`. (3) `probe(repo) == "usable"`; listing has no `-wal`/`-shm`. (4) Same repo: `report_for_file(...)["symbols"]` nonempty; `_c16_resolve_node` not `None`; `_c12_container` not `None`. **Re-list after 4:** still no sidecars. (5a) On locked DELETE (`schema_versions={1,5}`, writer held, reader `timeout=0`): plain `ro` execute → `str(e) == 'database is locked'`. (5b) Same fixture, writer still open, recorder reset: `codegraph_index._connect(repo)` raises `OperationalError` `'database is locked'` attributed to the **first** recorded connect; recorder length **exactly 1**; then `probe(repo) == "unreadable"`. (6a) static, `_connect` own source only: exactly two `sqlite3.connect(` call sites. (6b) runtime, WAL fixture, **fresh list**: exactly two recorded calls; `recorded[0].uri == f"file:{db}?mode=ro"`; `recorded[1].uri` contains `immutable=1`; every resolved timeout is 0. (6c) static: second call-site literal contains `immutable=1`. (6d) static: second connect inside `If` whose test compares against exact `'unable to open database file'`. Also add `test_live_init_wal_consumes_marker` in `tests/test_writ_codegraph_init.py`: real `writ-codegraph-init.sh` on a fixture built by real `codegraph init` (not `fake_codegraph` + DELETE). Expect probe `usable`, marker consumed, exit 0. Record observed `write_version`; if it is 1, the check does not count.
**Actions**: 1. Write `tests/test_connect_wal_lock.py` with `test_wal_and_lock_one_opener` as Design (TDD; will fail until Steps 1–3 hold — they should already). 2. Add `test_live_init_wal_consumes_marker` in `tests/test_writ_codegraph_init.py`. 3. Run the test command. Do not overwrite `~/.cursor/hooks/writ-blast-gate.sh`. Do not `ast.parse` / `ast.walk` the opener pin.
**Files to modify**:
- `tests/test_connect_wal_lock.py` — create; `test_wal_and_lock_one_opener`
- `tests/test_writ_codegraph_init.py` — live WAL wrapper happy path

<!-- plan-verify
new:   external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_connect_wal_lock.py::test_wal_and_lock_one_opener
new:   external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py::test_live_init_wal_consumes_marker
tier: A
qualifiers: grep-present "recorded.clear" tests/test_connect_wal_lock.py
qualifiers: grep-present "wraps=sqlite3.connect" tests/test_connect_wal_lock.py
qualifiers: grep-absent "ast.walk" tests/test_connect_wal_lock.py
qualifiers: grep-absent "ast.parse" tests/test_connect_wal_lock.py
qualifiers: byte-unchanged writ/cli.py
-->

**Test criteria**: - [ ] `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_connect_wal_lock.py tests/test_writ_codegraph_init.py -q` pass. One def. Fresh list per drive. No AST walk.
**Do not regress**: C1 ABSORB (runtime wrap). 5a/5b no mutation. chmod 000 is not 5a.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 10 — piggyback TD-01 note
**Goal**: Spec component 10 — TD-01 stays OPEN with an accurate repair story.
**Design**: In piggyback `docs/TECH_DEBT.md` TD-01, add a dated note that the wrapper deliberately does **not** run `codegraph index` and that Bucket 4 `codegraph init` is the repair (C-09 / C1-a). Replace the stale “Bucket 6 (writ wrapper runs `index`)” clause. **Status:** remains `OPEN`. No plugin bus. No `.codegraph/ready`.
**Actions**: 1. Edit `docs/TECH_DEBT.md` TD-01 as Design. 2. Confirm the heading still says `**Status:** OPEN`.
**Files to modify**:
- `docs/TECH_DEBT.md` — dated note; status OPEN

<!-- plan-verify
touch: docs/TECH_DEBT.md
tier: C
qualifiers: grep-present "does **not** run \`codegraph index\`" docs/TECH_DEBT.md
qualifiers: grep-present "**Status:** OPEN" docs/TECH_DEBT.md
-->

**Test criteria**: - [ ] `grep -n "Status: OPEN" docs/TECH_DEBT.md` shows TD-01 OPEN. Note names Bucket 4 `codegraph init` as the repair.
**Do not regress**: do not close TD-01; do not add plugin bus / `.codegraph/ready`.
**Report contract**: on done, report the literal test command run (copy-paste exact), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the unfenced last line `=== END REPORT ===`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

## E2E Done Criteria

**Prerequisites:** falkor-writ checkout; `codegraph` on PATH → `~/.codegraph/versions/v1.0.1`; Python 3.12; pytest. Not Cursor live deny (OQ-5.1). Not Claude plugin-cache (OQ-6).
**Walkthrough** (map to Capabilities):
1. `cd /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ && python3 -m pytest tests/test_codegraph_index.py tests/test_blast_radius.py tests/test_blast_gate_hook.py tests/test_artifact_claims.py tests/test_writ_codegraph_init.py tests/test_connect_wal_lock.py -q` → all pass → C1–C9.
2. Real-init WAL fixture: `header[18:20]==b'\x02\x02'`; `probe=="usable"`; wrap shows two URIs, first exact `file:{db}?mode=ro` → C1, C9.
3. Held `BEGIN EXCLUSIVE` DELETE: `_connect` raises `'database is locked'` with recorder length 1; `probe=="unreadable"` → C1, C2.
4. Hook pytest: unreadable Write reason **equals** HOW lock C sentence → C5.
5. Audit pytest: PRE-UNREADABLE / PRE-INDEX / PRE-SCHEMA equality; marker not consumed on unreadable → C6.
6. Wrapper junk: exit 1, db exists, one `init` zero `index` → C7.
7. `rg sqlite3.connect bin/lib/` only `codegraph_index.py` → C3.
8. piggyback `docs/TECH_DEBT.md` TD-01 still OPEN + no-index-retry note → C10.
**Done gate:** every line observed + matching, step tests passing. Live Cursor hook body may lag (OQ-5.2) — not a fail.

## Open Questions

- OQ-5.1 OPEN — Cursor deny envelope. Do not emit dual envelope. Do not claim Cursor blocks.
- OQ-6 OPEN — Claude cache refresh is operator, not a Done-cell.
- OQ-5.2 CLOSED 2-b — live `~/.cursor/hooks/writ-blast-gate.sh` copy is operator.
- OQ-2 / OQ-3 recorded — `busy` later; empty version table stays `usable`.
- TD-01 OPEN — no plugin bus; no `.codegraph/ready`.

## Out of Scope

Cursor live-hook body copy. Cursor deny envelope. Claude plugin-cache refresh. `busy`/`empty` as writ names. Empty `schema_versions` → still usable. `hooks.json` / `settings.json` / `install.sh --all/--only`. Write-gate auto-index. Change `KNOWN_SCHEMA_VERSIONS`. piggyback probe clone. MCP `tools/list`. Plugin bus. `.codegraph/ready`. Delete db from writ. Post-init `codegraph index`. `writ/cli.py`. `writ-doctor.sh`. C11/C12/C16 guards. Marker-consume predicate. Design §7 AST walk. Overwrite of `~/.cursor/hooks/writ-blast-gate.sh`.

## Gate co-satisfiability

One honest impl (HOW locks A–E) vs active gates:

| Gate | Honest impl |
|---|---|
| `grep-present "timeout=0"` `codegraph_index.py` | HOW lock A keyword |
| `grep-present "unable to open database file"` `_connect` | retry predicate |
| `grep-present "immutable=1"` `_connect` | retry URI only |
| `grep-present "unreadable"` `probe` | enum |
| `grep-present KNOWN_SCHEMA_VERSIONS = frozenset({1, 5})` | frozen; **no** grep-absent of the name |
| `grep-present codegraph_index._connect` blast_radius + artifact_claims | fold |
| `grep-present return "unreadable"` freshness | pass-through |
| `grep-present cannot be read` blast-gate | HOW lock C sentence |
| `grep-present permissionDecision` blast-gate | envelope kept |
| **no** `grep-absent stale` on blast-gate | else-stale branch stays — would fight |
| `grep-present PRE-UNREADABLE` + `writ codegraph-init` | audit |
| `grep-absent "Run the codegraph index"` `artifact_claims.py` | PRE-INDEX replacement; Actions mention the **old** string here only |
| `grep-absent "Rebuild the index"` `artifact_claims.py` | exact banned capitals; new copy has lowercase `rebuild the index` — **not** a fight |
| **no** `grep-absent "codegraph index"` wrapper | comments / “usable codegraph index” would fail |
| `grep-present still unreadable` + `exit 1` wrapper | HOW lock C |
| `grep-present recorded.clear` + `wraps=sqlite3.connect` | C1 ABSORB / M2 |
| `grep-absent ast.walk` / `ast.parse` WAL test | superseded AST |
| `byte-unchanged writ/cli.py` | CONSUMER-ONLY |
| `grep-present Status OPEN` TECH_DEBT | C-09 |
| **no** `new:` of a directory | ADR is a file path `external:` |
| **no** Done-cell mixing `new:` COLLISION + directory MISSING as exit 0 | all falkor-writ anchors are `external:` abs |

No red cells. `grep-absent stale` is **not** a gate. `grep-absent codegraph index` on the wrapper is **not** a gate.

## Claim sweep

First write — no amend markers. Swept this session: every `external:` `path:line` + quote in ## Facts, Implementation Order, and per-step Design/Actions against falkor-writ bodies + FCV live probes (2026-08-20). Extra FCV fact carried: freshness **cache-then-probe** today (M1); Step 4 flips the order. `test_artifact_claims.py:1670` substring is not an equality substitute.
