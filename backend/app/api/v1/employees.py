"""
Employee profile and referral stats endpoints:
- GET /employees/points (Tool Endpoint: calculates derived points purely from Zoho Candidate records)
- GET /employees/history (lists all referrals submitted by this employee)
"""

from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_auth_or_agent_user
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
    summary="Get employee referral points (Tool Endpoint)",
    description="Calculates earned referral points derived purely from Zoho Recruit Candidate records without Contacts module. Accessible via JWT or X-Agent-Key.",
)
@router.post(
    "/points",
    response_model=EmployeePointsResponse,
    summary="Get employee referral points (POST Tool Endpoint)",
    description="Calculates earned referral points derived purely from Zoho Recruit Candidate records. POST variant for iGentic tools.",
)
async def get_employee_points(
    req: ToolEmployeePointsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> EmployeePointsResponse:
    user_email = current_user.get("email", "").lower()
    res = await analytics_service.get_employee_points(user_email)
    return EmployeePointsResponse(**res)


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
        fn = c.get("First_Name") or ""
        ln = c.get("Last_Name") or ""
        name = f"{fn} {ln}".strip() or "Candidate"

        score = c.get("Referral_Score")
        items.append(
            ReferralListItem(
                candidate_id=str(c.get("id")),
                name=name,
                email=c.get("Email") or "",
                referred_by=user_email,
                referred_date=c.get("Referred_Date"),
                approval_status=c.get("Referral_Approval_Status") or "Pending",
                candidate_status=c.get("Candidate_Status") or "New",
                referral_score=float(score) if score is not None else None,
                best_match_title=c.get("Current_Job_Title"),
            )
        )

    return EmployeeHistoryResponse(
        email=user_email,
        total=len(items),
        referrals=items,
    )
