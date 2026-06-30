#!/usr/bin/env python3
"""Shared project-state location, validation, and publication helpers."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


STATE_RELATIVE_PATH = Path(".codex/session-continuity/PROJECT_STATE.md")
WRITER_MAX_BYTES = 12 * 1024
LOADER_MAX_BYTES = 16 * 1024
TITLE = "# Project Session State"
REQUIRED_SECTIONS = (
    "## Current Objective",
    "## User Intent and Constraints",
    "## Completed and Verified",
    "## Current Implementation State",
    "## Decisions and Rationale",
    "## Files and Areas in Focus",
    "## Verification Evidence",
    "## Open Issues and Risks",
    "## Next Actions",
    "## Resume Notes",
)
REQUIRED_FRONTMATTER = (
    "schema_version",
    "updated_at",
    "project_name",
    "project_root",
    "git_branch",
    "git_head",
    "git_dirty",
)


class StateError(Exception):
    """Base error for safe, user-readable state failures."""


class StateValidationError(StateError):
    """Raised when state content violates the version 1 contract."""


class StateFileError(StateError):
    """Raised when a state path is unsafe or unreadable."""


@dataclass(frozen=True)
class ProjectInfo:
    cwd: Path
    project_root: Path
    state_path: Path
    project_name: str
    git_branch: str | None
    git_head: str | None
    git_dirty: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "cwd": str(self.cwd),
            "project_root": str(self.project_root),
            "state_path": str(self.state_path),
            "project_name": self.project_name,
            "git_branch": self.git_branch,
            "git_head": self.git_head,
            "git_dirty": self.git_dirty,
        }


@dataclass(frozen=True)
class StateDocument:
    text: str
    frontmatter: dict[str, Any]
    warnings: tuple[str, ...]


def _absolute_directory(value: str | os.PathLike[str] | None) -> Path:
    raw = Path(value) if value else Path.cwd()
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise StateFileError(f"cannot resolve working directory {raw}: {exc}") from exc
    if not resolved.is_dir():
        raise StateFileError(f"working directory is not a directory: {resolved}")
    return resolved


def _git(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def locate_project(cwd: str | os.PathLike[str] | None = None) -> ProjectInfo:
    normalized_cwd = _absolute_directory(cwd)
    top = _git(normalized_cwd, "rev-parse", "--show-toplevel")
    if top:
        try:
            root = _absolute_directory(top)
        except StateError:
            root = normalized_cwd
    else:
        root = normalized_cwd

    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current") if head else None
    status_output = _git(root, "status", "--porcelain=v1", "--untracked-files=normal") if head else None
    git_dirty = bool(status_output) if status_output is not None else None

    return ProjectInfo(
        cwd=normalized_cwd,
        project_root=root,
        state_path=root / STATE_RELATIVE_PATH,
        project_name=root.name or "project",
        git_branch=branch or None,
        git_head=head or None,
        git_dirty=git_dirty,
    )


def _parse_scalar(raw: str, key: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if re.fullmatch(r"[A-Za-z0-9._/@+-]+", raw):
            return raw
        raise StateValidationError(f"invalid frontmatter value for {key}") from None


def _parse_frontmatter(lines: list[str]) -> tuple[dict[str, Any], int]:
    if not lines or lines[0] != "---":
        raise StateValidationError("missing opening frontmatter delimiter")
    try:
        closing = lines.index("---", 1)
    except ValueError:
        raise StateValidationError("missing closing frontmatter delimiter") from None

    values: dict[str, Any] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.+?)\s*", line)
        if not match:
            raise StateValidationError("frontmatter must use flat key-value entries")
        key, raw = match.groups()
        if key in values:
            raise StateValidationError(f"duplicate frontmatter field: {key}")
        values[key] = _parse_scalar(raw, key)

    missing = [key for key in REQUIRED_FRONTMATTER if key not in values]
    if missing:
        raise StateValidationError(f"missing frontmatter fields: {', '.join(missing)}")
    return values, closing + 1


def _validate_frontmatter(values: dict[str, Any]) -> None:
    version = values["schema_version"]
    if type(version) is not int:
        raise StateValidationError("schema_version must be the integer 1")
    if version != 1:
        raise StateValidationError(f"unsupported schema_version: {version}")

    updated_at = values["updated_at"]
    if not isinstance(updated_at, str):
        raise StateValidationError("updated_at must be an RFC 3339 string")
    timestamp = updated_at[:-1] + "+00:00" if updated_at.endswith("Z") else updated_at
    try:
        parsed_time = datetime.fromisoformat(timestamp)
    except ValueError:
        raise StateValidationError("updated_at must be an RFC 3339 timestamp") from None
    if parsed_time.tzinfo is None:
        raise StateValidationError("updated_at must include an explicit UTC offset or Z")

    project_name = values["project_name"]
    if not isinstance(project_name, str) or not project_name.strip() or len(project_name) > 200:
        raise StateValidationError("project_name must be a short non-empty string")
    if values["project_root"] != ".":
        raise StateValidationError("project_root must be '.'")

    branch = values["git_branch"]
    if branch is not None and not isinstance(branch, str):
        raise StateValidationError("git_branch must be a string or null")
    head = values["git_head"]
    if head is not None and (not isinstance(head, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", head)):
        raise StateValidationError("git_head must be a full 40-character hash or null")
    if values["git_dirty"] is not None and type(values["git_dirty"]) is not bool:
        raise StateValidationError("git_dirty must be a boolean or null")


def _section_problems(body_lines: list[str]) -> list[str]:
    problems: list[str] = []
    if body_lines.count(TITLE) != 1:
        problems.append(f"{TITLE!r} must appear exactly once")

    positions: list[int] = []
    for heading in REQUIRED_SECTIONS:
        count = body_lines.count(heading)
        if count != 1:
            problems.append(f"{heading!r} must appear exactly once")
        else:
            positions.append(body_lines.index(heading))

    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions):
        problems.append("required sections are out of order")

    if body_lines.count(TITLE) == 1 and positions and body_lines.index(TITLE) > positions[0]:
        problems.append("project title must precede required sections")

    if len(positions) == len(REQUIRED_SECTIONS) and positions == sorted(positions):
        for index, heading_position in enumerate(positions):
            end = positions[index + 1] if index + 1 < len(positions) else len(body_lines)
            content = [line for line in body_lines[heading_position + 1 : end] if line.strip()]
            if not content:
                problems.append(f"{REQUIRED_SECTIONS[index]!r} must not be empty")
    return problems


def validate_state_bytes(
    data: bytes,
    *,
    max_bytes: int,
    allow_malformed_sections: bool = False,
) -> StateDocument:
    if len(data) > max_bytes:
        raise StateValidationError(f"state exceeds {max_bytes} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise StateValidationError("state is not valid UTF-8") from None
    if "\x00" in text:
        raise StateValidationError("state contains a NUL byte")

    lines = text.splitlines()
    frontmatter, body_start = _parse_frontmatter(lines)
    _validate_frontmatter(frontmatter)
    problems = _section_problems(lines[body_start:])
    if problems and not allow_malformed_sections:
        raise StateValidationError("; ".join(problems))
    return StateDocument(text=text, frontmatter=frontmatter, warnings=tuple(problems))


def _within_root(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except ValueError:
        return False


def read_project_state(project_root: Path) -> StateDocument | None:
    root = project_root.resolve(strict=True)
    state_path = root / STATE_RELATIVE_PATH
    try:
        metadata = os.lstat(state_path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StateFileError(f"cannot inspect state file: {exc}") from exc

    if stat.S_ISLNK(metadata.st_mode):
        raise StateFileError("state path is a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise StateFileError("state path is not a regular file")

    try:
        resolved = state_path.resolve(strict=True)
    except OSError as exc:
        raise StateFileError(f"cannot resolve state path: {exc}") from exc
    if not _within_root(resolved, root):
        raise StateFileError("state path resolves outside the project root")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(state_path, flags)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise StateFileError("opened state path is not a regular file")
            if opened.st_size > LOADER_MAX_BYTES:
                raise StateValidationError(f"state exceeds {LOADER_MAX_BYTES} bytes")
            data = b""
            while len(data) <= LOADER_MAX_BYTES:
                chunk = os.read(descriptor, LOADER_MAX_BYTES + 1 - len(data))
                if not chunk:
                    break
                data += chunk
        finally:
            os.close(descriptor)
    except StateError:
        raise
    except OSError as exc:
        raise StateFileError(f"cannot read state file: {exc}") from exc

    return validate_state_bytes(data, max_bytes=LOADER_MAX_BYTES, allow_malformed_sections=True)


def publish_state(cwd: str | os.PathLike[str], source: str | os.PathLike[str]) -> Path:
    info = locate_project(cwd)
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    try:
        source_metadata = os.lstat(source_path)
    except OSError as exc:
        raise StateFileError(f"cannot inspect candidate: {exc}") from exc
    if stat.S_ISLNK(source_metadata.st_mode) or not stat.S_ISREG(source_metadata.st_mode):
        raise StateFileError("candidate must be a non-symlink regular file")
    if source_metadata.st_size > WRITER_MAX_BYTES:
        raise StateValidationError(f"candidate exceeds {WRITER_MAX_BYTES} bytes")
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise StateFileError(f"cannot read candidate: {exc}") from exc
    validate_state_bytes(data, max_bytes=WRITER_MAX_BYTES)

    target = info.state_path
    temporary_name: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".PROJECT_STATE.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
    except OSError as exc:
        raise StateFileError(f"cannot publish state to {target}: {exc}") from exc
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    locate = subparsers.add_parser("locate", help="print project and Git metadata as JSON")
    locate.add_argument("--cwd", default=os.getcwd())
    publish = subparsers.add_parser("publish", help="validate and atomically publish a candidate")
    publish.add_argument("--cwd", required=True)
    publish.add_argument("--source", required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "locate":
            print(json.dumps(locate_project(args.cwd).as_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(publish_state(args.cwd, args.source))
    except StateError as exc:
        print(f"session-continuity: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
