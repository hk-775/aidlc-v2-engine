#!/usr/bin/env python3
"""Dependency-free repository quality and safety scans."""

from __future__ import annotations

import argparse
import ast
import base64
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]

# These encoded values cover the task-supplied source-boundary label variants
# and a personal-name fragment found during path-only provenance review. They
# remain encoded so the scanner does not match its own machine-readable
# denylist. Ordinary repository content must not contain them.
ENCODED_PROVENANCE_TERMS = (
    "QWdlbnRTRExD",
    "YWdlbnRzZGxj",
    "dmlqYXk=",
)

EXCLUDED_PARTS = {
    ".coverage",
    ".git",
    ".tmp",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "demo-data",
    "local-data",
}

TEXT_SUFFIXES = {
    ".css",
    ".dot",
    ".drawio",
    ".html",
    ".in",
    ".js",
    ".json",
    ".lock",
    ".md",
    ".py",
    ".svg",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}

REQUIRED_FILES = {
    ".coveragerc",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/question.yml",
    ".github/actionlint.yaml",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    ".github/workflows/pages.yml",
    ".github/workflows/release.yml",
    ".gitleaksignore",
    ".gitignore",
    "CHANGELOG.md",
    "CODEOWNERS",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "LICENSE",
    "MANIFEST.in",
    "Makefile",
    "NOTICE",
    "PRFAQ.md",
    "QUICKSTART.md",
    "README.md",
    "SECURITY.md",
    "STARTUP.md",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/ADVERSARIAL_REVIEW.md",
    "docs/ARCHITECTURE.md",
    "docs/CLEAN_ROOM_PROVENANCE.md",
    "docs/CONFIGURATION.md",
    "docs/FEATURES_AND_FLOWS.md",
    "docs/LOCAL_RUNBOOK.md",
    "docs/PRD.md",
    "docs/PRODUCTION_READINESS.md",
    "docs/PUBLICATION_ARTIFACTS.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_PROCESS.md",
    "docs/RESPONSIBLE_USE.md",
    "docs/THREAT_MODEL.md",
    "docs/V2_REQUIREMENTS.md",
    "docs/WHITE_LABEL_CHECKLIST.md",
    "examples/evidence/README.md",
    "examples/evidence/build-and-test-summary.md",
    "examples/evidence/business-overview.md",
    "examples/evidence/code-summary.md",
    "examples/evidence/requirements.md",
    "examples/policy.strict.json",
    "launch-materials.md",
    "pyproject.toml",
    "requirements-build.lock",
    "requirements.lock",
    "schemas/audit-event.schema.json",
    "schemas/policy.schema.json",
    "schemas/project-state.schema.json",
    "site/app.js",
    "site/architecture.html",
    "site/architecture.js",
    "site/assets/aidlc-v2-engine-icon.svg",
    "site/assets/aidlc-v2-engine-logo.svg",
    "site/assets/architecture.drawio",
    "site/assets/architecture.png",
    "site/assets/architecture.svg",
    "site/index.html",
    "site/styles.css",
    "src/aidlc_v2_engine/data/scope-grid.json",
    "src/aidlc_v2_engine/data/stage-catalog.json",
    "tools/demo_check.py",
    "tools/history_scan.py",
    "tools/package_check.py",
    "tools/release_check.py",
    "tools/repo_scan.py",
}

EXPECTED_PROJECT_URLS = {
    "Homepage": "https://hk-775.github.io/aidlc-v2-engine/",
    "Repository": "https://github.com/hk-775/aidlc-v2-engine",
    "Issues": "https://github.com/hk-775/aidlc-v2-engine/issues",
    "Documentation": "https://github.com/hk-775/aidlc-v2-engine/tree/main/docs",
    "Changelog": "https://github.com/hk-775/aidlc-v2-engine/blob/main/CHANGELOG.md",
    "Security": "https://github.com/hk-775/aidlc-v2-engine/security/policy",
}


@dataclass(frozen=True, slots=True)
class Finding:
    scan: str
    path: str
    message: str
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "scan": self.scan,
            "path": self.path,
            "message": self.message,
        }
        if self.line is not None:
            result["line"] = self.line
        return result


def _is_excluded(path: Path, root: Path = ROOT) -> bool:
    relative = path.relative_to(root)
    return any(
        part in EXCLUDED_PARTS
        or part.endswith(".egg-info")
        or part.startswith(".aidlc")
        for part in relative.parts
    )


def source_files(root: Path = ROOT) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _is_excluded(path, root):
            continue
        yield path


