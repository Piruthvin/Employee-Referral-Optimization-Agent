"""
Interview scheduling endpoints:
- POST /interview/schedule (Tool Endpoint: creates Teams meeting, sends calendar invites, updates status)
Enforces strict approval gate: raises 409 Conflict if candidate is not in Approved state.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_auth_or_agent_user, get_tool_user
from app.services.interview_service import interview_service
from app.domain.models import InterviewScheduleRequest, InterviewScheduleResponse

router = APIRouter(prefix="/interview", tags=["Interviews"])


@router.post(
    "/schedule",
    response_model=InterviewScheduleResponse,
    tags=["Agent Tools"],
    summary="Tool 7: Schedule Interview",
    description="Creates a Microsoft Teams online meeting and calendar invites for approved candidates. Fails with 409 if referral is not in Approved status. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def schedule_interview(
    req: InterviewScheduleRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> InterviewScheduleResponse:
    user_role = current_user.get("role", "")
    if user_role not in ("recruiter", "hiring_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only recruiters and hiring managers can schedule interviews. Current role: '{user_role}'.",
        )

    recruiter_email = current_user.get("email", "")

    interviewer_list = list(req.interviewer_emails or [])
    if req.interviewer_email and req.interviewer_email not in interviewer_list:
        interviewer_list.append(req.interviewer_email)

    result = await interview_service.schedule_interview(
        candidate_id=req.candidate_id,
        start_time_iso=req.start_time,
        duration_minutes=req.duration_minutes,
        recruiter_email=recruiter_email,
        interviewer_emails=interviewer_list,
        notes=req.notes or req.subject,
    )
    return InterviewScheduleResponse(**result)
