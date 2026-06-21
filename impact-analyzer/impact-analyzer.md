# Impact Analyzer
For any code that the agent is about to [change], we want it to query and evaluate the blast radius to inform its decision:

```text
SELECT src.name, src.file_path, src.start_line
FROM edges e
JOIN nodes src ON e.source = src.id
WHERE e.target = 'the_node_you_changed'
AND e.kind IN ('calls', 'imports', 'instantiates')
```
To do this, we want to use hook to make sure the tool is guaranteed to be triggered.

Then, the hook would trigger our Impact Analyzer script, and pass in the parameter, and return the blast radius analysis

**Confusion point**: When AI trigger the hook block -> force AI to use Impact Analyzer script, AI input the param, and run blast analyze right? I am afraid AI dont want to do that and would give bad param - would that happen?
**Answer:** Yes, it is possible AI would do so, but that is because the script triggered by the hook let the AI to do so - meaning the script rely on AI unreliable input. We could totally avoid that by letting the hook extract param deterministically

**Confusion point:** "When AI calls Edit on a file, the hook receives the tool input automatically" -> How did that happened? AI output will be unpredictable, could hook have a crawler to get all the function names and pass them as parameter?
**Answer:** See _How hook works_

## How hook works:

Claude Code is a structured software, so when the AI want to write a file, it would need to pass a JSON string like this:

```JSON
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/src/storage/db.py",
    "old_string": "def init_db():",
    "new_string": "def init_db(path: str):"
  }
}
```

That's why our `PreToolUse` hook could trigger based on what the AI about to do - in this case is `Edit`.

Then you can see that the `tool_input` is structured with fields like `file_path` -> this is what the hook will be able to deterministically get.

## When to fire hook

If we do this combo:
- hook trigger before edit
- call blast analysis, takeing `file_path` as parameter, and then inject context back to AI
- the hook not blocking, so AI edit still go through
- AI did not rethink its edit, but would get instant feedback on its impact after each edit.
this might be good for /tdd-implementation

But then I have an idea: create the impact-analyzer to get the `new_string` + a crawler to get all the function names and pass them in as param for blast analysis. This would open up multiple ways to use the hook:
- when initializing /writing-details-spec: this skill is about surfacing unclear things about the solution design of the previous AI, so it is best for the agent to get context about the design's blast radius
- when AI read a section that has codes, use it to inject codebase knowledge into its context -> might be token wasting, so we might just apply for AI that is doing /research skill, which requires AI to go verify fuzzy claims and assumptions of specs

Further investigation show that hook could not recognize skill, so making hook specific to them is dead.

However, hooks are able to fired based on file type. With this, we limit the hooks to fire on .md file because:
- firing on .py means nothing - the AI is editting the codes, meaning it is at implementation point, not planning point, so blast radius does not make sense
- firing on codegraph read does not make sense: the AI see same infor twice
- firing on .md and extract inline code + code block is _very_ valuable: the AI reading plan/design/specs get extra context about the codebase.

## Final design:

**Trigger:** PostToolUse hook on Read, filtered to *.md files

**Flow:**
```text
AI reads plan.md 
→ hook fires with file content in tool output
→ crawler extracts names from inline code (`name`) + code blocks (``` ```)
→ query codegraph.db: find matching nodes, get callers
→ skip 0-caller names (new/unknown)
→ inject additionalContext with blast radius
```

**Output format (Option C, threshold-based):**
```text
IMPACT ANALYSIS — plan.md
init_db — 8 callers across 5 files [HIGH]
  src/: pipeline.py:69, core.py:14
  tests/: test_audit.py:27, test_pipeline.py:69
Success — 383 callers [CRITICAL — top 5 shown]
  ...
get_leaf_fn — 2 callers [LOW]: utils.py:10, helpers.py:44
```

**Threshold:**

| Caller count | Label    | Output                         |
| ------------ | -------- | ------------------------------ |
| 0            | —        | Silent                         |
| 1–2          | LOW      | One-line mention               |
| 3–5          | MEDIUM   | Summary + file list            |
| 6–15         | HIGH     | Full file-grouped list         |
| >15          | CRITICAL | Top 10 callers, truncated note |

Crawler: AST parser primary (Python code blocks), regex fallback (inline `name` + non-Python blocks)

DB discovery: walk up from cwd → find .codegraph/codegraph.db, silent if not found

Hook location: ~/.claude/settings.json (global — works for any project with codegraph)

