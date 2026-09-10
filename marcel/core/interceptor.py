from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from marcel.config import Settings
from marcel.core.engine import DeterministicPolicyEngine, GovernanceError, TokenBucketGovernor
from marcel.models.database import HitlStatus, HitlTransaction
from marcel.schemas import ExecutionIntent, PolicyDecision
from marcel.security.audit import AuditLogger

logger = structlog.get_logger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


class ExecutionDeniedError(PermissionError):
    pass


class ApprovalRejectedError(PermissionError):
    pass


class ApprovalTimeoutError(TimeoutError):
    pass


class AgentInterceptor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis,
        engine: DeterministicPolicyEngine,
        governor: TokenBucketGovernor,
        audit: AuditLogger,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._engine = engine
        self._governor = governor
        self._audit = audit
        self._settings = settings

    async def evaluate_or_wait(self, intent: ExecutionIntent, actor_id: str) -> PolicyDecision:
        async with self._session_factory() as session:
            async with session.begin():
                decision = await self._engine.evaluate(session, intent)
                await self._audit.append(
                    session,
                    event_type="execution_intent_evaluated",
                    actor_id=actor_id,
                    event_payload={"intent": intent.model_dump(mode="json"), "decision": decision.model_dump(mode="json")},
                )
                if decision.outcome == "deny":
                    return decision
                if decision.outcome == "allow":
                    if intent.requested_amount is not None and intent.currency is not None:
                        reserved, remaining = await self._governor.reserve(session, intent.agent_id, intent.currency, intent.requested_amount)
                        if not reserved:
                            return decision.model_copy(update={"outcome": "require_approval", "risk_score": max(decision.risk_score, 90), "reasons": [*decision.reasons, "Budget reservation failed"], "remaining_budget": remaining})
                    return decision
                transaction = await self._create_or_get_hitl(session, intent, decision)
                decision = decision.model_copy(update={"hitl_transaction_id": transaction.id})

        if decision.outcome == "require_approval" and decision.hitl_transaction_id:
            await self._publish_hitl_request(decision.hitl_transaction_id)
            return await self._await_resolution(intent, decision.hitl_transaction_id, actor_id)
        return decision

    async def execute(self, intent: ExecutionIntent, actor_id: str, operation: Callable[[], Awaitable[R]]) -> R:
        decision = await self.evaluate_or_wait(intent, actor_id)
        if decision.outcome == "deny":
            raise ExecutionDeniedError("; ".join(decision.reasons))
        if decision.outcome != "allow":
            raise ApprovalRejectedError("Execution was not approved")
        try:
            result = await operation()
        except Exception as exc:
            await self._record_execution_failure(intent, actor_id, exc)
            raise
        await self._commit_execution(intent, actor_id)
        return result

    def wrap(self, intent_builder: Callable[P, ExecutionIntent], actor_id_builder: Callable[P, str]) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        def decorator(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
            if not inspect.iscoroutinefunction(function):
                raise TypeError("Intercepted tool functions must be async")

            @wraps(function)
            async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                intent = intent_builder(*args, **kwargs)
                actor_id = actor_id_builder(*args, **kwargs)
                return await self.execute(intent, actor_id, lambda: function(*args, **kwargs))

            return cast(Callable[P, Awaitable[R]], wrapped)

        return decorator

    async def _create_or_get_hitl(self, session: AsyncSession, intent: ExecutionIntent, decision: PolicyDecision) -> HitlTransaction:
        existing_result = await session.execute(select(HitlTransaction).where(HitlTransaction.idempotency_key == intent.idempotency_key))
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing
        now = datetime.now(timezone.utc)
        transaction = HitlTransaction(
            idempotency_key=intent.idempotency_key,
            agent_id=intent.agent_id,
            action=intent.action,
            intent_payload=intent.payload,
            requested_amount=intent.requested_amount,
            currency=intent.currency,
            risk_score=decision.risk_score,
            reasons=decision.reasons,
            status=HitlStatus.PENDING,
            expires_at=now + timedelta(seconds=self._settings.approval_timeout_seconds),
            created_at=now,
            updated_at=now,
        )
        session.add(transaction)
        try:
            await session.flush()
        except IntegrityError:
            existing_result = await session.execute(select(HitlTransaction).where(HitlTransaction.idempotency_key == intent.idempotency_key))
            existing = existing_result.scalar_one_or_none()
            if existing is None:
                raise
            return existing
        await self._audit.append(session, event_type="hitl_requested", actor_id=intent.agent_id, event_payload={"hitl_transaction_id": transaction.id, "intent": intent.model_dump(mode="json"), "risk_score": decision.risk_score, "reasons": decision.reasons})
        return transaction

    async def _publish_hitl_request(self, transaction_id: str) -> None:
        payload = {"event": "hitl.requested", "transaction_id": transaction_id, "occurred_at": datetime.now(timezone.utc).isoformat()}
        await self._redis.publish("marcel:hitl:requests", str(payload))

    async def _await_resolution(self, intent: ExecutionIntent, transaction_id: str, actor_id: str) -> PolicyDecision:
        channel = f"marcel:hitl:resolution:{transaction_id}"
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            deadline = asyncio.get_running_loop().time() + self._settings.approval_timeout_seconds
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    await self._expire_transaction(transaction_id, actor_id)
                    raise ApprovalTimeoutError("HITL approval timed out")
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=min(remaining, 1.0))
                if message is None:
                    status_value = await self._get_transaction_status(transaction_id)
                    if status_value in {HitlStatus.APPROVED, HitlStatus.REJECTED, HitlStatus.EXPIRED}:
                        return await self._resolution_decision(intent, transaction_id, status_value)
                    continue
                status_value = await self._get_transaction_status(transaction_id)
                return await self._resolution_decision(intent, transaction_id, status_value)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def _resolution_decision(self, intent: ExecutionIntent, transaction_id: str, status_value: HitlStatus) -> PolicyDecision:
        if status_value == HitlStatus.APPROVED:
            if intent.requested_amount is not None and intent.currency is not None:
                async with self._session_factory() as session:
                    async with session.begin():
                        reserved, remaining = await self._governor.reserve(session, intent.agent_id, intent.currency, intent.requested_amount)
                        if not reserved:
                            return PolicyDecision(outcome="deny", risk_score=100, reasons=["Budget reservation failed after approval"], policy_ids=["system-budget"], remaining_budget=remaining, hitl_transaction_id=transaction_id)
            return PolicyDecision(outcome="allow", risk_score=0, reasons=["HITL approval granted"], policy_ids=[], hitl_transaction_id=transaction_id)
        if status_value == HitlStatus.EXPIRED:
            raise ApprovalTimeoutError("HITL approval expired")
        raise ApprovalRejectedError("HITL approval rejected")

    async def _get_transaction_status(self, transaction_id: str) -> HitlStatus:
        async with self._session_factory() as session:
            result = await session.execute(select(HitlTransaction.status).where(HitlTransaction.id == transaction_id))
            status_value = result.scalar_one_or_none()
            if status_value is None:
                raise GovernanceError("HITL transaction no longer exists")
            return status_value

    async def _expire_transaction(self, transaction_id: str, actor_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(select(HitlTransaction).where(HitlTransaction.id == transaction_id).with_for_update())
                transaction = result.scalar_one_or_none()
                if transaction and transaction.status == HitlStatus.PENDING:
                    transaction.status = HitlStatus.EXPIRED
                    transaction.resolved_at = datetime.now(timezone.utc)
                    transaction.updated_at = transaction.resolved_at
                    await self._audit.append(session, event_type="hitl_expired", actor_id=actor_id, event_payload={"hitl_transaction_id": transaction_id})

    async def _commit_execution(self, intent: ExecutionIntent, actor_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                if intent.requested_amount is not None and intent.currency is not None:
                    budget = await self._governor.commit(session, intent.agent_id, intent.currency, intent.requested_amount)
                    await self._governor.reset(intent.agent_id, intent.currency, budget.limit_amount - budget.consumed_amount)
                await self._audit.append(session, event_type="execution_completed", actor_id=actor_id, event_payload={"intent": intent.model_dump(mode="json")})

    async def _record_execution_failure(self, intent: ExecutionIntent, actor_id: str, exc: Exception) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                if intent.requested_amount is not None and intent.currency is not None:
                    await self._governor.release(session, intent.agent_id, intent.currency, intent.requested_amount)
                await self._audit.append(session, event_type="execution_failed", actor_id=actor_id, event_payload={"intent": intent.model_dump(mode="json"), "error_type": type(exc).__name__, "error": str(exc)[:1000]})
