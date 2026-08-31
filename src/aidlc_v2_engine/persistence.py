"""Durable local JSON persistence with recovery and audit integrity checks."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from aidlc_v2_engine.audit import (
    GENESIS_HASH,
    build_event,
    canonical_bytes,
    digest_json,
    state_digest,
    verify_event,
)
from aidlc_v2_engine.catalog import PHASES, STAGES, STAGE_SLUGS
from aidlc_v2_engine.errors import ConflictError, IntegrityError, NotFoundError, PersistenceError
from aidlc_v2_engine.models import (
    Actor,
    require_exact_keys,
    validate_depth,
    validate_scope,
    validate_state,
    validate_test_strategy,
    validate_text,
)
from aidlc_v2_engine.policy import validate_policy
from aidlc_v2_engine.values import OperationValues, ValueProvider

EVENT_FILENAME_PATTERN = re.compile(r"^(\d{8})-([a-z][a-z0-9_-]{1,63})\.json$")


@dataclass(slots=True)
class MutationResult:
    event_type: str
    payload: dict[str, Any]
    result: dict[str, Any]


Mutation = Callable[
    [dict[str, Any], dict[str, Any], OperationValues],
    MutationResult,
]


class JsonProjectRepository:
    """Stores one project in a directory of JSON files."""

    def __init__(self, root: str | Path, provider: ValueProvider | None = None) -> None:
        self.root = Path(root)
        self.provider = provider or ValueProvider()
        self.state_path = self.root / "state.json"
        self.policy_path = self.root / "policy.json"
        self.audit_dir = self.root / "audit"
        self.lock_path = self.root / ".aidlc-v2.lock"
        self.pending_path = self.root / ".aidlc-v2.pending.json"

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise PersistenceError(
                "symbolic links are not accepted for control-plane storage",
                code="unsafe_storage_path",
                details={"path": str(path)},
            )

    @staticmethod
    def _secure_directory(path: Path) -> None:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = -1
        try:
            descriptor = os.open(path, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise PersistenceError(
                    "project storage path is not a directory",
                    details={"path": str(path)},
                )
            os.fchmod(descriptor, 0o700)
        except OSError as error:
            raise PersistenceError(
                "project storage directory permissions could not be secured",
                details={"path": str(path), "reason": str(error)},
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _prepare_root(self, *, create: bool) -> None:
        self._reject_symlink(self.root)
        if self.root.exists():
            if not self.root.is_dir():
                raise PersistenceError("project storage path is not a directory")
        elif not create:
            raise NotFoundError(
                "project storage is not initialized",
                details={"path": str(self.root)},
            )
        else:
            self.root.mkdir(parents=True, mode=0o700)
        self._secure_directory(self.root)
        self._reject_symlink(self.audit_dir)
        if create:
            self.audit_dir.mkdir(mode=0o700, exist_ok=True)
        elif not self.audit_dir.is_dir():
            raise NotFoundError(
                "project audit directory is missing",
                details={"path": str(self.audit_dir)},
            )
        self._secure_directory(self.audit_dir)

    @contextmanager
    def _locked(self, *, create: bool = False) -> Iterator[None]:
        self._prepare_root(create=create)
        self._reject_symlink(self.lock_path)
        flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        descriptor = -1
        try:
            descriptor = os.open(self.lock_path, flags, 0o600)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise PersistenceError(
                    "project lock path is not a regular file",
                    details={"path": str(self.lock_path)},
                )
            os.fchmod(descriptor, 0o600)
        except OSError as error:
            if descriptor >= 0:
                os.close(descriptor)
            raise PersistenceError(
                "project lock file could not be opened safely",
                details={"path": str(self.lock_path), "reason": str(error)},
            ) from error
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            raise
        with os.fdopen(descriptor, "a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_json(self, path: Path) -> dict[str, Any]:
        self._reject_symlink(path)
        descriptor = -1
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_NONBLOCK"):
                flags |= os.O_NONBLOCK
            descriptor = os.open(path, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise PersistenceError(
                    "project JSON path is not a regular file",
                    details={"path": str(path)},
                )
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = -1
                value = json.load(handle)
        except FileNotFoundError as error:
            raise NotFoundError(
                "required project file is missing",
                details={"path": str(path)},
            ) from error
        except (OSError, json.JSONDecodeError) as error:
            raise PersistenceError(
                "project JSON could not be read",
                details={"path": str(path), "reason": str(error)},
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(value, dict):
            raise PersistenceError(
                "project JSON root must be an object",
                details={"path": str(path)},
            )
        return value

    def _atomic_write_json(self, path: Path, value: dict[str, Any]) -> None:
        temporary_name = f".{path.name}.{os.getpid()}.{os.urandom(6).hex()}.tmp"
        temporary_path = path.parent / temporary_name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(temporary_path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            data = canonical_bytes(value) + b"\n"
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary_path, path)
            self._fsync_directory(path.parent)
        except OSError as error:
            raise PersistenceError(
                "atomic JSON write failed",
                details={"path": str(path), "reason": str(error)},
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path.exists():
                temporary_path.unlink()

    def _event_path(self, event: dict[str, Any]) -> Path:
        return self.audit_dir / (
            f"{event['sequence']:08d}-{event['event_id']}.json"
        )

    def _append_event(self, event: dict[str, Any]) -> None:
        event_path = self._event_path(event)
        if event_path.exists():
            existing = self._read_json(event_path)
            if existing != event:
                raise IntegrityError(
                    "an audit sequence already exists with different content",
                    details={"sequence": event["sequence"]},
                )
            return
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = -1
        try:
            descriptor = os.open(event_path, flags, 0o400)
            os.fchmod(descriptor, stat.S_IRUSR)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(canonical_bytes(event) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._fsync_directory(self.audit_dir)
        except FileExistsError:
            existing = self._read_json(event_path)
            if existing != event:
                raise IntegrityError(
                    "an audit event append conflicted with existing content",
                    details={"sequence": event["sequence"]},
                )
        except OSError as error:
            raise PersistenceError(
                "audit event append failed",
                details={"path": str(event_path), "reason": str(error)},
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _finish_pending(self) -> None:
        if not self.pending_path.exists():
            return
        pending = self._read_json(self.pending_path)
        if set(pending) != {"event", "state"}:
            raise IntegrityError("pending transaction has an invalid shape")
        event = pending["event"]
        state = pending["state"]
        if not isinstance(event, dict) or not isinstance(state, dict):
            raise IntegrityError("pending transaction content is invalid")
        if self.state_path.exists():
            current_state = self._read_json(self.state_path)
            validate_state(current_state)
            current_count = current_state["audit"]["event_count"]
            if current_count == event.get("sequence"):
                if current_state != state or current_state["audit"]["head_hash"] != event.get(
                    "hash"
                ):
                    raise IntegrityError(
                        "pending transaction conflicts with the current state"
                    )
                self._verify_audit_unlocked(current_state)
                self.pending_path.unlink()
                self._fsync_directory(self.root)
                return
            if current_count + 1 != event.get("sequence"):
                raise IntegrityError(
                    "pending transaction sequence does not follow current state"
                )
            expected_previous = current_state["audit"]["head_hash"]
        else:
            if event.get("sequence") != 1:
                raise IntegrityError("initial pending transaction must be sequence one")
            expected_previous = GENESIS_HASH
        verify_event(event, expected_previous)
        validate_state(state)
        if state["audit"]["head_hash"] != event["hash"]:
            raise IntegrityError("pending state does not reference its audit event")
        if state_digest(state) != event["state_digest"]:
            raise IntegrityError("pending state content does not match its audit event")
        self._append_event(event)
        self._atomic_write_json(self.state_path, state)
        self._verify_audit_unlocked(state)
        self.pending_path.unlink()
        self._fsync_directory(self.root)

    def initialize(
        self,
        *,
        name: str,
        description: str,
        creator: Actor,
        policy: dict[str, Any],
        workspace_kind: str,
        scope: str,
        scope_source: str,
        depth: str,
        test_strategy: str,
        plan: dict[str, str],
    ) -> dict[str, Any]:
        if creator.kind != "human":
            from aidlc_v2_engine.errors import AuthorizationError

            raise AuthorizationError(
                "only a human can initialize an AI-DLC v2 workflow",
                code="human_initialization_required",
            )
        validated_policy = validate_policy(policy)
        project_name = validate_text(name, "name", maximum=120)
        project_description = validate_text(
            description,
            "description",
            minimum=0,
            maximum=4000,
        )
        if workspace_kind not in {"greenfield", "brownfield"}:
            raise PersistenceError("workspace_kind must be greenfield or brownfield")
        validate_scope(scope)
        if scope_source not in {"explicit", "auto", "composed"}:
            raise PersistenceError("scope_source must be explicit, auto, or composed")
        validate_depth(depth)
        validate_test_strategy(test_strategy)
        if not isinstance(plan, dict):
            raise PersistenceError("stage plan must be an object")
        require_exact_keys(plan, STAGE_SLUGS, "stage plan")
        if any(decision not in {"execute", "skip"} for decision in plan.values()):
            raise PersistenceError("stage plan decisions must be execute or skip")
        if any(plan[stage.slug] != "execute" for stage in STAGES if stage.is_initialization):
            raise PersistenceError("initialization stages cannot be skipped")

        with self._locked(create=True):
            self._finish_pending()
            existing_events = self._audit_files()
            if self.state_path.exists() or existing_events:
                raise ConflictError("project storage is already initialized")
            self._atomic_write_json(self.policy_path, validated_policy)
            values = OperationValues(self.provider, 1)
            project_id = values.identifier("project", project_name)
            event_id = values.identifier("event", "workflow_started")
            first_stage = next(
                stage.slug
                for stage in STAGES
                if not stage.is_initialization and plan[stage.slug] == "execute"
            )
            first_phase = next(
                stage.phase for stage in STAGES if stage.slug == first_stage
            )
            stage_records: dict[str, dict[str, Any]] = {}
            for stage in STAGES:
                if stage.is_initialization:
                    status = "completed"
                    started_at = values.timestamp
                    completed_at = values.timestamp
                elif plan[stage.slug] == "skip":
                    status = "skipped"
                    started_at = None
                    completed_at = None
                elif stage.slug == first_stage:
                    status = "active"
                    started_at = values.timestamp
                    completed_at = None
                else:
                    status = "pending"
                    started_at = None
                    completed_at = None
                stage_records[stage.slug] = {
                    "decision": plan[stage.slug],
                    "status": status,
                    "revision_count": 0,
                    "reviewer_iterations": 0,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "current_gate_id": None,
                }
            phase_records: dict[str, dict[str, Any]] = {}
            for phase in PHASES:
                phase_stages = [stage for stage in STAGES if stage.phase == phase]
                if phase == "initialization":
                    status = "verified"
                    verified_at = values.timestamp
                elif phase == first_phase:
                    status = "active"
                    verified_at = None
                elif all(plan[stage.slug] == "skip" for stage in phase_stages):
                    status = "skipped"
                    verified_at = None
                else:
                    status = "pending"
                    verified_at = None
                phase_records[phase] = {
                    "status": status,
                    "verified_at": verified_at,
                }
            state = {
                "schema_version": 2,
                "project": {
                    "id": project_id,
                    "name": project_name,
                    "description": project_description,
                    "workspace_kind": workspace_kind,
                    "created_at": values.timestamp,
                    "created_by": creator.actor_id,
                },
                "policy_digest": digest_json(validated_policy),
                "revision": 0,
                "workflow": {
                    "status": "running",
                    "scope": scope,
                    "scope_source": scope_source,
                    "depth": depth,
                    "test_strategy": test_strategy,
                    "iteration": 1,
                    "current_stage": first_stage,
                    "current_unit_id": None,
                    "last_completed_stage": "state-init",
                    "construction_autonomy": None,
                    "autonomy_prompt_pending": False,
                    "composition_revision": 1,
                    "started_at": values.timestamp,
                    "parked_at": None,
                    "completed_at": None,
                    "failure": None,
                },
                "phases": phase_records,
                "stages": stage_records,
                "artifacts": {},
                "gates": {},
                "questions": {},
                "sensors": {},
                "reviews": {},
                "units": {},
                "learnings": {},
                "audit": {
                    "event_count": 1,
                    "head_hash": GENESIS_HASH,
                },
            }
            event = build_event(
                sequence=1,
                event_id=event_id,
                timestamp=values.timestamp,
                event_type="WORKFLOW_STARTED",
                actor=creator.to_dict(),
                project_id=project_id,
                state_revision=0,
                snapshot_digest=state_digest(state),
                payload={
                    "name": project_name,
                    "policy_digest": state["policy_digest"],
                    "workspace_kind": workspace_kind,
                    "scope": scope,
                    "depth": depth,
                    "test_strategy": test_strategy,
                    "initialization_stages": [
                        stage.slug for stage in STAGES if stage.is_initialization
                    ],
                    "current_stage": first_stage,
                },
                previous_hash=GENESIS_HASH,
            )
            state["audit"]["head_hash"] = event["hash"]
            validate_state(state)
            self._atomic_write_json(
                self.pending_path,
                {"event": event, "state": state},
            )
            self._finish_pending()
            return copy.deepcopy(state)

    def _load_unlocked(self) -> tuple[dict[str, Any], dict[str, Any]]:
        self._finish_pending()
        state = self._read_json(self.state_path)
        policy = self._read_json(self.policy_path)
        validate_state(state)
        validated_policy = validate_policy(policy)
        actual_policy_digest = digest_json(validated_policy)
        if actual_policy_digest != state["policy_digest"]:
            raise IntegrityError(
                "the stored policy does not match the policy bound to project state"
            )
        self._verify_audit_unlocked(state)
        return state, validated_policy

    def load(self) -> dict[str, Any]:
        with self._locked():
            state, _ = self._load_unlocked()
            return copy.deepcopy(state)

    def load_policy(self) -> dict[str, Any]:
        with self._locked():
            _, policy = self._load_unlocked()
            return copy.deepcopy(policy)

    def mutate(self, actor: Actor, mutation: Mutation) -> dict[str, Any]:
        with self._locked():
            state, policy = self._load_unlocked()
            next_state = copy.deepcopy(state)
            sequence = state["audit"]["event_count"] + 1
            values = OperationValues(self.provider, sequence)
            mutation_result = mutation(next_state, policy, values)
            if not isinstance(mutation_result, MutationResult):
                raise PersistenceError("mutation did not return a MutationResult")
            next_state["revision"] = state["revision"] + 1
            event = build_event(
                sequence=sequence,
                event_id=values.identifier("event", mutation_result.event_type),
                timestamp=values.timestamp,
                event_type=mutation_result.event_type,
                actor=actor.to_dict(),
                project_id=state["project"]["id"],
                state_revision=next_state["revision"],
                snapshot_digest=state_digest(next_state),
                payload=mutation_result.payload,
                previous_hash=state["audit"]["head_hash"],
            )
            next_state["audit"] = {
                "event_count": sequence,
                "head_hash": event["hash"],
            }
            validate_state(next_state)
            self._atomic_write_json(
                self.pending_path,
                {"event": event, "state": next_state},
            )
            self._finish_pending()
            return copy.deepcopy(mutation_result.result)

    def _audit_files(self) -> list[Path]:
        files = []
        for path in self.audit_dir.iterdir():
            if path.name.startswith("."):
                continue
            self._reject_symlink(path)
            if not path.is_file() or not EVENT_FILENAME_PATTERN.fullmatch(path.name):
                raise IntegrityError(
                    "unexpected content exists in the audit directory",
                    details={"path": str(path)},
                )
            files.append(path)
        return sorted(files)

    def _verify_audit_unlocked(self, state: dict[str, Any]) -> dict[str, Any]:
        previous_hash = GENESIS_HASH
        final_event: dict[str, Any] | None = None
        files = self._audit_files()
        if len(files) != state["audit"]["event_count"]:
            raise IntegrityError(
                "audit event count does not match project state",
                details={
                    "files": len(files),
                    "state_count": state["audit"]["event_count"],
                },
            )
        for expected_sequence, path in enumerate(files, start=1):
            match = EVENT_FILENAME_PATTERN.fullmatch(path.name)
            if match is None:
                raise IntegrityError(
                    "audit event filename is invalid",
                    details={"path": str(path)},
                )
            event = self._read_json(path)
            if int(match.group(1)) != expected_sequence:
                raise IntegrityError(
                    "audit event filenames are not contiguous",
                    details={"expected_sequence": expected_sequence},
                )
            if event.get("sequence") != expected_sequence:
                raise IntegrityError(
                    "audit event sequence does not match its filename",
                    details={"path": str(path)},
                )
            if event.get("event_id") != match.group(2):
                raise IntegrityError(
                    "audit event id does not match its filename",
                    details={"path": str(path)},
                )
            verify_event(event, previous_hash)
            if event["state_revision"] != expected_sequence - 1:
                raise IntegrityError(
                    "audit event state revision is inconsistent with its sequence",
                    details={"sequence": expected_sequence},
                )
            if event["project_id"] != state["project"]["id"]:
                raise IntegrityError("audit event belongs to a different project")
            previous_hash = event["hash"]
            final_event = event
        if state["revision"] != len(files) - 1:
            raise IntegrityError(
                "project state revision is inconsistent with the audit count"
            )
        if previous_hash != state["audit"]["head_hash"]:
            raise IntegrityError("audit head hash does not match project state")
        if (
            final_event is None
            or final_event["state_revision"] != state["revision"]
            or final_event["state_digest"] != state_digest(state)
        ):
            raise IntegrityError("project state content does not match the final audit event")
        return {
            "valid": True,
            "event_count": len(files),
            "head_hash": previous_hash,
        }

    def verify_audit(self) -> dict[str, Any]:
        with self._locked():
            self._finish_pending()
            state = self._read_json(self.state_path)
            validate_state(state)
            return self._verify_audit_unlocked(state)

    def list_events(self) -> list[dict[str, Any]]:
        with self._locked():
            state, _ = self._load_unlocked()
            del state
            return [self._read_json(path) for path in self._audit_files()]
