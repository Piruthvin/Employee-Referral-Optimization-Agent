"""
Referral pipeline orchestration service.
Executes the full candidate intake lifecycle:
1. File validation & text extraction
2. Duplicate detection in Zoho
3. Structured parsing with agent/python fallback
4. Open job matching & ranking
5. Metadata discovery and candidate creation
6. Resume attachment upload with compensating rollback
7. Zoho Note creation (parsed JSON + parser audit)
8. Threshold-based job association
9. Recruiter email notification
"""

import json
import logging
from typing import Any
from fastapi import UploadFile, HTTPException, status

from app.core.config import get_settings
from app.services.resume_extract_service import resume_extract_service
from app.services.resume_parser_service import resume_parser_service
from app.services.job_match_service import job_match_service
from app.services.zoho_service import zoho_service
from app.services.zoho_field_mapper import zoho_field_mapper
from app.services.zoho_users_service import zoho_users_service
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class ReferralService:
    async def submit_referral(
        self,
        candidate_name: str,
        candidate_email: str,
        resume_file: UploadFile,
        current_user: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Orchestrates full referral submission pipeline.
        Logged with structured request tracing and zero PII in application logs.
        """
        settings = get_settings()
        employee_email = current_user.get("email", "").strip().lower()
        user_role = current_user.get("role", "employee")
        warnings: list[str] = []

        # 1. Validate File & Extract Text
        clean_text, file_bytes = await resume_extract_service.validate_and_extract(resume_file)
        filename = resume_file.filename or "resume.pdf"

        # 2. Duplicate Check in Zoho
        existing_candidate = await zoho_service.search_candidate_by_email(candidate_email)
        if existing_candidate:
            existing_id = existing_candidate.get("id")
            existing_referrer = existing_candidate.get("Referred_By") or existing_candidate.get("Created_By", {}).get("name")
            if user_role in ("recruiter", "hiring_manager"):
                detail_msg = f"Candidate with email '{candidate_email}' already exists in Zoho Recruit (ID: {existing_id}, Referred by: {existing_referrer})."
            else:
                detail_msg = f"A candidate with email '{candidate_email}' has already been referred or already exists in the system."

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail_msg,
            )

        # 3. Structure into JSON (Agent / Python with fallback)
        try:
            parsed_resume, parser_used = await resume_parser_service.parse_resume(
                clean_text,
                candidate_email=candidate_email,
                candidate_name=candidate_name,
            )
        except Exception as parse_err:
            logger.warning("Agent resume parsing failed: %s. Falling back to deterministic Python parser.", parse_err)
            parsed_resume, parser_used = resume_parser_service._parse_with_python(clean_text)


        # 4. Job Matching Against Open Jobs (AI Agent first, Python fallback)
        open_jobs = await zoho_service.get_open_jobs()
        try:
            job_matches, matcher_used = await job_match_service.rank_jobs_for_candidate_agent_first(
                candidate_skills=parsed_resume.skills,
                candidate_exp_years=parsed_resume.total_experience_years,
                open_jobs=open_jobs,
                candidate_profile=parsed_resume.model_dump(),
                min_match=0,
            )
        except Exception as jm_err:
            logger.warning("Job matching agent call raised unexpected error: %s. Falling back to deterministic Python matcher.", jm_err)
            job_matches = job_match_service.rank_jobs_for_candidate(
                candidate_skills=parsed_resume.skills,
                candidate_exp_years=parsed_resume.total_experience_years,
                open_jobs=open_jobs,
                min_match=0,
            )
            matcher_used = "python_fallback"

        best_match = job_matches[0] if job_matches else None
        referral_score = best_match["match_percent"] if best_match else None

        # 5. Field Mapping against Runtime Zoho Metadata
        candidates_meta = await zoho_field_mapper.get_candidate_fields_metadata()
        payload, has_mismatch, mismatch_details = zoho_field_mapper.map_to_zoho_candidate(
            authoritative_name=candidate_name,
            authoritative_email=candidate_email,
            parsed_resume=parsed_resume,
            employee_email=employee_email,
            referral_score=referral_score,
            candidates_meta=candidates_meta,
        )

        # 6. Create Candidate in Zoho Recruit
        candidate_id = await zoho_service.create_candidate(payload)

        # 7. Upload Resume Attachment (with Compensating Rollback)
        try:
            await zoho_service.upload_resume_attachment(candidate_id, file_bytes, filename)
        except Exception as att_err:
            logger.error("Attachment upload failed for candidate %s: %s. Initiating compensating delete...", candidate_id, att_err)
            del_ok = await zoho_service.delete_candidate(candidate_id)
            if not del_ok:
                logger.critical("CRITICAL: Compensating delete failed for orphaned candidate %s!", candidate_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Resume attachment upload failed. Referral creation was rolled back. Please try again.",
            )

        # 8. Add Zoho Note (Parsed JSON & Audit Info)
        note_content_lines = [
            f"=== Referral AI Parser Audit ===",
            f"Parser Used: {parser_used.upper()}",
            f"Job Matcher Used: {matcher_used.upper()}",
            f"Referral Score: {referral_score}%" if referral_score is not None else "Referral Score: N/A",
            f"Referred By: {employee_email}",
            f"\n=== Top Job Matches ===",
        ]
        if job_matches:
            for jm in job_matches[:3]:
                note_content_lines.append(f"• {jm['job_title']} ({jm['job_id']}): {jm['match_percent']}% match (Fit: {jm['experience_fit']})")
                if jm.get("notes"):
                    note_content_lines.append(f"  Why this match: {jm['notes']}")
        else:
            note_content_lines.append("No active open jobs found during referral.")

        if best_match:
            note_content_lines.append("\n=== Best Job Match JSON ===")
            note_content_lines.append(json.dumps(best_match, indent=2))

        if has_mismatch and mismatch_details:
            note_content_lines.append(f"\n⚠️ IDENTITY MISMATCH WARNING:\n{mismatch_details}")

        note_content_lines.append(f"\n=== Full Parsed Profile JSON ===")
        note_content_lines.append(json.dumps(parsed_resume.model_dump(), indent=2))

        try:
            await zoho_service.add_note(
                candidate_id=candidate_id,
                title="Referral Profile & Job Matches",
                content="\n".join(note_content_lines),
            )
        except Exception as note_err:
            logger.warning("Failed to create Zoho Note for candidate %s: %s", candidate_id, note_err)
            warnings.append("Note creation in Zoho failed.")

        # 9. Associate with Best Match Job if >= MIN_ASSOCIATE_MATCH (default 40)
        if best_match and best_match["match_percent"] >= settings.min_associate_match and best_match["job_id"]:
            try:
                await zoho_service.associate_candidate_to_job(candidate_id, best_match["job_id"])
            except Exception as assoc_err:
                logger.warning("Failed to associate candidate %s with job %s: %s", candidate_id, best_match["job_id"], assoc_err)
                warnings.append(f"Could not automatically associate candidate with job '{best_match['job_title']}'.")

        # 10. Recruiter Email Notification via Microsoft Graph (non-blocking)
        import asyncio
        asyncio.create_task(
            self._send_recruiter_notification(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                employee_email=employee_email,
                parsed_resume=parsed_resume,
                best_match=best_match,
                has_mismatch=has_mismatch,
                mismatch_details=mismatch_details,
                warnings=warnings,
            )
        )

        return {
            "success": True,
            "candidate_id": candidate_id,
            "best_match": {
                "job_id": best_match.get("job_id"),
                "job_title": best_match.get("job_title", "Unmatched"),
                "job_description": best_match.get("job_description", ""),
                "match_percent": best_match.get("match_percent", 0.0),
                "matched_skills": best_match.get("matched_skills", []),
                "missing_skills": best_match.get("missing_skills", []),
                "experience_fit": best_match.get("experience_fit", True),
                "notes": best_match.get("notes"),
            } if best_match else None,
            "status": "Pending recruiter approval",
            "warnings": warnings,
        }

    async def _send_recruiter_notification(
        self,
        candidate_id: str,
        candidate_name: str,
        candidate_email: str,
        employee_email: str,
        parsed_resume: Any,
        best_match: dict[str, Any] | None,
        has_mismatch: bool,
        mismatch_details: str | None,
        warnings: list[str],
    ) -> None:
        """Sends email notification to recruiters via Microsoft Graph."""
        settings = get_settings()
        recipients: list[str] = []

        if settings.recruiter_notify_emails:
            recipients = [e.strip() for e in settings.recruiter_notify_emails.split(",") if e.strip()]
        else:
            # Fallback to all active Zoho Recruiters / Admins
            try:
                active_users = await zoho_users_service.get_active_users()
                for u in active_users:
                    role = zoho_users_service.derive_user_role(u)
                    if role == "recruiter" and u.get("email"):
                        recipients.append(u["email"].strip())
            except Exception as e:
                logger.warning("Could not list active recruiters from Zoho for notification: %s", e)

        if not recipients:
            logger.info("No recruiter email addresses available for notification.")
            return

        approval_link = f"{settings.frontend_base_url.rstrip('/')}/approvals/{candidate_id}"
        subject = f"New Referral Submitted: {candidate_name} (Referred by {employee_email})"

        # HTML formatting
        mismatch_banner = ""
        if has_mismatch and mismatch_details:
            mismatch_banner = f"""
            <div style="background-color: #fef2f2; border: 1px solid #f87171; border-radius: 6px; padding: 12px; margin-bottom: 16px; color: #991b1b;">
                <strong>⚠️ Identity Mismatch Flag:</strong> {mismatch_details}
            </div>
            """

        best_job_text = best_match['job_title'] if best_match else 'None'
        best_score_text = f"{best_match['match_percent']}%" if best_match else 'N/A'
        matched_skills = ", ".join(best_match.get("matched_skills", [])) if best_match else "None"
        missing_skills = ", ".join(best_match.get("missing_skills", [])) if best_match else "None"
        top_skills = ", ".join(parsed_resume.skills[:8]) if parsed_resume.skills else "None listed"

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #0f172a; margin-top: 0;">New Employee Referral Intake</h2>
            {mismatch_banner}
            <p><strong>Candidate:</strong> {candidate_name} ({candidate_email})</p>
            <p><strong>Referred By:</strong> {employee_email}</p>
            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 16px 0;" />
            <h3 style="color: #334155; margin-bottom: 8px;">Candidate Highlights</h3>
            <ul>
                <li><strong>Current Role:</strong> {parsed_resume.current_job_title or 'Not specified'} at {parsed_resume.current_employer or 'Not specified'}</li>
                <li><strong>Total Experience:</strong> {parsed_resume.total_experience_years or 0} years</li>
                <li><strong>Top Skills:</strong> {top_skills}</li>
            </ul>
            <h3 style="color: #334155; margin-bottom: 8px;">Job Matching</h3>
            <ul>
                <li><strong>Best Matching Job:</strong> {best_job_text} ({best_score_text} match)</li>
                <li><strong>Matched Skills:</strong> {matched_skills}</li>
                <li><strong>Missing Skills:</strong> {missing_skills}</li>
            </ul>
            <div style="margin: 24px 0; text-align: center;">
                <a href="{approval_link}" style="background-color: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                    Review & Approve Referral
                </a>
            </div>
            <p style="color: #64748b; font-size: 12px; text-align: center;">
                Recruiter login is required to review this submission. Never share approval links.
            </p>
        </div>
        """

        try:
            await email_service.send_email(
                to_email=recipients,
                subject=subject,
                html_body=html_body,
                text_body=f"New referral: {candidate_name} referred by {employee_email}. Review at: {approval_link}",
            )
        except Exception as e:
            logger.warning("Recruiter notification email delivery failed: %s", e)
            warnings.append("Recruiter notification email could not be delivered.")


referral_service = ReferralService()
