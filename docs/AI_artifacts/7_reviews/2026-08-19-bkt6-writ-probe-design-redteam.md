# Red-team — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own model-specific quirks. Cross-model can catch shared-lineage blind spots; it cannot certify they are all caught.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk source this session).
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

A fourth plain-string probe state is the cheapest way to stop two sqlite failures from borrowing the names of two other failures. Callers that already ask `== "usable"` stay fail-closed without a rewrite; `unrecognized` stays a real foreign version (tuple intact); the greenfield marker stays unreachable from the new name. Gating the wrapper retry on “file exists” matches the live `codegraph index` refusal when the db is absent. Never deleting the db from writ is the right ownership split if codegraph `init` is the only sanctioned unlink. That is the strongest honest case. It still fails the live repair path and the live deny copy.

## Verdict

**rethink** — 1 CRITICAL, 3 MAJOR. Do not spec/plan the unreadable→`codegraph index` routing or the post-init retry as written.

---

## CRITICAL

### C1. Unreadable is routed to `codegraph index`; that command cannot repair the bucket’s own fixtures. Init can. The wrapper retry never runs on the cases the design says it covers.

Where: Chosen Approach §§3–5 (deny copy, `PRE-UNREADABLE`, wrapper retry); Implications “retry’s real remaining value is the `busy`/`unclassified` refusals”; C-08; grill lock 7 / lock 1-a
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): After this ships, a smashed index still blocks every code write. The new honest sentence tells the operator (and the agent) to run a command that prints `Failed to index` and leaves the file dead. The command that actually rebuilds it (`codegraph init` / `writ codegraph-init`) is the one the split messages *stop* recommending for this state. The “one retry” does not fire when init already refused.

Evidence:

Design (deny copy / audit / wrapper):

> `unreadable` (new): "… Run `codegraph index` to rebuild it, then retry the write."
> `PRE-UNREADABLE` … "Run `codegraph index` to rebuild it before dispatch."
> otherwise (`unreadable` / `unrecognized`) → run **exactly once**: `codegraph index "$INIT_PATH_ABS"`
> “The retry's real remaining value is the `busy`/`unclassified` refusals, where init deliberately touches nothing”

Live, this session, against the design’s own two collapse fixtures:

```
junk-bytes db + `codegraph index`  → exit 1  “Failed to index: file is not a database”
junk-bytes db + `codegraph init`   → exit 0  (Bucket 4 unlink + re-init + index; tables present)
schema-less sqlite + `codegraph index` → exit 1  “Failed to index: no such table: unresolved_refs”
chmod 000 db + `codegraph index`  → exit 1  “unable to open database file”
chmod 000 db + `codegraph init`   → exit 1  “Cannot repair index (errcode 14)”
```

`codegraph index` treats file-exists as initialized (`codegraph/src/directory.ts:93-101` `isInitialized` = `codegraph.db` exists) then `CodeGraph.open` (`codegraph/src/bin/codegraph.ts:749-756`). It never calls `unlinkUnreadableIndex`. Unlink lives only on `init`’s `health.status === 'unreadable'` branch (`codegraph.ts:628-632`). Errcode 14 (chmod/cantopen) is `unclassified` (`directory.ts:155-156`), which `init` refuses (`codegraph.ts:622-626`) — and the wrapper then exits at guard 1:

```
codegraph init "$@" || EXIT_CODE=$?
if [ "$EXIT_CODE" -ne 0 ]; then
    … exit "$EXIT_CODE"     # bin/writ-codegraph-init.sh:128-131
fi
```

`busy` and `unclassified` are exactly those exit-1 init paths. Retry is unreachable there. When init *succeeds* on junk (Bucket 4), probe is already `usable` and retry is skipped. So the locked “one `codegraph index` try after init” is dead for unreadable on both the new binary (init already repaired) and the old/junk path (index cannot open the file; writ must not delete it — C1).

Simulation (bad-faith executor, also the honest operator following C-08):

1. Write denied; reason says run `codegraph index`.
2. Run it on junk → exit 1, file unchanged.
3. Retry the write → denied again. Loop the grill’s lock 6 was written to break, with new wording.

Simpler design that removes the problem: keep the fourth name (needed so a greenfield marker cannot launder a dead db). Point unreadable deny/audit at `writ codegraph-init` (the command that unlinks). Drop the post-init `index` retry, or keep it only for `unrecognized` (open+clear+rebuild can actually change a foreign schema). That fights grill lock 7 / 1-a — which is why this is rethink, not a spec-fix.

