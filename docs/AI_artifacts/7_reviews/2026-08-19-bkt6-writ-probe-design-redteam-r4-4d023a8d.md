# Red-team r4 — Bucket 6 design (`2026-08-19-bkt6-writ-probe.md`)

_Reviewer:_ cursor-grok-4.6-high · _Mode:_ **cross-model** (design authored by claude-opus) · _Date:_ 2026-08-19
_NON-INTERACTIVE. Report-only. Fixes nothing._
_Cannot certify:_ this reviewer’s own model-specific quirks. Cross-model can catch opus-lineage blind spots; it cannot certify they are all caught. Closed r1 (unreadable→`codegraph index`), r2 C1/M2 (private openers / PRE-INDEX copy), and r3 C1/M1/M2 (WAL fixture bytes, noun-vs-command ban, OQ-5 entry) are not re-filed as the same IDs. This round attacks the **amend’s new gates**: the Cursor-twin “done when `install.sh copy_pair`” predicate, and the C-08 test that now bans only ``Run `codegraph index` ``.

Artifact: `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
Repo verified: `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` (on-disk source + live sqlite this session) and `/Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/install.sh`.
Contracts: falkor-writ `CLAUDE.md`; piggyback scope Bucket 6 freeze + OUT; grill `2026-08-19-bkt6-writ-probe-grill.md`.

## Steelman

A fourth plain-string `"unreadable"` is still the cheapest honest name: `!= "usable"` consumers stay fail-closed, `unrecognized` stays a real foreign version, and a smashed file can no longer ride a greenfield marker. Dropping the post-init `codegraph index` hop matches live evidence. The WAL `_connect` retry (plain `ro` first, `immutable=1` only on the exact `unable to open database file` ping) is the only way that fourth name does not also brand every healthy `codegraph init` as dead — live this session a checkpointed WAL file with no sidecars has `header[18:20] == b'\x02\x02'`, `mode=ro` ping raises that exact OperationalError, and `immutable=1` reads `{1,5}` without creating a sidecar. Folding every production `sqlite3.connect(` under `bin/lib/` onto that helper, probing before the freshness cache, and pinning WAL asserts 1–2 *before* `usable` are the right closures of r2/r3. That is the strongest honest case. It still makes the Cursor-twin refresh both mandatory and unsatisfiable, and it still pins C-08 with a ban string the leftover PRE-INDEX imperative does not contain.

## Verdict

**rethink** — 1 CRITICAL, 1 MAJOR. Do not spec “refresh the Cursor twin through `install.sh copy_pair`” as a done-cell. Do not ship the C-08 / PRE-INDEX tests as a ban on ``Run `codegraph index` ``.

---

## CRITICAL

### C1. The Cursor-twin done-cell is unsatisfiable: grill forbids a `hooks.json` edit, §3 forbids a one-file copy, and the named copier is not a command — the real invocations either rewrite live `~/.cursor/hooks.json` or reinstall every Village hook.

Where: Chosen Approach §3 “Same step, second file”; Surface-capability matrix note (a); Dual-predicate row “three split messages vs same strings on Claude and Cursor”; OQ-5.2; grill R15 / “No settings/hooks.json edit”
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): An honest worker cannot finish the blast-gate step. Guessing `install.sh --all` rewires every Cursor hook on this machine (the installer itself documents that as a 2026-08-09 live incident). Skipping the refresh — every named pytest still greens, because they run the falkor-writ source script — leaves Cursor on the pre-fix three-branch copy, so `freshness() == "unreadable"` falls into `else: stale` (pre-mortem #1, on the harness this session is). Hand-copying the one file, the only move that would not touch `hooks.json`, is banned by the same paragraph.

Evidence:

Grill (`2026-08-19-bkt6-writ-probe-grill.md` Shape + R15):

> One contract surface: `probe()` + its four consumers. **No settings/hooks.json edit.**
> Deny copy is command text, not a Claude-only hook event.

Design §3:

> The step is not done until the copy is refreshed through the **one** supported path — `agent_village/scripts/hooks/install.sh` `copy_pair` (manifest row `writ-blast-gate`) — and a `diff` between the two files is silent.
> Do **not** hand-patch the copy as a separate edit — two diverging hand-edits is the drift this note exists to prevent.

OQ-5.2 (same artifact, still OPEN):

> Open: whether the plan's step invokes `install.sh` directly or whether the manifest row needs its own refresh entry.

`copy_pair` is a bash function, not argv. Bare `install.sh` aborts. `--all` is the blast. `--only` writes `hooks.json`:

`agent_village/scripts/hooks/install.sh:50-75, 132-143`:

> What this does: wires Agent Village's Cursor hook scripts into a hooks.json (default ~/.cursor/hooks.json) and copies the script bodies next to it.
> Bare `install.sh` aborts (2026-08-09):
> `--only <id>…` install/replace ONLY those manifest ids
> `--all` full Village reinstall: strip all Village markers, emit every non-declined manifest row (intentional blast; use rarely)
> Bare install strips every Village-owned hook and re-emits the whole manifest. That is how failClosed / Shell blockers landed by accident (2026-08-09).

Writ-sourced copy is from `WRIT_REPO_ROOT` (the pin at `~/.config/agent-village/writ-root`), not from “the worktree you just edited” (`install.sh:407, 815`).

Blast-gate pytest runs the **source** script only: `falkor-writ/tests/test_blast_gate_hook.py:33` `HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"`. No test touches `~/.cursor/hooks/writ-blast-gate.sh`.

Deny strings live in the hook script’s Python heredoc (`writ-blast-gate.sh:174-202`), not in `blast_radius.py`. A falkor-writ code change updates Claude immediately; Cursor keeps the old three-branch copy until the file bytes move. Unreadable then hits `else:  # stale` at `:196`.

Simulation (honest §3 prose, every real invocation):

1. Implement enum + deny branch in `.claude/hooks/writ-blast-gate.sh`. All §7 pytest green (they exec `HOOK = REPO / .claude / hooks / …`).
2. “Refresh through `install.sh copy_pair`”:
   - `bash install.sh copy_pair` → exit 2 `unknown argument` (`install.sh:117-120`).
   - `bash install.sh` → exit 2, the 2026-08-09 abort.
   - `bash install.sh --all` → strips every Village marker and re-emits the whole manifest into live `~/.cursor/hooks.json` (installer’s own incident class).
   - `bash install.sh --only writ-blast-gate` → copies from `WRIT_REPO_ROOT` **and writes `hooks.json`**, which the grill froze out of this bucket.
   - `install -m 0755 .claude/hooks/writ-blast-gate.sh ~/.cursor/hooks/writ-blast-gate.sh` → the one-file copy that would satisfy `diff` silent without touching `hooks.json`. §3 forbids it.
3. Skip the refresh. Cursor copy still has three branches. After `freshness()` grows `"unreadable"`, Cursor deny reason contains `stale`. Claude’s new test does not see that file.

Simpler design that removes the problem: the done-cell is `diff -q falkor-writ/.claude/hooks/writ-blast-gate.sh ~/.cursor/hooks/writ-blast-gate.sh` after a one-file `install -m 0755` of that script only. Do not invoke `install.sh`. Close OQ-5.2 as “copy the body; do not re-emit `hooks.json`.” Envelope remain OQ-5.1.

Check:

```
# copy_pair is not a command:
bash /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/install.sh copy_pair ; echo exit=$?
# usage / abort:
sed -n '50,75p;132,143p;771,784p;805,816p' /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/install.sh
# pytest never sees the Cursor copy:
sed -n '32,33p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py
# unreadable falls into else stale in the live three-branch copy:
sed -n '174,202p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh
```

Human-authority: requiring a live-machine Village installer run against `~/.cursor/hooks.json` is operating burden (domain 3) and a security-posture rewrite of hook wiring (domain 5). The artifact decides it in §3 while OQ-5.2 still calls it open. A subagent cannot close that; the design did.

---

## MAJOR

### M1. The C-08 copy tests ban a string the leftover PRE-INDEX/PRE-SCHEMA text never contains. Adding `writ codegraph-init` beside `Run the codegraph index` greens every named assert and still instructs `codegraph index`.

Where: Constraints C-08; Chosen Approach §4 PRE-INDEX/PRE-SCHEMA rewrite; §7 “PRE-INDEX / PRE-SCHEMA copy test”; bad-faith table row “blast-gate ban / PRE-INDEX copy”
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): After this ships, a missing index can still tell the operator (and the agent) to “Run the codegraph index” — the command C1-a and C-08 exist to stop recommending. Dispatch still names `writ codegraph-init` too, so the new tests pass. The r2 leftover that r3 tried to close with a command-shaped ban survives because the ban is the backticked form, and the live sentence is the un-backticked imperative.

