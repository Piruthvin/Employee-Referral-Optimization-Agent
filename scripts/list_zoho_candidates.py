import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.zoho_service import zoho_service

async def main():
    cands, _ = await zoho_service.get_all_candidates(page=1, per_page=50)
    print(f"Total candidates in Zoho: {len(cands)}")
    for c in cands:
        name = f"{c.get('First_Name', '')} {c.get('Last_Name', '')}".strip()
        print(f"ID: {c.get('id')} | Name: {name} | Email: {c.get('Email')} | Status: {c.get('Candidate_Status')}")

if __name__ == "__main__":
    asyncio.run(main())
