"""
Deterministic Python resume parser.
Uses regular expressions, section header heuristics, date-range calculations,
and a comprehensive skill dictionary to structure raw resume text into JSON.
"""

import re
from typing import Any
from datetime import datetime

# ── Comprehensive Skill Dictionary (~200+ skills + common aliases) ─────────────

SKILL_ALIASES: dict[str, str] = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node": "Node.js",
    "vuejs": "Vue.js",
    "vue": "Vue.js",
    "angularjs": "Angular",
    "angular": "Angular",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "docker": "Docker",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "ms sql": "SQL Server",
    "sql server": "SQL Server",
    "golang": "Go",
    "c#": "C#",
    "c++": "C++",
    "rest": "REST API",
    "restful": "REST API",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "NLP",
    "genai": "Generative AI",
    "generative ai": "Generative AI",
    "llm": "LLMs",
    "llms": "LLMs",
}

TECH_SKILLS: list[str] = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "Go", "Rust", "Ruby", "PHP",
    "Swift", "Kotlin", "Scala", "Dart", "HTML", "CSS", "SQL", "Bash", "Shell", "R",
    # Frameworks & Libraries
    "FastAPI", "Django", "Flask", "React", "Next.js", "Vue.js", "Angular", "Express",
    "Node.js", "Spring Boot", ".NET", ".NET Core", "ASP.NET", "NestJS", "PyTorch",
    "TensorFlow", "Keras", "Scikit-Learn", "Pandas", "NumPy", "Tailwind CSS", "Bootstrap",
    # Cloud & DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible", "Helm",
    "Jenkins", "GitHub Actions", "GitLab CI", "CI/CD", "Prometheus", "Grafana",
    "Linux", "Nginx", "Apache", "Serverless",
    # Databases & Caching
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "DynamoDB", "Cassandra",
    "SQLite", "Oracle", "SQL Server", "Snowflake", "BigQuery", "Firebase",
    # Architecture & Tools
    "REST API", "GraphQL", "Microservices", "Kafka", "RabbitMQ", "Celery", "gRPC",
    "Git", "GitHub", "GitLab", "Jira", "Confluence", "Postman", "Swagger", "OpenAPI",
    # AI & Data
    "Machine Learning", "Deep Learning", "NLP", "Generative AI", "LLMs", "LangChain",
    "Data Analysis", "Data Engineering", "Data Modeling", "ETL", "Spark",
    # Methodologies & Soft Skills
    "Agile", "Scrum", "TDD", "BDD", "Code Review", "System Design", "Unit Testing",
]

SECTION_HEADERS: dict[str, list[str]] = {
    "summary": [
        "summary", "professional summary", "about me", "profile", "overview",
        "career objective", "objective", "executive summary"
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "technologies",
        "tech stack", "tools & technologies", "key skills", "proficiencies"
    ],
    "experience": [
        "experience", "work experience", "employment history", "professional experience",
        "work history", "relevant experience", "career history"
    ],
    "education": [
        "education", "academic background", "educational qualifications",
        "qualifications", "academic credentials", "degrees"
    ],
    "certifications": [
        "certifications", "certificates", "licenses", "certifications & licenses",
        "courses", "professional credentials"
    ],
    "languages": [
        "languages", "languages spoken", "language proficiencies"
    ],
}


