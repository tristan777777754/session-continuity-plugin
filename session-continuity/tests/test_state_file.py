from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from state_file import (  # noqa: E402
    LOADER_MAX_BYTES,
    REQUIRED_SECTIONS,
    STATE_RELATIVE_PATH,
    WRITER_MAX_BYTES,
    StateFileError,
    StateValidationError,
    locate_project,
    publish_state,
    read_project_state,
    validate_state_bytes,
)


def state_text(
    *,
    project_name: str = "example-project",
    schema_version: int = 1,
    sections: tuple[str, ...] = REQUIRED_SECTIONS,
    section_content: str = "None recorded.",
    extra_frontmatter: str = "",
) -> str:
    frontmatter = (
        "---\n"
        f"schema_version: {schema_version}\n"
        'updated_at: "2026-06-29T17:30:00+10:00"\n'
        f"project_name: {json.dumps(project_name, ensure_ascii=False)}\n"
        'project_root: "."\n'
        "git_branch: null\n"
        "git_head: null\n"
        "git_dirty: null\n"
        f"{extra_frontmatter}"
        "---\n\n"
    )
    body = "# Project Session State\n\n" + "\n\n".join(
        f"{heading}\n\n{section_content}" for heading in sections
    )
    return frontmatter + body + "\n"


class StateValidationTests(unittest.TestCase):
    def test_valid_document(self) -> None:
        document = validate_state_bytes(state_text().encode(), max_bytes=WRITER_MAX_BYTES)
        self.assertEqual(document.frontmatter["schema_version"], 1)
        self.assertEqual(document.warnings, ())

    def test_rejects_malformed_frontmatter(self) -> None:
        malformed = state_text().replace("schema_version: 1", "schema_version = 1")
        with self.assertRaisesRegex(StateValidationError, "flat key-value"):
            validate_state_bytes(malformed.encode(), max_bytes=WRITER_MAX_BYTES)

    def test_rejects_unsupported_schema(self) -> None:
        with self.assertRaisesRegex(StateValidationError, "unsupported schema_version"):
            validate_state_bytes(state_text(schema_version=2).encode(), max_bytes=WRITER_MAX_BYTES)

    def test_rejects_invalid_utf8(self) -> None:
        with self.assertRaisesRegex(StateValidationError, "valid UTF-8"):
            validate_state_bytes(b"\xff\xfe", max_bytes=WRITER_MAX_BYTES)

    def test_rejects_oversized_writer_input(self) -> None:
        oversized = b"x" * (WRITER_MAX_BYTES + 1)
        with self.assertRaisesRegex(StateValidationError, str(WRITER_MAX_BYTES)):
            validate_state_bytes(oversized, max_bytes=WRITER_MAX_BYTES)

    def test_rejects_out_of_order_sections(self) -> None:
        sections = list(REQUIRED_SECTIONS)
        sections[0], sections[1] = sections[1], sections[0]
        with self.assertRaisesRegex(StateValidationError, "out of order"):
            validate_state_bytes(state_text(sections=tuple(sections)).encode(), max_bytes=WRITER_MAX_BYTES)

    def test_loader_can_warn_about_missing_section(self) -> None:
        document = validate_state_bytes(
            state_text(sections=REQUIRED_SECTIONS[:-1]).encode(),
            max_bytes=LOADER_MAX_BYTES,
            allow_malformed_sections=True,
        )
        self.assertTrue(document.warnings)
        self.assertIn("Resume Notes", document.warnings[0])

    def test_unknown_frontmatter_fields_are_ignored(self) -> None:
        document = validate_state_bytes(
            state_text(extra_frontmatter='future_field: "supported"\n').encode(),
            max_bytes=WRITER_MAX_BYTES,
        )
        self.assertEqual(document.frontmatter["future_field"], "supported")


class ProjectLocationTests(unittest.TestCase):
    def test_non_git_directory_with_spaces_and_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project space Ω"
            root.mkdir()
            info = locate_project(root)
            self.assertEqual(info.project_root, root.resolve())
            self.assertIsNone(info.git_head)
            self.assertEqual(info.state_path, root.resolve() / STATE_RELATIVE_PATH)

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_git_root_metadata_and_dirty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test User"], check=True)
            (root / "tracked.txt").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "initial"], check=True)
            nested = root / "nested" / "path"
            nested.mkdir(parents=True)

            clean = locate_project(nested)
            self.assertEqual(clean.project_root, root.resolve())
            self.assertRegex(clean.git_head or "", r"^[0-9a-f]{40}$")
            self.assertFalse(clean.git_dirty)

            (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            dirty = locate_project(nested)
            self.assertTrue(dirty.git_dirty)


class PublicationAndReadTests(unittest.TestCase):
    def test_publish_is_valid_and_preserves_agents_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate.md"
            candidate.write_text(state_text(project_name=root.name), encoding="utf-8")
            agents = root / "AGENTS.md"
            original_agents = b"Do not touch this file.\n"
            agents.write_bytes(original_agents)

            target = publish_state(root, candidate)

            self.assertEqual(target, root.resolve() / STATE_RELATIVE_PATH)
            self.assertEqual(target.read_text(encoding="utf-8"), candidate.read_text(encoding="utf-8"))
            self.assertEqual(agents.read_bytes(), original_agents)
            self.assertEqual(read_project_state(root).warnings, ())  # type: ignore[union-attr]

    def test_missing_state_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertIsNone(read_project_state(Path(temporary)))

    def test_rejects_state_file_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "real.md"
            real.write_text(state_text(), encoding="utf-8")
            state_path = root / STATE_RELATIVE_PATH
            state_path.parent.mkdir(parents=True)
            state_path.symlink_to(real)
            with self.assertRaisesRegex(StateFileError, "symlink"):
                read_project_state(root)

    def test_rejects_parent_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
            root = Path(project)
            outside_state = Path(outside) / "session-continuity" / "PROJECT_STATE.md"
            outside_state.parent.mkdir()
            outside_state.write_text(state_text(), encoding="utf-8")
            (root / ".codex").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaisesRegex(StateFileError, "outside the project root"):
                read_project_state(root)

    def test_rejects_oversized_loader_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / STATE_RELATIVE_PATH
            state_path.parent.mkdir(parents=True)
            state_path.write_bytes(b"x" * (LOADER_MAX_BYTES + 1))
            with self.assertRaisesRegex(StateValidationError, str(LOADER_MAX_BYTES)):
                read_project_state(Path(temporary))

    def test_rejects_invalid_utf8_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / STATE_RELATIVE_PATH
            state_path.parent.mkdir(parents=True)
            state_path.write_bytes(b"\xff")
            with self.assertRaisesRegex(StateValidationError, "valid UTF-8"):
                read_project_state(Path(temporary))

    def test_publish_wraps_permission_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate.md"
            candidate.write_text(state_text(project_name=root.name), encoding="utf-8")
            with mock.patch("state_file.Path.mkdir", side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(StateFileError, "cannot publish state"):
                    publish_state(root, candidate)


if __name__ == "__main__":
    unittest.main()
