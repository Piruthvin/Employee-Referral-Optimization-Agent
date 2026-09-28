"""
Tests for resume intake, validation, extraction, parsing, and field mapping:
- File format, size, magic bytes, and scanned document thresholds
- PDF and DOCX text extraction
- Deterministic Python parser on 3 distinct resume profiles
- Parser agent failure/timeout fallback to Python parser
- Runtime Zoho Candidates field mapping with subforms and identity reconciliation
"""

import io
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import UploadFile, HTTPException
import pypdf
import docx

from app.services.resume_extract_service import resume_extract_service
from app.services.resume_parser_python import python_resume_parser
from app.services.resume_parser_service import resume_parser_service
from app.services.zoho_field_mapper import zoho_field_mapper
from app.domain.resume_schema import ParsedResume


def _create_minimal_pdf_bytes(text: str) -> bytes:
    """Creates a valid PDF binary byte string containing the given text."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Use annotation or text if supported, or write minimal PDF stream
    buf = io.BytesIO()
    writer.write(buf)
    # Simple valid PDF with text in stream
    pdf_content = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length " + str(len(text) + 20).encode() + b">>stream\nBT /F1 12 Tf 50 700 Td ("
        + text.encode("ascii", "replace")
        + b") Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000216 00000 n \ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n320\n%%EOF"
    )
    return pdf_content


def _create_minimal_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Sample Resumes ─────────────────────────────────────────────────────────────

SAMPLE_RESUME_DEV = """
Johnathan Developer
Email: john.dev@example.com | Phone: +91-9876543210 | Bangalore, India
LinkedIn: linkedin.com/in/johndev | GitHub: github.com/johndev

SUMMARY
Experienced Full Stack Python Engineer with 4.5 years of experience building high-throughput microservices and responsive web applications. Specialized in FastAPI, React, and cloud containerization.

SKILLS
Python, FastAPI, Django, JavaScript, TypeScript, React, Docker, Kubernetes, PostgreSQL, Redis, AWS, REST API, Git, CI/CD

PROFESSIONAL EXPERIENCE
Senior Backend Engineer | Acme Tech Solutions
Jan 2022 - Present | Bangalore
• Architected event-driven microservices using FastAPI and Redis.
• Deployed scalable services on AWS EKS using Kubernetes and Docker.

Software Engineer | Beta Corp
July 2019 - Dec 2021 | Hyderabad
• Developed core REST APIs with Django and PostgreSQL.

EDUCATION
Bachelor of Technology in Computer Science
Bangalore Institute of Technology, 2019
"""

SAMPLE_RESUME_DEVOPS = """
Sarah Jenkins
Email: sarah.devops@cloudnet.io | Phone: (555) 345-6789
Location: Pune, India | GitHub: github.com/sjenkins

PROFESSIONAL SUMMARY
Senior Cloud & DevOps Architect with 10+ years of experience leading multi-cloud infrastructure transformations. Expert in Kubernetes, Terraform, AWS, and secure CI/CD pipelines.

TECHNICAL SKILLS
AWS, Azure, GCP, Docker, Kubernetes, Terraform, Ansible, Linux, Python, Bash, CI/CD, GitHub Actions, Prometheus, Grafana, Microservices

WORK EXPERIENCE
Principal Cloud Architect | CloudNet Systems
2020 - Present
• Designed infrastructure as code across multi-region AWS and Azure environments using Terraform.
• Orchestrated zero-downtime Kubernetes deployments across 40+ microservices.

Lead DevOps Engineer | Enterprise Global
2014 - 2020
• Built enterprise automated CI/CD pipelines using GitHub Actions and Ansible.

EDUCATION
Master of Science in Information Technology
Pune University, 2014
"""

SAMPLE_RESUME_PM = """
Michael Vance
Email: mvance.product@example.com | Phone: +1-202-555-0143
LinkedIn: linkedin.com/in/michaelvance

SUMMARY
Senior Product Manager with 6 years of experience driving B2B SaaS products from conception through scaled adoption. Skilled in Agile roadmaps, backlog grooming, and data analytics.