Check:

```
T=$(mktemp -d); cd "$T"; git init -q .; mkdir -p .codegraph
printf 'junk' > .codegraph/codegraph.db
codegraph index "$T"; echo index_exit=$?
printf 'junk' > .codegraph/codegraph.db
codegraph init "$T"; echo init_exit=$?
sed -n '128,131p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh
```

---

## MAJOR

### M1. Freshness cache returns `"fresh"` without probing when mtime is unchanged — C-04 fail-closed is false for 300s on the design’s own `chmod 000` fixture.

Where: Implications “The freshness cache cannot go sticky on the new state”; Assumptions #5; C-04; `bin/lib/blast_radius.py:270-289`; `FRESH_CACHE_TTL = 300` at `:69`
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): For five minutes after a healthy check, a db that becomes unreadable without a content write (permissions, lock) still looks “fresh.” Code writes go through. The new `unreadable` branch never runs. The named test (“unreadable is never cached”) only covers not *writing* that word into the cache file.

Evidence:

Cache is checked **before** `probe()` (`blast_radius.py:270-281`): hit requires `verdict == "fresh"` and `db_mtime == _db_mtime(repo)`. `chmod` does not change mtime.

Reproduced this session:

```
chmod mtime before=1000000000.0 after=1000000000.0 changed=False
freshness usable → fresh  (cache written)
chmod 000 on db; mtime unchanged
probe after chmod → missing   (today; would be unreadable after the enum rename)
freshness after chmod → fresh
```

Design claim this contradicts: “`unreadable` therefore inherits the existing never-cached policy with no code change” and the existing docstring “it never masks a state change (db mtime is re-read on every call).” Re-reading an unchanged mtime is not a state check.

Simulation: (1) Write once while fresh → cache written. (2) Smash via `chmod 000` (the live Claim 1 fixture). (3) Next Write inside 300s: cache hit, skip probe, allow. All of §7’s named tests still pass: they build a fixture without a warm `fresh` cache.

C-04 freeze: “unreadable is never treated as usable; edits stay denied.” The gate’s usable-equivalent is `freshness() == "fresh"`.

Check:

```
python3 - <<'PY'
# see session transcript: chmod mtime unchanged; freshness stays 'fresh'
import os, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib")
import blast_radius, codegraph_index
repo = Path(tempfile.mkdtemp()) / "repo"; repo.mkdir()
idx = repo / ".codegraph"; idx.mkdir()
db = idx / "codegraph.db"
con = sqlite3.connect(db)
con.execute("CREATE TABLE schema_versions(version INTEGER PRIMARY KEY, updated_at INTEGER, description TEXT)")
con.execute("INSERT INTO schema_versions(version, updated_at, description) VALUES (1,0,'v1')")
con.commit(); con.close()
blast_radius.stale_index_days = 99999
print("before", blast_radius.freshness(repo))
os.chmod(db, 0)
print("probe", codegraph_index.probe(repo))
print("after", blast_radius.freshness(repo))
PY
```

---

### M2. Live deny copy is not the falkor-writ source. Named refresh path (`writ-doctor`) does not copy. Real copier edits `hooks.json`, which this grill forbade.

Where: Surface-capability matrix notes (a)(b); Chosen Approach §3 “Same step, second file — the Cursor twin”; grill “No settings/hooks.json edit”; R15; C-04 harness scope
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): Tests and the repo hook go green on the new three-way copy. Cursor (and Claude Code) keep denying with the *old* “unknown schema / stale” wording until a copy step that this design either names wrongly or that rewrites `~/.cursor/hooks.json`. Twin drift is the failure mode the matrix itself predicts.

Evidence:

Verified this session:

- `diff` silent: `falkor-writ/.claude/hooks/writ-blast-gate.sh` ↔ `~/.cursor/hooks/writ-blast-gate.sh` (copy dated 2026-08-19 11:23, **not a symlink**).
- `~/.cursor/hooks.json` `preToolUse` matcher `Write`, `failClosed: true`, command = that copy. Matches the matrix.
- Claude live body is a **third** non-symlink copy: `~/.claude/plugins/cache/writ/writ/1.6.1/.claude/hooks/writ-blast-gate.sh` (`diff` silent vs source today; `hooks/hooks.json` runs `${CLAUDE_PLUGIN_ROOT}/…`). falkor-writ `CLAUDE.md` Critical Rules: “`git pull` alone updates NOTHING that runs… `bin/writ-refresh-plugin-cache.sh`.” The design never names this copy.
- `rg blast-gate bin/writ-doctor.sh` → only the freshness *display* at line 367. No `cp`. `bin/` and `scripts/` in falkor-writ have **zero** install of this hook.
- Actual copier: `agent_village/scripts/hooks/install.sh` `copy_pair` from `$WRIT_REPO_ROOT/.claude/hooks/writ-blast-gate.sh` into `$HOME/.cursor/hooks/` (manifest row `writ-blast-gate`). Default `--target` is `$HOME/.cursor/hooks.json` and the script **writes** that file (header lines 54–55, 65, 155). Grill: “No settings/hooks.json edit.”

