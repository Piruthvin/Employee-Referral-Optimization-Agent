"""
Domain Pydantic schema for structured parsed resumes.
Treats resume content as untrusted data: trims lengths, coerces types, and drops unknown keys.
"""

from typing import Any
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ResumeLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    street: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zip: str | None = None

    @field_validator("street", "city", "state", "country", "zip", mode="before")
    @classmethod
    def trim_string(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s[:100] if s else None


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    degree: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    start_year: str | None = None
    end_year: str | None = None
    grade: str | None = None

    @field_validator("degree", "field_of_study", "institution", "start_year", "end_year", "grade", mode="before")
    @classmethod
    def clean_str(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s[:150] if s else None


class ExperienceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    location: str | None = None
    description: str | None = None

    @field_validator("job_title", "company", "start_date", "end_date", "location", mode="before")
    @classmethod
    def clean_short_str(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s[:200] if s else None

    @field_validator("description", mode="before")
    @classmethod
    def clean_desc(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s[:2000] if s else None

    @field_validator("is_current", mode="before")
    @classmethod
    def clean_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "current", "present")
        return False


class ResumeLinks(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)

    @field_validator("linkedin", "github", "portfolio", mode="before")
    @classmethod
    def clean_link(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s[:300] if s else None

    @field_validator("other", mode="before")
    @classmethod
    def clean_other(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, list):
            return [str(x).strip()[:300] for x in v if str(x).strip()]
        return [str(v).strip()[:300]]


class ParsedResume(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(default="", description="Candidate full name")
    email: str | None = None
    alternate_email: str | None = None
    phone: str | None = None
    alternate_phone: str | None = None
    headline: str | None = None
    summary: str | None = None
    total_experience_years: float | None = None
    current_employer: str | None = None
    current_job_title: str | None = None
    current_salary: str | float | None = None
    expected_salary: str | float | None = None
    notice_period: str | None = None
    location: ResumeLocation = Field(default_factory=ResumeLocation)
    skills: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    links: ResumeLinks = Field(default_factory=ResumeLinks)
    other_details: str | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_name(cls, v: Any) -> str:
        if not v:
            return "Candidate"
        s = str(v).strip()
        return s[:150] or "Candidate"

    @field_validator("email", "alternate_email", mode="before")
    @classmethod
    def clean_email(cls, v: Any) -> str | None:
        if not v:
            return None
        s = str(v).strip().lower()
        # Basic validation
        if "@" in s and "." in s:
            return s[:150]
        return None

    @field_validator("phone", "alternate_phone", mode="before")
    @classmethod
    def clean_phone(cls, v: Any) -> str | None:
        if not v:
            return None
        s = str(v).strip()
        # Remove unwanted punctuation
        cleaned = re.sub(r"[^\d+\-() ]", "", s)
        return cleaned[:50] if cleaned else None

    @field_validator("total_experience_years", mode="before")
    @classmethod
    def clean_exp(cls, v: Any) -> float | None:
        if v is None:
            return None
        try:
            val = float(v)
            return round(val, 1) if val >= 0 else 0.0
        except (ValueError, TypeError):
            # Attempt regex extraction (e.g. "5 years")
            if isinstance(v, str):
                match = re.search(r"(\d+(\.\d+)?)", v)
                if match:
                    try:
                        return round(float(match.group(1)), 1)
                    except ValueError:
                        pass
            return None

    @field_validator("skills", "certifications", "languages", mode="before")
    @classmethod
    def clean_string_list(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, str):
            items = [s.strip() for s in v.split(",") if s.strip()]
            return items[:100]
        if isinstance(v, list):
            res: list[str] = []
            for item in v:
                if item and isinstance(item, str) and item.strip():
                    clean_item = item.strip()[:100]
                    if clean_item not in res:
                        res.append(clean_item)
            return res[:100]
        return []

    @field_validator("summary", "headline", "other_details", mode="before")
    @classmethod
    def clean_text(cls, v: Any) -> str | None:
        if not v:
            return None
        s = str(v).strip()
        return s[:3000] if s else None

    @field_validator("current_employer", "current_job_title", "notice_period", mode="before")
    @classmethod
    def clean_short(cls, v: Any) -> str | None:
        if not v:
            return None
        s = str(v).strip()
        return s[:150] if s else None
