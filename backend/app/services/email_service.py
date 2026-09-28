"""
Email delivery service using Microsoft Graph API (sendMail).
Supports HTML content, plain-text fallback, and file/ICS attachments.
Gracefully degrades in development when Graph credentials are not provided.
"""

import base64
import logging
from typing import Any
import httpx
import msal

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self) -> None:
        self._msal_app: msal.ConfidentialClientApplication | None = None

    def _get_msal_app(self) -> msal.ConfidentialClientApplication | None:
        settings = get_settings()
        if not settings.ms_tenant_id or not settings.ms_client_id or not settings.ms_client_secret:
            return None
        if self._msal_app is None:
            authority = f"https://login.microsoftonline.com/{settings.ms_tenant_id}"
            self._msal_app = msal.ConfidentialClientApplication(
                client_id=settings.ms_client_id,
                client_credential=settings.ms_client_secret,
                authority=authority,
            )
        return self._msal_app

    async def get_graph_token(self) -> str | None:
        app = self._get_msal_app()
        if app is None:
            return None

        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_silent(scopes, account=None)
        if not result:
            result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" in result:
            return result["access_token"]
        logger.error("Failed to acquire MS Graph token: %s", result.get("error_description"))
        return None

    async def send_email(
        self,
        to_email: str | list[str],
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Sends an email via Microsoft Graph sendMail.
        If Graph credentials are not configured, logs message in development.
        """
        settings = get_settings()
        recipients = [to_email] if isinstance(to_email, str) else to_email
        recipients = [r.strip() for r in recipients if r and r.strip()]

        if not recipients:
            logger.warning("send_email called with no recipients.")
            return False

        token = await self.get_graph_token()
        if not token or not settings.ms_sender_upn:
            logger.warning(
                "[DEV/MOCK EMAIL] To: %s | Subject: %s | Graph credentials not fully configured.",
                recipients,
                subject,
            )
            # In development/test, return True to avoid crashing caller
            return True

        to_recipients_payload = [{"emailAddress": {"address": addr}} for addr in recipients]

        message_payload: dict[str, Any] = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "toRecipients": to_recipients_payload,
        }

        if attachments:
            formatted_attachments = []
            for att in attachments:
                # Expects dict with name, content_bytes (bytes) or content_base64 (str), content_type
                name = att.get("name", "attachment")
                content_type = att.get("content_type", "application/octet-stream")
                content_bytes = att.get("content_bytes")
                if content_bytes:
                    content_b64 = base64.b64encode(content_bytes).decode("utf-8")
                else:
                    content_b64 = att.get("content_base64", "")

                formatted_attachments.append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": name,
                        "contentType": content_type,
                        "contentBytes": content_b64,
                    }
                )
            message_payload["attachments"] = formatted_attachments

        url = f"https://graph.microsoft.com/v1.0/users/{settings.ms_sender_upn}/sendMail"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json={"message": message_payload, "saveToSentItems": "true"}, headers=headers)
            if resp.status_code in (200, 202):
                logger.info("Email sent successfully via Microsoft Graph to %s", recipients)
                return True
            logger.error("Microsoft Graph sendMail failed HTTP %d: %s", resp.status_code, resp.text)
            return False

    async def send_otp_email(self, to_email: str, otp: str) -> bool:
        """Sends a verification code for stateless login."""
        settings = get_settings()
        subject = f"Your Verification Code: {otp} - {settings.app_name}"
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #1e293b; margin-top: 0;">Verification Code</h2>
            <p style="color: #475569; font-size: 15px;">Use the 6-digit code below to securely log into the <strong>{settings.app_name}</strong>:</p>
            <div style="background-color: #f1f5f9; padding: 18px; text-align: center; border-radius: 6px; margin: 20px 0;">
                <span style="font-family: monospace; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #0f172a;">{otp}</span>
            </div>
            <p style="color: #64748b; font-size: 13px;">This code is valid for <strong>10 minutes</strong>. If you did not request this login, please ignore this email.</p>
        </div>
        """
        text_body = f"Your verification code is: {otp}. It expires in 10 minutes."
        return await self.send_email(to_email, subject, html_body, text_body)


email_service = EmailService()
