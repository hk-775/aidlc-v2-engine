from __future__ import annotations

import subprocess
from pathlib import Path

from tests.support import WorkspaceTestCase
from tools.history_scan import scan_history


class HistoryScanTests(WorkspaceTestCase):
    def run_git(self, root: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_deleted_credential_shape_is_detected_in_reachable_history(self) -> None:
        root = self.workspace / "repository"
        root.mkdir()
        self.run_git(root, "init", "--quiet")
        self.run_git(root, "config", "user.name", "Synthetic Test")
        self.run_git(root, "config", "user.email", "synthetic@example.invalid")

        prefix = "AK" + "IA"
        credential = prefix + ("Z" * 16)
        sample = root / "sample.txt"
        sample.write_text(credential + "\n", encoding="utf-8")
        self.run_git(root, "add", "sample.txt")
        self.run_git(
            root,
            "commit",
            "--quiet",
            "--no-verify",
            "--no-gpg-sign",
            "-m",
            "Add synthetic fixture",
        )

        sample.unlink()
        self.run_git(root, "add", "sample.txt")
        self.run_git(
            root,
            "commit",
            "--quiet",
            "--no-verify",
            "--no-gpg-sign",
            "-m",
            "Remove synthetic fixture",
        )

        findings, scanned, skipped = scan_history(root)
        self.assertGreater(scanned, 0)
        self.assertEqual(skipped, 0)
        self.assertTrue(
            any(finding.message == "cloud access key identifier" for finding in findings)
        )

    def test_clean_history_has_no_findings(self) -> None:
        root = self.workspace / "clean-repository"
        root.mkdir()
        self.run_git(root, "init", "--quiet")
        self.run_git(root, "config", "user.name", "Synthetic Test")
        self.run_git(root, "config", "user.email", "synthetic@example.invalid")
        (root / "README.md").write_text("Synthetic repository.\n", encoding="utf-8")
        self.run_git(root, "add", "README.md")
        self.run_git(
            root,
            "commit",
            "--quiet",
            "--no-verify",
            "--no-gpg-sign",
            "-m",
            "Initial synthetic commit",
        )

        findings, scanned, skipped = scan_history(root)
        self.assertEqual(findings, [])
        self.assertGreater(scanned, 0)
        self.assertEqual(skipped, 0)
