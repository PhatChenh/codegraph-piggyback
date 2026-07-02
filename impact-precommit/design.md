# impact-precommit — Design

**Status:** not built. **Effort:** S. **Build order:** #13 (last batch, alongside
dead-code-finder and doc-coverage — hygiene tier, low urgency).

---

## What it is

A last-look warning at the moment code is committed. When a commit is about to be made,
this tool looks at exactly which lines are being committed, finds which functions and
classes those lines belong to, and counts how many other places in the codebase depend on
each one. If something widely depended-on is being changed, it prints a warning listing the
dependents — before the commit lands, while fixing course is still free. By default it only
warns; a repo can opt in to a stricter mode where committing a change to a heavily-used
piece of code *without any test file in the same commit* is refused outright.

## Why it exists

The companion tool **impact-analyzer** fires at *read* time: when an agent reads a plan, it
learns the blast radius before implementing. But read-time advice can be forgotten twenty
edits later, and not every change flows through a plan. impact-precommit fires at *commit*
time — the last deterministic checkpoint before a change becomes history. Together they
bracket the work: warned going in, checked going out.

Blueprint principles served:

- **Determinism before inference:** "which committed lines overlap which symbols, and who
  calls them" is pure git + SQL. No LLM should ever be asked this.
- **Trust artifacts, not claims:** an agent claiming "this change is low-risk" is a claim;
  the caller-count table attached to the actual staged diff is an artifact.

The failure it prevents: a cheap implementing agent (or a tired human) commits a change to
a symbol with dozens of callers, with no test touching it, and nobody notices until
something downstream breaks. The strict mode makes that specific move mechanically
impossible.

---

## Inputs

1. **The staged diff:** `git diff --cached` (unified diff with line numbers) — nothing
   else about the working tree matters; only what is actually being committed.
2. **The codegraph index:** `.codegraph/codegraph.db` at the repo root, opened read-only.
   No DB → silent exit 0 (a repo without codegraph gets no gate and no noise).

---

## Core computation

Deterministic pipeline, no LLM:

1. Parse `git diff --cached` into per-file changed line ranges (from the `@@` hunk
   headers; new-side line numbers).
2. For each changed file, find the nodes whose span overlaps a changed range:

   ```sql
   SELECT id, name, qualified_name, kind, start_line, end_line
   FROM nodes
   WHERE file_path = ? AND NOT (end_line < ? OR start_line > ?);
   ```

3. For each overlapping node, count and list incoming dependents (the shared blast-radius
   query over `edges` with `kind IN ('calls','references','imports')`).
4. Classify each node with impact-analyzer's existing thresholds — LOW 1–2, MEDIUM 3–5,
   HIGH 6–15, CRITICAL >15 callers; 0 callers → silent.
5. **Strict check:** if any CRITICAL node is changed and *no test file* (test glob, e.g.
   `test_*.py` / `*_test.*` / `tests/**`) appears among the staged files, that is a
   strict-mode violation.

Note the caveat the DB itself provides: names present in `unresolved_refs` have
under-counted blast radius (dynamic dispatch); when a changed node's name appears there,
say so in the output rather than reporting a falsely small count.

---

## Output contract

Bounded report to stderr (so it never pollutes anything parsing stdout), grouped by file,
worst first:

```
── IMPACT PRE-COMMIT: 2 files staged, 3 symbols touched ──
  src/db.py::get_conn [CRITICAL] 23 callers (top 10 shown)
    src/: pipeline.py:69, core.py:14, ...
    ⚠ no test file staged with this change
  src/auth.py::validate_token [MEDIUM] 4 callers — routes.py:88, cli.py:14, ...
──────────────────────────────
```

Silent (no output at all) when every touched symbol has 0 callers or nothing overlaps a
known node.

### Exit codes

- Default (advisory): always exit 0 — the commit proceeds, warned.
- `--strict`: exit 1 **only** when a CRITICAL-blast symbol changed and no test file is in
  the same commit. A non-zero exit from a pre-commit hook blocks the commit; the developer
  can still consciously bypass with `git commit --no-verify` — the point is that ignoring
  the warning becomes a deliberate act, not an accident.

---

## Delivery

1. **`.git/hooks/pre-commit` wrapper:** a thin shell stub installed into a repo's
   `.git/hooks/` that calls the CLI. Whether the stub passes `--strict` is a **per-repo
   opt-in** — advisory-first is the default posture everywhere; blocking mode is enabled
   only in repos whose owner asked for it.
2. **CLI:** runnable standalone (`impact_precommit.py [--strict]`) against the current
   staged state, for CI use ("did this PR's commits touch CRITICAL symbols without
   tests?") and manual pre-flight checks.

Ships as a `manifest.json` entry so `piggyback install/init/update` distributes it; the
installer places the pre-commit stub (never overwriting an existing hand-written hook —
chain or refuse loudly).

---

## Ground rules inherited

- **Read-only DB:** `mode=ro&immutable=1` via `_shared/db.py`; the tool writes nothing —
  its only output is the report and an exit code.
- **Budgeted, fail-open:** silent when it has nothing to say; ≤ ~30 lines, top-10 callers
  per CRITICAL symbol; any internal error (no DB, git failure, schema drift) → exit 0 so a
  broken checker never holds a commit hostage. Only the *deliberate* strict rule exits 1.
- **Signatures as currency:** symbol identity (node spans, qualified names) comes from the
  same DB columns every sibling tool uses; no private notion of "a symbol".
- **Piggyback delivery rail:** manifest entry + standalone CLI. (This tool's trigger is a
  *git* hook, not a Claude Code hook — the rail still delivers and updates it.)

---

## Dependencies

- `_shared/db.py` — discovery, read-only connect, schema guard.
- `_shared/queries.py` — blast-radius / caller-count, nodes-overlapping-ranges.
- **impact-analyzer** — not a code dependency, but the threshold table (LOW/MEDIUM/HIGH/
  CRITICAL) must stay identical between the two so "CRITICAL" means one thing everywhere.
- `git` on PATH; a staged index to read.

## Non-goals

- Judging whether the change is *correct* — CI and reviewers do that.
- Fully blocking commits by default — advisory-first is the contract; blocking is opt-in
  per repo and scoped to exactly one rule (CRITICAL change + no staged test).
- Checking unstaged or already-committed changes (use changeset-context for branch-level
  briefs).
- Running tests, linting, or secret scanning — other hooks own those.

## Open questions

- **[Human-judgment]** Is "any test file staged" a sufficient strict-mode acquittal, or
  should the staged test have to *reference the changed symbol*? The stronger check is
  more honest but needs the test file to be indexed and adds failure modes; start loose?
- **[Human-judgment]** Should MEDIUM/HIGH symbols with `unresolved_refs` hits escalate to
  the strict rule (their true count may be CRITICAL), or stay advisory with the
  under-count caveat?
- **[Technical research]** Staged-vs-worktree line drift: codegraph indexes files on disk,
  but the staged content can differ from the worktree (partial staging). Measure how often
  this misaligns node spans in practice; if material, compare against `git show :<file>`
  content rather than assuming worktree == index.
