"""
Job openings and candidate matching endpoints:
- GET /jobs/open (lists active open job requisitions from Zoho Recruit)
- POST /jobs/match (Tool Endpoint: ranks open jobs against a candidate's profile)
"""

import logging
from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)

from app.core.dependencies import get_current_user, get_auth_or_agent_user, get_tool_user
from app.services.zoho_service import zoho_service
from app.services.job_match_service import job_match_service, normalize_skill
from app.domain.models import (
    JobOpeningsResponse,
    JobOpeningItem,
    JobMatchRequest,
    JobMatchResponse,
    JobMatchResult,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class ToolJobOpeningsRequest(BaseModel):
    requester_email: str | None = Field(default=None, description="Requester email for agent tool auth")


async def _build_open_jobs_response() -> JobOpeningsResponse:
    jobs = await zoho_service.get_open_jobs()
    items: list[JobOpeningItem] = []

    for j in jobs:
        req_skills = job_match_service.get_job_required_skills(j)
        req_exp = job_match_service.get_job_required_experience(j)
        title = j.get("Posting_Title") or j.get("Job_Title") or j.get("Job_Opening_Name") or "Job"
        desc = j.get("Job_Description") or j.get("Job_Summary") or ""

        items.append(
            JobOpeningItem(
                id=str(j.get("id")),
                title=title,
                department=j.get("Department"),
                required_skills=req_skills,
                required_experience=req_exp,
                status=j.get("Job_Opening_Status") or "Active",
                job_description=desc,
            )
        )

    return JobOpeningsResponse(total=len(items), data=items)


@router.get(
    "/open",
    response_model=JobOpeningsResponse,
    summary="List active job openings",
    description="Retrieves active job openings from Zoho Recruit with required skills and experience. Callable with no auth, JWT, or X-Agent-Key.",
)
async def list_open_jobs(
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> JobOpeningsResponse:
    return await _build_open_jobs_response()


@router.post(
    "/open",
    response_model=JobOpeningsResponse,
    tags=["Agent Tools"],
    summary="Tool 14: List Open Job Openings",
    description="Retrieves active job openings from Zoho Recruit with required skills, experience, and department. POST tool variant for iGentic agents. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def list_open_jobs_post(
    req: ToolJobOpeningsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> JobOpeningsResponse:
    return await _build_open_jobs_response()


@router.post(
    "/match",
    response_model=JobMatchResponse,
    tags=["Agent Tools"],
    summary="Tool 2: Match Jobs for Candidate",
    description="Calculates AI-agent-driven match scores between candidate skills/experience and all open job openings with deterministic Python fallback. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def match_jobs_for_candidate(
    req: JobMatchRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> JobMatchResponse:
    cand: dict[str, Any] | None = None
    if req.candidate_id:
        cand = await zoho_service.get_candidate_by_id(req.candidate_id)
    elif req.candidate_email:
        cand = await zoho_service.search_candidate_by_email(req.candidate_email)

    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found in Zoho Recruit.",
        )

    # Extract skills
    skills_raw = cand.get("Skill_Set") or cand.get("Skills") or []
    cand_skills: list[str] = []
    if isinstance(skills_raw, list):
        cand_skills = [str(s) for s in skills_raw if str(s).strip()]
    elif isinstance(skills_raw, str):
        cand_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    # Extract experience
    exp_val = cand.get("Experience_in_Years") or cand.get("Experience") or 0.0
    try:
        cand_exp = float(exp_val)
    except (ValueError, TypeError):
        cand_exp = 0.0

    open_jobs = await zoho_service.get_open_jobs()
    try:
        ranked, matcher_used = await job_match_service.rank_jobs_for_candidate_agent_first(
            candidate_skills=cand_skills,
            candidate_exp_years=cand_exp,
            open_jobs=open_jobs,
            candidate_profile={
                "candidate_id": str(cand.get("id")),
                "full_name": f"{cand.get('First_Name', '')} {cand.get('Last_Name', '')}".strip(),
                "email": cand.get("Email"),
                "skills": cand_skills,
                "total_experience_years": cand_exp,
                "current_job_title": cand.get("Current_Job_Title"),
            },
            candidate_id=str(cand.get("id")),
            min_match=req.min_match,
        )
    except Exception as e:
        logger.warning("Agent job matching failed: %s. Falling back to deterministic Python matcher.", e)
        ranked = job_match_service.rank_jobs_for_candidate(
            candidate_skills=cand_skills,
            candidate_exp_years=cand_exp,
            open_jobs=open_jobs,
            min_match=req.min_match,
        )
        matcher_used = "python_fallback"

    matches: list[JobMatchResult] = [
        JobMatchResult(
            job_id=r["job_id"],
            job_title=r["job_title"],
            match_percent=r["match_percent"],
            matched_skills=r["matched_skills"],
            missing_skills=r["missing_skills"],
            experience_fit=r["experience_fit"],
            department=r.get("department"),
            job_description=r.get("job_description"),
            notes=r.get("notes"),
        )
        for r in ranked
    ]

    return JobMatchResponse(
        candidate_id=str(cand.get("id")),
        total_matches=len(matches),
        matches=matches,
    )
