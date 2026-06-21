# Impact Analyzer — Design

## What it does

Hooks into `PostToolUse` on the `Read` tool. When AI reads a `.md` file (plan, design, spec), automatically queries codegraph for blast radius of every function/class name mentioned and injects the results as context.

**Goal:** AI that reads a plan already knows which nodes are widely called before it starts implementing. No manual querying, no extra tokens from AI asking codegraph.

---

## Trigger

| Hook event | Matcher | Filter |
|---|---|---|
| `PostToolUse` | `Read` | Only `.md` files |

Not triggered on `.py` reads — too noisy. `.md` = plans/specs only.

---

## Name extraction

1. **Inline code** — `` `function_name` `` or `` `ClassName` `` in prose
2. **Code blocks** — ` ```python ... ``` ` using AST parser (Python), regex fallback for other languages

Extracts **definitions only** (Option A): `def foo`, `class Bar`. Avoids noisy extraction of every identifier mentioned in prose.

Wait — actually Option A was revised: we extract **all names** (inline code + code blocks), including references. New functions not yet in codegraph return nothing — that's fine, silently skipped.

---

## Blast radius thresholds

| Caller count | Label | Output detail |
|---|---|---|
| 0 | — | Silent (skipped) |
| 1–2 | LOW | One-line: `name [LOW] N caller — file:line` |
| 3–5 | MEDIUM | Grouped by directory |
| 6–15 | HIGH | Full grouped list |
| >15 | CRITICAL | Top 10 callers shown, count noted |

---

## DB discovery

Walks up from `cwd` (provided by Claude Code in hook JSON) until it finds `.codegraph/codegraph.db`. Silent exit if not found — no codegraph = no output.

---

## Hook config

Add to `~/.claude/settings.json` (global, works for any project):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["/Users/phatchenh/The One Ring/workflow/vibe-coding/codegraph-piggyback/impact-analyzer/impact.py"]
          }
        ]
      }
    ]
  }
}
```

---

## Sample output

```
── IMPACT ANALYSIS: phase-3-plan.md ──
  init_db [HIGH] (8 callers)
    tests/: test_audit.py:27, test_pipeline.py:69, test_db.py:17
    src/: pipeline.py:69, core.py:14
  NoteMetadata [CRITICAL] (top 10 of 63 shown)
    src/: frontmatter.py:12, processor.py:44
    tests/: test_meta.py:8, test_pipeline.py:22
  get_connection [LOW] 2 callers — db.py:76, utils.py:11
──────────────────────────────
```

---

## Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Trigger on Edit/Write? | No | AI is following plan — blocking creates infinite loop |
| Trigger on .py reads? | No | Too noisy — fires on every source file AI reads |
| Trigger on .md reads? | Yes | Plans mention real function names → high signal, low noise |
| Block AI on high caller count? | Never | AI is plan-follower, not a rogue agent |
| AST vs regex | AST primary, regex fallback | AST precise for Python; regex catches other langs + inline prose |
| DB discovery | Walk up from cwd | Works for any project without config |
| Hook location | `~/.claude/settings.json` | Global — any project with codegraph benefits |
