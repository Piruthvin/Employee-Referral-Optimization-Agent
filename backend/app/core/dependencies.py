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
        zoho_user = await zoho_users_service.find_user_by_email(requester_email)
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
