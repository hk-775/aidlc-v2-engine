from __future__ import annotations

import unittest
from datetime import datetime, timezone

from aidlc_v2_engine.errors import AuthorizationError, ConflictError, ValidationError
from aidlc_v2_engine.models import Actor
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.service import LifecycleService
from aidlc_v2_engine.values import DeterministicValueProvider

from tests.support import WorkspaceTestCase


class LifecycleTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository, self.service = self.create_project()

    def test_initialization_auto_completes_three_stages(self) -> None:
        state = self.repository.load()
        self.assertEqual(state["workflow"]["scope"], "bugfix")
        self.assertEqual(state["workflow"]["current_stage"], "reverse-engineering")
        self.assertEqual(state["phases"]["initialization"]["status"], "verified")
        for stage in ("workspace-scaffold", "workspace-detection", "state-init"):
            self.assertEqual(state["stages"][stage]["status"], "completed")

    def test_full_bugfix_workflow_completes(self) -> None:
        self.complete_workflow(self.repository, self.service)
        state = self.repository.load()
        self.assertEqual(state["workflow"]["status"], "completed")
        self.assertIsNone(state["workflow"]["current_stage"])
        self.assertEqual(len(state["gates"]), 6)
        self.assertEqual(len(state["units"]), 0)
        self.assertTrue(self.repository.verify_audit()["valid"])

    def test_missing_outputs_block_gate(self) -> None:
        with self.assertRaises(ConflictError) as context:
            self.service.request_approval(
                actor=self.builder,
                rationale="Nothing has been produced.",
            )
        self.assertEqual(context.exception.code, "stage_outputs_missing")

    def test_reviewer_ready_is_required_before_gate(self) -> None:
        self.complete_current_stage(self.repository, self.service)
        self.register_current_outputs(self.repository, self.service)
        with self.assertRaises(ConflictError) as context:
            self.service.request_approval(
                actor=self.builder,
                rationale="Requirements are complete.",
            )
        self.assertEqual(context.exception.code, "review_ready_required")
        self.record_current_review(self.repository, self.service)
        gate = self.service.request_approval(
            actor=self.builder,
            rationale="Requirements and independent review are complete.",
        )["gate"]
        self.assertEqual(gate["status"], "pending")

    def test_gate_requester_cannot_self_approve(self) -> None:
        self.register_current_outputs(self.repository, self.service)
        gate = self.service.request_approval(
            actor=self.owner,
            rationale="Human-authored evidence is ready.",
        )["gate"]
        with self.assertRaises(AuthorizationError) as context:
            self.service.approve_stage(actor=self.owner, gate_id=gate["id"])
        self.assertEqual(context.exception.code, "self_approval_forbidden")

    def test_three_rejections_enable_accept_as_is(self) -> None:
        self.register_current_outputs(self.repository, self.service)
        for revision in range(3):
            gate = self.service.request_approval(
                actor=self.builder,
                rationale=f"Revision {revision + 1} is ready.",
            )["gate"]
            self.service.reject_stage(
                actor=self.owner,
                gate_id=gate["id"],
                reason="Revise the synthetic evidence.",
            )
        gate = self.service.request_approval(
            actor=self.builder,
            rationale="Third revision is ready for final human judgment.",
        )["gate"]
        result = self.service.approve_stage(
            actor=self.owner,
            gate_id=gate["id"],
            accept_as_is=True,
        )
        self.assertTrue(result["gate"]["accept_as_is"])
        self.assertEqual(
            self.repository.load()["workflow"]["current_stage"],
            "requirements-analysis",
        )

    def test_accept_as_is_before_limit_is_rejected(self) -> None:
        self.register_current_outputs(self.repository, self.service)
        gate = self.service.request_approval(
            actor=self.builder,
            rationale="First submission.",
        )["gate"]
        with self.assertRaises(ConflictError) as context:
            self.service.approve_stage(
                actor=self.owner,
                gate_id=gate["id"],
                accept_as_is=True,
            )
        self.assertEqual(context.exception.code, "revision_limit_not_reached")

    def test_tri_mode_question_is_recorded(self) -> None:
        for mode in ("guide", "edit-file", "chat"):
            result = self.service.answer_question(
                actor=self.builder,
                mode=mode,
                prompt=f"Prompt for {mode}",
                answer=f"Answer for {mode}",
            )
            self.assertEqual(result["question"]["mode"], mode)
        self.assertEqual(len(self.repository.load()["questions"]), 3)

    def test_ambiguous_auto_scope_requires_composition(self) -> None:
        repository = JsonProjectRepository(
            self.workspace / "ambiguous",
            DeterministicValueProvider(
                seed="ambiguous",
                base_time=datetime(2026, 8, 30, 11, 0, tzinfo=timezone.utc),
            ),
        )
        service = LifecycleService(repository)
        with self.assertRaises(ValidationError) as context:
            service.initialize(
                name="Ambiguous scope",
                description="Fix a CVE in broken infrastructure.",
                creator=self.owner,
                scope="auto",
            )
        self.assertEqual(context.exception.code, "scope_composition_required")

    def test_agent_cannot_approve_stage(self) -> None:
        self.register_current_outputs(self.repository, self.service)
        gate = self.service.request_approval(
            actor=self.builder,
            rationale="Evidence is ready.",
        )["gate"]
        with self.assertRaises(AuthorizationError):
            self.service.approve_stage(actor=self.builder, gate_id=gate["id"])

    def test_invalid_actor_kind_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Actor("bad_actor", "robot")


class CurrentV2VariantTests(WorkspaceTestCase):
    def test_greenfield_plan_skips_reverse_engineering(self) -> None:
        repository, _ = self.create_project(
            scope="feature",
            workspace_kind="greenfield",
            seed="greenfield-plan",
        )
        state = repository.load()
        self.assertEqual(
            state["stages"]["reverse-engineering"]["decision"],
            "skip",
        )
        self.assertEqual(
            state["stages"]["reverse-engineering"]["status"],
            "skipped",
        )

    def test_express_scope_opens_gate_without_reviewer_dispatch(self) -> None:
        repository, service = self.create_project(
            scope="express",
            workspace_kind="brownfield",
            seed="express-review-cap",
        )
        self.assertEqual(
            repository.load()["workflow"]["current_stage"],
            "reverse-engineering",
        )
        self.register_current_outputs(repository, service)
        gate = service.request_approval(
            actor=self.builder,
            rationale="Express evidence is complete without reviewer dispatch.",
        )["gate"]
        self.assertEqual(gate["status"], "pending")
        self.assertEqual(repository.load()["reviews"], {})


if __name__ == "__main__":
    unittest.main()
