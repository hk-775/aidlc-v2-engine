"""Injectable timestamp and identifier providers."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aidlc_v2_engine.errors import ValidationError


def format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValidationError("timestamps must include a timezone")
    utc_value = value.astimezone(timezone.utc)
    rendered = utc_value.isoformat(timespec="microseconds")
    return rendered.replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "fixed time must be an ISO-8601 timestamp",
            details={"value": value},
        ) from error
    if parsed.tzinfo is None:
        raise ValidationError("fixed time must include a timezone")
    return parsed.astimezone(timezone.utc)


class ValueProvider:
    """Provides values that can be replaced for deterministic evaluation."""

    def timestamp(self, event_sequence: int) -> str:
        del event_sequence
        return format_timestamp(datetime.now(timezone.utc))

    def identifier(self, prefix: str, event_sequence: int, discriminator: str) -> str:
        del event_sequence, discriminator
        return f"{prefix}_{secrets.token_hex(8)}"


@dataclass(frozen=True, slots=True)
class DeterministicValueProvider(ValueProvider):
    seed: str
    base_time: datetime

    def __post_init__(self) -> None:
        if not self.seed:
            raise ValidationError("deterministic seed cannot be empty")
        if self.base_time.tzinfo is None:
            raise ValidationError("deterministic base time must include a timezone")

    def timestamp(self, event_sequence: int) -> str:
        value = self.base_time + timedelta(microseconds=event_sequence - 1)
        return format_timestamp(value)

    def identifier(self, prefix: str, event_sequence: int, discriminator: str) -> str:
        material = f"{self.seed}\0{prefix}\0{event_sequence}\0{discriminator}".encode()
        suffix = hashlib.sha256(material).hexdigest()[:16]
        return f"{prefix}_{suffix}"


@dataclass(frozen=True, slots=True)
class OperationValues:
    provider: ValueProvider
    event_sequence: int

    @property
    def timestamp(self) -> str:
        return self.provider.timestamp(self.event_sequence)

    def identifier(self, prefix: str, discriminator: str) -> str:
        return self.provider.identifier(prefix, self.event_sequence, discriminator)
