import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.zoho_service import zoho_service

async def main():
    jobs = await zoho_service.get_open_jobs()
    print(f"Total open jobs: {len(jobs)}")
    for j in jobs:
        title = j.get("Posting_Title") or j.get("Job_Opening_Name")
        status = j.get("Job_Opening_Status")
        skills = j.get("Required_Skills")
        print(f"Job ID: {j.get('id')} | Title: {title} | Status: {status} | Skills: {skills}")

if __name__ == "__main__":
    asyncio.run(main())
