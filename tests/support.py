from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aidlc_v2_engine.catalog import SCOPE_CONFIG, STAGE_BY_SLUG, required_outputs
from aidlc_v2_engine.models import Actor
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.service import LifecycleService, sha256_digest
from aidlc_v2_engine.values import DeterministicValueProvider

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix=f"aidlc-v2-{self.__class__.__name__}-"
        )
        self.workspace = Path(self.temporary_directory.name)
        self.owner = Actor("human_owner", "human", ("workflow_owner",))
        self.other_human = Actor("human_reviewer", "human", ("human_reviewer",))
        self.builder = Actor("aidlc-developer-agent", "agent")
        self.product_reviewer = Actor("aidlc-product-lead-agent", "agent")
        self.architecture_reviewer = Actor(
            "aidlc-architecture-reviewer-agent",
            "agent",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_project(
        self,
        *,
        scope: str = "bugfix",
        workspace_kind: str = "brownfield",
        description: str = "Fix a deterministic parser bug.",
        policy: dict[str, Any] | None = None,
        seed: str = "test-seed",
    ) -> tuple[JsonProjectRepository, LifecycleService]:
        provider = DeterministicValueProvider(
            seed=seed,
            base_time=datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc),
        )
        repository = JsonProjectRepository(self.workspace / "project", provider)
        service = LifecycleService(repository)
        service.initialize(
            name="Synthetic workflow",
            description=description,
            creator=self.owner,
            workspace_kind=workspace_kind,
            scope=scope,
            policy=policy,
        )
        return repository, service

    def register_current_outputs(
        self,
        repository: JsonProjectRepository,
        service: LifecycleService,
        *,
        actor: Actor | None = None,
    ) -> list[dict[str, Any]]:
        actor = actor or self.builder
        state = repository.load()
        stage = state["workflow"]["current_stage"]
        unit_id = state["workflow"]["current_unit_id"]
        self.assertIsNotNone(stage)
        unit_kind = state["units"][unit_id]["kind"] if unit_id is not None else None
        artifacts = []
        for name in required_outputs(stage, unit_kind):
            artifacts.append(
                service.register_artifact(
                    actor=actor,
                    name=name,
                    title=name.replace("-", " ").title(),
                    digest=sha256_digest(
                        f"{stage}:{unit_id or 'global'}:{name}".encode()
                    ),
                    locator=(
                        f"evidence/{unit_id}/{stage}/{name}.md"
                        if unit_id is not None
                        else f"evidence/{stage}/{name}.md"
                    ),
                    workspace_change=stage == "code-generation",
                )["artifact"]
            )
        return artifacts

    def record_current_review(
        self,
        repository: JsonProjectRepository,
        service: LifecycleService,
        *,
        verdict: str = "ready",
    ) -> dict[str, Any] | None:
        stage = repository.load()["workflow"]["current_stage"]
        self.assertIsNotNone(stage)
        reviewer = STAGE_BY_SLUG[stage].reviewer
        scope = repository.load()["workflow"]["scope"]
        if reviewer is None or SCOPE_CONFIG[scope]["review_cap"] == "none":
            return None
        actor = (
            self.product_reviewer
            if reviewer == "aidlc-product-lead-agent"
            else self.architecture_reviewer
        )
        return service.record_review(
            actor=actor,
            verdict=verdict,
            summary=f"Synthetic {verdict} review.",
        )["review"]

    def complete_current_stage(
        self,
        repository: JsonProjectRepository,
        service: LifecycleService,
        *,
        requester: Actor | None = None,
        approver: Actor | None = None,
    ) -> dict[str, Any]:
        requester = requester or self.builder
        approver = approver or self.owner
        state = repository.load()
        stage = state["workflow"]["current_stage"]
        self.assertIsNotNone(stage)
        if STAGE_BY_SLUG[stage].is_per_unit and state["units"]:
            while repository.load()["workflow"]["current_unit_id"] is not None:
                self.register_current_outputs(repository, service, actor=requester)
                self.record_current_review(repository, service)
                service.complete_unit_stage(actor=requester)
        else:
            self.register_current_outputs(repository, service, actor=requester)
            self.record_current_review(repository, service)
        gate = service.request_approval(
            actor=requester,
            rationale="Declared synthetic outputs are complete.",
        )["gate"]
        result = service.approve_stage(actor=approver, gate_id=gate["id"])
        if repository.load()["workflow"]["autonomy_prompt_pending"]:
            service.set_autonomy(actor=approver, mode="gated")
        return result

    def complete_workflow(
        self,
        repository: JsonProjectRepository,
        service: LifecycleService,
    ) -> None:
        while repository.load()["workflow"]["status"] == "running":
            self.complete_current_stage(repository, service)
