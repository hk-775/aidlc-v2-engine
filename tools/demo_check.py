#!/usr/bin/env python3
"""Run the full synthetic lifecycle in operating-system temporary storage."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aidlc_v2_engine.demo import run_demo  # noqa: E402
from aidlc_v2_engine.errors import ForbiddenOperationError  # noqa: E402
from aidlc_v2_engine.models import Actor  # noqa: E402
from aidlc_v2_engine.persistence import JsonProjectRepository  # noqa: E402
from aidlc_v2_engine.service import LifecycleService  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aidlc-v2-demo-check-") as directory:
        result = run_demo(directory)
        service = LifecycleService(JsonProjectRepository(directory))
        denied = False
        try:
            service.guard_operation(actor=Actor("agent_builder", "agent"), operation="release")
        except ForbiddenOperationError:
            denied = True
        checks = {
            "workflow_completed": result["status"] == "completed",
            "bugfix_route_exercised": result["visited_stages"]
            == [
                "reverse-engineering",
                "requirements-analysis",
                "code-generation",
                "build-and-test",
                "deployment-pipeline",
                "deployment-execution",
            ],
            "zero_unit_incremental_path": result["unit_count"] == 0,
            "audit_valid": result["audit_valid"],
            "agent_release_denied": denied,
            "expected_event_count": result["event_count"] == 66,
        }
        output = {
            "ok": all(checks.values()),
            "checks": checks,
            "demo": result,
        }
        print(json.dumps(output, sort_keys=True))
        return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
