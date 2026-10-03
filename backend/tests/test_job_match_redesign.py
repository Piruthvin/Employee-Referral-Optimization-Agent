import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.config import get_settings
from app.services.job_match_service import job_match_service
from app.services.igentic_client import igentic_client
from app.services.referral_service import referral_service
from app.services.zoho_service import zoho_service
from app.services.zoho_field_mapper import zoho_field_mapper
from app.services.email_service import email_service
from app.services.resume_parser_service import resume_parser_service
from app.domain.resume_schema import ParsedResume
from app.domain.models import JobMatchResult


SAMPLE_OPEN_JOBS = [
    {
        "id": "242705000000424001",
        "Posting_Title": "Senior Python Developer",
        "Department": "Engineering",
        "Job_Description": "Looking for Senior Python Developer with FastAPI, Docker, and PostgreSQL experience.",
        "Skill_Set": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "Experience_in_Years": 4.0,
        "Job_Opening_Status": "Active",
    },
    {
        "id": "242705000000424002",
        "Posting_Title": "Cloud Solutions Architect",
        "Department": "Cloud & Infra",
        "Job_Description": "Seeking Cloud Architect with Azure, Kubernetes, and Terraform experience.",
        "Skill_Set": ["Azure", "Kubernetes", "Terraform"],
        "Experience_in_Years": 7.0,
        "Job_Opening_Status": "Active",
    },
]


def test_job_match_unmarshal_json_variants():
    """Verifies robust unmarshaling across pure JSON, code fences, prose, and termination markers."""
    # 1. Pure JSON
    pure = '{"candidate_id": "c1", "total_matches": 1, "matches": [{"job_id": "242705000000424001", "job_title": "Senior Python Developer", "match_percent": 90.0, "notes": "Great fit"}]}'
    res1 = job_match_service._unmarshal_json(pure)
    assert res1["candidate_id"] == "c1"

    # 2. Markdown fenced with ```json
    fenced_json = '```json\n{"candidate_id": "c2", "total_matches": 1, "matches": [{"job_id": "242705000000424001", "job_title": "Senior Python Developer", "match_percent": 88.0, "notes": "Strong skills"}]}\n```'
    res2 = job_match_service._unmarshal_json(fenced_json)
    assert res2["candidate_id"] == "c2"

    # 3. Markdown fenced with generic ```
    fenced_generic = '```\n{"candidate_id": "c3", "total_matches": 1, "matches": [{"job_id": "242705000000424001", "job_title": "Senior Python Developer", "match_percent": 85.0, "notes": "Solid"}]}\n```'
    res3 = job_match_service._unmarshal_json(fenced_generic)
    assert res3["candidate_id"] == "c3"

    # 4. Conversational prose with TERMINATE THE PROCESS
    prose_wrapped = (
        'Here is the ranked job match for the candidate:\n\n'
        '{"candidate_id": "c4", "total_matches": 1, "matches": [{"job_id": "242705000000424001", "job_title": "Senior Python Developer", "match_percent": 95.0, "notes": "Excellent candidate"}]}\n\n'
        'TERMINATE THE PROCESS'
    )
    res4 = job_match_service._unmarshal_json(prose_wrapped)
    assert res4["candidate_id"] == "c4"

    # 5. Raw list input
    raw_list = '[{"job_id": "242705000000424001", "job_title": "Senior Python Developer", "match_percent": 92.0, "notes": "Fit"}]'
    res5 = job_match_service._unmarshal_json(raw_list)
    assert isinstance(res5, list)
    assert res5[0]["job_id"] == "242705000000424001"

    # 6. Dict input directly
    dict_input = {"candidate_id": "c6", "matches": []}
    assert job_match_service._unmarshal_json(dict_input) == dict_input

    # 7. Unparseable garbage raises ValueError
    with pytest.raises(ValueError, match="Could not parse valid JSON"):
        job_match_service._unmarshal_json("Hello, this is just conversational text without any JSON structure.")


def test_deterministic_python_matcher_includes_notes_and_desc():
    """Verifies that rank_jobs_for_candidate populates job_description and notes."""
    skills = ["Python", "FastAPI", "Docker"]
    exp = 5.0
    ranked = job_match_service.rank_jobs_for_candidate(skills, exp, SAMPLE_OPEN_JOBS)
    assert len(ranked) == 2
    top = ranked[0]
    assert top["job_title"] == "Senior Python Developer"
    assert "FastAPI" in top["matched_skills"]
    assert "notes" in top
    assert "Matched on" in top["notes"]
    assert "job_description" in top
    assert "Looking for Senior Python Developer" in top["job_description"]


@pytest.mark.asyncio
async def test_rank_jobs_agent_success():
    """Verifies that agent match returns validated results with AI notes and matcher_used='agent'."""
    settings = get_settings()
    settings.job_match_mode = "auto"
    settings.igentic_executor_url = "https://mock.executor/api"
    settings.igentic_app_id = "test-app"

    agent_response = """
    {
      "candidate_id": "cand-123",
      "total_matches": 1,
      "matches": [
        {
          "job_id": "242705000000424001",
          "job_title": "Senior Python Developer",
          "job_description": "Custom role description",
          "department": "Engineering",
          "match_percent": 94.0,
          "matched_skills": ["Python", "FastAPI", "Docker"],
          "missing_skills": ["PostgreSQL"],
          "experience_fit": true,
          "notes": "Candidate has 5 years of Python/FastAPI experience directly aligning with backend requirements."
        }
      ]
    }
    TERMINATE THE PROCESS
    """
    with patch.object(igentic_client, "match_jobs", AsyncMock(return_value=agent_response)):
        ranked, matcher = await job_match_service.rank_jobs_for_candidate_agent_first(
            candidate_skills=["Python", "FastAPI"],
            candidate_exp_years=5.0,
            open_jobs=SAMPLE_OPEN_JOBS,
        )

        assert matcher == "agent"
        assert len(ranked) == 1
        assert ranked[0]["job_id"] == "242705000000424001"
        assert ranked[0]["match_percent"] == 94.0
        assert "directly aligning" in ranked[0]["notes"]


