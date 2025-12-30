# Continue Work

Pick up where the last session left off and continue implementing the roadmap.

## Instructions

1. **Check current progress** by running:
   ```bash
   gh issue list --state open --json number,title,labels --limit 50
   ```

2. **Identify the next task**:
   - Issues are organized by phase (Phase 1 → Phase 7)
   - Work on the lowest phase number first (dependencies matter)
   - Within a phase, pick any open issue

3. **Get issue details** for the one you'll work on:
   ```bash
   gh issue view <issue_number>
   ```

4. **Check/create branch for the phase**:
   - Each phase should be worked on in its own branch
   - Branch naming: `phase-<N>-<description>` (e.g., `phase-1-foundation-auth`)
   - Check if branch exists: `git branch | grep phase-<N>`
   - If starting a new phase, create and checkout branch:
     ```bash
     git checkout -b phase-<N>-<description>
     ```
   - If continuing work on existing phase branch:
     ```bash
     git checkout phase-<N>-<description>
     ```

5. **Implement using TDD** (see `CLAUDE.md` for full guidelines):
   - Read the issue's success criteria carefully
   - Check dependencies (linked issues that must be done first)
   - **Write tests first** that verify the success criteria
   - Run tests (should fail - "red")
   - Implement minimum code to pass tests ("green")
   - Refactor if needed (keep tests passing)
   - Commit: `git commit -m "feat: <description> (#<issue>)"`

6. **When issue is complete**, close it:
   ```bash
   gh issue close <issue_number> --comment "Implemented in commit <sha>"
   ```

7. **Update the roadmap** (`ai_docs/tribal-knowledge-poc/technical-roadmap.md`):
   - Change `- [ ] #N` to `- [x] #N` for completed items

8. **When all issues in a phase are complete**, merge the phase branch into main:
   ```bash
   git checkout main
   git pull origin main
   git merge phase-<N>-<description>
   git push origin main
   ```
   - Optionally delete the phase branch after merging:
     ```bash
     git branch -d phase-<N>-<description>
     git push origin --delete phase-<N>-<description>
     ```

9. **Report what you accomplished** and what's next.

## Quick Reference

- **Tracking Issue**: #5 (has overview of all phases)
- **Roadmap**: `ai_docs/tribal-knowledge-poc/technical-roadmap.md`
- **Spec**: `ai_docs/tribal-knowledge-poc/specification.md`

## Phase Order (respect dependencies)

1. Phase 1: Foundation & Authentication (no dependencies)
2. Phase 2: Slack Data Collection (needs Phase 1)
3. Phase 3: AI Extraction Engine (needs Phase 2)
4. Phase 4: Summarization & Enrichment (needs Phase 3)
5. Phase 5: Quality Scoring & Deduplication (needs Phase 4)
6. Phase 6: Notion Integration (needs Phases 3-5)
7. Phase 7: Testing & Documentation (needs all)

