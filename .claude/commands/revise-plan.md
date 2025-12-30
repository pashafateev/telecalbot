# Revise Plan

Update the roadmap and adjust GitHub issues when the plan needs to change significantly.

## Usage

```
/revise-plan <path-to-roadmap.md>
```

Then describe what changed or let AI analyze recent context to identify needed changes.

## When to Use

- Approach for a phase won't work, need to pivot
- Discovered a new phase is needed
- Multiple deliverables should be combined or split
- A phase is no longer needed
- Dependencies changed significantly
- Scope increased or decreased substantially

## Instructions

### 1. Understand the Change

**Ask or infer:**
- What triggered the revision? (discovery, blocker, feedback)
- Which phases/deliverables are affected?
- Is this additive (new work) or subtractive (removing work)?
- Does this affect dependencies?

**Sources to check:**
- Recent issue comments with concerns or blockers
- PR reviews with significant feedback
- Conversations in the current session
- User's description of what changed

### 2. Update the Roadmap Document

**For modified phases:**
- Rewrite the Goal, Deliverables, Technical Approach as needed
- Update effort estimates
- Add notes about why it changed: `> **Revised**: [Date] - [Reason]`

**For new phases:**
- Insert at appropriate position
- Maintain phase numbering or renumber as needed
- Add dependencies to/from other phases

**For removed phases:**
- Don't delete — mark as cancelled with reason
- `### ~~Phase N: Title~~ (Cancelled)`
- `> Cancelled: [Date] - [Reason]`

**For restructured deliverables:**
- Update the deliverable list
- Note what was combined/split and why

### 3. Adjust GitHub Issues

**For obsolete issues:**
```bash
gh issue close <number> --comment "Closed: Plan revised - [reason]. See updated roadmap."
```

**For issues that need updating:**
```bash
gh issue edit <number> --body "..."
```
- Update description to match new plan
- Add comment explaining the change

**For new work:**
```bash
gh issue create --title "[Phase N] New deliverable" --body "..." --label "roadmap,phase-N"
```

**For dependency changes:**
- Update issue bodies to reflect new dependencies
- Add comments linking related issues

### 4. Update Parent Tracking Issue

- Update the overview to reflect current plan
- Mark cancelled items
- Add new items
- Add revision note:
  ```markdown
  ---
  **Revision History**
  - [Date]: [Summary of changes]
  ```

### 5. Update Cross-References

- Ensure all issue numbers in roadmap are still valid
- Update checkboxes: closed issues → `- [~] #42 (cancelled)`
- New issues get added with checkboxes: `- [ ] #55 New deliverable`

### 6. Report Summary

Output:
```markdown
## Plan Revised

### Changes Made
- Phase 3: Approach changed from X to Y
- Phase 4: Added new phase for [reason]
- Deliverables 3.2 and 3.3: Combined into single deliverable

### Issues Updated
- #42: Closed (approach changed)
- #43: Updated description
- #55: Created (new deliverable)

### Roadmap Updated
- Phase 3: Rewritten
- Phase 4: New phase added
- Revision note added

### Impact on Timeline
- Estimated effort: +2 days due to new phase
- Dependencies: Phase 5 now depends on new Phase 4
```

## Example

**User says:** "The embedding approach for deduplication won't work - too expensive. We need to use simpler text similarity instead."

**AI does:**
1. Finds Phase 5 (Quality Scoring & Deduplication) in roadmap
2. Updates Technical Approach section
3. Updates any affected deliverables
4. Edits issue #48 with new approach
5. Adds revision note to roadmap
6. Reports changes

**Roadmap before:**
```markdown
### Phase 5: Quality Scoring & Deduplication
**Technical Approach**:
- Implement simple embedding similarity using sentence-transformers
- Set similarity threshold at 0.85 for duplicate detection
```

**Roadmap after:**
```markdown
### Phase 5: Quality Scoring & Deduplication
> **Revised**: 2024-01-15 - Embeddings too expensive, switched to text similarity

**Technical Approach**:
- Use fuzzy text matching (rapidfuzz) for duplicate detection
- Set similarity threshold at 0.90 for duplicate detection
- Falls back to exact title matching as first pass
```

