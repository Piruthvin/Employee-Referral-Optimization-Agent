"""
Comprehensive Zoho Recruit API Service.
Encapsulates all interaction with Candidates, Job Openings, Attachments, Notes, and Associations.
Includes automatic token refresh, exponential backoff, rate limiting resilience, and error mapping.
"""

import time
import asyncio
import logging
from typing import Any
import urllib.parse
import httpx

from app.core.config import get_settings
from app.infrastructure.zoho_auth import zoho_auth_manager
from app.infrastructure.retry import retry_async

logger = logging.getLogger(__name__)


class ZohoService:
    def __init__(self) -> None:
        self._cached_candidates: list[dict[str, Any]] = []
        self._candidates_cache_time: float = 0.0
        self._cache_lock = asyncio.Lock()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: Any = None,
    ) -> httpx.Response:
        """Centralized authenticated HTTP request executor with automatic retry and token renewal."""
        settings = get_settings()
        url = f"{settings.zoho_recruit_base_url.rstrip('/')}/{path.lstrip('/')}"

        async def _execute() -> httpx.Response:
            token = await zoho_auth_manager.get_access_token()
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            if json_data is not None:
                headers["Content-Type"] = "application/json"

            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    files=files,
                    data=data,
                    headers=headers,
                )

                if resp.status_code == 401:
                    logger.warning("Zoho request to %s returned 401. Invalidating token and retrying...", path)
                    zoho_auth_manager.invalidate_token()
                    new_token = await zoho_auth_manager.get_access_token()
                    headers["Authorization"] = f"Zoho-oauthtoken {new_token}"
                    resp = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        files=files,
                        data=data,
                        headers=headers,
                    )

                return resp

        return await retry_async(_execute)

    # ── Candidates CRUD & Search ──────────────────────────────────────────────

    async def search_candidate_by_email(self, email: str) -> dict[str, Any] | None:
        """Searches Candidates in Zoho by email address."""
        clean_email = email.strip().lower()
        criteria = f"((Email:equals:{clean_email}))"
        encoded = urllib.parse.quote(criteria)
        path = f"Candidates/search?criteria={encoded}"

        resp = await self._request("GET", path)
        if resp.status_code == 204:
            return None
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return data[0] if data else None
        logger.warning("Candidate search by email returned HTTP %d: %s", resp.status_code, resp.text)
        return None

    async def get_candidate_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        """Fetches full candidate details by Zoho record ID."""
        path = f"Candidates/{candidate_id}"
        resp = await self._request("GET", path)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return data[0] if data else None
        return None

    async def create_candidate(self, payload: dict[str, Any]) -> str:
        """
        Creates a candidate in Zoho Recruit.
        Returns the new candidate ID.
        """
        path = "Candidates"
        body = {"data": [payload]}
        resp = await self._request("POST", path, json_data=body)

        if resp.status_code not in (200, 201):
            logger.error("Zoho candidate creation failed HTTP %d: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Zoho candidate creation failed: HTTP {resp.status_code} - {resp.text}")

        res_data = resp.json().get("data", [{}])[0]
        status = res_data.get("status")
        if status != "success":
            logger.error("Zoho candidate create returned error: %s", res_data)
            raise RuntimeError(f"Zoho create error: {res_data.get('message', 'Unknown error')}")

        cand_id = str(res_data.get("details", {}).get("id"))
        logger.info("Successfully created candidate record in Zoho Recruit. ID: %s", cand_id)
        return cand_id

    async def delete_candidate(self, candidate_id: str) -> bool:
        """Compensating rollback action: Deletes a newly created candidate."""
        path = f"Candidates?ids={candidate_id}"
        resp = await self._request("DELETE", path)
        if resp.status_code in (200, 204):
            logger.info("Compensating delete succeeded for candidate ID: %s", candidate_id)
            return True
        logger.error("Compensating candidate delete failed HTTP %d: %s", resp.status_code, resp.text)
        return False

    async def update_candidate(self, candidate_id: str, fields: dict[str, Any]) -> bool:
        """Updates specific fields on a candidate record in Zoho."""
        path = "Candidates"
        payload = {"id": candidate_id, **fields}
        body = {"data": [payload]}
        resp = await self._request("PUT", path, json_data=body)
        if resp.status_code in (200, 201):
            return True
        logger.error("Failed to update candidate %s HTTP %d: %s", candidate_id, resp.status_code, resp.text)
        return False

    async def get_candidates_by_referrer(self, referrer_email: str) -> list[dict[str, Any]]:
        """Retrieves all candidates referred by the given employee email."""
        clean_email = referrer_email.strip().lower()
        criteria = f"((Referred_By:equals:{clean_email}))"
        encoded = urllib.parse.quote(criteria)
        path = f"Candidates/search?criteria={encoded}"

        resp = await self._request("GET", path)
        if resp.status_code == 204:
            return []
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []

    async def get_all_candidates(self, page: int = 1, per_page: int = 200) -> tuple[list[dict[str, Any]], bool]:
        """Paginates all candidates from Zoho Recruit."""
        path = "Candidates"
        params = {"page": page, "per_page": per_page}
        resp = await self._request("GET", path, params=params)

        if resp.status_code == 204:
            return [], False
        if resp.status_code == 200:
            data = resp.json()
            cands = data.get("data", [])
            more = data.get("info", {}).get("more_records", False)
            return cands, more
        return [], False

    async def get_all_candidates_cached(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Cached candidate list for analytics and dashboards (60 second TTL)."""
        now = time.time()
        if not force_refresh and self._cached_candidates and (now - self._candidates_cache_time) < 60:
            return self._cached_candidates

        async with self._cache_lock:
            now = time.time()
            if not force_refresh and self._cached_candidates and (now - self._candidates_cache_time) < 60:
                return self._cached_candidates

            all_records: list[dict[str, Any]] = []
            page = 1
            while True:
                records, more = await self.get_all_candidates(page=page, per_page=200)
                if not records:
                    break
                all_records.extend(records)
                if not more:
                    break
                page += 1

            self._cached_candidates = all_records
            self._candidates_cache_time = time.time()
            return self._cached_candidates

    # ── Attachments ───────────────────────────────────────────────────────────

    async def upload_resume_attachment(self, candidate_id: str, file_bytes: bytes, filename: str) -> str:
        """
        Uploads resume attachment to Zoho Recruit Candidates attachment endpoint.
        POST /Candidates/{id}/Attachments
        """
        path = f"Candidates/{candidate_id}/Attachments"
        files = {
            "file": (filename, file_bytes, "application/octet-stream"),
        }
        resp = await self._request("POST", path, files=files)

        if resp.status_code not in (200, 201):
            logger.error("Zoho attachment upload failed HTTP %d: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Attachment upload failed: HTTP {resp.status_code} - {resp.text}")

        res_data = resp.json().get("data", [{}])[0]
        att_id = str(res_data.get("details", {}).get("id", ""))
        logger.info("Successfully attached resume to candidate %s. Attachment ID: %s", candidate_id, att_id)
        return att_id

    async def get_candidate_attachments(self, candidate_id: str) -> list[dict[str, Any]]:
        """Lists all attachments for a candidate."""
        path = f"Candidates/{candidate_id}/Attachments"
        resp = await self._request("GET", path)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []

    async def download_attachment(self, candidate_id: str, attachment_id: str) -> tuple[bytes, str]:
        """
        Downloads the attachment content from Zoho Recruit.
        Returns:
            (file_bytes, content_type)
        """
        path = f"Candidates/{candidate_id}/Attachments/{attachment_id}"
        resp = await self._request("GET", path)
        if resp.status_code == 200:
            ctype = resp.headers.get("content-type", "application/octet-stream")
            return resp.content, ctype
        raise RuntimeError(f"Attachment download failed: HTTP {resp.status_code} - {resp.text}")

    # ── Notes ─────────────────────────────────────────────────────────────────

    async def add_note(self, candidate_id: str, title: str, content: str) -> bool:
        """
        Creates a Zoho Note associated with the Candidate record.
        POST /Notes
        """
        path = "Notes"
        payload = {
            "data": [
                {
                    "Note_Title": title[:100],
                    "Note_Content": content[:5000],
                    "Parent_Id": candidate_id,
                    "se_module": "Candidates",
                }
            ]
        }
        resp = await self._request("POST", path, json_data=payload)
        if resp.status_code in (200, 201):
            return True
        logger.warning("Zoho add_note failed HTTP %d: %s", resp.status_code, resp.text)
        return False

    async def get_candidate_notes(self, candidate_id: str) -> list[dict[str, Any]]:
        """Fetches notes attached to a candidate record."""
        path = f"Candidates/{candidate_id}/Notes"
        resp = await self._request("GET", path)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []

    # ── Job Openings & Associations ───────────────────────────────────────────

    async def get_open_jobs(self) -> list[dict[str, Any]]:
        """Fetches all open/active job openings from Zoho Recruit."""
        path = "JobOpenings"
        params = {"page": 1, "per_page": 200}
        resp = await self._request("GET", path, params=params)

        if resp.status_code == 200:
            jobs = resp.json().get("data", [])
            # Filter active jobs if status is present
            active = []
            for j in jobs:
                st = (j.get("Job_Opening_Status") or j.get("Status") or "").lower()
                if not st or st in ("in-progress", "active", "open", "in progress"):
                    active.append(j)
            return active or jobs
        return []

    async def associate_candidate_to_job(self, candidate_id: str, job_id: str) -> bool:
        """
        Associates a candidate with a specific job opening in Zoho Recruit.
        PUT /Candidates/actions/associate
        Payload: {"data": [{"jobids": [job_id], "ids": [candidate_id]}]}
        """
        path = "Candidates/actions/associate"
        payload = {
            "data": [
                {
                    "jobids": [str(job_id)],
                    "ids": [str(candidate_id)],
                }
            ]
        }
        resp = await self._request("PUT", path, json_data=payload)
        if resp.status_code in (200, 201):
            logger.info("Successfully associated candidate %s to job %s.", candidate_id, job_id)
            return True
        logger.warning("Failed to associate candidate %s to job %s: HTTP %d %s", candidate_id, job_id, resp.status_code, resp.text)
        return False


zoho_service = ZohoService()
