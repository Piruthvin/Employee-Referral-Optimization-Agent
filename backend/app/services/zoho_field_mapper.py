"""
Zoho Candidates field mapper.
Discovers actual Candidates module metadata at runtime via /settings/fields?module=Candidates (cached),
reconciles authoritative employee input with parsed resume data,
maps fields to exact Zoho API names, formats subforms (Experience_Details, Educational_Details),
and prevents invalid picklist values from failing record creation.
"""

import time
import asyncio
import logging
from datetime import date
from typing import Any
import httpx

from app.core.config import get_settings
from app.infrastructure.zoho_auth import zoho_auth_manager
from app.domain.resume_schema import ParsedResume

logger = logging.getLogger(__name__)


class ZohoFieldMapper:
    METADATA_CACHE_TTL = 3600  # 1 hour

    def __init__(self) -> None:
        self._cached_fields: dict[str, dict[str, Any]] = {}
        self._cache_timestamp: float = 0.0
        self._lock = asyncio.Lock()

    async def get_candidate_fields_metadata(self, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """
        Retrieves Candidates module field metadata from Zoho Recruit /settings/fields?module=Candidates.
        Returns a dictionary keyed by lowercase api_name.
        """
        now = time.time()
        if not force_refresh and self._cached_fields and (now - self._cache_timestamp) < self.METADATA_CACHE_TTL:
            return self._cached_fields

        async with self._lock:
            now = time.time()
            if not force_refresh and self._cached_fields and (now - self._cache_timestamp) < self.METADATA_CACHE_TTL:
                return self._cached_fields

            settings = get_settings()
            if not settings.zoho_client_id or not settings.zoho_refresh_token:
                logger.info("Zoho credentials not set; using default standard candidate field definitions.")
                return self._get_fallback_metadata()

            url = f"{settings.zoho_recruit_base_url.rstrip('/')}/settings/fields?module=Candidates"
            token = await zoho_auth_manager.get_access_token()
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Accept": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        fields_list = data.get("fields", [])
                        field_dict: dict[str, dict[str, Any]] = {}
                        for f in fields_list:
                            api_name = f.get("api_name")
                            if api_name:
                                field_dict[api_name.lower()] = f
                        self._cached_fields = field_dict
                        self._cache_timestamp = time.time()
                        logger.info("Fetched and cached %d Candidates fields from Zoho metadata API.", len(field_dict))
                        return self._cached_fields
                    else:
                        logger.warning("Zoho /settings/fields failed HTTP %d: %s. Using fallback metadata.", resp.status_code, resp.text)
                        return self._get_fallback_metadata()
            except Exception as e:
                logger.warning("Failed to query Zoho /settings/fields (%s). Using fallback metadata.", e)
                return self._get_fallback_metadata()

    def _get_fallback_metadata(self) -> dict[str, dict[str, Any]]:
        """Standard candidate fields fallback."""
        standard_names = [
            "First_Name", "Last_Name", "Email", "Secondary_Email", "Phone", "Mobile",
            "Current_Employer", "Current_Job_Title", "Experience_in_Years", "Experience",
            "Skill_Set", "Highest_Qualification", "Candidate_Status", "Source",
            "City", "State", "Country", "Zip_Code", "Current_Salary", "Expected_Salary",
            "Additional_Info", "Referred_By", "Referred_Date", "Referral_Score",
            "Referral_Approval_Status", "Referral_Approval_Note",
            "Experience_Details", "Educational_Details"
        ]
        return {name.lower(): {"api_name": name} for name in standard_names}

    def _find_field_name(self, candidates_meta: dict[str, dict[str, Any]], *candidates_to_try: str) -> str | None:
        """Finds the actual API name case-insensitively from available metadata."""
        for candidate in candidates_to_try:
            lowered = candidate.lower().strip()
            if lowered in candidates_meta:
                return candidates_meta[lowered].get("api_name") or candidate
        return None

    def map_to_zoho_candidate(
        self,
        authoritative_name: str,
        authoritative_email: str,
        parsed_resume: ParsedResume,
        employee_email: str,
        referral_score: float | None,
        candidates_meta: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Any], bool, str | None]:
        """
        Maps parsed resume and authoritative submission data to Zoho Recruit Candidates payload.
        Returns:
            (payload_dict, has_identity_mismatch, mismatch_details)
        """
        settings = get_settings()
        payload: dict[str, Any] = {}

        # 1. Reconcile Name and Email
        # Authoritative name splits into First_Name and Last_Name (Last_Name mandatory in Zoho)
        name_parts = authoritative_name.strip().split()
        if len(name_parts) > 1:
            first_name = " ".join(name_parts[:-1])
            last_name = name_parts[-1]
        else:
            first_name = ""
            last_name = authoritative_name.strip() or "Candidate"

        fn_field = self._find_field_name(candidates_meta, "First_Name") or "First_Name"
        ln_field = self._find_field_name(candidates_meta, "Last_Name") or "Last_Name"
        if first_name:
            payload[fn_field] = first_name
        payload[ln_field] = last_name

        # Primary Email
        email_field = self._find_field_name(candidates_meta, "Email") or "Email"
        payload[email_field] = authoritative_email.strip().lower()

        # Check identity mismatch
        has_mismatch = False
        mismatch_notes = []

        resume_email = (parsed_resume.email or "").strip().lower()
        if resume_email and resume_email != authoritative_email.strip().lower():
            has_mismatch = True
            mismatch_notes.append(f"Resume email ({resume_email}) differs from submitted email ({authoritative_email}).")
            sec_email_field = self._find_field_name(candidates_meta, "Secondary_Email") or "Secondary_Email"
            payload[sec_email_field] = resume_email

        resume_name = parsed_resume.full_name.strip()
        if resume_name and resume_name.lower() != authoritative_name.strip().lower() and resume_name != "Candidate":
            # If significant name difference
            if not all(part.lower() in resume_name.lower() for part in name_parts):
                has_mismatch = True
                mismatch_notes.append(f"Resume name ('{resume_name}') differs from submitted name ('{authoritative_name}').")

        mismatch_details = "; ".join(mismatch_notes) if mismatch_notes else None

        # 2. Contact numbers
        phone_val = parsed_resume.phone
        if phone_val:
            mobile_field = self._find_field_name(candidates_meta, "Mobile", "Phone")
            if mobile_field:
                payload[mobile_field] = phone_val

        # 3. Employment & Experience
        if parsed_resume.current_employer:
            emp_field = self._find_field_name(candidates_meta, "Current_Employer", "Employer")
            if emp_field:
                payload[emp_field] = parsed_resume.current_employer

        if parsed_resume.current_job_title:
            title_field = self._find_field_name(candidates_meta, "Current_Job_Title", "Job_Title", "Designation")
            if title_field:
                payload[title_field] = parsed_resume.current_job_title

        if parsed_resume.total_experience_years is not None:
            exp_field = self._find_field_name(candidates_meta, "Experience_in_Years", "Experience", "Total_Work_Experience")
            if exp_field:
                payload[exp_field] = float(parsed_resume.total_experience_years)

        # 4. Skills
        if parsed_resume.skills:
            skill_field = self._find_field_name(candidates_meta, "Skill_Set", "Skills")
            if skill_field:
                # Check metadata json_type
                meta_info = candidates_meta.get(skill_field.lower(), {})
                if meta_info.get("json_type") == "jsonarray":
                    payload[skill_field] = parsed_resume.skills
                else:
                    payload[skill_field] = ", ".join(parsed_resume.skills)

        # 5. Highest Qualification
        if parsed_resume.education:
            qual_field = self._find_field_name(candidates_meta, "Highest_Qualification", "Highest_Qualification_Held")
            if qual_field:
                payload[qual_field] = str(parsed_resume.education[0].degree or "")

        # 6. Address / Location
        loc = parsed_resume.location
        if loc.city:
            city_f = self._find_field_name(candidates_meta, "City")
            if city_f:
                payload[city_f] = loc.city
        if loc.state:
            state_f = self._find_field_name(candidates_meta, "State")
            if state_f:
                payload[state_f] = loc.state
        if loc.country:
            country_f = self._find_field_name(candidates_meta, "Country")
            if country_f:
                payload[country_f] = loc.country
        if loc.zip:
            zip_f = self._find_field_name(candidates_meta, "Zip_Code", "Zip", "Postal_Code")
            if zip_f:
                payload[zip_f] = loc.zip

        # 7. Subforms: Experience_Details & Educational_Details if present
        exp_subform_name = self._find_field_name(candidates_meta, "Experience_Details")
        if exp_subform_name and parsed_resume.experience:
            subform_rows = []
            for exp in parsed_resume.experience:
                row = {
                    "Company": exp.company or "",
                    "Occupation_Title": exp.job_title or "",
                    "Summary": exp.description or "",
                    "I_currently_work_here": exp.is_current,
                }
                if exp.start_date or exp.end_date:
                    row["Work_Duration"] = {
                        "from": exp.start_date or "",
                        "to": exp.end_date or ("Present" if exp.is_current else ""),
                    }
                subform_rows.append(row)
            if subform_rows:
                payload[exp_subform_name] = subform_rows

        edu_subform_name = self._find_field_name(candidates_meta, "Educational_Details")
        if edu_subform_name and parsed_resume.education:
            edu_rows = []
            for edu in parsed_resume.education:
                edu_rows.append({
                    "Institute_School": edu.institution or "",
                    "Major_Department": edu.field_of_study or "",
                    "Degree": edu.degree or "",
                    "Duration": {
                        "from": edu.start_year or "",
                        "to": edu.end_year or "",
                    }
                })
            if edu_rows:
                payload[edu_subform_name] = edu_rows

        # 8. Standard Referral Lifecycle Fields
        # Source
        source_field = self._find_field_name(candidates_meta, "Source") or "Source"
        payload[source_field] = "Employee Referral"

        # Referred_By
        referred_by_f = self._find_field_name(candidates_meta, "Referred_By") or "Referred_By"
        payload[referred_by_f] = employee_email.strip().lower()

        # Referred_Date
        referred_date_f = self._find_field_name(candidates_meta, "Referred_Date") or "Referred_Date"
        payload[referred_date_f] = date.today().isoformat()

        # Referral_Approval_Status
        approval_status_f = self._find_field_name(candidates_meta, "Referral_Approval_Status") or "Referral_Approval_Status"
        payload[approval_status_f] = "Pending"

        # Candidate_Status
        cand_status_f = self._find_field_name(candidates_meta, "Candidate_Status") or "Candidate_Status"
        payload[cand_status_f] = settings.status_on_referral

        # Referral_Score
        if referral_score is not None:
            score_f = self._find_field_name(candidates_meta, "Referral_Score") or "Referral_Score"
            payload[score_f] = round(referral_score, 1)

        # 9. Additional Info for unmapped details
        unmapped: list[str] = []
        if parsed_resume.summary:
            unmapped.append(f"Summary: {parsed_resume.summary}")
        if parsed_resume.certifications:
            unmapped.append(f"Certifications: {', '.join(parsed_resume.certifications)}")
        if parsed_resume.links.linkedin:
            unmapped.append(f"LinkedIn: {parsed_resume.links.linkedin}")
        if parsed_resume.links.github:
            unmapped.append(f"GitHub: {parsed_resume.links.github}")
        if parsed_resume.notice_period:
            unmapped.append(f"Notice Period: {parsed_resume.notice_period}")

        if unmapped:
            add_info_f = self._find_field_name(candidates_meta, "Additional_Info")
            if add_info_f:
                payload[add_info_f] = "\n".join(unmapped)[:2000]

        return payload, has_mismatch, mismatch_details


zoho_field_mapper = ZohoFieldMapper()
