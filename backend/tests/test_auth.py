"""
Unit and integration tests for Authentication and Role Mapping:
- OTP generation, delivery, and verification
- User enumeration prevention (identical responses for unknown users)
- Inactive user rejection
- Zoho Profile & Role derivation (recruiter, employee, hiring manager, disallowed roles)
- Production refusal of email_only mode
- Absence of tenure/joining date restrictions
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.core.config import Settings
from app.core.security import verify_challenge_token, create_challenge_token
from app.services.zoho_users_service import zoho_users_service


@pytest.mark.asyncio
async def test_login_otp_flow_success(client, mock_zoho_active_users):
    """Verifies complete OTP login lifecycle from request to JWT session creation."""
    captured_otp = {}

    async def fake_send_otp(email, otp):
        captured_otp["otp"] = otp
        return True

    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch("app.api.v1.auth.email_service.send_otp_email", side_effect=fake_send_otp):

        # 1. Request OTP
        req_resp = await client.post("/api/v1/auth/login/request", json={"email": "employee@company.com"})
        assert req_resp.status_code == 200
        req_data = req_resp.json()
        assert req_data["success"] is True
        challenge_token = req_data["challenge_token"]
        assert challenge_token is not None
        assert "otp" in captured_otp

        # 2. Verify with valid OTP
        ver_resp = await client.post(
            "/api/v1/auth/login/verify",
            json={"challenge_token": challenge_token, "otp": captured_otp["otp"]},
        )
        assert ver_resp.status_code == 200
        ver_data = ver_resp.json()
        assert "access_token" in ver_data
        assert ver_data["role"] == "employee"
        assert ver_data["email"] == "employee@company.com"
        assert ver_data["name"] == "John Employee"


@pytest.mark.asyncio
async def test_login_otp_invalid_code(client, mock_zoho_active_users):
    """Verifies that submitting an incorrect OTP returns 401 and tracks remaining attempts."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch("app.api.v1.auth.email_service.send_otp_email", AsyncMock(return_value=True)):

        req_resp = await client.post("/api/v1/auth/login/request", json={"email": "employee@company.com"})
        challenge_token = req_resp.json()["challenge_token"]

        ver_resp = await client.post(
            "/api/v1/auth/login/verify",
            json={"challenge_token": challenge_token, "otp": "999999"},
        )
        assert ver_resp.status_code == 401
        assert "Invalid verification code" in ver_resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_otp_max_attempts_exceeded(client, mock_zoho_active_users):
    """Verifies challenge token is permanently rejected after 5 failed attempts."""
    # Create challenge token with 5 attempts already recorded
    token = create_challenge_token("employee@company.com", "123456")
    curr_token = token
    for _ in range(5):
        is_val, _, _, next_tok = verify_challenge_token(curr_token, "000000")
        assert not is_val
        if next_tok:
            curr_token = next_tok

    # Now verify should be rejected with attempt limit
    is_val, _, err_msg, _ = verify_challenge_token(curr_token, "123456")
    assert not is_val
    assert "Maximum verification attempts exceeded" in err_msg


@pytest.mark.asyncio
async def test_unknown_email_returns_generic_response(client, mock_zoho_active_users):
    """User enumeration prevention: unknown emails receive identical success response."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch("app.api.v1.auth.email_service.send_otp_email", AsyncMock(return_value=True)) as mock_send:

        resp = await client.post("/api/v1/auth/login/request", json={"email": "attacker@unknown-domain.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "If this email belongs to an active Zoho Recruit user" in data["message"]
        assert data["challenge_token"] is not None
        # Must not send an email for unknown users
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_inactive_user_rejected(client, mock_zoho_active_users):
    """Inactive Zoho users are treated as non-existent to prevent unauthorized access."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)):
        user = await zoho_users_service.find_user_by_email("inactive@company.com")
        assert user is None


@pytest.mark.asyncio
async def test_role_mapping_from_zoho_users():
    """Validates role mapping logic: Administrator->recruiter, Employee->employee, etc."""
    settings = Settings()

    # Recruiter / Admin
    assert settings.derive_role("Administrator", "Admin") == "recruiter"
    assert settings.derive_role("Standard", "Recruiter Admin") == "recruiter"
    assert settings.derive_role("Senior Recruiter", "Staff") == "recruiter"

    # Employee
    assert settings.derive_role("Employee", "Employee") == "employee"
    assert settings.derive_role("Standard", "Employee") == "employee"

    # Hiring Manager
    assert settings.derive_role("Standard", "Hiring Manager") == "hiring_manager"

    # Unauthorized role
    assert settings.derive_role("Guest", "Contractor") is None


def test_email_only_refused_in_production():
    """Application must fail-fast and refuse to start if email_only auth is set in production."""
    with pytest.raises(ValueError, match="AUTH_MODE=email_only is strictly prohibited in production"):
        Settings(
            APP_ENV="production",
            AUTH_MODE="email_only",
            JWT_SECRET_KEY="x" * 64,
            AGENT_API_KEY="x" * 32,
            ZOHO_CLIENT_ID="id",
            ZOHO_CLIENT_SECRET="sec",
            ZOHO_REFRESH_TOKEN="tok",
        )


def test_no_tenure_or_contacts_logic_in_settings():
    """Confirms complete elimination of Date_of_Joining, tenure checks, and Contacts settings."""
    settings = Settings()
    # Check that settings attributes do not include tenure or contacts fields
    assert not hasattr(settings, "date_of_joining")
    assert not hasattr(settings, "min_tenure_years")
    assert not hasattr(settings, "zoho_contacts_base_url")


@pytest.mark.asyncio
async def test_get_me_and_validate(client, employee_jwt):
    """Tests /auth/me and /auth/validate endpoints with valid JWT token."""
    headers = {"Authorization": f"Bearer {employee_jwt}"}

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "employee@company.com"
    assert me_data["role"] == "employee"

    val_resp = await client.get("/api/v1/auth/validate", headers=headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is True
