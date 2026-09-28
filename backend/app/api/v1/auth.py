"""
Authentication endpoints:
- Stateless email OTP challenge / verification
- Role mapping purely from Zoho Recruit Active Users
- Rate limiting and enumeration prevention
"""

import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status
from app.core.config import get_settings
from app.core.security import (
    generate_otp,
    create_challenge_token,
    verify_challenge_token,
    create_session_jwt,
    login_ip_limiter,
    login_email_limiter,
)
from app.core.dependencies import get_current_user
from app.services.zoho_users_service import zoho_users_service
from app.services.email_service import email_service
from app.domain.models import (
    LoginRequest,
    LoginResponse,
    VerifyRequest,
    VerifyResponse,
    UserMeResponse,
    ValidateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login/request",
    response_model=LoginResponse,
    summary="Request login verification code",
    description="Initiates stateless email OTP login. Validates user against Zoho Active Users. Sends a 6-digit OTP via Microsoft Graph.",
)
async def login_request(req: LoginRequest, request: Request) -> LoginResponse:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    email = req.email.strip().lower()

    # Rate limiting
    if not login_ip_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts from this IP address. Please wait a few minutes.",
        )
    if not login_email_limiter.is_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login requests for this email address. Please wait a few minutes.",
        )

    # Check against Zoho Active Users
    zoho_user = None
    try:
        zoho_user = await zoho_users_service.find_user_by_email(email)
    except Exception as e:
        logger.error("Failed to query Zoho Users: %s", e)

    # Email-only mode (development testing only)
    if settings.auth_mode == "email_only" and settings.app_env == "development":
        if not zoho_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{email}' is not an active user in Zoho Recruit.",
            )
        role = zoho_users_service.derive_user_role(zoho_user)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Zoho Recruit user role is not permitted to access this application.",
            )
        # Create session token directly
        fn = zoho_user.get("first_name", "") or ""
        ln = zoho_user.get("last_name", "") or ""
        name = f"{fn} {ln}".strip() or email
        token = create_session_jwt(email, role, name, str(zoho_user.get("id", "")))
        return LoginResponse(
            success=True,
            message="Development direct login successful.",
            challenge_token=token,
            auth_mode="email_only",
        )

    # Standard OTP Mode
    # Enumeration prevention: if user is not found, return generic success without sending email
    if not zoho_user:
        logger.info("Login requested for unknown/inactive email: %s. Returning generic response.", email)
        # Create a dummy challenge token to maintain response structure
        dummy_otp = generate_otp()
        dummy_token = create_challenge_token(email, dummy_otp)
        return LoginResponse(
            success=True,
            message="If this email belongs to an active Zoho Recruit user, a 6-digit verification code has been sent.",
            challenge_token=dummy_token,
            auth_mode="otp",
        )

    # Check role eligibility
    role = zoho_users_service.derive_user_role(zoho_user)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted. Your Zoho profile or role is not authorized for this platform.",
        )

    # Generate 6-digit OTP & sign challenge token
    otp = generate_otp(6)
    challenge_token = create_challenge_token(email, otp)

    # Send OTP email via Microsoft Graph
    sent = await email_service.send_otp_email(email, otp)
    if not sent:
        logger.warning("Failed to send OTP email to %s via Microsoft Graph.", email)

    return LoginResponse(
        success=True,
        message="If this email belongs to an active Zoho Recruit user, a 6-digit verification code has been sent.",
        challenge_token=challenge_token,
        auth_mode="otp",
    )


@router.post(
    "/login/verify",
    response_model=VerifyResponse,
    summary="Verify code and issue session token",
    description="Validates the OTP against the signed challenge token. Issues an 8-hour JWT session token upon success.",
)
async def login_verify(req: VerifyRequest) -> VerifyResponse:
    settings = get_settings()

    # Development email_only bypass
    if settings.auth_mode == "email_only" and settings.app_env == "development":
        from jose import jwt, JWTError
        from app.core.security import ALGORITHM
        try:
            payload = jwt.decode(req.challenge_token, settings.jwt_secret_key, algorithms=[ALGORITHM])
            if payload.get("type") == "session":
                return VerifyResponse(
                    access_token=req.challenge_token,
                    token_type="bearer",
                    expires_in=settings.jwt_expiry_hours * 3600,
                    role=payload.get("role", "employee"),
                    email=payload.get("email", ""),
                    name=payload.get("name", ""),
                    zoho_user_id=payload.get("zoho_user_id", ""),
                )
        except JWTError:
            pass

    # Verify challenge token
    is_valid, email, err_msg, new_challenge_token = verify_challenge_token(req.challenge_token, req.otp)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_msg or "Invalid verification code.",
            headers={"X-New-Challenge-Token": new_challenge_token} if new_challenge_token else None,
        )

    # Look up user in Zoho to fetch latest role and ID
    zoho_user = await zoho_users_service.find_user_by_email(email)
    if not zoho_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User record not found in Zoho Recruit Active Users.",
        )

    role = zoho_users_service.derive_user_role(zoho_user)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted.",
        )

    fn = zoho_user.get("first_name", "") or ""
    ln = zoho_user.get("last_name", "") or ""
    name = f"{fn} {ln}".strip() or email
    user_id = str(zoho_user.get("id", ""))

    access_token = create_session_jwt(
        email=email,
        role=role,
        name=name,
        zoho_user_id=user_id,
        expires_in_hours=settings.jwt_expiry_hours,
    )

    return VerifyResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiry_hours * 3600,
        role=role,
        email=email,
        name=name,
        zoho_user_id=user_id,
    )


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Current authenticated user details",
    description="Returns identity, role, and Zoho metadata for the currently logged-in user.",
)
async def get_me(user: dict = Depends(get_current_user)) -> UserMeResponse:
    return UserMeResponse(
        email=user.get("email", ""),
        role=user.get("role", "employee"),
        name=user.get("name", ""),
        zoho_user_id=user.get("zoho_user_id", ""),
    )


@router.get(
    "/validate",
    response_model=ValidateResponse,
    summary="Validate active session token",
    description="Confirms whether the caller's JWT is valid.",
)
async def validate_session(user: dict = Depends(get_current_user)) -> ValidateResponse:
    return ValidateResponse(
        valid=True,
        email=user.get("email", ""),
        role=user.get("role", "employee"),
    )
