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
from app.domain.exceptions import ZohoValidationError
from app.services.zoho_users_service import zoho_users_service
from app.services.zoho_service import zoho_service

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

    # Startup verification for Zoho active users directory
    try:
        users = await zoho_users_service.get_active_users()
        logger.info(
            "Zoho active users directory initialized (zoho_users_source: %s, count: %d)",
            zoho_users_service.users_source,
            len(users),
        )
    except Exception as exc:
        logger.warning(
            "Zoho active users directory unreachable at startup (zoho_users_source: %s): %s",
            zoho_users_service.users_source,
            exc,
        )

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

    openapi_tags = [
        {
            "name": "Agent Tools",
            "description": "The 13 Agent Tool Endpoints callable without authentication headers, with a valid frontend Bearer JWT, or with X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
        },
        {"name": "Authentication", "description": "User login, OTP challenge, session token issuance, and validation."},
        {"name": "Referrals", "description": "Candidate referral submission, listing, and lifecycle management."},
        {"name": "Approvals", "description": "Recruiter review, audit notes, and approval actions."},
        {"name": "Jobs", "description": "Zoho Recruit open jobs and candidate skill matching."},
        {"name": "Employees", "description": "Employee profiles, earned referral points, and submission history."},
        {"name": "Interviews", "description": "Teams interview scheduling and calendar invite dispatch."},
        {"name": "Notifications", "description": "Email delivery and candidate notifications via Microsoft Graph."},
        {"name": "Analytics", "description": "Recruitment dashboards, conversion funnels, and trend analytics."},
        {"name": "Chat", "description": "Multi-agent conversational chat via iGentic platform."},
        {"name": "System", "description": "Container liveness, readiness, and OAuth callbacks."},
    ]

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise full-stack Employee Referral Optimization Agent integrating Zoho Recruit, iGentic AI, and Microsoft 365.",
        openapi_tags=openapi_tags,
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
    @app.exception_handler(ZohoValidationError)
    async def zoho_validation_exception_handler(request: Request, exc: ZohoValidationError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.warning("[Request %s] Zoho validation error: %s (field=%s, code=%s)", req_id, exc.detail, exc.field_name, exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "ZohoValidationError",
                "detail": exc.detail,
                "field": exc.field_name,
                "code": exc.code,
                "request_id": req_id,
            },
        )

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
        """Readiness probe: indicates container readiness to accept traffic and reports user directory source."""
        return {
            "status": "ready",
            "auth_mode": settings.auth_mode,
            "app_env": settings.app_env,
            "zoho_users_source": zoho_users_service.users_source,
            "zoho_search_source": zoho_service.search_source,
        }

    @app.get("/zoho/callback", tags=["System"])
    async def zoho_oauth_callback(code: str | None = None, error: str | None = None):
        """Captures OAuth redirect from Zoho, exchanges code for refresh token, and updates backend configuration."""
        from fastapi.responses import HTMLResponse
        if error:
            return JSONResponse(status_code=400, content={"error": error})
        if not code:
            return JSONResponse(status_code=400, content={"error": "Missing authorization code parameter."})

        from scripts.get_zoho_refresh_token import update_env_file
        import httpx

        accounts_base = settings.zoho_accounts_base_url.rstrip("/")
        token_url = f"{accounts_base}/oauth/v2/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.zoho_client_id,
            "client_secret": settings.zoho_client_secret,
            "redirect_uri": "http://localhost:8000/zoho/callback",
            "code": code,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(token_url, data=payload)
            data = resp.json()

        if "error" in data:
            return JSONResponse(status_code=400, content={"error": data.get("error"), "details": data})

        new_refresh_token = data.get("refresh_token")
        if not new_refresh_token:
            return JSONResponse(
                status_code=400,
                content={"error": "No refresh_token returned by Zoho. Did you set access_type=offline and prompt=consent?", "details": data},
            )

        update_env_file("ZOHO_REFRESH_TOKEN", new_refresh_token)
        settings.zoho_refresh_token = new_refresh_token

        from app.infrastructure.zoho_auth import zoho_auth_manager
        zoho_auth_manager.invalidate_token()
        zoho_users_service.invalidate_cache()

        try:
            users = await zoho_users_service.get_active_users(force_refresh=True)
            user_count = len(users)
            user_source = zoho_users_service.users_source
        except Exception as exc:
            user_count = 0
            user_source = f"error: {exc}"

        html = f"""
        <html>
        <head><title>Zoho OAuth Authorization Successful</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; line-height: 1.6;">
            <h2 style="color: #2e7d32;">Zoho Authorization Successful</h2>
            <p>The new refresh token with consolidated scopes (Users, Modules, Settings, Org) has been successfully saved to <code>backend/.env</code>.</p>
            <ul>
                <li><strong>Directory Source:</strong> {user_source}</li>
                <li><strong>Active Zoho Users Loaded:</strong> {user_count}</li>
            </ul>
            <p>You can now return to the IDE / continue verification.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=200)

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
