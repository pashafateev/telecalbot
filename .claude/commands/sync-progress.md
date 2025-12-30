# Sync Progress and Learnings

Review completed work, update roadmap with progress, and capture learnings in AI docs.

## Usage

```
/sync-progress [optional: path-to-roadmap.md]
```

If no roadmap path provided, looks for roadmaps in `ai_docs/` directory.

## Instructions

### 1. Gather Context

**Review recent activity:**
- Check `gh issue list --state closed` for recently closed issues with `roadmap` label
- Check `gh pr list --state merged` for recently merged PRs
- Review issue comments on open roadmap issues
- Look at recent commits: `git log --oneline -20`

### 2. Update Roadmap Progress

**For each completed issue:**
- Find the corresponding line in the roadmap
- Mark checkbox as complete: `- [ ] #42` → `- [x] #42`
- Add completion note if significant: `- [x] #42 Working Python environment ✓`

**For issues with progress:**
- Add status notes: `- [ ] #43 API connections (in progress - auth working)`

### 3. Extract Learnings

**Analyze completed work to identify:**
- What was discovered that wasn't in the original plan?
- What dependencies emerged?
- What took longer/shorter than expected?
- What technical decisions were made?
- What risks materialized or were avoided?

**Sources to check:**
- Issue comments (especially discussions, decisions)
- PR descriptions (what was actually implemented)
- Commit messages (what changed)
- Code changes (new patterns, unexpected complexity)

### 4. Update AI Docs

**Add learnings to appropriate location:**
- If `ai_docs/learnings.md` exists, append there
- Otherwise, add "## Implementation Learnings" section to roadmap
- Or create `ai_docs/learnings.md`

**Learning format:**
```markdown
## Learnings - [Date]

### Phase N: [Phase Title]

**Completed:** #42, #43

**Discoveries:**
- [What was learned]

**Effort Adjustments:**
- [What took longer/shorter and why]

**Technical Decisions:**
- [Decisions made and rationale]

**New Requirements Identified:**
- [Any new work discovered]
```

### 5. Create Follow-up Issues (if needed)

If learnings reveal new work needed:
- Create new issues with `gh issue create`
- Link to parent issue/phase
- Add to roadmap under appropriate phase

### 6. Report Summary

Output:
- Issues completed since last sync
- Roadmap sections updated
- Learnings captured
- New issues created (if any)
- Current overall progress (e.g., "Phase 1: 3/5 complete, Phase 2: 0/4")

## Example Output

```
## Sync Complete

### Progress
- Phase 1: 3/5 deliverables complete (60%)
- Phase 2: 0/4 deliverables complete (0%)

### Recently Completed
- #42 Working Python environment
- #43 Claude API authentication

### Learnings Captured
Added to ai_docs/learnings.md:
- Discovered: Slack API requires additional scopes for thread fetching
- Effort adjustment: API setup took 2hrs instead of estimated 4-6hrs

### Roadmap Updated
- Marked #42, #43 as complete
- Added note about Slack scopes to Phase 2

### New Issues Created
- #48 Add thread:read scope to Slack app (discovered dependency)
```

