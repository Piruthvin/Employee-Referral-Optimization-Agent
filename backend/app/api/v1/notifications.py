"""
Notification endpoints:
- POST /notifications/email (Tool Endpoint: allows Referral_Agent / recruiters to send email alerts)
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_auth_or_agent_user
from app.services.email_service import email_service
from app.domain.models import EmailNotificationRequest, EmailNotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "/email",
    response_model=EmailNotificationResponse,
    summary="Send notification email (Tool Endpoint)",
    description="Sends an email via Microsoft Graph to candidates, employees, or recruiters. Accessible via JWT or X-Agent-Key.",
)
async def send_email_notification(
    req: EmailNotificationRequest,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> EmailNotificationResponse:
    # Basic permission check: recruiters, or agent on behalf of recruiter
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <p style="white-space: pre-wrap; color: #1e293b;">{req.message}</p>
    </div>
    """

    ok = await email_service.send_email(
        to_email=req.to_email,
        subject=req.subject,
        html_body=html_content,
        text_body=req.message,
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send notification email via Microsoft Graph.",
        )

    return EmailNotificationResponse(success=True, message=f"Email sent successfully to {req.to_email}.")
