"""
Interview scheduling endpoints:
- POST /interview/schedule (Tool Endpoint: creates Teams meeting, sends calendar invites, updates status)
Enforces strict approval gate: raises 409 Conflict if candidate is not in Approved state.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_auth_or_agent_user
from app.services.interview_service import interview_service
from app.domain.models import InterviewScheduleRequest, InterviewScheduleResponse

router = APIRouter(prefix="/interview", tags=["Interviews"])


@router.post(
    "/schedule",
    response_model=InterviewScheduleResponse,
    summary="Schedule candidate interview (Tool Endpoint)",
    description="Creates a Microsoft Teams online meeting and generates .ics calendar invites for approved candidates. Blocked with 409 if referral is pending or rejected. Accessible to recruiters via JWT or X-Agent-Key.",
)
async def schedule_interview(
    req: InterviewScheduleRequest,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> InterviewScheduleResponse:
    user_role = current_user.get("role", "")
    if user_role not in ("recruiter", "hiring_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only recruiters and hiring managers can schedule interviews. Current role: '{user_role}'.",
        )

    recruiter_email = current_user.get("email", "")

    result = await interview_service.schedule_interview(
        candidate_id=req.candidate_id,
        start_time_iso=req.start_time,
        duration_minutes=req.duration_minutes,
        recruiter_email=recruiter_email,
        interviewer_emails=req.interviewer_emails,
        notes=req.notes,
    )
    return InterviewScheduleResponse(**result)
