"""
Tests for referral intake lifecycle, recruiter approvals, interview scheduling, and role isolation:
- Duplicate 409 conflict detection
- Source and Referred_By metadata verification
- Compensating rollback on attachment failure
- Job match ranking and threshold-based association
- Recruiter notifications
- Approval state transitions (Approve / Reject)
- Approval gate blocking interview scheduling (409 Conflict)
- Employee tenant isolation (cannot access others' referrals)
- Dual auth: Agent-key header role re-derivation
"""

import io
import pytest
from unittest.mock import patch, AsyncMock
from app.services.zoho_service import zoho_service
from app.services.email_service import email_service
from app.services.zoho_users_service import zoho_users_service


@pytest.mark.asyncio
async def test_duplicate_referral_conflict_409(client, employee_jwt, recruiter_jwt):
    """Submitting an already-existing candidate email returns 409 with role-based details."""
    existing_cand = {
        "id": "5910001",
        "Email": "duplicate.candidate@example.com",
        "Referred_By": "prior.referrer@company.com",
    }

    dummy_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 2\ntrailer<</Size 2>>\nstartxref\n40\n%%EOF"

    with patch.object(zoho_service, "search_candidate_by_email", AsyncMock(return_value=existing_cand)), \
         patch("app.services.resume_extract_service.resume_extract_service.validate_and_extract", AsyncMock(return_value=("Sample resume text " * 20, dummy_pdf))):

        # 1. As Employee: generic conflict message
        emp_resp = await client.post(
            "/api/v1/referral/submit",
            data={"candidate_name": "Duplicate Candidate", "candidate_email": "duplicate.candidate@example.com"},
            files={"resume_file": ("resume.pdf", dummy_pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {employee_jwt}"},
        )
        assert emp_resp.status_code == 409
        assert "already been referred or already exists" in emp_resp.json()["detail"]
        assert "prior.referrer" not in emp_resp.json()["detail"]

        # 2. As Recruiter: specific conflict message with existing ID and referrer
        rec_resp = await client.post(
            "/api/v1/referral/submit",
            data={"candidate_name": "Duplicate Candidate", "candidate_email": "duplicate.candidate@example.com"},
            files={"resume_file": ("resume.pdf", dummy_pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {recruiter_jwt}"},
        )
        assert rec_resp.status_code == 409
        assert "5910001" in rec_resp.json()["detail"]
        assert "prior.referrer@company.com" in rec_resp.json()["detail"]


@pytest.mark.asyncio
async def test_attachment_upload_failure_triggers_compensating_rollback(client, employee_jwt):
    """If resume attachment fails, the newly created Zoho candidate must be deleted immediately."""
    dummy_pdf = b"%PDF-1.4" + (b"0" * 300)

    with patch.object(zoho_service, "search_candidate_by_email", AsyncMock(return_value=None)), \
         patch("app.services.resume_extract_service.resume_extract_service.validate_and_extract", AsyncMock(return_value=("Candidate text " * 30, dummy_pdf))), \
         patch.object(zoho_service, "create_candidate", AsyncMock(return_value="999001")), \
         patch.object(zoho_service, "upload_resume_attachment", AsyncMock(side_effect=RuntimeError("Attachment upload failed"))), \
         patch.object(zoho_service, "delete_candidate", AsyncMock(return_value=True)) as mock_delete:

        resp = await client.post(
            "/api/v1/referral/submit",
            data={"candidate_name": "Rollback Test", "candidate_email": "rollback@test.com"},
            files={"resume_file": ("resume.pdf", dummy_pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {employee_jwt}"},
        )

        assert resp.status_code == 500
        assert "Referral creation was rolled back" in resp.json()["detail"]
        mock_delete.assert_called_once_with("999001")


@pytest.mark.asyncio
async def test_referral_submission_success_pipeline(client, employee_jwt, mock_zoho_active_users):
    """End-to-end referral creation: candidate created, attached, noted, associated, and recruiter notified."""
    dummy_pdf = b"%PDF-1.4" + (b"0" * 300)
    matching_resume_text = (
        "Alex Smith\n"
        "Email: alex.smith@example.com\n"
        "SUMMARY: Experienced Python FastAPI Docker developer.\n"
        "SKILLS: Python, FastAPI, Docker, Kubernetes, PostgreSQL.\n"
        "EXPERIENCE: Senior Developer at Tech Corp 2020 - 2024.\n"
    )
    mock_jobs = [
        {
            "id": "JOB_101",
            "Posting_Title": "Senior Python Developer",
            "Skill_Set": "Python, FastAPI, Docker",
            "Experience": 3.0,
        }
    ]

    with patch.object(zoho_service, "search_candidate_by_email", AsyncMock(return_value=None)), \
         patch("app.services.resume_extract_service.resume_extract_service.validate_and_extract", AsyncMock(return_value=(matching_resume_text, dummy_pdf))), \
         patch.object(zoho_service, "get_open_jobs", AsyncMock(return_value=mock_jobs)), \
         patch.object(zoho_service, "create_candidate", AsyncMock(return_value="CAND_555")), \
         patch.object(zoho_service, "upload_resume_attachment", AsyncMock(return_value="ATT_111")), \
         patch.object(zoho_service, "add_note", AsyncMock(return_value=True)) as mock_note, \
         patch.object(zoho_service, "associate_candidate_to_job", AsyncMock(return_value=True)) as mock_assoc, \
         patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(email_service, "send_email", AsyncMock(return_value=True)) as mock_email:

        resp = await client.post(
            "/api/v1/referral/submit",
            data={"candidate_name": "Alex Smith", "candidate_email": "alex.smith@example.com"},
            files={"resume_file": ("resume.pdf", dummy_pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {employee_jwt}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["candidate_id"] == "CAND_555"
        assert data["status"] == "Pending recruiter approval"

        # Verify Note and Association were executed
        mock_note.assert_called_once()
        mock_assoc.assert_called_once_with("CAND_555", "JOB_101")
        mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_approve_reject_flow_and_role_enforcement(client, employee_jwt, recruiter_jwt):
    """Recruiters can approve and reject referrals; employees receive 403 Forbidden."""
    mock_candidate = {
        "id": "CAND_1",
        "First_Name": "Sam",
        "Last_Name": "Altman",
        "Email": "sam@test.com",
        "Referred_By": "employee@company.com",
        "Referral_Approval_Status": "Pending",
    }

    with patch.object(zoho_service, "get_candidate_by_id", AsyncMock(return_value=mock_candidate)), \
         patch.object(zoho_service, "update_candidate", AsyncMock(return_value=True)), \
         patch.object(zoho_service, "add_note", AsyncMock(return_value=True)), \
         patch.object(email_service, "send_email", AsyncMock(return_value=True)):

        # Employee attempt must be blocked
        emp_resp = await client.post(
            "/api/v1/approvals/CAND_1/approve",
            json={"note": "Employee cannot approve"},
            headers={"Authorization": f"Bearer {employee_jwt}"},
        )
        assert emp_resp.status_code == 403

        # Recruiter approve succeeds
        rec_resp = await client.post(
            "/api/v1/approvals/CAND_1/approve",
            json={"note": "Great fit for the platform."},
            headers={"Authorization": f"Bearer {recruiter_jwt}"},
        )
        assert rec_resp.status_code == 200
        assert rec_resp.json()["approval_status"] == "Approved"

        # Recruiter reject succeeds
        rej_resp = await client.post(
            "/api/v1/approvals/CAND_1/reject",
            json={"note": "Position closed."},
            headers={"Authorization": f"Bearer {recruiter_jwt}"},
        )
        assert rej_resp.status_code == 200
        assert rej_resp.json()["approval_status"] == "Rejected"


@pytest.mark.asyncio
async def test_interview_blocked_before_approval(client, recruiter_jwt):
    """Interview scheduling is blocked with 409 Conflict until referral is approved."""
    pending_cand = {
        "id": "CAND_PENDING",
        "First_Name": "Pending",
        "Last_Name": "Candidate",
        "Email": "pending@test.com",
        "Referral_Approval_Status": "Pending",
    }
    approved_cand = {
        "id": "CAND_APPROVED",
        "First_Name": "Approved",
        "Last_Name": "Candidate",
        "Email": "approved@test.com",
        "Referral_Approval_Status": "Approved",
    }

    # 1. Attempt schedule on Pending -> 409
    with patch.object(zoho_service, "get_candidate_by_id", AsyncMock(return_value=pending_cand)):
        resp_pend = await client.post(
            "/api/v1/interview/schedule",
            json={"candidate_id": "CAND_PENDING", "start_time": "2026-10-15T10:00:00Z", "duration_minutes": 60},
            headers={"Authorization": f"Bearer {recruiter_jwt}"},
        )
        assert resp_pend.status_code == 409
        assert "Referral not approved" in resp_pend.json()["detail"]

    # 2. Attempt schedule on Approved -> 200
    with patch.object(zoho_service, "get_candidate_by_id", AsyncMock(return_value=approved_cand)), \
         patch.object(zoho_service, "update_candidate", AsyncMock(return_value=True)), \
         patch.object(zoho_service, "add_note", AsyncMock(return_value=True)), \
         patch.object(email_service, "send_email", AsyncMock(return_value=True)):

        resp_app = await client.post(
            "/api/v1/interview/schedule",
            json={"candidate_id": "CAND_APPROVED", "start_time": "2026-10-15T10:00:00Z", "duration_minutes": 60},
            headers={"Authorization": f"Bearer {recruiter_jwt}"},
        )
        assert resp_app.status_code == 200
        data = resp_app.json()
        assert data["success"] is True
        assert "teams.microsoft.com" in data["meeting_url"]


@pytest.mark.asyncio
async def test_employee_cannot_access_others_referrals(client, employee_jwt):
    """Employees are strictly restricted from inspecting referrals submitted by other users."""
    other_cand = {
        "id": "CAND_OTHER",
        "Email": "other@candidate.com",
        "Referred_By": "different.employee@company.com",
        "Referral_Approval_Status": "Pending",
    }

    with patch.object(zoho_service, "get_candidate_by_id", AsyncMock(return_value=other_cand)):
        resp = await client.get("/api/v1/referral/CAND_OTHER", headers={"Authorization": f"Bearer {employee_jwt}"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_key_auth_re_derives_role(client, mock_zoho_active_users):
    """iGentic tool calls with X-Agent-Key header re-derive user role from Zoho Users."""
    mock_candidates = [
        {
            "id": "CAND_77",
            "First_Name": "Agent",
            "Last_Name": "Check",
            "Email": "agent.check@test.com",
            "Referred_By": "employee@company.com",
            "Referral_Approval_Status": "Pending",
            "Source": "Employee Referral",
        }
    ]

    with patch.object(zoho_users_service, "get_active_users", AsyncMock(return_value=mock_zoho_active_users)), \
         patch.object(zoho_service, "get_all_candidates_cached", AsyncMock(return_value=mock_candidates)):

        # 1. With recruiter email -> allowed to view pending approvals
        headers_rec = {"X-Agent-Key": "test-agent-key-secret-12345"}
        resp_rec = await client.get("/api/v1/approvals/pending?requester_email=recruiter@company.com", headers=headers_rec)
        assert resp_rec.status_code == 200

        # 2. With employee email -> blocked from pending approvals (403)
        resp_emp = await client.get("/api/v1/approvals/pending?requester_email=employee@company.com", headers=headers_rec)
        assert resp_emp.status_code == 403

        # 3. With invalid X-Agent-Key -> 401
        headers_invalid = {"X-Agent-Key": "wrong-agent-key"}
        resp_inv = await client.get("/api/v1/approvals/pending?requester_email=recruiter@company.com", headers=headers_invalid)
        assert resp_inv.status_code == 401


@pytest.mark.asyncio
async def test_top_candidates_matching_and_helpful_fallback(client, recruiter_jwt):
    """Test get_top_candidates_by_role token matching and available_jobs recommendations."""
    from app.services.analytics_service import analytics_service

    mock_candidates = [
        {
            "id": "CAND_101",
            "First_Name": "Priya",
            "Last_Name": "Sharma",
            "Email": "priya@example.com",
            "Current_Job_Title": None,
            "Skill_Set": "Python, FastAPI, Docker, PostgreSQL, REST APIs",
            "Experience_in_Years": 5,
            "Referral_Approval_Status": "Approved",
            "Referral_Score": 0.0,
        },
        {
            "id": "CAND_102",
            "First_Name": "Bob",
            "Last_Name": "Jones",
            "Email": "bob@example.com",
            "Current_Job_Title": "Junior Frontend Developer",
            "Skill_Set": "JavaScript, React, CSS",
            "Experience_in_Years": 2,
            "Referral_Approval_Status": "Pending",
            "Referral_Score": 0.0,
        }
    ]
    mock_jobs = [
        {
            "id": "JOB_999",
            "Posting_Title": "Software Engineer",
            "Job_Opening_Status": "In-progress",
        }
    ]

    with patch.object(zoho_service, "get_all_candidates_cached", AsyncMock(return_value=mock_candidates)), \
         patch.object(zoho_service, "get_open_jobs", AsyncMock(return_value=mock_jobs)):

        # 1. Query for "Senior Python Engineer" matches Priya (Python + FastAPI + experience)
        res_python = await analytics_service.get_top_candidates_by_role("Senior Python Engineer")
        assert len(res_python.candidates) >= 1
        assert res_python.candidates[0]["name"] == "Priya Sharma"
        assert res_python.candidates[0]["referral_score"] >= 50
        assert "Software Engineer" in res_python.available_jobs

        # 2. Query for non-existent role "Nurse" returns empty candidates with available_jobs and actionable message
        res_nurse = await analytics_service.get_top_candidates_by_role("Nurse")
        assert len(res_nurse.candidates) == 0
        assert res_nurse.total_matching == 0
        assert "Software Engineer" in res_nurse.available_jobs
        assert "Software Engineer" in res_nurse.message
        assert "No candidate referrals currently match 'Nurse'" in res_nurse.message
