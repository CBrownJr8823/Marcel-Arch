from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marcel.models.database import AuditLog

logger = structlog.get_logger(__name__)


class AuditIntegrityError(RuntimeError):
    """Raised when an append-only audit chain cannot be verified."""


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class AuditSigner:
    def __init__(self, hmac_key: str) -> None:
        if len(hmac_key) < 32:
            raise ValueError("Audit HMAC key must be at least 32 characters")
        self._key = hmac_key.encode("utf-8")

    def sign(self, payload: str) -> str:
        return hmac.new(self._key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, payload: str, signature: str) -> bool:
        return hmac.compare_digest(self.sign(payload), signature)


class AuditLogger:
    def __init__(self, signer: AuditSigner) -> None:
        self._signer = signer

    async def append(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        actor_id: str,
        event_payload: dict[str, Any],
    ) -> AuditLog:
        if not event_type or len(event_type) > 128:
            raise ValueError("event_type must be between 1 and 128 characters")
        if not actor_id or len(actor_id) > 128:
            raise ValueError("actor_id must be between 1 and 128 characters")

        last_row = await session.execute(select(AuditLog).order_by(AuditLog.sequence_number.desc()).limit(1))
        previous = last_row.scalar_one_or_none()
        sequence = 1 if previous is None else previous.sequence_number + 1
        created_at = datetime.now(timezone.utc)
        previous_hash = previous.entry_hash if previous else None
        material = canonical_json(
            {
                "sequence_number": sequence,
                "event_type": event_type,
                "actor_id": actor_id,
                "event_payload": event_payload,
                "previous_hash": previous_hash,
                "created_at": created_at.isoformat(),
            }
        )
        entry_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        signature = self._signer.sign(entry_hash)
        record = AuditLog(
            sequence_number=sequence,
            event_type=event_type,
            actor_id=actor_id,
            event_payload=event_payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            signature=signature,
            created_at=created_at,
        )
        session.add(record)
        await session.flush()
        logger.info("audit_event_appended", sequence=sequence, event_type=event_type, actor_id=actor_id)
        return record

    async def verify_chain(self, session: AsyncSession) -> int:
        result = await session.execute(select(AuditLog).order_by(AuditLog.sequence_number.asc()))
        records = list(result.scalars())
        expected_previous_hash: str | None = None
        expected_sequence = 1
        for record in records:
            if record.sequence_number != expected_sequence:
                raise AuditIntegrityError(f"Unexpected audit sequence number {record.sequence_number}")
            material = canonical_json(
                {
                    "sequence_number": record.sequence_number,
                    "event_type": record.event_type,
                    "actor_id": record.actor_id,
                    "event_payload": record.event_payload,
                    "previous_hash": record.previous_hash,
                    "created_at": record.created_at.isoformat(),
                }
            )
            computed_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if record.previous_hash != expected_previous_hash:
                raise AuditIntegrityError(f"Broken previous hash at sequence {record.sequence_number}")
            if not hmac.compare_digest(computed_hash, record.entry_hash):
                raise AuditIntegrityError(f"Invalid hash at sequence {record.sequence_number}")
            if not self._signer.verify(record.entry_hash, record.signature):
                raise AuditIntegrityError(f"Invalid signature at sequence {record.sequence_number}")
            expected_previous_hash = record.entry_hash
            expected_sequence += 1
        return len(records)

    async def count(self, session: AsyncSession) -> int:
        result = await session.execute(select(func.count(AuditLog.id)))
        return int(result.scalar_one())raise ValueError("event_type must be between 1 and 128 characters")
if not actor_id or len(actor_id) > 128:
raise ValueError("actor_id must be between 1 and 128 characters")
        last_row = await session.execute(select(AuditLog).order_by(AuditLog.sequence_
        previous = last_row.scalar_one_or_none()
        sequence = 1 if previous is None else previous.sequence_number + 1
        created_at = datetime.now(timezone.utc)
        previous_hash = previous.entry_hash if previous else None
        material = canonical_json(
            {
"sequence_number": sequence,
"event_type": event_type,
"actor_id": actor_id,
"event_payload": event_payload,
"previous_hash": previous_hash,
"created_at": created_at.isoformat(),
            }
        )
        entry_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        signature = self._signer.sign(entry_hash)
        record = AuditLog(
            sequence_number=sequence,
            event_type=event_type,
            actor_id=actor_id,
            event_payload=event_payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            signature=signature,
            created_at=created_at,
        )
        session.add(record)
await session.flush()
        logger.info("audit_event_appended", sequence=sequence, event_type=event_type
return record
async def verify_chain(self, session: AsyncSession) -> int:
        result = await session.execute(select(AuditLog).order_by(AuditLog.sequence_nu
        records = list(result.scalars())
        expected_previous_hash: str | None = None
        expected_sequence = 1
for record in records:
if record.sequence_number != expected_sequence:
raise AuditIntegrityError(f"Unexpected audit sequence number {record
            material = canonical_json(
                {
"sequence_number": record.sequence_number,
"event_type": record.event_type,
"actor_id": record.actor_id,
"event_payload": record.event_payload,
"previous_hash": record.previous_hash,
"created_at": record.created_at.isoformat(),
                }
            )
            computed_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
if record.previous_hash != expected_previous_hash:
raise AuditIntegrityError(f"Broken previous hash at sequence {record
if not hmac.compare_digest(computed_hash, record.entry_hash):
raise AuditIntegrityError(f"Invalid hash at sequence {record.sequence
if not self._signer.verify(record.entry_hash, record.signature):
raise AuditIntegrityError(f"Invalid signature at sequence {record.seq
expected_previous_hash = record.entry_hash
expected_sequence += 1
return len(records)
async def count(self, session: AsyncSession) -> int:
result = await session.execute(select(func.count(AuditLog.id)))
return int(result.scalar_one())
