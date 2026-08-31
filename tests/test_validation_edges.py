from __future__ import annotations

import unittest

from aidlc_v2_engine.errors import ConflictError

from tests.support import WorkspaceTestCase


class NavigationAndLearningTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository, self.service = self.create_project()

    def test_depth_and_test_strategy_change_independently(self) -> None:
        self.service.set_depth(actor=self.owner, depth="comprehensive")
        self.service.set_test_strategy(actor=self.owner, test_strategy="standard")
        workflow = self.repository.load()["workflow"]
        self.assertEqual(workflow["depth"], "comprehensive")
        self.assertEqual(workflow["test_strategy"], "standard")

    def test_recompose_adds_pending_stage(self) -> None:
        result = self.service.recompose(
            actor=self.owner,
            add=["ci-pipeline"],
            reason="Exercise CI pipeline generation for this repair.",
        )
        self.assertEqual(result["plan"]["ci-pipeline"], "execute")
        self.assertEqual(result["workflow"]["scope_source"], "composed")

    def test_recompose_cannot_move_walking_skeleton_anchor(self) -> None:
        with self.assertRaises(ConflictError) as context:
            self.service.recompose(
                actor=self.owner,
                add=["functional-design"],
                reason="Attempt to move the first Construction stage.",
            )
        self.assertEqual(context.exception.code, "walking_skeleton_anchor_frozen")

    def test_skip_current_inception_stage(self) -> None:
        self.service.skip_current_stage(
            actor=self.owner,
            reason="Existing code knowledge is already current.",
        )
        state = self.repository.load()
        self.assertEqual(state["stages"]["reverse-engineering"]["status"], "skipped")
        self.assertEqual(state["workflow"]["current_stage"], "requirements-analysis")

    def test_jump_to_later_stage_records_skips(self) -> None:
        self.service.jump_to_stage(
            actor=self.owner,
            target_stage="code-generation",
            reason="Use an approved emergency repair path.",
        )
        state = self.repository.load()
        self.assertEqual(state["workflow"]["current_stage"], "code-generation")
        self.assertEqual(state["stages"]["reverse-engineering"]["status"], "skipped")
        self.assertEqual(state["stages"]["requirements-analysis"]["status"], "skipped")
        self.assertIsNone(state["workflow"]["current_unit_id"])
        self.assertEqual(state["units"], {})

    def test_park_and_resume_preserve_cursor(self) -> None:
        before = self.repository.load()["workflow"]["current_stage"]
        self.service.park(actor=self.owner, reason="Pause for human availability.")
        self.assertEqual(self.repository.load()["workflow"]["status"], "parked")
        self.service.resume(actor=self.owner)
        workflow = self.repository.load()["workflow"]
        self.assertEqual(workflow["status"], "running")
        self.assertEqual(workflow["current_stage"], before)

    def test_learning_applies_next_workflow(self) -> None:
        learning = self.service.propose_learning(
            actor=self.builder,
            section="tradeoff",
            summary="Prefer a bounded parser fixture before broad fuzzing.",
        )["learning"]
        decided = self.service.decide_learning(
            actor=self.owner,
            learning_id=learning["id"],
            decision="keep",
            target_scope="project",
        )["learning"]
        self.assertEqual(decided["status"], "kept")
        event = self.repository.list_events()[-1]
        self.assertEqual(event["payload"]["effective"], "next-workflow")

    def test_open_question_cannot_be_promoted(self) -> None:
        learning = self.service.propose_learning(
            actor=self.builder,
            section="open-question",
            summary="Should the parser accept comments?",
        )["learning"]
        with self.assertRaises(ConflictError):
            self.service.decide_learning(
                actor=self.owner,
                learning_id=learning["id"],
                decision="keep",
                target_scope="project",
            )

    def test_completed_operation_can_loop_to_ideation(self) -> None:
        self.complete_workflow(self.repository, self.service)
        result = self.service.loop_to_ideation(
            actor=self.owner,
            reason="Production feedback requires another repair iteration.",
        )
        self.assertEqual(result["workflow"]["status"], "running")
        self.assertEqual(result["workflow"]["iteration"], 2)
        self.assertEqual(result["workflow"]["current_stage"], "reverse-engineering")


if __name__ == "__main__":
    unittest.main()
