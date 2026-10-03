"""
Notification endpoints:
- POST /notifications/email (Tool Endpoint: allows Referral_Agent / recruiters to send email alerts)
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_auth_or_agent_user, get_tool_user
from app.services.email_service import email_service
from app.domain.models import EmailNotificationRequest, EmailNotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "/email",
    response_model=EmailNotificationResponse,
    tags=["Agent Tools"],
    summary="Tool 8: Notify Employee",
    description="Sends an email via Microsoft Graph to candidates, employees, or recruiters. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def send_email_notification(
    req: EmailNotificationRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> EmailNotificationResponse:
    recipient = (req.recipient_email or req.to_email or "").strip()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="recipient_email or to_email is required.",
        )

    html_content = req.body_html
    if not html_content:
        msg_text = req.message or req.body_text or ""
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <p style="white-space: pre-wrap; color: #1e293b;">{msg_text}</p>
        </div>
        """

    text_body = req.body_text or req.message or ""

    ok = await email_service.send_email(
        to_email=recipient,
        subject=req.subject,
        html_body=html_content,
        text_body=text_body,
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send notification email via Microsoft Graph: email sending is not configured correctly for this tenant. MS_SENDER_UPN in backend/.env must be an active Microsoft 365 tenant mailbox, not an external or Gmail address.",
        )

    return EmailNotificationResponse(success=True, message=f"Email sent successfully to {recipient}.")