Evidence:

Live PRE-INDEX (`falkor-writ/bin/lib/artifact_claims.py:987-989`):

> "No codegraph index for this repo. Run the codegraph index "
> "before dispatch, or mark the repo greenfield "

C-08 (design):

> No message instructs the operator to run `codegraph index` — i.e. the literal command string ``Run `codegraph index` `` (and any other imperative form of it)

§7 named test (the only pytest pin for that rewrite):

> both findings' messages contain `writ codegraph-init` and do **not** contain the command string ``Run `codegraph index` ``
> Note the existing PRE-INDEX assertion at `test_artifact_claims.py:1670` is `"index" in msg.lower()` — it passes either way and does **not** substitute for this test.

Live this session (Python, exact strings):

```
LIVE PRE-INDEX
  writ codegraph-init False
  ban Run `codegraph index` False
  imperative Run the codegraph index True
  C-08 tests pass? False          # must add the token

GAMED PRE-INDEX  (keep old imperative, insert Run `writ codegraph-init`)
  writ codegraph-init True
  ban Run `codegraph index` False
  imperative Run the codegraph index True
  C-08 tests pass? True           # leftover instruction intact

SPECIFIED replacement (design §4)
  writ codegraph-init True
  ban Run `codegraph index` False
  imperative Run the codegraph index False
  C-08 tests pass? True           # honest path also passes
```