Design: “refreshed through the supported path (`writ-doctor` / the install script that placed it)” and “Do **not** hand-patch the copy.” Both allowed paths are therefore either fictional (writ-doctor) or a forbidden hooks.json edit (av install.sh), or an unnamed Claude cache refresh + session restart (operating burden, never asked).

Simulation: implementer edits only falkor-writ source + tests (code-home per R5-a). Cursor twin unchanged. Pre-mortem #1’s “stale” swallow is exactly what the twin still does.

Check:

```
diff -q ~/.cursor/hooks/writ-blast-gate.sh \
  /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh
diff -q ~/.claude/plugins/cache/writ/writ/1.6.1/.claude/hooks/writ-blast-gate.sh \
  /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh
rg -n 'blast-gate|cursor/hooks' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-doctor.sh
rg -n 'writ-blast-gate' /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/manifest.json /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/install.sh
```

Human-authority: operating burden of “refresh the twin / restart Claude” is assumed, not asked. Grill forbade the install path that actually does it.

---

### M3. Chosen Approach implements OQ-1-A (skip `index` on `missing`) as if frozen, while declaring OQ-1 a plan blocker. That narrows grill lock 5 / shape item 5 without an owner answer.

Where: Summary “retry gated on the db file existing”; Chosen Approach §5 step 3; Dual-predicate table row 2; OQ-1; grill shape item 5 and lock 1-a
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): Spec/plan will inherit “no retry when the file is absent” as settled. The grill text still says: after init, if probe ≠ usable, run `codegraph index` once. A later compliance review will either fail the plan for narrowing a freeze, or the freeze silently moves.

Evidence:

Grill (LOCKED): “`writ codegraph-init` still runs `codegraph init`, then if probe ≠ usable runs **`codegraph index` once** and re-probes.”
Grill: “Open questions remaining: **None** for this grill.”
Design OQ-1: “Does the retry skip the `missing` state? (narrows lock 5) — *blocker for the plan's wrapper step.*”
Design Chosen: `kind == missing` → **no retry**. Dual-predicate table marks that pair as a **yes** fight, then adopts the narrowing.

C1 above makes skip-on-missing *empirically* right (`index` also refuses with no db). That does not make it a closed owner lock. Human-authority: scope freeze change, recorded as OPEN and simultaneously as Chosen.

Check: quote grill shape item 5 vs design Chosen Approach §5 steps 3–4 vs OQ-1 first sentence.

---

## Gate matrix (audits 2–3, highest-stakes pairs)

| Pair | Result |
|---|---|
| C-08 unreadable → `codegraph index` vs live `index` on junk/schema-less | **red** → C1 |
| “retry covers busy/unclassified” vs wrapper guard 1 exit on init ≠ 0 | **red** → C1 |
| C-04 unreadable never usable vs freshness cache-before-probe | **red** → M1 |
| “same strings on Claude and Cursor (one script)” vs user-level + plugin-cache copies | **red** → M2 |
| lock 5 probe ≠ usable → index vs Chosen skip on missing | **red** → M3 |
| PRE-UNREADABLE before missing vs marker-match proceed | **green** (branch order as specified does close the launder) |
| consume only on `usable` vs wider enum | **green** |
| C1 never delete db | **green** (no unlink in writ; chmod-000 then has **no** in-scope repair — leftover of C1) |

## Human-authority

Silent: operating burden of copy-refresh + Claude restart (M2). OQ-1 freeze narrowing treated as chosen (M3). Cache TTL 300s is pre-existing, not newly assumed. Cursor deny-envelope left unverified — correctly not claimed.

## Mode

Cross-model (opus design / grok 4.6 review). Certifies craft + this lineage’s attack on repair-routing and copy-drift. Does not certify a third lineage would agree on severity.

**Verdict: rethink.**
