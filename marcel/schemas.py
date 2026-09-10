from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
class AgentCreate(StrictModel):
id: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    display_name: str = Field(min_length=1, max_length=256)
    tenant_id: str = Field(min_length=1, max_length=128)
    allowed_actions: list[str] = Field(min_length=1, max_length=200)
    risk_tier: Literal["low", "standard", "high", "critical"] = "standard"
    metadata: dict[str, Any] = Field(default_factory=dict)
    @field_validator("allowed_actions")
    @classmethod
def validate_actions(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(action.strip() for action in value if action.strip())
if not normalized:
raise ValueError("allowed_actions must contain at least one non-empty act
if any(len(action) > 256 for action in normalized):
raise ValueError("each allowed action must be 256 characters or fewer")
return normalized
class AgentResponse(StrictModel):
id: str
    display_name: str
    tenant_id: str
    allowed_actions: list[str]
    risk_tier: str
    active: bool
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
class BudgetUpsert(StrictModel):
    limit_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    @field_validator("currency")
    @classmethod
def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
if not normalized.isalpha():
raise ValueError("currency must contain only alphabetic ISO-4217 characte
marcel/schemas.py
return normalized
class BudgetResponse(StrictModel):
    agent_id: str
    currency: str
    limit_amount: Decimal
    consumed_amount: Decimal
    remaining_amount: Decimal
    active: bool
    version: int
    updated_at: datetime
class ExecutionIntent(StrictModel):
    agent_id: str = Field(min_length=3, max_length=128)
    action: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)
    requested_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decim
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9
    correlation_id: str | None = Field(default=None, min_length=1, max_length=128)
    @field_validator("currency")
    @classmethod
def normalize_optional_currency(cls, value: str | None) -> str | None:
if value is None:
return None
        normalized = value.upper()
if not normalized.isalpha():
raise ValueError("currency must contain only alphabetic characters")
return normalized
class PolicyDecision(StrictModel):
    outcome: Literal["allow", "deny", "require_approval"]
    risk_score: int = Field(ge=0, le=100)
    reasons: list[str]
    policy_ids: list[str]
    remaining_budget: Decimal | None = None
    hitl_transaction_id: str | None = None
class PolicyCreate(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    version: int = Field(ge=1)
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=1_000_000)
    definition: dict[str, Any]
class PolicyResponse(StrictModel):
id: str
    name: str
    version: int
    enabled: bool
priority: int
definition: dict[str, Any]
created_at: datetime
updated_at: datetime
class HitlResolution(StrictModel):
decision: Literal["approved", "rejected"]
comment: str | None = Field(default=None, max_length=4000)
class HitlResponse(StrictModel):
id: str
idempotency_key: str
agent_id: str
action: str
requested_amount: Decimal | None
currency: str | None
risk_score: int
reasons: list[str]
status: str
reviewer_id: str | None
reviewer_comment: str | None
expires_at: datetime
resolved_at: datetime | None
created_at: datetime
class TokenRequest(StrictModel):
subject: str = Field(min_length=1, max_length=128)
roles: list[str] = Field(default_factory=list, max_length=20)
class TokenResponse(StrictModel):
access_token: str
token_type: Literal["bearer"] = "bearer"
expires_in: int
class HealthResponse(StrictModel):
status: Literal["ok"]
database: Literal["ok"]
redis: Literal["ok"]
