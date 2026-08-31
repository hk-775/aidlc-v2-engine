from __future__ import annotations

import unittest
from datetime import datetime, timezone

from aidlc_v2_engine.audit import canonical_bytes
from aidlc_v2_engine.demo import run_demo
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.service import LifecycleService
from aidlc_v2_engine.values import DeterministicValueProvider

from tests.support import WorkspaceTestCase


class DeterminismTests(WorkspaceTestCase):
    def test_same_values_produce_identical_initial_state(self) -> None:
        states = []
        for name in ("one", "two"):
            repository = JsonProjectRepository(
                self.workspace / name,
                DeterministicValueProvider(
                    seed="same-seed",
                    base_time=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc),
                ),
            )
            service = LifecycleService(repository)
            states.append(
                service.initialize(
                    name="Deterministic project",
                    description="Fix a synthetic bug.",
                    creator=self.owner,
                    workspace_kind="brownfield",
                    scope="bugfix",
                )
            )
        self.assertEqual(canonical_bytes(states[0]), canonical_bytes(states[1]))

    def test_demo_is_deterministic_except_store_path(self) -> None:
        first = run_demo(self.workspace / "demo-one")
        second = run_demo(self.workspace / "demo-two")
        first.pop("store")
        second.pop("store")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
