"""Pinned AI-DLC v2 methodology catalog and deterministic routing helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

PHASES = (
    "initialization",
    "ideation",
    "inception",
    "construction",
    "operation",
)

DEPTH_LEVELS = ("minimal", "standard", "comprehensive")
TEST_STRATEGIES = ("minimal", "standard", "comprehensive")
UNIT_KINDS = ("service", "spec", "ui", "packaging", "library")
EXECUTION_TYPES = ("always", "conditional")
STAGE_MODES = ("inline", "mob", "pipeline", "subagent")
REVIEW_CLASSES = ("advisory", "adversarial")
REVIEW_CAPS = ("none", "advisory", "adversarial")
SCOPE_ORDER = (
    "enterprise",
    "feature",
    "mvp",
    "poc",
    "bugfix",
    "refactor",
    "infra",
    "security-patch",
    "classic",
    "workshop",
    "express",
)

DOMAIN_AGENTS = (
    "aidlc-product-agent",
    "aidlc-design-agent",
    "aidlc-delivery-agent",
    "aidlc-architect-agent",
    "aidlc-aws-platform-agent",
    "aidlc-compliance-agent",
    "aidlc-devsecops-agent",
    "aidlc-developer-agent",
    "aidlc-quality-agent",
    "aidlc-pipeline-deploy-agent",
    "aidlc-operations-agent",
)
REVIEW_AGENTS = (
    "aidlc-product-lead-agent",
    "aidlc-architecture-reviewer-agent",
)
COMPOSER_AGENT = "aidlc-composer-agent"
ORCHESTRATOR = "orchestrator"
KNOWN_AGENTS = (ORCHESTRATOR, COMPOSER_AGENT, *DOMAIN_AGENTS, *REVIEW_AGENTS)


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    name: str
    required: bool
    conditional_on: str | None = None


@dataclass(frozen=True, slots=True)
class StageDefinition:
    slug: str
    number: str
    name: str
    phase: str
    execution: str
    condition: str
    lead_agent: str
    support_agents: tuple[str, ...]
    mode: str
    produces: tuple[str, ...]
    optional_produces: tuple[str, ...]
    produces_kinds: dict[str, tuple[str, ...]]
    consumes: tuple[ArtifactInput, ...]
    requires_stage: tuple[str, ...]
    sensors: tuple[str, ...]
    reviewer: str | None
    review_artifact: str | None
    review_class: str | None
    reviewer_max_iterations: int
    for_each: str | None
    workspace_requires: bool

    @property
    def is_initialization(self) -> bool:
        return self.phase == "initialization"

    @property
    def is_per_unit(self) -> bool:
        return self.for_each == "unit-of-work"


@dataclass(frozen=True, slots=True)
class ScopeDetection:
    scope: str
    confidence: str
    reason: str
    needs_composition: bool
    matched_scopes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "confidence": self.confidence,
            "reason": self.reason,
            "needs_composition": self.needs_composition,
            "matched_scopes": list(self.matched_scopes),
        }


def _load_json(name: str) -> dict[str, Any]:
    path = files(__package__).joinpath("data", name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"catalog resource {name} must contain an object")
    return value


_STAGE_RESOURCE = _load_json("stage-catalog.json")
_SCOPE_RESOURCE = _load_json("scope-grid.json")
UPSTREAM_BASELINE = dict(_STAGE_RESOURCE["upstream"])


def _stage_from_record(record: dict[str, Any]) -> StageDefinition:
    consumes = tuple(
        ArtifactInput(
            name=item["artifact"],
            required=item["required"],
            conditional_on=item.get("conditional_on"),
        )
        for item in record.get("consumes", ())
    )
    return StageDefinition(
        slug=record["slug"],
        number=record["number"],
        name=record["name"],
        phase=record["phase"],
        execution=record["execution"].casefold(),
        condition=record["condition"],
        lead_agent=record["lead_agent"],
        support_agents=tuple(record.get("support_agents", ())),
        mode=record["mode"],
        produces=tuple(record.get("produces", ())),
        optional_produces=tuple(record.get("optional_produces", ())),
        produces_kinds={
            artifact: tuple(kinds)
            for artifact, kinds in record.get("produces_kinds", {}).items()
        },
        consumes=consumes,
        requires_stage=tuple(record.get("requires_stage", ())),
        sensors=tuple(record.get("sensors", ())),
        reviewer=record.get("reviewer"),
        review_artifact=record.get("review_artifact"),
        review_class=record.get("review_class"),
        reviewer_max_iterations=record.get("reviewer_max_iterations", 0),
        for_each=record.get("for_each"),
        workspace_requires=record.get("workspace_requires", False),
    )


STAGES = tuple(_stage_from_record(record) for record in _STAGE_RESOURCE["stages"])
STAGE_SLUGS = tuple(stage.slug for stage in STAGES)
STAGE_INDEX = {stage.slug: index for index, stage in enumerate(STAGES)}
STAGE_BY_SLUG = {stage.slug: stage for stage in STAGES}
PER_UNIT_STAGES = tuple(stage.slug for stage in STAGES if stage.is_per_unit)

SCOPES = SCOPE_ORDER
SCOPE_CONFIG = {
    name: {
        "depth": record["depth"],
        "test_strategy": record["test_strategy"],
        "skeleton": record["skeleton"],
        "review_cap": record["review_cap"],
        "stages": {
            slug: decision.casefold() for slug, decision in record["stages"].items()
        },
    }
    for name, record in _SCOPE_RESOURCE["scopes"].items()
}

_artifact_producers: dict[str, list[str]] = {}
for _stage in STAGES:
    for _artifact in (*_stage.produces, *_stage.optional_produces):
        _artifact_producers.setdefault(_artifact, []).append(_stage.slug)
ARTIFACT_PRODUCERS = {
    artifact: tuple(producers)
    for artifact, producers in _artifact_producers.items()
}


def _validate_catalog() -> None:
    if len(PHASES) != 5 or len(STAGES) != 33 or len(SCOPES) != 11:
        raise RuntimeError("the pinned AI-DLC v2 catalog has an unexpected size")
    if len(STAGE_BY_SLUG) != len(STAGES):
        raise RuntimeError("stage slugs must be unique")
    if tuple(dict.fromkeys(stage.phase for stage in STAGES)) != PHASES:
        raise RuntimeError("stage phases are not in the expected order")
    if set(SCOPE_CONFIG) != set(SCOPES):
        raise RuntimeError("scope configuration is inconsistent")
    for scope, config in SCOPE_CONFIG.items():
        if set(config["stages"]) != set(STAGE_SLUGS):
            raise RuntimeError(f"scope {scope} does not cover every stage")
        if config["depth"] not in DEPTH_LEVELS:
            raise RuntimeError(f"scope {scope} has an invalid depth")
        if config["test_strategy"] not in TEST_STRATEGIES:
            raise RuntimeError(f"scope {scope} has an invalid test strategy")
        if not isinstance(config["skeleton"], bool):
            raise RuntimeError(f"scope {scope} has an invalid skeleton setting")
        if config["review_cap"] not in REVIEW_CAPS:
            raise RuntimeError(f"scope {scope} has an invalid review cap")
    for stage in STAGES:
        if stage.execution not in EXECUTION_TYPES:
            raise RuntimeError(f"stage {stage.slug} has an invalid execution type")
        if stage.mode not in STAGE_MODES:
            raise RuntimeError(f"stage {stage.slug} has an invalid mode")
        if stage.lead_agent not in KNOWN_AGENTS:
            raise RuntimeError(f"stage {stage.slug} has an unknown lead agent")
        if any(agent not in KNOWN_AGENTS for agent in stage.support_agents):
            raise RuntimeError(f"stage {stage.slug} has an unknown support agent")
        if stage.reviewer is not None and stage.reviewer not in REVIEW_AGENTS:
            raise RuntimeError(f"stage {stage.slug} has an unknown reviewer")
        if (stage.reviewer is None) != (stage.review_artifact is None):
            raise RuntimeError(
                f"stage {stage.slug} reviewer and review artifact must be paired"
            )
        if stage.review_artifact is not None and stage.review_artifact not in stage.produces:
            raise RuntimeError(
                f"stage {stage.slug} review artifact must be a required output"
            )
        if stage.review_class is not None and stage.review_class not in REVIEW_CLASSES:
            raise RuntimeError(f"stage {stage.slug} has an invalid review class")
        if (stage.reviewer is None) != (stage.review_class is None):
            raise RuntimeError(
                f"stage {stage.slug} reviewer and review class must be paired"
            )
        if any(required not in STAGE_BY_SLUG for required in stage.requires_stage):
            raise RuntimeError(f"stage {stage.slug} references an unknown dependency")


_validate_catalog()


_SCOPE_PATTERNS = (
    ("security-patch", (r"\bsecurity\b", r"\bcve[- ]?\d*", r"\bvulnerabilit", r"\bpatch\b")),
    ("bugfix", (r"\bbug\b", r"\bbugfix\b", r"\bfix\b", r"\bbroken\b", r"\bdefect\b")),
    ("refactor", (r"\brefactor", r"\bclean[ -]?up\b", r"\bsimplif")),
    ("infra", (r"\binfrastructure\b", r"\binfra\b", r"\bprovision", r"\bdeploy")),
    ("poc", (r"\bproof of concept\b", r"\bprototype\b", r"\bpoc\b", r"\bspike\b")),
    ("mvp", (r"\bminimum viable\b", r"\bmvp\b")),
    ("workshop", (r"\bworkshop\b", r"\blab\b", r"\btraining\b")),
    ("express", (r"\bexpress\b", r"\blightweight\b")),
)


def detect_scope(description: str) -> ScopeDetection:
    """Return deterministic keyword routing and surface ambiguous compositions."""

    normalized = " ".join(description.casefold().split())
    matches = tuple(
        scope
        for scope, patterns in _SCOPE_PATTERNS
        if any(re.search(pattern, normalized) for pattern in patterns)
    )
    word_count = len(normalized.split())
    if len(matches) == 1 and word_count <= 5:
        return ScopeDetection(
            scope=matches[0],
            confidence="high",
            reason=f"description matched the {matches[0]} routing vocabulary",
            needs_composition=False,
            matched_scopes=matches,
        )
    if len(matches) > 1:
        return ScopeDetection(
            scope="classic",
            confidence="ambiguous",
            reason="description matched multiple scope vocabularies",
            needs_composition=True,
            matched_scopes=matches,
        )
    if len(matches) == 1:
        return ScopeDetection(
            scope=matches[0],
            confidence="contextual",
            reason=(
                "a specialized scope keyword appeared in a longer description; "
                "adaptive composition is required"
            ),
            needs_composition=True,
            matched_scopes=matches,
        )
    if word_count > 5:
        return ScopeDetection(
            scope="classic",
            confidence="compose",
            reason=(
                "rich freeform intent did not clearly select a stock scope; "
                "adaptive composition is required"
            ),
            needs_composition=True,
            matched_scopes=(),
        )
    return ScopeDetection(
        scope="classic",
        confidence="default",
        reason="no specialized routing vocabulary matched; using the classic default",
        needs_composition=False,
        matched_scopes=(),
    )


def stage_definition(slug: str) -> StageDefinition:
    try:
        return STAGE_BY_SLUG[slug]
    except KeyError as error:
        raise KeyError(f"unknown AI-DLC v2 stage: {slug}") from error


def stage_plan(scope: str) -> dict[str, str]:
    try:
        return dict(SCOPE_CONFIG[scope]["stages"])
    except KeyError as error:
        raise KeyError(f"unknown AI-DLC v2 scope: {scope}") from error


def active_stage_slugs(scope: str) -> tuple[str, ...]:
    plan = stage_plan(scope)
    return tuple(slug for slug in STAGE_SLUGS if plan[slug] == "execute")


def required_outputs(slug: str, unit_kind: str | None = None) -> tuple[str, ...]:
    stage = stage_definition(slug)
    required: list[str] = []
    for artifact in stage.produces:
        applicable_kinds = stage.produces_kinds.get(artifact)
        if (
            applicable_kinds is None
            or unit_kind is None
            or unit_kind in applicable_kinds
        ):
            required.append(artifact)
    return tuple(required)


def required_inputs(
    slug: str,
    *,
    plan: dict[str, str],
    workspace_kind: str,
) -> tuple[str, ...]:
    stage = stage_definition(slug)
    required: list[str] = []
    for item in stage.consumes:
        if not item.required:
            continue
        if item.conditional_on is not None and item.conditional_on != workspace_kind:
            continue
        producers = ARTIFACT_PRODUCERS.get(item.name, ())
        if producers and not any(plan.get(producer) == "execute" for producer in producers):
            continue
        required.append(item.name)
    return tuple(required)


def scope_summary(scope: str) -> dict[str, Any]:
    config = SCOPE_CONFIG[scope]
    active = active_stage_slugs(scope)
    return {
        "scope": scope,
        "active_stage_count": len(active),
        "total_stage_count": len(STAGES),
        "depth": config["depth"],
        "test_strategy": config["test_strategy"],
        "skeleton": config["skeleton"],
        "review_cap": config["review_cap"],
        "active_stages": list(active),
    }


def public_catalog() -> dict[str, Any]:
    return {
        "upstream_baseline": dict(UPSTREAM_BASELINE),
        "phases": list(PHASES),
        "stage_count": len(STAGES),
        "scopes": [scope_summary(scope) for scope in SCOPES],
        "domain_agents": list(DOMAIN_AGENTS),
        "review_agents": list(REVIEW_AGENTS),
        "composer_agent": COMPOSER_AGENT,
        "depth_levels": list(DEPTH_LEVELS),
        "test_strategies": list(TEST_STRATEGIES),
        "unit_kinds": list(UNIT_KINDS),
    }
