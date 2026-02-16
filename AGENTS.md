# Telecalbot Agent Contract

Primary workflow policy is defined at `../../../AGENTS_GLOBAL.md`.
This file adds repository-specific, non-negotiable rules.

## Mandatory Start Protocol

Before running any command, output a `PRECHECK` block with:
1. Current branch.
2. Task goal in one sentence.
3. Hard rules that will be followed in this task.
4. Escalation plan for blocked GitHub/network commands.

## GitHub/Network Failure Policy

If a required `gh`/GitHub command fails due to connectivity or sandboxing:
1. Retry once using elevated execution per environment policy.
2. If still blocked, mark GitHub actions as blocked and continue local work.
3. Report exact blocked command and pending follow-up action.

## Violation Recovery Protocol

If the user reports a rule break, respond with:
1. `Violation: <rule>`
2. `Correction: <next compliant action>`
3. Then continue immediately with compliant behavior.

## Repository-Specific Rule

- Keep issue `#3` (roadmap meta-issue) open unless explicitly instructed to close it.
