from __future__ import annotations
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, AsyncSession, async_sessi
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON
from marcel.config import Settings
class Base(AsyncAttrs, DeclarativeBase):
pass
JsonType = JSON().with_variant(JSONB, "postgresql")
class HitlStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("agent_id", "currency", name="uq_budget_agent_
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    consumed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, 
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
class Agent(Base):
    __tablename__ = "agents"
id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    allowed_actions: Mapped[list[str]] = mapped_column(JsonType, nullable=False, defa
    risk_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="stand
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JsonType, nulla
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_policy_name_versio
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    definition: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
class AuditLog(Base):
    __tablename__ = "audit_logs"
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
class HitlTransaction(Base):
    __tablename__ = "hitl_transactions"
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    intent_payload: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    requested_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list
    status: Mapped[HitlStatus] = mapped_column(Enum(HitlStatus), nullable=False, defa
    reviewer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nul
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=Fa
def create_engine_and_sessionmaker(settings: Settings) -> tuple[AsyncEngine, async_se
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
"echo": False,
"pool_pre_ping": True,
"future": True,
    }
if settings.database_url.startswith("sqlite+"):
        connect_args["check_same_thread"] = False
else:
        engine_kwargs["pool_size"] = settings.database_pool_size
        engine_kwargs["max_overflow"] = settings.database_max_overflow
    engine = create_async_engine(settings.database_url, connect_args=connect_args, **
return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSes
async def create_database_schema(engine: AsyncEngine) -> None:
async with engine.begin() as connection:
await connection.run_sync(Base.metadata.create_all)
