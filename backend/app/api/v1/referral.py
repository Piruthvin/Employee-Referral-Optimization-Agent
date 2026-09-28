"""
Referral management endpoints:
- POST /referral/submit (multipart form with exactly 3 fields: candidate_name, candidate_email, resume_file)
- POST /referral/status & GET /referral/{candidate_id} (dual JWT / agent-key auth with role isolation)
- GET /referral/list (own referrals for employee, all referrals for recruiters)
- GET /referral/{candidate_id}/resume (stream resume directly from Zoho attachments)
"""

import io
import logging
from typing import Any
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user, get_auth_or_agent_user
from app.services.referral_service import referral_service
from app.services.zoho_service import zoho_service
from app.domain.models import (
    ReferralSubmitResponse,
    ReferralStatusRequest,
    ReferralStatusResponse,
    ReferralListResponse,
    ReferralListItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/referral", tags=["Referrals"])


@router.post(
    "/submit",
    response_model=ReferralSubmitResponse,
    summary="Submit candidate referral",
    description="Submits a new candidate referral. Requires exactly candidate name, candidate email, and resume file (PDF or DOCX, max 5MB).",
)
async def submit_referral(
    candidate_name: str = Form(..., description="Full legal name of candidate"),
    candidate_email: str = Form(..., description="Primary email address of candidate"),
    resume_file: UploadFile = File(..., description="Resume file in PDF or DOCX format (max 5MB)"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ReferralSubmitResponse:
    """Intake endpoint for employee referral submissions."""
    result = await referral_service.submit_referral(
        candidate_name=candidate_name.strip(),
        candidate_email=candidate_email.strip().lower(),
        resume_file=resume_file,
        current_user=current_user,
    )
    return ReferralSubmitResponse(**result)


@router.post(
    "/status",
    response_model=ReferralStatusResponse,
    summary="Get referral status (Tool Endpoint)",
    description="Retrieves the referral approval status, candidate lifecycle stage, and audit notes. Accessible via JWT or X-Agent-Key.",
)
async def get_referral_status_post(
    req: ReferralStatusRequest,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ReferralStatusResponse:
    user_email = current_user.get("email", "").lower()
    user_role = current_user.get("role", "employee")

    cand: dict[str, Any] | None = None
    if req.candidate_id:
        cand = await zoho_service.get_candidate_by_id(req.candidate_id)
    elif req.candidate_email:
        cand = await zoho_service.search_candidate_by_email(req.candidate_email)

    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate referral not found.",
        )

    # Enforce role boundary: employees can only inspect their own referrals
    referred_by = (cand.get("Referred_By") or "").strip().lower()
    if user_role == "employee" and referred_by != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are only permitted to view status for referrals submitted by your email.",
        )

    cand_id = str(cand.get("id"))
    notes = await zoho_service.get_candidate_notes(cand_id)

    first_name = cand.get("First_Name") or ""
    last_name = cand.get("Last_Name") or ""
    name = f"{first_name} {last_name}".strip() or "Candidate"

    return ReferralStatusResponse(
        candidate_id=cand_id,
        name=name,
        email=cand.get("Email") or "",
        referred_by=referred_by,
        referred_date=cand.get("Referred_Date"),
        approval_status=cand.get("Referral_Approval_Status") or "Pending",
        candidate_status=cand.get("Candidate_Status") or "New",
        referral_score=float(cand.get("Referral_Score")) if cand.get("Referral_Score") is not None else None,
        best_match=None,
        notes=notes,
    )


@router.get(
    "/{candidate_id}",
    response_model=ReferralStatusResponse,
    summary="Get single referral details",
    description="Retrieves candidate referral record by Zoho record ID.",
)
async def get_referral_by_id(
    candidate_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ReferralStatusResponse:
    user_email = current_user.get("email", "").lower()
    user_role = current_user.get("role", "employee")

    cand = await zoho_service.get_candidate_by_id(candidate_id)
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    referred_by = (cand.get("Referred_By") or "").strip().lower()
    if user_role == "employee" and referred_by != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this referral record.",
        )

    notes = await zoho_service.get_candidate_notes(candidate_id)
    first_name = cand.get("First_Name") or ""
    last_name = cand.get("Last_Name") or ""
    name = f"{first_name} {last_name}".strip() or "Candidate"

    return ReferralStatusResponse(
        candidate_id=candidate_id,
        name=name,
        email=cand.get("Email") or "",
        referred_by=referred_by,
        referred_date=cand.get("Referred_Date"),
        approval_status=cand.get("Referral_Approval_Status") or "Pending",
        candidate_status=cand.get("Candidate_Status") or "New",
        referral_score=float(cand.get("Referral_Score")) if cand.get("Referral_Score") is not None else None,
        best_match=None,
        notes=notes,
    )


@router.get(
    "/list",
    response_model=ReferralListResponse,
    summary="List candidate referrals",
    description="Returns referrals. Employees see only their own submissions; recruiters/managers see all.",
)
async def list_referrals(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ReferralListResponse:
    user_email = current_user.get("email", "").lower()
    user_role = current_user.get("role", "employee")

    items: list[ReferralListItem] = []

    if user_role == "employee":
        candidates = await zoho_service.get_candidates_by_referrer(user_email)
    else:
        candidates = await zoho_service.get_all_candidates_cached()

    for c in candidates:
        referred_by = c.get("Referred_By") or ""
        source = (c.get("Source") or "").lower()
        if not (referred_by or "referral" in source):
            continue

        fn = c.get("First_Name") or ""
        ln = c.get("Last_Name") or ""
        name = f"{fn} {ln}".strip() or "Candidate"

        score = c.get("Referral_Score")
        items.append(
            ReferralListItem(
                candidate_id=str(c.get("id")),
                name=name,
                email=c.get("Email") or "",
                referred_by=referred_by,
                referred_date=c.get("Referred_Date"),
                approval_status=c.get("Referral_Approval_Status") or "Pending",
                candidate_status=c.get("Candidate_Status") or "New",
                referral_score=float(score) if score is not None else None,
                best_match_title=c.get("Current_Job_Title"),
            )
        )

    return ReferralListResponse(total=len(items), data=items)


@router.get(
    "/{candidate_id}/resume",
    summary="Download candidate resume",
    description="Streams resume attachment from Zoho Recruit. Accessible to recruiters or the referring employee.",
)
async def download_resume(
    candidate_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    user_email = current_user.get("email", "").lower()
    user_role = current_user.get("role", "employee")

    cand = await zoho_service.get_candidate_by_id(candidate_id)
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    referred_by = (cand.get("Referred_By") or "").strip().lower()
    if user_role == "employee" and referred_by != user_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this resume.")

    attachments = await zoho_service.get_candidate_attachments(candidate_id)
    if not attachments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No resume attachment found in Zoho.")

    # Select latest attachment
    target_att = attachments[0]
    attachment_id = str(target_att.get("id"))
    filename = target_att.get("File_Name") or "resume.pdf"

    file_bytes, content_type = await zoho_service.download_attachment(candidate_id, attachment_id)

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
