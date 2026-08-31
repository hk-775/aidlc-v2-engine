"""Human-governed AI-DLC v2 workflow operations."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from aidlc_v2_engine.catalog import (
    ARTIFACT_PRODUCERS,
    PER_UNIT_STAGES,
    PHASES,
    SCOPE_CONFIG,
    STAGES,
    STAGE_BY_SLUG,
    STAGE_INDEX,
    STAGE_SLUGS,
    detect_scope,
    required_inputs,
    required_outputs,
    stage_plan,
)
from aidlc_v2_engine.errors import (
    AuthorizationError,
    ConflictError,
    ForbiddenOperationError,
    NotFoundError,
    ValidationError,
)
from aidlc_v2_engine.models import (
    ARTIFACT_NAME_PATTERN,
    DIGEST_PATTERN,
    HARD_DENIED_AGENT_OPERATIONS,
    ID_PATTERN,
    QUESTION_MODES,
    REVIEW_VERDICTS,
    SENSOR_STATUSES,
    Actor,
    validate_depth,
    validate_locator,
    validate_scope,
    validate_stage,
    validate_test_strategy,
    validate_text,
    validate_unit_kind,
)
from aidlc_v2_engine.persistence import JsonProjectRepository, MutationResult
from aidlc_v2_engine.policy import default_policy


def sha256_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


class LifecycleService:
    """Application service for one durable AI-DLC v2 workflow."""

    def __init__(self, repository: JsonProjectRepository) -> None:
        self.repository = repository

    def initialize(
        self,
        *,
        name: str,
        description: str,
        creator: Actor,
        workspace_kind: str = "greenfield",
        scope: str = "auto",
        depth: str | None = None,
        test_strategy: str | None = None,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if workspace_kind not in {"greenfield", "brownfield"}:
            raise ValidationError("workspace_kind must be greenfield or brownfield")
        if scope == "auto":
            detection = detect_scope(description)
            if detection.needs_composition:
                raise ValidationError(
                    "scope detection is ambiguous; compose or choose a scope explicitly",
                    code="scope_composition_required",
                    details=detection.to_dict(),
                )
            selected_scope = detection.scope
            scope_source = "auto"
        else:
            selected_scope = validate_scope(scope)
            scope_source = "explicit"
        defaults = SCOPE_CONFIG[selected_scope]
        selected_depth = validate_depth(depth or defaults["depth"])
        selected_strategy = validate_test_strategy(
            test_strategy or defaults["test_strategy"]
        )
        plan = stage_plan(selected_scope)
        if workspace_kind == "greenfield":
            plan["reverse-engineering"] = "skip"
        return self.repository.initialize(
            name=name,
            description=description,
            creator=creator,
            policy=policy or default_policy(),
            workspace_kind=workspace_kind,
            scope=selected_scope,
            scope_source=scope_source,
            depth=selected_depth,
            test_strategy=selected_strategy,
            plan=plan,
        )

    @staticmethod
    def _require_human(actor: Actor, action: str) -> None:
        if actor.kind != "human":
            raise AuthorizationError(
                f"{action} requires a human actor",
                code="human_actor_required",
                details={"action": action, "actor_id": actor.actor_id},
            )

    @staticmethod
    def _require_agent_permission(
        actor: Actor,
        policy: dict[str, Any],
        operation: str,
    ) -> None:
        if actor.kind != "agent":
            return
        if operation in HARD_DENIED_AGENT_OPERATIONS:
            raise ForbiddenOperationError(
                "the operation is permanently denied to agents",
                details={"operation": operation, "actor_id": actor.actor_id},
            )
        if not policy["agent_permissions"].get(operation, False):
            raise AuthorizationError(
                "policy does not grant this agent operation",
                code="agent_permission_disabled",
                details={"operation": operation, "actor_id": actor.actor_id},
            )

    @staticmethod
    def _require_running(
        state: dict[str, Any],
        *,
        allow_autonomy_prompt: bool = False,
        allow_failure: bool = False,
    ) -> None:
        workflow = state["workflow"]
        if workflow["status"] != "running":
            raise ConflictError(
                "workflow is not running",
                code="workflow_not_running",
                details={"status": workflow["status"]},
            )
        if workflow["failure"] is not None and not allow_failure:
            raise ConflictError(
                "a Bolt failure requires a human retry, skip, or abort decision",
                code="bolt_failure_action_required",
                details=workflow["failure"],
            )
        if workflow["autonomy_prompt_pending"] and not allow_autonomy_prompt:
            raise ConflictError(
                "the walking-skeleton ladder choice is required before continuing",
                code="autonomy_choice_required",
            )

    @staticmethod
    def _current_context(
        state: dict[str, Any],
    ) -> tuple[str, str | None]:
        stage = state["workflow"]["current_stage"]
        if stage is None:
            raise ConflictError("workflow has no current stage")
        return stage, state["workflow"]["current_unit_id"]

    @staticmethod
    def _plan(state: dict[str, Any]) -> dict[str, str]:
        return {
            slug: record["decision"]
            for slug, record in state["stages"].items()
        }

    @staticmethod
    def _ordered_units(state: dict[str, Any]) -> list[dict[str, Any]]:
        return sorted(state["units"].values(), key=lambda item: (item["order"], item["id"]))

    @staticmethod
    def _unit_stage_dependencies_settled(
        state: dict[str, Any],
        unit: dict[str, Any],
        stage: str,
    ) -> bool:
        return all(
            state["units"][dependency]["stage_statuses"][stage]
            in {"awaiting_approval", "completed", "skipped"}
            for dependency in unit["dependencies"]
        )

    def _next_ready_unit(
        self,
        state: dict[str, Any],
        stage: str,
    ) -> dict[str, Any] | None:
        for unit in self._ordered_units(state):
            if (
                unit["status"] != "skipped"
                and unit["stage_statuses"][stage] == "pending"
                and self._unit_stage_dependencies_settled(state, unit, stage)
            ):
                return unit
        return None

    @staticmethod
    def _uses_unit_iterations(state: dict[str, Any], stage: str) -> bool:
        return STAGE_BY_SLUG[stage].is_per_unit and bool(state["units"])

    @staticmethod
    def _effective_reviewer(
        state: dict[str, Any],
        stage: str,
    ) -> str | None:
        if SCOPE_CONFIG[state["workflow"]["scope"]]["review_cap"] == "none":
            return None
        return STAGE_BY_SLUG[stage].reviewer

    @staticmethod
    def _first_per_unit_stage(state: dict[str, Any]) -> str | None:
        return next(
            (
                slug
                for slug in PER_UNIT_STAGES
                if state["stages"][slug]["decision"] == "execute"
            ),
            None,
        )

    @staticmethod
    def _next_global_stage(
        state: dict[str, Any],
        start_index: int,
    ) -> str | None:
        return next(
            (
                stage.slug
                for stage in STAGES[start_index + 1 :]
                if state["stages"][stage.slug]["decision"] == "execute"
            ),
            None,
        )

    @staticmethod
    def _new_unit_record(
        *,
        unit_id: str,
        name: str,
        kind: str,
        order: int,
        dependencies: list[str],
        walking_skeleton: bool,
        actor_id: str,
        timestamp: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": unit_id,
            "name": name,
            "kind": kind,
            "order": order,
            "dependencies": dependencies,
            "walking_skeleton": walking_skeleton,
            "status": "planned",
            "stage_statuses": {
                slug: (
                    "pending"
                    if state["stages"][slug]["decision"] == "execute"
                    else "skipped"
                )
                for slug in PER_UNIT_STAGES
            },
            "created_by": actor_id,
            "created_at": timestamp,
            "completed_at": None,
        }

    @staticmethod
    def _sync_per_unit_stage(
        state: dict[str, Any],
        slug: str,
        timestamp: str,
    ) -> None:
        record = state["stages"][slug]
        if record["decision"] == "skip":
            record["status"] = "skipped"
            record["completed_at"] = None
            return
        statuses = [
            unit["stage_statuses"][slug]
            for unit in state["units"].values()
        ]
        if not statuses:
            record["status"] = "pending"
            return
        if all(status in {"completed", "skipped"} for status in statuses):
            record["status"] = "completed"
            record["completed_at"] = record["completed_at"] or timestamp
        elif "awaiting_approval" in statuses:
            record["status"] = "awaiting_approval"
            record["completed_at"] = None
        elif "revising" in statuses:
            record["status"] = "revising"
            record["completed_at"] = None
        elif "active" in statuses:
            record["status"] = "active"
            record["completed_at"] = None
        else:
            record["status"] = "pending"
            record["completed_at"] = None
        if any(status not in {"pending", "skipped"} for status in statuses):
            record["started_at"] = record["started_at"] or timestamp

    def _sync_all_per_unit_stages(
        self,
        state: dict[str, Any],
        timestamp: str,
    ) -> None:
        for slug in PER_UNIT_STAGES:
            self._sync_per_unit_stage(state, slug, timestamp)

    @staticmethod
    def _refresh_phases(state: dict[str, Any], timestamp: str) -> None:
        current_stage = state["workflow"]["current_stage"]
        current_phase = (
            STAGE_BY_SLUG[current_stage].phase if current_stage is not None else None
        )
        for phase in PHASES:
            record = state["phases"][phase]
            if phase == "initialization":
                record["status"] = "verified"
                record["verified_at"] = record["verified_at"] or timestamp
                continue
            statuses = [
                state["stages"][stage.slug]["status"]
                for stage in STAGES
                if stage.phase == phase
            ]
            if all(status == "skipped" for status in statuses):
                record["status"] = "skipped"
                record["verified_at"] = None
            elif all(status in {"completed", "skipped"} for status in statuses):
                record["status"] = "verified"
                record["verified_at"] = record["verified_at"] or timestamp
            elif phase == current_phase or any(
                status in {"active", "awaiting_approval", "revising"}
                for status in statuses
            ):
                record["status"] = "active"
                record["verified_at"] = None
            else:
                record["status"] = "pending"
                record["verified_at"] = None

    def _activate_normal_stage(
        self,
        state: dict[str, Any],
        slug: str,
        timestamp: str,
    ) -> None:
        record = state["stages"][slug]
        record["status"] = "active"
        record["started_at"] = record["started_at"] or timestamp
        record["completed_at"] = None
        record["current_gate_id"] = None
        state["workflow"]["current_stage"] = slug
        state["workflow"]["current_unit_id"] = None

    def _activate_unit_stage(
        self,
        state: dict[str, Any],
        slug: str,
        unit: dict[str, Any],
        timestamp: str,
    ) -> None:
        unit["status"] = "active"
        unit["stage_statuses"][slug] = "active"
        state["stages"][slug]["started_at"] = (
            state["stages"][slug]["started_at"] or timestamp
        )
        state["stages"][slug]["current_gate_id"] = None
        state["workflow"]["current_stage"] = slug
        state["workflow"]["current_unit_id"] = unit["id"]
        self._sync_per_unit_stage(state, slug, timestamp)

    def _activate_stage(
        self,
        state: dict[str, Any],
        slug: str,
        timestamp: str,
        values: Any,
        actor_id: str,
    ) -> None:
        definition = STAGE_BY_SLUG[slug]
        if not definition.is_per_unit or not state["units"]:
            self._activate_normal_stage(state, slug, timestamp)
            return
        del values, actor_id
        unit = self._next_ready_unit(state, slug)
        if unit is None:
            raise ConflictError(
                "no dependency-ready Unit is available for Construction",
                code="unit_dependency_blocked",
            )
        self._activate_unit_stage(state, slug, unit, timestamp)

    def _finish_workflow(self, state: dict[str, Any], timestamp: str) -> None:
        workflow = state["workflow"]
        workflow["status"] = "completed"
        workflow["current_stage"] = None
        workflow["current_unit_id"] = None
        workflow["completed_at"] = timestamp
        workflow["parked_at"] = None
        self._refresh_phases(state, timestamp)

    def _advance(
        self,
        state: dict[str, Any],
        *,
        completed_stage: str,
        completed_unit_id: str | None,
        timestamp: str,
        values: Any,
        actor_id: str,
    ) -> None:
        definition = STAGE_BY_SLUG[completed_stage]
        workflow = state["workflow"]
        workflow["last_completed_stage"] = completed_stage

        if (
            definition.is_per_unit
            and state["units"]
            and completed_unit_id is not None
        ):
            raise ConflictError(
                "stage-major Construction advances only after the stage-level gate"
            )

        if (
            definition.is_per_unit
            and state["units"]
            and completed_stage == self._first_per_unit_stage(state)
            and SCOPE_CONFIG[workflow["scope"]]["skeleton"]
            and workflow["construction_autonomy"] is None
        ):
            workflow["autonomy_prompt_pending"] = True

        start_index = STAGE_INDEX[completed_stage]

        next_stage = self._next_global_stage(state, start_index)
        if next_stage is None:
            self._finish_workflow(state, timestamp)
            return
        self._activate_stage(
            state,
            next_stage,
            timestamp,
            values,
            actor_id,
        )
        self._refresh_phases(state, timestamp)

    @staticmethod
    def _context_artifacts(
        state: dict[str, Any],
        stage: str,
        unit_id: str | None,
    ) -> list[dict[str, Any]]:
        return [
            artifact
            for artifact in state["artifacts"].values()
            if artifact["stage"] == stage and artifact["unit_id"] == unit_id
        ]

    @staticmethod
    def _context_reviews(
        state: dict[str, Any],
        stage: str,
        unit_id: str | None,
    ) -> list[dict[str, Any]]:
        return sorted(
            (
                review
                for review in state["reviews"].values()
                if review["stage"] == stage and review["unit_id"] == unit_id
            ),
            key=lambda item: (item["iteration"], item["recorded_at"], item["id"]),
        )

    @staticmethod
    def _artifact_exists(
        state: dict[str, Any],
        *,
        name: str,
        stage: str,
        unit_id: str | None,
    ) -> bool:
        return any(
            artifact["name"] == name
            and artifact["stage"] == stage
            and artifact["unit_id"] == unit_id
            for artifact in state["artifacts"].values()
        )

    def _missing_inputs(
        self,
        state: dict[str, Any],
        stage: str,
        unit_id: str | None,
    ) -> list[str]:
        plan = self._plan(state)
        missing: list[str] = []
        for name in required_inputs(
            stage,
            plan=plan,
            workspace_kind=state["project"]["workspace_kind"],
        ):
            producers = tuple(
                producer
                for producer in ARTIFACT_PRODUCERS.get(name, ())
                if plan.get(producer) == "execute"
                and STAGE_INDEX[producer] < STAGE_INDEX[stage]
            )
            if not producers:
                continue

            def producer_is_satisfied(producer: str) -> bool:
                producer_definition = STAGE_BY_SLUG[producer]
                if not producer_definition.is_per_unit or not state["units"]:
                    return self._artifact_exists(
                        state,
                        name=name,
                        stage=producer,
                        unit_id=None,
                    )
                if unit_id is not None:
                    return self._artifact_exists(
                        state,
                        name=name,
                        stage=producer,
                        unit_id=unit_id,
                    )
                applicable_units = [
                    unit
                    for unit in self._ordered_units(state)
                    if unit["status"] != "skipped"
                    and name in required_outputs(producer, unit["kind"])
                ]
                return all(
                    self._artifact_exists(
                        state,
                        name=name,
                        stage=producer,
                        unit_id=unit["id"],
                    )
                    for unit in applicable_units
                )

            if not any(producer_is_satisfied(producer) for producer in producers):
                missing.append(name)
        return sorted(set(missing))

    def _assert_stage_ready(
        self,
        state: dict[str, Any],
        policy: dict[str, Any],
        stage: str,
        unit_id: str | None,
    ) -> None:
        definition = STAGE_BY_SLUG[stage]
        artifacts = self._context_artifacts(state, stage, unit_id)
        artifact_names = {artifact["name"] for artifact in artifacts}
        if policy["gates"]["require_declared_outputs"]:
            unit_kind = state["units"][unit_id]["kind"] if unit_id is not None else None
            missing_outputs = sorted(set(required_outputs(stage, unit_kind)) - artifact_names)
            if missing_outputs:
                raise ConflictError(
                    "stage cannot complete until every declared output is registered",
                    code="stage_outputs_missing",
                    details={"stage": stage, "missing": missing_outputs},
                )
        if policy["gates"]["require_declared_inputs"]:
            missing_inputs = self._missing_inputs(state, stage, unit_id)
            if missing_inputs:
                raise ConflictError(
                    "stage cannot complete because required upstream artifacts are missing",
                    code="stage_inputs_missing",
                    details={"stage": stage, "missing": missing_inputs},
                )
        if (
            definition.workspace_requires
            and policy["artifact_controls"][
                "require_workspace_change_for_code_generation"
            ]
            and not any(artifact["workspace_change"] for artifact in artifacts)
        ):
            raise ConflictError(
                "code generation requires asserted evidence of a real workspace change",
                code="workspace_change_required",
            )
        if stage == "units-generation" and any(
            state["stages"][slug]["decision"] == "execute"
            for slug in PER_UNIT_STAGES
        ) and not state["units"]:
            raise ConflictError(
                "units-generation must register at least one Unit",
                code="units_required",
            )
        reviewer = self._effective_reviewer(state, stage)
        if reviewer is not None:
            reviews = self._context_reviews(state, stage, unit_id)
            max_iterations = min(
                definition.reviewer_max_iterations,
                policy["gates"]["reviewer_max_iterations"],
            )
            if (
                (not reviews or reviews[-1]["verdict"] != "ready")
                and len(reviews) < max_iterations
            ):
                raise ConflictError(
                    "the independent reviewer loop has not reached READY",
                    code="review_ready_required",
                    details={
                        "stage": stage,
                        "reviewer": reviewer,
                        "iterations": len(reviews),
                        "max_iterations": max_iterations,
                    },
                )
        if policy["gates"]["require_sensor_results"]:
            latest = {
                sensor["sensor"]: sensor
                for sensor in state["sensors"].values()
                if sensor["stage"] == stage and sensor["unit_id"] == unit_id
            }
            missing_sensors = sorted(set(definition.sensors) - set(latest))
            failed_sensors = sorted(
                sensor
                for sensor, record in latest.items()
                if sensor in definition.sensors and record["status"] == "fail"
            )
            if missing_sensors or failed_sensors:
                raise ConflictError(
                    "required sensor evidence is incomplete",
                    code="sensor_evidence_incomplete",
                    details={"missing": missing_sensors, "failed": failed_sensors},
                )

    def _assert_unit_stage_ready_for_gate(
        self,
        state: dict[str, Any],
        policy: dict[str, Any],
        stage: str,
    ) -> None:
        applicable = [
            unit
            for unit in self._ordered_units(state)
            if unit["status"] != "skipped"
        ]
        if not applicable:
            raise ConflictError(
                "stage-major Construction has no applicable Units",
                code="units_required",
            )
        unsettled = [
            unit["id"]
            for unit in applicable
            if unit["stage_statuses"][stage]
            not in {"awaiting_approval", "completed"}
        ]
        if unsettled:
            raise ConflictError(
                "every Unit must settle the current Construction stage before its gate",
                code="unit_stage_iterations_pending",
                details={"stage": stage, "unit_ids": unsettled},
            )
        for unit in applicable:
            self._assert_stage_ready(state, policy, stage, unit["id"])

    def add_unit(
        self,
        *,
        actor: Actor,
        name: str,
        kind: str,
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        name = validate_text(name, "name", maximum=120)
        kind = validate_unit_kind(kind)
        dependency_ids = list(dict.fromkeys(dependencies or ()))
        if any(not ID_PATTERN.fullmatch(item) for item in dependency_ids):
            raise ValidationError("unit dependencies must be portable Unit identifiers")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "add_unit")
            current_stage, _ = self._current_context(state)
            if STAGE_INDEX[current_stage] > STAGE_INDEX["delivery-planning"]:
                raise ConflictError(
                    "Units are frozen after Delivery Planning",
                    code="unit_plan_frozen",
                )
            if len(state["units"]) >= policy["construction"]["max_units"]:
                raise ConflictError("the configured Unit limit has been reached")
            missing = sorted(set(dependency_ids) - set(state["units"]))
            if missing:
                raise NotFoundError(
                    "a Unit dependency was not found",
                    details={"unit_ids": missing},
                )
            unit_id = values.identifier("unit", f"{name}:{kind}:{len(state['units']) + 1}")
            unit = self._new_unit_record(
                unit_id=unit_id,
                name=name,
                kind=kind,
                order=len(state["units"]) + 1,
                dependencies=dependency_ids,
                walking_skeleton=not state["units"],
                actor_id=actor.actor_id,
                timestamp=values.timestamp,
                state=state,
            )
            state["units"][unit_id] = unit
            return MutationResult(
                event_type="UNIT_CREATED",
                payload={
                    "unit_id": unit_id,
                    "kind": kind,
                    "walking_skeleton": unit["walking_skeleton"],
                    "dependencies": dependency_ids,
                },
                result={"unit": unit},
            )

        return self.repository.mutate(actor, mutation)

    def register_artifact(
        self,
        *,
        actor: Actor,
        name: str,
        title: str,
        digest: str,
        locator: str = "",
        workspace_change: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(name, str) or not ARTIFACT_NAME_PATTERN.fullmatch(name):
            raise ValidationError("artifact name must use lowercase kebab-case")
        title = validate_text(title, "title", maximum=200)
        if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
            raise ValidationError(
                "artifact digest must be sha256 followed by 64 lowercase hex characters"
            )
        locator = validate_locator(locator)
        if not isinstance(workspace_change, bool):
            raise ValidationError("workspace_change must be boolean")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "register_artifact")
            stage, unit_id = self._current_context(state)
            context_status = (
                state["units"][unit_id]["stage_statuses"][stage]
                if unit_id is not None
                else state["stages"][stage]["status"]
            )
            if context_status not in {"active", "revising"}:
                raise ConflictError("artifacts can only be added while a stage is active")
            definition = STAGE_BY_SLUG[stage]
            allowed = {*definition.produces, *definition.optional_produces}
            if name not in allowed:
                raise ValidationError(
                    "artifact is not declared by the current stage",
                    details={"stage": stage, "artifact": name, "allowed": sorted(allowed)},
                )
            if len(state["artifacts"]) >= policy["limits"]["max_artifacts"]:
                raise ConflictError("the configured artifact limit has been reached")
            existing = self._context_artifacts(state, stage, unit_id)
            if any(
                item["name"] == name and item["digest"] == digest
                for item in existing
            ):
                raise ConflictError(
                    "the same artifact version is already registered",
                    code="duplicate_artifact",
                )
            artifact_id = values.identifier(
                "artifact",
                f"{stage}:{unit_id or 'global'}:{name}:{digest}",
            )
            artifact = {
                "id": artifact_id,
                "name": name,
                "stage": stage,
                "unit_id": unit_id,
                "title": title,
                "digest": digest,
                "locator": locator,
                "workspace_change": workspace_change,
                "submitted_by": actor.actor_id,
                "submitted_at": values.timestamp,
            }
            event_type = (
                "ARTIFACT_UPDATED"
                if any(item["name"] == name for item in existing)
                else "ARTIFACT_CREATED"
            )
            state["artifacts"][artifact_id] = artifact
            return MutationResult(
                event_type=event_type,
                payload={
                    "artifact_id": artifact_id,
                    "artifact": name,
                    "stage": stage,
                    "unit_id": unit_id,
                    "digest": digest,
                    "workspace_change": workspace_change,
                },
                result={"artifact": artifact},
            )

        return self.repository.mutate(actor, mutation)

    def answer_question(
        self,
        *,
        actor: Actor,
        mode: str,
        prompt: str,
        answer: str,
    ) -> dict[str, Any]:
        if mode not in QUESTION_MODES:
            raise ValidationError(
                "question mode must be guide, edit-file, or chat",
                details={"mode": mode},
            )
        prompt = validate_text(prompt, "prompt", maximum=1000)
        answer = validate_text(answer, "answer", maximum=10000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "answer_question")
            stage, unit_id = self._current_context(state)
            if len(state["questions"]) >= policy["limits"]["max_questions"]:
                raise ConflictError("the configured question limit has been reached")
            question_id = values.identifier(
                "question",
                f"{stage}:{unit_id or 'global'}:{mode}:{prompt}",
            )
            question = {
                "id": question_id,
                "stage": stage,
                "unit_id": unit_id,
                "mode": mode,
                "prompt": prompt,
                "answer": answer,
                "answered_by": actor.actor_id,
                "answered_at": values.timestamp,
            }
            state["questions"][question_id] = question
            return MutationResult(
                event_type="QUESTION_ANSWERED",
                payload={
                    "question_id": question_id,
                    "stage": stage,
                    "unit_id": unit_id,
                    "mode": mode,
                },
                result={"question": question},
            )

        return self.repository.mutate(actor, mutation)

    def record_sensor(
        self,
        *,
        actor: Actor,
        sensor: str,
        status: str,
        summary: str,
    ) -> dict[str, Any]:
        if not isinstance(sensor, str) or not ARTIFACT_NAME_PATTERN.fullmatch(sensor):
            raise ValidationError("sensor must use lowercase kebab-case")
        if status not in SENSOR_STATUSES:
            raise ValidationError("sensor status must be pass, warn, or fail")
        summary = validate_text(summary, "summary", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "record_sensor")
            stage, unit_id = self._current_context(state)
            if sensor not in STAGE_BY_SLUG[stage].sensors:
                raise ValidationError(
                    "sensor is not declared for the current stage",
                    details={"stage": stage, "sensor": sensor},
                )
            if len(state["sensors"]) >= policy["limits"]["max_sensors"]:
                raise ConflictError("the configured sensor limit has been reached")
            sensor_id = values.identifier(
                "sensor",
                f"{stage}:{unit_id or 'global'}:{sensor}:{status}",
            )
            record = {
                "id": sensor_id,
                "stage": stage,
                "unit_id": unit_id,
                "sensor": sensor,
                "status": status,
                "summary": summary,
                "recorded_by": actor.actor_id,
                "recorded_at": values.timestamp,
            }
            state["sensors"][sensor_id] = record
            return MutationResult(
                event_type=f"SENSOR_{status.upper().replace('-', '_')}",
                payload={
                    "sensor_id": sensor_id,
                    "sensor": sensor,
                    "stage": stage,
                    "unit_id": unit_id,
                },
                result={"sensor": record},
            )

        return self.repository.mutate(actor, mutation)

    def record_review(
        self,
        *,
        actor: Actor,
        verdict: str,
        summary: str,
    ) -> dict[str, Any]:
        if verdict not in REVIEW_VERDICTS:
            raise ValidationError("review verdict must be ready or not-ready")
        summary = validate_text(summary, "summary", maximum=2000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "record_review")
            stage, unit_id = self._current_context(state)
            definition = STAGE_BY_SLUG[stage]
            reviewer = self._effective_reviewer(state, stage)
            if reviewer is None:
                raise ConflictError("the current stage has no independent reviewer")
            if actor.kind == "agent" and actor.actor_id != reviewer:
                raise AuthorizationError(
                    "only the configured reviewer agent may record this verdict",
                    code="reviewer_identity_required",
                    details={"reviewer": reviewer},
                )
            reviews = self._context_reviews(state, stage, unit_id)
            maximum = min(
                definition.reviewer_max_iterations,
                policy["gates"]["reviewer_max_iterations"],
            )
            if len(reviews) >= maximum:
                raise ConflictError(
                    "the reviewer loop iteration cap has been reached",
                    code="review_iteration_limit",
                )
            if len(state["reviews"]) >= policy["limits"]["max_reviews"]:
                raise ConflictError("the configured review limit has been reached")
            iteration = len(reviews) + 1
            review_id = values.identifier(
                "review",
                f"{stage}:{unit_id or 'global'}:{iteration}:{verdict}",
            )
            review = {
                "id": review_id,
                "stage": stage,
                "unit_id": unit_id,
                "reviewer": actor.actor_id,
                "verdict": verdict,
                "iteration": iteration,
                "summary": summary,
                "recorded_at": values.timestamp,
            }
            state["reviews"][review_id] = review
            state["stages"][stage]["reviewer_iterations"] += 1
            return MutationResult(
                event_type="REVIEW_RECORDED",
                payload={
                    "review_id": review_id,
                    "stage": stage,
                    "unit_id": unit_id,
                    "verdict": verdict,
                    "iteration": iteration,
                },
                result={"review": review},
            )

        return self.repository.mutate(actor, mutation)

    def _settle_current_unit_stage(
        self,
        state: dict[str, Any],
        policy: dict[str, Any],
        values: Any,
    ) -> tuple[str, str, str | None]:
        stage, unit_id = self._current_context(state)
        if unit_id is None or not self._uses_unit_iterations(state, stage):
            raise ConflictError(
                "the current context is not a per-Unit Construction iteration",
                code="unit_stage_iteration_not_active",
            )
        unit = state["units"][unit_id]
        if unit["stage_statuses"][stage] not in {"active", "revising"}:
            raise ConflictError("the current Unit stage is not active")
        self._assert_stage_ready(state, policy, stage, unit_id)
        unit["stage_statuses"][stage] = "awaiting_approval"
        self._sync_per_unit_stage(state, stage, values.timestamp)

        next_unit = self._next_ready_unit(state, stage)
        if next_unit is not None:
            self._activate_unit_stage(state, stage, next_unit, values.timestamp)
            self._refresh_phases(state, values.timestamp)
            return stage, unit_id, next_unit["id"]

        blocked = [
            item["id"]
            for item in self._ordered_units(state)
            if item["status"] != "skipped"
            and item["stage_statuses"][stage] == "pending"
        ]
        if blocked:
            raise ConflictError(
                "remaining Units are blocked by the current Unit dependency graph",
                code="unit_dependency_blocked",
                details={"stage": stage, "unit_ids": blocked},
            )

        state["workflow"]["current_unit_id"] = None
        state["stages"][stage]["status"] = "active"
        state["stages"][stage]["current_gate_id"] = None
        self._refresh_phases(state, values.timestamp)
        return stage, unit_id, None

    def complete_unit_stage(self, *, actor: Actor) -> dict[str, Any]:
        """Settle one Unit for the current stage-major Construction stage."""

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "complete_unit_stage")
            stage, unit_id, next_unit_id = self._settle_current_unit_stage(
                state,
                policy,
                values,
            )
            return MutationResult(
                event_type="UNIT_STAGE_SETTLED",
                payload={
                    "stage": stage,
                    "unit_id": unit_id,
                    "next_unit_id": next_unit_id,
                    "stage_gate_ready": next_unit_id is None,
                },
                result={
                    "workflow": state["workflow"],
                    "stage": state["stages"][stage],
                    "unit": state["units"][unit_id],
                },
            )

        return self.repository.mutate(actor, mutation)

    def request_approval(
        self,
        *,
        actor: Actor,
        rationale: str,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        rationale = validate_text(rationale, "rationale", maximum=1000)
        supplied_evidence = list(dict.fromkeys(evidence_ids or ()))
        if any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in supplied_evidence):
            raise ValidationError("evidence identifiers are invalid")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "request_approval")
            stage, unit_id = self._current_context(state)
            definition = STAGE_BY_SLUG[stage]
            if definition.is_initialization:
                raise ConflictError("initialization stages do not use approval gates")
            aggregate_unit_stage = self._uses_unit_iterations(state, stage)
            if aggregate_unit_stage and unit_id is not None:
                raise ConflictError(
                    "settle every Unit before opening the stage-level gate",
                    code="unit_stage_iterations_pending",
                    details={"stage": stage, "unit_id": unit_id},
                )
            context_status = (
                state["units"][unit_id]["stage_statuses"][stage]
                if unit_id is not None
                else state["stages"][stage]["status"]
            )
            if context_status not in {"active", "revising"}:
                raise ConflictError("the current stage is not ready to request approval")
            if aggregate_unit_stage:
                self._assert_unit_stage_ready_for_gate(state, policy, stage)
                context_artifacts = [
                    artifact
                    for artifact in state["artifacts"].values()
                    if artifact["stage"] == stage and artifact["unit_id"] is not None
                ]
            else:
                self._assert_stage_ready(state, policy, stage, unit_id)
                context_artifacts = self._context_artifacts(state, stage, unit_id)
            allowed_ids = {artifact["id"] for artifact in context_artifacts}
            selected_evidence = supplied_evidence or sorted(allowed_ids)
            unknown = sorted(set(selected_evidence) - allowed_ids)
            if unknown:
                raise ValidationError(
                    "gate evidence must belong to the current stage context",
                    details={"artifact_ids": unknown},
                )
            if len(state["gates"]) >= policy["limits"]["max_gates"]:
                raise ConflictError("the configured gate limit has been reached")
            gate_id = values.identifier(
                "gate",
                f"{stage}:{unit_id or 'global'}:{state['stages'][stage]['revision_count']}",
            )
            gate = {
                "id": gate_id,
                "stage": stage,
                "unit_id": unit_id,
                "status": "pending",
                "rationale": rationale,
                "evidence_ids": selected_evidence,
                "requested_by": actor.actor_id,
                "requested_by_kind": actor.kind,
                "requested_at": values.timestamp,
                "decided_by": None,
                "decided_at": None,
                "reason": None,
                "accept_as_is": False,
            }
            state["gates"][gate_id] = gate
            state["stages"][stage]["current_gate_id"] = gate_id
            if unit_id is not None:
                state["units"][unit_id]["stage_statuses"][stage] = "awaiting_approval"
                self._sync_per_unit_stage(state, stage, values.timestamp)
            else:
                state["stages"][stage]["status"] = "awaiting_approval"
            return MutationResult(
                event_type="STAGE_AWAITING_APPROVAL",
                payload={
                    "gate_id": gate_id,
                    "stage": stage,
                    "unit_id": unit_id,
                    "evidence_ids": selected_evidence,
                },
                result={"gate": gate},
            )

        return self.repository.mutate(actor, mutation)

    @staticmethod
    def _pending_gate(
        state: dict[str, Any],
        gate_id: str,
    ) -> dict[str, Any]:
        gate = state["gates"].get(gate_id)
        if gate is None:
            raise NotFoundError("approval gate was not found")
        if gate["status"] != "pending":
            raise ConflictError("approval gate is already resolved")
        if (
            gate["stage"] != state["workflow"]["current_stage"]
            or gate["unit_id"] != state["workflow"]["current_unit_id"]
        ):
            raise ConflictError("approval gate is not for the current stage context")
        return gate

    def approve_stage(
        self,
        *,
        actor: Actor,
        gate_id: str,
        accept_as_is: bool = False,
    ) -> dict[str, Any]:
        self._require_human(actor, "stage approval")
        if not isinstance(accept_as_is, bool):
            raise ValidationError("accept_as_is must be boolean")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            gate = self._pending_gate(state, gate_id)
            if (
                policy["gates"]["require_independent_approval"]
                and gate["requested_by"] == actor.actor_id
            ):
                raise AuthorizationError(
                    "a gate requester cannot approve the same gate",
                    code="self_approval_forbidden",
                )
            stage = gate["stage"]
            unit_id = gate["unit_id"]
            revisions = state["stages"][stage]["revision_count"]
            if accept_as_is:
                if not policy["gates"]["allow_accept_as_is_after_limit"]:
                    raise AuthorizationError("accept-as-is is disabled by policy")
                if revisions < policy["gates"]["revision_limit"]:
                    raise ConflictError(
                        "accept-as-is is available only after the revision limit",
                        code="revision_limit_not_reached",
                    )
            aggregate_unit_stage = (
                unit_id is None and self._uses_unit_iterations(state, stage)
            )
            if aggregate_unit_stage:
                self._assert_unit_stage_ready_for_gate(state, policy, stage)
            else:
                self._assert_stage_ready(state, policy, stage, unit_id)
            gate["status"] = "approved"
            gate["decided_by"] = actor.actor_id
            gate["decided_at"] = values.timestamp
            gate["accept_as_is"] = accept_as_is
            state["stages"][stage]["current_gate_id"] = None
            if aggregate_unit_stage:
                for unit in self._ordered_units(state):
                    if unit["stage_statuses"][stage] == "awaiting_approval":
                        unit["stage_statuses"][stage] = "completed"
                    if all(
                        status in {"completed", "skipped"}
                        for status in unit["stage_statuses"].values()
                    ):
                        unit["status"] = "completed"
                        unit["completed_at"] = values.timestamp
                self._sync_per_unit_stage(state, stage, values.timestamp)
            elif unit_id is not None:
                state["units"][unit_id]["stage_statuses"][stage] = "completed"
                self._sync_per_unit_stage(state, stage, values.timestamp)
            else:
                state["stages"][stage]["status"] = "completed"
                state["stages"][stage]["completed_at"] = values.timestamp
            self._advance(
                state,
                completed_stage=stage,
                completed_unit_id=unit_id,
                timestamp=values.timestamp,
                values=values,
                actor_id=actor.actor_id,
            )
            return MutationResult(
                event_type="GATE_APPROVED",
                payload={
                    "gate_id": gate_id,
                    "stage": stage,
                    "unit_id": unit_id,
                    "accept_as_is": accept_as_is,
                    "human_turn_fresh": True,
                    "next_stage": state["workflow"]["current_stage"],
                    "next_unit_id": state["workflow"]["current_unit_id"],
                },
                result={
                    "gate": gate,
                    "workflow": state["workflow"],
                },
            )

        return self.repository.mutate(actor, mutation)

    def reject_stage(
        self,
        *,
        actor: Actor,
        gate_id: str,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "stage rejection")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            gate = self._pending_gate(state, gate_id)
            if (
                policy["gates"]["require_independent_approval"]
                and gate["requested_by"] == actor.actor_id
            ):
                raise AuthorizationError(
                    "a gate requester cannot decide the same gate",
                    code="self_approval_forbidden",
                )
            stage = gate["stage"]
            unit_id = gate["unit_id"]
            aggregate_unit_stage = (
                unit_id is None and self._uses_unit_iterations(state, stage)
            )
            gate["status"] = "rejected"
            gate["decided_by"] = actor.actor_id
            gate["decided_at"] = values.timestamp
            gate["reason"] = reason
            state["stages"][stage]["revision_count"] += 1
            state["stages"][stage]["current_gate_id"] = None
            if aggregate_unit_stage:
                for unit in self._ordered_units(state):
                    if unit["status"] == "skipped":
                        continue
                    unit["stage_statuses"][stage] = "pending"
                    if unit["status"] == "completed":
                        unit["status"] = "active"
                        unit["completed_at"] = None
                next_unit = self._next_ready_unit(state, stage)
                if next_unit is None:
                    raise ConflictError(
                        "the rejected stage cannot find a dependency-ready Unit",
                        code="unit_dependency_blocked",
                    )
                self._activate_unit_stage(
                    state,
                    stage,
                    next_unit,
                    values.timestamp,
                )
            elif unit_id is not None:
                state["units"][unit_id]["stage_statuses"][stage] = "revising"
                self._sync_per_unit_stage(state, stage, values.timestamp)
            else:
                state["stages"][stage]["status"] = "revising"
            return MutationResult(
                event_type="GATE_REJECTED",
                payload={
                    "gate_id": gate_id,
                    "stage": stage,
                    "unit_id": unit_id,
                    "revision_count": state["stages"][stage]["revision_count"],
                    "reason": reason,
                },
                result={"gate": gate, "stage": state["stages"][stage]},
            )

        return self.repository.mutate(actor, mutation)

    def complete_autonomous_stage(self, *, actor: Actor) -> dict[str, Any]:
        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "complete_autonomous_stage")
            stage, unit_id = self._current_context(state)
            if (
                STAGE_BY_SLUG[stage].phase != "construction"
                or state["workflow"]["construction_autonomy"] != "autonomous"
            ):
                raise AuthorizationError(
                    "this Construction context still requires a human gate",
                    code="human_gate_required",
                )
            completed_unit_id = unit_id
            if unit_id is not None:
                _, _, next_unit_id = self._settle_current_unit_stage(
                    state,
                    policy,
                    values,
                )
                if next_unit_id is None:
                    for unit in self._ordered_units(state):
                        if unit["stage_statuses"][stage] == "awaiting_approval":
                            unit["stage_statuses"][stage] = "completed"
                        if all(
                            status in {"completed", "skipped"}
                            for status in unit["stage_statuses"].values()
                        ):
                            unit["status"] = "completed"
                            unit["completed_at"] = values.timestamp
                    self._sync_per_unit_stage(state, stage, values.timestamp)
                    self._advance(
                        state,
                        completed_stage=stage,
                        completed_unit_id=None,
                        timestamp=values.timestamp,
                        values=values,
                        actor_id=actor.actor_id,
                    )
            else:
                self._assert_stage_ready(state, policy, stage, None)
                state["stages"][stage]["status"] = "completed"
                state["stages"][stage]["completed_at"] = values.timestamp
                self._advance(
                    state,
                    completed_stage=stage,
                    completed_unit_id=None,
                    timestamp=values.timestamp,
                    values=values,
                    actor_id=actor.actor_id,
                )
            return MutationResult(
                event_type="STAGE_COMPLETED",
                payload={
                    "stage": stage,
                    "unit_id": completed_unit_id,
                    "autonomous": True,
                    "next_stage": state["workflow"]["current_stage"],
                    "next_unit_id": state["workflow"]["current_unit_id"],
                },
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def set_autonomy(self, *, actor: Actor, mode: str) -> dict[str, Any]:
        self._require_human(actor, "Construction autonomy selection")
        if mode not in {"autonomous", "gated"}:
            raise ValidationError("autonomy mode must be autonomous or gated")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state, allow_autonomy_prompt=True)
            del policy
            workflow = state["workflow"]
            if not workflow["autonomy_prompt_pending"]:
                raise ConflictError("the autonomy ladder is not currently pending")
            if workflow["construction_autonomy"] is not None:
                raise ConflictError("Construction autonomy has already been selected")
            workflow["construction_autonomy"] = mode
            workflow["autonomy_prompt_pending"] = False
            return MutationResult(
                event_type="AUTONOMY_MODE_SET",
                payload={"mode": mode},
                result={"workflow": workflow},
            )

        return self.repository.mutate(actor, mutation)

    def fail_bolt(
        self,
        *,
        actor: Actor,
        summary: str,
    ) -> dict[str, Any]:
        summary = validate_text(summary, "summary", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(state)
            self._require_agent_permission(actor, policy, "fail_bolt")
            stage, unit_id = self._current_context(state)
            if unit_id is None:
                raise ConflictError("Bolt failure applies only to per-Unit Construction")
            failure = {
                "unit_id": unit_id,
                "stage": stage,
                "summary": summary,
                "failed_at": values.timestamp,
                "reported_by": actor.actor_id,
            }
            state["workflow"]["failure"] = failure
            state["units"][unit_id]["status"] = "failed"
            return MutationResult(
                event_type="BOLT_FAILED",
                payload=failure,
                result={"failure": failure},
            )

        return self.repository.mutate(actor, mutation)

    def resolve_bolt_failure(
        self,
        *,
        actor: Actor,
        action: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "Bolt failure resolution")
        if action not in {"retry", "skip", "abort"}:
            raise ValidationError("failure action must be retry, skip, or abort")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_running(
                state,
                allow_autonomy_prompt=True,
                allow_failure=True,
            )
            del policy
            failure = state["workflow"]["failure"]
            if failure is None:
                raise ConflictError("no Bolt failure is awaiting resolution")
            unit = state["units"][failure["unit_id"]]
            if action == "retry":
                unit["status"] = "active"
                state["workflow"]["failure"] = None
            elif action == "abort":
                state["workflow"]["failure"] = None
                state["workflow"]["status"] = "aborted"
                state["workflow"]["current_stage"] = None
                state["workflow"]["current_unit_id"] = None
                state["workflow"]["autonomy_prompt_pending"] = False
            else:
                if unit["walking_skeleton"]:
                    raise ConflictError(
                        "the walking-skeleton Bolt cannot be skipped",
                        code="walking_skeleton_required",
                    )
                unit["status"] = "skipped"
                for slug in PER_UNIT_STAGES:
                    if unit["stage_statuses"][slug] not in {"completed", "skipped"}:
                        unit["stage_statuses"][slug] = "skipped"
                state["workflow"]["failure"] = None
                self._sync_all_per_unit_stages(state, values.timestamp)
                current_stage = failure["stage"]
                next_unit = self._next_ready_unit(state, current_stage)
                if next_unit is not None:
                    self._activate_unit_stage(
                        state,
                        current_stage,
                        next_unit,
                        values.timestamp,
                    )
                else:
                    remaining = [
                        item["id"]
                        for item in self._ordered_units(state)
                        if item["status"] != "skipped"
                        and item["stage_statuses"][current_stage] == "pending"
                    ]
                    if remaining:
                        raise ConflictError(
                            "remaining Units are dependency-blocked",
                            details={"unit_ids": remaining},
                        )
                    state["workflow"]["current_unit_id"] = None
                    state["stages"][current_stage]["status"] = "active"
                    if state["workflow"]["construction_autonomy"] == "autonomous":
                        for candidate in self._ordered_units(state):
                            if (
                                candidate["stage_statuses"][current_stage]
                                == "awaiting_approval"
                            ):
                                candidate["stage_statuses"][current_stage] = "completed"
                        self._sync_per_unit_stage(
                            state,
                            current_stage,
                            values.timestamp,
                        )
                        self._advance(
                            state,
                            completed_stage=current_stage,
                            completed_unit_id=None,
                            timestamp=values.timestamp,
                            values=values,
                            actor_id=actor.actor_id,
                        )
                    else:
                        state["stages"][current_stage]["current_gate_id"] = None
                self._refresh_phases(state, values.timestamp)
            return MutationResult(
                event_type="BOLT_FAILURE_RESOLVED",
                payload={
                    "unit_id": failure["unit_id"],
                    "stage": failure["stage"],
                    "action": action,
                },
                result={"workflow": state["workflow"], "unit": unit},
            )

        return self.repository.mutate(actor, mutation)

    def set_depth(self, *, actor: Actor, depth: str) -> dict[str, Any]:
        self._require_human(actor, "depth change")
        depth = validate_depth(depth)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy, values
            self._require_running(state, allow_autonomy_prompt=True)
            previous = state["workflow"]["depth"]
            state["workflow"]["depth"] = depth
            return MutationResult(
                event_type="DEPTH_CHANGED",
                payload={"previous": previous, "depth": depth},
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def set_test_strategy(
        self,
        *,
        actor: Actor,
        test_strategy: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "test strategy change")
        test_strategy = validate_test_strategy(test_strategy)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy, values
            self._require_running(state, allow_autonomy_prompt=True)
            previous = state["workflow"]["test_strategy"]
            state["workflow"]["test_strategy"] = test_strategy
            return MutationResult(
                event_type="TEST_STRATEGY_CHANGED",
                payload={"previous": previous, "test_strategy": test_strategy},
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    @staticmethod
    def _normalize_stage_list(values: Iterable[str]) -> list[str]:
        result = list(dict.fromkeys(values))
        for slug in result:
            validate_stage(slug)
        return result

    def recompose(
        self,
        *,
        actor: Actor,
        add: list[str] | None = None,
        skip: list[str] | None = None,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "workflow recomposition")
        add_stages = self._normalize_stage_list(add or ())
        skip_stages = self._normalize_stage_list(skip or ())
        if set(add_stages).intersection(skip_stages):
            raise ValidationError("a stage cannot be both added and skipped")
        if not add_stages and not skip_stages:
            raise ValidationError("recomposition requires at least one stage change")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            self._require_running(state, allow_autonomy_prompt=True)
            if (
                STAGE_BY_SLUG[state["workflow"]["current_stage"]].phase == "construction"
                and state["workflow"]["construction_autonomy"] == "autonomous"
            ):
                raise ConflictError(
                    "recomposition is forbidden during autonomous Construction",
                    code="autonomous_recompose_forbidden",
                )
            current_stage, _ = self._current_context(state)
            current_index = STAGE_INDEX[current_stage]
            changed = [*add_stages, *skip_stages]
            for slug in changed:
                definition = STAGE_BY_SLUG[slug]
                record = state["stages"][slug]
                if definition.is_initialization:
                    raise ConflictError("initialization stages are immutable")
                if STAGE_INDEX[slug] <= current_index:
                    raise ConflictError(
                        "recomposition can change only ahead-of-cursor stages",
                        details={"stage": slug},
                    )
                if record["status"] not in {"pending", "skipped"}:
                    raise ConflictError(
                        "completed or in-progress stages are frozen",
                        details={"stage": slug, "status": record["status"]},
                    )
            old_anchor = self._first_per_unit_stage(state)
            proposed = self._plan(state)
            for slug in add_stages:
                proposed[slug] = "execute"
            for slug in skip_stages:
                proposed[slug] = "skip"
            new_anchor = next(
                (slug for slug in PER_UNIT_STAGES if proposed[slug] == "execute"),
                None,
            )
            if old_anchor != new_anchor:
                raise ConflictError(
                    "the first executable Construction stage is the walking-skeleton anchor",
                    code="walking_skeleton_anchor_frozen",
                    details={"current": old_anchor, "proposed": new_anchor},
                )
            for slug in add_stages:
                state["stages"][slug]["decision"] = "execute"
                state["stages"][slug]["status"] = "pending"
            for slug in skip_stages:
                state["stages"][slug]["decision"] = "skip"
                state["stages"][slug]["status"] = "skipped"
                state["stages"][slug]["started_at"] = None
                state["stages"][slug]["completed_at"] = None
            for unit in state["units"].values():
                for slug in PER_UNIT_STAGES:
                    if slug in add_stages:
                        unit["stage_statuses"][slug] = "pending"
                    elif slug in skip_stages:
                        unit["stage_statuses"][slug] = "skipped"
            state["workflow"]["scope_source"] = "composed"
            state["workflow"]["composition_revision"] += 1
            self._refresh_phases(state, values.timestamp)
            return MutationResult(
                event_type="RECOMPOSED",
                payload={
                    "add": add_stages,
                    "skip": skip_stages,
                    "reason": reason,
                    "composition_revision": state["workflow"]["composition_revision"],
                },
                result={
                    "workflow": state["workflow"],
                    "plan": self._plan(state),
                },
            )

        return self.repository.mutate(actor, mutation)

    def skip_current_stage(
        self,
        *,
        actor: Actor,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "stage skip")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            self._require_running(state, allow_autonomy_prompt=True)
            stage, unit_id = self._current_context(state)
            if unit_id is not None or STAGE_BY_SLUG[stage].phase not in {
                "ideation",
                "inception",
            }:
                raise ConflictError(
                    "interactive skip is limited to Ideation and Inception",
                    code="stage_skip_not_allowed",
                )
            gate_id = state["stages"][stage]["current_gate_id"]
            if gate_id is not None and state["gates"][gate_id]["status"] == "pending":
                gate = state["gates"][gate_id]
                gate["status"] = "superseded"
                gate["decided_by"] = actor.actor_id
                gate["decided_at"] = values.timestamp
                gate["reason"] = reason
            state["stages"][stage]["decision"] = "skip"
            state["stages"][stage]["status"] = "skipped"
            state["stages"][stage]["current_gate_id"] = None
            self._advance(
                state,
                completed_stage=stage,
                completed_unit_id=None,
                timestamp=values.timestamp,
                values=values,
                actor_id=actor.actor_id,
            )
            return MutationResult(
                event_type="STAGE_SKIPPED",
                payload={
                    "stage": stage,
                    "reason": reason,
                    "next_stage": state["workflow"]["current_stage"],
                },
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def jump_to_stage(
        self,
        *,
        actor: Actor,
        target_stage: str,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "stage jump")
        target_stage = validate_stage(target_stage)
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            self._require_running(state, allow_autonomy_prompt=True)
            current_stage, current_unit_id = self._current_context(state)
            if current_unit_id is not None:
                raise ConflictError("jump is unavailable inside a Bolt")
            if STAGE_INDEX[target_stage] <= STAGE_INDEX[current_stage]:
                raise ConflictError("jump target must be ahead of the current stage")
            target_record = state["stages"][target_stage]
            if target_record["status"] not in {"pending", "skipped"}:
                raise ConflictError("jump target is not available")
            skipped: list[str] = []
            for stage in STAGES[
                STAGE_INDEX[current_stage] : STAGE_INDEX[target_stage]
            ]:
                if stage.is_initialization:
                    continue
                record = state["stages"][stage.slug]
                if record["status"] in {
                    "active",
                    "awaiting_approval",
                    "revising",
                    "pending",
                }:
                    gate_id = record["current_gate_id"]
                    if gate_id is not None and state["gates"][gate_id]["status"] == "pending":
                        gate = state["gates"][gate_id]
                        gate["status"] = "superseded"
                        gate["decided_by"] = actor.actor_id
                        gate["decided_at"] = values.timestamp
                        gate["reason"] = reason
                    record["decision"] = "skip"
                    record["status"] = "skipped"
                    record["current_gate_id"] = None
                    skipped.append(stage.slug)
            target_record["decision"] = "execute"
            target_record["status"] = "pending"
            self._activate_stage(
                state,
                target_stage,
                values.timestamp,
                values,
                actor.actor_id,
            )
            self._refresh_phases(state, values.timestamp)
            return MutationResult(
                event_type="STAGE_JUMPED",
                payload={
                    "from_stage": current_stage,
                    "target_stage": target_stage,
                    "skipped": skipped,
                    "reason": reason,
                },
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def redo_current_stage(
        self,
        *,
        actor: Actor,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "stage redo")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            self._require_running(state, allow_autonomy_prompt=True)
            stage, unit_id = self._current_context(state)
            gate_id = state["stages"][stage]["current_gate_id"]
            if gate_id is not None and state["gates"][gate_id]["status"] == "pending":
                gate = state["gates"][gate_id]
                gate["status"] = "superseded"
                gate["decided_by"] = actor.actor_id
                gate["decided_at"] = values.timestamp
                gate["reason"] = reason
            state["stages"][stage]["current_gate_id"] = None
            if unit_id is not None:
                state["units"][unit_id]["stage_statuses"][stage] = "active"
                self._sync_per_unit_stage(state, stage, values.timestamp)
            else:
                state["stages"][stage]["status"] = "active"
            return MutationResult(
                event_type="STAGE_REDO",
                payload={"stage": stage, "unit_id": unit_id, "reason": reason},
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def park(self, *, actor: Actor, reason: str) -> dict[str, Any]:
        self._require_human(actor, "workflow park")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            self._require_running(state, allow_autonomy_prompt=True)
            stage, _ = self._current_context(state)
            if (
                STAGE_BY_SLUG[stage].phase == "construction"
                and state["workflow"]["construction_autonomy"] == "autonomous"
            ):
                raise ConflictError(
                    "an unattended autonomous Construction run cannot be parked",
                    code="autonomous_park_forbidden",
                )
            state["workflow"]["status"] = "parked"
            state["workflow"]["parked_at"] = values.timestamp
            return MutationResult(
                event_type="WORKFLOW_PARKED",
                payload={"stage": stage, "reason": reason},
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def resume(self, *, actor: Actor) -> dict[str, Any]:
        self._require_human(actor, "workflow resume")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy, values
            if state["workflow"]["status"] != "parked":
                raise ConflictError("workflow is not parked")
            state["workflow"]["status"] = "running"
            state["workflow"]["parked_at"] = None
            return MutationResult(
                event_type="WORKFLOW_UNPARKED",
                payload={
                    "stage": state["workflow"]["current_stage"],
                    "unit_id": state["workflow"]["current_unit_id"],
                },
                result={"workflow": state["workflow"]},
            )

        return self.repository.mutate(actor, mutation)

    def propose_learning(
        self,
        *,
        actor: Actor,
        section: str,
        summary: str,
    ) -> dict[str, Any]:
        if section not in {
            "interpretation",
            "deviation",
            "tradeoff",
            "open-question",
        }:
            raise ValidationError("learning section is invalid")
        summary = validate_text(summary, "summary", maximum=2000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            self._require_agent_permission(actor, policy, "propose_learning")
            if len(state["learnings"]) >= policy["limits"]["max_learnings"]:
                raise ConflictError("the configured learning limit has been reached")
            learning_id = values.identifier("learning", f"{section}:{summary}")
            learning = {
                "id": learning_id,
                "section": section,
                "summary": summary,
                "status": "candidate",
                "target_scope": None,
                "proposed_by": actor.actor_id,
                "proposed_at": values.timestamp,
                "decided_by": None,
                "decided_at": None,
            }
            state["learnings"][learning_id] = learning
            return MutationResult(
                event_type="LEARNING_CANDIDATE_RECORDED",
                payload={"learning_id": learning_id, "section": section},
                result={"learning": learning},
            )

        return self.repository.mutate(actor, mutation)

    def decide_learning(
        self,
        *,
        actor: Actor,
        learning_id: str,
        decision: str,
        target_scope: str | None = None,
    ) -> dict[str, Any]:
        self._require_human(actor, "learning decision")
        if decision not in {"keep", "reject"}:
            raise ValidationError("learning decision must be keep or reject")
        if target_scope not in {None, "project", "team"}:
            raise ValidationError("learning target scope must be project or team")

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            learning = state["learnings"].get(learning_id)
            if learning is None:
                raise NotFoundError("learning candidate was not found")
            if learning["status"] != "candidate":
                raise ConflictError("learning candidate is already resolved")
            if decision == "keep":
                if learning["section"] == "open-question":
                    raise ConflictError("open questions cannot become learned rules")
                if target_scope is None:
                    raise ValidationError("kept learning requires project or team scope")
                learning["status"] = "kept"
                learning["target_scope"] = target_scope
                event_type = "RULE_LEARNED"
            else:
                learning["status"] = "rejected"
                learning["target_scope"] = None
                event_type = "LEARNING_REJECTED"
            learning["decided_by"] = actor.actor_id
            learning["decided_at"] = values.timestamp
            return MutationResult(
                event_type=event_type,
                payload={
                    "learning_id": learning_id,
                    "decision": decision,
                    "target_scope": learning["target_scope"],
                    "effective": "next-workflow",
                },
                result={"learning": learning},
            )

        return self.repository.mutate(actor, mutation)

    def loop_to_ideation(
        self,
        *,
        actor: Actor,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "workflow feedback loop")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(
            state: dict[str, Any],
            policy: dict[str, Any],
            values: Any,
        ) -> MutationResult:
            del policy
            if state["workflow"]["status"] != "completed":
                raise ConflictError("only a completed workflow can loop to Ideation")
            for stage in STAGES:
                if stage.is_initialization:
                    continue
                record = state["stages"][stage.slug]
                record["status"] = (
                    "pending" if record["decision"] == "execute" else "skipped"
                )
                record["started_at"] = None
                record["completed_at"] = None
                record["current_gate_id"] = None
                record["revision_count"] = 0
                record["reviewer_iterations"] = 0
            for unit in state["units"].values():
                unit["status"] = "planned"
                unit["completed_at"] = None
                for slug in PER_UNIT_STAGES:
                    unit["stage_statuses"][slug] = (
                        "pending"
                        if state["stages"][slug]["decision"] == "execute"
                        else "skipped"
                    )
            workflow = state["workflow"]
            workflow["status"] = "running"
            workflow["iteration"] += 1
            workflow["completed_at"] = None
            workflow["parked_at"] = None
            workflow["failure"] = None
            workflow["construction_autonomy"] = None
            workflow["autonomy_prompt_pending"] = False
            first_stage = next(
                stage.slug
                for stage in STAGES
                if not stage.is_initialization
                and state["stages"][stage.slug]["decision"] == "execute"
            )
            self._activate_stage(
                state,
                first_stage,
                values.timestamp,
                values,
                actor.actor_id,
            )
            self._refresh_phases(state, values.timestamp)
            return MutationResult(
                event_type="WORKFLOW_LOOPED",
                payload={
                    "iteration": workflow["iteration"],
                    "reason": reason,
                    "current_stage": workflow["current_stage"],
                },
                result={"workflow": workflow},
            )

        return self.repository.mutate(actor, mutation)

    def guard_operation(self, *, actor: Actor, operation: str) -> dict[str, Any]:
        if not isinstance(operation, str) or not operation.strip():
            raise ValidationError("operation is required")
        operation = operation.strip()
        policy = self.repository.load_policy()
        self._require_agent_permission(actor, policy, operation)
        return {
            "allowed": True,
            "operation": operation,
            "actor": actor.to_dict(),
        }

    def outcomes(self) -> dict[str, Any]:
        state = self.repository.load()
        completed = [
            slug for slug, record in state["stages"].items() if record["status"] == "completed"
        ]
        skipped = [
            slug for slug, record in state["stages"].items() if record["status"] == "skipped"
        ]
        return {
            "project": state["project"],
            "workflow": state["workflow"],
            "active_stage_count": sum(
                record["decision"] == "execute"
                for record in state["stages"].values()
            ),
            "completed_stages": completed,
            "skipped_stages": skipped,
            "artifact_count": len(state["artifacts"]),
            "gate_count": len(state["gates"]),
            "unit_count": len(state["units"]),
            "kept_learnings": [
                learning
                for learning in state["learnings"].values()
                if learning["status"] == "kept"
            ],
            "audit": self.repository.verify_audit(),
        }