CORE COMPETENCIES
Agile, Scrum, Product Roadmaps, Jira, Confluence, Data Analysis, SQL, System Design, User Testing

EXPERIENCE
Senior Product Manager | InnovateX
March 2021 - Present
• Led cross-functional engineering and design pods using Scrum and Jira.
• Defined product feature specifications and tracked user engagement metrics.

Product Specialist | Digital Works
2018 - 2021
• Managed product backlog and user interview feedback loops.

EDUCATION
Bachelor of Business Administration
Mumbai University, 2018
"""


@pytest.mark.asyncio
async def test_resume_validation_wrong_file_type():
    file = UploadFile(filename="resume.txt", file=io.BytesIO(b"simple text content"))
    with pytest.raises(HTTPException) as exc:
        await resume_extract_service.validate_and_extract(file)
    assert exc.value.status_code == 400
    assert "Only PDF (.pdf) and Word (.docx) documents are accepted" in exc.value.detail


@pytest.mark.asyncio
async def test_resume_validation_oversized_file():
    # 6MB dummy content
    big_content = b"%PDF" + (b"0" * (6 * 1024 * 1024))
    file = UploadFile(filename="resume.pdf", file=io.BytesIO(big_content))
    with pytest.raises(HTTPException) as exc:
        await resume_extract_service.validate_and_extract(file)
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_resume_validation_fake_pdf():
    # PDF extension but invalid magic bytes
    file = UploadFile(filename="resume.pdf", file=io.BytesIO(b"NOT A REAL PDF HEADER 12345"))
    with pytest.raises(HTTPException) as exc:
        await resume_extract_service.validate_and_extract(file)
    assert exc.value.status_code == 400
    assert "File header does not match a valid PDF document" in exc.value.detail


@pytest.mark.asyncio
async def test_resume_validation_scanned_pdf():
    # Valid PDF magic bytes but under 200 characters of text
    short_text = "Short text under 200 characters."
    pdf_bytes = _create_minimal_pdf_bytes(short_text)
    file = UploadFile(filename="scanned.pdf", file=io.BytesIO(pdf_bytes))
    with pytest.raises(HTTPException) as exc:
        await resume_extract_service.validate_and_extract(file)
    assert exc.value.status_code == 422
    assert "Text-based resume required" in exc.value.detail


@pytest.mark.asyncio
async def test_docx_extraction_success():
    paragraphs = [
        "Jane Doe Resume",
        "Email: jane.doe@example.com | Phone: 9876543210",
        "SUMMARY: Experienced software engineer with over 5 years of background.",
        "SKILLS: Python, FastAPI, React, Docker, SQL, PostgreSQL, AWS.",
        "EXPERIENCE: Software Architect at CloudCorp from 2020 to 2025. Built microservices.",
        "EDUCATION: Bachelor of Science in Engineering, 2020.",
        "Extra line to ensure text length exceeds the 200 character threshold required for scanned checks.",
    ]
    docx_bytes = _create_minimal_docx_bytes(paragraphs)
    file = UploadFile(filename="resume.docx", file=io.BytesIO(docx_bytes))
    text, raw_bytes = await resume_extract_service.validate_and_extract(file)
    assert len(text) >= 200
    assert "Jane Doe Resume" in text
    assert "FastAPI" in text


def test_python_parser_on_3_sample_resumes():
    """Tests deterministic Python parser across 3 distinct job profiles."""
    # 1. Developer
    res_dev = python_resume_parser.parse(SAMPLE_RESUME_DEV)
    assert "Johnathan" in res_dev["full_name"]
    assert res_dev["email"] == "john.dev@example.com"
    assert "FastAPI" in res_dev["skills"]
    assert "Python" in res_dev["skills"]
    assert "Docker" in res_dev["skills"]
    assert res_dev["total_experience_years"] is not None
    assert res_dev["location"]["city"] == "Bangalore"

    # 2. DevOps
    res_ops = python_resume_parser.parse(SAMPLE_RESUME_DEVOPS)
    assert "Sarah" in res_ops["full_name"]
    assert res_ops["email"] == "sarah.devops@cloudnet.io"
    assert "Kubernetes" in res_ops["skills"]
    assert "Terraform" in res_ops["skills"]
    assert res_ops["total_experience_years"] is not None

    # 3. Product Manager
    res_pm = python_resume_parser.parse(SAMPLE_RESUME_PM)
    assert "Michael" in res_pm["full_name"]
    assert "Agile" in res_pm["skills"]
    assert "Scrum" in res_pm["skills"]
    assert "Jira" in res_pm["skills"]


@pytest.mark.asyncio
async def test_parser_agent_success():
    """Agent parser returns structured profile matching ParsedResume schema."""
    from app.core.config import get_settings
    settings = get_settings()
    settings.igentic_parser_executor_url = "https://mock-executor.ai/agent"
    settings.igentic_parser_app_id = "mock-parser-app"

    agent_output = {
        "full_name": "Alice Smith",
        "email": "alice@test.com",
        "phone": "555-123-4567",
        "skills": ["Python", "FastAPI"],
        "total_experience_years": 3.0,
        "education": [],
        "experience": [],
    }
    with patch.object(resume_parser_service, "_call_agent_parser", AsyncMock(return_value=agent_output)):
        parsed, used = await resume_parser_service.parse_resume("Raw resume text for Alice Smith with skills...")
        assert used == "agent"
        assert parsed.full_name == "Alice Smith"
        assert parsed.email == "alice@test.com"


@pytest.mark.asyncio
async def test_parser_agent_fallback_on_error():
    """When agent parser times out or errors, auto mode falls back to Python parser."""
    with patch.object(resume_parser_service, "_call_agent_parser", AsyncMock(side_effect=TimeoutError("Timeout"))):
        parsed, used = await resume_parser_service.parse_resume(SAMPLE_RESUME_DEV)
        assert used == "python"
        assert parsed.email == "john.dev@example.com"
        assert "FastAPI" in parsed.skills


def test_zoho_field_mapper_reconciliation_and_metadata():
    """Verifies field mapping, picklist safety, subform packing, and identity mismatch alerts."""
    parsed = ParsedResume(
        full_name="John Resume Name",
        email="resume.email@example.com",
        phone="9876543210",
        skills=["Python", "FastAPI", "Docker"],
        total_experience_years=4.5,
        current_employer="Tech Corp",
        current_job_title="Lead Architect",
        location={"city": "Bangalore", "country": "India"},
        experience=[
            {
                "job_title": "Developer",
                "company": "Prev Co",
                "start_date": "2020",
                "end_date": "2022",
                "is_current": False,
                "description": "Built APIs",
            }
        ],
    )

    mock_metadata = zoho_field_mapper._get_fallback_metadata()

    payload, has_mismatch, mismatch_details = zoho_field_mapper.map_to_zoho_candidate(
        authoritative_name="Authoritative Name",
        authoritative_email="authoritative.email@company.com",
        parsed_resume=parsed,
        employee_email="referrer@company.com",
        referral_score=85.0,
        candidates_meta=mock_metadata,
    )

    # Name and email must adhere to authoritative employee submission
    assert payload["First_Name"] == "Authoritative"
    assert payload["Last_Name"] == "Name"
    assert payload["Email"] == "authoritative.email@company.com"
    assert payload["Secondary_Email"] == "resume.email@example.com"

    # Mismatch flag must be raised
    assert has_mismatch is True
    assert mismatch_details is not None
    assert "differs from submitted email" in mismatch_details

    # Standard Referral Lifecycle Fields
    assert payload["Source"] == "Employee Referral"
    assert payload["Referred_By"] == "referrer@company.com"
    assert payload["Referral_Approval_Status"] == "Pending"
    assert payload["Referral_Score"] == 85.0

    # Subform packing
    assert "Experience_Details" in payload
    assert len(payload["Experience_Details"]) == 1
    assert payload["Experience_Details"][0]["Company"] == "Prev Co"