def text_files(root: Path = ROOT) -> Iterable[Path]:
    for path in source_files(root):
        if not path.suffix or path.suffix.casefold() in TEXT_SUFFIXES:
            yield path


def _relative(path: Path, root: Path = ROOT) -> str:
    return path.relative_to(root).as_posix()


def scan_python_syntax(root: Path = ROOT) -> list[Finding]:
    findings = []
    for path in source_files(root):
        if path.suffix != ".py":
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as error:
            findings.append(Finding("python_syntax", _relative(path, root), str(error)))
    return findings


def scan_formatting(root: Path = ROOT) -> list[Finding]:
    findings = []
    for path in text_files(root):
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeError) as error:
            findings.append(Finding("formatting", _relative(path, root), str(error)))
            continue
        if b"\r\n" in data:
            findings.append(
                Finding("formatting", _relative(path, root), "CRLF line endings")
            )
        if data and not data.endswith(b"\n"):
            findings.append(
                Finding("formatting", _relative(path, root), "missing final newline")
            )
        if data.endswith(b"\n\n"):
            findings.append(
                Finding(
                    "formatting",
                    _relative(path, root),
                    "extra blank line at end of file",
                )
            )
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.rstrip(" \t") != line:
                findings.append(
                    Finding(
                        "formatting",
                        _relative(path, root),
                        "trailing whitespace",
                        line_number,
                    )
                )
            if path.name != "Makefile" and "\t" in line:
                findings.append(
                    Finding(
                        "formatting",
                        _relative(path, root),
                        "tab character",
                        line_number,
                    )
                )
    return findings


def scan_json(root: Path = ROOT) -> list[Finding]:
    findings = []
    for path in source_files(root):
        if path.suffix != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            findings.append(Finding("json", _relative(path, root), str(error)))
    return findings


def decoded_provenance_terms() -> tuple[str, ...]:
    return tuple(
        base64.b64decode(value.encode("ascii")).decode("utf-8")
        for value in ENCODED_PROVENANCE_TERMS
    )


def scan_denylist(root: Path = ROOT) -> list[Finding]:
    findings = []
    denied = tuple(
        sorted({term.casefold() for term in decoded_provenance_terms()})
    )
    for path in text_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            findings.append(Finding("denylist", _relative(path, root), str(error)))
            continue
        for line_number, line in enumerate(lines, start=1):
            normalized_line = line.casefold()
            for term in denied:
                if term in normalized_line:
                    findings.append(
                        Finding(
                            "denylist",
                            _relative(path, root),
                            "provenance-boundary term detected",
                            line_number,
                        )
                    )
    return findings


def scan_branding_provenance(root: Path = ROOT) -> list[Finding]:
    findings = [
        Finding("branding_provenance", finding.path, finding.message, finding.line)
        for finding in scan_denylist(root)
    ]
    expected_branding = {
        "LICENSE": "AI-DLC v2 Engine Contributors",
        "NOTICE": "AI-DLC v2 Engine",
        "README.md": "AI-DLC v2 Engine",
        "pyproject.toml": 'name = "aidlc-v2-engine"',
        "site/index.html": "AI-DLC v2 Engine",
        "site/assets/aidlc-v2-engine-logo.svg": "AI-DLC v2 Engine logo",
    }
    for relative_path, expected_text in expected_branding.items():
        path = root / relative_path
        if not path.is_file():
            findings.append(
                Finding(
                    "branding_provenance",
                    relative_path,
                    "required branding file is missing",
                )
            )
            continue
        if expected_text not in path.read_text(encoding="utf-8"):
            findings.append(
                Finding(
                    "branding_provenance",
                    relative_path,
                    "expected AI-DLC v2 Engine branding marker is missing",
                )
            )
    return findings


CREDENTIAL_PATTERNS = (
    (
        "cloud access key identifier",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "private key material",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "repository access token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "assigned secret value",
        re.compile(
            r"(?i)\b(?:api[_-]?key|password|secret|token)\b\s*[:=]\s*"
            r"[\"'][^\"'\n]{12,}[\"']"
        ),
    ),
)


def scan_credentials(root: Path = ROOT) -> list[Finding]:
    findings = []
    for path in text_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            findings.append(Finding("credentials", _relative(path, root), str(error)))
            continue
        for line_number, line in enumerate(lines, start=1):
            for label, pattern in CREDENTIAL_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            "credentials",
                            _relative(path, root),
                            label,
                            line_number,
                        )
                    )
    return findings


