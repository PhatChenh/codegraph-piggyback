# BLUEPRINT — Derivative tools on top of codegraph

Everything buildable on `.codegraph/codegraph.db` (+ the decision index and the
diagram model from `ssot-diagram/`), organized by the three goals they serve:

1. **G1 — Help AI read code better and save tokens.**
2. **G2 — Enforce careful code planning and writing, without bloating tokens.**
3. **G3 — Help a non-coder understand and keep track of the codebase** — including
   understanding what an agent *proposes to build* during `/build-pipeline`, before
   any code exists.

Status legend: ✅ shipped · 🔧 stub dir exists, not built · 🆕 new idea, no dir yet.

---

## 0. Ground rules every tool inherits

These are the reasons the old hand-maintained docs died and this stack won't:

- **Read-only on the DB.** No tool ever writes to `.codegraph/codegraph.db`. Derived
  state lives in the tool's own file (`docs/decision-index.json`,
  `diagram-model.json`, …). Codegraph re-indexes; our files survive.
- **Determinism up, inference gated.** A verdict (stale, missing, unreferenced,
  blast radius) is always a pure computation over the DB. An LLM may explain or
  propose on top, behind a human approve step, and anything it wrote is pinned to a
  content signature so drift is *visible*, never silent.
- **Signatures are the shared currency.** File = `files.content_hash`. Symbol =
  sha256 of its source slice `[start_line, end_line]`. Component = sha256 over member
  hashes. Already implemented in `ssot-diagram/decision_index.py` — extract into
  `_shared/` rather than reimplementing (see §4).
- **Hooks are token-budgeted and fail-open.** A hook that injects context must be
  bounded (≤ ~30 lines), silent when it has nothing to say, and never block the
  session on its own errors. `impact-analyzer` set this pattern (0 callers → silent;
  \>15 callers → top 10 only); every injector below follows it.
- **Piggyback is the delivery rail.** Every tool ships as a `manifest.json` entry
  (script + hook events + scope) so `piggyback install/init/update` distributes it.
  CLIs additionally run standalone for CI and manual use.

### The DB, in one glance (what queries can lean on)

| Table | Load-bearing columns |
|---|---|
| `nodes` | `id, kind, name, qualified_name, file_path, start/end_line, docstring, signature, is_exported, decorators` |
| `edges` | `source, target, kind (calls/imports/contains/extends/references/…), metadata, provenance` |
| `files` | `path, content_hash, language, modified_at, node_count` |
| `nodes_fts` | FTS5 over name / qualified_name / docstring / signature |
| `unresolved_refs` | references codegraph couldn't resolve (useful negative signal) |

Two query idioms cover ~80% of every tool below:

```sql
-- blast radius of a symbol (who breaks if it changes)
SELECT n2.name, n2.file_path, e.line
FROM edges e JOIN nodes n1 ON e.target = n1.id
             JOIN nodes n2 ON e.source = n2.id
WHERE n1.name = ? AND e.kind IN ('calls','references','imports');

-- resolve a doc-mentioned token to real code (exists? ambiguous?)
SELECT id, kind, qualified_name, file_path, start_line, end_line
FROM nodes WHERE name = ? OR qualified_name = ?;
```

---

## G1 — Help AI read code better, save tokens

Codegraph's own MCP tools already handle *interactive* lookup ("explore before
read"). The gap these tools fill: **pushing the right structural context to the
agent at the right moment**, so it never spends turns (or tokens) discovering what
the DB already knows.

### 1.1 impact-analyzer ✅ (extend)

**What it does today:** `PostToolUse:Read` hook — when the agent reads a `.md`
plan/spec, extracts code names mentioned in it, queries caller counts, and injects a
blast-radius warning (LOW/MEDIUM/HIGH/CRITICAL) before the agent starts implementing.

**Worthwhile extensions (small, in priority order):**
1. **Definition-line pointer** — for each flagged name, include `file:line` of the
   definition so the agent's follow-up read is surgical, not a whole-file read.
2. **`unresolved_refs` cross-check** — a plan mentioning a name that sits in
   `unresolved_refs` is touching code codegraph couldn't statically resolve; flag it
   as "dynamic dispatch — blast radius under-counted." Cheap honesty about the one
   place counts lie.
3. **Per-session dedup** — same doc read twice shouldn't inject twice (tiny state
   file keyed by transcript id + content hash).

### 1.2 changeset-context 🔧 — the branch brief

**What:** `context_brief.py` — given a branch, a diff, or a file list, emit a
structured brief of everything the change touches *plus its one-hop neighborhood*,
sized to a token budget. The "here's what you need to know before touching this"
document, generated instead of hand-written.

