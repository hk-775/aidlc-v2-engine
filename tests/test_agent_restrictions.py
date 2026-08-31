from __future__ import annotations

import unittest

from aidlc_v2_engine.errors import AuthorizationError, ForbiddenOperationError

from tests.support import WorkspaceTestCase


class AgentRestrictionTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository, self.service = self.create_project()

    def test_agents_cannot_make_human_navigation_decisions(self) -> None:
        operations = (
            lambda: self.service.set_depth(actor=self.builder, depth="standard"),
            lambda: self.service.set_test_strategy(
                actor=self.builder,
                test_strategy="comprehensive",
            ),
            lambda: self.service.skip_current_stage(
                actor=self.builder,
                reason="Agent attempted skip.",
            ),
            lambda: self.service.park(
                actor=self.builder,
                reason="Agent attempted park.",
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(AuthorizationError):
                    operation()

    def test_external_delivery_operations_are_hard_denied(self) -> None:
        for operation in ("merge", "deploy", "release", "accept_risk", "bypass_gate"):
            with self.subTest(operation=operation):
                with self.assertRaises(ForbiddenOperationError):
                    self.service.guard_operation(
                        actor=self.builder,
                        operation=operation,
                    )

    def test_agent_may_register_declared_artifact(self) -> None:
        artifact = self.service.register_artifact(
            actor=self.builder,
            name="business-overview",
            title="Business overview",
            digest="sha256:" + "a" * 64,
            locator="evidence/business-overview.md",
        )["artifact"]
        self.assertEqual(artifact["submitted_by"], self.builder.actor_id)

    def test_agent_cannot_record_another_reviewer_identity(self) -> None:
        self.complete_current_stage(self.repository, self.service)
        self.register_current_outputs(self.repository, self.service)
        with self.assertRaises(AuthorizationError) as context:
            self.service.record_review(
                actor=self.builder,
                verdict="ready",
                summary="Builder cannot impersonate the product reviewer.",
            )
        self.assertEqual(context.exception.code, "reviewer_identity_required")


if __name__ == "__main__":
    unittest.main()
