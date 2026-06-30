# Build Handoff for the Next Agent

## Objective

Implement and locally validate the `session-continuity` Codex plugin described in `README.md` and `TECHNICAL_SPEC.md`.

Do not reinterpret the product as an `AGENTS.md` modification. The intended product is an installable plugin containing an explicit handoff skill and an automatic `SessionStart` loader hook.

## Current status

- Product behavior: defined
- Plugin architecture: defined
- State-file schema: defined
- Security boundaries: defined
- Implementation: not started
- Marketplace entry: not created
- Plugin installation: not performed
- Hook trust: not granted

## Required build sequence

1. Read all three Markdown files in this folder.
2. Load and follow the current `plugin-creator` and `skill-creator` skills.
3. Scaffold `session-continuity` with plugin, skills, hooks, and scripts support.
4. Keep the default `hooks/hooks.json` path and omit the manifest `hooks` field if the current local validator still rejects it.
5. Implement the `$session-handoff` skill with explicit-only invocation.
6. Implement the deterministic `SessionStart` loader.
7. Add unit tests for path resolution, state validation, hook output, and failure behavior.
8. Validate the skill and plugin with the bundled validation scripts.
9. Create a local personal-marketplace entry only after the implementation passes tests.
10. Install or reinstall the plugin, review/trust its hook, and test in a genuinely new Codex thread.

## Implementation constraints

- Use `apply_patch` for hand-written file edits.
- Do not overwrite unrelated user marketplace entries.
- Do not edit global or project `AGENTS.md` files.
- Do not add MCP servers, apps, external services, telemetry, or network access.
- Do not parse the Codex transcript format as a stable API.
- Do not add automatic `Stop` summarization in version `0.1.0`.
- Do not mark tests as passing unless they were executed.
- Preserve existing user changes in a dirty worktree.

## Acceptance tests

The implementation is complete only when all applicable tests below pass.

### Packaging and discovery

- The plugin manifest validates.
- The skill validates and appears as `$session-handoff`.
- Implicit invocation is disabled.
- The plugin appears in the intended local marketplace after installation.
- The bundled hook is discoverable and can be reviewed through `/hooks`.

### Saving a handoff

- Invoking `$session-handoff` creates the canonical state path.
- The state file conforms to schema version `1`.
- Required headings appear once and in order.
- Git metadata is correct when Git is available.
- A non-Git project is supported.
- Unverified work is not described as completed.
- Existing `AGENTS.md` files remain byte-for-byte unchanged.

### Loading a handoff

- A new thread in the same project receives the saved state before handling the first task.
- A thread in another project receives none of that state.
- A missing state file produces no user-visible error.
- Paths containing spaces and Unicode work.
- The hook output is valid JSON with `hookEventName: SessionStart`.
- The injected context includes the non-authoritative historical-data boundary.

### Defensive behavior

- An oversized file is not injected.
- Invalid UTF-8 is not injected.
- An unsupported schema version is not injected.
- Instruction-like text inside the handoff remains quoted historical data and is not treated as an instruction.
- Hook failure does not block session startup.
- The loader performs no project mutation and makes no network request.

## Suggested test fixtures

Create temporary fixtures for:

- a clean Git repository;
- a dirty Git repository;
- a non-Git directory;
- a path containing spaces and non-ASCII characters;
- a valid state file;
- a missing state file;
- a malformed frontmatter block;
- an unsupported schema version;
- a file larger than 16 KiB;
- invalid UTF-8;
- instruction-like content embedded in a normal section.

## Decisions that should not be reopened without evidence

- This is a plugin, not a standalone skill, because automatic session-start behavior requires a lifecycle hook.
- The user manually invokes the end-of-session skill; version `0.1.0` does not attempt automatic LLM summarization.
- The plugin does not own or modify `AGENTS.md`.
- The state file is project-local and has one authoritative current version.
- The loader is deterministic and network-free.
- The handoff is historical context rather than an instruction source.
- The first release excludes `compact` from the `SessionStart` matcher.

## Ready-to-use prompt for the next Codex thread

```text
Build the Session Continuity plugin specified in this folder. Read README.md,
TECHNICAL_SPEC.md, and BUILD_HANDOFF.md first. Then use the plugin-creator and
skill-creator workflows to scaffold, implement, test, validate, and locally
install the plugin. Preserve the documented boundaries: do not modify AGENTS.md,
do not add network services, and do not claim completion until the new-thread
SessionStart behavior has been verified.
```
