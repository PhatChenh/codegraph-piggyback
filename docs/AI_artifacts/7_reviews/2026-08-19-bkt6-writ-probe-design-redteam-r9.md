# Red-team r9 — Bucket 6 design (amend: last-patch gates)

_Date:_ 2026-08-20
_Mode:_ **cross-model** (design continuation was syn-2-kimi-k3; reviewer is cursor-grok-4.6-high). Craft errors in the r8 pin text can be certified; shared-lineage judgment of “AST is enough” cannot.
_Artifact:_ `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md`
_Repo verified:_ `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`
_SQLite this run:_ 3.51.0 (same as the artifact’s cited session)
_Scope of this round:_ last patch’s new gates — equality 6b; `_connect`-observed 5b; `vfs=unix-none` matrix row; AST one-opener; OQ-5.2 OPEN. Earlier closed IDs were not re-litigated except where the r8 text still contradicts itself.

## Steelman

The chosen shape is the honest one: a four-word probe, WAL-without-`-shm` recovered by one exact-string retry, a locked DELETE db left `unreadable`, and every other `bin/lib/` opener deleted so the fallback cannot be copied. Equality on the first recorded URI (`recorded[0].uri == f"file:{db}?mode=ro"`) is the right answer to SQLite URI §3.3 — `immutable`, `nolock`, and `vfs=NAME` are not a two-token list, they are an open set of lock-skips — and binding 5b to `_connect` actually observing `'database is locked'` on the first recorded attempt is the right answer to a dead first connect that greened every source/URI pin. Re-opening OQ-5.2 (overwrite of the live `~/.cursor/hooks/` file) is the right human-authority move. The rest of this report attacks that version, not a weaker one.

## Executive summary

Equality 6b and `_connect`-observed 5b **hold** on `_connect` itself (live: locked DELETE is `'database is locked'` under plain `ro`, rows under `immutable=1` / `nolock=1` / `vfs=unix-none` / **`vfs=unix-dotfile`**; real `codegraph init` WAL still needs the retry even over `unix-none`). The r8 AST one-opener pin **does not do what it claims**: the specified walk misses `import sqlite3 as sq` / `sqlite3.dbapi2.connect` / `getattr(sqlite3, "connect")`, and a private `immutable=1` opener in C12/C16 greens the pin, assert 4, and the post-4 listing. OQ-5.2 is labeled OPEN but Option A / the surface matrix / the dual-predicate table still treat the live Cursor copy as a required Done-cell. **Verdict: revise.**

CRITICAL: 1 · MAJOR: 2 · MINOR: omitted from the return (none load-bearing on the r8 gates beyond the two Majors)

---

## Findings

### C1 — Specified AST one-opener walk greens a private `immutable=1` opener

