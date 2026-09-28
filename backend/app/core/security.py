"""
Security and authentication primitives:
- JWT token generation & verification (HS256)
- Stateless OTP challenge token generation and verification using HMAC
- In-memory rate limiting for auth endpoints (per-IP and per-email)
- Constant-time secret comparison for Agent API key
"""

import hmac
import hashlib
import time
import secrets
import logging
from typing import Any, Tuple
from collections import defaultdict
from jose import jwt, JWTError
from app.core.config import get_settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure random 6-digit numeric OTP."""
    # e.g., 000000 to 999999
    number = secrets.randbelow(10 ** length)
    return f"{number:0{length}d}"


def _hash_otp(email: str, otp: str, secret_key: str) -> str:
    """Computes SHA-256 HMAC for the OTP keyed to the recipient email."""
    normalized_email = email.strip().lower()
    msg = f"{normalized_email}:{otp.strip()}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def create_challenge_token(email: str, otp: str, expires_in_seconds: int = 600) -> str:
    """
    Creates a short-lived (10 min) signed challenge token containing:
    - email (subject)
    - HMAC of the OTP (the plain OTP is NEVER stored or sent in token)
    - attempt counter
    - expiration timestamp
    """
    settings = get_settings()
    now = int(time.time())
    otp_hash = _hash_otp(email, otp, settings.jwt_secret_key)

    payload = {
        "sub": email.strip().lower(),
        "otp_hash": otp_hash,
        "attempts": 0,
        "type": "otp_challenge",
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def verify_challenge_token(challenge_token: str, submitted_otp: str) -> Tuple[bool, str, str, str | None]:
    """
    Verifies the submitted OTP against the challenge token.
    Returns:
        (is_valid: bool, email: str, error_message: str, new_challenge_token: str | None)
    """
    settings = get_settings()
    try:
        payload = jwt.decode(challenge_token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return False, "", "Invalid or expired challenge token. Please request a new code.", None

    if payload.get("type") != "otp_challenge":
        return False, "", "Invalid token type.", None

    email = payload.get("sub", "")
    stored_hash = payload.get("otp_hash", "")
    attempts = payload.get("attempts", 0)

    if attempts >= 5:
        return False, email, "Maximum verification attempts exceeded. Please request a new code.", None

    computed_hash = _hash_otp(email, submitted_otp, settings.jwt_secret_key)
    if hmac.compare_digest(stored_hash, computed_hash):
        return True, email, "", None

    # Invalid OTP - increment attempts and issue updated token
    payload["attempts"] = attempts + 1
    new_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)
    remaining = 5 - (attempts + 1)
    msg = f"Invalid verification code. {remaining} attempt(s) remaining." if remaining > 0 else "Invalid code. Max attempts exceeded."
    return False, email, msg, new_token


def create_session_jwt(
    email: str,
    role: str,
    name: str,
    zoho_user_id: str,
    expires_in_hours: int | None = None,
) -> str:
    """
    Creates an 8-hour session JWT with standard claims:
    sub, role, email, name, zoho_user_id, iat, exp.
    """
    settings = get_settings()
    hours = expires_in_hours if expires_in_hours is not None else settings.jwt_expiry_hours
    now = int(time.time())
    payload = {
        "sub": email.strip().lower(),
        "email": email.strip().lower(),
        "role": role,
        "name": name,
        "zoho_user_id": zoho_user_id,
        "type": "session",
        "iat": now,
        "exp": now + (hours * 3600),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def decode_session_jwt(token: str) -> dict[str, Any]:
    """Decodes and validates a session JWT."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != "session":
        raise JWTError("Invalid token type. Expected session token.")
    return payload


def verify_agent_api_key(provided_key: str | None) -> bool:
    """Constant-time comparison for the X-Agent-Key header."""
    if not provided_key:
        return False
    settings = get_settings()
    if not settings.agent_api_key:
        return False
    return secrets.compare_digest(provided_key.strip(), settings.agent_api_key.strip())


# ── In-Memory Rate Limiting ────────────────────────────────────────────────────

class InMemoryRateLimiter:
    """Simple sliding window rate limiter per key (e.g. IP or email)."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean older entries
        recent = [t for t in self._history[key] if t > cutoff]
        self._history[key] = recent
        if len(recent) >= self.max_requests:
            return False
        self._history[key].append(now)
        return True


# Global rate limiters for auth
login_ip_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=300)      # 10 req / 5 min per IP
login_email_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=300)    # 5 req / 5 min per email
