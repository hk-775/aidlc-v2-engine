"""Fail-closed policy defaults for the independent AI-DLC v2 engine."""

from __future__ import annotations

import copy
from typing import Any

from aidlc_v2_engine.errors import ValidationError
from aidlc_v2_engine.models import (
    AGENT_PERMISSION_KEYS,
    HARD_DENIED_AGENT_OPERATIONS,
    require_exact_keys,
)


def default_policy() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "gates": {
            "require_human_for_non_initialization": True,
            "require_independent_approval": True,
            "revision_limit": 3,
            "reviewer_max_iterations": 2,
            "allow_accept_as_is_after_limit": True,
            "require_declared_outputs": True,
            "require_declared_inputs": True,
            "require_sensor_results": False,
        },
        "agent_permissions": {
            "register_artifact": True,
            "answer_question": True,
            "record_sensor": True,
            "record_review": True,
            "request_approval": True,
            "complete_unit_stage": True,
            "complete_autonomous_stage": True,
            "add_unit": True,
            "fail_bolt": True,
            "propose_learning": True,
            "approve_stage": False,
            "reject_stage": False,
            "accept_as_is": False,
            "recompose": False,
            "skip_stage": False,
            "jump_stage": False,
            "redo_stage": False,
            "set_depth": False,
            "set_test_strategy": False,
            "set_autonomy": False,
            "resolve_bolt_failure": False,
            "accept_learning": False,
            "park_workflow": False,
            "resume_workflow": False,
            "loop_workflow": False,
            "merge": False,
            "deploy": False,
            "release": False,
            "accept_risk": False,
            "bypass_gate": False,
        },
        "construction": {
            "first_bolt_gated": True,
            "failure_halts": True,
            "allow_parallel_independent_bolts": True,
            "max_units": 100,
        },
        "artifact_controls": {
            "digest_algorithm": "sha256",
            "require_workspace_change_for_code_generation": True,
        },
        "learning": {
            "apply_learned_rules_next_workflow": True,
            "allow_org_promotion": False,
        },
        "limits": {
            "max_artifacts": 5000,
            "max_gates": 1000,
            "max_questions": 5000,
            "max_sensors": 5000,
            "max_reviews": 1000,
            "max_learnings": 1000,
        },
    }


def _validate_limit(value: Any, label: str, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError(
            f"{label} must be an integer between {minimum} and {maximum}",
            details={"field": label, "value": value},
        )


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise ValidationError("policy must be a JSON object")
    require_exact_keys(
        policy,
        {
            "schema_version",
            "gates",
            "agent_permissions",
            "construction",
            "artifact_controls",
            "learning",
            "limits",
        },
        "policy",
    )
    if policy["schema_version"] != 2:
        raise ValidationError("unsupported policy schema version")

    gates = policy["gates"]
    if not isinstance(gates, dict):
        raise ValidationError("gates must be an object")
    require_exact_keys(
        gates,
        {
            "require_human_for_non_initialization",
            "require_independent_approval",
            "revision_limit",
            "reviewer_max_iterations",
            "allow_accept_as_is_after_limit",
            "require_declared_outputs",
            "require_declared_inputs",
            "require_sensor_results",
        },
        "gates",
    )
    boolean_gate_fields = {
        "require_human_for_non_initialization",
        "require_independent_approval",
        "allow_accept_as_is_after_limit",
        "require_declared_outputs",
        "require_declared_inputs",
        "require_sensor_results",
    }
    if any(not isinstance(gates[field], bool) for field in boolean_gate_fields):
        raise ValidationError("gate boolean controls must be booleans")
    mandatory_true = {
        "require_human_for_non_initialization",
        "require_independent_approval",
        "require_declared_outputs",
        "require_declared_inputs",
    }
    weakened = sorted(field for field in mandatory_true if not gates[field])
    if weakened:
        raise ValidationError(
            "mandatory AI-DLC v2 gate controls cannot be disabled",
            code="unsafe_gate_policy",
            details={"controls": weakened},
        )
    _validate_limit(gates["revision_limit"], "gates.revision_limit", 1, 10)
    _validate_limit(
        gates["reviewer_max_iterations"],
        "gates.reviewer_max_iterations",
        1,
        10,
    )

    permissions = policy["agent_permissions"]
    if not isinstance(permissions, dict):
        raise ValidationError("agent_permissions must be an object")
    require_exact_keys(permissions, AGENT_PERMISSION_KEYS, "agent_permissions")
    if any(not isinstance(value, bool) for value in permissions.values()):
        raise ValidationError("agent permission values must be booleans")
    enabled_denied = sorted(
        operation for operation in HARD_DENIED_AGENT_OPERATIONS if permissions[operation]
    )
    if enabled_denied:
        raise ValidationError(
            "hard-denied agent operations cannot be enabled",
            code="unsafe_agent_permission",
            details={"operations": enabled_denied},
        )

    construction = policy["construction"]
    if not isinstance(construction, dict):
        raise ValidationError("construction must be an object")
    require_exact_keys(
        construction,
        {
            "first_bolt_gated",
            "failure_halts",
            "allow_parallel_independent_bolts",
            "max_units",
        },
        "construction",
    )
    if any(
        not isinstance(construction[field], bool)
        for field in (
            "first_bolt_gated",
            "failure_halts",
            "allow_parallel_independent_bolts",
        )
    ):
        raise ValidationError("construction boolean controls must be booleans")
    if not construction["first_bolt_gated"] or not construction["failure_halts"]:
        raise ValidationError(
            "walking-skeleton gating and halt-on-failure are mandatory",
            code="unsafe_construction_policy",
        )
    _validate_limit(construction["max_units"], "construction.max_units", 1, 1000)

    artifact_controls = policy["artifact_controls"]
    if not isinstance(artifact_controls, dict):
        raise ValidationError("artifact_controls must be an object")
    require_exact_keys(
        artifact_controls,
        {
            "digest_algorithm",
            "require_workspace_change_for_code_generation",
        },
        "artifact_controls",
    )
    if artifact_controls["digest_algorithm"] != "sha256":
        raise ValidationError("sha256 is the only supported artifact digest")
    if artifact_controls["require_workspace_change_for_code_generation"] is not True:
        raise ValidationError(
            "code generation must retain a real-workspace-change guard",
            code="unsafe_artifact_policy",
        )

    learning = policy["learning"]
    if not isinstance(learning, dict):
        raise ValidationError("learning must be an object")
    require_exact_keys(
        learning,
        {"apply_learned_rules_next_workflow", "allow_org_promotion"},
        "learning",
    )
    if learning["apply_learned_rules_next_workflow"] is not True:
        raise ValidationError("learned rules must not alter an in-flight workflow")
    if learning["allow_org_promotion"] is not False:
        raise ValidationError(
            "automatic organization-level rule promotion is forbidden",
            code="unsafe_learning_policy",
        )

    limits = policy["limits"]
    if not isinstance(limits, dict):
        raise ValidationError("limits must be an object")
    expected_limits = {
        "max_artifacts",
        "max_gates",
        "max_questions",
        "max_sensors",
        "max_reviews",
        "max_learnings",
    }
    require_exact_keys(limits, expected_limits, "limits")
    for field in expected_limits:
        _validate_limit(limits[field], f"limits.{field}", 1, 100000)
    return copy.deepcopy(policy)
