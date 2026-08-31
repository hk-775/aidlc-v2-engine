"""Core value objects and strict structural validation for AI-DLC v2 state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable

from aidlc_v2_engine.catalog import (
    DEPTH_LEVELS,
    PER_UNIT_STAGES,
    PHASES,
    SCOPES,
    STAGE_BY_SLUG,
    STAGE_SLUGS,
    TEST_STRATEGIES,
    UNIT_KINDS,
)
from aidlc_v2_engine.errors import ValidationError

WORKFLOW_STATUSES = {"running", "parked", "completed", "aborted"}
PHASE_STATUSES = {"pending", "active", "verified", "skipped"}
STAGE_STATUSES = {
    "pending",
    "active",
    "awaiting_approval",
    "revising",
    "completed",
    "skipped",
}
GATE_STATUSES = {"pending", "approved", "rejected", "superseded"}
QUESTION_MODES = {"guide", "edit-file", "chat"}
SENSOR_STATUSES = {"pass", "warn", "fail"}
REVIEW_VERDICTS = {"ready", "not-ready"}
UNIT_STATUSES = {"planned", "active", "completed", "failed", "skipped"}
LEARNING_STATUSES = {"candidate", "kept", "rejected"}
LEARNING_SCOPES = {"project", "team"}

GOVERNANCE_ROLES = {
    "workflow_owner",
    "human_reviewer",
    "risk_owner",
    "release_manager",
}

HARD_DENIED_AGENT_OPERATIONS = {
    "approve_stage",
    "reject_stage",
    "accept_as_is",
    "recompose",
    "skip_stage",
    "jump_stage",
    "redo_stage",
    "set_depth",
    "set_test_strategy",
    "set_autonomy",
    "resolve_bolt_failure",
    "accept_learning",
    "park_workflow",
    "resume_workflow",
    "loop_workflow",
    "merge",
    "deploy",
    "release",
    "accept_risk",
    "bypass_gate",
}

AGENT_PERMISSION_KEYS = {
    "register_artifact",
    "answer_question",
    "record_sensor",
    "record_review",
    "request_approval",
    "complete_unit_stage",
    "complete_autonomous_stage",
    "add_unit",
    "fail_bolt",
    "propose_learning",
    *HARD_DENIED_AGENT_OPERATIONS,
}

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
ARTIFACT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
LOCATOR_MAX_LENGTH = 1024


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_identifier(value: Any, label: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValidationError(
            f"{label} is not a portable identifier",
            details={"field": label, "value": value},
        )
    return value


def validate_text(
    value: Any,
    label: str,
    *,
    minimum: int = 1,
    maximum: int = 500,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string", details={"field": label})
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ValidationError(
            f"{label} length must be between {minimum} and {maximum}",
            details={"field": label, "length": len(normalized)},
        )
    if any(ord(character) < 32 and character not in "\t\n" for character in normalized):
        raise ValidationError(
            f"{label} contains unsupported control characters",
            details={"field": label},
        )
    return normalized


def validate_locator(locator: Any) -> str:
    if not isinstance(locator, str):
        raise ValidationError("artifact locator must be a string")
    normalized = locator.strip()
    if not normalized:
        return ""
    if len(normalized) > LOCATOR_MAX_LENGTH:
        raise ValidationError(
            f"artifact locator cannot exceed {LOCATOR_MAX_LENGTH} characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValidationError("artifact locator contains unsupported control characters")
    if "\\" in normalized:
        raise ValidationError("artifact locator must use portable forward slashes")
    path = PurePosixPath(normalized)
    segments = normalized.split("/")
    if (
        path.is_absolute()
        or not path.parts
        or any(segment in {"", ".", ".."} for segment in segments)
        or ":" in segments[0]
    ):
        raise ValidationError("artifact locator must be a normalized safe relative path")
    return normalized


def validate_stage(stage: Any) -> str:
    if not isinstance(stage, str) or stage not in STAGE_BY_SLUG:
        raise ValidationError(
            "stage is not part of the pinned AI-DLC v2 lifecycle",
            details={"stage": stage, "allowed": list(STAGE_SLUGS)},
        )
    return stage


def validate_scope(scope: Any) -> str:
    if not isinstance(scope, str) or scope not in SCOPES:
        raise ValidationError(
            "scope is not an AI-DLC v2 scope",
            details={"scope": scope, "allowed": list(SCOPES)},
        )
    return scope


def validate_depth(depth: Any) -> str:
    if not isinstance(depth, str) or depth not in DEPTH_LEVELS:
        raise ValidationError(
            "depth is invalid",
            details={"depth": depth, "allowed": list(DEPTH_LEVELS)},
        )
    return depth


def validate_test_strategy(strategy: Any) -> str:
    if not isinstance(strategy, str) or strategy not in TEST_STRATEGIES:
        raise ValidationError(
            "test strategy is invalid",
            details={"test_strategy": strategy, "allowed": list(TEST_STRATEGIES)},
        )
    return strategy


def validate_unit_kind(kind: Any) -> str:
    if not isinstance(kind, str) or kind not in UNIT_KINDS:
        raise ValidationError(
            "unit kind is invalid",
            details={"kind": kind, "allowed": list(UNIT_KINDS)},
        )
    return kind


def require_exact_keys(
    value: dict[str, Any],
    expected: Iterable[str],
    label: str,
) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        raise ValidationError(
            f"{label} has unexpected or missing fields",
            details={
                "field": label,
                "missing": sorted(expected_set - actual_set),
                "unexpected": sorted(actual_set - expected_set),
            },
        )


def _validate_timestamp(value: Any, label: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not TIMESTAMP_PATTERN.fullmatch(value):
        raise ValidationError(f"{label} must be a UTC ISO-8601 timestamp")


def _validate_optional_identifier(value: Any, label: str) -> None:
    if value is not None:
        _validate_identifier(value, label, ID_PATTERN)


def _validate_string_list(
    value: Any,
    label: str,
    *,
    pattern: re.Pattern[str],
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be an array")
    if not allow_empty and not value:
        raise ValidationError(f"{label} cannot be empty")
    if any(not isinstance(item, str) or not pattern.fullmatch(item) for item in value):
        raise ValidationError(f"{label} contains an invalid value")
    if len(value) != len(set(value)):
        raise ValidationError(f"{label} cannot contain duplicates")
    return value


@dataclass(frozen=True, slots=True)
class Actor:
    """A caller identity asserted by the embedding environment."""

    actor_id: str
    kind: str
    roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.actor_id, "actor_id", ID_PATTERN)
        if self.kind not in {"human", "agent"}:
            raise ValidationError(
                "actor kind must be human or agent",
                details={"kind": self.kind},
            )
        if not isinstance(self.roles, (list, tuple)) or any(
            not isinstance(role, str) for role in self.roles
        ):
            raise ValidationError("actor roles must be role identifiers")
        if len(self.roles) > 20:
            raise ValidationError("actor cannot hold more than 20 roles")
        for role in self.roles:
            _validate_identifier(role, "role", ROLE_PATTERN)
        normalized_roles = tuple(sorted(set(self.roles)))
        if self.kind == "agent" and GOVERNANCE_ROLES.intersection(normalized_roles):
            raise ValidationError(
                "agents cannot claim human governance roles",
                code="agent_governance_role_forbidden",
                details={"roles": sorted(GOVERNANCE_ROLES.intersection(normalized_roles))},
            )
        object.__setattr__(self, "roles", normalized_roles)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.actor_id,
            "kind": self.kind,
            "roles": list(self.roles),
        }


def validate_actor_record(value: Any, label: str = "actor") -> Actor:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    require_exact_keys(value, {"id", "kind", "roles"}, label)
    roles = value["roles"]
    if not isinstance(roles, list):
        raise ValidationError(f"{label}.roles must be an array")
    return Actor(value["id"], value["kind"], tuple(roles))


def _validate_project(project: Any) -> None:
    if not isinstance(project, dict):
        raise ValidationError("project must be an object")
    require_exact_keys(
        project,
        {
            "id",
            "name",
            "description",
            "workspace_kind",
            "created_at",
            "created_by",
        },
        "project",
    )
    _validate_identifier(project["id"], "project.id", ID_PATTERN)
    validate_text(project["name"], "project.name", maximum=120)
    validate_text(project["description"], "project.description", minimum=0, maximum=4000)
    if project["workspace_kind"] not in {"greenfield", "brownfield"}:
        raise ValidationError("project.workspace_kind must be greenfield or brownfield")
    _validate_timestamp(project["created_at"], "project.created_at")
    _validate_identifier(project["created_by"], "project.created_by", ID_PATTERN)


def _validate_failure(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValidationError("workflow.failure must be an object or null")
    require_exact_keys(
        value,
        {"unit_id", "stage", "summary", "failed_at", "reported_by"},
        "workflow.failure",
    )
    _validate_identifier(value["unit_id"], "workflow.failure.unit_id", ID_PATTERN)
    validate_stage(value["stage"])
    validate_text(value["summary"], "workflow.failure.summary", maximum=1000)
    _validate_timestamp(value["failed_at"], "workflow.failure.failed_at")
    _validate_identifier(value["reported_by"], "workflow.failure.reported_by", ID_PATTERN)


def _validate_workflow(workflow: Any) -> None:
    if not isinstance(workflow, dict):
        raise ValidationError("workflow must be an object")
    require_exact_keys(
        workflow,
        {
            "status",
            "scope",
            "scope_source",
            "depth",
            "test_strategy",
            "iteration",
            "current_stage",
            "current_unit_id",
            "last_completed_stage",
            "construction_autonomy",
            "autonomy_prompt_pending",
            "composition_revision",
            "started_at",
            "parked_at",
            "completed_at",
            "failure",
        },
        "workflow",
    )
    if workflow["status"] not in WORKFLOW_STATUSES:
        raise ValidationError("workflow.status is invalid")
    validate_scope(workflow["scope"])
    if workflow["scope_source"] not in {"explicit", "auto", "composed"}:
        raise ValidationError("workflow.scope_source is invalid")
    validate_depth(workflow["depth"])
    validate_test_strategy(workflow["test_strategy"])
    if not _is_integer(workflow["iteration"]) or workflow["iteration"] < 1:
        raise ValidationError("workflow.iteration must be a positive integer")
    if workflow["current_stage"] is not None:
        validate_stage(workflow["current_stage"])
    _validate_optional_identifier(
        workflow["current_unit_id"],
        "workflow.current_unit_id",
    )
    if workflow["last_completed_stage"] is not None:
        validate_stage(workflow["last_completed_stage"])
    if workflow["construction_autonomy"] not in {None, "gated", "autonomous"}:
        raise ValidationError("workflow.construction_autonomy is invalid")
    if not isinstance(workflow["autonomy_prompt_pending"], bool):
        raise ValidationError("workflow.autonomy_prompt_pending must be boolean")
    if (
        not _is_integer(workflow["composition_revision"])
        or workflow["composition_revision"] < 1
    ):
        raise ValidationError("workflow.composition_revision must be positive")
    _validate_timestamp(workflow["started_at"], "workflow.started_at")
    _validate_timestamp(workflow["parked_at"], "workflow.parked_at", nullable=True)
    _validate_timestamp(workflow["completed_at"], "workflow.completed_at", nullable=True)
    _validate_failure(workflow["failure"])
    if workflow["status"] in {"completed", "aborted"} and workflow["current_stage"] is not None:
        raise ValidationError("terminal workflows cannot have a current stage")
    if workflow["status"] == "parked" and workflow["parked_at"] is None:
        raise ValidationError("parked workflows require workflow.parked_at")
    if workflow["status"] == "completed" and workflow["completed_at"] is None:
        raise ValidationError("completed workflows require workflow.completed_at")


def _validate_phases(phases: Any) -> None:
    if not isinstance(phases, dict):
        raise ValidationError("phases must be an object")
    require_exact_keys(phases, PHASES, "phases")
    for phase, record in phases.items():
        if not isinstance(record, dict):
            raise ValidationError(f"phases.{phase} must be an object")
        require_exact_keys(record, {"status", "verified_at"}, f"phases.{phase}")
        if record["status"] not in PHASE_STATUSES:
            raise ValidationError(f"phases.{phase}.status is invalid")
        _validate_timestamp(
            record["verified_at"],
            f"phases.{phase}.verified_at",
            nullable=True,
        )
        if record["status"] == "verified" and record["verified_at"] is None:
            raise ValidationError(f"phases.{phase} verified status requires a timestamp")


def _validate_stages(stages: Any) -> None:
    if not isinstance(stages, dict):
        raise ValidationError("stages must be an object")
    require_exact_keys(stages, STAGE_SLUGS, "stages")
    for slug, record in stages.items():
        if not isinstance(record, dict):
            raise ValidationError(f"stages.{slug} must be an object")
        require_exact_keys(
            record,
            {
                "decision",
                "status",
                "revision_count",
                "reviewer_iterations",
                "started_at",
                "completed_at",
                "current_gate_id",
            },
            f"stages.{slug}",
        )
        if record["decision"] not in {"execute", "skip"}:
            raise ValidationError(f"stages.{slug}.decision is invalid")
        if record["status"] not in STAGE_STATUSES:
            raise ValidationError(f"stages.{slug}.status is invalid")
        for field in ("revision_count", "reviewer_iterations"):
            if not _is_integer(record[field]) or record[field] < 0:
                raise ValidationError(f"stages.{slug}.{field} must be non-negative")
        _validate_timestamp(
            record["started_at"],
            f"stages.{slug}.started_at",
            nullable=True,
        )
        _validate_timestamp(
            record["completed_at"],
            f"stages.{slug}.completed_at",
            nullable=True,
        )
        _validate_optional_identifier(
            record["current_gate_id"],
            f"stages.{slug}.current_gate_id",
        )
        if record["decision"] == "skip" and record["status"] != "skipped":
            raise ValidationError(f"stages.{slug} skip decision must have skipped status")
        if record["status"] == "completed" and record["completed_at"] is None:
            raise ValidationError(f"stages.{slug} completion requires a timestamp")


def _validate_artifact(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "name",
            "stage",
            "unit_id",
            "title",
            "digest",
            "locator",
            "workspace_change",
            "submitted_by",
            "submitted_at",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    _validate_identifier(record["name"], f"{label}.name", ARTIFACT_NAME_PATTERN)
    validate_stage(record["stage"])
    _validate_optional_identifier(record["unit_id"], f"{label}.unit_id")
    validate_text(record["title"], f"{label}.title", maximum=200)
    if not isinstance(record["digest"], str) or not DIGEST_PATTERN.fullmatch(
        record["digest"]
    ):
        raise ValidationError(f"{label}.digest must be a lowercase SHA-256 digest")
    if validate_locator(record["locator"]) != record["locator"]:
        raise ValidationError(f"{label}.locator must be normalized")
    if not isinstance(record["workspace_change"], bool):
        raise ValidationError(f"{label}.workspace_change must be boolean")
    _validate_identifier(record["submitted_by"], f"{label}.submitted_by", ID_PATTERN)
    _validate_timestamp(record["submitted_at"], f"{label}.submitted_at")


def _validate_gate(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "stage",
            "unit_id",
            "status",
            "rationale",
            "evidence_ids",
            "requested_by",
            "requested_by_kind",
            "requested_at",
            "decided_by",
            "decided_at",
            "reason",
            "accept_as_is",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    validate_stage(record["stage"])
    _validate_optional_identifier(record["unit_id"], f"{label}.unit_id")
    if record["status"] not in GATE_STATUSES:
        raise ValidationError(f"{label}.status is invalid")
    validate_text(record["rationale"], f"{label}.rationale", maximum=1000)
    _validate_string_list(record["evidence_ids"], f"{label}.evidence_ids", pattern=ID_PATTERN)
    _validate_identifier(record["requested_by"], f"{label}.requested_by", ID_PATTERN)
    if record["requested_by_kind"] not in {"human", "agent"}:
        raise ValidationError(f"{label}.requested_by_kind is invalid")
    _validate_timestamp(record["requested_at"], f"{label}.requested_at")
    _validate_optional_identifier(record["decided_by"], f"{label}.decided_by")
    _validate_timestamp(record["decided_at"], f"{label}.decided_at", nullable=True)
    if record["reason"] is not None:
        validate_text(record["reason"], f"{label}.reason", maximum=1000)
    if not isinstance(record["accept_as_is"], bool):
        raise ValidationError(f"{label}.accept_as_is must be boolean")
    resolved = record["status"] in {"approved", "rejected", "superseded"}
    if resolved != (record["decided_at"] is not None):
        raise ValidationError(f"{label} resolution fields conflict with status")
    if record["status"] in {"approved", "rejected"} and record["decided_by"] is None:
        raise ValidationError(f"{label} resolved status requires decided_by")


def _validate_question(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "stage",
            "unit_id",
            "mode",
            "prompt",
            "answer",
            "answered_by",
            "answered_at",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    validate_stage(record["stage"])
    _validate_optional_identifier(record["unit_id"], f"{label}.unit_id")
    if record["mode"] not in QUESTION_MODES:
        raise ValidationError(f"{label}.mode is invalid")
    validate_text(record["prompt"], f"{label}.prompt", maximum=1000)
    validate_text(record["answer"], f"{label}.answer", maximum=10000)
    _validate_identifier(record["answered_by"], f"{label}.answered_by", ID_PATTERN)
    _validate_timestamp(record["answered_at"], f"{label}.answered_at")


def _validate_sensor(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "stage",
            "unit_id",
            "sensor",
            "status",
            "summary",
            "recorded_by",
            "recorded_at",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    validate_stage(record["stage"])
    _validate_optional_identifier(record["unit_id"], f"{label}.unit_id")
    _validate_identifier(record["sensor"], f"{label}.sensor", ARTIFACT_NAME_PATTERN)
    if record["status"] not in SENSOR_STATUSES:
        raise ValidationError(f"{label}.status is invalid")
    validate_text(record["summary"], f"{label}.summary", maximum=1000)
    _validate_identifier(record["recorded_by"], f"{label}.recorded_by", ID_PATTERN)
    _validate_timestamp(record["recorded_at"], f"{label}.recorded_at")


def _validate_review(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "stage",
            "unit_id",
            "reviewer",
            "verdict",
            "iteration",
            "summary",
            "recorded_at",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    validate_stage(record["stage"])
    _validate_optional_identifier(record["unit_id"], f"{label}.unit_id")
    _validate_identifier(record["reviewer"], f"{label}.reviewer", ID_PATTERN)
    if record["verdict"] not in REVIEW_VERDICTS:
        raise ValidationError(f"{label}.verdict is invalid")
    if not _is_integer(record["iteration"]) or record["iteration"] < 1:
        raise ValidationError(f"{label}.iteration must be positive")
    validate_text(record["summary"], f"{label}.summary", maximum=2000)
    _validate_timestamp(record["recorded_at"], f"{label}.recorded_at")


def _validate_unit(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "name",
            "kind",
            "order",
            "dependencies",
            "walking_skeleton",
            "status",
            "stage_statuses",
            "created_by",
            "created_at",
            "completed_at",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    validate_text(record["name"], f"{label}.name", maximum=120)
    validate_unit_kind(record["kind"])
    if not _is_integer(record["order"]) or record["order"] < 1:
        raise ValidationError(f"{label}.order must be positive")
    _validate_string_list(
        record["dependencies"],
        f"{label}.dependencies",
        pattern=ID_PATTERN,
    )
    if not isinstance(record["walking_skeleton"], bool):
        raise ValidationError(f"{label}.walking_skeleton must be boolean")
    if record["status"] not in UNIT_STATUSES:
        raise ValidationError(f"{label}.status is invalid")
    stage_statuses = record["stage_statuses"]
    if not isinstance(stage_statuses, dict):
        raise ValidationError(f"{label}.stage_statuses must be an object")
    require_exact_keys(stage_statuses, PER_UNIT_STAGES, f"{label}.stage_statuses")
    if any(status not in STAGE_STATUSES for status in stage_statuses.values()):
        raise ValidationError(f"{label}.stage_statuses contains an invalid status")
    _validate_identifier(record["created_by"], f"{label}.created_by", ID_PATTERN)
    _validate_timestamp(record["created_at"], f"{label}.created_at")
    _validate_timestamp(record["completed_at"], f"{label}.completed_at", nullable=True)
    if record["status"] == "completed" and record["completed_at"] is None:
        raise ValidationError(f"{label} completed status requires a timestamp")


def _validate_learning(record: dict[str, Any], label: str) -> None:
    require_exact_keys(
        record,
        {
            "id",
            "section",
            "summary",
            "status",
            "target_scope",
            "proposed_by",
            "proposed_at",
            "decided_by",
            "decided_at",
        },
        label,
    )
    _validate_identifier(record["id"], f"{label}.id", ID_PATTERN)
    if record["section"] not in {
        "interpretation",
        "deviation",
        "tradeoff",
        "open-question",
    }:
        raise ValidationError(f"{label}.section is invalid")
    validate_text(record["summary"], f"{label}.summary", maximum=2000)
    if record["status"] not in LEARNING_STATUSES:
        raise ValidationError(f"{label}.status is invalid")
    if record["target_scope"] not in {None, *LEARNING_SCOPES}:
        raise ValidationError(f"{label}.target_scope is invalid")
    _validate_identifier(record["proposed_by"], f"{label}.proposed_by", ID_PATTERN)
    _validate_timestamp(record["proposed_at"], f"{label}.proposed_at")
    _validate_optional_identifier(record["decided_by"], f"{label}.decided_by")
    _validate_timestamp(record["decided_at"], f"{label}.decided_at", nullable=True)
    if record["section"] == "open-question" and record["status"] == "kept":
        raise ValidationError("open questions cannot be promoted to learned rules")


def _validate_collection(
    state: dict[str, Any],
    name: str,
    validator: Any,
) -> None:
    collection = state[name]
    if not isinstance(collection, dict):
        raise ValidationError(f"{name} must be an object")
    for key, record in collection.items():
        _validate_identifier(key, f"{name} key", ID_PATTERN)
        if not isinstance(record, dict) or record.get("id") != key:
            raise ValidationError(f"{name} entries must be objects keyed by id")
        validator(record, f"{name}.{key}")


def validate_state(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise ValidationError("project state must be an object")
    require_exact_keys(
        state,
        {
            "schema_version",
            "project",
            "policy_digest",
            "revision",
            "workflow",
            "phases",
            "stages",
            "artifacts",
            "gates",
            "questions",
            "sensors",
            "reviews",
            "units",
            "learnings",
            "audit",
        },
        "state",
    )
    if state["schema_version"] != 2:
        raise ValidationError("unsupported project state schema version")
    if not _is_integer(state["revision"]) or state["revision"] < 0:
        raise ValidationError("state revision must be non-negative")
    if not isinstance(state["policy_digest"], str) or not HASH_PATTERN.fullmatch(
        state["policy_digest"]
    ):
        raise ValidationError("policy_digest must be a lowercase SHA-256 digest")

    _validate_project(state["project"])
    _validate_workflow(state["workflow"])
    _validate_phases(state["phases"])
    _validate_stages(state["stages"])
    _validate_collection(state, "artifacts", _validate_artifact)
    _validate_collection(state, "gates", _validate_gate)
    _validate_collection(state, "questions", _validate_question)
    _validate_collection(state, "sensors", _validate_sensor)
    _validate_collection(state, "reviews", _validate_review)
    _validate_collection(state, "units", _validate_unit)
    _validate_collection(state, "learnings", _validate_learning)

    current_stage = state["workflow"]["current_stage"]
    current_unit_id = state["workflow"]["current_unit_id"]
    if current_stage is not None:
        current_record = state["stages"][current_stage]
        if current_record["status"] not in {
            "active",
            "awaiting_approval",
            "revising",
        }:
            raise ValidationError("workflow current stage is not active")
        if STAGE_BY_SLUG[current_stage].is_per_unit:
            if current_unit_id is not None and current_unit_id not in state["units"]:
                raise ValidationError("per-unit current stage references an unknown unit")
            if current_unit_id is None and state["units"]:
                unsettled = [
                    unit["id"]
                    for unit in state["units"].values()
                    if unit["status"] != "skipped"
                    and unit["stage_statuses"][current_stage]
                    not in {"awaiting_approval", "completed"}
                ]
                if unsettled:
                    raise ValidationError(
                        "stage-level per-unit context requires every Unit iteration "
                        "to be settled"
                    )
        elif current_unit_id is not None:
            raise ValidationError("non-unit current stage cannot carry current_unit_id")

    for artifact in state["artifacts"].values():
        if artifact["unit_id"] is not None and artifact["unit_id"] not in state["units"]:
            raise ValidationError("artifact references an unknown unit")
        stage = STAGE_BY_SLUG[artifact["stage"]]
        if stage.is_per_unit:
            if state["units"] and artifact["unit_id"] is None:
                raise ValidationError("per-unit artifact is missing its unit binding")
        elif artifact["unit_id"] is not None:
            raise ValidationError("non-unit artifact cannot carry a unit binding")
    for gate in state["gates"].values():
        if any(item not in state["artifacts"] for item in gate["evidence_ids"]):
            raise ValidationError("gate references unknown evidence")
        if gate["unit_id"] is not None and gate["unit_id"] not in state["units"]:
            raise ValidationError("gate references an unknown unit")
    for unit_id, unit in state["units"].items():
        if unit_id in unit["dependencies"]:
            raise ValidationError("a unit cannot depend on itself")
        if any(dependency not in state["units"] for dependency in unit["dependencies"]):
            raise ValidationError("unit references an unknown dependency")

    audit = state["audit"]
    if not isinstance(audit, dict):
        raise ValidationError("audit must be an object")
    require_exact_keys(audit, {"event_count", "head_hash"}, "audit")
    if not _is_integer(audit["event_count"]) or audit["event_count"] < 1:
        raise ValidationError("audit.event_count must be positive")
    if not isinstance(audit["head_hash"], str) or not HASH_PATTERN.fullmatch(
        audit["head_hash"]
    ):
        raise ValidationError("audit.head_hash must be a lowercase SHA-256 digest")
