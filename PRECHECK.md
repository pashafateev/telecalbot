# Session Precheck Template

Paste this at the start of a task to enforce workflow behavior:

```text
PRECHECK REQUIRED

Before running any command:
1. Read AGENTS.md and list the hard rules you will follow for this task.
2. State current branch and one-sentence task goal.
3. State escalation behavior for blocked GitHub/network commands:
   - retry once with elevated execution
   - if still blocked, report blocker and continue local work
4. Then proceed.
```

