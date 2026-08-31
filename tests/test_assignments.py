from __future__ import annotations

import unittest

from aidlc_v2_engine.errors import ConflictError

from tests.support import WorkspaceTestCase


class ConstructionStageMajorTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository, self.service = self.create_project(scope="feature")
        self.service.jump_to_stage(
            actor=self.owner,
            target_stage="units-generation",
            reason="Focus this test on current-v2 Construction routing.",
        )
        self.first_id, self.second_id = self._add_two_units()
        for _ in range(3):
            self.complete_current_stage(self.repository, self.service)
        state = self.repository.load()
        self.assertEqual(state["workflow"]["current_stage"], "functional-design")
        self.assertEqual(state["workflow"]["current_unit_id"], self.first_id)

    def _add_two_units(self) -> tuple[str, str]:
        first = self.service.add_unit(
            actor=self.builder,
            name="Walking skeleton",
            kind="service",
        )["unit"]
        second = self.service.add_unit(
            actor=self.builder,
            name="Follow-on library",
            kind="library",
            dependencies=[first["id"]],
        )["unit"]
        return first["id"], second["id"]

    def _settle_current_unit(self) -> None:
        self.register_current_outputs(self.repository, self.service)
        self.record_current_review(self.repository, self.service)
        self.service.complete_unit_stage(actor=self.builder)

    def _approve_walking_skeleton_stage(self) -> None:
        self._settle_current_unit()
        self._settle_current_unit()
        state = self.repository.load()
        self.assertIsNone(state["workflow"]["current_unit_id"])
        gate = self.service.request_approval(
            actor=self.builder,
            rationale="Functional design is ready for every Unit.",
        )["gate"]
        self.assertIsNone(gate["unit_id"])
        self.service.approve_stage(actor=self.owner, gate_id=gate["id"])
        state = self.repository.load()
        self.assertTrue(state["workflow"]["autonomy_prompt_pending"])
        self.assertEqual(state["workflow"]["current_stage"], "nfr-requirements")
        self.assertEqual(state["workflow"]["current_unit_id"], self.first_id)

    def test_first_unit_is_walking_skeleton(self) -> None:
        state = self.repository.load()
        self.assertTrue(state["units"][self.first_id]["walking_skeleton"])
        self.assertFalse(state["units"][self.second_id]["walking_skeleton"])

    def test_default_construction_walk_is_stage_major(self) -> None:
        self._settle_current_unit()
        state = self.repository.load()
        self.assertEqual(state["workflow"]["current_stage"], "functional-design")
        self.assertEqual(state["workflow"]["current_unit_id"], self.second_id)
        self.assertEqual(
            state["units"][self.first_id]["stage_statuses"]["functional-design"],
            "awaiting_approval",
        )
        self._settle_current_unit()
        state = self.repository.load()
        self.assertIsNone(state["workflow"]["current_unit_id"])
        self.assertEqual(state["stages"]["functional-design"]["status"], "active")

    def test_autonomous_mode_skips_later_construction_stage_gate(self) -> None:
        self._approve_walking_skeleton_stage()
        self.service.set_autonomy(actor=self.owner, mode="autonomous")
        self.register_current_outputs(self.repository, self.service)
        self.record_current_review(self.repository, self.service)
        self.service.complete_autonomous_stage(actor=self.builder)
        self.assertEqual(
            self.repository.load()["workflow"]["current_unit_id"],
            self.second_id,
        )
        self.register_current_outputs(self.repository, self.service)
        self.record_current_review(self.repository, self.service)
        self.service.complete_autonomous_stage(actor=self.builder)
        state = self.repository.load()
        self.assertEqual(state["workflow"]["current_stage"], "nfr-design")
        self.assertEqual(state["workflow"]["current_unit_id"], self.first_id)
        self.assertEqual(
            state["stages"]["nfr-requirements"]["status"],
            "completed",
        )

    def test_failure_halts_until_human_retries(self) -> None:
        self._approve_walking_skeleton_stage()
        self.service.set_autonomy(actor=self.owner, mode="autonomous")
        self.service.fail_bolt(
            actor=self.builder,
            summary="Synthetic compiler failure.",
        )
        with self.assertRaises(ConflictError) as context:
            self.register_current_outputs(self.repository, self.service)
        self.assertEqual(context.exception.code, "bolt_failure_action_required")
        self.service.resolve_bolt_failure(actor=self.owner, action="retry")
        self.assertIsNone(self.repository.load()["workflow"]["failure"])

    def test_failed_non_skeleton_unit_can_be_skipped(self) -> None:
        self._approve_walking_skeleton_stage()
        self.service.set_autonomy(actor=self.owner, mode="autonomous")
        self.register_current_outputs(self.repository, self.service)
        self.record_current_review(self.repository, self.service)
        self.service.complete_autonomous_stage(actor=self.builder)
        self.service.fail_bolt(actor=self.builder, summary="Synthetic failure.")
        self.service.resolve_bolt_failure(actor=self.owner, action="skip")
        state = self.repository.load()
        self.assertEqual(state["units"][self.second_id]["status"], "skipped")
        self.assertEqual(state["workflow"]["current_stage"], "nfr-design")
        self.assertEqual(state["workflow"]["current_unit_id"], self.first_id)

    def test_walking_skeleton_cannot_be_skipped_after_failure(self) -> None:
        self._approve_walking_skeleton_stage()
        self.service.set_autonomy(actor=self.owner, mode="autonomous")
        self.service.fail_bolt(actor=self.builder, summary="Skeleton failed.")
        with self.assertRaises(ConflictError) as context:
            self.service.resolve_bolt_failure(actor=self.owner, action="skip")
        self.assertEqual(context.exception.code, "walking_skeleton_required")

    def test_units_freeze_after_delivery_planning_boundary(self) -> None:
        with self.assertRaises(ConflictError) as context:
            self.service.add_unit(
                actor=self.builder,
                name="Late Unit",
                kind="service",
            )
        self.assertEqual(context.exception.code, "unit_plan_frozen")


if __name__ == "__main__":
    unittest.main()
