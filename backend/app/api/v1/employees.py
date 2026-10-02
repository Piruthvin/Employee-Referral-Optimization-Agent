"""
Employee profile and referral stats endpoints:
- GET /employees/points (Tool Endpoint: calculates derived points purely from Zoho Candidate records)
- GET /employees/history (lists all referrals submitted by this employee)
"""

from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_auth_or_agent_user, get_tool_user
from app.services.analytics_service import analytics_service
from app.services.zoho_service import zoho_service
from app.domain.models import (
    EmployeePointsResponse,
    EmployeeHistoryResponse,
    ReferralListItem,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


class ToolEmployeePointsRequest(BaseModel):
    requester_email: str | None = None


@router.get(
    "/points",
    response_model=EmployeePointsResponse,
    summary="Get employee referral points",
    description="Calculates earned referral points derived purely from Zoho Recruit Candidate records without Contacts module. Accessible via JWT.",
)
async def get_employee_points_get(
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> EmployeePointsResponse:
    user_email = current_user.get("email", "").lower()
    res = await analytics_service.get_employee_points(user_email)
    return EmployeePointsResponse(**res)


@router.post(
    "/points",
    response_model=EmployeePointsResponse,
    tags=["Agent Tools"],
    summary="Tool 3: Get Employee Points",
    description="Calculates earned referral points derived purely from Zoho Recruit Candidate records. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_employee_points_post(
    req: ToolEmployeePointsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> EmployeePointsResponse:
    user_email = current_user.get("email", "").lower()
    if not user_email:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester_email is required when calling without session token.",
        )
    res = await analytics_service.get_employee_points(user_email)
    return EmployeePointsResponse(**res)


from app.api.v1.referral import extract_referred_by, extract_referred_date


@router.get(
    "/history",
    response_model=EmployeeHistoryResponse,
    summary="Get employee referral history",
    description="Retrieves chronological submission history and status updates for the authenticated employee's referrals.",
)
async def get_employee_history(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeHistoryResponse:
    user_email = current_user.get("email", "").lower()
    candidates = await zoho_service.get_candidates_by_referrer(user_email)

    items: list[ReferralListItem] = []
    for c in candidates:
        cand_id = str(c.get("id") or "")
        if not cand_id:
            continue

        fn = str(c.get("First_Name") or "").strip()
        ln = str(c.get("Last_Name") or "").strip()
        name = f"{fn} {ln}".strip() or str(c.get("Candidate_Name") or "Candidate").strip()

        score_val = c.get("Referral_Score")
        try:
            score = float(score_val) if score_val is not None else 85.0
        except (ValueError, TypeError):
            score = 85.0

        app_status = str(c.get("Referral_Approval_Status") or "").strip()
        cand_status = str(c.get("Candidate_Status") or "").strip()
        if not app_status:
            if cand_status.lower() in ("in-review", "approved", "interview scheduled"):
                app_status = "Approved"
            elif cand_status.lower() in ("rejected",):
                app_status = "Rejected"
            else:
                app_status = "Pending"

        job_title = str(c.get("Current_Job_Title") or "General Intake").strip()
        ref_date = extract_referred_date(c)

        items.append(
            ReferralListItem(
                candidate_id=cand_id,
                name=name,
                full_name=name,
                email=str(c.get("Email") or c.get("Secondary_Email") or "").strip(),
                referred_by=extract_referred_by(c) or user_email,
                referred_date=ref_date,
                approval_status=app_status,
                candidate_status=cand_status or "New",
                referral_score=score,
                best_match={
                    "job_id": None,
                    "job_title": job_title,
                    "match_percent": score,
                },
                best_match_title=job_title,
            )
        )

    return EmployeeHistoryResponse(
        email=user_email,
        total=len(items),
        referrals=items,
    )

