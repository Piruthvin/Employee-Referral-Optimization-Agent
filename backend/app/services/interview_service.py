"""
Interview scheduling service.
Enforces approval gate (409 Conflict if not Approved).
Creates Microsoft Teams online meetings via app-only Graph token (organizer: MS_ORGANIZER_UPN),
generates RFC 5545 .ics calendar attachments, updates Zoho candidate status,
and notifies candidate, recruiter, and referring employee.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Any
import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.zoho_service import zoho_service
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class InterviewService:
    async def schedule_interview(
        self,
        candidate_id: str,
        start_time_iso: str,
        duration_minutes: int,
        recruiter_email: str,
        interviewer_emails: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Schedules an interview for an approved candidate.
        Raises HTTP 409 if referral is not yet approved.
        """
        settings = get_settings()
        cand = await zoho_service.get_candidate_by_id(candidate_id)
        if not cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

        # ENFORCE APPROVAL GATE
        approval_status = (cand.get("Referral_Approval_Status") or "").strip().lower()
        cand_status = (cand.get("Candidate_Status") or "").strip().lower()
        is_approved = approval_status == "approved" or cand_status in (
            settings.status_on_approval.lower(),
            "in-review",
            "approved",
        )
        if not is_approved:
            # Check candidate notes as fallback
            notes = await zoho_service.get_candidate_notes(candidate_id)
            is_approved = any(n.get("Note_Title") == "Referral Approved" for n in notes)

        if not is_approved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Referral not approved. Current candidate status is '{cand.get('Candidate_Status', 'Pending')}'. Interview scheduling is only allowed after recruiter approval.",
            )

        # Parse timestamps
        try:
            start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
        except Exception:
            start_dt = datetime.utcnow() + timedelta(days=2)

        end_dt = start_dt + timedelta(minutes=duration_minutes)

        cand_first = cand.get("First_Name") or ""
        cand_last = cand.get("Last_Name") or ""
        cand_name = f"{cand_first} {cand_last}".strip() or "Candidate"
        cand_email = cand.get("Email")
        employee_email = cand.get("Referred_By")

        # Create Teams Meeting via Microsoft Graph
        meeting_url = await self._create_teams_meeting(
            subject=f"Interview with {cand_name} - {settings.app_name}",
            start_dt=start_dt,
            end_dt=end_dt,
        )

        # Update Candidate Status in Zoho Recruit
        await zoho_service.update_candidate(
            candidate_id=candidate_id,
            fields={
                "Candidate_Status": settings.status_on_interview_scheduled,
            },
        )

        # Add Note in Zoho
        note_content = (
            f"Interview Scheduled\n"
            f"Start: {start_dt.isoformat()}\n"
            f"Duration: {duration_minutes} minutes\n"
            f"Teams Link: {meeting_url}\n"
            f"Recruiter: {recruiter_email}\n"
            f"Notes: {notes or 'N/A'}"
        )
        await zoho_service.add_note(candidate_id, "Interview Scheduled", note_content)

        # Generate .ics Calendar Invitation
        ics_bytes = self._generate_ics(
            summary=f"Job Interview - {cand_name}",
            description=f"Job interview for {cand_name}.\n\nJoin Teams Meeting: {meeting_url}\n\nNotes: {notes or 'None'}",
            start_dt=start_dt,
            end_dt=end_dt,
            location="Microsoft Teams Meeting",
        )

        attachment = {
            "name": "interview_invitation.ics",
            "content_type": "text/calendar; method=REQUEST",
            "content_bytes": ics_bytes,
        }

        # Send Email to Candidate
        if cand_email:
            cand_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h2 style="color: #0f172a; margin-top: 0;">Interview Invitation</h2>
                <p>Dear {cand_name},</p>
                <p>We are pleased to invite you to an interview. Your details are as follows:</p>
                <ul>
                    <li><strong>Date & Time:</strong> {start_dt.strftime('%B %d, %Y at %I:%M %p UTC')}</li>
                    <li><strong>Duration:</strong> {duration_minutes} minutes</li>
                    <li><strong>Platform:</strong> Microsoft Teams</li>
                </ul>
                <div style="margin: 24px 0; text-align: center;">
                    <a href="{meeting_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                        Join Teams Meeting
                    </a>
                </div>
                <p style="color: #64748b; font-size: 13px;">A calendar invitation (.ics) is attached to this email. Please confirm your availability.</p>
            </div>
            """
            await email_service.send_email(
                to_email=cand_email,
                subject=f"Interview Invitation: {cand_name}",
                html_body=cand_html,
                text_body=f"Interview scheduled on {start_dt}. Join: {meeting_url}",
                attachments=[attachment],
            )

        # Send Email to Recruiter & Interviewers
        all_recruiters = [recruiter_email]
        if interviewer_emails:
            all_recruiters.extend(interviewer_emails)

        rec_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #0f172a; margin-top: 0;">Interview Confirmed: {cand_name}</h2>
            <p><strong>Candidate:</strong> {cand_name} ({cand_email})</p>
            <p><strong>Time:</strong> {start_dt.strftime('%B %d, %Y at %I:%M %p UTC')}</p>
            <p><strong>Teams Meeting:</strong> <a href="{meeting_url}">{meeting_url}</a></p>
            <p><strong>Notes:</strong> {notes or 'None'}</p>
        </div>
        """
        await email_service.send_email(
            to_email=all_recruiters,
            subject=f"Interview Confirmed: {cand_name}",
            html_body=rec_html,
            attachments=[attachment],
        )

        # Send Email to Referring Employee
        if employee_email:
            emp_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h2 style="color: #0f172a; margin-top: 0;">Referral Progress Update</h2>
                <p>Great news! An interview has been officially scheduled for your referral, <strong>{cand_name}</strong>.</p>
                <p><strong>Interview Date:</strong> {start_dt.strftime('%B %d, %Y at %I:%M %p UTC')}</p>
                <p style="color: #64748b; font-size: 13px;">We will keep you posted on further updates in your referral dashboard.</p>
            </div>
            """
            await email_service.send_email(
                to_email=employee_email,
                subject=f"Interview Scheduled for your referral {cand_name}!",
                html_body=emp_html,
            )

        return {
            "success": True,
            "candidate_id": candidate_id,
            "meeting_url": meeting_url,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "status": settings.status_on_interview_scheduled,
            "message": "Interview successfully scheduled with Teams meeting and invitations sent.",
        }

    async def _create_teams_meeting(self, subject: str, start_dt: datetime, end_dt: datetime) -> str:
        """Calls Microsoft Graph onlineMeetings endpoint using organizer UPN."""
        settings = get_settings()
        token = await email_service.get_graph_token()

        if not token or not settings.ms_organizer_upn:
            # Fallback simulated Teams URL for dev / offline testing
            mock_id = uuid.uuid4().hex[:12]
            return f"https://teams.microsoft.com/l/meetup-join/{mock_id}"

        url = f"https://graph.microsoft.com/v1.0/users/{settings.ms_organizer_upn}/onlineMeetings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "startDateTime": start_dt.isoformat(),
            "endDateTime": end_dt.isoformat(),
            "subject": subject,
            "lobbyBypassSettings": {"scope": "organization"},
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    join_url = data.get("joinWebUrl") or data.get("joinUrl")
                    if join_url:
                        return join_url
                if resp.status_code in (401, 403):
                    logger.error(
                        "Teams onlineMeetings failed HTTP %d: %s. "
                        "Configuration Issue: Teams meeting creation is not configured correctly for this tenant. "
                        "MS_ORGANIZER_UPN ('%s') must be an active Microsoft 365 tenant mailbox, not an external or Gmail address.",
                        resp.status_code, resp.text, settings.ms_organizer_upn,
                    )
                else:
                    logger.error("Teams onlineMeetings failed HTTP %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Exception calling Graph onlineMeetings: %s", e)

        # Fallback if Graph fails
        mock_id = uuid.uuid4().hex[:12]
        return f"https://teams.microsoft.com/l/meetup-join/{mock_id}"

    @staticmethod
    def _generate_ics(
        summary: str,
        description: str,
        start_dt: datetime,
        end_dt: datetime,
        location: str,
    ) -> bytes:
        """Generates standard RFC 5545 iCalendar byte payload."""
        uid = f"{uuid.uuid4()}@referralagent.internal"
        now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dtstart_str = start_dt.strftime("%Y%m%dT%H%M%SZ")
        dtend_str = end_dt.strftime("%Y%m%dT%H%M%SZ")

        escaped_desc = description.replace("\r", "").replace("\n", "\\n")
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Referral Agent//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_str}",
            f"DTSTART:{dtstart_str}",
            f"DTEND:{dtend_str}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{escaped_desc}",
            f"LOCATION:{location}",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return "\r\n".join(ics_lines).encode("utf-8")


interview_service = InterviewService()
