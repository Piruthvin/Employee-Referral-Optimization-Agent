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
from app.domain.exceptions import ZohoValidationError, ZohoTransportError

logger = logging.getLogger(__name__)


class ZohoService:
    def __init__(self) -> None:
        self._cached_candidates: list[dict[str, Any]] = []
        self._candidates_cache_time: float = 0.0
        self._cache_lock = asyncio.Lock()
        self.search_source: str = "live"
        self._referrer_candidates_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._referrer_cache_ttl: float = 45.0

    def invalidate_cache(self) -> None:
        """Invalidates candidate and referrer caches immediately on write."""
        self._cached_candidates = []
        self._candidates_cache_time = 0.0
        self._referrer_candidates_cache.clear()
        logger.debug("Zoho candidates and referrer search cache invalidated.")

    def _inspect_write_response(self, resp: httpx.Response, action_description: str) -> dict[str, Any]:
        """
        Validates Zoho Recruit v2 write response.
        Zoho Recruit v2 returns HTTP 200, 201, or 202 as transport acceptance,
        with per-record results in resp.json()['data'][0].
        Raises ZohoValidationError on schema/data error, or ZohoTransportError on transport failure.
        """
        if resp.status_code not in (200, 201, 202):
            logger.error("Zoho %s transport failed HTTP %d: %s", action_description, resp.status_code, resp.text)
            status_code = 502 if resp.status_code >= 500 else resp.status_code
            raise ZohoTransportError(f"Zoho {action_description} failed: HTTP {resp.status_code} - {resp.text}", status_code=status_code)

        try:
            body = resp.json()
        except Exception:
            return {}

        data_list = body.get("data", [])
        if not data_list or not isinstance(data_list, list):
            return body

        first_record = data_list[0]
        rec_status = first_record.get("status")
        if rec_status == "error":
            code = first_record.get("code", "ERROR")
            message = first_record.get("message", "Zoho record write rejected")
            details = first_record.get("details", {})
            logger.error("Zoho %s returned record error: %s", action_description, first_record)
            raise ZohoValidationError(code=code, message=message, details=details)

        return first_record

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
        Accepts HTTP 200, 201, and 202 as accepted transport, then inspects data[0].status.
        Raises ZohoValidationError on record error, or returns the new candidate ID.
        """
        path = "Candidates"
        body = {"data": [payload]}
        resp = await self._request("POST", path, json_data=body)

        record = self._inspect_write_response(resp, "candidate creation")
        cand_id = str(record.get("details", {}).get("id") or record.get("id") or "")
        if not cand_id:
            raise ZohoValidationError(
                code="MISSING_RECORD_ID",
                message="Zoho accepted candidate creation but returned no record ID",
                details=record,
            )

        self.invalidate_cache()
        logger.info("Successfully created candidate record in Zoho Recruit. ID: %s", cand_id)
        return cand_id

    async def delete_candidate(self, candidate_id: str) -> bool:
        """Compensating rollback action: Deletes a newly created candidate."""
        path = f"Candidates?ids={candidate_id}"
        resp = await self._request("DELETE", path)
        if resp.status_code in (200, 204):
            self.invalidate_cache()
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
        self._inspect_write_response(resp, f"candidate update {candidate_id}")
        self.invalidate_cache()
        return True

    async def get_candidates_by_referrer(self, referrer_email: str) -> list[dict[str, Any]]:
        """
        Retrieves all candidates referred by the given employee email.

        Hierarchy:
        1. Primary targeted search: ((Referred_By:equals:{clean_email}))
           Zoho Recruit criteria search when custom Referred_By field is enabled.
        2. Secondary targeted search: ((Additional_Info:contains:{clean_email}))
           Zoho Recruit native text field searchable via criteria, returns HTTP 200.
        3. Genuine fallback: Filter cached candidate list.
           Logs visible WARNING and sets search_source = "fallback".
        Caches results for 45s across bursts of dashboard queries, invalidated on write.
        """
        clean_email = referrer_email.strip().lower()
        now = time.time()

        if clean_email in self._referrer_candidates_cache:
            cache_ts, cached_list = self._referrer_candidates_cache[clean_email]
            if (now - cache_ts) < self._referrer_cache_ttl:
                return cached_list

        # Path 1: Primary search by Referred_By
        try:
            crit1 = f"((Referred_By:equals:{clean_email}))"
            enc1 = urllib.parse.quote(crit1)
            resp1 = await self._request("GET", f"Candidates/search?criteria={enc1}")
            if resp1.status_code == 200:
                self.search_source = "live"
                data = resp1.json().get("data", [])
                self._referrer_candidates_cache[clean_email] = (now, data)
                return data
            if resp1.status_code == 204:
                self.search_source = "live"
                self._referrer_candidates_cache[clean_email] = (now, [])
                return []
        except Exception as e:
            logger.debug("Primary search criteria check error: %s", e)

        # Path 2: Secondary targeted live search by Additional_Info
        try:
            crit2 = f"((Additional_Info:contains:{clean_email}))"
            enc2 = urllib.parse.quote(crit2)
            resp2 = await self._request("GET", f"Candidates/search?criteria={enc2}")
            if resp2.status_code == 200:
                self.search_source = "live"
                data = resp2.json().get("data", [])
                self._referrer_candidates_cache[clean_email] = (now, data)
                return data
            if resp2.status_code == 204:
                self.search_source = "live"
                self._referrer_candidates_cache[clean_email] = (now, [])
                return []
        except Exception as e:
            logger.debug("Secondary search criteria check error: %s", e)

        # Path 3: Genuine fallback (filtered cached candidate list)
        self.search_source = "fallback"
        logger.warning(
            "Zoho /Candidates/search by Referred_By returned HTTP %s and Additional_Info returned HTTP %s. "
            "Using filtered cached candidate list fallback for %s.",
            getattr(locals().get("resp1"), "status_code", "ERR"),
            getattr(locals().get("resp2"), "status_code", "ERR"),
            clean_email,
        )
        all_candidates = await self.get_all_candidates_cached()
        matched: list[dict[str, Any]] = []
        for c in all_candidates:
            ref_by = str(c.get("Referred_By") or "").strip().lower()
            emp_lookup = str(c.get("Referred_by_Employee__s") or "").strip().lower()
            source = str(c.get("Source") or "").strip().lower()
            add_info = str(c.get("Additional_Info") or "").strip().lower()
            if clean_email in ref_by or clean_email in emp_lookup or clean_email in source or clean_email in add_info:
                matched.append(c)

        self._referrer_candidates_cache[clean_email] = (now, matched)
        return matched

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
        params = {"attachments_category": "Resume"}
        resp = await self._request("POST", path, params=params, files=files)
        record = self._inspect_write_response(resp, f"resume upload for candidate {candidate_id}")
        att_id = str(record.get("details", {}).get("id") or record.get("id") or "")
        self.invalidate_cache()
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
        try:
            self._inspect_write_response(resp, f"add note to candidate {candidate_id}")
            self.invalidate_cache()
            return True
        except Exception as e:
            logger.warning("Zoho add_note for candidate %s failed: %s", candidate_id, e)
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
        try:
            self._inspect_write_response(resp, f"associate candidate {candidate_id} to job {job_id}")
            self.invalidate_cache()
            logger.info("Successfully associated candidate %s to job %s.", candidate_id, job_id)
            return True
        except Exception as e:
            logger.warning("Failed to associate candidate %s to job %s: %s", candidate_id, job_id, e)
            return False


zoho_service = ZohoService()