```
Where: artifact §7 “One-opener tests” / “The guard is an ast walk, not a grep” (design ~922–953) + bad-faith table row “one-opener guard” (~1005)
Severity: CRITICAL
Confidence: VERIFIED
Impact (plain language): The test that is supposed to prove “exactly one door into the index” will pass while C12/C16 (and any other `bin/lib/` reader) keep their own key — and that key skips locks. After merge, a later `_connect` fix does not reach those readers; a locked or WAL index can still be read through the side door. The pin is the only enforcement named for “delete the duplicate open, don’t copy the fix.”
Evidence:
  Artifact claim (design ~945–948): “A private C12/C16/blast opener **fails the AST pin in every form**: renamed `import sqlite3 as sq`, `from sqlite3 import connect`, RW `connect(str(db))`, or an aliased private `immutable=1` (which creates no sidecars and would also slip a listing-only check — the AST is the door that stays shut; **private `immutable=1` via alias must fail this pin by construction**).”
  Specified walk (design ~938–941), quoted: count a `Call` whose `func` is `Attribute(attr == 'connect', value == Name('sqlite3'))`, AND any `Call` whose `func` is a `Name` bound by `from sqlite3 import connect` (`ImportFrom(module == 'sqlite3')`).
  That walk does **not** mention `Import` aliases (`import sqlite3 as sq` → `sq.connect`), `sqlite3.dbapi2.connect`, `getattr(sqlite3, "connect")`, a bound local (`opener = sqlite3.connect; opener(...)`), or `from sqlite3.dbapi2 import connect`.
  Live this session, implementing that walk literally:

    plain            hits=[('sqlite3.connect', 2)]
    alias_import     hits=NONE
    dbapi2           hits=NONE
    getattr          hits=NONE
    bound            hits=NONE
    from_dbapi2      hits=NONE
    from_import      hits=[('imported connect as connect', 2)]  # the one extra form they did add

  `sqlite3.connect is sqlite3.dbapi2.connect` → True (same function).
  Lazy production (honest `_connect` in `codegraph_index.py`; C12/C16 rewritten to):

    import sqlite3 as sq
    sq.connect(f"file:{db}?mode=ro&immutable=1", uri=True, timeout=0)

  Specified walk on that trio: counted connects live in **exactly one file**, `codegraph_index.py`. Pin greens.
  Same opener on a `BEGIN EXCLUSIVE` DELETE db this session: `[(1,), (5,)]` — lock skipped. Real `codegraph init` WAL: `immutable=1` reads, no `-wal`/`-shm` created → assert 4 + post-assert-4 listing also green.
  Today’s real openers are still the four `sqlite3.connect(` sites the design lists (`codegraph_index.py:48`, `blast_radius.py:135`, `artifact_claims.py:2166`, `artifact_claims.py:2488`) — folding them is the point of the pin; the pin as specified does not hold that fold.
  Bad-faith table row ~1005 is still the *grep* form (`sqlite3.connect(` count == 1) vs `sqlite3.connect(str(path))`. A worker who implements the table, not the body, also greens `from sqlite3 import connect` — the hole r8 said it closed.
Check:
  python3 -c '
  import ast, textwrap
  def walk(src):
      t=ast.parse(src); imported=set()
      for n in ast.walk(t):
          if isinstance(n, ast.ImportFrom) and n.module=="sqlite3":
              for a in n.names:
                  if a.name=="connect": imported.add(a.asname or "connect")
      hits=[]
      for n in ast.walk(t):
          if not isinstance(n, ast.Call): continue
          f=n.func
          if isinstance(f, ast.Attribute) and f.attr=="connect" and isinstance(f.value, ast.Name) and f.value.id=="sqlite3":
              hits.append("sqlite3.connect")
          elif isinstance(f, ast.Name) and f.id in imported:
              hits.append("from-import")
      return hits
  print("alias", walk("import sqlite3 as sq\nsq.connect(x)"))
  print("dbapi2", walk("import sqlite3\nsqlite3.dbapi2.connect(x)"))
  '
```

**Stronger rejected alternative (inside the finding, not a rewrite):** a runtime recorder on `sqlite3.connect` for the whole WAL+lock test — every URI in `bin/lib/` during that test must be one of the two `_connect` URIs. AST membership cannot see aliases; a recorder can. Do not proceed on the specified walk as the one-opener door.

---

### M1 — OQ-5.2 is OPEN; the rest of the design still treats the live Cursor overwrite as required

```
Where: OQ-5.2 (design ~1341–1367) vs surface-capability matrix (~290–297) vs Option A “Files touched” (~1143–1144) vs dual-predicate table (~1134) vs residual-MAJOR rule (~1396) vs assumption 9 (~1478–1481)
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The impl step is written as if the owner already said “yes, overwrite the hook my running Cursor is using.” If the owner meant “no” (same class as OQ-6’s Claude cache), a worker following Option A / the dual-predicate “honest path” overwrites `~/.cursor/hooks/writ-blast-gate.sh` anyway. If the worker honors OPEN and skips the copy, the dual-predicate table’s “no fight” row is false: Claude source and Cursor copy diverge, and the grill’s “same strings on Claude and Cursor” lock is broken. Either way the human-authority answer is assumed in prose, not asked.
Evidence:
  OQ-5.2 (design ~1341–1348): “the **authorization** is open. … **Question to the owner:** may the impl step run the body copy below, or is it an operator action like OQ-6’s?”
  Residual-MAJOR rule (design ~1396–1397): “A residual MAJOR is allowed to leave this design only as an entry here (OQ-5.1, OQ-5.2, OQ-6) — **not as prose elsewhere.**”
  Prose elsewhere that still decides “yes”:
    ~294: “after the deny-copy edit the plan **must** refresh the Cursor copy”
    ~1143–1144 Option A files touched: “`.claude/hooks/writ-blast-gate.sh` (deny branch) **plus a body-only `install -m 0755` refresh of its `~/.cursor/hooks/` copy**” — not gated on owner yes
    ~1134 dual-predicate: pair “three split messages” vs “same strings on Claude and Cursor” marked **Fight? no**, honest path “provided the plan’s Done cell is the one-file `install -m 0755` + silent `diff -q`”
    ~1479 assumption 9: “the copy **must** be refreshed after the deny-copy edit”
  Grill lock (handoff `2026-08-19-bkt6-writ-probe-grill.md` shape item 7 / R15): same strings on Claude and Cursor; **no** settings/hooks.json edit. The strings-lock is only kept if the copy runs. That is an unanswered operating-burden / live-machine overwrite (human-authority domains 3 and 11), the same class OQ-6 correctly left as operator work.
  Live wiring this session: `~/.cursor/hooks.json` still has `command: bash /Users/phatchenh/.cursor/hooks/writ-blast-gate.sh` on `preToolUse` / `Write` / `failClosed: true` (file lines 84–87). Overwriting that file is not a repo edit; it is a live-session change.
Check:
  rg -n "must refresh|Files touched|Fight\?|must be refreshed" docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
  sed -n '80,88p' ~/.cursor/hooks.json
```

Human-authority: silently assumed **operating burden** (operator’s live Cursor hook) and **irreversible overwrite** of a file outside the repo. An OPEN OQ does not license Option A to list the overwrite as an unconditional file touch.

---

### M2 — 5b “exactly one recorded connect” and 6b “exactly two recorded calls” share one `def` and “the same” shim, with no specified reset

```
Where: artifact §7 assert 5b (~818–827) and assert 6b (~864–871), both required inside the single `def` that also holds asserts 1–4 (~724–731)
Severity: MAJOR
Confidence: VERIFIED (text co-satisfiability; not a SQLite fact)
Impact (plain language): A worker who keeps one `recorded = []` for the whole test — the reading “the same recording shim used for 6b” invites — cannot green both 5b and 6b on an honest `_connect`. They will drop one pin, split the `def` (forbidden by r7/r8), or fake the recorder. The two pins that r8 added then fail to co-exist.
Evidence:
  Assert 5b (design ~825–826), on the locked DELETE fixture: “the recorder shows **exactly ONE** recorded connect — the retry did **not** fire.”
  Assert 6b (design ~869–871), on the WAL fixture: “exactly **two** recorded calls — the retry actually fired.”
  Bind (design ~820–821): 5b runs `_connect` “with the module’s `sqlite3.connect` patched by **the same recording shim** used for 6b.”
  Bind (design ~724–731): 5a/5b “must sit inside a **single `def test_…`**” with asserts 1–4. Assert 6 is in that same numbered block.
  Assert 3 already calls `probe()` → `_connect` on the WAL db (two connects if honest). If the shim is on for the whole function, the list is already length 2 *before* 5b, and longer after assert 4’s folded readers. Then 5b’s “exactly ONE” is red on honest code. If the list is *not* reset between 5b and 6b, 6b’s “exactly two” is red after 5b appended one more.
  The spec never says “reset the recorder”, “new list per drive”, or “assert on the slice for this call.” “Same shim” is the opposite of “fresh recording.”
Check: In the test `def` the plan will write, search for one `recorded` list versus two. If one list and no `recorded.clear()` / new list between 5b and 6b, both pins cannot pass together on honest `_connect`.
```

This is under-specified, not unsatisfiable-if-reset. A good-faith worker may split recordings; a literal worker cannot satisfy the pair. Bad-faith and good-faith do not pass equally — honest-literal fails — which is how unstated resets get dropped.

---

## Six-audit notes (only where they feed the findings)

1. **Fact & arithmetic.** Recomputed this session, python sqlite 3.51.0:
   - Locked DELETE + `BEGIN EXCLUSIVE`: plain `ro` → `'database is locked'` in 0.0s with `timeout=0`; default timeout → **5.235s** (artifact’s 5.14–5.34 band).
   - Same locked db returns `[(1,), (5,)]` under `immutable=1`, `nolock=1`, `vfs=unix-none`, and **`vfs=unix-dotfile`**. `vfs=unix-excl` still locks. `vfs=unix-nolock` → `no such vfs` on this build.
   - Real `codegraph init` in a temp git repo: header `b'\x02\x02'`, listing `[.gitignore, codegraph.db]`; plain `ro` and `vfs=unix-none` → `'unable to open database file'`; `immutable=1` → rows; listing after reads unchanged. Equality 6b’s `vfs=unix-none` matrix row is factually right. `unix-dotfile` is a fourth lock-skip VFS; equality still rejects the extra `vfs=` key, so 6b is not broken by it — the AST pin is.
   - `sqlite3.connect` `__text_signature__`: `timeout` is the **second positional**. 6b’s “kwargs hold `timeout == 0`” fails an honest `connect(uri, 0, uri=True)` even though timeout is 0. Not raised as MAJOR; keyword form still satisfies.

2. **Internal consistency.** C1: coverage claim vs specified walk. M1: OQ-5.2 OPEN vs “must refresh” / Option A files-touched / dual-predicate “no fight” / “residual MAJOR not as prose elsewhere.” M2: one-`def` + same shim vs one-vs-two recorded counts.

3. **Gaming simulation (transcript).** Highest-stakes r8 claims: one opener; first URI exact `file:{db}?mode=ro`; locked db stays unreadable via `_connect`.
   - `_connect` first URI `?mode=ro&vfs=unix-none`: 6b equality **red** (live extra key). 5b1 **red** (no `'database is locked'`). Pin holds on `_connect`.
   - C12/C16 `import sqlite3 as sq` + `sq.connect(...?mode=ro&immutable=1)`: AST pin **green** (C1). Assert 4 **green**. Post-4 listing **green**. 5b/6b still pass on `_connect`. Intent of “one opener” **betrayed**. This is the r8 gate that does not hold.
   - Cursor copy skipped: pytest **green** (artifact already records this). Dual-predicate “same strings” **betrayed** unless OQ-5.2 is yes — which is unanswered (M1).

4. **Assumption feasibility.** Duplicate openers exist at the cited lines (`blast_radius.py:133-137`, `artifact_claims.py:2166-2168` and `2488-2490`). `probe()` still maps connect failure to `"missing"` (`codegraph_index.py:67-68`). `freshness()` still folds non-usable to `"unrecognized"` (`blast_radius.py:288-289`). WAL hole on real `codegraph init` reproduced. Python stdlib has **no** `vfs_register` (only `register_adapter` / `register_converter`) — a default-VFS swap without a URI key is not a stdlib game. Grill OUT list not re-opened in the r8 patch.

5. **Contract compliance.** Grill freeze (enum, fail-closed, no db delete, no `index` retry, no `hooks.json`) is intact in the chosen approach. R15 “same strings / one script” is **not** intact while OQ-5.2 is OPEN and Option A still lists the copy as a file touch (M1). Scope C-11 (no piggyback probe clone, no MCP, no ready-file) not violated by the r8 pin text.

6. **Missing-by-construction.** The r8 amend is written as a pin-vs-lazy-URI arms race on `_connect`. That hides the still-duplicate *call sites* (C12/C16 `import sqlite3` inside the function today) and treats AST shape as if it were a runtime identity. It also hides that “same strings on Cursor” is not a test and is not owner-authorized. 5b/6b on `_connect` can be perfect while the one-opener contract is empty.

## Human-authority audit

| Domain | In this artifact | Status |
|---|---|---|
| Operating burden / irreversible overwrite of live `~/.cursor/hooks/writ-blast-gate.sh` | OQ-5.2 OPEN, but Option A / matrix / assumption 9 still require the copy | **M1 — silently assumed in prose** |
| Claude cache refresh | OQ-6 OPEN, not a Done-cell | asked (ok) |
| Cursor deny envelope | OQ-5.1 OPEN | asked (ok) |
| `timeout=0` vs default ~5.2s lock wait | chosen as production pin (r7) | not re-asked; not an r8-new gate; left |
| OQ-4 WAL `immutable=1` stale-read residual | closed as away-craft, owner not re-asked | prior round; not re-opened here |

## What this mode cannot certify

Cross-model craft review of the r8 pin text. It cannot certify that a same-lineage author would not again prefer “one more AST form” over a runtime recorder (that preference is how C1 survived into r8). Adjudication stays with ORCH/judge.

## Verdict

**revise** — do not proceed to spec/plan on the specified AST one-opener walk (C1). Close or gate every leftover “must copy ~/.cursor/hooks” sentence on a recorded owner answer (M1). Say “new recorder list per drive” (or equivalent) so 5b and 6b can both pass in the one `def` (M2). Equality 6b and `_connect`-observed 5b on `_connect` itself do not need another URI-token round.

=== END REPORT ===
