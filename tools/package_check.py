#!/usr/bin/env python3
"""Build and inspect temporary source and wheel archives without publishing."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

try:
    from tools.release_check import ReleaseCheckError, read_version, verify_distribution
except ModuleNotFoundError:
    from release_check import ReleaseCheckError, read_version, verify_distribution

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result: dict[str, object] = {
        "ok": False,
        "build_command": "python -m build --no-isolation",
    }
    with tempfile.TemporaryDirectory(prefix="aidlc-v2-package-check-") as directory:
        source_directory = Path(directory) / "source"
        shutil.copytree(
            ROOT,
            source_directory,
            ignore=shutil.ignore_patterns(
                ".git",
                ".tmp",
                ".coverage",
                "*.egg-info",
                "__pycache__",
                "*.pyc",
                ".venv*",
                "build",
                "dist",
            ),
        )
        output_directory = Path(directory) / "dist"
        build_temporary_directory = Path(directory) / "tmp"
        build_temporary_directory.mkdir()
        command = [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(output_directory),
            str(source_directory),
        ]
        completed = subprocess.run(
            command,
            cwd=source_directory,
            env={
                **os.environ,
                "TMPDIR": str(build_temporary_directory),
                "TEMP": str(build_temporary_directory),
                "TMP": str(build_temporary_directory),
            },
            check=False,
            capture_output=True,
            text=True,
        )
        archives = (
            sorted(output_directory.glob("*")) if output_directory.exists() else []
        )
        wheel_members: list[str] = []
        source_members: list[str] = []
        for archive in archives:
            if archive.suffix == ".whl":
                with zipfile.ZipFile(archive) as package:
                    wheel_members = sorted(package.namelist())
            elif archive.name.endswith(".tar.gz"):
                with tarfile.open(archive, "r:gz") as package:
                    source_members = sorted(package.getnames())
        required_wheel_suffixes = {
            "aidlc_v2_engine/__init__.py",
            "aidlc_v2_engine/catalog.py",
            "aidlc_v2_engine/cli.py",
            "aidlc_v2_engine/data/scope-grid.json",
            "aidlc_v2_engine/data/stage-catalog.json",
            "aidlc_v2_engine/service.py",
        }
        wheel_ok = all(
            any(member.endswith(suffix) for member in wheel_members)
            for suffix in required_wheel_suffixes
        )
        required_source_suffixes = {
            "/.github/workflows/release.yml",
            "/.gitleaksignore",
            "/CODEOWNERS",
            "/README.md",
            "/docs/ARCHITECTURE.md",
            "/docs/PUBLICATION_ARTIFACTS.md",
            "/docs/RELEASE_PROCESS.md",
            "/docs/V2_REQUIREMENTS.md",
            "/examples/evidence/README.md",
            "/examples/evidence/build-and-test-summary.md",
            "/examples/evidence/business-overview.md",
            "/examples/evidence/code-summary.md",
            "/examples/evidence/requirements.md",
            "/examples/policy.strict.json",
            "/requirements-build.lock",
            "/schemas/policy.schema.json",
            "/site/assets/architecture.drawio",
            "/site/assets/architecture.png",
            "/site/assets/aws-services-architecture.drawio",
            "/site/assets/aws-services-architecture.png",
            "/site/architecture.html",
            "/site/architecture.js",
            "/site/index.html",
            "/tests/test_lifecycle.py",
            "/tools/browser_check.py",
            "/tools/history_scan.py",
            "/tools/release_check.py",
            "/uv.lock",
        }
        source_ok = all(
            any(member.endswith(suffix) for member in source_members)
            for suffix in required_source_suffixes
        )
        release_artifacts = []
        release_check_error = None
        if completed.returncode == 0:
            try:
                release_artifacts = verify_distribution(
                    output_directory,
                    read_version(source_directory),
                )
            except (OSError, ReleaseCheckError) as error:
                release_check_error = str(error)
        result = {
            "ok": (
                completed.returncode == 0
                and len(archives) == 2
                and wheel_ok
                and source_ok
                and release_check_error is None
            ),
            "returncode": completed.returncode,
            "archive_count": len(archives),
            "archive_names": [archive.name for archive in archives],
            "wheel_member_count": len(wheel_members),
            "source_member_count": len(source_members),
            "wheel_contents_ok": wheel_ok,
            "source_contents_ok": source_ok,
            "release_artifacts": release_artifacts,
            "release_check_error": release_check_error,
            "output_tail": (
                completed.stdout.splitlines() + completed.stderr.splitlines()
            )[-12:],
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
