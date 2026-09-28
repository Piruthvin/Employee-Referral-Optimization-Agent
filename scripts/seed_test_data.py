#!/usr/bin/env python3
"""
scripts/seed_test_data.py

Creates a sample open Job Opening in Zoho Recruit if no active openings exist.
Safety rule: requires explicit --confirm flag to execute writes.
"""

import sys
import argparse
import asyncio
from pathlib import Path

# Add backend to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.services.zoho_service import zoho_service


async def seed(confirm: bool) -> None:
    print("=" * 70)
    print("           Zoho Recruit Test Data Seeder")
    print("=" * 70)

    if not confirm:
        print("[-] Safety gate: This script modifies data in your Zoho Recruit account.")
        print("    To proceed, re-run with: python scripts/seed_test_data.py --confirm")
        sys.exit(0)

    print("[*] Checking for existing open job openings...")
    existing_jobs = await zoho_service.get_open_jobs()
    if existing_jobs:
        print(f"[i] Found {len(existing_jobs)} existing active job openings:")
        for j in existing_jobs[:3]:
            title = j.get("Posting_Title") or j.get("Job_Title") or "Job"
            print(f"    - ID: {j.get('id')} | Title: {title}")
        print("[i] No seeding required. System already has active jobs for matching.")
        return

    print("[*] No active open job openings found. Creating sample job opening...")
    sample_job = {
        "Posting_Title": "Senior Full Stack Python Engineer",
        "Job_Opening_Status": "In-progress",
        "Department_Name": "Engineering",
        "Required_Skills": "Python, FastAPI, React, Docker, PostgreSQL, Redis, Kubernetes",
        "Skill_Set": "Python, FastAPI, React, Docker, PostgreSQL, Redis, Kubernetes",
        "Experience": 3.0,
        "Job_Description": (
            "We are seeking a talented Senior Full Stack Python Engineer to build scalable microservices "
            "using FastAPI and modern React frontend interfaces. Strong experience with Docker and Kubernetes is required."
        ),
    }

    try:
        # Create Job Opening in Zoho
        resp = await zoho_service._request("POST", "JobOpenings", json_data={"data": [sample_job]})
        if resp.status_code in (200, 201):
            data = resp.json().get("data", [{}])[0]
            job_id = data.get("details", {}).get("id")
            print(f"[+] Successfully created test Job Opening! ID: {job_id}")
            print("    Title: Senior Full Stack Python Engineer")
            print("    Skills: Python, FastAPI, React, Docker, PostgreSQL, Redis, Kubernetes")
        else:
            print(f"[-] Failed to create job opening: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[-] Error creating job opening: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed test data in Zoho Recruit")
    parser.add_argument("--confirm", action="store_true", help="Explicit confirmation to create records")
    args = parser.parse_args()
    asyncio.run(seed(args.confirm))
