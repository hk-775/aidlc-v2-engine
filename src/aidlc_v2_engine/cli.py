"""Command-line interface with stable JSON results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from aidlc_v2_engine.catalog import (
    DEPTH_LEVELS,
    SCOPES,
    TEST_STRATEGIES,
    UNIT_KINDS,
    detect_scope,
    public_catalog,
)
from aidlc_v2_engine.demo import run_demo
from aidlc_v2_engine.errors import AIDLCEngineError, PersistenceError, ValidationError
from aidlc_v2_engine.models import Actor, QUESTION_MODES, SENSOR_STATUSES
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.policy import validate_policy
from aidlc_v2_engine.service import LifecycleService, sha256_digest
from aidlc_v2_engine.values import DeterministicValueProvider, ValueProvider, parse_timestamp


def _actor_from_args(args: argparse.Namespace) -> Actor:
    return Actor(
        actor_id=args.actor_id,
        kind=args.actor_kind,
        roles=tuple(args.role or ()),
    )


def _add_actor_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--actor-kind", required=True, choices=("human", "agent"))
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        help="Asserted actor role; repeat for more than one role.",
    )


def _load_json_file(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise PersistenceError(
            "JSON file could not be read",
            details={"path": str(path), "reason": str(error)},
        ) from error
    if not isinstance(value, dict):
        raise ValidationError("JSON file root must be an object")
    return value


def _provider_from_args(args: argparse.Namespace) -> ValueProvider:
    if args.id_seed is None and args.fixed_time is None:
        return ValueProvider()
    if args.id_seed is None or args.fixed_time is None:
        raise ValidationError("--id-seed and --fixed-time must be supplied together")
    return DeterministicValueProvider(
        seed=args.id_seed,
        base_time=parse_timestamp(args.fixed_time),
    )


def _emit(value: dict[str, Any], *, pretty: bool, stream: Any | None = None) -> None:
    stream = stream or sys.stdout
    json.dump(
        value,
        stream,
        indent=2 if pretty else None,
        sort_keys=True,
        separators=None if pretty else (",", ":"),
    )
    stream.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aidlc-v2",
        description="Independent local automation engine for AI-DLC v2.",
    )
    parser.add_argument(
        "--store",
        default=".aidlc-v2",
        help="Local workflow storage directory.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--id-seed", help="Deterministic identifier seed.")
    parser.add_argument("--fixed-time", help="Deterministic UTC ISO-8601 base time.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("catalog", help="Return the pinned methodology catalog.")
    detect = subparsers.add_parser("detect-scope", help="Detect scope from an intent.")
    detect.add_argument("--description", required=True)

    init = subparsers.add_parser("init", help="Initialize an AI-DLC v2 workflow.")
    init.add_argument("--name", required=True)
    init.add_argument("--description", required=True)
    init.add_argument(
        "--workspace-kind",
        choices=("greenfield", "brownfield"),
        default="greenfield",
    )
    init.add_argument("--scope", choices=("auto", *SCOPES), default="auto")
    init.add_argument("--depth", choices=DEPTH_LEVELS)
    init.add_argument("--test-strategy", choices=TEST_STRATEGIES)
    init.add_argument("--policy")
    _add_actor_arguments(init)

    subparsers.add_parser("status", help="Return complete workflow state.")
    subparsers.add_parser("plan", help="Return the current execute/skip stage plan.")
    subparsers.add_parser("policy", help="Return the active policy.")
    subparsers.add_parser("outcomes", help="Return a compact outcomes pack.")
    subparsers.add_parser("verify-audit", help="Verify the complete audit hash chain.")
    subparsers.add_parser("events", help="Return all audit events in sequence.")

    validate_parser = subparsers.add_parser(
        "validate-policy",
        help="Validate a policy file without changing workflow state.",
    )
    validate_parser.add_argument("--file", required=True)

    unit = subparsers.add_parser("add-unit", help="Add a Unit of Work / Bolt.")
    _add_actor_arguments(unit)
    unit.add_argument("--name", required=True)
    unit.add_argument("--kind", choices=UNIT_KINDS, required=True)
    unit.add_argument("--depends-on", action="append", default=[])

    artifact = subparsers.add_parser(
        "add-artifact",
        help="Register a declared artifact for the current stage context.",
    )
    _add_actor_arguments(artifact)
    artifact.add_argument("--name", required=True)
    artifact.add_argument("--title", required=True)
    digest_group = artifact.add_mutually_exclusive_group(required=True)
    digest_group.add_argument("--digest")
    digest_group.add_argument("--file")
    artifact.add_argument("--locator", default="")
    artifact.add_argument("--workspace-change", action="store_true")

    question = subparsers.add_parser(
        "answer-question",
        help="Record one canonical tri-mode question answer.",
    )
    _add_actor_arguments(question)
    question.add_argument("--mode", choices=QUESTION_MODES, required=True)
    question.add_argument("--prompt", required=True)
    question.add_argument("--answer", required=True)

    sensor = subparsers.add_parser("record-sensor", help="Record an advisory sensor result.")
    _add_actor_arguments(sensor)
    sensor.add_argument("--sensor", required=True)
    sensor.add_argument("--status", choices=SENSOR_STATUSES, required=True)
    sensor.add_argument("--summary", required=True)

    review = subparsers.add_parser(
        "record-review",
        help="Record an independent READY or NOT-READY reviewer verdict.",
    )
    _add_actor_arguments(review)
    review.add_argument("--verdict", choices=("ready", "not-ready"), required=True)
    review.add_argument("--summary", required=True)

    request = subparsers.add_parser(
        "request-approval",
        help="Open the human approval gate for the current stage context.",
    )
    _add_actor_arguments(request)
    request.add_argument("--rationale", required=True)
    request.add_argument("--evidence", action="append", default=[])

    settle_unit = subparsers.add_parser(
        "complete-unit-stage",
        help="Settle one Unit iteration before the stage-major Construction gate.",
    )
    _add_actor_arguments(settle_unit)

    approve = subparsers.add_parser("approve-stage", help="Approve a pending stage gate.")
    _add_actor_arguments(approve)
    approve.add_argument("--gate-id", required=True)
    approve.add_argument("--accept-as-is", action="store_true")

    reject = subparsers.add_parser("reject-stage", help="Reject a pending stage gate.")
    _add_actor_arguments(reject)
    reject.add_argument("--gate-id", required=True)
    reject.add_argument("--reason", required=True)

    autonomous = subparsers.add_parser(
        "complete-autonomous",
        help="Complete the current non-skeleton Unit stage under granted autonomy.",
    )
    _add_actor_arguments(autonomous)

    autonomy = subparsers.add_parser(
        "set-autonomy",
        help="Resolve the post-walking-skeleton autonomy ladder.",
    )
    _add_actor_arguments(autonomy)
    autonomy.add_argument("--mode", choices=("autonomous", "gated"), required=True)

    fail_bolt = subparsers.add_parser("fail-bolt", help="Halt on a Bolt failure.")
    _add_actor_arguments(fail_bolt)
    fail_bolt.add_argument("--summary", required=True)

    resolve_bolt = subparsers.add_parser(
        "resolve-bolt-failure",
        help="Choose retry, skip, or abort after a Bolt failure.",
    )
    _add_actor_arguments(resolve_bolt)
    resolve_bolt.add_argument("--action", choices=("retry", "skip", "abort"), required=True)

    depth = subparsers.add_parser("set-depth", help="Change artifact depth.")
    _add_actor_arguments(depth)
    depth.add_argument("--depth", choices=DEPTH_LEVELS, required=True)

    strategy = subparsers.add_parser(
        "set-test-strategy",
        help="Change the independent test strategy.",
    )
    _add_actor_arguments(strategy)
    strategy.add_argument("--test-strategy", choices=TEST_STRATEGIES, required=True)

    compose = subparsers.add_parser(
        "recompose",
        help="Change pending ahead-of-cursor execute/skip decisions.",
    )
    _add_actor_arguments(compose)
    compose.add_argument("--add", action="append", default=[])
    compose.add_argument("--skip", action="append", default=[])
    compose.add_argument("--reason", required=True)

    skip = subparsers.add_parser("skip-stage", help="Skip the current early-phase stage.")
    _add_actor_arguments(skip)
    skip.add_argument("--reason", required=True)

    jump = subparsers.add_parser("jump-stage", help="Jump to a later stage.")
    _add_actor_arguments(jump)
    jump.add_argument("--target", required=True)
    jump.add_argument("--reason", required=True)

    redo = subparsers.add_parser("redo-stage", help="Redo the current stage context.")
    _add_actor_arguments(redo)
    redo.add_argument("--reason", required=True)

    park = subparsers.add_parser("park", help="Park the workflow.")
    _add_actor_arguments(park)
    park.add_argument("--reason", required=True)

    resume = subparsers.add_parser("resume", help="Resume a parked workflow.")
    _add_actor_arguments(resume)

    learning = subparsers.add_parser(
        "propose-learning",
        help="Record a memory diary learning candidate.",
    )
    _add_actor_arguments(learning)
    learning.add_argument(
        "--section",
        choices=("interpretation", "deviation", "tradeoff", "open-question"),
        required=True,
    )
    learning.add_argument("--summary", required=True)

    decide = subparsers.add_parser(
        "decide-learning",
        help="Keep or reject a learning candidate.",
    )
    _add_actor_arguments(decide)
    decide.add_argument("--learning-id", required=True)
    decide.add_argument("--decision", choices=("keep", "reject"), required=True)
    decide.add_argument("--target-scope", choices=("project", "team"))

    loop = subparsers.add_parser(
        "loop-to-ideation",
        help="Start a new lifecycle iteration from a completed workflow.",
    )
    _add_actor_arguments(loop)
    loop.add_argument("--reason", required=True)

    guard = subparsers.add_parser(
        "guard-operation",
        help="Check whether an asserted actor may request an operation.",
    )
    _add_actor_arguments(guard)
    guard.add_argument("--operation", required=True)

    subparsers.add_parser(
        "demo",
        help="Run the deterministic synthetic bugfix workflow demonstration.",
    )
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "catalog":
        return {"ok": True, "catalog": public_catalog()}
    if args.command == "detect-scope":
        return {"ok": True, "detection": detect_scope(args.description).to_dict()}
    if args.command == "validate-policy":
        policy = validate_policy(_load_json_file(args.file))
        return {"ok": True, "valid": True, "schema_version": policy["schema_version"]}
    if args.command == "demo":
        return {"ok": True, "demo": run_demo(args.store)}

    provider = _provider_from_args(args)
    repository = JsonProjectRepository(args.store, provider)
    service = LifecycleService(repository)
    if args.command == "init":
        policy = _load_json_file(args.policy) if args.policy else None
        state = service.initialize(
            name=args.name,
            description=args.description,
            creator=_actor_from_args(args),
            workspace_kind=args.workspace_kind,
            scope=args.scope,
            depth=args.depth,
            test_strategy=args.test_strategy,
            policy=policy,
        )
        return {"ok": True, "state": state}
    if args.command == "status":
        return {"ok": True, "state": repository.load()}
    if args.command == "plan":
        state = repository.load()
        return {
            "ok": True,
            "scope": state["workflow"]["scope"],
            "composition_revision": state["workflow"]["composition_revision"],
            "plan": {
                slug: record["decision"]
                for slug, record in state["stages"].items()
            },
        }
    if args.command == "policy":
        return {"ok": True, "policy": repository.load_policy()}
    if args.command == "outcomes":
        return {"ok": True, "outcomes": service.outcomes()}
    if args.command == "verify-audit":
        return {"ok": True, "audit": repository.verify_audit()}
    if args.command == "events":
        return {"ok": True, "events": repository.list_events()}

    actor = _actor_from_args(args)
    if args.command == "add-unit":
        result = service.add_unit(
            actor=actor,
            name=args.name,
            kind=args.kind,
            dependencies=args.depends_on,
        )
    elif args.command == "add-artifact":
        if args.file:
            try:
                content = Path(args.file).read_bytes()
            except OSError as error:
                raise PersistenceError(
                    "artifact file could not be read",
                    details={"path": args.file, "reason": str(error)},
                ) from error
            digest = sha256_digest(content)
            locator = args.locator or Path(args.file).name
        else:
            digest = args.digest
            locator = args.locator
        result = service.register_artifact(
            actor=actor,
            name=args.name,
            title=args.title,
            digest=digest,
            locator=locator,
            workspace_change=args.workspace_change,
        )
    elif args.command == "answer-question":
        result = service.answer_question(
            actor=actor,
            mode=args.mode,
            prompt=args.prompt,
            answer=args.answer,
        )
    elif args.command == "record-sensor":
        result = service.record_sensor(
            actor=actor,
            sensor=args.sensor,
            status=args.status,
            summary=args.summary,
        )
    elif args.command == "record-review":
        result = service.record_review(
            actor=actor,
            verdict=args.verdict,
            summary=args.summary,
        )
    elif args.command == "request-approval":
        result = service.request_approval(
            actor=actor,
            rationale=args.rationale,
            evidence_ids=args.evidence,
        )
    elif args.command == "complete-unit-stage":
        result = service.complete_unit_stage(actor=actor)
    elif args.command == "approve-stage":
        result = service.approve_stage(
            actor=actor,
            gate_id=args.gate_id,
            accept_as_is=args.accept_as_is,
        )
    elif args.command == "reject-stage":
        result = service.reject_stage(
            actor=actor,
            gate_id=args.gate_id,
            reason=args.reason,
        )
    elif args.command == "complete-autonomous":
        result = service.complete_autonomous_stage(actor=actor)
    elif args.command == "set-autonomy":
        result = service.set_autonomy(actor=actor, mode=args.mode)
    elif args.command == "fail-bolt":
        result = service.fail_bolt(actor=actor, summary=args.summary)
    elif args.command == "resolve-bolt-failure":
        result = service.resolve_bolt_failure(actor=actor, action=args.action)
    elif args.command == "set-depth":
        result = service.set_depth(actor=actor, depth=args.depth)
    elif args.command == "set-test-strategy":
        result = service.set_test_strategy(
            actor=actor,
            test_strategy=args.test_strategy,
        )
    elif args.command == "recompose":
        result = service.recompose(
            actor=actor,
            add=args.add,
            skip=args.skip,
            reason=args.reason,
        )
    elif args.command == "skip-stage":
        result = service.skip_current_stage(actor=actor, reason=args.reason)
    elif args.command == "jump-stage":
        result = service.jump_to_stage(
            actor=actor,
            target_stage=args.target,
            reason=args.reason,
        )
    elif args.command == "redo-stage":
        result = service.redo_current_stage(actor=actor, reason=args.reason)
    elif args.command == "park":
        result = service.park(actor=actor, reason=args.reason)
    elif args.command == "resume":
        result = service.resume(actor=actor)
    elif args.command == "propose-learning":
        result = service.propose_learning(
            actor=actor,
            section=args.section,
            summary=args.summary,
        )
    elif args.command == "decide-learning":
        result = service.decide_learning(
            actor=actor,
            learning_id=args.learning_id,
            decision=args.decision,
            target_scope=args.target_scope,
        )
    elif args.command == "loop-to-ideation":
        result = service.loop_to_ideation(actor=actor, reason=args.reason)
    elif args.command == "guard-operation":
        result = service.guard_operation(actor=actor, operation=args.operation)
    else:
        raise ValidationError("unsupported command")
    return {"ok": True, **result}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = execute(args)
    except AIDLCEngineError as error:
        _emit({"ok": False, "error": error.to_dict()}, pretty=args.pretty, stream=sys.stderr)
        return error.exit_code
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _emit(
            {
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": "an unexpected internal error occurred",
                    "details": {"type": type(error).__name__},
                },
            },
            pretty=args.pretty,
            stream=sys.stderr,
        )
        return 70
    _emit(result, pretty=args.pretty)
    return 0
