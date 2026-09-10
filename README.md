# Marcel Arch

Marcel Arch is a lightweight governance control plane for agentic execution systems. It sits between CrewAI, AutoGen, LangGraph, or custom agents and execution tools such as payments, procurement, cloud provisioning, and data operations.

It provides:

- Deterministic JSON policy evaluation with no dynamic code execution.
- Per-agent, per-currency financial caps using PostgreSQL as the authoritative ledger and Redis/Lua for atomic distributed reservations.
- JWT-protected API and interceptor boundaries.
- Signed, chained, append-only audit records using HMAC-SHA256.
- Redis Pub/Sub-backed human-in-the-loop approval blocking.

## Architecture

```text
+----------------------+       JWT        +------------------------------------+
| CrewAI / AutoGen /   |----------------->| Marcel Arch API / Interceptor       |
| LangGraph / custom   |                  |------------------------------------|
| agent execution loop |                  | Identity & action permission check  |
+----------+-----------+                  | Deterministic policy engine         |
           |                              | Redis atomic budget reservation     |
           |                              | HMAC audit-chain append             |
           |                              +--+--------------------+------------+
           |                                 |                    |
           |                                 v                    v
           |                         +---------------+    +------------------+
           |                         | PostgreSQL /   |    | Redis             |
           |                         | SQLite ledger  |    | budget + pub/sub  |
           |                         +---------------+    +---------+--------+
           |                                                      |
           |  blocked when HITL is required                       v
           +<------------------------------------------------ Approver REST API
                                                                  |
                                                                  v
                                                        approve / reject event
```

## Security model

The service is deliberately fail-closed for unknown agents, unauthorized actions, malformed policies, missing budgets, and invalid JWTs.

HMAC signatures expose modification of the audit chain, but key custody is essential. Production deployments should store `AUDIT_HMAC_KEY` in a KMS/HSM, periodically export signed audit checkpoints to immutable storage, rotate keys with explicit key identifiers, and verify chains from a separate security domain.

Use TLS termination, Redis TLS (`rediss://`), PostgreSQL TLS, secret management, database migrations, RBAC backed by an enterprise IdP, rate limiting at an ingress, and workload identity before exposing this service outside a trusted network.

## Run locally

### Prerequisites

- Docker and Docker Compose, or Python 3.11+, Redis 7+, and PostgreSQL 16+.

### Compose

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`. OpenAPI is at `http://localhost:8000/docs`.

### Native development

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
export JWT_SECRET='development-secret-at-least-32-characters-long'
export AUDIT_HMAC_KEY='separate-development-audit-key-at-least-32-chars'
export DATABASE_URL='sqlite+aiosqlite:///./marcel_arch.db'
export REDIS_URL='redis://localhost:6379/0'
uvicorn main:app --reload
```

## Environment variables

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `ENVIRONMENT` | No | `development` | `development`, `test`, `staging`, or `production` |
| `DATABASE_URL` | No | SQLite local URL | `sqlite+aiosqlite` or `postgresql+asyncpg` connection URL |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis or Redis TLS URL |
| `JWT_SECRET` | Yes | — | At least 32-character JWT signing secret |
| `AUDIT_HMAC_KEY` | Yes | — | Separate at least 32-character audit signing key |
| `JWT_ISSUER` | No | `marcel-arch` | Required JWT issuer |
| `JWT_AUDIENCE` | No | `marcel-arch-clients` | Required JWT audience |
| `JWT_EXPIRY_SECONDS` | No | `900` | JWT lifetime in seconds |
| `APPROVAL_TIMEOUT_SECONDS` | No | `900` | HITL wait and expiry timeout |
| `CORS_ORIGINS` | No | localhost values | JSON list of allowed origins |

## API workflow

For a local demo, mint a short-lived admin token using the development-only token endpoint:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/v1/tokens \
  -H 'Content-Type: application/json' \
  -d '{"subject":"demo-admin","roles":["admin","operator","finance","approver"]}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

Register an agent:

```bash
curl -X POST http://localhost:8000/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "id":"treasury-agent-01",
    "display_name":"Treasury Payment Agent",
    "tenant_id":"acme-finance",
    "allowed_actions":["payment.submit","vendor.create"],
    "risk_tier":"high"
  }'
