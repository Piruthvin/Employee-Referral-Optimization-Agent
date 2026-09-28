"""
iGentic Multi-Agent AI Platform client.
Handles communication with the iGentic executor:
- Injects verified context headers: [CONTEXT role=<role> email=<email>]
- Streams Server-Sent Events (SSE) chunks directly to caller
- Supports session/conversation state continuity
- Graceful offline/mock mode for development when iGentic credentials are unset
"""

import json
import logging
from typing import AsyncGenerator
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class IGenticClient:
    async def call_stream(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
    ) -> AsyncGenerator[str, None]:
        """
        Invokes iGentic executor with streaming enabled and yields SSE chunks.
        Prepends verified context tag: [CONTEXT role=<role> email=<email>].
        """
        settings = get_settings()
        trusted_input = f"[CONTEXT role={user_role} email={user_email}]\n{user_message}"

        # If iGentic executor is not configured, provide mock development SSE stream
        if not settings.igentic_executor_url or not settings.igentic_app_id:
            logger.info("iGentic executor credentials not configured; yielding simulated development stream.")
            curr_sid = session_id or "dev-session-001"
            yield f"data: {json.dumps({'Type': 'status', 'Status': 'Routing via Group Chat Manager...'})}\n\n"
            yield f"data: {json.dumps({'Type': 'status', 'Status': 'Referral_Agent processing...'})}\n\n"

            # Contextual response
            mock_reply = (
                f"Hello! As the **Referral Agent**, I am here to help you optimize candidate referrals.\n\n"
                f"• Verified Role: `{user_role}`\n"
                f"• Verified Email: `{user_email}`\n\n"
                f"*(Note: iGentic executor is running in local simulation mode. Configure `IGENTIC_EXECUTOR_URL` and `IGENTIC_APP_ID` in `.env` to connect to cloud agents.)*"
            )
            yield f"data: {json.dumps({'Type': 'complete', 'Result': mock_reply, 'SessionId': curr_sid})}\n\n"
            return

        body = {
            "userInput": trusted_input,
            "UserInputType": "",
            "sessionId": session_id or "",
            "executionId": "",
            "connectionID": "",
            "isStreaming": True,
            "Username": settings.igentic_username,
        }

        headers = {
            "Authorization": f"Bearer {settings.igentic_bearer_token}",
            "x-api-key": settings.igentic_api_key,
            "x-app-id": settings.igentic_app_id,
            "x-username": settings.igentic_username,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if session_id:
            headers["x-session-id"] = session_id

        timeout = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", settings.igentic_executor_url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        logger.error("iGentic stream returned HTTP %d: %s", resp.status_code, err_text.decode("utf-8", errors="ignore"))
                        yield f"data: {json.dumps({'Type': 'error', 'Error': f'Upstream agent service returned {resp.status_code}'})}\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if line:
                            yield f"{line}\n"
                        else:
                            yield "\n"
            except Exception as e:
                logger.error("Error streaming from iGentic executor: %s", e)
                yield f"data: {json.dumps({'Type': 'error', 'Error': 'Failed to connect to agent service.'})}\n\n"

    async def call_sync(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
    ) -> dict[str, str]:
        """Non-streaming request to iGentic executor."""
        settings = get_settings()
        trusted_input = f"[CONTEXT role={user_role} email={user_email}]\n{user_message}"

        if not settings.igentic_executor_url or not settings.igentic_app_id:
            return {
                "response": f"Hello! Verified as {user_role} ({user_email}). iGentic cloud executor is in local development mode.",
                "conversation_id": session_id or "dev-session-001",
            }

        body = {
            "userInput": trusted_input,
            "UserInputType": "",
            "sessionId": session_id or "",
            "executionId": "",
            "connectionID": "",
            "isStreaming": False,
            "Username": settings.igentic_username,
        }

        headers = {
            "Authorization": f"Bearer {settings.igentic_bearer_token}",
            "x-api-key": settings.igentic_api_key,
            "x-app-id": settings.igentic_app_id,
            "x-username": settings.igentic_username,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if session_id:
            headers["x-session-id"] = session_id

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(settings.igentic_executor_url, json=body, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"iGentic executor failed with HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            result_text = data.get("Result") or data.get("result") or data.get("output") or resp.text
            sid = data.get("SessionId") or data.get("sessionId") or session_id or ""
            return {"response": result_text, "conversation_id": sid}


igentic_client = IGenticClient()
