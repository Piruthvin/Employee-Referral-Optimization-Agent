import json
import logging
import re
from typing import Any, Tuple

from app.core.config import get_settings
from app.domain.models import JobMatchResponse, JobMatchResult
from app.services.igentic_client import igentic_client
from app.services.resume_parser_python import TECH_SKILLS, SKILL_ALIASES

logger = logging.getLogger(__name__)


def normalize_skill(skill: str) -> str:
    """Normalizes skill using lowercase canonical aliases."""
    s = skill.strip().lower()
    return SKILL_ALIASES.get(s, skill.strip())


class JobMatchService:
    @staticmethod
    def extract_skills_from_text(text: str) -> list[str]:
        """Extracts recognized skills from job title or description text."""
        if not text:
            return []
        found: set[str] = set()
        lowered = text.lower()

        # Check aliases
        for alias, canon in SKILL_ALIASES.items():
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, lowered):
                found.add(canon)

        # Check standard dictionary
        for skill in TECH_SKILLS:
            pattern = rf"\b{re.escape(skill.lower())}\b"
            if re.search(pattern, lowered):
                found.add(skill)

        return sorted(list(found))

    @staticmethod
    def get_job_required_skills(job: dict[str, Any]) -> list[str]:
        """
        Extracts required skills from job opening object.
        Checks 'Skill_Set', 'Required_Skills', or falls back to 'Job_Description'.
        """
        raw_skills = job.get("Skill_Set") or job.get("Required_Skills") or job.get("Skills")
        if raw_skills:
            if isinstance(raw_skills, list):
                skills = [normalize_skill(str(s)) for s in raw_skills if str(s).strip()]
                if skills:
                    return list(dict.fromkeys(skills))
            elif isinstance(raw_skills, str):
                skills = [normalize_skill(s) for s in raw_skills.split(",") if s.strip()]
                if skills:
                    return list(dict.fromkeys(skills))

        # Fallback: extract from description and job title
        desc = f"{job.get('Posting_Title', '')} {job.get('Job_Description', '')} {job.get('Job_Summary', '')}"
        return JobMatchService.extract_skills_from_text(desc)

    @staticmethod
    def get_job_required_experience(job: dict[str, Any]) -> float:
        """Extracts required experience in years from job opening."""
        raw_exp = job.get("Experience") or job.get("Required_Experience") or job.get("Work_Experience")
        if raw_exp is not None:
            try:
                return float(raw_exp)
            except (ValueError, TypeError):
                match = re.search(r"(\d+(\.\d+)?)", str(raw_exp))
                if match:
                    return float(match.group(1))

        # Check description
        desc = job.get("Job_Description", "")
        match = re.search(r"(\d+)\+?\s*years?", desc, re.IGNORECASE)
        if match:
            return float(match.group(1))

        return 0.0

    @classmethod
    def match_candidate(
        cls,
        candidate_skills: list[str],
        candidate_exp_years: float | None,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Matches candidate profile against a single job opening.
        match_percent = (matched_required_skills / total_required_skills) * 100
        """
        job_id = str(job.get("id", ""))
        job_title = job.get("Posting_Title") or job.get("Job_Title") or job.get("Job_Opening_Name") or "Job Opening"
        department = job.get("Department") or job.get("Department_Name")

        required_skills = cls.get_job_required_skills(job)
        required_exp = cls.get_job_required_experience(job)

        cand_norm_skills = {normalize_skill(s).lower(): s for s in candidate_skills}

        matched_skills: list[str] = []
        missing_skills: list[str] = []

        if not required_skills:
            # If no skills specified in job description, assign a default baseline match
            match_percent = 50.0
        else:
            for req in required_skills:
                norm_req = normalize_skill(req).lower()
                if norm_req in cand_norm_skills:
                    matched_skills.append(req)
                else:
                    # Partial match heuristic
                    if any(norm_req in cs or cs in norm_req for cs in cand_norm_skills):
                        matched_skills.append(req)
                    else:
                        missing_skills.append(req)

            match_percent = (len(matched_skills) / len(required_skills)) * 100.0

        cand_exp = candidate_exp_years if candidate_exp_years is not None else 0.0
        exp_fit = cand_exp >= required_exp

        return {
            "job_id": job_id,
            "job_title": job_title,
            "department": department,
            "match_percent": round(match_percent, 1),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "experience_fit": exp_fit,
            "required_experience": required_exp,
            "candidate_experience": cand_exp,
        }

    @classmethod
    def rank_jobs_for_candidate(
        cls,
        candidate_skills: list[str],
        candidate_exp_years: float | None,
        open_jobs: list[dict[str, Any]],
        min_match: int = 0,
    ) -> list[dict[str, Any]]:
        """Matches candidate against all open jobs and returns ranked list."""
        results: list[dict[str, Any]] = []
        for job in open_jobs:
            match = cls.match_candidate(candidate_skills, candidate_exp_years, job)
            if match["match_percent"] >= min_match:
                results.append(match)

        # Sort descending by match_percent, then by experience_fit
        results.sort(key=lambda x: (x["match_percent"], x["experience_fit"]), reverse=True)
        return results

    @classmethod
    def _unmarshal_json(cls, raw_output: Any) -> Any:
        """
        Robustly parses JSON from LLM agent output.
        Handles dict/list, markdown code fences, and conversational prose.
        """
        if isinstance(raw_output, (dict, list)):
            return raw_output

        if not isinstance(raw_output, str):
            raise ValueError(f"Expected JSON string, dict, or list, got {type(raw_output).__name__}")

        cleaned = raw_output.strip()

        # 1. Strip markdown code fences if present
        if "```" in cleaned:
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
            if fence_match:
                cleaned = fence_match.group(1).strip()

        # 2. Direct JSON parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Find first JSON object or array
        obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))
            except json.JSONDecodeError:
                pass

        raise ValueError("Could not parse valid JSON from agent job matching response.")

    @classmethod
    def _validate_and_reconcile_matches(
        cls,
        data: Any,
        open_jobs: list[dict[str, Any]],
        min_match: int = 0,
    ) -> list[dict[str, Any]] | None:
        """
        Validates unmarshaled agent data against JobMatchResult schema.
        Ensures job_id, job_title, match_percent, matched_skills, missing_skills, experience_fit.
        """
        raw_items: list[Any] = []
        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            if "matches" in data and isinstance(data["matches"], list):
                raw_items = data["matches"]
            elif "ranked_jobs" in data and isinstance(data["ranked_jobs"], list):
                raw_items = data["ranked_jobs"]
            elif "job_matches" in data and isinstance(data["job_matches"], list):
                raw_items = data["job_matches"]

        if not raw_items:
            return None

        # Build lookup of open jobs by id and title
        jobs_by_id = {str(j.get("id")): j for j in open_jobs}
        jobs_by_title = {
            (j.get("Posting_Title") or j.get("Job_Title") or j.get("Job_Opening_Name") or "").strip().lower(): j
            for j in open_jobs
        }

        validated: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            job_id = str(item.get("job_id") or "")
            job_title = str(item.get("job_title") or "")

            # If job_id not directly matched, attempt match by title
            matched_job = jobs_by_id.get(job_id)
            if not matched_job and job_title:
                matched_job = jobs_by_title.get(job_title.strip().lower())
                if matched_job:
                    job_id = str(matched_job.get("id"))
                    job_title = (
                        matched_job.get("Posting_Title")
                        or matched_job.get("Job_Title")
                        or matched_job.get("Job_Opening_Name")
                        or job_title
                    )

            if not job_id and open_jobs:
                # Fallback to first open job if only 1 exists
                job_id = str(open_jobs[0].get("id"))
                if not job_title:
                    job_title = (
                        open_jobs[0].get("Posting_Title")
                        or open_jobs[0].get("Job_Title")
                        or open_jobs[0].get("Job_Opening_Name")
                        or "Job Opening"
                    )

            try:
                pct = float(item.get("match_percent") if item.get("match_percent") is not None else 50.0)
            except (ValueError, TypeError):
                pct = 50.0

            matched_skills = item.get("matched_skills")
            if not isinstance(matched_skills, list):
                matched_skills = [str(s) for s in matched_skills.split(",")] if isinstance(matched_skills, str) else []

            missing_skills = item.get("missing_skills")
            if not isinstance(missing_skills, list):
                missing_skills = [str(s) for s in missing_skills.split(",")] if isinstance(missing_skills, str) else []

            exp_fit = bool(item.get("experience_fit", True))
            dept = item.get("department")
            if not dept and matched_job:
                dept = matched_job.get("Department") or matched_job.get("Department_Name")

            result_obj = JobMatchResult(
                job_id=job_id,
                job_title=job_title or "Job Opening",
                match_percent=round(pct, 1),
                matched_skills=[str(s) for s in matched_skills],
                missing_skills=[str(s) for s in missing_skills],
                experience_fit=exp_fit,
                department=dept,
            )

            res_dict = result_obj.model_dump()
            if res_dict["match_percent"] >= min_match:
                validated.append(res_dict)

        if not validated:
            return None

        # Sort descending by match_percent, then experience_fit
        validated.sort(key=lambda x: (x["match_percent"], x["experience_fit"]), reverse=True)
        return validated

    @classmethod
    async def rank_jobs_for_candidate_agent_first(
        cls,
        candidate_skills: list[str],
        candidate_exp_years: float | None,
        open_jobs: list[dict[str, Any]],
        candidate_profile: dict[str, Any] | None = None,
        candidate_id: str | None = None,
        min_match: int = 0,
    ) -> Tuple[list[dict[str, Any]], str]:
        """
        Matches candidate against open jobs using iGentic Referral_Agent first,
        with deterministic Python matcher as fallback.

        Returns:
            (ranked_matches: list[dict[str, Any]], matcher_used: "agent" | "python" | "python_fallback")
        """
        settings = get_settings()
        mode = settings.job_match_mode.lower().strip()

        if mode == "python":
            logger.info("Using deterministic Python job matcher (mode=python).")
            res = cls.rank_jobs_for_candidate(candidate_skills, candidate_exp_years, open_jobs, min_match)
            return res, "python"

        if not open_jobs:
            return [], "agent" if mode == "agent" else "python"

        # Prepare normalized candidate profile payload
        profile_payload = dict(candidate_profile or {})
        if "skills" not in profile_payload:
            profile_payload["skills"] = candidate_skills
        if "total_experience_years" not in profile_payload:
            profile_payload["total_experience_years"] = candidate_exp_years

        # Prepare structured open jobs list for agent
        jobs_payload = []
        for j in open_jobs:
            req_skills = cls.get_job_required_skills(j)
            req_exp = cls.get_job_required_experience(j)
            title = j.get("Posting_Title") or j.get("Job_Title") or j.get("Job_Opening_Name") or "Job Opening"
            desc = j.get("Job_Description") or j.get("Job_Summary") or ""
            jobs_payload.append({
                "id": str(j.get("id", "")),
                "title": title,
                "department": j.get("Department") or j.get("Department_Name"),
                "required_skills": req_skills,
                "required_experience": req_exp,
                "description": desc[:1000] if desc else "",
            })

        if mode in ("agent", "auto"):
            if settings.igentic_executor_url and settings.igentic_app_id:
                try:
                    logger.info("Calling iGentic Referral_Agent for job matching via unified executor...")
                    raw_result = await igentic_client.match_jobs(
                        candidate_profile=profile_payload,
                        open_jobs=jobs_payload,
                        candidate_id=candidate_id,
                    )
                    if raw_result:
                        data_dict = cls._unmarshal_json(raw_result)
                        matches_list = cls._validate_and_reconcile_matches(data_dict, open_jobs, min_match)
                        if matches_list is not None:
                            logger.info(
                                "Successfully matched %d jobs via iGentic Referral_Agent (top match: %s).",
                                len(matches_list),
                                f"{matches_list[0].get('match_percent')}%" if matches_list else "None",
                            )
                            return matches_list, "agent"
                        else:
                            raise ValueError("Agent response could not be validated into JobMatchResult items.")
                except Exception as e:
                    logger.warning("Agent job matcher failed: %s", e)
                    if mode == "agent":
                        raise RuntimeError(f"iGentic Referral_Agent job match execution failed: {str(e)}") from e
            else:
                if mode == "agent":
                    raise ValueError(
                        "JOB_MATCH_MODE=agent configured but IGENTIC_EXECUTOR_URL or "
                        "IGENTIC_APP_ID is missing."
                    )
                logger.info("iGentic executor credentials not configured. Falling back to Python job matcher.")

        # Fallback to deterministic python
        logger.info("Using deterministic Python job matcher (fallback/auto).")
        fallback_res = cls.rank_jobs_for_candidate(candidate_skills, candidate_exp_years, open_jobs, min_match)
        return fallback_res, "python_fallback"


job_match_service = JobMatchService()

