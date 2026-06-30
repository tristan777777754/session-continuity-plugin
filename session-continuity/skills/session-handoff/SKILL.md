---
name: session-handoff
description: Save a concise, evidence-based project handoff for a future Codex session. Use only when the user explicitly invokes $session-handoff or explicitly asks to end, wrap up, checkpoint, summarize, or hand off the current project session.
---

# Session Handoff

Create one verified snapshot of the project's current state for a later Codex thread.

## Workflow

1. Resolve this skill's plugin root by moving two directories up from this `SKILL.md`, then run:

   ```bash
   python3 <plugin-root>/scripts/state_file.py locate --cwd "$PWD"
   ```

   Use the returned `project_root`, `state_path`, project name, and Git metadata. Do not discover the project by scanning for an older handoff.

2. Read [references/state-schema.md](references/state-schema.md). Inspect the current conversation and relevant repository evidence. Review the working-tree diff and status when Git is available. Use the current repository and observed tool results as truth; do not re-summarize or preserve claims merely because they appear in an older handoff.

3. Record only evidence-backed state:
   - Put finished work in **Completed and Verified** only when repository or session evidence supports it.
   - Put exact commands that ran and their observed outcomes in **Verification Evidence**. State `not run` when applicable.
   - Separate partial, planned, failed, and unverified work from completed work.
   - Keep durable user constraints and expensive-to-rediscover rationale; omit chat transcripts and routine narration.

4. Perform a best-effort secret review before writing. Remove access tokens, API keys, passwords, cookies, private keys, credential-bearing URLs, and copied environment values. Do not expose or repeat a suspected secret in the final response.

5. Create a complete UTF-8 candidate at `<project-root>/.PROJECT_STATE.md.candidate` using a file-editing tool, not a shell heredoc. Keep it at or below 12 KiB. Use `None recorded.` for an empty required section. Stage the candidate at the project root because `.codex/` may be protected under the normal workspace sandbox.

6. Validate and atomically publish the candidate:

   ```bash
   python3 <plugin-root>/scripts/state_file.py publish --cwd <project-root> --source <candidate-path>
   ```

   If validation fails, fix the candidate and rerun. If Codex blocks creation of the canonical `.codex/` directory, request narrowly scoped approval to rerun this exact publisher command; do not choose another storage location. Remove the candidate after either a successful publish or a final failed attempt.

7. Report the canonical state path and the single highest-value next action.

## Boundaries

- Never edit, create, replace, or use project `AGENTS.md` as continuity storage.
- Never parse Codex transcript files as an interface.
- Never commit, push, publish, or modify `.gitignore` unless the user separately requests it.
- Never call network services for this workflow.
- Replace the current handoff; do not create a transcript archive.
