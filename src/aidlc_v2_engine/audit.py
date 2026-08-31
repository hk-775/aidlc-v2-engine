"""Canonical hash-chained audit event helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from aidlc_v2_engine.errors import IntegrityError, ValidationError
from aidlc_v2_engine.models import (
    HASH_PATTERN,
    ID_PATTERN,
    TIMESTAMP_PATTERN,
    require_exact_keys,
    validate_actor_record,
)

GENESIS_HASH = "0" * 64


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def state_digest(state: dict[str, Any]) -> str:
    """Hash state content without its circular audit-head fields."""

    content = copy.deepcopy(state)
    content.pop("audit", None)
    return digest_json(content)


def event_hash(event_without_hash: dict[str, Any]) -> str:
    return digest_json(event_without_hash)


def build_event(
    *,
    sequence: int,
    event_id: str,
    timestamp: str,
    event_type: str,
    actor: dict[str, Any],
    project_id: str,
    state_revision: int,
    snapshot_digest: str,
    payload: dict[str, Any],
    previous_hash: str,
) -> dict[str, Any]:
    event = {
        "schema_version": 1,
        "sequence": sequence,
        "event_id": event_id,
        "timestamp": timestamp,
        "type": event_type,
        "actor": actor,
        "project_id": project_id,
        "state_revision": state_revision,
        "state_digest": snapshot_digest,
        "payload": payload,
        "previous_hash": previous_hash,
    }
    event["hash"] = event_hash(event)
    return event


def validate_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        raise ValidationError("audit event must be an object")
    require_exact_keys(
        event,
        {
            "schema_version",
            "sequence",
            "event_id",
            "timestamp",
            "type",
            "actor",
            "project_id",
            "state_revision",
            "state_digest",
            "payload",
            "previous_hash",
            "hash",
        },
        "audit event",
    )
    if event["schema_version"] != 1:
        raise ValidationError("unsupported audit event schema version")
    if (
        isinstance(event["sequence"], bool)
        or not isinstance(event["sequence"], int)
        or event["sequence"] < 1
    ):
        raise ValidationError("audit event sequence must be positive")
    if not isinstance(event["event_id"], str) or not ID_PATTERN.fullmatch(
        event["event_id"]
    ):
        raise ValidationError("audit event id is invalid")
    if not isinstance(event["timestamp"], str) or not TIMESTAMP_PATTERN.fullmatch(
        event["timestamp"]
    ):
        raise ValidationError("audit event timestamp is invalid")
    if (
        not isinstance(event["type"], str)
        or not 1 <= len(event["type"]) <= 100
        or event["type"] != event["type"].strip()
        or any(ord(character) < 32 for character in event["type"])
    ):
        raise ValidationError("audit event type is invalid")
    validate_actor_record(event["actor"], "audit event actor")
    if not isinstance(event["project_id"], str) or not ID_PATTERN.fullmatch(
        event["project_id"]
    ):
        raise ValidationError("audit event project_id is invalid")
    if (
        isinstance(event["state_revision"], bool)
        or not isinstance(event["state_revision"], int)
        or event["state_revision"] < 0
    ):
        raise ValidationError("audit event state_revision is invalid")
    if not isinstance(event["state_digest"], str) or not HASH_PATTERN.fullmatch(
        event["state_digest"]
    ):
        raise ValidationError("audit event state_digest is invalid")
    if not isinstance(event["payload"], dict):
        raise ValidationError("audit event payload must be an object")
    for field in ("previous_hash", "hash"):
        if not isinstance(event[field], str) or not HASH_PATTERN.fullmatch(event[field]):
            raise ValidationError(f"audit event {field} is invalid")


def verify_event(event: dict[str, Any], expected_previous_hash: str) -> None:
    validate_event(event)
    if event["previous_hash"] != expected_previous_hash:
        raise IntegrityError(
            "audit hash chain does not link to the previous event",
            details={
                "sequence": event["sequence"],
                "expected_previous_hash": expected_previous_hash,
                "actual_previous_hash": event["previous_hash"],
            },
        )
    unsigned = dict(event)
    actual_hash = unsigned.pop("hash")
    expected_hash = event_hash(unsigned)
    if actual_hash != expected_hash:
        raise IntegrityError(
            "audit event hash verification failed",
            details={"sequence": event["sequence"]},
        )
