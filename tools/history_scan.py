#!/usr/bin/env python3
"""Scan every reachable Git blob for credentials and provenance markers."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from tools.repo_scan import CREDENTIAL_PATTERNS, decoded_provenance_terms
except ModuleNotFoundError:
    from repo_scan import CREDENTIAL_PATTERNS, decoded_provenance_terms

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_BLOB_BYTES = 2_000_000


class HistoryScanError(RuntimeError):
    """Raised when Git history cannot be enumerated safely."""


@dataclass(frozen=True, slots=True)
class HistoryFinding:
    object_id: str
    path: str
    message: str
    line: int

    def to_dict(self) -> dict[str, object]:
        return {
            "object": self.object_id,
            "path": self.path,
            "message": self.message,
            "line": self.line,
        }


def _run_git(
    root: Path,
    *arguments: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        input=input_text,
        text=True,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise HistoryScanError(detail or f"git {' '.join(arguments)} failed")
    return completed


def _reachable_objects(root: Path) -> dict[str, str]:
    output = _run_git(root, "rev-list", "--objects", "--all").stdout
    objects: dict[str, str] = {}
    for line in output.splitlines():
        object_id, separator, path = line.partition(" ")
        objects.setdefault(object_id, path if separator else "(Git object)")
    return objects


def _small_blob_ids(
    root: Path,
    object_ids: list[str],
    max_blob_bytes: int,
) -> tuple[list[str], int]:
    if not object_ids:
        return [], 0
    request = "".join(f"{object_id}\n" for object_id in object_ids)
    output = _run_git(root, "cat-file", "--batch-check", input_text=request).stdout
    selected = []
    skipped = 0
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 3:
            raise HistoryScanError(f"unexpected git cat-file response: {line}")
        object_id, object_type, size_text = fields
        if object_type != "blob":
            continue
        try:
            size = int(size_text)
        except ValueError as error:
            raise HistoryScanError(f"invalid Git object size: {line}") from error
        if size > max_blob_bytes:
            skipped += 1
            continue
        selected.append(object_id)
    return selected, skipped


def _read_blobs(root: Path, object_ids: list[str]) -> dict[str, bytes]:
    if not object_ids:
        return {}
    process = subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    request = "".join(f"{object_id}\n" for object_id in object_ids).encode("ascii")
    output, error_output = process.communicate(request)
    if process.returncode != 0:
        detail = error_output.decode("utf-8", errors="replace").strip()
        raise HistoryScanError(detail or "git cat-file --batch failed")

    blobs: dict[str, bytes] = {}
    offset = 0
    for requested_id in object_ids:
        header_end = output.find(b"\n", offset)
        if header_end < 0:
            raise HistoryScanError("truncated git cat-file header")
        header = output[offset:header_end].decode("ascii", errors="replace")
        offset = header_end + 1
        fields = header.split()
        if len(fields) != 3 or fields[1] != "blob":
            raise HistoryScanError(f"unexpected git cat-file response: {header}")
        object_id, _, size_text = fields
        try:
            size = int(size_text)
        except ValueError as error:
            raise HistoryScanError(f"invalid Git object size: {header}") from error
        content_end = offset + size
        if content_end >= len(output) or output[content_end : content_end + 1] != b"\n":
            raise HistoryScanError(f"truncated Git blob: {requested_id}")
        blobs[object_id] = output[offset:content_end]
        offset = content_end + 1
    return blobs


def _history_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    provenance = re.compile(
        "|".join(re.escape(term) for term in decoded_provenance_terms()),
        re.IGNORECASE,
    )
    return (*CREDENTIAL_PATTERNS, ("provenance-boundary term", provenance))


def scan_history(
    root: Path = ROOT,
    *,
    max_blob_bytes: int = DEFAULT_MAX_BLOB_BYTES,
) -> tuple[list[HistoryFinding], int, int]:
    objects = _reachable_objects(root)
    blob_ids, skipped = _small_blob_ids(
        root,
        list(objects),
        max_blob_bytes,
    )
    blobs = _read_blobs(root, blob_ids)
    findings = []
    for object_id, content in blobs.items():
        text = content.decode("utf-8", errors="ignore")
        seen: set[tuple[str, int]] = set()
        for label, pattern in _history_patterns():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                key = (label, line)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    HistoryFinding(
                        object_id=object_id,
                        path=objects.get(object_id, "(Git blob)"),
                        message=label,
                        line=line,
                    )
                )
    findings.sort(key=lambda finding: (finding.path, finding.object_id, finding.line))
    return findings, len(blob_ids), skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--max-blob-bytes",
        type=int,
        default=DEFAULT_MAX_BLOB_BYTES,
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        findings, scanned, skipped = scan_history(
            args.root.resolve(),
            max_blob_bytes=args.max_blob_bytes,
        )
        complete = skipped == 0
        result: dict[str, object] = {
            "ok": not findings and complete,
            "complete": complete,
            "blob_count": scanned,
            "skipped_large_blob_count": skipped,
            "finding_count": len(findings),
            "findings": [finding.to_dict() for finding in findings],
        }
    except HistoryScanError as error:
        result = {
            "ok": False,
            "complete": False,
            "blob_count": 0,
            "skipped_large_blob_count": 0,
            "finding_count": 0,
            "findings": [],
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
