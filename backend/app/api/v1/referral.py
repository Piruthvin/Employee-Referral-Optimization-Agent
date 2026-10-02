"""
Referral management endpoints:
- POST /referral/submit (multipart form with exactly 3 fields: candidate_name, candidate_email, resume_file)
- POST /referral/status & GET /referral/{candidate_id} (dual JWT / agent-key auth with role isolation)
- GET /referral/list (own referrals for employee, all referrals for recruiters)
- GET /referral/{candidate_id}/resume (stream resume directly from Zoho attachments)
"""

import io
import re
import logging
from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user, get_auth_or_agent_user, get_tool_user
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


def extract_referred_by(cand: dict[str, Any]) -> str:
    """Extracts referring employee email safely from record fields or Additional_Info."""
    # 1. Direct Referred_By field
    ref = cand.get("Referred_By")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()

    # 2. Referred_by_Employee__s or Internal_Employee__s (dict or str)
    for k in ("Referred_by_Employee__s", "Internal_Employee__s"):
        val = cand.get(k)
        if isinstance(val, dict):
            name_or_email = val.get("email") or val.get("name") or ""
            if name_or_email:
                return str(name_or_email).strip()
        elif isinstance(val, str) and val.strip():
            return val.strip()

    # 3. Additional_Info tag [Referred By: ...]
    add_info = str(cand.get("Additional_Info") or "")
    m = re.search(r"\[Referred By:\s*([^\]\r\n]+)\]", add_info, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 4. Source containing email
    source = str(cand.get("Source") or "").strip()
    if "@" in source:
        return source

    return ""


def extract_referred_date(cand: dict[str, Any]) -> str:
    """Extracts ISO date safely from Referred_Date or Created_Time, defaulting to today."""
    d = cand.get("Referred_Date")
    if isinstance(d, str) and d.strip():
        return d.strip()[:10]
    created = cand.get("Created_Time") or cand.get("created_time")
    if isinstance(created, str) and len(created) >= 10:
        return created[:10]
    return date.today().isoformat()


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
    tags=["Agent Tools"],
    summary="Tool 1: Get Referral Status",
    description="Retrieves the referral approval status, candidate lifecycle stage, and audit notes. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_referral_status_post(
    req: ReferralStatusRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> ReferralStatusResponse:
    user_email = current_user.get("email", "").lower()
    user_role = current_user.get("role", "unauthenticated")

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

    cand_id = str(cand.get("id"))
    # Enforce role boundary: recruiters/managers can view any candidate;
    # employees can only inspect their own referrals;
    # unauthenticated callers without valid identity cannot inspect candidates.
    referred_by = extract_referred_by(cand)
    if user_role not in ("recruiter", "hiring_manager"):
        if not user_email or (referred_by.lower() != user_email and user_email not in str(cand.get("Additional_Info") or "").lower()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are only permitted to view status for referrals submitted by your email.",
            )

    notes = await zoho_service.get_candidate_notes(cand_id)
    first_name = str(cand.get("First_Name") or "").strip()
    last_name = str(cand.get("Last_Name") or "").strip()
    name = f"{first_name} {last_name}".strip() or str(cand.get("Candidate_Name") or "Candidate").strip()

    score_val = cand.get("Referral_Score")
    try:
        score = float(score_val) if score_val is not None else 85.0
    except (ValueError, TypeError):
        score = 85.0

    return ReferralStatusResponse(
        candidate_id=cand_id,
        name=name,
        email=str(cand.get("Email") or cand.get("Secondary_Email") or "").strip(),
        referred_by=referred_by or "System",
        referred_date=extract_referred_date(cand),
        approval_status=str(cand.get("Referral_Approval_Status") or "Pending").strip(),
        candidate_status=str(cand.get("Candidate_Status") or "New").strip(),
        referral_score=score,
        best_match=None,
        notes=notes,
    )


@router.get(
    "/list",
    response_model=list[ReferralListItem],
    summary="List candidate referrals",
    description="Returns referrals. Employees see only their own submissions; recruiters/managers see all.",
)
async def list_referrals(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[ReferralListItem]:
    user_email = current_user.get("email", "").lower()
    user_role = current_user.get("role", "employee")

    if user_role == "employee":
        candidates = await zoho_service.get_candidates_by_referrer(user_email)
    else:
        candidates = await zoho_service.get_all_candidates_cached()

    response.headers["X-Zoho-Search-Source"] = zoho_service.search_source

    items: list[ReferralListItem] = []
    for c in candidates:
        cand_id = str(c.get("id") or "")
        if not cand_id:
            continue

        ref_by = extract_referred_by(c)
        source = str(c.get("Source") or "").lower()
        add_info = str(c.get("Additional_Info") or "").lower()

        if user_role == "employee":
            if ref_by.lower() != user_email and user_email not in source and user_email not in add_info:
                continue
        else:
            if not (ref_by or "referral" in source or "referral" in add_info):
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
                referred_by=ref_by or ("Employee Referral" if "referral" in source else "System"),
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

    return items


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

    referred_by = extract_referred_by(cand)
    if user_role == "employee" and referred_by.lower() != user_email and user_email not in str(cand.get("Additional_Info") or "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this referral record.",
        )

    notes = await zoho_service.get_candidate_notes(candidate_id)
    first_name = str(cand.get("First_Name") or "").strip()
    last_name = str(cand.get("Last_Name") or "").strip()
    name = f"{first_name} {last_name}".strip() or str(cand.get("Candidate_Name") or "Candidate").strip()

    score_val = cand.get("Referral_Score")
    try:
        score = float(score_val) if score_val is not None else 85.0
    except (ValueError, TypeError):
        score = 85.0

    return ReferralStatusResponse(
        candidate_id=candidate_id,
        name=name,
        email=str(cand.get("Email") or cand.get("Secondary_Email") or "").strip(),
        referred_by=referred_by or "System",
        referred_date=extract_referred_date(cand),
        approval_status=str(cand.get("Referral_Approval_Status") or "Pending").strip(),
        candidate_status=str(cand.get("Candidate_Status") or "New").strip(),
        referral_score=score,
        best_match=None,
        notes=notes,
    )


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
