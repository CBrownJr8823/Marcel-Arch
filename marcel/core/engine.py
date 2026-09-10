from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marcel.models.database import Agent, Budget, Policy
from marcel.schemas import ExecutionIntent, PolicyDecision

logger = structlog.get_logger(__name__)


class GovernanceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuleResult:
    outcome: Literal["allow", "deny", "require_approval"]
    risk_score: int
    reason: str
    policy_id: str


class TokenBucketGovernor:
    """Atomic Redis/Lua budget reservation with a database source of truth."""

    _RESERVE_SCRIPT = """
    local current = tonumber(redis.call('GET', KEYS[1]) or ARGV[1])
    local amount = tonumber(ARGV[2])
    if current < amount then
      return {-1, current}
    end
    local remaining = current - amount
    redis.call('SET', KEYS[1], tostring(remaining), 'EX', ARGV[3])
    return {1, remaining}
    """

    def __init__(self, redis: Redis, reservation_ttl_seconds: int = 86400) -> None:
        self._redis = redis
        self._reservation_ttl_seconds = reservation_ttl_seconds

    @staticmethod
    def _key(agent_id: str, currency: str) -> str:
        return f"marcel:budget:{agent_id}:{currency}"

    async def remaining(self, session: AsyncSession, agent_id: str, currency: str) -> Decimal | None:
        budget = await self._get_budget(session, agent_id, currency)
        if budget is None or not budget.active:
            return None
        key = self._key(agent_id, currency)
        cached = await self._redis.get(key)
        if cached is None:
            remaining = budget.limit_amount - budget.consumed_amount
            if remaining < Decimal("0"):
                remaining = Decimal("0")
            await self._redis.set(key, str(remaining), ex=self._reservation_ttl_seconds, nx=True)
            cached = await self._redis.get(key)
        return Decimal(cached.decode("utf-8") if isinstance(cached, bytes) else str(cached))

    async def reserve(self, session: AsyncSession, agent_id: str, currency: str, amount: Decimal) -> tuple[bool, Decimal | None]:
        if amount <= 0:
            raise ValueError("Reservation amount must be positive")
        budget = await self._get_budget(session, agent_id, currency)
        if budget is None or not budget.active:
            return False, None
        database_remaining = budget.limit_amount - budget.consumed_amount
        if database_remaining < amount:
            return False, max(database_remaining, Decimal("0"))
        key = self._key(agent_id, currency)
        result = await self._redis.eval(
            self._RESERVE_SCRIPT,
            1,
            key,
            str(max(database_remaining, Decimal("0"))),
            str(amount),
            str(self._reservation_ttl_seconds),
        )
        if not isinstance(result, list) or len(result) != 2:
            raise GovernanceError("Unexpected Redis budget reservation response")
        allowed = int(result[0]) == 1
        remaining = Decimal(str(result[1]))
        return allowed, remaining

    async def commit(self, session: AsyncSession, agent_id: str, currency: str, amount: Decimal) -> Budget:
        if amount <= 0:
            raise ValueError("Commit amount must be positive")
        query = select(Budget).where(Budget.agent_id == agent_id, Budget.currency == currency).with_for_update()
        result = await session.execute(query)
        budget = result.scalar_one_or_none()
        if budget is None or not budget.active:
            raise GovernanceError("No active budget exists for this agent and currency")
        if budget.consumed_amount + amount > budget.limit_amount:
            raise GovernanceError("Budget cap exceeded during commit")
        budget.consumed_amount += amount
        budget.version += 1
        budget.updated_at = datetime.now(timezone.utc)
        session.add(budget)
        return budget

    async def release(self, session: AsyncSession, agent_id: str, currency: str, amount: Decimal) -> None:
        if amount <= 0:
            return
        budget = await self._get_budget(session, agent_id, currency)
        if budget is None:
            return
        key = self._key(agent_id, currency)
        remaining = budget.limit_amount - budget.consumed_amount
        await self._redis.set(key, str(max(remaining, Decimal("0"))), ex=self._reservation_ttl_seconds)

    async def reset(self, agent_id: str, currency: str, remaining: Decimal) -> None:
        if remaining < 0:
            raise ValueError("remaining cannot be negative")
        await self._redis.set(self._key(agent_id, currency), str(remaining), ex=self._reservation_ttl_seconds)

    @staticmethod
    async def _get_budget(session: AsyncSession, agent_id: str, currency: str) -> Budget | None:
        result = await session.execute(select(Budget).where(Budget.agent_id == agent_id, Budget.currency == currency))
        return result.scalar_one_or_none()


