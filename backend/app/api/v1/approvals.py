"""
Recruiter approval workflow endpoints:
- GET /approvals/pending (lists candidates awaiting review)
- GET /approvals/{candidate_id} (retrieves full profile, matches, and identity mismatch alerts)
- POST /approvals/{candidate_id}/approve (sets Approved, advances status, notifies employee)
- POST /approvals/{candidate_id}/reject (sets Rejected, updates status, notifies employee)
Accessible to recruiters and hiring managers only (enforces role check on all calls).
"""

from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_auth_or_agent_user, get_tool_user
from app.services.approval_service import approval_service
from app.domain.models import (
    PendingApprovalItem,
    ApprovalDetailResponse,
    ApproveRejectRequest,
    ApprovalActionResponse,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _assert_recruiter_or_manager(user: dict[str, Any]) -> None:
    role = user.get("role", "")
    if role not in ("recruiter", "hiring_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Only recruiters and hiring managers can access approval operations. Your role is '{role}'.",
        )


class ToolApprovalActionRequest(BaseModel):
    candidate_id: str
    note: str | None = None
    requester_email: str | None = None


class ToolPendingRequest(BaseModel):
    requester_email: str | None = None


@router.get(
    "/pending",
    response_model=list[PendingApprovalItem],
    summary="Get pending referrals",
    description="Lists all candidate referrals currently awaiting recruiter review. Accessible via JWT or X-Agent-Key for recruiters.",
)
async def get_pending_approvals_get(
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> list[PendingApprovalItem]:
    _assert_recruiter_or_manager(current_user)
    return await approval_service.get_pending_approvals()


@router.post(
    "/pending",
    response_model=list[PendingApprovalItem],
    tags=["Agent Tools"],
    summary="Tool 4: Get Pending Approvals",
    description="Lists all candidate referrals currently awaiting recruiter review. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_pending_approvals_post(
    req: ToolPendingRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> list[PendingApprovalItem]:
    _assert_recruiter_or_manager(current_user)
    return await approval_service.get_pending_approvals()


@router.post(
    "/approve",
    response_model=ApprovalActionResponse,
    tags=["Agent Tools"],
    summary="Tool 5: Approve Referral",
    description="Approves a candidate referral in Zoho Recruit, updates status, and notifies referring employee. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def approve_referral_tool(
    req: ToolApprovalActionRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> ApprovalActionResponse:
    _assert_recruiter_or_manager(current_user)
    recruiter_email = current_user.get("email", "")
    res = await approval_service.approve_referral(
        candidate_id=req.candidate_id,
        note=req.note,
        recruiter_email=recruiter_email,
    )
    return ApprovalActionResponse(**res)


@router.post(
    "/reject",
    response_model=ApprovalActionResponse,
    tags=["Agent Tools"],
    summary="Tool 6: Reject Referral",
    description="Rejects a candidate referral in Zoho Recruit, records mandatory reason, and notifies referring employee. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def reject_referral_tool(
    req: ToolApprovalActionRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> ApprovalActionResponse:
    _assert_recruiter_or_manager(current_user)
    recruiter_email = current_user.get("email", "")
    res = await approval_service.reject_referral(
        candidate_id=req.candidate_id,
        note=req.note,
        recruiter_email=recruiter_email,
    )
    return ApprovalActionResponse(**res)


@router.get(
    "/{candidate_id}",
    response_model=ApprovalDetailResponse,
    summary="Get candidate approval details",
    description="Retrieves comprehensive review details for a candidate, including parsed profile, job match results, and identity mismatch flags.",
)
async def get_approval_detail(
    candidate_id: str,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ApprovalDetailResponse:
    _assert_recruiter_or_manager(current_user)
    return await approval_service.get_approval_detail(candidate_id)


@router.post(
    "/{candidate_id}/approve",
    response_model=ApprovalActionResponse,
    summary="Approve referral (REST Endpoint)",
    description="Approves a candidate referral in Zoho Recruit, logs audit note, and notifies referring employee via email.",
)
async def approve_referral(
    candidate_id: str,
    req: ApproveRejectRequest | None = None,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ApprovalActionResponse:
    _assert_recruiter_or_manager(current_user)
    note = req.note if req else None
    recruiter_email = current_user.get("email", "")

    res = await approval_service.approve_referral(
        candidate_id=candidate_id,
        note=note,
        recruiter_email=recruiter_email,
    )
    return ApprovalActionResponse(**res)


@router.post(
    "/{candidate_id}/reject",
    response_model=ApprovalActionResponse,
    summary="Reject referral (REST Endpoint)",
    description="Rejects a candidate referral in Zoho Recruit, records rejection note, and informs the referring employee.",
)
async def reject_referral(
    candidate_id: str,
    req: ApproveRejectRequest,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ApprovalActionResponse:
    _assert_recruiter_or_manager(current_user)
    recruiter_email = current_user.get("email", "")

    res = await approval_service.reject_referral(
        candidate_id=candidate_id,
        note=req.note,
        recruiter_email=recruiter_email,
    )
    return ApprovalActionResponse(**res)