REMOTE_REFERENCE = re.compile(r"(?:https?:)?//", re.IGNORECASE)
NETWORK_CODE = re.compile(
    r"""(?ix)
    @import\s+(?:url\()?["']?\s*(?:https?:)?//
    |url\(\s*["']?\s*(?:https?:)?//
    |\b(?:fetch|WebSocket|EventSource|XMLHttpRequest|sendBeacon)\s*\(
    """
)


class _SiteAssetParser(HTMLParser):
    loaded_attributes = {
        "audio": ("src",),
        "embed": ("src",),
        "iframe": ("src",),
        "image": ("href",),
        "img": ("src", "srcset"),
        "input": ("src",),
        "object": ("data",),
        "script": ("src",),
        "source": ("src", "srcset"),
        "use": ("href",),
        "video": ("poster", "src"),
    }
    loaded_link_relations = {
        "icon",
        "manifest",
        "modulepreload",
        "prefetch",
        "preload",
        "stylesheet",
    }

    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[int, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        for attribute in self.loaded_attributes.get(tag, ()):
            value = values.get(attribute)
            if value and REMOTE_REFERENCE.search(value):
                self.references.append((self.getpos()[0], f"{tag} {attribute}"))
        if tag == "link":
            relations = set((values.get("rel") or "").casefold().split())
            href = values.get("href")
            if (
                relations & self.loaded_link_relations
                and href
                and REMOTE_REFERENCE.search(href)
            ):
                self.references.append((self.getpos()[0], "link href"))
        style = values.get("style")
        if style and NETWORK_CODE.search(style):
            self.references.append((self.getpos()[0], f"{tag} style"))


def scan_external_assets(root: Path = ROOT) -> list[Finding]:
    findings = []
    site_root = root / "site"
    if not site_root.exists():
        return [Finding("external_assets", "site", "site directory is missing")]
    for path in sorted(site_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".html", ".css", ".js", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix in {".html", ".svg"}:
            parser = _SiteAssetParser()
            parser.feed(text)
            for line_number, source in parser.references:
                findings.append(
                    Finding(
                        "external_assets",
                        _relative(path, root),
                        f"network-loaded asset reference in {source}",
                        line_number,
                    )
                )
        for line_number, line in enumerate(text.splitlines(), start=1):
            if NETWORK_CODE.search(line):
                findings.append(
                    Finding(
                        "external_assets",
                        _relative(path, root),
                        "external asset or network API reference",
                        line_number,
                    )
                )
    return findings


def scan_workflows(root: Path = ROOT) -> list[Finding]:
    findings = []
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return [Finding("workflows", ".github/workflows", "directory is missing")]
    action_reference = re.compile(r"^\s*(?:-\s*)?uses:\s*([^#\s]+)")
    pinned_action = re.compile(r"[^@\s]+@[0-9a-fA-F]{40}")
    for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))):
        text = path.read_text(encoding="utf-8")
        relative = _relative(path, root)
        lines = text.splitlines()
        if not re.search(r"(?m)^permissions:\s*$", text):
            findings.append(
                Finding("workflows", relative, "top-level permissions are missing")
            )
        if "contents: read" not in text:
            findings.append(
                Finding("workflows", relative, "contents permission is not read-only")
            )
        for line_number, line in enumerate(lines, start=1):
            if "runs-on: ubuntu-latest" in line:
                findings.append(
                    Finding(
                        "workflows",
                        relative,
                        "runner must use an explicit Ubuntu version",
                        line_number,
                    )
                )
            if re.match(r"^\s*pull_request_target\s*:", line):
                findings.append(
                    Finding(
                        "workflows",
                        relative,
                        "pull_request_target is not permitted",
                        line_number,
                    )
                )
            action_match = action_reference.match(line)
            if not action_match:
                continue
            action = action_match.group(1)
            if not action.startswith("./") and not pinned_action.fullmatch(action):
                findings.append(
                    Finding(
                        "workflows",
                        relative,
                        f"action is not pinned to a full commit: {action}",
                        line_number,
                    )
                )
            if not action.startswith("actions/checkout@"):
                continue
            action_indent = len(line) - len(line.lstrip())
            block = []
            for following in lines[line_number:]:
                following_indent = len(following) - len(following.lstrip())
                if following.lstrip().startswith("- ") and following_indent <= action_indent:
                    break
                block.append(following)
            if not any(
                re.match(r"^\s*persist-credentials:\s*false\s*$", candidate)
                for candidate in block
            ):
                findings.append(
                    Finding(
                        "workflows",
                        relative,
                        "checkout must disable persisted credentials",
                        line_number,
                    )
                )
    return findings


