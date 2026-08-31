#!/usr/bin/env python3
"""Verify AI-DLC v2 Engine release identity and built artifact digests."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_VERSION = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
)
REQUIRED_WHEEL_SUFFIXES = {
    "aidlc_v2_engine/__init__.py",
    "aidlc_v2_engine/catalog.py",
    "aidlc_v2_engine/cli.py",
    "aidlc_v2_engine/data/scope-grid.json",
    "aidlc_v2_engine/data/stage-catalog.json",
    "aidlc_v2_engine/service.py",
    ".dist-info/entry_points.txt",
    ".dist-info/licenses/LICENSE",
    ".dist-info/licenses/NOTICE",
    ".dist-info/METADATA",
}
REQUIRED_ENTRY_POINT_LINE = "aidlc-v2 = aidlc_v2_engine.cli:main"
REQUIRED_SOURCE_SUFFIXES = {
    "/.github/workflows/release.yml",
    "/.gitleaksignore",
    "/CODEOWNERS",
    "/README.md",
    "/docs/RELEASE_PROCESS.md",
    "/docs/V2_REQUIREMENTS.md",
    "/docs/PUBLICATION_ARTIFACTS.md",
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
REQUIRED_METADATA_LINES = {
    "License-Expression: Apache-2.0",
    "License-File: LICENSE",
    "License-File: NOTICE",
    "Project-URL: Repository, https://github.com/hk-775/aidlc-v2-engine",
    "Project-URL: Security, https://github.com/hk-775/aidlc-v2-engine/security/policy",
}


class ReleaseCheckError(RuntimeError):
    """Raised when release metadata or artifacts are inconsistent."""


def _source_version(root: Path) -> str:
    path = root / "src" / "aidlc_v2_engine" / "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id == "__version__"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise ReleaseCheckError("src/aidlc_v2_engine/__init__.py has no literal __version__")


def read_version(root: Path = ROOT) -> str:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    try:
        project_version = pyproject["project"]["version"]
    except KeyError as error:
        raise ReleaseCheckError("pyproject.toml has no project version") from error
    if not isinstance(project_version, str) or not SEMANTIC_VERSION.fullmatch(
        project_version
    ):
        raise ReleaseCheckError("project version is not strict semantic versioning")
    source_version = _source_version(root)
    if source_version != project_version:
        raise ReleaseCheckError(
            f"version mismatch: pyproject={project_version}, source={source_version}"
        )
    return project_version


def validate_release_tag(tag: str, version: str) -> None:
    expected = f"v{version}"
    if tag != expected:
        raise ReleaseCheckError(f"release tag must be {expected}, received {tag}")


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        text=True,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ReleaseCheckError(detail or f"git {' '.join(arguments)} failed")
    return completed.stdout.strip()


def verify_annotated_tag(root: Path, tag: str) -> str:
    _git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{tag}}")
    tagged_commit = _git(root, "rev-list", "-n", "1", tag)
    current_commit = _git(root, "rev-parse", "HEAD")
    if tagged_commit != current_commit:
        raise ReleaseCheckError(
            f"tag {tag} resolves to {tagged_commit}, not checked-out {current_commit}"
        )
    return current_commit


def verify_distribution(directory: Path, version: str) -> list[dict[str, object]]:
    expected_names = {
        f"aidlc_v2_engine-{version}-py3-none-any.whl",
        f"aidlc_v2_engine-{version}.tar.gz",
    }
    if not directory.is_dir():
        raise ReleaseCheckError(f"distribution directory is missing: {directory}")
    artifacts = sorted(path for path in directory.iterdir() if path.is_file())
    actual_names = {path.name for path in artifacts}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ReleaseCheckError(
            f"distribution mismatch; missing={missing}, unexpected={unexpected}"
        )
    results = []
    for path in artifacts:
        content = path.read_bytes()
        if not content:
            raise ReleaseCheckError(f"distribution artifact is empty: {path.name}")
        if path.suffix == ".whl":
            try:
                with zipfile.ZipFile(path) as archive:
                    members = archive.namelist()
                    missing = sorted(
                        suffix
                        for suffix in REQUIRED_WHEEL_SUFFIXES
                        if not any(member.endswith(suffix) for member in members)
                    )
                    if missing:
                        raise ReleaseCheckError(
                            f"wheel is missing required members: {missing}"
                        )
                    metadata_name = next(
                        member
                        for member in members
                        if member.endswith(".dist-info/METADATA")
                    )
                    metadata = archive.read(metadata_name).decode("utf-8")
                    entry_points_name = next(
                        member
                        for member in members
                        if member.endswith(".dist-info/entry_points.txt")
                    )
                    entry_points = archive.read(entry_points_name).decode("utf-8")
            except (KeyError, StopIteration, UnicodeError, zipfile.BadZipFile) as error:
                raise ReleaseCheckError(f"invalid wheel: {path.name}") from error
            missing_metadata = sorted(
                line for line in REQUIRED_METADATA_LINES if line not in metadata
            )
            if missing_metadata:
                raise ReleaseCheckError(
                    f"wheel metadata is missing required fields: {missing_metadata}"
                )
            if REQUIRED_ENTRY_POINT_LINE not in entry_points:
                raise ReleaseCheckError(
                    "wheel entry points do not expose the aidlc-v2 command"
                )
        elif path.name.endswith(".tar.gz"):
            try:
                with tarfile.open(path, "r:gz") as archive:
                    members = archive.getnames()
            except tarfile.TarError as error:
                raise ReleaseCheckError(f"invalid source archive: {path.name}") from error
            missing = sorted(
                suffix
                for suffix in REQUIRED_SOURCE_SUFFIXES
                if not any(member.endswith(suffix) for member in members)
            )
            if missing:
                raise ReleaseCheckError(
                    f"source archive is missing required members: {missing}"
                )
        results.append(
            {
                "name": path.name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--require-annotated-tag", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        version = read_version(root)
        validate_release_tag(args.tag, version)
        commit = (
            verify_annotated_tag(root, args.tag)
            if args.require_annotated_tag
            else None
        )
        distribution = (
            verify_distribution(
                args.dist if args.dist.is_absolute() else root / args.dist,
                version,
            )
            if args.dist is not None
            else []
        )
        result: dict[str, object] = {
            "ok": True,
            "version": version,
            "tag": args.tag,
            "commit": commit,
            "artifacts": distribution,
        }
    except (OSError, SyntaxError, tomllib.TOMLDecodeError, ReleaseCheckError) as error:
        result = {
            "ok": False,
            "tag": args.tag,
            "error": str(error),
        }
    json.dump(
        result,
        sys.stdout,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