class DeterministicPolicyEngine:
    """Evaluates JSON/YAML-derived policy definitions without executing arbitrary code."""

    def __init__(self, governor: TokenBucketGovernor) -> None:
        self._governor = governor

    async def evaluate(self, session: AsyncSession, intent: ExecutionIntent) -> PolicyDecision:
        agent_result = await session.execute(select(Agent).where(Agent.id == intent.agent_id))
        agent = agent_result.scalar_one_or_none()
        if agent is None or not agent.active:
            return PolicyDecision(outcome="deny", risk_score=100, reasons=["Agent is not registered or active"], policy_ids=[])
        if intent.action not in agent.allowed_actions and "*" not in agent.allowed_actions:
            return PolicyDecision(outcome="deny", risk_score=100, reasons=["Action is not allowed for agent"], policy_ids=[])

        policies_result = await session.execute(select(Policy).where(Policy.enabled.is_(True)).order_by(Policy.priority.asc(), Policy.name.asc()))
        policies = list(policies_result.scalars())
        rule_results: list[RuleResult] = []
        for policy in policies:
            rule_results.extend(self._evaluate_policy(policy, agent, intent))

        remaining: Decimal | None = None
        if intent.requested_amount is not None:
            if intent.currency is None:
                return PolicyDecision(outcome="deny", risk_score=100, reasons=["Currency is required for financial intent"], policy_ids=[])
            remaining = await self._governor.remaining(session, intent.agent_id, intent.currency)
            if remaining is None:
                rule_results.append(RuleResult("deny", 100, "No active budget assigned", "system-budget"))
            elif intent.requested_amount > remaining:
                rule_results.append(RuleResult("require_approval", 90, "Requested amount exceeds remaining budget", "system-budget"))

        if any(result.outcome == "deny" for result in rule_results):
            outcome: Literal["allow", "deny", "require_approval"] = "deny"
        elif any(result.outcome == "require_approval" for result in rule_results):
            outcome = "require_approval"
        else:
            outcome = "allow"

        risk_score = min(100, max([self._base_risk(agent.risk_tier), *(result.risk_score for result in rule_results)]))
        reasons = [result.reason for result in rule_results] or ["All deterministic controls passed"]
        policy_ids = sorted(set(result.policy_id for result in rule_results))
        decision = PolicyDecision(
            outcome=outcome,
            risk_score=risk_score,
            reasons=reasons,
            policy_ids=policy_ids,
            remaining_budget=remaining,
        )
        logger.info("policy_evaluated", agent_id=intent.agent_id, action=intent.action, outcome=outcome, risk_score=risk_score)
        return decision

    def _evaluate_policy(self, policy: Policy, agent: Agent, intent: ExecutionIntent) -> list[RuleResult]:
        definition = policy.definition
        if not isinstance(definition, dict):
            return [RuleResult("deny", 100, "Policy definition is malformed", policy.id)]
        rules = definition.get("rules", [])
        if not isinstance(rules, list):
            return [RuleResult("deny", 100, "Policy rules must be a list", policy.id)]
        results: list[RuleResult] = []
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                results.append(RuleResult("deny", 100, f"Malformed rule at index {index}", policy.id))
                continue
            if self._matches(rule.get("when", {}), agent, intent):
                effect = rule.get("effect", "deny")
                if effect not in {"allow", "deny", "require_approval"}:
                    results.append(RuleResult("deny", 100, f"Invalid effect in policy rule {index}", policy.id))
                    continue
                risk_score = rule.get("risk_score", 50)
                if not isinstance(risk_score, int) or not 0 <= risk_score <= 100:
                    results.append(RuleResult("deny", 100, f"Invalid risk_score in policy rule {index}", policy.id))
                    continue
                reason = rule.get("reason", f"Policy {policy.name} rule {index} matched")
                if not isinstance(reason, str) or not reason.strip():
                    reason = f"Policy {policy.name} rule {index} matched"
                results.append(RuleResult(effect, risk_score, reason, policy.id))
        return results

    def _matches(self, conditions: Any, agent: Agent, intent: ExecutionIntent) -> bool:
        if not isinstance(conditions, dict):
            return False
        allowed_keys = {"actions", "agent_ids", "tenant_ids", "risk_tiers", "amount_gte", "amount_gt", "payload_equals", "payload_contains"}
        if set(conditions).difference(allowed_keys):
            return False
        if "actions" in conditions and not self._match_string_list(conditions["actions"], intent.action):
            return False
        if "agent_ids" in conditions and not self._match_string_list(conditions["agent_ids"], agent.id):
            return False
        if "tenant_ids" in conditions and not self._match_string_list(conditions["tenant_ids"], agent.tenant_id):
            return False
        if "risk_tiers" in conditions and not self._match_string_list(conditions["risk_tiers"], agent.risk_tier):
            return False
        amount = intent.requested_amount or Decimal("0")
        if "amount_gte" in conditions and amount < self._decimal_condition(conditions["amount_gte"]):
            return False
        if "amount_gt" in conditions and amount <= self._decimal_condition(conditions["amount_gt"]):
            return False
        if "payload_equals" in conditions and not self._payload_equals(conditions["payload_equals"], intent.payload):
            return False
        if "payload_contains" in conditions and not self._payload_contains(conditions["payload_contains"], intent.payload):
            return False
        return True

    @staticmethod
    def _match_string_list(value: Any, actual: str) -> bool:
        return isinstance(value, list) and all(isinstance(item, str) for item in value) and (actual in value or "*" in value)

    @staticmethod
    def _decimal_condition(value: Any) -> Decimal:
        try:
            decimal = Decimal(str(value))
        except Exception as exc:
            raise GovernanceError("Invalid numeric policy condition") from exc
        if decimal < 0:
            raise GovernanceError("Numeric policy condition cannot be negative")
        return decimal

    @staticmethod
    def _payload_equals(expected: Any, actual: dict[str, Any]) -> bool:
        return isinstance(expected, dict) and all(actual.get(key) == value for key, value in expected.items())

    @staticmethod
    def _payload_contains(expected: Any, actual: dict[str, Any]) -> bool:
        if not isinstance(expected, dict):
            return False
        serialized = json.dumps(actual, sort_keys=True, default=str)
        return all(str(value) in serialized for value in expected.values())

    @staticmethod
    def _base_risk(risk_tier: str) -> int:
        return {"low": 10, "standard": 25, "high": 50, "critical": 75}.get(risk_tier, 100)    @staticmethod
