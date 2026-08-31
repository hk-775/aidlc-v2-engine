from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from aidlc_v2_engine.cli import main

from tests.support import WorkspaceTestCase


class CliTests(WorkspaceTestCase):
    def invoke(self, *arguments: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(arguments))
        output = stdout.getvalue() if code == 0 else stderr.getvalue()
        return code, json.loads(output)

    def test_catalog_command(self) -> None:
        code, result = self.invoke("catalog")
        self.assertEqual(code, 0)
        self.assertEqual(result["catalog"]["stage_count"], 33)  # type: ignore[index]

    def test_detect_scope_command(self) -> None:
        code, result = self.invoke(
            "detect-scope",
            "--description",
            "Patch a CVE vulnerability.",
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["detection"]["scope"], "security-patch")  # type: ignore[index]

    def test_init_and_status_commands(self) -> None:
        store = str(self.workspace / "cli-project")
        common = (
            "--store",
            store,
            "--id-seed",
            "cli-test",
            "--fixed-time",
            "2026-08-30T12:00:00Z",
        )
        code, initialized = self.invoke(
            *common,
            "init",
            "--name",
            "CLI project",
            "--description",
            "Fix a synthetic bug.",
            "--workspace-kind",
            "brownfield",
            "--scope",
            "bugfix",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--role",
            "workflow_owner",
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            initialized["state"]["workflow"]["current_stage"],  # type: ignore[index]
            "reverse-engineering",
        )
        code, status = self.invoke(*common, "status")
        self.assertEqual(code, 0)
        self.assertEqual(status["state"]["workflow"]["scope"], "bugfix")  # type: ignore[index]

    def test_expected_failure_is_structured_json(self) -> None:
        store = str(self.workspace / "missing")
        code, result = self.invoke("--store", store, "status")
        self.assertNotEqual(code, 0)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "not_found")  # type: ignore[index]

    def test_demo_command(self) -> None:
        code, result = self.invoke(
            "--store",
            str(self.workspace / "demo"),
            "demo",
        )
        self.assertEqual(code, 0)
        demo = result["demo"]
        self.assertEqual(demo["status"], "completed")  # type: ignore[index]
        self.assertTrue(demo["audit_valid"])  # type: ignore[index]
        self.assertEqual(demo["visited_stages"], [  # type: ignore[index]
            "reverse-engineering",
            "requirements-analysis",
            "code-generation",
            "build-and-test",
            "deployment-pipeline",
            "deployment-execution",
        ])


if __name__ == "__main__":
    unittest.main()
