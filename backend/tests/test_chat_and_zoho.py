"""
Tests for iGentic chat streaming, Zoho pagination, token refresh retry, and analytics calculations:
- Chat SSE streaming relay with context injection
- Synchronous chat completions
- Zoho Recruit multi-page pagination loop
- Zoho 401 token invalidation and refresh recovery
- Derived employee points computation
- Recruiter dashboard KPI aggregation
"""

import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import Response, Request

from app.services.igentic_client import igentic_client
from app.services.zoho_service import zoho_service
from app.infrastructure.zoho_auth import zoho_auth_manager


@pytest.mark.asyncio
async def test_chat_sse_stream_relay_and_context_injection(client, employee_jwt):
    """Verifies that chat streaming relays SSE events and prepends [CONTEXT role=... email=...]."""
    headers = {"Authorization": f"Bearer {employee_jwt}"}

    captured_call = {}

    async def fake_stream(user_message, session_id, user_email, user_role):
        captured_call["message"] = user_message
        captured_call["email"] = user_email
        captured_call["role"] = user_role
        yield f"data: {json.dumps({'Type': 'status', 'Status': 'Thinking...'})}\n\n"
        yield f"data: {json.dumps({'Type': 'complete', 'Result': 'Hello from agent!', 'SessionId': 'sess-123'})}\n\n"

    with patch.object(igentic_client, "call_stream", side_effect=fake_stream):
        resp = await client.post(
            "/api/v1/chat/stream",
            json={"message": "What is my referral bonus?", "conversation_id": "sess-123"},
            headers=headers,
        )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body_text = resp.text
        assert "Thinking..." in body_text
        assert "Hello from agent!" in body_text
        assert captured_call["email"] == "employee@company.com"
        assert captured_call["role"] == "employee"


@pytest.mark.asyncio
async def test_chat_sync_completion(client, recruiter_jwt):
    """Verifies synchronous non-streaming chat endpoint."""
    headers = {"Authorization": f"Bearer {recruiter_jwt}"}

    with patch.object(igentic_client, "call_sync", AsyncMock(return_value={"response": "Recruiter summary text", "conversation_id": "conv-99"})):
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Show analytics summary"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "Recruiter summary text"
        assert data["conversation_id"] == "conv-99"


@pytest.mark.asyncio
async def test_zoho_pagination_loop():
    """Verifies that ZohoService paginates through multiple pages until more_records is False."""
    page_1 = [
        {"id": "1", "Referred_By": "emp@company.com", "Source": "Employee Referral"},
        {"id": "2", "Referred_By": "emp@company.com", "Source": "Employee Referral"},
    ]
    page_2 = [
        {"id": "3", "Referred_By": "emp@company.com", "Source": "Employee Referral"},
    ]

    async def fake_get_all(page=1, per_page=200):
        if page == 1:
            return page_1, True
        elif page == 2:
            return page_2, False
        return [], False

    with patch.object(zoho_service, "get_all_candidates", side_effect=fake_get_all):
        all_cands = await zoho_service.get_all_candidates_cached(force_refresh=True)
        assert len(all_cands) == 3
        assert [c["id"] for c in all_cands] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_zoho_401_token_refresh_retry():
    """Tests that receiving a 401 from Zoho triggers token invalidation and refresh before retry."""
    req = Request("GET", "https://recruit.zoho.in/recruit/v2/Candidates")

    calls = {"count": 0}

    async def fake_send_request(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            # First attempt returns 401
            return Response(status_code=401, request=req, json={"code": "AUTHENTICATION_FAILURE"})
        # Second attempt succeeds
        return Response(status_code=200, request=req, json={"data": [{"id": "99"}]})

    with patch.object(zoho_auth_manager, "get_access_token", AsyncMock(return_value="valid-token")), \
         patch.object(zoho_auth_manager, "invalidate_token") as mock_inval, \
         patch("httpx.AsyncClient.request", side_effect=fake_send_request):

        cand = await zoho_service.get_candidate_by_id("99")
        assert cand is not None
        assert cand["id"] == "99"
        mock_inval.assert_called_once()


@pytest.mark.asyncio
async def test_employee_points_calculation(client, employee_jwt):
    """Verifies that GET /employees/points calculates points purely from Zoho candidate counts."""
    mock_referrals = [
        {"id": "1", "Referred_By": "employee@company.com", "Referral_Approval_Status": "Approved"},
        {"id": "2", "Referred_By": "employee@company.com", "Referral_Approval_Status": "Pending"},
        {"id": "3", "Referred_By": "employee@company.com", "Referral_Approval_Status": "Approved"},
    ]

    with patch.object(zoho_service, "get_candidates_by_referrer", AsyncMock(return_value=mock_referrals)):
        resp = await client.get("/api/v1/employees/points", headers={"Authorization": f"Bearer {employee_jwt}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["referral_count"] == 3
        assert data["approved_count"] == 2
        # 3 referrals * 10 points = 30 points
        assert data["points"] == 30


@pytest.mark.asyncio
async def test_dashboard_metrics_aggregation(client, recruiter_jwt):
    """Verifies that GET /analytics/dashboard correctly aggregates counts and conversion rates."""
    mock_candidates = [
        {
            "id": "1",
            "Referred_By": "emp1@company.com",
            "Source": "Employee Referral",
            "Referral_Approval_Status": "Approved",
            "Candidate_Status": "Interview Scheduled",
            "Referred_Date": "2026-09-01",
            "Modified_Time": "2026-09-03",
        },
        {
            "id": "2",
            "Referred_By": "emp2@company.com",
            "Source": "Employee Referral",
            "Referral_Approval_Status": "Pending",
            "Candidate_Status": "New",
            "Referred_Date": "2026-09-20",
        },
        {
            "id": "3",
            "Referred_By": "emp3@company.com",
            "Source": "Employee Referral",
            "Referral_Approval_Status": "Rejected",
            "Candidate_Status": "Rejected",
            "Referred_Date": "2026-09-10",
            "Modified_Time": "2026-09-11",
        },
        {
            "id": "4",
            "Referred_By": "emp1@company.com",
            "Source": "Employee Referral",
            "Referral_Approval_Status": "Approved",
            "Candidate_Status": "Hired",
            "Referred_Date": "2026-08-01",
            "Modified_Time": "2026-08-05",
        },
    ]

    with patch.object(zoho_service, "get_all_candidates_cached", AsyncMock(return_value=mock_candidates)):
        resp = await client.get("/api/v1/analytics/dashboard", headers={"Authorization": f"Bearer {recruiter_jwt}"})
        assert resp.status_code == 200
        kpis = resp.json()
        assert kpis["total_referrals"] == 4
        assert kpis["pending_approvals"] == 1
        assert kpis["approved_referrals"] == 2
        assert kpis["rejected_referrals"] == 1
        assert kpis["interviews_scheduled"] == 1
        assert kpis["total_points_awarded"] == 40
        # 1 hired / 4 total = 25.0%
        assert kpis["conversion_rate_percent"] == 25.0
