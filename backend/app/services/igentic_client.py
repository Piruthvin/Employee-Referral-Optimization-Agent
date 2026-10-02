"""
iGentic Multi-Agent AI Platform client.
Unified client for the single iGentic app with 3 participants:
Group Chat Manager -> Referral_Agent / Analytics_Agent / Resume_Parser_Agent.
Uses ONE executor URL, ONE app ID, and ONE set of credentials for both:
- Chat interactions (send_chat_message / call_stream / call_sync)
- Resume parsing (parse_resume)
"""

import json
import logging
from typing import Any, AsyncGenerator, Union
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class IGenticClient:
    """
    Unified client for the iGentic executor managing Group Chat Manager and its 3 participants:
    - Referral_Agent
    - Analytics_Agent
    - Resume_Parser_Agent
    """

    def _get_headers(self, session_id: str | None = None, accept: str = "application/json") -> dict[str, str]:
        settings = get_settings()
        headers = {
            "Authorization": f"Bearer {settings.igentic_bearer_token}",
            "x-api-key": settings.igentic_api_key,
            "x-app-id": settings.igentic_app_id,
            "x-username": settings.igentic_username,
            "Content-Type": "application/json",
            "Accept": accept,
        }
        if session_id:
            headers["x-session-id"] = session_id
        return headers

    async def send_chat_message(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
        is_streaming: bool = False,
    ) -> Union[AsyncGenerator[str, None], dict[str, str]]:
        """
        Sends human chat message to iGentic executor.
        Prepends verified context tag: [CONTEXT role=<role> email=<email>].
        Group Chat Manager routes to Referral_Agent or Analytics_Agent.
        """
        if is_streaming:
            return self._stream_chat(user_message, session_id, user_email, user_role)
        return await self._sync_chat(user_message, session_id, user_email, user_role)

    async def _stream_chat(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
    ) -> AsyncGenerator[str, None]:
        settings = get_settings()
        trusted_input = f"[CONTEXT role={user_role} email={user_email}]\n{user_message}"

        # If iGentic executor is not configured, provide mock development SSE stream
        if not settings.igentic_executor_url or not settings.igentic_app_id:
            logger.info("iGentic executor credentials not configured; yielding simulated development stream.")
            curr_sid = session_id or "dev-session-001"
            yield f"data: {json.dumps({'Type': 'status', 'Status': 'Routing via Group Chat Manager...'})}\n\n"
            yield f"data: {json.dumps({'Type': 'status', 'Status': 'Referral_Agent processing...'})}\n\n"

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

        headers = self._get_headers(session_id=session_id, accept="text/event-stream")
        timeout = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", settings.igentic_executor_url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        logger.error(
                            "iGentic stream returned HTTP %d: %s",
                            resp.status_code,
                            err_text.decode("utf-8", errors="ignore"),
                        )
                        yield f"data: {json.dumps({'Type': 'error', 'Error': f'Upstream agent service returned {resp.status_code}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if line:
                            yield f"{line}\n"
                        else:
                            yield "\n"
                    yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("Error streaming from iGentic executor: %s", e)
                yield f"data: {json.dumps({'Type': 'error', 'Error': 'Failed to connect to agent service.'})}\n\n"
                yield "data: [DONE]\n\n"


    async def _sync_chat(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
    ) -> dict[str, str]:
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

        headers = self._get_headers(session_id=session_id, accept="application/json")
        timeout = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(settings.igentic_executor_url, json=body, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"iGentic executor failed with HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            result_text = data.get("Result") or data.get("result") or data.get("output") or resp.text
            sid = data.get("SessionId") or data.get("sessionId") or session_id or ""
            return {"response": result_text, "conversation_id": sid}

    # Aliases for backwards compatibility with existing endpoints and tests
    def call_stream(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion generator (delegates to _stream_chat)."""
        return self._stream_chat(user_message, session_id, user_email, user_role)

    async def call_sync(
        self,
        user_message: str,
        session_id: str | None,
        user_email: str,
        user_role: str,
    ) -> dict[str, str]:
        """Synchronous chat completion (delegates to _sync_chat)."""
        return await self._sync_chat(user_message, session_id, user_email, user_role)

    async def parse_resume(
        self,
        raw_text: str,
        candidate_email: str | None = None,
        candidate_name: str | None = None,
    ) -> str | None:
        """
        Sends structured resume-parsing payload to the same iGentic executor URL.
        Contains 'raw_resume_text' which triggers RULE 1 in Group Chat Manager,
        routing the request directly to Resume_Parser_Agent.
        Returns the raw response text (expected to be JSON profile string).
        """
        settings = get_settings()
        if not settings.igentic_executor_url or not settings.igentic_app_id:
            logger.info("iGentic executor credentials not configured; parse_resume returning None.")
            return None

        # Build payload shaped to match RULE 1
        payload: dict[str, Any] = {"raw_resume_text": raw_text}
        if candidate_email:
            payload["candidate_email"] = candidate_email
        if candidate_name:
            payload["candidate_name"] = candidate_name

        payload_str = json.dumps(payload)

        body = {
            "userInput": payload_str,
            "UserInputType": "",
            "sessionId": "",
            "executionId": "",
            "connectionID": "",
            "isStreaming": False,
            "Username": settings.igentic_username,
        }

        headers = self._get_headers(session_id=None, accept="application/json")
        timeout = httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(settings.igentic_executor_url, json=body, headers=headers)
            if resp.status_code != 200:
                logger.error("iGentic parse_resume returned HTTP %d: %s", resp.status_code, resp.text)
                raise RuntimeError(f"iGentic executor failed with HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            result_text = data.get("Result") or data.get("result") or data.get("output") or resp.text
            if isinstance(result_text, dict):
                return json.dumps(result_text)
            return str(result_text)

    async def match_jobs(
        self,
        candidate_profile: dict[str, Any],
        open_jobs: list[dict[str, Any]],
        candidate_id: str | None = None,
    ) -> str | None:
        """
        Sends structured job-matching payload to the unified iGentic executor.
        Contains 'job_match_request' marker which triggers RULE 2 in Group Chat Manager,
        routing the request directly to Referral_Agent.
        Returns the raw response text (expected to be JSON JobMatchResponse string).
        """
        settings = get_settings()
        if not settings.igentic_executor_url or not settings.igentic_app_id:
            logger.info("iGentic executor credentials not configured; match_jobs returning None.")
            return None

        # Build payload shaped to match RULE 2
        payload: dict[str, Any] = {
            "job_match_request": {
                "candidate_profile": candidate_profile,
                "open_jobs": open_jobs,
            }
        }
        if candidate_id:
            payload["job_match_request"]["candidate_id"] = candidate_id

        payload_str = json.dumps(payload)

        body = {
            "userInput": payload_str,
            "UserInputType": "",
            "sessionId": "",
            "executionId": "",
            "connectionID": "",
            "isStreaming": False,
            "Username": settings.igentic_username,
        }

        headers = self._get_headers(session_id=None, accept="application/json")
        timeout = httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(settings.igentic_executor_url, json=body, headers=headers)
            if resp.status_code != 200:
                logger.error("iGentic match_jobs returned HTTP %d: %s", resp.status_code, resp.text)
                raise RuntimeError(f"iGentic executor failed with HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            result_text = data.get("Result") or data.get("result") or data.get("output") or resp.text
            if isinstance(result_text, dict):
                return json.dumps(result_text)
            return str(result_text)


igentic_client = IGenticClient()

