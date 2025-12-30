# Create GitHub Issues from Roadmap

Parse a technical roadmap document and create GitHub issues for each deliverable.

## Usage

```
/roadmap-to-issues <path-to-roadmap.md>
```

## Instructions

1. **Read the roadmap file** provided as the argument

2. **Parse the structure** to identify:
   - Phases (usually `### Phase N: Title`)
   - Deliverables within each phase (usually bullet points under "Deliverables")
   - Dependencies between phases
   - Effort estimates (S, M, L)
   - Success criteria

3. **Create a parent tracking issue** first:
   - Title: `📋 Roadmap: [Roadmap Title]`
   - Body: Overview + links to all phase issues (will update after creating them)
   - Labels: `roadmap`, `tracking`

4. **Create one issue per deliverable** using `gh issue create`:
   ```bash
   gh issue create --title "[Phase N] Deliverable title" --body "..." --label "roadmap,phase-N"
   ```
   
   Issue body format:
   ```markdown
   ## Context
   **Phase**: Phase N - [Phase Title]
   **Roadmap**: [Link to roadmap file]
   
   ## Deliverable
   [Deliverable description from roadmap]
   
   ## Success Criteria
   - [ ] [Criteria 1]
   - [ ] [Criteria 2]
   
   ## Dependencies
   - Blocked by: [list prerequisite issues/phases]
   
   ## Effort Estimate
   [S/M/L from roadmap]
   
   ## Technical Approach
   [Any technical details from roadmap]
   ```

5. **Update the parent tracking issue** with links to all created issues

6. **Update the roadmap file** to add issue numbers:
   - Add issue numbers next to deliverables: `- Working Python environment → #42`
   - Add checkboxes: `- [ ] #42 Working Python environment`

7. **Report summary** of what was created:
   - Total issues created
   - Parent tracking issue number
   - Any issues or warnings

## Example

Input roadmap:
```markdown
### Phase 1: Foundation
**Deliverables**:
- Working Python environment
- Authenticated API connections
```

Creates:
- Issue #1: `📋 Roadmap: Technical Roadmap` (parent)
- Issue #2: `[Phase 1] Working Python environment`
- Issue #3: `[Phase 1] Authenticated API connections`

Updates roadmap:
```markdown
### Phase 1: Foundation
**Deliverables**:
- [ ] #2 Working Python environment
- [ ] #3 Authenticated API connections
```

