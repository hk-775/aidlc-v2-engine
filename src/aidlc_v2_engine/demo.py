"""Deterministic, industry-neutral AI-DLC v2 bugfix demonstration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aidlc_v2_engine.catalog import STAGE_BY_SLUG, required_outputs
from aidlc_v2_engine.models import Actor
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.service import LifecycleService, sha256_digest
from aidlc_v2_engine.values import DeterministicValueProvider


def run_demo(store: str | Path) -> dict[str, Any]:
    provider = DeterministicValueProvider(
        seed="aidlc-v2-engine-synthetic-demo-v1",
        base_time=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
    )
    repository = JsonProjectRepository(store, provider)
    service = LifecycleService(repository)
    owner = Actor("human_owner", "human", ("workflow_owner",))
    builder = Actor("aidlc-developer-agent", "agent")
    product_reviewer = Actor("aidlc-product-lead-agent", "agent")
    architecture_reviewer = Actor("aidlc-architecture-reviewer-agent", "agent")

    service.initialize(
        name="Synthetic parser repair",
        description="Fix a deterministic parser bug in a synthetic local library.",
        creator=owner,
        workspace_kind="brownfield",
        scope="bugfix",
    )

    visited: list[str] = []
    while repository.load()["workflow"]["status"] != "completed":
        state = repository.load()
        if state["workflow"]["autonomy_prompt_pending"]:
            service.set_autonomy(actor=owner, mode="gated")
            state = repository.load()
        stage = state["workflow"]["current_stage"]
        unit_id = state["workflow"]["current_unit_id"]
        if stage is None:
            break
        visited.append(stage)
        definition = STAGE_BY_SLUG[stage]
        unit_kind = state["units"][unit_id]["kind"] if unit_id is not None else None
        for name in required_outputs(stage, unit_kind):
            content = (
                f"Synthetic {name} for {stage}.\n"
                "No customer, personal, credential, or production data is present.\n"
            ).encode()
            service.register_artifact(
                actor=builder,
                name=name,
                title=name.replace("-", " ").title(),
                digest=sha256_digest(content),
                locator=(
                    f"evidence/{unit_id}/{stage}/{name}.md"
                    if unit_id is not None
                    else f"evidence/{stage}/{name}.md"
                ),
                workspace_change=stage == "code-generation" and name == "code-summary",
            )
        service.answer_question(
            actor=builder,
            mode="chat",
            prompt=f"What is the bounded outcome for {stage}?",
            answer=f"Produce only the declared synthetic outputs for {stage}.",
        )
        for sensor in definition.sensors:
            service.record_sensor(
                actor=builder,
                sensor=sensor,
                status="pass",
                summary="Synthetic deterministic sensor pass.",
            )
        if definition.reviewer == "aidlc-product-lead-agent":
            service.record_review(
                actor=product_reviewer,
                verdict="ready",
                summary="Synthetic product review is READY.",
            )
        elif definition.reviewer == "aidlc-architecture-reviewer-agent":
            service.record_review(
                actor=architecture_reviewer,
                verdict="ready",
                summary="Synthetic architecture review is READY.",
            )
        gate = service.request_approval(
            actor=builder,
            rationale=f"Declared outputs for {stage} are complete.",
        )["gate"]
        service.approve_stage(actor=owner, gate_id=gate["id"])

    state = repository.load()
    verification = repository.verify_audit()
    return {
        "store": str(Path(store)),
        "project_id": state["project"]["id"],
        "project_name": state["project"]["name"],
        "scope": state["workflow"]["scope"],
        "status": state["workflow"]["status"],
        "visited_stages": visited,
        "artifact_count": len(state["artifacts"]),
        "gate_count": len(state["gates"]),
        "unit_count": len(state["units"]),
        "event_count": verification["event_count"],
        "audit_valid": verification["valid"],
    }