```

Assign a budget:

```bash
curl -X PUT http://localhost:8000/v1/agents/treasury-agent-01/budgets \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"limit_amount":"25000.00","currency":"USD"}'
```

Create a policy requiring review for payments of $5,000 or more:

```bash
curl -X POST http://localhost:8000/v1/policies \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"high-value-payment-review",
    "version":1,
    "priority":10,
    "definition":{
      "rules":[{
        "when":{"actions":["payment.submit"],"amount_gte":"5000"},
        "effect":"require_approval",
        "risk_score":85,
        "reason":"Payments at or above USD 5,000 require treasury approval"
      }]
    }
  }'
```

## Wrap a live agent tool

Use the in-process interceptor when the agent process can import Marcel Arch. It blocks until an approver resolves a high-risk action, then commits the budget only after the external tool succeeds.

```python
import asyncio
from decimal import Decimal

from marcel.schemas import ExecutionIntent
from main import app


async def initialize() -> None:
    async with app.router.lifespan_context(app):
        interceptor = app.state.interceptor

        def intent_for_payment(vendor_id: str, amount: Decimal) -> ExecutionIntent:
            return ExecutionIntent(
                agent_id="treasury-agent-01",
                action="payment.submit",
                payload={"vendor_id": vendor_id, "payment_method": "ACH"},
                requested_amount=amount,
                currency="USD",
                idempotency_key="payment-2026-00000001",
                correlation_id="workflow-42",
            )

        @interceptor.wrap(
            intent_builder=lambda vendor_id, amount: intent_for_payment(vendor_id, amount),
            actor_id_builder=lambda vendor_id, amount: "treasury-agent-01",
        )
        async def submit_payment(vendor_id: str, amount: Decimal) -> dict[str, str]:
            # Replace this with the real, idempotent payment-provider call.
            return {"provider_payment_id": "pay_123", "vendor_id": vendor_id, "amount": str(amount)}

        result = await submit_payment("vendor-772", Decimal("7500.00"))
        print(result)


asyncio.run(initialize())
```

When this call reaches the high-value policy, the coroutine waits. Retrieve the `hitl_transaction_id` from an evaluate response or operational event, then resolve it:

```bash
curl -X POST http://localhost:8000/v1/hitl/TRANSACTION_ID/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approved","comment":"Treasury verified invoice and vendor banking details."}'
```

## Operational guarantees and boundaries

- Redis reservation prevents concurrent agents from spending the same currently available budget in the normal path.
- PostgreSQL locking at commit remains authoritative and prevents committed usage from exceeding a budget cap.
- Tool providers must support idempotency. Marcel Arch cannot atomically commit both a third-party payment and its local ledger without a provider-supported idempotency key or a transaction/outbox/saga integration.
- The public `POST /v1/intents/evaluate` endpoint intentionally waits for a HITL outcome. For long approval windows, use async job orchestration or a callback-driven adapter rather than holding an HTTP request open.
- The token endpoint is demo-oriented. Disable it in production and delegate JWT issuance to your IdP.

## Production checklist

- Replace schema creation with Alembic migrations.
- Run at least two application replicas behind a TLS-enabled ingress.
- Use PostgreSQL, not SQLite, in non-local environments.
- Use Redis Sentinel/Cluster or a managed Redis with persistence and TLS.
- Put JWT and HMAC keys in KMS/HSM-backed secret storage and rotate them.
- Add enterprise identity federation and scoped RBAC claims.
- Export audit-chain checkpoints to an immutable external archive.
- Instrument API latency, policy outcomes, approval latency, reservation failures, Redis availability, and audit verification failures.
- Perform load, failure-injection, authorization, and concurrency testing against real execution adapters.
