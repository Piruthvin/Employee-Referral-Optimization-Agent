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


@pytest.mark.asyncio
async def test_email_only_mode_response_contract(client, mock_zoho_active_users):
    """
    Regression Test (a):
    Validates that email_only mode returns a complete, immediate session payload
    with access_token, user, and decodable JWT claims, matching the direct login contract.
    """
    from app.core.config import get_settings
    settings = get_settings()
    orig_env = settings.app_env
    orig_mode = settings.auth_mode

    try:
        settings.app_env = "development"
        settings.auth_mode = "email_only"

        with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)):
            resp = await client.post("/api/v1/auth/login/request", json={"email": "employee@company.com"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["auth_mode"] == "email_only"
            assert data["message"] == "Development direct login successful."
            assert data["access_token"] is not None
            assert data["challenge_token"] is not None
            assert data["role"] == "employee"
            assert data["user"]["email"] == "employee@company.com"
            assert data["user"]["role"] == "employee"

            # Direct verify bypass also accepts the session token
            ver_resp = await client.post(
                "/api/v1/auth/login/verify",
                json={"challenge_token": data["challenge_token"], "otp": "000000"},
            )
            assert ver_resp.status_code == 200
            ver_data = ver_resp.json()
            assert ver_data["access_token"] == data["challenge_token"]
            assert ver_data["role"] == "employee"
            assert ver_data["user"]["role"] == "employee"
    finally:
        settings.app_env = orig_env
        settings.auth_mode = orig_mode


@pytest.mark.asyncio
async def test_otp_mode_sendmail_exact_contract_and_verification(client, mock_zoho_active_users):
    """
    Regression Test (b):
    Validates that OTP mode calls Graph sendMail exactly once with the recipient email
    and a 6-digit code, NEVER exposes the plain OTP in response or challenge token,
    and requires the exact OTP within expiry for /auth/login/verify to succeed.
    """
    from app.core.config import get_settings
    from jose import jwt
    settings = get_settings()
    orig_env = settings.app_env
    orig_mode = settings.auth_mode

    try:
        settings.app_env = "production"
        settings.auth_mode = "otp"

        sent_calls = []

        async def fake_send_otp_email(to_email: str, otp: str) -> bool:
            sent_calls.append({"to_email": to_email, "otp": otp})
            return True

        with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
             patch("app.api.v1.auth.email_service.send_otp_email", side_effect=fake_send_otp_email):

            # 1. Request OTP
            resp = await client.post("/api/v1/auth/login/request", json={"email": "employee@company.com"})
            assert resp.status_code == 200
            data = resp.json()

            # Contract assertions
            assert data["success"] is True
            assert data["auth_mode"] == "otp"
            challenge_token = data["challenge_token"]
            assert challenge_token is not None

            # Assert sendMail was called exactly once with correct email and 6-digit code
            assert len(sent_calls) == 1
            dispatched_otp = sent_calls[0]["otp"]
            assert len(dispatched_otp) == 6
            assert dispatched_otp.isdigit()
            assert sent_calls[0]["to_email"] == "employee@company.com"

            # Assert the plain OTP is NEVER in the response JSON or plaintext challenge token
            assert dispatched_otp not in resp.text
            decoded_claims = jwt.get_unverified_claims(challenge_token)
            assert "otp" not in decoded_claims
            assert dispatched_otp not in str(decoded_claims)

            # 2. Verify with wrong OTP fails with 401
            bad_resp = await client.post(
                "/api/v1/auth/login/verify",
                json={"challenge_token": challenge_token, "otp": "000000"},
            )
            assert bad_resp.status_code == 401
            assert "Invalid verification code" in bad_resp.json()["detail"]

            # 3. Verify with correct OTP succeeds with 200
            good_resp = await client.post(
                "/api/v1/auth/login/verify",
                json={"challenge_token": challenge_token, "otp": dispatched_otp},
            )
            assert good_resp.status_code == 200
            good_data = good_resp.json()
            assert "access_token" in good_data
            assert good_data["role"] == "employee"
            assert good_data["email"] == "employee@company.com"
            assert good_data["user"]["email"] == "employee@company.com"

            # 4. Expired challenge token test
            expired_token = create_challenge_token("employee@company.com", dispatched_otp, expires_in_seconds=-10)
            exp_resp = await client.post(
                "/api/v1/auth/login/verify",
                json={"challenge_token": expired_token, "otp": dispatched_otp},
            )
            assert exp_resp.status_code == 401
            assert "expired" in exp_resp.json()["detail"].lower()
    finally:
        settings.app_env = orig_env
        settings.auth_mode = orig_mode


@pytest.mark.asyncio
async def test_zoho_users_live_success_never_invokes_fallback(client):
    """
    Regression Test (A.1.5): When /users succeeds (HTTP 200),
    the fallback path is NEVER invoked, users_source is 'live',
    and active users are correctly populated.
    """
    import respx
    import httpx
    from app.core.config import get_settings
    settings = get_settings()

    zoho_users_service.invalidate_cache()
    mock_users_payload = {
        "users": [
            {
                "id": "111111111111111111",
                "first_name": "Live",
                "last_name": "Recruiter",
                "email": "live.recruiter@company.com",
                "status": "active",
                "profile": {"name": "Administrator"},
                "role": {"name": "Administrator"},
            }
        ],
        "info": {"more_records": False},
    }

    with respx.mock(assert_all_called=False) as respx_mock, \
         patch.object(zoho_users_service, "_get_fallback_users", wraps=zoho_users_service._get_fallback_users) as spy_fallback:
        respx_mock.get(f"{settings.zoho_recruit_base_url.rstrip('/')}/users").mock(
            return_value=httpx.Response(200, json=mock_users_payload)
        )

        users = await zoho_users_service.get_active_users(force_refresh=True)
        assert len(users) == 1
        assert users[0]["email"] == "live.recruiter@company.com"
        assert zoho_users_service.users_source == "live"
        assert zoho_users_service.fallback_invoked is False
        spy_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_zoho_users_genuine_failure_returns_503_and_no_fallback_auth(client):
    """
    Regression Test (A.1.5): When /users genuinely fails (e.g. 401 scope mismatch or 500),
    the app returns a clear 503 Service Unavailable error to the login endpoint,
    users_source is 'unavailable', and no fake identities can authenticate.
    """
    import respx
    import httpx
    from app.core.config import get_settings
    settings = get_settings()

    zoho_users_service.invalidate_cache()

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(f"{settings.zoho_recruit_base_url.rstrip('/')}/users").mock(
            return_value=httpx.Response(
                401,
                json={"code": "OAUTH_SCOPE_MISMATCH", "message": "invalid oauth scope to access this URL"},
            )
        )

        # 1. Attempt login in email_only mode
        resp = await client.post("/api/v1/auth/login/request", json={"email": "piruthvin12@gmail.com"})
        assert resp.status_code == 503
        data = resp.json()
        assert "Zoho identity service is unavailable" in data["detail"]
        assert zoho_users_service.users_source == "unavailable"

        # 2. Check /ready probe reports unavailable
        ready_resp = await client.get("/api/v1/ready")
        assert ready_resp.status_code == 200
        assert ready_resp.json()["zoho_users_source"] == "unavailable"

        # 3. Verify fallback returned empty list and fake users cannot log in
        assert zoho_users_service._get_fallback_users() == []

