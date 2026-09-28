"""
Pytest fixtures and environment configuration.
Configures test settings and mocks external network calls.
"""

import os
import sys
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


# Set test environment before any app imports
os.environ["APP_ENV"] = "development"
os.environ["AUTH_MODE"] = "otp"
os.environ["JWT_SECRET_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
os.environ["AGENT_API_KEY"] = "test-agent-key-secret-12345"
os.environ["ZOHO_CLIENT_ID"] = "dummy-client-id"
os.environ["ZOHO_CLIENT_SECRET"] = "dummy-client-secret"
os.environ["ZOHO_REFRESH_TOKEN"] = "dummy-refresh-token"
os.environ["ZOHO_ACCOUNTS_BASE_URL"] = "https://accounts.zoho.in"
os.environ["ZOHO_RECRUIT_BASE_URL"] = "https://recruit.zoho.in/recruit/v2"
os.environ["MIN_ASSOCIATE_MATCH"] = "40"
os.environ["POINTS_PER_REFERRAL"] = "10"
os.environ["RESUME_PARSER_MODE"] = "auto"

from app.main import app
from app.core.config import get_settings
from app.core.security import create_session_jwt
from app.services.zoho_users_service import zoho_users_service
from app.infrastructure.zoho_auth import zoho_auth_manager
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def reset_singletons():
    """Resets cached data in singletons between tests and mocks external Zoho token refresh."""
    zoho_users_service.invalidate_cache()
    with patch.object(zoho_auth_manager, "get_access_token", AsyncMock(return_value="mock-zoho-access-token")):
        yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def employee_jwt() -> str:
    return create_session_jwt(
        email="employee@company.com",
        role="employee",
        name="John Employee",
        zoho_user_id="1000001",
    )


@pytest.fixture
def recruiter_jwt() -> str:
    return create_session_jwt(
        email="recruiter@company.com",
        role="recruiter",
        name="Jane Recruiter",
        zoho_user_id="1000002",
    )


@pytest.fixture
def hiring_manager_jwt() -> str:
    return create_session_jwt(
        email="manager@company.com",
        role="hiring_manager",
        name="Mark Manager",
        zoho_user_id="1000003",
    )


@pytest.fixture
def mock_zoho_active_users():
    return [
        {
            "id": "1000001",
            "first_name": "John",
            "last_name": "Employee",
            "email": "employee@company.com",
            "status": "active",
            "profile": {"name": "Employee"},
            "role": {"name": "Employee"},
        },
        {
            "id": "1000002",
            "first_name": "Jane",
            "last_name": "Recruiter",
            "email": "recruiter@company.com",
            "status": "active",
            "profile": {"name": "Administrator"},
            "role": {"name": "Recruiter Admin"},
        },
        {
            "id": "1000003",
            "first_name": "Mark",
            "last_name": "Manager",
            "email": "manager@company.com",
            "status": "active",
            "profile": {"name": "Standard"},
            "role": {"name": "Hiring Manager"},
        },
        {
            "id": "1000004",
            "first_name": "Inactive",
            "last_name": "User",
            "email": "inactive@company.com",
            "status": "inactive",
            "profile": {"name": "Employee"},
            "role": {"name": "Employee"},
        },
        {
            "id": "1000005",
            "first_name": "Guest",
            "last_name": "User",
            "email": "guest@company.com",
            "status": "active",
            "profile": {"name": "Guest Profile"},
            "role": {"name": "Guest Role"},
        },
    ]