**Inputs:** `git diff --name-only <base>...` (or explicit paths) → touched files.

**Core computation (all SQL + git, no LLM):**
1. Touched files → their nodes (`nodes WHERE file_path IN (…)`).
2. For each node: incoming edges (callers — who depends on this change) and outgoing
   edges (callees — what this change depends on), grouped and counted.
3. Decisions anchored to any touched file/symbol (join `docs/decision-index.json`),
   with live staleness status — *the change you're making may invalidate ADR-0007* is
   exactly the sentence an agent never discovers on its own.
4. Signatures + docstring first-lines only — never bodies (codegraph MCP serves
   bodies on demand; the brief is a map, not the territory).

**Output contract (markdown, budgeted ≤ ~150 lines):**

```
## Change brief: branch fix/retry-logic (4 files, 11 symbols)
### src/queue/retry.py — 3 symbols touched
  retry_with_backoff  ← called by 7 (worker.py:88, scheduler.py:41, …)
  ⚠ ADR-0012 "retry policy" anchors here — status FRESH, will need refresh
### Depends on (outgoing): db.get_conn (12 callers — shared), config.load
### Not in graph: `new_backoff_curve` (mentioned in branch name? plan?) — new symbol
```

**Delivery:** CLI first (`piggyback` script, run manually or from `/build-pipeline`).
Optional later: `SessionStart` hook variant that runs `git diff` vs default branch
and injects only when a branch is mid-flight.
**Effort:** S–M. Highest leverage-per-line tool in G1.

### 1.3 repo-map 🆕 — token-budgeted orientation map

**What:** `repo_map.py --budget 1500` — a ranked, compressed map of the repo's API
surface for cold-start orientation: the most-depended-on symbols, signatures only,
grouped by file. What aider's repo-map does, but computed from codegraph's real edge
table instead of re-parsing, and with deterministic ranking.

**Ranking:** in-degree (`COUNT edges WHERE target = node AND kind IN
('calls','imports','references')`), tie-broken by `is_exported DESC, name`. Include
`kind IN ('class','function','method','interface')` only; skip tests by glob.
Budget enforcement: emit highest-ranked first, stop at budget (estimate 0.3
tokens/char); collapse remainder to `+ N more in src/foo/`.

**Delivery:** CLI + optional `SessionStart` hook for repos where you want every
session pre-oriented. **Effort:** S.

### 1.4 dead-code-finder 🔧 + doc-coverage 🔧 — hygiene pair (build last)

Both are single queries with reporting around them; they save tokens indirectly (less
junk for agents to read) but serve G1 least directly.

