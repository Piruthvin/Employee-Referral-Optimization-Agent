"""
Live chat testing script covering employee & recruiter chat queries,
testing exact sent and received pairs, and checking for clean non-duplicated responses.
"""

import asyncio
import json
from app.services.igentic_client import igentic_client
from app.core.security import create_session_jwt

async def run_chat_tests():
    emp_email = "piruthvin.official.2@gmail.com"
    rec_email = "piruthvin.official.3@gmail.com"

    test_cases = [
        {
            "category": "Pending Referrals Count (Recruiter)",
            "role": "recruiter",
            "email": rec_email,
            "message": "tell me how many referrals are in pending state",
        },
        {
            "category": "Pending Approvals List (Recruiter)",
            "role": "recruiter",
            "email": rec_email,
            "message": "show pending approvals",
        },
        {
            "category": "Employee Referral Points Inquiry",
            "role": "employee",
            "email": emp_email,
            "message": "what is my referral point?",
        },
        {
            "category": "Employee Alternative Points Inquiry",
            "role": "employee",
            "email": emp_email,
            "message": "how many points do I have?",
        },
        {
            "category": "Top Referrals for Role (Recruiter)",
            "role": "recruiter",
            "email": rec_email,
            "message": "Who are the top referrals for Senior Python Engineer?",
        },
        {
            "category": "Greeting (Employee)",
            "role": "employee",
            "email": emp_email,
            "message": "Hi",
        },
        {
            "category": "Role Guardrail (Employee attempting recruiter approval)",
            "role": "employee",
            "email": emp_email,
            "message": "approve candidate Piruthvin M",
        },
    ]

    print("=" * 80)
    print("LIVE CHAT AGENT TEST EXECUTION")
    print("=" * 80)

    results = []
    for idx, tc in enumerate(test_cases, 1):
        print(f"\n--- Test {idx}: {tc['category']} ---")
        print(f"Role: {tc['role']} | Email: {tc['email']}")
        print(f"Message Sent: {tc['message']}")
        
        try:
            res = await igentic_client.call_sync(
                user_message=tc["message"],
                session_id=f"test-session-{idx}",
                user_email=tc["email"],
                user_role=tc["role"],
            )
            response_text = res.get("response", "")
            print(f"Response Received:\n{response_text}\n")
            
            # Check for duplication or leaked control tokens
            has_leak = "TERMINATE THE PROCESS" in response_text or "TurnToken" in response_text
            duplicate_check = response_text.count("No referral metrics") > 1
            
            results.append({
                "test": tc["category"],
                "sent": tc["message"],
                "role": tc["role"],
                "email": tc["email"],
                "received": response_text,
                "passed": not has_leak and not duplicate_check,
            })
        except Exception as e:
            print(f"Error during test {idx}: {e}")
            results.append({
                "test": tc["category"],
                "sent": tc["message"],
                "role": tc["role"],
                "email": tc["email"],
                "received": f"ERROR: {e}",
                "passed": False,
            })

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        print(f"[{status_str}] {r['test']}")

if __name__ == "__main__":
    asyncio.run(run_chat_tests())
