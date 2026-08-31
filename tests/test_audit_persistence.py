from __future__ import annotations

import json
import os
import unittest

from aidlc_v2_engine.audit import canonical_bytes
from aidlc_v2_engine.errors import ConflictError, IntegrityError, PersistenceError
from aidlc_v2_engine.models import Actor
from aidlc_v2_engine.persistence import JsonProjectRepository

from tests.support import WorkspaceTestCase


class AuditPersistenceTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository, self.service = self.create_project()

    def test_audit_chain_binds_current_state(self) -> None:
        self.service.answer_question(
            actor=self.builder,
            mode="chat",
            prompt="What is being repaired?",
            answer="A synthetic parser edge case.",
        )
        verification = self.repository.verify_audit()
        self.assertTrue(verification["valid"])
        self.assertEqual(verification["event_count"], 2)

    def test_event_tampering_is_detected(self) -> None:
        event_path = sorted(self.repository.audit_dir.iterdir())[0]
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["payload"]["scope"] = "enterprise"
        os.chmod(event_path, 0o600)
        event_path.write_bytes(canonical_bytes(event) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_state_tampering_is_detected(self) -> None:
        state = json.loads(self.repository.state_path.read_text(encoding="utf-8"))
        state["workflow"]["depth"] = "comprehensive"
        self.repository.state_path.write_bytes(canonical_bytes(state) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.load()

    def test_policy_tampering_is_detected(self) -> None:
        policy = json.loads(self.repository.policy_path.read_text(encoding="utf-8"))
        policy["limits"]["max_artifacts"] += 1
        self.repository.policy_path.write_bytes(canonical_bytes(policy) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.load()

    def test_failed_mutation_does_not_advance_revision(self) -> None:
        before = self.repository.load()
        with self.assertRaises(ConflictError):
            self.service.request_approval(
                actor=self.builder,
                rationale="No outputs exist.",
            )
        after = self.repository.load()
        self.assertEqual(after["revision"], before["revision"])
        self.assertEqual(after["audit"], before["audit"])

    def test_second_initialization_is_rejected(self) -> None:
        with self.assertRaises(ConflictError):
            self.service.initialize(
                name="Duplicate",
                description="Duplicate initialization.",
                creator=self.owner,
                workspace_kind="brownfield",
                scope="bugfix",
            )

    def test_symlink_storage_root_is_rejected(self) -> None:
        target = self.workspace / "real"
        target.mkdir()
        link = self.workspace / "link"
        link.symlink_to(target, target_is_directory=True)
        repository = JsonProjectRepository(link)
        with self.assertRaises(PersistenceError):
            repository.initialize(
                name="Unsafe",
                description="Synthetic symlink check.",
                creator=Actor("human_owner", "human", ("workflow_owner",)),
                policy=self.repository.load_policy(),
                workspace_kind="brownfield",
                scope="bugfix",
                scope_source="explicit",
                depth="minimal",
                test_strategy="minimal",
                plan={
                    slug: record["decision"]
                    for slug, record in self.repository.load()["stages"].items()
                },
            )


if __name__ == "__main__":
    unittest.main()