@pytest.mark.asyncio
async def test_rank_jobs_auto_fallback_on_agent_malformed_response():
    """
    CRITICAL: In JOB_MATCH_MODE=auto, when agent returns malformed output,
    it must NOT raise an unhandled exception or crash. It must log a warning
    and fall back to deterministic Python matcher with matcher_used='python_fallback'.
    """
    settings = get_settings()
    settings.job_match_mode = "auto"
    settings.igentic_executor_url = "https://mock.executor/api"
    settings.igentic_app_id = "test-app"

    malformed_response = "Sorry, I am unable to format the jobs right now due to a network glitch."

    with patch.object(igentic_client, "match_jobs", AsyncMock(return_value=malformed_response)):
        ranked, matcher = await job_match_service.rank_jobs_for_candidate_agent_first(
            candidate_skills=["Python", "FastAPI", "PostgreSQL"],
            candidate_exp_years=5.0,
            open_jobs=SAMPLE_OPEN_JOBS,
        )

        assert matcher == "python_fallback"
        assert len(ranked) > 0
        assert ranked[0]["job_title"] == "Senior Python Developer"
        assert "notes" in ranked[0]
        assert "Matched on" in ranked[0]["notes"]


@pytest.mark.asyncio
async def test_rank_jobs_auto_fallback_on_agent_exception():
    """
    CRITICAL: In JOB_MATCH_MODE=auto, when agent call throws a network/HTTP exception,
    it must NOT crash. It must fall back to deterministic Python.
    """
    settings = get_settings()
    settings.job_match_mode = "auto"
    settings.igentic_executor_url = "https://mock.executor/api"
    settings.igentic_app_id = "test-app"

    with patch.object(igentic_client, "match_jobs", AsyncMock(side_effect=RuntimeError("Connection reset by peer"))):
        ranked, matcher = await job_match_service.rank_jobs_for_candidate_agent_first(
            candidate_skills=["Azure", "Kubernetes"],
            candidate_exp_years=8.0,
            open_jobs=SAMPLE_OPEN_JOBS,
        )

        assert matcher == "python_fallback"
        assert len(ranked) > 0
        assert ranked[0]["job_title"] == "Cloud Solutions Architect"


@pytest.mark.asyncio
async def test_submit_referral_resilient_to_agent_failure_and_graph_401(client, employee_jwt):
    """
    CRITICAL END-TO-END FLOW:
    When a referral is submitted, if agent job matching fails AND Microsoft Graph
    sendMail returns 401 (e.g. Gmail UPN misconfiguration), candidate creation
    MUST STILL SUCCEED (200), saving candidate and attachment, returning fallback match,
    and reporting non-fatal warnings without crashing with 500.
    """
    settings = get_settings()
    settings.job_match_mode = "auto"
    settings.resume_parser_mode = "auto"
    settings.igentic_executor_url = "https://mock.executor/api"
    settings.igentic_app_id = "test-app"

    mock_parsed_resume = ParsedResume(
        full_name="Alex River",
        email="alex.river@example.com",
        phone="555-0199",
        current_job_title="Software Engineer",
        current_employer="Tech Corp",
        total_experience_years=4.0,
        skills=["Python", "FastAPI", "PostgreSQL"],
    )

    dummy_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 2\ntrailer<</Size 2>>\nstartxref\n40\n%%EOF"

    with patch.object(zoho_service, "search_candidate_by_email", AsyncMock(return_value=None)), \
         patch("app.services.resume_extract_service.resume_extract_service.validate_and_extract", AsyncMock(return_value=("Sample resume text " * 20, dummy_pdf))), \
         patch.object(resume_parser_service, "parse_resume", AsyncMock(return_value=(mock_parsed_resume, "python"))), \
         patch.object(zoho_service, "get_open_jobs", AsyncMock(return_value=SAMPLE_OPEN_JOBS)), \
         patch.object(igentic_client, "match_jobs", AsyncMock(side_effect=ValueError("Could not parse valid JSON"))), \
         patch.object(zoho_field_mapper, "get_candidate_fields_metadata", AsyncMock(return_value=[])), \
         patch.object(zoho_service, "create_candidate", AsyncMock(return_value="cand-rec-7777")), \
         patch.object(zoho_service, "upload_resume_attachment", AsyncMock(return_value=True)), \
         patch.object(zoho_service, "add_note", AsyncMock(return_value=True)), \
         patch.object(zoho_service, "associate_candidate_to_job", AsyncMock(return_value=True)), \
         patch.object(email_service, "send_email", AsyncMock(return_value=False)):

        resp = await client.post(
            "/api/v1/referral/submit",
            data={"candidate_name": "Alex River", "candidate_email": "alex.river@example.com"},
            files={"resume_file": ("Alex_River_Resume.pdf", dummy_pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {employee_jwt}"},
        )

        assert resp.status_code == 200
        result = resp.json()
        assert result["success"] is True
        assert result["candidate_id"] == "cand-rec-7777"
        assert result["best_match"] is not None
        assert result["best_match"]["job_title"] == "Senior Python Developer"
        assert "notes" in result["best_match"]
        assert "Matched on" in result["best_match"]["notes"]
        assert result["best_match"]["job_id"] == "242705000000424001"
