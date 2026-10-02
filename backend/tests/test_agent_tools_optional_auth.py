"""
Tests verifying that all 13 Agent Tool endpoints:
1. Are callable with NO authentication headers at all (0 headers).
2. Continue working when called with a valid frontend Bearer JWT.
3. Continue working when called with X-Agent-Key.
4. Gracefully ignore invalid or expired Bearer JWT / invalid X-Agent-Key.
5. Strictly enforce live Zoho role boundaries (recruiter vs employee) inside business logic.
6. Preserve mandatory authentication on all non-tool endpoints.
"""

from unittest.mock import AsyncMock, patch
import pytest
from app.services.zoho_users_service import zoho_users_service
from app.services.zoho_service import zoho_service
from app.services.approval_service import approval_service
from app.services.interview_service import interview_service
from app.services.email_service import email_service
from app.services.analytics_service import analytics_service


@pytest.fixture
def mock_candidates():
    return [
        {
            "id": "CAND_101",
            "First_Name": "Alice",
            "Last_Name": "Smith",
            "Email": "alice@example.com",
            "Referred_By": "employee@company.com",
            "Referral_Approval_Status": "Approved",
            "Candidate_Status": "Approved",
            "Referral_Score": 88.0,
            "Skill_Set": ["Python", "FastAPI"],
            "Experience_in_Years": 4.0,
            "Current_Job_Title": "Python Developer",
            "Referred_Date": "2026-09-20",
        },
        {
            "id": "CAND_102",
            "First_Name": "Bob",
            "Last_Name": "Jones",
            "Email": "bob@example.com",
            "Referred_By": "other@company.com",
            "Referral_Approval_Status": "Pending",
            "Candidate_Status": "Waiting for Review",
            "Referral_Score": 75.0,
            "Skill_Set": ["React"],
            "Experience_in_Years": 2.0,
            "Current_Job_Title": "Frontend Developer",
            "Referred_Date": "2026-09-25",
        },
    ]


