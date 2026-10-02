import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
import httpx

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.config import get_settings

logger = logging.getLogger("tests_live")

RECRUITER_EMAIL = "piruthvin.official.3@gmail.com"
EMPLOYEE_EMAIL = "piruthvin.official.2@gmail.com"
E2E_IDS_PATH = backend_root.parent / "docs" / "e2e_created_ids.json"


def pytest_configure(config):
    config.addinivalue_line("markers", "zoho: Live Zoho Recruit tests")
    config.addinivalue_line("markers", "graph: Live Microsoft Graph and Teams tests")
    config.addinivalue_line("markers", "igentic: Live iGentic router and connection tests")
    config.addinivalue_line("markers", "tools: Live agent tool endpoints verification")
    config.addinivalue_line("markers", "api: Live backend API matrix and validation tests")
    config.addinivalue_line("markers", "ui: Real browser UI tests")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("LIVE") != "1":
        skip_live = pytest.mark.skip(reason="Live tests require LIVE=1 environment variable")
        for item in items:
            if "tests_live" in str(item.fspath):
                item.add_marker(skip_live)


class E2ETracker:
    def __init__(self, path: Path):
        self.path = path
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"candidates": [], "jobs": [], "teams_meetings": []}, indent=2))

    def _read(self) -> dict[str, list[str]]:
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {"candidates": [], "jobs": [], "teams_meetings": []}

    def _write(self, data: dict[str, list[str]]):
        self.path.write_text(json.dumps(data, indent=2))

    def add_candidate(self, candidate_id: str):
        if not candidate_id:
            return
        data = self._read()
        if candidate_id not in data["candidates"]:
            data["candidates"].append(str(candidate_id))
            self._write(data)

    def add_job(self, job_id: str):
        if not job_id:
            return
        data = self._read()
        if job_id not in data["jobs"]:
            data["jobs"].append(str(job_id))
            self._write(data)

    def add_meeting(self, meeting_id: str):
        if not meeting_id:
            return
        data = self._read()
        if meeting_id not in data["teams_meetings"]:
            data["teams_meetings"].append(str(meeting_id))
            self._write(data)

    def get_tracked_ids(self) -> dict[str, list[str]]:
        return self._read()


@pytest.fixture(scope="session")
def tracker() -> E2ETracker:
    return E2ETracker(E2E_IDS_PATH)


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")


@pytest.fixture(scope="session")
async def http_client(base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=base_url, timeout=45.0) as client:
        yield client


@pytest.fixture(scope="session")
async def employee_token(http_client: httpx.AsyncClient) -> str:
    # Request login
    resp = await http_client.post("/api/v1/auth/login/request", json={"email": EMPLOYEE_EMAIL})
    assert resp.status_code == 200, f"Employee login request failed: {resp.text}"
    challenge = resp.json().get("challenge_token", "")

    # Verify login
    resp = await http_client.post(
        "/api/v1/auth/login/verify",
        json={"email": EMPLOYEE_EMAIL, "otp": "000000", "challenge_token": challenge},
    )
    assert resp.status_code == 200, f"Employee login verify failed: {resp.text}"
    token = resp.json().get("access_token", "")
    assert token, "Employee token missing in login response"
    return token


@pytest.fixture(scope="session")
async def recruiter_token(http_client: httpx.AsyncClient) -> str:
    # Request login
    resp = await http_client.post("/api/v1/auth/login/request", json={"email": RECRUITER_EMAIL})
    assert resp.status_code == 200, f"Recruiter login request failed: {resp.text}"
    challenge = resp.json().get("challenge_token", "")

    # Verify login
    resp = await http_client.post(
        "/api/v1/auth/login/verify",
        json={"email": RECRUITER_EMAIL, "otp": "000000", "challenge_token": challenge},
    )
    assert resp.status_code == 200, f"Recruiter login verify failed: {resp.text}"
    token = resp.json().get("access_token", "")
    assert token, "Recruiter token missing in login response"
    return token


@pytest.fixture(scope="session")
def employee_headers(employee_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {employee_token}"}


@pytest.fixture(scope="session")
def recruiter_headers(recruiter_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {recruiter_token}"}


@pytest.fixture(scope="session")
def agent_headers() -> dict[str, str]:
    settings = get_settings()
    return {"X-Agent-Key": settings.agent_api_key}


class IndependentZohoClient:
    """Independent helper calling Zoho Recruit APIs directly without using app service code."""
    def __init__(self):
        settings = get_settings()
        self.accounts_url = settings.zoho_accounts_url.rstrip("/")
        self.base_url = settings.zoho_recruit_base_url.rstrip("/")
        self.client_id = settings.zoho_client_id
        self.client_secret = settings.zoho_client_secret
        self.refresh_token = settings.zoho_refresh_token
        self._access_token: str | None = None
        self._cache_file = backend_root.parent / "tmp" / "zoho_token_cache.json"

    async def get_token(self) -> str:
        # Check disk cache
        if self._cache_file.exists():
            try:
                cached = json.loads(self._cache_file.read_text())
                if cached.get("access_token") and cached.get("expires_at", 0) > asyncio.get_event_loop().time() + 60:
                    self._access_token = cached["access_token"]
                    return self._access_token
            except Exception:
                pass

        if self._access_token:
            return self._access_token

        # Exchange refresh token
        url = f"{self.accounts_url}/oauth/v2/token"
        params = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params=params)
            assert resp.status_code == 200, f"Direct Zoho token refresh failed: {resp.text}"
            data = resp.json()
            token = data.get("access_token")
            assert token, f"No access token in direct response: {data}"
            self._access_token = token
            return token

    async def get_candidate_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        token = await self.get_token()
        url = f"{self.base_url}/Candidates/{candidate_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return data[0] if data else None
            return None

    async def search_candidates_by_email(self, email: str) -> list[dict[str, Any]]:
        token = await self.get_token()
        criteria = f"((Email:equals:{email.strip().lower()}))"
        url = f"{self.base_url}/Candidates/search"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params={"criteria": criteria}, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []

    async def get_attachments(self, candidate_id: str) -> list[dict[str, Any]]:
        token = await self.get_token()
        url = f"{self.base_url}/Candidates/{candidate_id}/Attachments"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []

    async def download_attachment_bytes(self, candidate_id: str, attachment_id: str) -> bytes:
        token = await self.get_token()
        url = f"{self.base_url}/Candidates/{candidate_id}/Attachments/{attachment_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            assert resp.status_code == 200, f"Direct attachment download failed: {resp.status_code} - {resp.text}"
            return resp.content

    async def get_notes(self, candidate_id: str) -> list[dict[str, Any]]:
        token = await self.get_token()
        url = f"{self.base_url}/Candidates/{candidate_id}/Notes"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []

    async def get_job_openings(self) -> list[dict[str, Any]]:
        token = await self.get_token()
        url = f"{self.base_url}/JobOpenings"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []

    async def delete_candidate(self, candidate_id: str) -> bool:
        token = await self.get_token()
        url = f"{self.base_url}/Candidates?ids={candidate_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            return resp.status_code in (200, 204)


@pytest.fixture(scope="session")
def direct_zoho() -> IndependentZohoClient:
    return IndependentZohoClient()