- **dead-code-finder:** nodes with no incoming `calls`/`imports`/`references` edges,
  filtered: skip `is_exported` in library code, entry-point globs, decorated symbols
  (`decorators IS NOT NULL` — routes/fixtures register dynamically), test files, and
  anything with hits in `unresolved_refs.reference_name` (dynamic use — don't accuse).
  Output grouped by directory with `file:line`. Delivery: CLI / cron. **Effort:** S.
- **doc-coverage:** `kind IN ('function','method') AND docstring IS NULL`, scoped to
  files changed in the current diff (CI mode) or whole repo (report mode). Exit 1 in
  CI mode. **Effort:** XS.

---

## G2 — Enforce careful planning and writing, without token bloat

The theme: **make claims checkable.** Plans and specs are full of factual claims
about code ("modify `foo` in `bar.py`", "X has no other callers"). Today those
claims are verified by an LLM re-reading code (`/factual-code-verification`) —
expensive and fallible. The DB can verify the *factual* subset deterministically for
free, leaving the LLM only the judgment calls.

### 2.1 codegraph-gate ✅

Shipped. `PreToolUse:Grep|Glob|Read` + `PostToolUse` ordering gate that enforces
codegraph-first exploration with per-file shown+edited exemptions. No changes needed;
listed here because 2.2 deliberately mirrors its "deterministic nudge, fail-open"
posture.

### 2.2 plan-verifier 🆕 ⭐ — deterministic fact-check of plans and specs

**The star of G2.** Before a plan is approved (and before `/build-pipeline` spends a
whole phase on factual verification), mechanically verify every code-referencing
claim in the plan against the DB.

**Claim extraction, two tiers:**
1. **Declared manifest (exact, preferred).** Plans adopt a tiny convention — an HTML
   comment block the planner agent writes (add one line to the writ-planner /
   build-pipeline plan template so it's produced automatically):

   ```markdown
   <!-- plan-verify
   touch: src/auth.py::validate_token, src/db.py::get_conn
   new:   src/auth.py::refresh_token
   remove: src/auth.py::legacy_check
   -->
   ```
2. **Heuristic sweep (fallback).** Backticked identifiers + path-like tokens in
   prose, resolved the same way `decision_index bootstrap` resolves anchor tokens
   (reuse that resolver — it already handles ambiguity honestly).

**Verdicts (pure DB lookups):**

| Claim | Check | Verdict when wrong |
|---|---|---|
| `touch: X` | X exists, unique | `MISSING` (plan edits a ghost) / `AMBIGUOUS` (needs `name@path`) |
| `new: Y` | Y does **not** exist | `COLLISION` (name already taken — silent shadowing ahead) |
| `remove: Z` | Z exists + incoming edge count | `BLOCKED` (Z has N callers the plan never mentions) |
| any touched X | caller count vs plan text | `UNACKNOWLEDGED-BLAST` (X has 12 callers; plan doesn't say "callers") |

**Output:** table of claims + verdicts + evidence (`file:line`, caller counts), exit
1 on any `MISSING/COLLISION/BLOCKED` in `--strict`. Bounded — it prints verdicts,
not source.

**Delivery:**
- CLI: `plan_verify.py <plan.md>` — run as a `/build-pipeline` step between spec and
  plan-approval; this is the deterministic core of factual-code-verification, leaving
  the LLM pass to judgment-only questions (semantics, coupling, intent).
- Hook: `PostToolUse:Write|Edit` matched on `*plan*.md` / `docs/plans/**` — verdicts
  injected right as the agent writes the plan, so it fixes ghosts immediately.

**Why it saves tokens rather than costing them:** every `MISSING` caught here is an
implementation turn that won't be spent editing a file that doesn't exist, and a
review round that won't bounce. **Effort:** M (extraction is the work; verdicts are
trivial). **Depends on:** `_shared` resolver extraction (§4).

### 2.3 impact pre-commit gate 🔧 (the original impact-analyzer plan)

`git diff --cached` → changed line ranges → nodes whose `[start_line,end_line]`
overlap → caller counts → warn, and `--strict` blocks when a CRITICAL-blast symbol
changed while no test file is in the same commit. Complements 1.1 (which fires at
*read* time) by firing at *commit* time. Delivery: `.git/hooks/pre-commit` wrapper +
CLI. **Effort:** S. Deliberately advisory-first; blocking mode opt-in per repo.

### 2.4 decision-index read-hook ✅

Shipped (P1). When an agent reads an ADR whose anchors drifted, it's told to
*propose, not rewrite*. Listed for completeness — it's G2's "don't build on a stale
decision" guard.

---

## G3 — Help a non-coder understand and keep track

### 3.1 ssot-diagram — the interactive SSOT map

The flagship; fully specced in [`ssot-diagram/roadmap.md`](ssot-diagram/roadmap.md)
(P3 model extractor → P4 gated narratives → P5 three-level renderer → P6
regeneration). Two architectural choices there matter to every other G3 tool:

- **`diagram-model.json` is a public intermediate.** Any tool that wants to *show*
  something renders through it — one schema, one renderer, one design system.
- **The renderer is data-blind.** It draws whatever model it's given, which is what
  makes 3.2 nearly free once P5 ships.

### 3.2 plan-visualizer 🆕 ⭐ — see what the agent proposes before it builds

**Your explicitly stated need:** during `/build-pipeline`, the agent produces designs
and plans you can't evaluate as a non-coder. This tool renders the *proposed change*
as a diagram overlay on the *current* code graph — before any code is written.

**Inputs:** the same `plan-verify` manifest from 2.2 (touch/new/remove lists) +
`diagram-model.json` for the current repo. Zero LLM in the picture itself.

**Computation:**
1. Resolve `touch`/`remove` entries to model nodes; mark them.
2. Synthesize dashed "proposed" nodes for `new` entries, placed inside the component
   their declared path belongs to.
3. Pull one-hop callers of every touched/removed node — the "collateral" set (these
   are the boxes a non-coder should ask about: *"why does changing the retry logic
   touch billing?"*).
4. Everything else fades (design system's existing `faded` treatment).

**Rendering (reuses P5 renderer + design-system tokens):**
- touched → action badge (amber) · new → positive badge + dashed border · removed →
  danger badge + strikethrough label · collateral callers → neutral, highlighted edges
  with real counts (`calls ×7`).
- Header panel, plain language, deterministic: *"This plan changes 3 things inside
  Payments, adds 1 new piece, removes 1. 12 existing places depend on the changed
  code. 2 decisions (ADR-0007, ADR-0012) are anchored to affected code."* Every
  number is a query result.
- Verdicts from 2.2 surface as warning chips on the affected nodes — a `MISSING`
  claim literally renders as a ghost node, which is the most honest possible picture
  of a hallucinated plan.

**Delivery:** `plan_visualize.py <plan.md> -o plan-preview.html`, wired as an
optional `/build-pipeline` step right after plan-verify: the human gate reviews a
picture, not a wall of markdown. **Effort:** S *after* P5 ships (it's model
synthesis + reuse); M standalone. **Depends on:** 2.2, ssot P3+P5.

### 3.3 sot-enrichment 🔧 → symbol biography

Reframed from the old "merge ADRs into codegraph nodes" (which would violate the
read-only rule) to a **join-at-query-time** layer: `biography.py <symbol>` answers
*"tell me everything about this piece"* for a non-coder:

1. What it is — kind, plain location, docstring, narrative from `narratives.json`
   if approved (reuse, don't regenerate).
2. Who depends on it — caller count + component names (edges roll-up).
3. Decisions about it — decision-index entries anchored to it, with status.
4. Its history — `git log --follow -L<start>,<end>:<file>` summarized to dates +
   subjects (deterministic; commit messages are already human language).

Delivery: CLI + a "node detail" side-panel data source for the diagram (P5 can embed
biography JSON per node later). **Effort:** S — it's composition of shipped parts.
This is the honest version of the original sot-enrichment idea.

### 3.4 drift-digest 🆕 — "what changed since I last looked"

The non-coder's changelog, computed instead of remembered.

**Mechanism:** `digest.py snapshot` stores a dated snapshot — just `{path:
content_hash}` + per-file symbol name lists (a few KB). `digest.py since <date|last>`
diffs snapshots + current DB and prints, grouped by component (macro names from the
ssot config, so it speaks the same vocabulary as the diagram):

```
Since 2026-06-24 (last snapshot):
  Payments — 3 files changed, 2 new functions (validate_iban, retry_charge), 1 removed
  Auth — untouched
  Decisions: ADR-0012 went STALE (its anchored code changed Jun 28)
  New unresolved references: 2 (dynamic code the index can't see — worth asking about)
```

**Delivery:** CLI + optional cron (weekly snapshot). Pairs naturally with ssot P6:
regenerate diagram + print digest in one habit. **Effort:** S.

---

## 4. Shared infrastructure — `_shared/` (currently empty; build first)

Extract from `decision_index.py` instead of writing fresh — it already has tested
versions of most of this:

| Module | Contents | Source |
|---|---|---|
| `db.py` | `find_db()` walk-up, read-only connect (`mode=ro`), schema guard (fail-loud on missing tables/columns) | extract from `decision_index.py` |
| `sig.py` | file/symbol/component signature recipes | extract from `decision_index.py` |
| `resolve.py` | doc-token → node resolution with honest `AMBIGUOUS`/`UNRESOLVED` outcomes | extract from bootstrap |
| `queries.py` | blast-radius, in-degree ranking, nodes-for-files, edge roll-up | new, ~6 functions |
| `budget.py` | token estimation + budgeted-emit helper (emit ranked items until budget) | new, tiny |
| `hookio.py` | hook JSON stdin parsing, bounded fail-open output | extract from `impact-analyzer`/`decision_hook` |

Rule: extraction happens **when the second consumer appears**, not speculatively —
plan-verifier (2.2) needing the resolver is the natural trigger.

---

## 5. Build order (recommended)

Interleaves "understand" and "enforce" so each step pays off alone:

| # | Tool | Goal | Why this position | Effort |
|---|---|---|---|---|
| 1 | ssot P2 curation (user) + P3 model extractor | G3 | unblocks diagram *and* defines the model every viz tool reuses | M |
| 2 | plan-verifier | G2 | immediate `/build-pipeline` pain relief; triggers `_shared` extraction | M |
| 3 | ssot P4–P6 (narratives, renderer, plumbing) | G3 | the end-goal artifact | L |
| 4 | plan-visualizer | G3 | nearly free once #2 + #3 exist; your stated top need | S |
| 5 | changeset-context | G1 | best token-saver; reuses `queries.py` from #2 | S–M |
| 6 | drift-digest + biography | G3 | tracking habits; compose shipped parts | S each |
| 7 | repo-map | G1 | nice-to-have orientation | S |
| 8 | impact pre-commit, dead-code, doc-coverage | G2/G1 | hygiene; anytime, low urgency | S/XS |

Items 2 and 4 are the pair that changes `/build-pipeline` for you specifically:
**verify the plan's facts mechanically, then look at the plan as a picture** — the
human gate stops being "trust the agent's prose."