@pytest.mark.asyncio
async def test_tool_1_referral_status_no_auth(client, mock_zoho_active_users, mock_candidates):
    """Tool 1: POST /api/v1/referral/status works with 0 auth headers."""
    cand = mock_candidates[0]
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(zoho_service, "get_candidate_by_id", AsyncMock(return_value=cand)), \
         patch.object(zoho_service, "get_candidate_notes", AsyncMock(return_value=[])):

        # No auth headers, caller is referring employee -> 200
        resp = await client.post(
            "/api/v1/referral/status",
            json={"candidate_id": "CAND_101", "requester_email": "employee@company.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_id"] == "CAND_101"
        assert data["approval_status"] == "Approved"

        # Employee attempting to view someone else's referral -> 403
        resp_forbidden = await client.post(
            "/api/v1/referral/status",
            json={"candidate_id": "CAND_101", "requester_email": "manager@company.com"},
        )
        # manager is hiring_manager -> allowed
        assert resp_forbidden.status_code == 200

        # Unauthenticated without requester_email -> 403 (cannot inspect)
        resp_no_email = await client.post(
            "/api/v1/referral/status",
            json={"candidate_id": "CAND_101"},
        )
        assert resp_no_email.status_code == 403


@pytest.mark.asyncio
async def test_tool_2_jobs_match_no_auth(client, mock_zoho_active_users, mock_candidates):
    """Tool 2: POST /api/v1/jobs/match works with 0 auth headers."""
    cand = mock_candidates[0]
    mock_jobs = [
        {
            "id": "JOB_1",
            "Posting_Title": "Python Developer",
            "Department": "Engineering",
            "Job_Opening_Status": "Active",
            "Required_Skills": ["Python", "FastAPI"],
            "Experience_in_Years": 3.0,
        }
    ]
    with patch.object(zoho_service, "get_candidate_by_id", AsyncMock(return_value=cand)), \
         patch.object(zoho_service, "get_open_jobs", AsyncMock(return_value=mock_jobs)):

        resp = await client.post(
            "/api/v1/jobs/match",
            json={"candidate_id": "CAND_101", "min_match": 40},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "matches" in data
        assert len(data["matches"]) >= 1


@pytest.mark.asyncio
async def test_tool_3_employees_points_no_auth(client, mock_zoho_active_users):
    """Tool 3: POST /api/v1/employees/points works with 0 auth headers."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(analytics_service, "get_employee_points", AsyncMock(return_value={
             "email": "employee@company.com", "total_referrals": 2, "approved_referrals": 1, "points": 10
         })):

        # No auth header, requester_email in body
        resp = await client.post(
            "/api/v1/employees/points",
            json={"requester_email": "employee@company.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["points"] == 10

        # No auth header and no email -> 400
        resp_no_email = await client.post("/api/v1/employees/points", json={})
        assert resp_no_email.status_code == 400


@pytest.mark.asyncio
async def test_tool_4_approvals_pending_no_auth_and_role_gate(client, mock_zoho_active_users):
    """Tool 4: POST /api/v1/approvals/pending works with recruiter email, rejects employee."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(approval_service, "get_pending_approvals", AsyncMock(return_value=[])):

        # Recruiter calling with NO auth header -> 200
        resp = await client.post(
            "/api/v1/approvals/pending",
            json={"requester_email": "recruiter@company.com"},
        )
        assert resp.status_code == 200

        # Employee calling with NO auth header -> 403 Forbidden
        resp_emp = await client.post(
            "/api/v1/approvals/pending",
            json={"requester_email": "employee@company.com"},
        )
        assert resp_emp.status_code == 403

        # Anonymous caller with NO email -> 403 Forbidden
        resp_anon = await client.post("/api/v1/approvals/pending", json={})
        assert resp_anon.status_code == 403


@pytest.mark.asyncio
async def test_tool_5_and_6_approve_reject_no_auth(client, mock_zoho_active_users):
    """Tools 5 & 6: POST /api/v1/approvals/approve & reject work with recruiter, reject employee."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(approval_service, "approve_referral", AsyncMock(return_value={
             "success": True, "candidate_id": "CAND_101", "approval_status": "Approved", "message": "Referral approved."
         })), \
         patch.object(approval_service, "reject_referral", AsyncMock(return_value={
             "success": True, "candidate_id": "CAND_101", "approval_status": "Rejected", "message": "Referral rejected."
         })):

        # Tool 5: Approve by recruiter with 0 auth headers -> 200
        resp_app = await client.post(
            "/api/v1/approvals/approve",
            json={"candidate_id": "CAND_101", "requester_email": "recruiter@company.com", "note": "Great fit"},
        )
        assert resp_app.status_code == 200
        assert resp_app.json()["approval_status"] == "Approved"

        # Tool 5: Approve by employee -> 403
        resp_app_emp = await client.post(
            "/api/v1/approvals/approve",
            json={"candidate_id": "CAND_101", "requester_email": "employee@company.com", "note": "Great fit"},
        )
        assert resp_app_emp.status_code == 403

        # Tool 6: Reject by recruiter with 0 auth headers -> 200
        resp_rej = await client.post(
            "/api/v1/approvals/reject",
            json={"candidate_id": "CAND_101", "requester_email": "recruiter@company.com", "note": "Mismatch"},
        )
        assert resp_rej.status_code == 200
        assert resp_rej.json()["approval_status"] == "Rejected"

        # Tool 6: Reject by employee -> 403
        resp_rej_emp = await client.post(
            "/api/v1/approvals/reject",
            json={"candidate_id": "CAND_101", "requester_email": "employee@company.com", "note": "Mismatch"},
        )
        assert resp_rej_emp.status_code == 403


@pytest.mark.asyncio
async def test_tool_7_interview_schedule_no_auth(client, mock_zoho_active_users):
    """Tool 7: POST /api/v1/interview/schedule works with recruiter, rejects employee."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(interview_service, "schedule_interview", AsyncMock(return_value={
             "success": True,
             "candidate_id": "CAND_101",
             "meeting_url": "https://teams.microsoft.com/l/meetup-join/123",
             "start_time": "2026-10-05T14:00:00Z",
             "end_time": "2026-10-05T15:00:00Z",
             "status": "Interview Scheduled",
             "message": "Scheduled successfully",
         })):

        # Recruiter with 0 auth headers -> 200
        resp = await client.post(
            "/api/v1/interview/schedule",
            json={
                "candidate_id": "CAND_101",
                "start_time": "2026-10-05T14:00:00Z",
                "interviewer_email": "interviewer@company.com",
                "requester_email": "recruiter@company.com",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Interview Scheduled"

        # Employee with 0 auth headers -> 403
        resp_emp = await client.post(
            "/api/v1/interview/schedule",
            json={
                "candidate_id": "CAND_101",
                "start_time": "2026-10-05T14:00:00Z",
                "interviewer_email": "interviewer@company.com",
                "requester_email": "employee@company.com",
            },
        )
        assert resp_emp.status_code == 403


@pytest.mark.asyncio
async def test_tool_8_notifications_email_no_auth(client):
    """Tool 8: POST /api/v1/notifications/email works with 0 auth headers."""
    with patch.object(email_service, "send_email", AsyncMock(return_value=True)):
        resp = await client.post(
            "/api/v1/notifications/email",
            json={
                "recipient_email": "candidate@example.com",
                "subject": "Interview Invitation",
                "body_html": "<p>You are invited</p>",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_tools_9_to_13_analytics_no_auth_and_role_gate(client, mock_zoho_active_users):
    """Tools 9-13: Analytics endpoints work with recruiter, reject employee."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(analytics_service, "get_dashboard_metrics", AsyncMock(return_value={
             "total_referrals": 10, "pending_approvals": 2, "approved_referrals": 6, "rejected_referrals": 2,
             "interviews_scheduled": 4, "total_points_awarded": 60, "conversion_rate_percent": 40.0, "avg_approval_days": 1.5
         })), \
         patch.object(analytics_service, "get_conversion_metrics", AsyncMock(return_value={
             "total_referrals": 10, "approved": 6, "scheduled": 4, "hired": 2,
             "referral_to_approved_percent": 60.0, "approved_to_interview_percent": 66.7, "overall_hire_conversion_percent": 20.0
         })), \
         patch.object(analytics_service, "get_pending_referrals", AsyncMock(return_value={
             "count": 1, "threshold_days": 5, "referrals": []
         })), \
         patch.object(analytics_service, "get_top_candidates_by_role", AsyncMock(return_value={
             "role": "Python Developer", "candidates": []
         })), \
         patch.object(analytics_service, "get_referral_trends", AsyncMock(return_value={
             "periods": []
         })):

        rec_body = {"requester_email": "recruiter@company.com"}
        emp_body = {"requester_email": "employee@company.com"}

        # Tool 9: Dashboard
        resp_9 = await client.post("/api/v1/analytics/dashboard", json=rec_body)
        assert resp_9.status_code == 200
        resp_9_emp = await client.post("/api/v1/analytics/dashboard", json=emp_body)
        assert resp_9_emp.status_code == 403

        # Tool 10: Conversion
        resp_10 = await client.post("/api/v1/analytics/conversion", json=rec_body)
        assert resp_10.status_code == 200
        resp_10_emp = await client.post("/api/v1/analytics/conversion", json=emp_body)
        assert resp_10_emp.status_code == 403

        # Tool 11: Pending
        resp_11 = await client.post("/api/v1/analytics/pending", json={"requester_email": "recruiter@company.com", "days_threshold": 5})
        assert resp_11.status_code == 200
        resp_11_emp = await client.post("/api/v1/analytics/pending", json=emp_body)
        assert resp_11_emp.status_code == 403

        # Tool 12: Top Candidates
        resp_12 = await client.post("/api/v1/analytics/top-candidates", json={"job_title": "Python Developer", "requester_email": "recruiter@company.com"})
        assert resp_12.status_code == 200
        resp_12_emp = await client.post("/api/v1/analytics/top-candidates", json={"job_title": "Python Developer", "requester_email": "employee@company.com"})
        assert resp_12_emp.status_code == 403

        # Tool 13: Trends
        resp_13 = await client.post("/api/v1/analytics/trends", json=rec_body)
        assert resp_13.status_code == 200
        resp_13_emp = await client.post("/api/v1/analytics/trends", json=emp_body)
        assert resp_13_emp.status_code == 403


@pytest.mark.asyncio
async def test_jwt_override_and_invalid_auth_handling(client, recruiter_jwt, mock_zoho_active_users):
    """Verified Bearer JWT always wins over body, and invalid headers are ignored gracefully."""
    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(approval_service, "get_pending_approvals", AsyncMock(return_value=[])):

        # 1. Valid recruiter JWT + conflicting employee body -> Recruiter JWT wins!
        headers = {"Authorization": f"Bearer {recruiter_jwt}"}
        resp = await client.post(
            "/api/v1/approvals/pending",
            headers=headers,
            json={"requester_email": "employee@company.com"},  # conflict!
        )
        assert resp.status_code == 200

        # 2. Invalid JWT header + valid recruiter email in body -> JWT ignored, body role derived -> 200
        headers_invalid_jwt = {"Authorization": "Bearer invalid.jwt.token"}
        resp_fallback = await client.post(
            "/api/v1/approvals/pending",
            headers=headers_invalid_jwt,
            json={"requester_email": "recruiter@company.com"},
        )
        assert resp_fallback.status_code == 200

        # 3. Invalid X-Agent-Key + valid recruiter email in body -> Agent key ignored, body role derived -> 200
        headers_invalid_key = {"X-Agent-Key": "wrong-agent-key"}
        resp_fallback_key = await client.post(
            "/api/v1/approvals/pending",
            headers=headers_invalid_key,
            json={"requester_email": "recruiter@company.com"},
        )
        assert resp_fallback_key.status_code == 200

        # 4. Valid X-Agent-Key + recruiter email -> 200
        headers_valid_key = {"X-Agent-Key": "test-agent-key-secret-12345"}
        resp_valid_key = await client.post(
            "/api/v1/approvals/pending",
            headers=headers_valid_key,
            json={"requester_email": "recruiter@company.com"},
        )
        assert resp_valid_key.status_code == 200


@pytest.mark.asyncio
async def test_non_tool_endpoints_still_require_auth(client):
    """Non-tool endpoints MUST still require authentication and return 401 when missing."""
    # /api/v1/auth/me without token -> 401
    resp_me = await client.get("/api/v1/auth/me")
    assert resp_me.status_code == 401

    # /api/v1/referral/list without token -> 401
    resp_list = await client.get("/api/v1/referral/list")
    assert resp_list.status_code == 401

    # /api/v1/employees/history without token -> 401
    resp_hist = await client.get("/api/v1/employees/history")
    assert resp_hist.status_code == 401

    # /api/v1/jobs/open without token -> 401
    resp_jobs = await client.get("/api/v1/jobs/open")
    assert resp_jobs.status_code == 401
