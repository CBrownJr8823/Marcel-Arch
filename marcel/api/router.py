from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from marcel.core.interceptor import AgentInterceptor, ApprovalRejectedError, ApprovalTimeoutError
from marcel.models.database import Agent, Budget, HitlStatus, HitlTransaction, Policy
from marcel.schemas import AgentCreate, AgentResponse, BudgetResponse, BudgetUpsert, ExecutionIntent, HealthResponse, HitlResolution, HitlResponse, PolicyCreate, PolicyDecision, PolicyResponse, TokenRequest, TokenResponse
from marcel.security.auth import create_access_token, require_principal, require_role

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["marcel-arch"])


def session_from_request(request: Request) -> AsyncSession:
    return request.state.session


def interceptor_from_request(request: Request) -> AgentInterceptor:
    return request.app.state.interceptor


def budget_response(budget: Budget) -> BudgetResponse:
    return BudgetResponse(agent_id=budget.agent_id, currency=budget.currency, limit_amount=budget.limit_amount, consumed_amount=budget.consumed_amount, remaining_amount=max(Decimal("0"), budget.limit_amount - budget.consumed_amount), active=budget.active, version=budget.version, updated_at=budget.updated_at)


def hitl_response(transaction: HitlTransaction) -> HitlResponse:
    return HitlResponse(id=transaction.id, idempotency_key=transaction.idempotency_key, agent_id=transaction.agent_id, action=transaction.action, requested_amount=transaction.requested_amount, currency=transaction.currency, risk_score=transaction.risk_score, reasons=transaction.reasons, status=transaction.status.value, reviewer_id=transaction.reviewer_id, reviewer_comment=transaction.reviewer_comment, expires_at=transaction.expires_at, resolved_at=transaction.resolved_at, created_at=transaction.created_at)


@router.post("/tokens", response_model=TokenResponse, include_in_schema=False)
async def issue_token(payload: TokenRequest, request: Request) -> TokenResponse:
    settings = request.app.state.settings
    token = create_access_token(settings, payload.subject, payload.roles)
    return TokenResponse(access_token=token, expires_in=settings.jwt_expiry_seconds)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    await request.app.state.redis.ping()
    async with request.app.state.session_factory() as session:
        await session.execute(select(1))
    return HealthResponse(status="ok", database="ok", redis="ok")


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(payload: AgentCreate, request: Request, principal: dict[str, Any] = Depends(require_role("admin", "operator"))) -> AgentResponse:
    now = datetime.now(timezone.utc)
    agent = Agent(id=payload.id, display_name=payload.display_name, tenant_id=payload.tenant_id, allowed_actions=payload.allowed_actions, risk_tier=payload.risk_tier, metadata_json=payload.metadata, active=True, created_at=now, updated_at=now)
    async with request.app.state.session_factory() as session:
        async with session.begin():
            session.add(agent)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Agent ID already exists") from exc
            await request.app.state.audit.append(session, event_type="agent_registered", actor_id=str(principal["sub"]), event_payload={"agent_id": agent.id})
    return AgentResponse(id=agent.id, display_name=agent.display_name, tenant_id=agent.tenant_id, allowed_actions=agent.allowed_actions, risk_tier=agent.risk_tier, active=agent.active, metadata=agent.metadata_json, created_at=agent.created_at, updated_at=agent.updated_at)