def _key(agent_id: str, currency: str) -> str:
return f"marcel:budget:{agent_id}:{currency}"
async def remaining(self, session: AsyncSession, agent_id: str, currency: str) ->
        budget = await self._get_budget(session, agent_id, currency)
if budget is None or not budget.active:
return None
        key = self._key(agent_id, currency)
        cached = await self._redis.get(key)
if cached is None:
            remaining = budget.limit_amount - budget.consumed_amount
if remaining < Decimal("0"):
                remaining = Decimal("0")
await self._redis.set(key, str(remaining), ex=self._reservation_ttl_secon
            cached = await self._redis.get(key)
return Decimal(cached.decode("utf-8") if isinstance(cached, bytes) else str(c
async def reserve(self, session: AsyncSession, agent_id: str, currency: str, amou
if amount <= 0:
raise ValueError("Reservation amount must be positive")
        budget = await self._get_budget(session, agent_id, currency)
if budget is None or not budget.active:
return False, None
        database_remaining = budget.limit_amount - budget.consumed_amount
if database_remaining < amount:
return False, max(database_remaining, Decimal("0"))
        key = self._key(agent_id, currency)
        result = await self._redis.eval(
self._RESERVE_SCRIPT,
1,
            key,
str(max(database_remaining, Decimal("0"))),
str(amount),
str(self._reservation_ttl_seconds),
        )
if not isinstance(result, list) or len(result) != 2:
raise GovernanceError("Unexpected Redis budget reservation response")
        allowed = int(result[0]) == 1
        remaining = Decimal(str(result[1]))
return allowed, remaining
async def commit(self, session: AsyncSession, agent_id: str, currency: str, amoun
if amount <= 0:
raise ValueError("Commit amount must be positive")
        query = select(Budget).where(Budget.agent_id == agent_id, Budget.currency == 
        result = await session.execute(query)
        budget = result.scalar_one_or_none()
if budget is None or not budget.active:
raise GovernanceError("No active budget exists for this agent and currenc
if budget.consumed_amount + amount > budget.limit_amount:
raise GovernanceError("Budget cap exceeded during commit")
        budget.consumed_amount += amount
        budget.version += 1
        budget.updated_at = datetime.now(timezone.utc)
        session.add(budget)
return budget
async def release(self, session: AsyncSession, agent_id: str, currency: str, amou
if amount <= 0:
return
        budget = await self._get_budget(session, agent_id, currency)
if budget is None:
return
        key = self._key(agent_id, currency)
        remaining = budget.limit_amount - budget.consumed_amount
await self._redis.set(key, str(max(remaining, Decimal("0"))), ex=self._reserv
async def reset(self, agent_id: str, currency: str, remaining: Decimal) -> None:
if remaining < 0:
raise ValueError("remaining cannot be negative")
await self._redis.set(self._key(agent_id, currency), str(remaining), ex=self
    @staticmethod
async def _get_budget(session: AsyncSession, agent_id: str, currency: str) -> Bud
        result = await session.execute(select(Budget).where(Budget.agent_id == agent_
return result.scalar_one_or_none()
class DeterministicPolicyEngine:
"""Evaluates JSON/YAML-derived policy definitions without executing arbitrary cod
def __init__(self, governor: TokenBucketGovernor) -> None:
self._governor = governor
async def evaluate(self, session: AsyncSession, intent: ExecutionIntent) -> Polic
        agent_result = await session.execute(select(Agent).where(Agent.id == intent.a
        agent = agent_result.scalar_one_or_none()
if agent is None or not agent.active:
return PolicyDecision(outcome="deny", risk_score=100, reasons=["Agent is 
if intent.action not in agent.allowed_actions and "*" not in agent.allowed_ac
return PolicyDecision(outcome="deny", risk_score=100, reasons=["Action is
        policies_result = await session.execute(select(Policy).where(Policy.enabled.i
        policies = list(policies_result.scalars())
        rule_results: list[RuleResult] = []
for policy in policies:
            rule_results.extend(self._evaluate_policy(policy, agent, intent))
        remaining: Decimal | None = None
if intent.requested_amount is not None:
if intent.currency is None:
return PolicyDecision(outcome="deny", risk_score=100, reasons=["Curre
            remaining = await self._governor.remaining(session, intent.agent_id, inte
if remaining is None:
                rule_results.append(RuleResult("deny", 100, "No active budget assigne
elif intent.requested_amount > remaining:
                rule_results.append(RuleResult("require_approval", 90, "Requested amo
if any(result.outcome == "deny" for result in rule_results):
            outcome: Literal["allow", "deny", "require_approval"] = "deny"
elif any(result.outcome == "require_approval" for result in rule_results):
            outcome = "require_approval"
else:
            outcome = "allow"
        risk_score = min(100, max([self._base_risk(agent.risk_tier), *(result.risk_sc
        reasons = [result.reason for result in rule_results] or ["All deterministic c
        policy_ids = sorted(set(result.policy_id for result in rule_results))
        decision = PolicyDecision(
            outcome=outcome,
            risk_score=risk_score,
            reasons=reasons,
            policy_ids=policy_ids,
            remaining_budget=remaining,
        )
        logger.info("policy_evaluated", agent_id=intent.agent_id, action=intent.actio
return decision
def _evaluate_policy(self, policy: Policy, agent: Agent, intent: ExecutionIntent)
        definition = policy.definition
if not isinstance(definition, dict):
return [RuleResult("deny", 100, "Policy definition is malformed", policy
        rules = definition.get("rules", [])
if not isinstance(rules, list):
return [RuleResult("deny", 100, "Policy rules must be a list", policy.id)
        results: list[RuleResult] = []
for index, rule in enumerate(rules):
if not isinstance(rule, dict):
                results.append(RuleResult("deny", 100, f"Malformed rule at index {ind
continue
if self._matches(rule.get("when", {}), agent, intent):
                effect = rule.get("effect", "deny")
if effect not in {"allow", "deny", "require_approval"}:
                    results.append(RuleResult("deny", 100, f"Invalid effect in policy
continue
                risk_score = rule.get("risk_score", 50)
if not isinstance(risk_score, int) or not 0 <= risk_score <= 100:
                    results.append(RuleResult("deny", 100, f"Invalid risk_score in po
continue
                reason = rule.get("reason", f"Policy {policy.name} rule {index} match
if not isinstance(reason, str) or not reason.strip():
                    reason = f"Policy {policy.name} rule {index} matched"
                results.append(RuleResult(effect, risk_score, reason, policy.id))
return results
def _matches(self, conditions: Any, agent: Agent, intent: ExecutionIntent) -> boo
if not isinstance(conditions, dict):
return False
        allowed_keys = {"actions", "agent_ids", "tenant_ids", "risk_tiers", "amount_g
if set(conditions).difference(allowed_keys):
return False
if "actions" in conditions and not self._match_string_list(conditions["action
return False
if "agent_ids" in conditions and not self._match_string_list(conditions["agen
return False
if "tenant_ids" in conditions and not self._match_string_list(conditions["ten
return False
if "risk_tiers" in conditions and not self._match_string_list(conditions["ris
return False
amount = intent.requested_amount or Decimal("0")
if "amount_gte" in conditions and amount < self._decimal_condition(conditions
return False
if "amount_gt" in conditions and amount <= self._decimal_condition(conditions
return False
if "payload_equals" in conditions and not self._payload_equals(conditions["pa
return False
if "payload_contains" in conditions and not self._payload_contains(conditions
return False
return True
@staticmethod
def _match_string_list(value: Any, actual: str) -> bool:
return isinstance(value, list) and all(isinstance(item, str) for item in valu
@staticmethod
def _decimal_condition(value: Any) -> Decimal:
try:
decimal = Decimal(str(value))
except Exception as exc:
raise GovernanceError("Invalid numeric policy condition") from exc
if decimal < 0:
raise GovernanceError("Numeric policy condition cannot be negative")
return decimal
@staticmethod
def _payload_equals(expected: Any, actual: dict[str, Any]) -> bool:
return isinstance(expected, dict) and all(actual.get(key) == value for key, v
@staticmethod
def _payload_contains(expected: Any, actual: dict[str, Any]) -> bool:
if not isinstance(expected, dict):
return False
serialized = json.dumps(actual, sort_keys=True, default=str)
return all(str(value) in serialized for value in expected.values())
@staticmethod
def _base_risk(risk_tier: str) -> int:
return {"low": 10, "standard": 25, "high": 50, "critical": 75}.get(risk_tier, 100)
