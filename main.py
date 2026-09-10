from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from marcel.api.router import router
from marcel.config import Settings, get_settings
from marcel.core.engine import DeterministicPolicyEngine, TokenBucketGovernor
from marcel.core.interceptor import AgentInterceptor
from marcel.models.database import create_database_schema, create_engine_and_sessionmaker
from marcel.security.audit import AuditLogger, AuditSigner


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def session_middleware(request: Request, call_next):
    async with request.app.state.session_factory() as session:
        request.state.session = session
        response = await call_next(request)
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine, session_factory = create_engine_and_sessionmaker(settings)
        redis = Redis.from_url(settings.redis_url, decode_responses=False, socket_timeout=settings.redis_socket_timeout_seconds, health_check_interval=settings.redis_health_check_interval_seconds)
        await redis.ping()
        await create_database_schema(engine)
        signer = AuditSigner(settings.audit_hmac_key.get_secret_value())
        audit = AuditLogger(signer)
        governor = TokenBucketGovernor(redis)
        policy_engine = DeterministicPolicyEngine(governor)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.redis = redis
        app.state.audit = audit
        app.state.interceptor = AgentInterceptor(session_factory, redis, policy_engine, governor, audit, settings)
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type"])
    app.middleware("http")(session_middleware)
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        structlog.get_logger(__name__).exception("unhandled_exception", error_type=type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