@router.put("/agents/{agent_id}/budgets", response_model=BudgetResponse)
async def upsert_budget(agent_id: str, payload: BudgetUpsert, request: Request, principal: dict[str, Any] = Depends(require_role("admin", "finance"))) -> BudgetResponse:
    now = datetime.now(timezone.utc)
    async with request.app.state.session_factory() as session:
        async with session.begin():
            agent = (await session.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
            if agent is None:
                raise HTTPException(status_code=404, detail="Agent not found")
            budget = (await session.execute(select(Budget).where(Budget.agent_id == agent_id, Budget.currency == payload.currency).with_for_update())).scalar_one_or_none()
            if budget is None:
                budget = Budget(agent_id=agent_id, currency=payload.currency, limit_amount=payload.limit_amount, consumed_amount=Decimal("0"), version=1, active=True, created_at=now, updated_at=now)
                session.add(budget)
            else:
                if payload.limit_amount < budget.consumed_amount:
                    raise HTTPException(status_code=422, detail="Budget limit cannot be lower than already consumed amount")
                budget.limit_amount = payload.limit_amount
                budget.version += 1
                budget.updated_at = now
            await session.flush()
            await request.app.state.interceptor._governor.reset(agent_id, payload.currency, budget.limit_amount - budget.consumed_amount)
            await request.app.state.audit.append(session, event_type="budget_updated", actor_id=str(principal["sub"]), event_payload={"agent_id": agent_id, "currency": payload.currency, "limit_amount": str(payload.limit_amount)})
    return budget_response(budget)


@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(payload: PolicyCreate, request: Request, principal: dict[str, Any] = Depends(require_role("admin", "operator"))) -> PolicyResponse:
    now = datetime.now(timezone.utc)
    policy = Policy(name=payload.name, version=payload.version, enabled=payload.enabled, priority=payload.priority, definition=payload.definition, created_at=now, updated_at=now)
    async with request.app.state.session_factory() as session:
        async with session.begin():
            session.add(policy)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Policy name and version already exist") from exc
            await request.app.state.audit.append(session, event_type="policy_created", actor_id=str(principal["sub"]), event_payload={"policy_id": policy.id, "name": policy.name, "version": policy.version})
    return PolicyResponse(id=policy.id, name=policy.name, version=policy.version, enabled=policy.enabled, priority=policy.priority, definition=policy.definition, created_at=policy.created_at, updated_at=policy.updated_at)


@router.post("/intents/evaluate", response_model=PolicyDecision)
async def evaluate_intent(payload: ExecutionIntent, request: Request, principal: dict[str, Any] = Depends(require_principal)) -> PolicyDecision:
    interceptor = interceptor_from_request(request)
    try:
        return await interceptor.evaluate_or_wait(payload, str(principal["sub"]))
    except ApprovalRejectedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ApprovalTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc


@router.get("/hitl/{transaction_id}", response_model=HitlResponse)
async def get_hitl(transaction_id: str, request: Request, _: dict[str, Any] = Depends(require_role("admin", "operator", "approver"))) -> HitlResponse:
    async with request.app.state.session_factory() as session:
        transaction = (await session.execute(select(HitlTransaction).where(HitlTransaction.id == transaction_id))).scalar_one_or_none()
        if transaction is None:
            raise HTTPException(status_code=404, detail="HITL transaction not found")
        return hitl_response(transaction)


@router.post("/hitl/{transaction_id}/resolve", response_model=HitlResponse)
async def resolve_hitl(transaction_id: str, payload: HitlResolution, request: Request, principal: dict[str, Any] = Depends(require_role("admin", "approver"))) -> HitlResponse:
    now = datetime.now(timezone.utc)
    async with request.app.state.session_factory() as session:
        async with session.begin():
            transaction = (await session.execute(select(HitlTransaction).where(HitlTransaction.id == transaction_id).with_for_update())).scalar_one_or_none()
            if transaction is None:
                raise HTTPException(status_code=404, detail="HITL transaction not found")
            if transaction.status != HitlStatus.PENDING:
                raise HTTPException(status_code=409, detail=f"HITL transaction is already {transaction.status.value}")
            if transaction.expires_at <= now:
                transaction.status = HitlStatus.EXPIRED
                transaction.resolved_at = now
                transaction.updated_at = now
                raise HTTPException(status_code=409, detail="HITL transaction has expired")
            transaction.status = HitlStatus.APPROVED if payload.decision == "approved" else HitlStatus.REJECTED
            transaction.reviewer_id = str(principal["sub"])
            transaction.reviewer_comment = payload.comment
            transaction.resolved_at = now
            transaction.updated_at = now
            await request.app.state.audit.append(session, event_type="hitl_resolved", actor_id=str(principal["sub"]), event_payload={"hitl_transaction_id": transaction.id, "decision": payload.decision, "comment": payload.comment})
            await session.flush()
            response = hitl_response(transaction)
    await request.app.state.redis.publish(f"marcel:hitl:resolution:{transaction_id}", payload.decision)
    return response
