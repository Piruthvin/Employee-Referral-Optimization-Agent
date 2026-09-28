"""
Main FastAPI application entry point for Employee Referral Optimization Agent.
Configures CORS, Request-ID tracing, security headers, global error handlers,
API v1 routers, and container health probes.
"""

import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.api.v1.auth import router as auth_router
from app.api.v1.referral import router as referral_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.employees import router as employees_router
from app.api.v1.interview import router as interview_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.chat import router as chat_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("referral_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    settings = get_settings()
    logger.info("Starting %s v%s in %s environment...", settings.app_name, settings.app_version, settings.app_env)
    # Fail-fast configuration validation
    try:
        settings.validate_environment_policies()
    except Exception as exc:
        logger.critical("Startup configuration error: %s", exc)
        raise exc
    yield
    logger.info("Shutting down %s...", settings.app_name)


class RequestIdAndSecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id

        response = await call_next(request)

        # Attach tracking and security headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise full-stack Employee Referral Optimization Agent integrating Zoho Recruit, iGentic AI, and Microsoft 365.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware setup
    app.add_middleware(RequestIdAndSecurityHeadersMiddleware)

    cors_origins = settings.cors_origins or ["http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    # Global Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "detail": exc.errors(),
                "request_id": req_id,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # Check if HTTP exception
        status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
        detail = getattr(exc, "detail", str(exc) if settings.debug else "An unexpected internal server error occurred.")

        logger.error("[Request %s] Unhandled exception: %s", req_id, exc, exc_info=True)

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.__class__.__name__,
                "detail": detail,
                "request_id": req_id,
            },
        )

    # Health & Readiness Probes (Root and API v1)
    @app.get("/health", tags=["System"])
    @app.get("/api/v1/health", tags=["System"])
    async def health_check():
        """Liveness probe: returns immediate 200 without making external requests."""
        return {"status": "healthy", "service": settings.app_name, "version": settings.app_version}

    @app.get("/ready", tags=["System"])
    @app.get("/api/v1/ready", tags=["System"])
    async def readiness_check():
        """Readiness probe: indicates container readiness to accept traffic."""
        return {"status": "ready", "auth_mode": settings.auth_mode, "app_env": settings.app_env}

    # Register API v1 Routers
    api_v1_prefix = "/api/v1"
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(referral_router, prefix=api_v1_prefix)
    app.include_router(approvals_router, prefix=api_v1_prefix)
    app.include_router(jobs_router, prefix=api_v1_prefix)
    app.include_router(employees_router, prefix=api_v1_prefix)
    app.include_router(interview_router, prefix=api_v1_prefix)
    app.include_router(notifications_router, prefix=api_v1_prefix)
    app.include_router(analytics_router, prefix=api_v1_prefix)
    app.include_router(chat_router, prefix=api_v1_prefix)

    return app


app = create_app()
