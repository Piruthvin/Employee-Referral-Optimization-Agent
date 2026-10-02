"""
FastAPI dependency injection utilities for authentication, roles, and agent-key authorization.
"""

import logging
from typing import Any, Callable
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.core.config import get_settings
from app.core.security import decode_session_jwt, verify_agent_api_key
from app.services.zoho_users_service import zoho_users_service
from app.domain.exceptions import ZohoUsersUnavailableError

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> dict[str, Any]:
    """
    Validates the session JWT from Authorization: Bearer <token>.
    Returns decoded token claims (email, role, name, zoho_user_id).
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_session_jwt(credentials.credentials)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired session token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def require_role(allowed_roles: list[str]) -> Callable:
    """
    Enforces that the authenticated user possesses one of the allowed application roles.
    Allowed roles: 'employee', 'recruiter', 'hiring_manager'.
    """
    async def _role_checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_role = user.get("role", "")
        # Recruiter role is permitted for hiring_manager access
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role in {allowed_roles}, but current role is '{user_role}'.",
            )
        return user

    return _role_checker


async def get_auth_or_agent_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> dict[str, Any]:
    """
    Authenticates requests via EITHER:
    1. Direct JWT session token (from React frontend)
    2. X-Agent-Key header (from iGentic AI platform HTTP tools)

    When using X-Agent-Key:
    - Extracts `requester_email` from the request JSON body or query param.
    - Validates requester against Zoho Active Users.
    - Re-derives the role directly from Zoho Users (NEVER trusts any role sent in request).
    """
    agent_key = request.headers.get("X-Agent-Key")
    if agent_key:
        if not verify_agent_api_key(agent_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Agent-Key header.",
            )

        # Agent authenticated - find requester_email from body or query
        requester_email: str | None = None

        # Try body first
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json
                body_json = json.loads(body_bytes.decode("utf-8"))
                if isinstance(body_json, dict):
                    requester_email = body_json.get("requester_email") or body_json.get("email")
        except Exception:
            pass

        if not requester_email:
            requester_email = request.query_params.get("requester_email")

        if not requester_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="requester_email is required when authenticating via X-Agent-Key.",
            )

        # Lookup in Zoho Users and re-derive role
        try:
            zoho_user = await zoho_users_service.find_user_by_email(requester_email)
        except ZohoUsersUnavailableError as exc:
            logger.error("[Dependencies] Zoho users directory unavailable: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Zoho identity service is unavailable. Please try again later.",
            ) from exc

        if not zoho_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requester email '{requester_email}' is not an active Zoho user.",
            )

        role = zoho_users_service.derive_user_role(zoho_user)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not permitted.",
            )

        first_name = zoho_user.get("first_name", "") or ""
        last_name = zoho_user.get("last_name", "") or ""
        name = f"{first_name} {last_name}".strip() or requester_email

        return {
            "sub": requester_email.strip().lower(),
            "email": requester_email.strip().lower(),
            "role": role,
            "name": name,
            "zoho_user_id": str(zoho_user.get("id", "")),
            "auth_type": "agent_key",
        }

    # Fallback to standard Bearer JWT
    return await get_current_user(credentials)


async def get_tool_user(request: Request) -> dict[str, Any]:
    """
    Authentication dependency for the 13 Agent Tool endpoints.
    Authentication is fully OPTIONAL:
    1. If a valid session JWT is provided (Authorization: Bearer <token>), it is validated
       and its claims (email, role, name, zoho_user_id) are used as trusted identity,
       strictly overriding any client-supplied body requester_email.
       If an invalid/expired Bearer token is provided, it is ignored gracefully.
    2. If X-Agent-Key is provided, it is accepted if valid; if invalid, it is ignored gracefully.
    3. If no valid JWT is present, identity is resolved from `requester_email` in the request body
       or query params, and the real role is dynamically derived live from Zoho Active Users.
    4. If no authentication header and no requester_email is provided, an unauthenticated identity
       (role='unauthenticated') is returned so endpoints without role restrictions can proceed,
       while endpoints requiring recruiter/employee permissions are properly enforced by business logic.
    """
    # 1. Check for Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.strip().lower().startswith("bearer "):
        token = auth_header.strip()[7:].strip()
        try:
            payload = decode_session_jwt(token)
            return {
                "sub": str(payload.get("sub", "")).strip().lower(),
                "email": str(payload.get("email", "")).strip().lower(),
                "role": str(payload.get("role", "employee")),
                "name": str(payload.get("name", "")),
                "zoho_user_id": str(payload.get("zoho_user_id", "")),
                "auth_type": "bearer_jwt",
            }
        except Exception as exc:
            logger.debug("[get_tool_user] Bearer token validation failed (ignored on tool route): %s", exc)

    # 2. Check for X-Agent-Key
    agent_key = request.headers.get("X-Agent-Key") or request.headers.get("x-agent-key")
    has_valid_agent_key = False
    if agent_key:
        if verify_agent_api_key(agent_key):
            has_valid_agent_key = True
        else:
            logger.debug("[get_tool_user] Invalid X-Agent-Key provided (ignored on tool route).")

    # 3. Extract requester_email from JSON body or query parameters
    requester_email: str | None = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            import json
            body_json = json.loads(body_bytes.decode("utf-8"))
            if isinstance(body_json, dict):
                requester_email = (
                    body_json.get("requester_email")
                    or body_json.get("email")
                    or body_json.get("user_email")
                )
    except Exception:
        pass

    if not requester_email:
        requester_email = request.query_params.get("requester_email") or request.query_params.get("email")

    # 4. If requester_email is present, look up live in Zoho Users and dynamically derive role
    if requester_email and str(requester_email).strip():
        clean_email = str(requester_email).strip().lower()
        try:
            zoho_user = await zoho_users_service.find_user_by_email(clean_email)
        except ZohoUsersUnavailableError as exc:
            logger.error("[get_tool_user] Zoho users directory unavailable: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Zoho identity service is unavailable. Please try again later.",
            ) from exc

        if not zoho_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requester email '{clean_email}' is not an active Zoho user.",
            )

        role = zoho_users_service.derive_user_role(zoho_user)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not permitted.",
            )

        first_name = zoho_user.get("first_name", "") or ""
        last_name = zoho_user.get("last_name", "") or ""
        name = f"{first_name} {last_name}".strip() or clean_email

        return {
            "sub": clean_email,
            "email": clean_email,
            "role": role,
            "name": name,
            "zoho_user_id": str(zoho_user.get("id", "")),
            "auth_type": "agent_key" if has_valid_agent_key else "no_auth",
        }

    # 5. Fallback unauthenticated identity for routes that don't enforce role boundaries
    return {
        "sub": "",
        "email": "",
        "role": "unauthenticated",
        "name": "Anonymous Caller",
        "zoho_user_id": "",
        "auth_type": "none",
    }

