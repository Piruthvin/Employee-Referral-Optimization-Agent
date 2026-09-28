"""
Deterministic Python Job Matching Service.
Matches parsed candidate skills and experience against active Zoho Recruit job openings.
Calculates match percentage, matched skills, missing skills, and experience fit.
"""

import re
from typing import Any
from app.services.resume_parser_python import TECH_SKILLS, SKILL_ALIASES


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


job_match_service = JobMatchService()
