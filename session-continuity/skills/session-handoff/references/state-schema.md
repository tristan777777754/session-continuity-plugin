# Project state schema

Write the handoff to `.codex/session-continuity/PROJECT_STATE.md` under the resolved project root.

Use this exact flat frontmatter shape. Quote strings, use lowercase JSON-style booleans, and use `null` for unavailable Git values.

```yaml
---
schema_version: 1
updated_at: "2026-06-29T17:30:00+10:00"
project_name: "example-project"
project_root: "."
git_branch: "feature/example"
git_head: "0123456789abcdef0123456789abcdef01234567"
git_dirty: true
---
```

`updated_at` must be RFC 3339 with an explicit UTC offset or `Z`. `git_head` must be the full 40-character commit hash when available.

Include these headings exactly once and in this order:

```markdown
# Project Session State

## Current Objective

## User Intent and Constraints

## Completed and Verified

## Current Implementation State

## Decisions and Rationale

## Files and Areas in Focus

## Verification Evidence

## Open Issues and Risks

## Next Actions

## Resume Notes
```

Every section must contain useful text or `None recorded.` Keep paths relative to the project root where practical. Do not include machine-specific absolute paths in the handoff.