def scan_forbidden_operation_contract(root: Path = ROOT) -> list[Finding]:
    del root
    try:
        from aidlc_v2_engine.models import HARD_DENIED_AGENT_OPERATIONS
        from aidlc_v2_engine.policy import default_policy, validate_policy

        policy = validate_policy(default_policy())
    except Exception as error:
        return [Finding("forbidden_operations", "src/aidlc_v2_engine", str(error))]
    findings = []
    for operation in sorted(HARD_DENIED_AGENT_OPERATIONS):
        if policy["agent_permissions"].get(operation) is not False:
            findings.append(
                Finding(
                    "forbidden_operations",
                    "src/aidlc_v2_engine/policy.py",
                    f"agent operation is not hard denied: {operation}",
                )
            )
    return findings


def scan_packaging(root: Path = ROOT) -> list[Finding]:
    findings = []
    for required in sorted(REQUIRED_FILES):
        if not (root / required).is_file():
            findings.append(Finding("packaging", required, "required file is missing"))
    for path in source_files(root):
        if path.suffix in {".whl", ".zip"} or path.name.endswith(".tar.gz"):
            findings.append(
                Finding(
                    "packaging",
                    _relative(path, root),
                    "package archive must not be committed",
                )
            )
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"]
            if project.get("name") != "aidlc-v2-engine":
                findings.append(
                    Finding("packaging", "pyproject.toml", "unexpected package name")
                )
            if project.get("dependencies") != []:
                findings.append(
                    Finding(
                        "packaging",
                        "pyproject.toml",
                        "runtime dependency list must remain empty",
                    )
                )
            if project.get("scripts") != {
                "aidlc-v2": "aidlc_v2_engine.cli:main",
            }:
                findings.append(
                    Finding(
                        "packaging",
                        "pyproject.toml",
                        "console script identity is missing or inconsistent",
                    )
                )
            if project.get("urls") != EXPECTED_PROJECT_URLS:
                findings.append(
                    Finding(
                        "packaging",
                        "pyproject.toml",
                        "canonical project URLs are missing or inconsistent",
                    )
                )
            if project.get("license-files") != ["LICENSE", "NOTICE"]:
                findings.append(
                    Finding(
                        "packaging",
                        "pyproject.toml",
                        "license files are not explicitly declared",
                    )
                )
        except (KeyError, OSError, tomllib.TOMLDecodeError) as error:
            findings.append(Finding("packaging", "pyproject.toml", str(error)))
    ignore_path = root / ".gitignore"
    if ignore_path.exists():
        ignore_text = ignore_path.read_text(encoding="utf-8")
        for pattern in (
            ".coverage",
            ".tmp/",
            "*.whl",
            "*.tar.gz",
            "demo-data/",
            "!requirements-build.lock",
            "!requirements.lock",
        ):
            if pattern not in ignore_text:
                findings.append(
                    Finding("packaging", ".gitignore", f"missing ignore pattern: {pattern}")
                )
    return findings


SCANS: dict[str, Callable[[Path], list[Finding]]] = {
    "python_syntax": scan_python_syntax,
    "formatting": scan_formatting,
    "json": scan_json,
    "branding_provenance": scan_branding_provenance,
    "credentials": scan_credentials,
    "external_assets": scan_external_assets,
    "workflows": scan_workflows,
    "forbidden_operations": scan_forbidden_operation_contract,
    "packaging": scan_packaging,
}


def run_scans(root: Path = ROOT, selected: Iterable[str] | None = None) -> dict[str, object]:
    selected_names = list(selected or SCANS)
    findings = []
    summaries = {}
    for name in selected_names:
        scan_findings = SCANS[name](root)
        findings.extend(scan_findings)
        summaries[name] = {
            "ok": not scan_findings,
            "finding_count": len(scan_findings),
        }
    return {
        "ok": not findings,
        "scan_count": len(selected_names),
        "scans": summaries,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scans",
        nargs="*",
        metavar="SCAN",
        help="Optional subset; all scans run by default.",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    unknown_scans = sorted(set(args.scans) - set(SCANS))
    if unknown_scans:
        parser.error(
            "unknown scan selection: "
            + ", ".join(unknown_scans)
            + "; choose from "
            + ", ".join(SCANS)
        )
    result = run_scans(ROOT, args.scans or None)
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
