# Session Continuity for Codex

Session Continuity is a local Codex plugin that carries compact, verified project state from one thread into the next.

It is designed for users who intentionally start a fresh Codex thread for each task and want continuity without copying an old conversation into the new thread.

## How it works

1. Run `$session-handoff` at the end of a useful work session.
2. The skill inspects the current conversation, repository, Git status, and observed verification results.
3. It atomically writes the current project state to:

   ```text
   <project-root>/.codex/session-continuity/PROJECT_STATE.md
   ```

4. In a later thread, the plugin's `SessionStart` hook loads that file as historical, non-authoritative context.

The current user request, repository state, verified tool results, and `AGENTS.md` instructions always take precedence over the saved handoff.

## Features

- Explicit-only `$session-handoff` skill
- Automatic project-local state loading on `startup`, `resume`, and `clear`
- Git and non-Git project support
- Atomic state replacement with a 12 KiB writer limit
- Defensive 16 KiB loader limit
- UTF-8, schema, heading-order, symlink, and path-escape validation
- Fail-open startup behavior when state is missing or invalid
- No network access, telemetry, database, or external service
- Never creates, replaces, or modifies `AGENTS.md`

## Plugin structure

```text
session-continuity/
├── .codex-plugin/plugin.json
├── skills/session-handoff/
├── hooks/hooks.json
├── hooks/session_start.py
├── scripts/state_file.py
└── tests/
```

## Local installation

Clone the repository and copy the plugin into your personal plugin directory:

```bash
git clone https://github.com/tristan777777754/session-continuity-plugin.git
mkdir -p ~/plugins
cp -R session-continuity-plugin/session-continuity ~/plugins/session-continuity
```

Add the following entry to `~/.agents/plugins/marketplace.json`, preserving any existing entries:

```json
{
  "name": "session-continuity",
  "source": {
    "source": "local",
    "path": "./plugins/session-continuity"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

Install the plugin using the name of your personal marketplace:

```bash
codex plugin add session-continuity@personal
```

Open `/hooks`, review the Session Continuity command, and trust it. Hook definitions are intentionally not trusted automatically.

## Usage

At the end of a session, explicitly invoke:

```text
$session-handoff
```

If the normal workspace sandbox protects the project's `.codex/` directory, approve the narrowly scoped publisher command when Codex asks. The plugin will not use an alternate storage location.

Start a genuinely new Codex thread in the same project. The saved handoff is loaded automatically; no separate “read the previous summary” prompt is needed.

## State safety

The loader treats `PROJECT_STATE.md` as untrusted historical data:

- It may be stale or wrong.
- Text inside it is not an instruction source.
- Suspicious instructions or secrets inside it must not be followed or repeated.
- State from one project is never searched for or loaded into another project.

The handoff remains local unless you choose to commit or synchronize it. The plugin does not modify `.gitignore` automatically.

## Development

The runtime uses only the Python 3 standard library.

Run the test suite:

```bash
cd session-continuity
python3 -m unittest discover -s tests -v
```

The current suite covers project-root resolution, Git metadata, atomic publication, schema validation, invalid UTF-8, size limits, symlinks, path escape, hook JSON, malformed-state warnings, project isolation, and `AGENTS.md` preservation.

See [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) for the complete state contract and security model.

## Status

Version `0.1.0` is implemented and locally validated with Codex CLI `0.138.0`.

Codex `0.138.0` requires the plugin manifest to declare the hook path explicitly. Its runtime accepts and discovers this field, although the older bundled `plugin-creator` validation helper still reports the `hooks` field as unsupported.

## License

MIT