Existing pin `test_artifact_claims.py:1670` `"index" in msg.lower()` matches gamed, specified, and live.

PRE-SCHEMA live (`artifact_claims.py:1002-1004`) has no backticked command either: `"Rebuild the index at a known schema version."` Appending `Run \`writ codegraph-init\`…` greens the same test without deleting “Rebuild the index”.

Simulation (bad-faith reading of the new gate, equal cost to good-faith):

1. In `check_predispatch`, insert `Run \`writ codegraph-init\`` into the existing PRE-INDEX / PRE-SCHEMA strings. Do not delete `Run the codegraph index` / `Rebuild the index`.
2. Named §7 test: contains `writ codegraph-init` ✓; ``Run `codegraph index` `` not in message ✓.
3. `:1670` `"index" in msg.lower()` ✓.
4. Operator following PRE-INDEX still runs `codegraph index` (C1-a: junk → `Failed to index: file is not a database`, exit 1).

Simpler design that removes the problem: assert the specified sentences (or ban the live leftover `Run the codegraph index` as an imperative, not the two-word noun and not only the backticked command). Exact-string (or “does not contain `Run the codegraph index`”) is the discriminator the r3 noun exception still needs.

Check:

```
python3 - <<'PY'
pre = ("No codegraph index for this repo. Run the codegraph index "
       "before dispatch, or mark the repo greenfield ")
gamed = pre.replace("or mark", "Run `writ codegraph-init` before dispatch, or mark")
ban = "Run `codegraph index`"
print('live ban', ban in pre, 'gamed token', 'writ codegraph-init' in gamed,
      'gamed ban', ban in gamed, 'gamed leftover', 'Run the codegraph index' in gamed)
PY
sed -n '986,1005p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py
sed -n '1665,1671p' /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_artifact_claims.py
```

---

## Six audits (index)

1. **Fact & arithmetic.** Consumer-table line refs (`codegraph_index.py:63-79`, `blast_radius.py:285-289`, `artifact_claims.py:975-1031, 2166-2168, 2488-2490`, `writ-codegraph-init.sh:165-175`, `writ-doctor.sh:367`) match on-disk. `sqlite3.connect(` under `bin/lib/` is still exactly the four sites the design lists. WAL error string this session is exactly `unable to open database file` (junk is `file is not a database`; chmod 000 is the same CANTOPEN string on both URIs). No number to recompute was wrong. The false fact is the copier name (`install.sh copy_pair` is not a command) — C1.
2. **Internal consistency.** Grill “no hooks.json edit” vs §3 “refresh via install.sh” vs OQ-5.2 “path still open” vs “do not hand-patch” — C1. C-08 “any other imperative form” vs §7 ban of only the backticked command — M1. Dual-predicate table claims the Cursor-string pair has “no fight”; the fight is the refresh path, not the strings.
3. **Gaming simulation.** Transcripts under C1 and M1. Both bad-faith readings pass as easily as good-faith; both named pytest sets stay green.
4. **Assumption feasibility.** `_connect` WAL retry, `immutable=1`, junk/chmod error strings, Cursor wiring at `~/.cursor/hooks.json:84-86`, byte-identical copy, `CURSOR-KNOWLEDGE.md:246-255` nested-envelope note — all hold. Assumed-but-absent: an `install.sh copy_pair` subcommand (C1). `codegraph init` on chmod 000 is still unclassified errcode 14 (`directory.ts:155-156`) and refuses — the design’s “CLI cannot repair chmod 000” claim holds.
5. **Contract compliance.** Grill one-surface + no `hooks.json` edit broken by the Cursor-twin done-cell (C1). C1-a / C-08 intent broken by the leftover PRE-INDEX imperative the new test cannot see (M1). OUT list (auto-index, `KNOWN_SCHEMA_VERSIONS`, piggyback probe clone, MCP, plugin bus, `.codegraph/ready`) is not reopened. OQ-4 A is craft the grill allowed; leftover-WAL + `immutable=1` did **not** verify as a stale-usable retry path this session (plain `ro` still succeeded when a `-wal` file was present).
6. **Missing-by-construction.** The author’s position (OQ-5 is the residual Cursor MAJOR; C-08 ban is now command-shaped) hides that §3 still *decides* a copier OQ-5.2 calls open, and that the command-shaped ban does not match the live leftover sentence. Pytest-on-source hides Cursor drift.

Mode: **cross-model** (opus design, grok 4.6 reviewer). Certifies craft against this repo and these contracts. Cannot certify shared-judgment misses both lineages share.
