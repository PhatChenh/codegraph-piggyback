# Claude Code Hooks

## What hooks are

Hooks = shell scripts (or HTTP endpoints) that Claude Code runs automatically at specific moments. Configured in `.claude/settings.json`. Claude has no choice — hooks fire regardless of what the AI wants to do.

**What hooks can do:**
- **Inject context** → add text into Claude's context window (`additionalContext`) — AI reads it and adjusts
- **Block the action** → return `permissionDecision: "deny"` — AI cannot proceed
- **Force AI to ask user** → return `permissionDecision: "ask"` — pauses, shows user a prompt
- **Just warn** → return `systemMessage` — shows warning in transcript, AI continues

**Hook types (by mechanism):**
- `command` — shell script, receives JSON on stdin, returns decisions via exit codes + stdout
- `http` — POST JSON to a URL, same response format as command
- `mcp_tool` — call a tool on a connected MCP server
- `prompt` — send prompt to Claude for yes/no evaluation
- `agent` — spawn a subagent that uses tools to verify conditions

**Hook locations:**

| Location | Scope |
|---|---|
| `~/.claude/settings.json` | All projects |
| `.claude/settings.json` | Single project (committable) |
| `.claude/settings.local.json` | Single project (gitignored) |

---

## All hook events

| Event | When | Can block? |
|---|---|---|
| `SessionStart` | Session begins/resumes | No (context only) |
| `Setup` | `--init-only` or maintenance mode | No |
| `UserPromptSubmit` | User submits prompt, before processing | Yes |
| `UserPromptExpansion` | Slash command expands | Yes |
| `PreToolUse` | Before tool executes | Yes |
| `PermissionRequest` | Permission dialog appears | Yes |
| `PermissionDenied` | Auto mode classifier denies tool | No |
| `PostToolUse` | After tool succeeds | No |
| `PostToolUseFailure` | After tool fails | No |
| `PostToolBatch` | Batch of parallel tools resolves | Yes |
| `Stop` | Claude finishes responding | Yes |
| `StopFailure` | Turn ends due to API error | No |
| `SubagentStart` | Subagent spawned | No (can inject context) |
| `SubagentStop` | Subagent finishes | Yes |
| `TaskCreated` | Task created | Yes |
| `TaskCompleted` | Task completed | Yes |
| `Notification` | Claude Code sends notification | No |
| `MessageDisplay` | Assistant message displays | No |
| `InstructionsLoaded` | CLAUDE.md or rules loaded | No |
| `ConfigChange` | Config file changes | Yes |
| `CwdChanged` | Working directory changes | No |
| `FileChanged` | Watched file changes | No |
| `WorktreeCreate` | Worktree created | Yes |
| `WorktreeRemove` | Worktree removed | No |
| `PreCompact` | Context compaction starts | Yes |
| `PostCompact` | Context compaction ends | No |
| `Elicitation` | MCP user input flow | Yes |
| `ElicitationResult` | MCP user input result | Yes |
| `TeammateIdle` | Agent team teammate idle | Yes |

---

## Minimal example

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/impact_check.sh"
          }
        ]
      }
    ]
  }
}
```

Script returns `additionalContext` to inject blast radius info before AI edits a file:

```bash
#!/bin/bash
FILE=$(jq -r '.tool_input.file_path' < /dev/stdin)
python3 impact.py "$FILE" | jq -R -s '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: .
  }
}'
```

**Exit codes:**
- `0` → success, parse stdout for JSON
- `2` → blocking error, stderr fed to Claude as error message
- other → non-blocking error, first line of stderr shown in transcript

---

## Relevant events for codegraph-piggyback tools

| Tool | Best hook event | Reason |
|---|---|---|
| impact-analyzer | `SubagentStart` | Inject blast radius before subagent begins work |
| impact-analyzer alt | `PreToolUse` on `Edit\|Write` | File-by-file warning as AI edits |
| doc-coverage | `PostToolUse` on `Edit\|Write` | Check docstrings after AI adds new functions |
| changeset-context | `SessionStart` | Inject codebase context at session open |
