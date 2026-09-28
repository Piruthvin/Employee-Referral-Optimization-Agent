"""
Recruiter approval gate service.
Manages Pending, Approved, and Rejected status lifecycles, adds audit notes in Zoho,
and notifies referring employees via email upon recruiter decisions.
"""

import json
import logging
from typing import Any
from datetime import datetime, date
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.zoho_service import zoho_service
from app.services.email_service import email_service
from app.domain.models import PendingApprovalItem, ApprovalDetailResponse

logger = logging.getLogger(__name__)


class ApprovalService:
    async def get_pending_approvals(self) -> list[PendingApprovalItem]:
        """Fetches all candidates where Referral_Approval_Status is 'Pending'."""
        candidates = await zoho_service.get_all_candidates_cached()
        pending_list: list[PendingApprovalItem] = []

        for cand in candidates:
            app_status = (cand.get("Referral_Approval_Status") or "Pending").strip()
            # If Referral_Approval_Status is pending or missing on an employee referral
            source = (cand.get("Source") or "").lower()
            referred_by = cand.get("Referred_By") or ""

            if (app_status.lower() == "pending" or not app_status) and (referred_by or "referral" in source):
                cand_id = str(cand.get("id", ""))
                first_name = cand.get("First_Name") or ""
                last_name = cand.get("Last_Name") or ""
                name = f"{first_name} {last_name}".strip() or "Unnamed Candidate"
                email = cand.get("Email") or ""
                referred_date = cand.get("Referred_Date")
                score = cand.get("Referral_Score")

                days_pending = 0
                if referred_date:
                    try:
                        ref_d = datetime.strptime(referred_date[:10], "%Y-%m-%d").date()
                        days_pending = max(0, (date.today() - ref_d).days)
                    except Exception:
                        pass

                skills_raw = cand.get("Skill_Set") or []
                skills: list[str] = []
                if isinstance(skills_raw, list):
                    skills = [str(s) for s in skills_raw[:5]]
                elif isinstance(skills_raw, str):
                    skills = [s.strip() for s in skills_raw.split(",")[:5] if s.strip()]

                pending_list.append(
                    PendingApprovalItem(
                        candidate_id=cand_id,
                        name=name,
                        email=email,
                        referred_by=referred_by,
                        referred_date=referred_date,
                        referral_score=float(score) if score is not None else None,
                        best_match=None,
                        current_employer=cand.get("Current_Employer"),
                        current_job_title=cand.get("Current_Job_Title"),
                        experience_years=float(cand.get("Experience_in_Years") or 0) if cand.get("Experience_in_Years") is not None else None,
                        top_skills=skills,
                        days_pending=days_pending,
                    )
                )

        # Sort pending by referral_score descending, then by days_pending descending
        pending_list.sort(key=lambda x: (x.referral_score or 0.0, x.days_pending), reverse=True)
        return pending_list

    async def get_approval_detail(self, candidate_id: str) -> ApprovalDetailResponse:
        """Retrieves full candidate detail, parsed profile from Zoho Notes, and match info."""
        cand = await zoho_service.get_candidate_by_id(candidate_id)
        if not cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

        # Read candidate notes to reconstruct parsed profile if available
        notes = await zoho_service.get_candidate_notes(candidate_id)
        parsed_profile: dict[str, Any] | None = None
        has_mismatch = False
        mismatch_details: str | None = None

        for n in notes:
            content = n.get("Note_Content") or ""
            if "=== Full Parsed Profile JSON ===" in content:
                try:
                    json_str = content.split("=== Full Parsed Profile JSON ===")[1].strip()
                    parsed_profile = json.loads(json_str)
                except Exception:
                    pass
            if "⚠️ IDENTITY MISMATCH WARNING:" in content:
                has_mismatch = True
                mismatch_details = content.split("⚠️ IDENTITY MISMATCH WARNING:")[1].split("===")[0].strip()

        approval_status = cand.get("Referral_Approval_Status") or "Pending"

        return ApprovalDetailResponse(
            candidate_id=candidate_id,
            candidate=cand,
            parsed_profile=parsed_profile,
            match_details=None,
            has_identity_mismatch=has_mismatch,
            identity_mismatch_details=mismatch_details,
            approval_status=approval_status,
        )

    async def approve_referral(
        self,
        candidate_id: str,
        note: str | None,
        recruiter_email: str,
    ) -> dict[str, Any]:
        """Approves a referral, updates Zoho statuses, adds note, and notifies referring employee."""
        settings = get_settings()
        cand = await zoho_service.get_candidate_by_id(candidate_id)
        if not cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

        # Update Candidate in Zoho
        update_fields: dict[str, Any] = {
            "Referral_Approval_Status": "Approved",
            "Candidate_Status": settings.status_on_approval,
        }
        if note:
            update_fields["Referral_Approval_Note"] = note

        updated = await zoho_service.update_candidate(candidate_id, update_fields)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update candidate approval status in Zoho Recruit.",
            )

        # Add Note
        audit_note = f"Referral Approved by {recruiter_email}.\nNote: {note or 'No note provided.'}"
        await zoho_service.add_note(candidate_id, "Referral Approved", audit_note)

        # Notify referring employee
        employee_email = cand.get("Referred_By")
        if employee_email:
            cand_name = f"{cand.get('First_Name', '')} {cand.get('Last_Name', '')}".strip() or "Candidate"
            await self._notify_employee_decision(
                employee_email=employee_email,
                candidate_name=cand_name,
                decision="Approved",
                note=note,
            )

        return {
            "success": True,
            "candidate_id": candidate_id,
            "approval_status": "Approved",
            "message": "Referral approved successfully.",
        }

    async def reject_referral(
        self,
        candidate_id: str,
        note: str | None,
        recruiter_email: str,
    ) -> dict[str, Any]:
        """Rejects a referral, updates Zoho statuses, adds note, and notifies referring employee."""
        settings = get_settings()
        cand = await zoho_service.get_candidate_by_id(candidate_id)
        if not cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

        update_fields: dict[str, Any] = {
            "Referral_Approval_Status": "Rejected",
            "Candidate_Status": settings.status_on_rejection,
        }
        if note:
            update_fields["Referral_Approval_Note"] = note

        updated = await zoho_service.update_candidate(candidate_id, update_fields)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update candidate rejection status in Zoho Recruit.",
            )

        audit_note = f"Referral Rejected by {recruiter_email}.\nNote: {note or 'No note provided.'}"
        await zoho_service.add_note(candidate_id, "Referral Rejected", audit_note)

        employee_email = cand.get("Referred_By")
        if employee_email:
            cand_name = f"{cand.get('First_Name', '')} {cand.get('Last_Name', '')}".strip() or "Candidate"
            await self._notify_employee_decision(
                employee_email=employee_email,
                candidate_name=cand_name,
                decision="Rejected",
                note=note,
            )

        return {
            "success": True,
            "candidate_id": candidate_id,
            "approval_status": "Rejected",
            "message": "Referral rejected.",
        }

    async def _notify_employee_decision(
        self,
        employee_email: str,
        candidate_name: str,
        decision: str,
        note: str | None,
    ) -> None:
        """Sends decision update to the referring employee."""
        subject = f"Referral Update: {candidate_name} has been {decision}"
        note_section = f"<p><strong>Recruiter feedback:</strong> {note}</p>" if note else ""

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #0f172a; margin-top: 0;">Referral Status Update</h2>
            <p>Your referral for <strong>{candidate_name}</strong> has been reviewed by the recruiting team.</p>
            <p><strong>Decision:</strong> <span style="font-weight: bold; color: {'#16a34a' if decision == 'Approved' else '#dc2626'};">{decision.upper()}</span></p>
            {note_section}
            <p style="color: #64748b; font-size: 13px; margin-top: 24px;">Thank you for your active participation in our employee referral program!</p>
        </div>
        """
        try:
            await email_service.send_email(
                to_email=employee_email,
                subject=subject,
                html_body=html_body,
                text_body=f"Your referral for {candidate_name} has been {decision}. Note: {note or 'N/A'}",
            )
        except Exception as e:
            logger.warning("Failed to email employee %s decision update: %s", employee_email, e)


approval_service = ApprovalService()