class PythonResumeParser:
    @classmethod
    def parse(cls, text: str) -> dict[str, Any]:
        """Parses raw text into structured resume dictionary."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        email = cls._extract_email(text)
        phone = cls._extract_phone(text)
        links = cls._extract_links(text)
        sections = cls._segment_sections(lines)

        full_name = cls._extract_name(lines, email, sections)
        skills = cls._extract_skills(text, sections.get("skills", ""))
        experience, current_emp, current_title = cls._extract_experience(sections.get("experience", ""))
        education = cls._extract_education(sections.get("education", ""))
        certifications = cls._extract_certifications(sections.get("certifications", ""))
        languages = cls._extract_languages(sections.get("languages", ""))
        total_exp = cls._calculate_total_experience(text, experience)
        summary = cls._extract_summary(sections.get("summary", ""), lines)
        location = cls._extract_location(text)

        return {
            "full_name": full_name or "Candidate",
            "email": email,
            "alternate_email": None,
            "phone": phone,
            "alternate_phone": None,
            "headline": current_title or (skills[0] + " Specialist" if skills else None),
            "summary": summary,
            "total_experience_years": total_exp,
            "current_employer": current_emp,
            "current_job_title": current_title,
            "current_salary": None,
            "expected_salary": None,
            "notice_period": cls._extract_notice_period(text),
            "location": location,
            "skills": skills,
            "education": education,
            "experience": experience,
            "certifications": certifications,
            "languages": languages,
            "links": links,
            "other_details": None,
        }

    @staticmethod
    def _extract_email(text: str) -> str | None:
        pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        match = re.search(pattern, text)
        return match.group(0).lower() if match else None

    @staticmethod
    def _extract_phone(text: str) -> str | None:
        # Match standard phone numbers with optional + country code
        pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        match = re.search(pattern, text)
        if match:
            clean = re.sub(r"[^\d+]", "", match.group(0))
            if len(clean) >= 10:
                return match.group(0).strip()
        return None

    @staticmethod
    def _extract_links(text: str) -> dict[str, Any]:
        links: dict[str, Any] = {"linkedin": None, "github": None, "portfolio": None, "other": []}
        # LinkedIn
        li_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if li_match:
            links["linkedin"] = f"https://linkedin.com/in/{li_match.group(1)}"

        # GitHub
        gh_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if gh_match:
            links["github"] = f"https://github.com/{gh_match.group(1)}"

        # URLs general
        url_matches = re.findall(r"https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?", text)
        for u in url_matches:
            if "linkedin.com" in u or "github.com" in u:
                continue
            if not links["portfolio"]:
                links["portfolio"] = u
            elif u not in links["other"]:
                links["other"].append(u)

        return links

    @classmethod
    def _segment_sections(cls, lines: list[str]) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_section: str | None = None

        for line in lines:
            line_clean = line.strip().lower().rstrip(":")
            found_header = None
            for sec_name, headers in SECTION_HEADERS.items():
                if line_clean in headers:
                    found_header = sec_name
                    break

            if found_header:
                current_section = found_header
                if current_section not in sections:
                    sections[current_section] = []
            elif current_section:
                sections[current_section].append(line)

        return {k: "\n".join(v) for k, v in sections.items()}

    @staticmethod
    def _extract_name(lines: list[str], email: str | None, sections: dict[str, str]) -> str:
        for line in lines[:5]:
            # Skip lines with email or phone or URLs
            if email and email in line.lower():
                continue
            if "@" in line or "http" in line or re.search(r"\d{4,}", line):
                continue
            # If line is 2 to 4 capitalized words
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() or w[0].isalpha() for w in words if w):
                return line.strip()
        # Fallback to email username or first line
        if lines:
            return lines[0].strip()
        return "Candidate"

    @classmethod
    def _extract_skills(cls, full_text: str, skills_section: str) -> list[str]:
        found: set[str] = set()

        # 1. Look in skills section with high priority
        text_to_search = f"{skills_section}\n{full_text}"
        lowered = text_to_search.lower()

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

        # Preserve canonical casing
        return sorted(list(found))

    @staticmethod
    def _extract_experience(exp_text: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
        items: list[dict[str, Any]] = []
        current_employer: str | None = None
        current_job_title: str | None = None

        if not exp_text:
            return items, current_employer, current_job_title

        blocks = exp_text.split("\n\n")
        date_pattern = r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?(?:\d{4}|\d{2}/\d{4})\s*(?:-|–|to)\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?(?:\d{4}|\d{2}/\d{4}|present|current)"

        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            match = re.search(date_pattern, block, re.IGNORECASE)
            date_str = match.group(0) if match else None
            is_cur = bool(re.search(r"present|current", block, re.IGNORECASE))

            title = lines[0][:150]
            company = lines[1][:150] if len(lines) > 1 else None

            if is_cur and not current_employer and company:
                current_employer = company
                current_job_title = title

            desc = "\n".join(lines[2:]) if len(lines) > 2 else None
            items.append({
                "job_title": title,
                "company": company,
                "start_date": date_str.split("-")[0].strip() if date_str and "-" in date_str else date_str,
                "end_date": date_str.split("-")[1].strip() if date_str and "-" in date_str else ("Present" if is_cur else None),
                "is_current": is_cur,
                "location": None,
                "description": desc[:1500] if desc else None,
            })

        if items and not current_employer:
            current_employer = items[0].get("company")
            current_job_title = items[0].get("job_title")

        return items[:10], current_employer, current_job_title

    @staticmethod
    def _extract_education(edu_text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not edu_text:
            return items

        lines = [l.strip() for l in edu_text.splitlines() if l.strip()]
        for line in lines:
            degree = None
            for deg_keyword in ["bachelor", "master", "phd", "b.tech", "m.tech", "b.e", "m.e", "b.sc", "m.sc", "bca", "mca", "mba"]:
                if deg_keyword in line.lower():
                    degree = line[:150]
                    break

            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
            year = year_match.group(0) if year_match else None

            if degree or year:
                items.append({
                    "degree": degree or line[:150],
                    "field_of_study": None,
                    "institution": line[:150],
                    "start_year": None,
                    "end_year": year,
                    "grade": None,
                })
        return items[:5]

    @staticmethod
    def _extract_certifications(cert_text: str) -> list[str]:
        if not cert_text:
            return []
        lines = [l.strip().lstrip("•-* ") for l in cert_text.splitlines() if l.strip()]
        return [l[:150] for l in lines[:10]]

    @staticmethod
    def _extract_languages(lang_text: str) -> list[str]:
        common = ["English", "Hindi", "Tamil", "Telugu", "Kannada", "Spanish", "French", "German", "Mandarin"]
        found = []
        lowered = lang_text.lower()
        for lang in common:
            if lang.lower() in lowered:
                found.append(lang)
        return found or ["English"]

    @staticmethod
    def _calculate_total_experience(text: str, experience: list[dict[str, Any]]) -> float | None:
        # Check explicit mention e.g., "5+ years of experience"
        match = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?\s*(?:of\s*)?experience", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        # Calculate from years mentioned in experience items
        years_found: set[int] = set()
        for exp in experience:
            for field in [exp.get("start_date"), exp.get("end_date")]:
                if field:
                    y_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(field))
                    if y_match:
                        years_found.add(int(y_match.group(1)))

        if len(years_found) >= 2:
            span = max(years_found) - min(years_found)
            return float(min(span, 40))

        return 2.0  # Safe default if undetermined

    @staticmethod
    def _extract_summary(summary_text: str, all_lines: list[str]) -> str | None:
        if summary_text:
            return summary_text[:2000].strip()
        # Look for intro paragraph
        for line in all_lines[1:5]:
            if len(line) > 60:
                return line[:1000].strip()
        return None

    @staticmethod
    def _extract_location(text: str) -> dict[str, Any]:
        # Simple city/country heuristic
        indian_cities = ["Bangalore", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Mumbai", "Delhi", "Noida", "Gurgaon"]
        for city in indian_cities:
            if re.search(rf"\b{city}\b", text, re.IGNORECASE):
                return {"city": city, "state": None, "country": "India", "street": None, "zip": None}
        return {"city": None, "state": None, "country": None, "street": None, "zip": None}

    @staticmethod
    def _extract_notice_period(text: str) -> str | None:
        match = re.search(r"(?:notice\s*period\s*:?\s*)(\d+\s*(?:days?|months?)|immediate)", text, re.IGNORECASE)
        return match.group(1).strip() if match else None


python_resume_parser = PythonResumeParser()
